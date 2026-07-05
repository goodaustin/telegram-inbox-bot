import asyncio
import base64
import json
from importlib import resources
from typing import Any
from openai import AsyncOpenAI
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

# OpenAI function-calling wrapper around CLASSIFY_TOOL's schema.
_OPENAI_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": CLASSIFY_TOOL["name"],
        "description": CLASSIFY_TOOL["description"],
        "parameters": CLASSIFY_TOOL["input_schema"],
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


_CATEGORY_ENUM = CLASSIFY_TOOL["input_schema"]["properties"]["category"]["enum"]

# raw_text carries the full OCR of an image, so the response can be long; too low a
# cap truncates the JSON mid-string (JSONDecodeError "Unterminated string").
_MAX_TOKENS = 4096

# Gemini's OpenAI-compat endpoint doesn't reliably honor forced tool_choice, so
# that provider gets a JSON-mode path instead of function calling. This instruction
# is appended to the system prompt so the model emits exactly the expected shape.
_JSON_INSTRUCTION = (
    "\n\n---\n"
    "Return ONLY a single JSON object — no markdown, no code fences, no prose — "
    "with exactly these keys:\n"
    '- "category": one of ' + ", ".join(_CATEGORY_ENUM) + "\n"
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
                {"role": "system", "content": system + _JSON_INSTRUCTION},
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
        tools=[_OPENAI_TOOL],
        tool_choice={"type": "function", "function": {"name": "classify_item"}},
    )
    tool_calls = resp.choices[0].message.tool_calls
    if not tool_calls:
        raise ClassifierError("no tool_calls in response")
    return json.loads(tool_calls[0].function.arguments)


async def classify(
    *,
    image_bytes: bytes | None,
    text: str | None,
    settings: Settings,
    client: AsyncOpenAI | None = None,
) -> ClassifierResult:
    if client is None:
        client = _make_client(settings)

    system = _load_system_prompt()
    content = _build_content(image_bytes, text)

    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            args = await _request_args(client, settings, system, content)
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
