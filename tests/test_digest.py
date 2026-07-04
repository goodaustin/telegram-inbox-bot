from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo
import pytest
from freezegun import freeze_time
from inbox_bot.digest import format_digest, send_digest
from inbox_bot.config import Settings


@pytest.fixture
def settings(monkeypatch):
    for k, v in {
        "TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHANNEL_ID": "-1001234567890",
        "OPENAI_API_KEY": "x", "NOTION_TOKEN": "x",
        "NOTION_DB_RESTAURANT": "a", "NOTION_DB_PLACE": "b",
        "NOTION_DB_TODO": "c", "NOTION_DB_ARTICLE": "d",
        "NOTION_DB_QUOTE": "e", "NOTION_DB_APPAREL": "f",
        "NOTION_DB_SKINCARE": "g", "NOTION_DB_PHOTO": "p", "NOTION_DB_FUNNY": "fn", "NOTION_DB_INBOX": "h",
    }.items():
        monkeypatch.setenv(k, v)
    return Settings()


def test_format_digest_separates_overdue_and_this_week():
    now = datetime(2026, 6, 28, 7, 30, tzinfo=ZoneInfo("Asia/Taipei"))
    todos = [
        {"task": "預約洗牙", "deadline": "2026-06-25"},   # overdue
        {"task": "回信 Jenny", "deadline": "2026-06-27"}, # overdue
        {"task": "訂端午高鐵", "deadline": "2026-06-30"},  # this week
        {"task": "換護照", "deadline": "2026-07-02"},     # this week
    ]
    articles = [
        {"title": "LLM 推論成本", "publisher": "Substack"},
        {"title": "Q2 半導體", "publisher": "財訊"},
    ]
    msg = format_digest(now, todos, articles, articles_db_id="d")
    assert "已過期 (2)" in msg
    assert "預約洗牙" in msg
    assert "本週到期 (2)" in msg
    assert "訂端午高鐵" in msg
    assert "待讀待看 (2 篇)" in msg
    assert "LLM 推論成本" in msg
    assert "週日" in msg


def test_format_digest_empty_lists():
    now = datetime(2026, 6, 28, 7, 30, tzinfo=ZoneInfo("Asia/Taipei"))
    msg = format_digest(now, [], [], articles_db_id="d")
    assert "沒有待辦" in msg or "✨" in msg
    assert "沒有待讀" in msg or "📭" in msg


@freeze_time("2026-06-28 07:30:00", tz_offset=0)
async def test_send_digest_pushes_to_telegram_channel(settings):
    notion = MagicMock()
    notion.databases.query = AsyncMock(side_effect=[
        # todos query response
        {"results": [
            {"properties": {
                "Task": {"title": [{"plain_text": "預約洗牙"}]},
                "Deadline": {"date": {"start": "2026-06-30"}},
            }}
        ]},
        # articles query response
        {"results": [
            {"properties": {
                "Title": {"title": [{"plain_text": "LLM 文章"}]},
                "Publisher": {"rich_text": [{"plain_text": "Substack"}]},
            }}
        ]},
    ])
    tg = MagicMock()
    tg.send_message = AsyncMock()

    await send_digest(settings, telegram_bot=tg, notion_client=notion)

    tg.send_message.assert_awaited_once()
    kwargs = tg.send_message.await_args.kwargs
    assert kwargs["chat_id"] == -1001234567890
    text = kwargs["text"]
    assert "預約洗牙" in text
    assert "LLM 文章" in text
