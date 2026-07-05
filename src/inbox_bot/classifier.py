import asyncio
import base64
import json
import re
import httpx
from importlib import resources
from typing import Any
from urllib.parse import urlparse
from openai import AsyncOpenAI
from inbox_bot.categories import all_category_keys, render_custom_prompt_section
from inbox_bot.config import Settings
from inbox_bot.schemas import ClassifierResult


class ClassifierError(Exception):
    pass


CLASSIFY_TOOL: dict[str, Any] = {
    "name": "classify_item",
    "description": "Classify an inbox item and extract structured fields.",
    "input_schema": {
        "type": "object",
        "required": ["category", "confidence", "raw_text", "fields"],
        "properties": {
            "category": {
                "type": "string",
                "enum": ["restaurant", "place", "todo", "article",
                         "quote", "apparel", "skincare", "photo", "funny", "inbox"],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "raw_text": {"type": "string"},
            "fields": {"type": "object"},
        },
    },
}


def _make_client(settings: Settings) -> AsyncOpenAI:
    if settings.classifier_provider == "gemini":
        return AsyncOpenAI(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
        )
    return AsyncOpenAI(api_key=settings.openai_api_key)


def _load_system_prompt() -> str:
    return resources.files("inbox_bot.prompts").joinpath("classify.md").read_text(encoding="utf-8")


def _build_content(image_bytes: bytes | None, text: str | None) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    if text:
        parts.append({"type": "text", "text": text})
    if not parts:
        parts.append({"type": "text", "text": "(empty)"})
    return parts


# raw_text carries the full OCR of an image, so the response can be long; too low a
# cap truncates the JSON mid-string (JSONDecodeError "Unterminated string").
_MAX_TOKENS = 4096


def _build_openai_tool(keys: list[str]) -> dict[str, Any]:
    schema = {
        "type": "object",
        "required": ["category", "confidence", "raw_text", "fields"],
        "properties": {
            "category": {"type": "string", "enum": keys},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "raw_text": {"type": "string"},
            "fields": {"type": "object"},
        },
    }
    return {"type": "function", "function": {
        "name": "classify_item",
        "description": CLASSIFY_TOOL["description"],
        "parameters": schema,
    }}


def _json_instruction(keys: list[str]) -> str:
    # Gemini's OpenAI-compat endpoint doesn't reliably honor forced tool_choice, so
    # that provider gets a JSON-mode path instead of function calling. This
    # instruction is appended to the system prompt so the model emits exactly the
    # expected shape.
    return (
        "\n\n---\n"
        "Return ONLY a single JSON object — no markdown, no code fences, no prose — "
        "with exactly these keys:\n"
        '- "category": one of ' + ", ".join(keys) + "\n"
        '- "confidence": a number from 0 to 1\n'
        '- "raw_text": a string (OCR of the image, or echo of the input text)\n'
        '- "fields": a JSON object holding the extracted fields for that category\n'
    )


def _strip_fences(raw: str) -> str:
    """Drop a leading ```/```json fence and trailing ``` if the model added them."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if "```" in s:
            s = s[: s.rfind("```")]
    return s.strip()


async def _request_args(
    client: AsyncOpenAI,
    settings: Settings,
    system: str,
    content: list[dict[str, Any]],
    keys: list[str],
) -> dict[str, Any]:
    """Call the model and return the raw classification args dict.

    gemini: JSON mode (response_format) — its OpenAI-compat endpoint doesn't
    reliably honor forced tool_choice. Other providers: forced function call.
    Raises ClassifierError on a structurally empty response (caller won't retry).
    """
    if settings.classifier_provider == "gemini":
        resp = await client.chat.completions.create(
            model=settings.classifier_model,
            max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system + _json_instruction(keys)},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        if not raw:
            raise ClassifierError("no content in response")
        return json.loads(_strip_fences(raw))

    resp = await client.chat.completions.create(
        model=settings.classifier_model,
        max_tokens=_MAX_TOKENS,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        tools=[_build_openai_tool(keys)],
        tool_choice={"type": "function", "function": {"name": "classify_item"}},
    )
    tool_calls = resp.choices[0].message.tool_calls
    if not tool_calls:
        raise ClassifierError("no tool_calls in response")
    return json.loads(tool_calls[0].function.arguments)


_URL_RE = re.compile(r"https?://\S+")
_META_TIMEOUT = 6.0
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


def _bare_single_url(text: str | None) -> str | None:
    """Return the URL iff the message is essentially just one link. A caption
    alongside the link gives the model real content, so those are left to it."""
    if not text:
        return None
    urls = _URL_RE.findall(text)
    if len(urls) != 1:
        return None
    if text.replace(urls[0], "").strip():
        return None
    return urls[0].rstrip(").,]}")


def _extract_link_meta(html: str) -> str | None:
    """Pull a compact preview (site/title/description/type) from a page's
    OpenGraph / twitter / <title> tags. Returns None if nothing useful found."""
    def meta(prop: str) -> str | None:
        pat = re.escape(prop)
        m = re.search(
            r'<meta[^>]+(?:property|name)=["\']' + pat
            + r'["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']'
                + pat + r'["\']', html, re.I)
        return m.group(1).strip() if m else None

    title = meta("og:title") or meta("twitter:title")
    if not title:
        t = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        title = t.group(1).strip() if t else None
    desc = meta("og:description") or meta("twitter:description")
    site = meta("og:site_name")
    otype = meta("og:type")

    parts = []
    if site:
        parts.append(f"網站/site: {site}")
    if title:
        parts.append(f"標題/title: {title}")
    if desc:
        parts.append(f"描述/description: {desc}")
    if otype:
        parts.append(f"og:type: {otype}")
    return "\n".join(parts) if parts else None


async def _fetch_url_context(url: str) -> str | None:
    """Best-effort fetch of a link's preview metadata so the model classifies by
    real content, not a bare URL. Returns None on any failure (timeout, non-HTML,
    blocked) — the caller falls back gracefully."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=_META_TIMEOUT,
            headers={"User-Agent": _BROWSER_UA, "Accept-Language": "zh-TW,zh,en"},
        ) as c:
            resp = await c.get(url)
        if "html" not in resp.headers.get("content-type", "").lower():
            return None
        return _extract_link_meta(resp.text[:200_000])
    except Exception:
        return None


def _youtube_fallback(url: str) -> ClassifierResult | None:
    """If metadata fetch fails, a YouTube link is still reliably a video."""
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if host in ("youtube.com", "m.youtube.com", "youtu.be") or host.endswith(".youtube.com"):
        return ClassifierResult(
            category="article", confidence=1.0, raw_text=url,
            fields={"title": url, "url": url, "type": "影片"},
        )
    return None


async def classify(
    *,
    image_bytes: bytes | None,
    text: str | None,
    settings: Settings,
    client: AsyncOpenAI | None = None,
) -> ClassifierResult:
    # bare links: fetch the page's preview metadata so the model classifies by
    # real content (models can't open URLs; cautious ones dump links to inbox).
    text_for_model = text
    if image_bytes is None:
        bare_url = _bare_single_url(text)
        if bare_url is not None:
            ctx = await _fetch_url_context(bare_url)
            if ctx:
                text_for_model = f"{text}\n\n[連結預覽 link preview]\n{ctx}"
            else:
                fallback = _youtube_fallback(bare_url)
                if fallback is not None:
                    return fallback
                # unknown link with no preview → let the model decide

    if client is None:
        client = _make_client(settings)

    keys = all_category_keys()
    system = _load_system_prompt() + render_custom_prompt_section()
    content = _build_content(image_bytes, text_for_model)

    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            args = await _request_args(client, settings, system, content, keys)
            result = ClassifierResult(**args)
            if result.confidence < settings.confidence_threshold:
                return ClassifierResult(
                    category="inbox",
                    confidence=result.confidence,
                    raw_text=result.raw_text,
                    fields={
                        "original_category": result.category,
                        "reason": "low_confidence",
                        **result.fields,
                    },
                )
            return result
        except ClassifierError:
            # structural failure — don't retry, don't wrap
            raise
        except Exception as e:
            last_err = e
            if attempt == 1:
                await asyncio.sleep(2)
                continue
            raise ClassifierError(f"classifier failed after retry: {e}") from e

    raise ClassifierError(f"unreachable: {last_err}")
