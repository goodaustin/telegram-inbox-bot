import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, quote
from zoneinfo import ZoneInfo
from notion_client import AsyncClient
from inbox_bot.categories import custom_category_keys
from inbox_bot.config import Settings, db_id_for_category
from inbox_bot.schemas import ClassifierResult

log = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0)  # sleeps between attempts (one fewer than attempts)
_FAILED_WRITES_PATH = Path(__file__).resolve().parents[2] / "logs" / "failed_writes.jsonl"


class NotionWriteError(Exception):
    pass


def build_maps_link(name: str, city: str) -> str:
    q = f"{name} {city}".strip()
    return f"https://www.google.com/maps/search/?api=1&query={quote(q)}"


def build_telegram_url(channel_id: int, message_id: int) -> str:
    # Channels start with -100; strip the "-100" prefix for t.me/c/ URLs
    short = str(channel_id).removeprefix("-100")
    return f"https://t.me/c/{short}/{message_id}"


def _title(value: str | None) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": (value or "")[:2000]}}]}


def _text(value: str | None) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": (value or "")[:2000]}}]}


def _select(value: str | None) -> dict[str, Any]:
    return {"select": {"name": (value or "")[:100]}}


def _multi(values: list[str] | None) -> dict[str, Any]:
    # tolerate None and None/empty elements (Gemini JSON mode emits nulls)
    return {"multi_select": [{"name": v[:100]} for v in (values or []) if v]}


def _url(value: str) -> dict[str, Any]:
    return {"url": value or None}


def _date(dt: datetime) -> dict[str, Any]:
    return {"date": {"start": dt.isoformat()}}


def _number(value: Any) -> dict[str, Any]:
    try:
        return {"number": float(value) if value not in (None, "") else None}
    except (TypeError, ValueError):
        return {"number": None}


def _status(name: str) -> dict[str, Any]:
    return {"status": {"name": name}}


def _checkbox(value: bool) -> dict[str, Any]:
    return {"checkbox": value}


def build_properties(
    category: str,
    fields: dict[str, Any],
    telegram_url: str,
    maps_link: str | None,
    now: datetime,
) -> dict[str, dict[str, Any]]:
    g = fields.get  # shorthand

    if category == "restaurant":
        return {
            "Name": _title(g("name", "")),
            "City/Area": _select(g("city", "未知")),
            "Cuisine": _multi(g("cuisine") or []),
            "Maps Link": _url(maps_link or ""),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "place":
        return {
            "Name": _title(g("name", "")),
            "City/Country": _select(g("city", "未知")),
            "Type": _select(g("type", "其他")),
            "Maps Link": _url(maps_link or ""),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "todo":
        deadline = now + timedelta(days=7)
        return {
            "Task": _title(g("task", "")),
            "Deadline": _date(deadline),
            "Status": _status("Not started"),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "article":
        return {
            "Title": _title(g("title", "")),
            "URL": _url(g("url", "")),
            "Publisher": _text(g("publisher", "")),
            "Type": _select(g("type", "文章")),
            "Summary": _text(g("summary", "")),
            "Read?": _checkbox(False),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "quote":
        return {
            "Quote": _title(g("quote", "")),
            "Author": _text(g("author", "")),
            "Tags": _multi(g("tags") or []),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "apparel":
        return {
            "Item": _title(g("item", "")),
            "Brand": _text(g("brand", "")),
            "Type": _select(g("type", "其他")),
            "Price": _number(g("price")),
            "URL": _url(g("url", "")),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "skincare":
        return {
            "Product": _title(g("product", "")),
            "Brand": _text(g("brand", "")),
            "Category": _select(g("category", "其他")),
            "Price": _number(g("price")),
            "URL": _url(g("url", "")),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "photo":
        return {
            "Name": _title(g("description", "")),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "funny":
        return {
            "Name": _title(g("caption", "")),
            "Tags": _multi(g("tags") or []),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category in custom_category_keys():
        return {
            "Name": _title(g("name", "")),
            "Notes": _text(g("notes", "")),
            "Tags": _multi(g("tags") or []),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    # inbox fallback
    return {
        "Raw Text": _title(g("raw_text", "") or fields.get("reason", "")),
        "Reason": _text(f"{g('reason', 'unknown')} (was: {g('original_category', '—')})"),
        "Source": _url(telegram_url),
        "Date Added": _date(now),
    }


async def write_to_notion(
    *,
    result: ClassifierResult,
    telegram_message_url: str,
    image_bytes: bytes | None,
    settings: Settings,
    client: AsyncClient | None = None,
) -> str:
    if client is None:
        client = AsyncClient(auth=settings.notion_token)

    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)

    maps_link = None
    if result.category in ("restaurant", "place"):
        maps_link = build_maps_link(
            result.fields.get("name", ""),
            result.fields.get("city", ""),
        )

    # Drop null-valued fields (Gemini's JSON mode emits explicit nulls for empty
    # fields) so build_properties' per-category defaults apply instead of passing
    # None into _select/_title/_text (which do value[:n] → TypeError).
    fields = {k: v for k, v in result.fields.items() if v is not None}
    # inbox fallback needs raw_text in fields so build_properties can title it
    if result.category == "inbox":
        fields.setdefault("raw_text", result.raw_text)

    properties = build_properties(
        category=result.category,
        fields=fields,
        telegram_url=telegram_message_url,
        maps_link=maps_link,
        now=now,
    )

    db_id = db_id_for_category(result.category, settings)

    # Children: include OCR'd text as a paragraph block for searchability
    children = []
    if result.raw_text:
        children.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text",
                "text": {"content": result.raw_text[:2000]}}]},
        })

    last_err: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            page = await client.pages.create(
                parent={"database_id": db_id},
                properties=properties,
                children=children,
            )
            return page["url"]
        except Exception as e:
            last_err = e
            log.warning("notion write attempt %d failed: %s", attempt, e)
            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(_BACKOFF_SECONDS[attempt - 1])

    # all retries exhausted — append to failed_writes.jsonl
    _FAILED_WRITES_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": now.isoformat(),
        "category": result.category,
        "fields": result.fields,
        "raw_text": result.raw_text,
        "telegram_url": telegram_message_url,
        "error": str(last_err),
    }
    with _FAILED_WRITES_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    raise NotionWriteError(f"notion write failed after {_MAX_ATTEMPTS} attempts: {last_err}") from last_err
