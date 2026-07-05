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
        "NOTION_DB_SKINCARE": "g", "NOTION_DB_PHOTO": "p", "NOTION_DB_FUNNY": "fn", "NOTION_DB_INBOX": "h",
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
                         "quote", "apparel", "skincare", "photo", "funny", "inbox"}


def test_make_client_openai_uses_api_key(settings, monkeypatch):
    import inbox_bot.classifier as clf
    fake = MagicMock()
    monkeypatch.setattr(clf, "AsyncOpenAI", fake)
    clf._make_client(settings)
    fake.assert_called_once_with(api_key=settings.openai_api_key)


def test_make_client_gemini_uses_base_url(monkeypatch):
    import inbox_bot.classifier as clf
    from inbox_bot.config import Settings
    env = {
        "TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHANNEL_ID": "-1001",
        "NOTION_TOKEN": "x", "CLASSIFIER_PROVIDER": "gemini", "GEMINI_API_KEY": "gm-x",
        "NOTION_DB_RESTAURANT": "a", "NOTION_DB_PLACE": "b", "NOTION_DB_TODO": "c",
        "NOTION_DB_ARTICLE": "d", "NOTION_DB_QUOTE": "e", "NOTION_DB_APPAREL": "f",
        "NOTION_DB_SKINCARE": "g", "NOTION_DB_PHOTO": "p", "NOTION_DB_FUNNY": "fn",
        "NOTION_DB_INBOX": "h",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s = Settings(_env_file=None)
    fake = MagicMock()
    monkeypatch.setattr(clf, "AsyncOpenAI", fake)
    clf._make_client(s)
    fake.assert_called_once_with(api_key="gm-x", base_url=s.gemini_base_url)


def _make_json_response(payload: dict):
    """A chat-completion whose message carries JSON in .content (no tool_calls) —
    how Gemini's OpenAI-compat endpoint replies under response_format json mode."""
    message = MagicMock()
    message.content = json.dumps(payload)
    message.tool_calls = None
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture
def gemini_settings(monkeypatch):
    for k, v in {
        "TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHANNEL_ID": "-1001",
        "NOTION_TOKEN": "x", "CLASSIFIER_PROVIDER": "gemini",
        "GEMINI_API_KEY": "gm-x", "CLASSIFIER_MODEL": "gemini-2.5-flash",
        "NOTION_DB_RESTAURANT": "a", "NOTION_DB_PLACE": "b",
        "NOTION_DB_TODO": "c", "NOTION_DB_ARTICLE": "d",
        "NOTION_DB_QUOTE": "e", "NOTION_DB_APPAREL": "f",
        "NOTION_DB_SKINCARE": "g", "NOTION_DB_PHOTO": "p",
        "NOTION_DB_FUNNY": "fn", "NOTION_DB_INBOX": "h",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return Settings(_env_file=None)


async def test_gemini_uses_json_response_format(gemini_settings):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_make_json_response({
        "category": "todo", "confidence": 0.9,
        "raw_text": "買牛奶", "fields": {"task": "買牛奶"},
    }))
    result = await classify(image_bytes=None, text="買牛奶",
                            settings=gemini_settings, client=client)
    assert result.category == "todo"
    assert result.fields["task"] == "買牛奶"
    kwargs = client.chat.completions.create.await_args.kwargs
    # gemini path must use JSON mode and must NOT send function tools
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "tools" not in kwargs
    # token cap must be generous — raw_text (OCR) truncation breaks JSON parsing
    assert kwargs["max_tokens"] >= 2048


def test_bare_single_url_extracts():
    from inbox_bot.classifier import _bare_single_url
    assert _bare_single_url("https://youtu.be/x") == "https://youtu.be/x"


def test_bare_single_url_none_for_caption():
    from inbox_bot.classifier import _bare_single_url
    # a caption gives the model real content — don't treat as a bare link
    assert _bare_single_url("好好笑 https://youtu.be/x") is None


def test_bare_single_url_none_for_plain_text():
    from inbox_bot.classifier import _bare_single_url
    assert _bare_single_url("買牛奶") is None


def test_extract_link_meta_parses_og():
    from inbox_bot.classifier import _extract_link_meta
    html = ('<html><head>'
            '<meta property="og:title" content="東京自由行攻略">'
            '<meta property="og:description" content="景點與美食推薦">'
            '<meta property="og:site_name" content="Instagram">'
            '</head></html>')
    meta = _extract_link_meta(html)
    assert meta is not None
    assert "東京自由行攻略" in meta and "景點與美食推薦" in meta


def test_extract_link_meta_none_when_empty():
    from inbox_bot.classifier import _extract_link_meta
    assert _extract_link_meta("<html><body>nothing here</body></html>") is None


async def test_classify_enriches_bare_url_with_preview(gemini_settings, monkeypatch):
    import inbox_bot.classifier as clf

    async def fake_fetch(url):
        return "標題/title: 東京自由行\n描述/description: 景點推薦"
    monkeypatch.setattr(clf, "_fetch_url_context", fake_fetch)

    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_make_json_response({
        "category": "place", "confidence": 0.9,
        "raw_text": "x", "fields": {"name": "東京", "city": "東京/日本"},
    }))
    result = await classify(image_bytes=None,
                            text="https://www.instagram.com/p/ABC/",
                            settings=gemini_settings, client=client)
    assert result.category == "place"
    # the fetched preview must have been handed to the model
    sent = client.chat.completions.create.await_args.kwargs["messages"][1]["content"]
    assert "東京自由行" in json.dumps(sent, ensure_ascii=False)


