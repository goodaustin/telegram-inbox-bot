import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo
import pytest
from inbox_bot.notion_writer import (
    build_maps_link, build_telegram_url, build_properties, write_to_notion,
    NotionWriteError,
)
from inbox_bot.schemas import ClassifierResult
from inbox_bot.config import Settings


@pytest.fixture
def settings(monkeypatch):
    for k, v in {
        "TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHANNEL_ID": "-1001234567890",
        "OPENAI_API_KEY": "x", "NOTION_TOKEN": "x",
        "NOTION_DB_RESTAURANT": "db_rest", "NOTION_DB_PLACE": "db_place",
        "NOTION_DB_TODO": "db_todo", "NOTION_DB_ARTICLE": "db_article",
        "NOTION_DB_QUOTE": "db_quote", "NOTION_DB_APPAREL": "db_apparel",
        "NOTION_DB_SKINCARE": "db_skincare", "NOTION_DB_PHOTO": "db_photo",
        "NOTION_DB_INBOX": "db_inbox",
    }.items():
        monkeypatch.setenv(k, v)
    return Settings()


def test_maps_link_encodes_query():
    url = build_maps_link("Maisen", "東京/表參道")
    assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "Maisen" in url
    # encoded Chinese
    assert "%E6%9D%B1%E4%BA%AC" in url


def test_telegram_url_strips_100_prefix():
    # channel -1001234567890 → t.me/c/1234567890/<msg>
    url = build_telegram_url(-1001234567890, 42)
    assert url == "https://t.me/c/1234567890/42"


def test_build_properties_restaurant():
    now = datetime(2026, 6, 28, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="restaurant",
        fields={"name": "Maisen", "city": "東京/表參道",
                "cuisine": ["日料", "炸物"], "notes": ""},
        telegram_url="https://t.me/c/1/2",
        maps_link="https://maps.google.com/...",
        now=now,
    )
    assert props["Name"]["title"][0]["text"]["content"] == "Maisen"
    assert props["City/Area"]["select"]["name"] == "東京/表參道"
    assert {o["name"] for o in props["Cuisine"]["multi_select"]} == {"日料", "炸物"}
    assert props["Maps Link"]["url"].startswith("https://maps.google")
    assert props["Source"]["url"] == "https://t.me/c/1/2"
    assert props["Date Added"]["date"]["start"].startswith("2026-06-28")


def test_build_properties_todo_sets_deadline_plus_7_days():
    now = datetime(2026, 6, 28, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="todo",
        fields={"task": "預約洗牙", "notes": ""},
        telegram_url="https://t.me/c/1/2",
        maps_link=None,
        now=now,
    )
    assert props["Task"]["title"][0]["text"]["content"] == "預約洗牙"
    # 2026-06-28 + 7 days = 2026-07-05
    assert props["Deadline"]["date"]["start"].startswith("2026-07-05")
    assert props["Status"]["status"]["name"] == "Not started"


def test_build_properties_photo_has_no_status():
    now = datetime(2026, 7, 4, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="photo",
        fields={"description": "京都嵐山竹林", "notes": "構圖漂亮"},
        telegram_url="https://t.me/c/1/2",
        maps_link=None,
        now=now,
    )
    assert props["Name"]["title"][0]["text"]["content"] == "京都嵐山竹林"
    assert props["Notes"]["rich_text"][0]["text"]["content"] == "構圖漂亮"
    assert props["Source"]["url"] == "https://t.me/c/1/2"
    assert "Status" not in props


def test_build_properties_inbox_minimal():
    now = datetime(2026, 6, 28, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="inbox",
        fields={"reason": "low_confidence", "original_category": "restaurant"},
        telegram_url="https://t.me/c/1/2",
        maps_link=None,
        now=now,
    )
    assert "Raw Text" in props
    assert props["Reason"]["rich_text"][0]["text"]["content"].startswith("low_confidence")


def test_build_properties_place_smoke():
    now = datetime(2026, 6, 28, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="place",
        fields={"name": "Louvre", "city": "Paris/France", "type": "景點", "notes": ""},
        telegram_url="https://t.me/c/1/2",
        maps_link="https://maps.google.com/x",
        now=now,
    )
    assert props["Name"]["title"][0]["text"]["content"] == "Louvre"
    assert props["City/Country"]["select"]["name"] == "Paris/France"
    assert props["Type"]["select"]["name"] == "景點"


def test_build_properties_article_smoke():
    now = datetime(2026, 6, 28, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="article",
        fields={"title": "X", "url": "https://x", "publisher": "Y", "summary": "z"},
        telegram_url="https://t.me/c/1/2", maps_link=None, now=now,
    )
    assert props["Title"]["title"][0]["text"]["content"] == "X"
    assert props["URL"]["url"] == "https://x"
    assert props["Read?"]["checkbox"] is False


