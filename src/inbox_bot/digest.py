import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo
from notion_client import AsyncClient as NotionAsyncClient
from telegram import Bot
from inbox_bot.config import Settings

log = logging.getLogger(__name__)


async def query_open_todos(client: NotionAsyncClient, settings: Settings) -> list[dict[str, Any]]:
    resp = await client.databases.query(
        database_id=settings.notion_db_todo,
        filter={"property": "Status", "status": {"does_not_equal": "Done"}},
        sorts=[{"property": "Deadline", "direction": "ascending"}],
    )
    todos = []
    for row in resp.get("results", []):
        props = row.get("properties", {})
        title = props.get("Task", {}).get("title", [])
        task = title[0]["plain_text"] if title else "(untitled)"
        deadline = (props.get("Deadline", {}).get("date") or {}).get("start", "")
        todos.append({"task": task, "deadline": deadline})
    return todos


async def query_unread_articles(
    client: NotionAsyncClient, settings: Settings, limit: int = 10
) -> list[dict[str, Any]]:
    resp = await client.databases.query(
        database_id=settings.notion_db_article,
        filter={"property": "Read?", "checkbox": {"equals": False}},
        sorts=[{"property": "Date Added", "direction": "descending"}],
        page_size=limit,
    )
    articles = []
    for row in resp.get("results", []):
        props = row.get("properties", {})
        t = props.get("Title", {}).get("title", [])
        title = t[0]["plain_text"] if t else "(untitled)"
        p = props.get("Publisher", {}).get("rich_text", [])
        publisher = p[0]["plain_text"] if p else ""
        articles.append({"title": title, "publisher": publisher})
    return articles


def _format_date(d: str) -> str:
    # "2026-06-30" → "6/30"
    try:
        dt = datetime.fromisoformat(d)
        return f"{dt.month}/{dt.day}"
    except ValueError:
        return d


def format_digest(
    now: datetime,
    todos: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    articles_db_id: str,
) -> str:
    today = now.date()
    overdue = [t for t in todos if t["deadline"] and datetime.fromisoformat(t["deadline"]).date() < today]
    this_week = [t for t in todos if t["deadline"] and today <= datetime.fromisoformat(t["deadline"]).date() <= today + timedelta(days=7)]
    later = [t for t in todos if t["deadline"] and datetime.fromisoformat(t["deadline"]).date() > today + timedelta(days=7)]

    weekday_name = "週日"  # this only ever runs on Sunday
    lines = [f"☀️ 早安 — 本週清單 ({weekday_name} {now.month}/{now.day})",
             "─" * 18]

    if overdue:
        lines.append(f"\n⚠️ 已過期 ({len(overdue)})")
        for t in overdue:
            lines.append(f"• {_format_date(t['deadline'])} - {t['task']}")

    if this_week:
        lines.append(f"\n📅 本週到期 ({len(this_week)})")
        for t in this_week:
            lines.append(f"• {_format_date(t['deadline'])} - {t['task']}")

    if later:
        lines.append(f"\n📆 之後 ({len(later)})")
        for t in later[:5]:
            lines.append(f"• {_format_date(t['deadline'])} - {t['task']}")

    if not (overdue or this_week or later):
        lines.append("\n✨ 沒有待辦事項")

    if articles:
        lines.append(f"\n📖 待讀待看 ({len(articles)} 篇)")
        for a in articles[:5]:
            pub = f"({a['publisher']})" if a["publisher"] else ""
            lines.append(f"• 「{a['title']}」{pub}")
        if len(articles) > 5:
            lines.append(f"   👉 全部: https://www.notion.so/{articles_db_id.replace('-', '')}")
    else:
        lines.append("\n📭 沒有待讀待看")

    return "\n".join(lines)


async def send_digest(
    settings: Settings,
    *,
    telegram_bot: Bot | None = None,
    notion_client: NotionAsyncClient | None = None,
) -> None:
    if notion_client is None:
        notion_client = NotionAsyncClient(auth=settings.notion_token)
    if telegram_bot is None:
        telegram_bot = Bot(token=settings.telegram_bot_token)

    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)

    todos = await query_open_todos(notion_client, settings)
    articles = await query_unread_articles(notion_client, settings)

    text = format_digest(now, todos, articles, articles_db_id=settings.notion_db_article)

    try:
        await telegram_bot.send_message(
            chat_id=settings.telegram_channel_id,
            text=text,
        )
    except Exception:
        log.exception("digest send failed")
        # last-ditch: still raise so apscheduler logs it
        raise