async def test_classify_youtube_fallback_when_fetch_fails(gemini_settings, monkeypatch):
    import inbox_bot.classifier as clf

    async def fake_fetch(url):
        return None
    monkeypatch.setattr(clf, "_fetch_url_context", fake_fetch)

    client = MagicMock()
    client.chat.completions.create = AsyncMock()
    result = await classify(image_bytes=None, text="https://youtu.be/x",
                            settings=gemini_settings, client=client)
    assert result.category == "article" and result.fields["type"] == "影片"
    client.chat.completions.create.assert_not_awaited()


async def test_classify_unknown_link_no_preview_goes_to_model(gemini_settings, monkeypatch):
    import inbox_bot.classifier as clf

    async def fake_fetch(url):
        return None
    monkeypatch.setattr(clf, "_fetch_url_context", fake_fetch)

    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_make_json_response({
        "category": "inbox", "confidence": 0.9,
        "raw_text": "x", "fields": {"reason": "no preview"},
    }))
    result = await classify(image_bytes=None,
                            text="https://www.threads.net/@x/post/1",
                            settings=gemini_settings, client=client)
    # no longer hardcoded to funny — the model decides
    assert result.category == "inbox"
    client.chat.completions.create.assert_awaited()


async def test_gemini_strips_code_fences(gemini_settings):
    fenced = MagicMock()
    fenced.content = ('```json\n{"category": "quote", "confidence": 0.9, '
                      '"raw_text": "x", "fields": {"quote": "x"}}\n```')
    fenced.tool_calls = None
    choice = MagicMock()
    choice.message = fenced
    resp = MagicMock()
    resp.choices = [choice]
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=resp)
    result = await classify(image_bytes=None, text="x",
                            settings=gemini_settings, client=client)
    assert result.category == "quote"


from inbox_bot.classifier import _build_openai_tool, _json_instruction


def test_build_openai_tool_uses_given_keys():
    tool = _build_openai_tool(["todo", "recipe"])
    enum = tool["function"]["parameters"]["properties"]["category"]["enum"]
    assert enum == ["todo", "recipe"]


def test_json_instruction_lists_keys():
    instr = _json_instruction(["todo", "recipe"])
    assert "todo" in instr and "recipe" in instr


async def test_classify_accepts_custom_category(settings, monkeypatch):
    # patch the single source (get_custom_categories) so the enum, the prompt
    # section, AND ClassifierResult validation all see the custom key.
    import inbox_bot.categories as cats
    from inbox_bot.categories import CustomCategory
    monkeypatch.setattr(cats, "get_custom_categories",
                        lambda: [CustomCategory("recipe", "食譜", "食譜、料理")])
    client = make_mock_client({
        "category": "recipe", "confidence": 0.9,
        "raw_text": "番茄炒蛋做法", "fields": {"name": "番茄炒蛋", "notes": "", "tags": []},
    })
    result = await classify(image_bytes=None, text="番茄炒蛋做法", settings=settings, client=client)
    assert result.category == "recipe"
    assert result.fields["name"] == "番茄炒蛋"
