import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from inbox_bot.classifier import classify, ClassifierError, CLASSIFY_TOOL
from inbox_bot.config import Settings


@pytest.fixture
def settings(monkeypatch):
    for k, v in {
        "TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHANNEL_ID": "-1001",
        "OPENAI_API_KEY": "x", "NOTION_TOKEN": "x",
        "NOTION_DB_RESTAURANT": "a", "NOTION_DB_PLACE": "b",
        "NOTION_DB_TODO": "c", "NOTION_DB_ARTICLE": "d",
        "NOTION_DB_QUOTE": "e", "NOTION_DB_APPAREL": "f",
        "NOTION_DB_SKINCARE": "g", "NOTION_DB_PHOTO": "p", "NOTION_DB_INBOX": "h",
    }.items():
        monkeypatch.setenv(k, v)
    return Settings()


def _make_response(tool_arguments: dict):
    """Build an OpenAI-like chat completion carrying a forced function tool_call.

    OpenAI returns tool-call arguments as a JSON *string* under
    resp.choices[0].message.tool_calls[0].function.arguments.
    """
    fn = MagicMock()
    fn.name = "classify_item"
    fn.arguments = json.dumps(tool_arguments)
    tool_call = MagicMock()
    tool_call.function = fn
    message = MagicMock()
    message.tool_calls = [tool_call]
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def make_mock_client(tool_arguments: dict):
    """Return an AsyncOpenAI-like mock whose chat.completions.create returns a forced tool call."""
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_make_response(tool_arguments))
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
    err = Exception("transient")
    success = _make_response({
        "category": "quote", "confidence": 0.9,
        "raw_text": "x", "fields": {"quote": "x", "author": "", "tags": []},
    })
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=[err, success])

    result = await classify(image_bytes=None, text="x",
                            settings=settings, client=client)
    assert result.category == "quote"
    assert client.chat.completions.create.await_count == 2


async def test_raises_after_second_failure(settings):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=Exception("perm fail"))
    with pytest.raises(ClassifierError):
        await classify(image_bytes=None, text="x",
                       settings=settings, client=client)


async def test_does_not_retry_on_structural_error(settings):
    """When the forced call somehow returns no tool_calls, fail fast (no retry)."""
    message = MagicMock()
    message.tool_calls = None  # no tool call present
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    with pytest.raises(ClassifierError):
        await classify(image_bytes=None, text="x",
                       settings=settings, client=client)
    # MUST be exactly 1 call — no retry on structural failure
    assert client.chat.completions.create.await_count == 1


def test_classify_tool_schema_includes_all_categories():
    enum = CLASSIFY_TOOL["input_schema"]["properties"]["category"]["enum"]
    assert set(enum) == {"restaurant", "place", "todo", "article",
                         "quote", "apparel", "skincare", "photo", "inbox"}
