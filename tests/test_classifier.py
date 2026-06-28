import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from inbox_bot.classifier import classify, ClassifierError, CLASSIFY_TOOL
from inbox_bot.config import Settings


@pytest.fixture
def settings(monkeypatch):
    for k, v in {
        "TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHANNEL_ID": "-1001",
        "ANTHROPIC_API_KEY": "x", "NOTION_TOKEN": "x",
        "NOTION_DB_RESTAURANT": "a", "NOTION_DB_PLACE": "b",
        "NOTION_DB_TODO": "c", "NOTION_DB_ARTICLE": "d",
        "NOTION_DB_QUOTE": "e", "NOTION_DB_APPAREL": "f",
        "NOTION_DB_SKINCARE": "g", "NOTION_DB_INBOX": "h",
    }.items():
        monkeypatch.setenv(k, v)
    return Settings()


def make_mock_client(tool_input: dict):
    """Return an AsyncAnthropic-like mock whose .messages.create returns a forced tool_use."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "classify_item"
    tool_block.input = tool_input
    response = MagicMock()
    response.content = [tool_block]
    response.stop_reason = "tool_use"
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


async def test_classify_text_returns_structured_result(settings):
    client = make_mock_client({
        "category": "todo",
        "confidence": 0.9,
        "raw_text": "預約洗牙",
        "fields": {"task": "預約洗牙", "notes": ""},
    })
    result = await classify(image_bytes=None, text="預約洗牙",
                            settings=settings, client=client)
    assert result.category == "todo"
    assert result.fields["task"] == "預約洗牙"
    assert result.confidence == 0.9


async def test_low_confidence_routes_to_inbox(settings):
    client = make_mock_client({
        "category": "restaurant",
        "confidence": 0.4,
        "raw_text": "blurry text",
        "fields": {"name": "??"},
    })
    result = await classify(image_bytes=b"\x89PNG...", text=None,
                            settings=settings, client=client)
    assert result.category == "inbox"
    assert result.fields["original_category"] == "restaurant"
    assert result.fields["reason"] == "low_confidence"


async def test_retries_once_on_api_error(settings):
    from anthropic import APIError
    client = MagicMock()
    # Use a real APIError-like exception
    err = Exception("transient")
    success_block = MagicMock()
    success_block.type = "tool_use"
    success_block.input = {
        "category": "quote", "confidence": 0.9,
        "raw_text": "x", "fields": {"quote": "x", "author": "", "tags": []},
    }
    success_resp = MagicMock()
    success_resp.content = [success_block]
    client.messages.create = AsyncMock(side_effect=[err, success_resp])

    result = await classify(image_bytes=None, text="x",
                            settings=settings, client=client)
    assert result.category == "quote"
    assert client.messages.create.await_count == 2


async def test_raises_after_second_failure(settings):
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=Exception("perm fail"))
    with pytest.raises(ClassifierError):
        await classify(image_bytes=None, text="x",
                       settings=settings, client=client)


async def test_does_not_retry_on_structural_error(settings):
    """When forced tool_use somehow returns no tool_use block, fail fast (no retry)."""
    text_block = MagicMock()
    text_block.type = "text"  # not tool_use
    text_block.input = None
    response = MagicMock()
    response.content = [text_block]
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)

    with pytest.raises(ClassifierError):
        await classify(image_bytes=None, text="x",
                       settings=settings, client=client)
    # MUST be exactly 1 call — no retry on structural failure
    assert client.messages.create.await_count == 1


def test_classify_tool_schema_includes_all_categories():
    enum = CLASSIFY_TOOL["input_schema"]["properties"]["category"]["enum"]
    assert set(enum) == {"restaurant", "place", "todo", "article",
                         "quote", "apparel", "skincare", "inbox"}
