import os
import pytest
from inbox_bot.config import Settings, db_id_for_category


@pytest.fixture
def fake_env(monkeypatch):
    env = {
        "TELEGRAM_BOT_TOKEN": "123:abc",
        "TELEGRAM_CHANNEL_ID": "-1001234567890",
        "ANTHROPIC_API_KEY": "sk-ant-x",
        "NOTION_TOKEN": "ntn_x",
        "NOTION_DB_RESTAURANT": "db_rest",
        "NOTION_DB_PLACE": "db_place",
        "NOTION_DB_TODO": "db_todo",
        "NOTION_DB_ARTICLE": "db_article",
        "NOTION_DB_QUOTE": "db_quote",
        "NOTION_DB_APPAREL": "db_apparel",
        "NOTION_DB_SKINCARE": "db_skincare",
        "NOTION_DB_INBOX": "db_inbox",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return env


def test_settings_loads_required_fields(fake_env):
    s = Settings()
    assert s.telegram_bot_token == "123:abc"
    assert s.telegram_channel_id == -1001234567890
    assert s.notion_db_restaurant == "db_rest"


def test_settings_defaults(fake_env):
    s = Settings()
    assert s.classifier_model == "claude-haiku-4-5-20251001"
    assert s.confidence_threshold == 0.6
    assert s.timezone == "Asia/Taipei"
    assert s.digest_hour == 7
    assert s.digest_minute == 30


def test_db_id_for_category_dispatches_correctly(fake_env):
    s = Settings()
    assert db_id_for_category("restaurant", s) == "db_rest"
    assert db_id_for_category("todo", s) == "db_todo"
    assert db_id_for_category("inbox", s) == "db_inbox"


def test_db_id_for_unknown_category_falls_back_to_inbox(fake_env):
    s = Settings()
    assert db_id_for_category("weird_unknown", s) == "db_inbox"