def test_build_properties_article_has_type_select():
    now = datetime(2026, 7, 4, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="article",
        fields={"title": "某影片", "url": "https://youtu.be/x",
                "publisher": "某頻道", "summary": "s", "type": "影片"},
        telegram_url="https://t.me/c/1/2", maps_link=None, now=now,
    )
    assert props["Type"]["select"]["name"] == "影片"


def test_build_properties_article_type_defaults_to_文章():
    now = datetime(2026, 7, 4, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="article",
        fields={"title": "X", "url": "", "publisher": "", "summary": ""},
        telegram_url="https://t.me/c/1/2", maps_link=None, now=now,
    )
    assert props["Type"]["select"]["name"] == "文章"


def test_build_properties_quote_smoke():
    now = datetime(2026, 6, 28, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="quote",
        fields={"quote": "Q", "author": "A", "tags": ["t1"]},
        telegram_url="https://t.me/c/1/2", maps_link=None, now=now,
    )
    assert props["Quote"]["title"][0]["text"]["content"] == "Q"
    assert props["Author"]["rich_text"][0]["text"]["content"] == "A"


def test_build_properties_apparel_smoke():
    now = datetime(2026, 6, 28, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="apparel",
        fields={"item": "shirt", "brand": "B", "type": "上衣", "price": 999, "url": "", "notes": ""},
        telegram_url="https://t.me/c/1/2", maps_link=None, now=now,
    )
    assert props["Item"]["title"][0]["text"]["content"] == "shirt"
    assert props["Type"]["select"]["name"] == "上衣"
    assert props["Price"]["number"] == 999.0


def test_build_properties_skincare_smoke():
    now = datetime(2026, 6, 28, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="skincare",
        fields={"product": "Cream", "brand": "B", "category": "乳液",
                "price": "1500", "url": "", "notes": ""},
        telegram_url="https://t.me/c/1/2", maps_link=None, now=now,
    )
    assert props["Product"]["title"][0]["text"]["content"] == "Cream"
    assert props["Category"]["select"]["name"] == "乳液"
    assert props["Price"]["number"] == 1500.0


async def test_write_to_notion_dispatches_to_correct_db(settings):
    client = MagicMock()
    client.pages.create = AsyncMock(return_value={"id": "page_x", "url": "https://notion.so/page_x"})
    result = ClassifierResult(
        category="quote", confidence=0.9, raw_text="x",
        fields={"quote": "x", "author": "", "tags": []},
    )
    url = await write_to_notion(
        result=result,
        telegram_message_url="https://t.me/c/1/2",
        image_bytes=None,
        settings=settings,
        client=client,
    )
    assert url == "https://notion.so/page_x"
    args, kwargs = client.pages.create.call_args
    assert kwargs["parent"]["database_id"] == "db_quote"


async def test_write_to_notion_retries_on_transient_failure(settings, monkeypatch):
    monkeypatch.setattr("inbox_bot.notion_writer._BACKOFF_SECONDS", (0, 0))
    client = MagicMock()
    client.pages.create = AsyncMock(side_effect=[
        Exception("rate limit"),
        Exception("rate limit"),
        {"id": "p", "url": "https://notion.so/p"},
    ])
    result = ClassifierResult(category="quote", confidence=0.9, raw_text="x",
                              fields={"quote": "x"})
    url = await write_to_notion(
        result=result, telegram_message_url="https://t.me/c/1/2",
        image_bytes=None, settings=settings, client=client,
    )
    assert url == "https://notion.so/p"
    assert client.pages.create.await_count == 3


async def test_write_to_notion_after_all_retries_appends_to_jsonl(
    settings, monkeypatch, tmp_path
):
    monkeypatch.setattr("inbox_bot.notion_writer._BACKOFF_SECONDS", (0, 0))
    monkeypatch.setattr("inbox_bot.notion_writer._FAILED_WRITES_PATH",
                        tmp_path / "failed_writes.jsonl")
    client = MagicMock()
    client.pages.create = AsyncMock(side_effect=Exception("permanent"))
    result = ClassifierResult(category="quote", confidence=0.9, raw_text="x",
                              fields={"quote": "x"})

    with pytest.raises(NotionWriteError):
        await write_to_notion(
            result=result, telegram_message_url="https://t.me/c/1/2",
            image_bytes=None, settings=settings, client=client,
        )
    assert client.pages.create.await_count == 3

    jsonl = (tmp_path / "failed_writes.jsonl").read_text().splitlines()
    assert len(jsonl) == 1
    record = json.loads(jsonl[0])
    assert record["category"] == "quote"
    assert record["telegram_url"] == "https://t.me/c/1/2"
    assert "error" in record
