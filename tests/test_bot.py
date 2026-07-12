from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from freezegun import freeze_time
from inbox_bot.bot import handle_channel_post, _route_life_command, CATEGORY_EMOJI
from inbox_bot.config import Settings
from inbox_bot.schemas import ClassifierResult


def _life_post():
    post = MagicMock()
    post.reply_text = AsyncMock()
    post.reply_to_message = None
    return post


def _life_settings(tmp_path):
    return SimpleNamespace(life_dir=str(tmp_path), timezone="Asia/Taipei")


@freeze_time("2026-07-13 06:00:00")  # = 14:00 台北時間 2026-07-13
async def test_j_backfill_without_space_writes_yesterday(tmp_path):
    post = _life_post()
    handled = await _route_life_command(post, "/j-1 昨天漏記的", _life_settings(tmp_path))
    assert handled is True
    p = tmp_path / "journal" / "2026" / "2026-07-12.md"
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "昨天漏記的" in text
    assert "[補記]" in text
    post.reply_text.assert_awaited()


@freeze_time("2026-07-13 06:00:00")
async def test_j_offset_without_content_replies_hint_and_writes_nothing(tmp_path):
    post = _life_post()
    handled = await _route_life_command(post, "/j -1", _life_settings(tmp_path))
    assert handled is True
    assert not (tmp_path / "journal" / "2026" / "2026-07-13.md").exists()
    assert not (tmp_path / "journal" / "2026" / "2026-07-12.md").exists()
    reply = post.reply_text.await_args.args[0]
    assert "內容" in reply


@freeze_time("2026-07-13 06:00:00")
async def test_j_with_space_and_content_writes_today(tmp_path):
    post = _life_post()
    handled = await _route_life_command(post, "/j 今天寫的", _life_settings(tmp_path))
    assert handled is True
    p = tmp_path / "journal" / "2026" / "2026-07-13.md"
    assert p.exists()
    assert "今天寫的" in p.read_text(encoding="utf-8")


async def test_jog_is_not_treated_as_journal(tmp_path):
    post = _life_post()
    handled = await _route_life_command(post, "/jog 隨便打", _life_settings(tmp_path))
    assert handled is False
    assert not (tmp_path / "journal").exists()


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


def _make_update_with_text(message_id: int, text: str, channel_id: int):
    update = MagicMock()
    update.channel_post.message_id = message_id
    update.channel_post.text = text
    update.channel_post.caption = None
    update.channel_post.photo = []
    update.channel_post.chat.id = channel_id
    update.channel_post.reply_text = AsyncMock()
    return update


def _make_update_with_photo(message_id: int, caption: str | None, channel_id: int):
    photo_size = MagicMock()
    photo_size.file_id = "FILE_ID_X"
    update = MagicMock()
    update.channel_post.message_id = message_id
    update.channel_post.text = None
    update.channel_post.caption = caption
    update.channel_post.photo = [photo_size]  # smallest, largest in real API
    update.channel_post.chat.id = channel_id
    update.channel_post.reply_text = AsyncMock()
    return update


def _make_context_with_settings(settings: Settings):
    ctx = MagicMock()
    ctx.bot_data = {"settings": settings}
    ctx.bot.get_file = AsyncMock()
    return ctx


async def test_text_message_flows_to_notion(settings):
    update = _make_update_with_text(42, "預約洗牙", -1001234567890)
    ctx = _make_context_with_settings(settings)

    with patch("inbox_bot.bot.classify", new=AsyncMock(return_value=ClassifierResult(
            category="todo", confidence=0.9, raw_text="預約洗牙",
            fields={"task": "預約洗牙"}))) as mock_classify, \
         patch("inbox_bot.bot.write_to_notion", new=AsyncMock(
             return_value="https://notion.so/page_xyz")) as mock_write:
        await handle_channel_post(update, ctx)

    mock_classify.assert_awaited_once()
    mock_write.assert_awaited_once()
    update.channel_post.reply_text.assert_awaited_once()
    reply = update.channel_post.reply_text.await_args.args[0]
    assert CATEGORY_EMOJI["todo"] in reply
    assert "https://notion.so/page_xyz" in reply


async def test_photo_downloads_largest_size_and_classifies(settings):
    update = _make_update_with_photo(7, "看起來不錯", -1001234567890)
    # add a second, larger photo size
    larger = MagicMock(); larger.file_id = "FILE_BIG"
    update.channel_post.photo.append(larger)

    file_mock = AsyncMock()
    file_mock.download_as_bytearray = AsyncMock(return_value=bytearray(b"\x89PNGFAKE"))

    ctx = _make_context_with_settings(settings)
    ctx.bot.get_file = AsyncMock(return_value=file_mock)

    with patch("inbox_bot.bot.classify", new=AsyncMock(return_value=ClassifierResult(
            category="restaurant", confidence=0.9, raw_text="x",
            fields={"name": "X", "city": "台北/信義"}))) as mock_classify, \
         patch("inbox_bot.bot.write_to_notion", new=AsyncMock(
             return_value="https://notion.so/p")):
        await handle_channel_post(update, ctx)

    ctx.bot.get_file.assert_awaited_once_with("FILE_BIG")
    kwargs = mock_classify.await_args.kwargs
    assert kwargs["image_bytes"] == bytes(b"\x89PNGFAKE")
    assert kwargs["text"] == "看起來不錯"


def test_category_emoji_covers_all_categories():
    from typing import get_args
    from inbox_bot.schemas import Category
    missing = set(get_args(Category)) - set(CATEGORY_EMOJI)
    assert not missing, f"CATEGORY_EMOJI missing: {missing}"


async def test_classifier_error_replies_with_failure_and_writes_to_inbox(settings):
    from inbox_bot.classifier import ClassifierError
    update = _make_update_with_text(99, "x", -1001234567890)
    ctx = _make_context_with_settings(settings)

    with patch("inbox_bot.bot.classify", new=AsyncMock(side_effect=ClassifierError("boom"))), \
         patch("inbox_bot.bot.write_to_notion", new=AsyncMock(
             return_value="https://notion.so/inbox_p")) as mock_write:
        await handle_channel_post(update, ctx)

    # Must have written to Notion (Inbox DB), via a fallback ClassifierResult
    mock_write.assert_awaited_once()
    inbox_result = mock_write.await_args.kwargs["result"]
    assert inbox_result.category == "inbox"
    reply = update.channel_post.reply_text.await_args.args[0]
    assert "❌ 分類失敗" in reply
