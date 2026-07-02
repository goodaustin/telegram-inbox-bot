from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    telegram_bot_token: str
    telegram_channel_id: int
    openai_api_key: str
    notion_token: str

    notion_db_restaurant: str
    notion_db_place: str
    notion_db_todo: str
    notion_db_article: str
    notion_db_quote: str
    notion_db_apparel: str
    notion_db_skincare: str
    notion_db_inbox: str

    classifier_model: str = "gpt-4.1-mini"
    confidence_threshold: float = 0.6
    timezone: str = "Asia/Taipei"
    digest_hour: int = 7
    digest_minute: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()


_CATEGORY_TO_ATTR = {
    "restaurant": "notion_db_restaurant",
    "place": "notion_db_place",
    "todo": "notion_db_todo",
    "article": "notion_db_article",
    "quote": "notion_db_quote",
    "apparel": "notion_db_apparel",
    "skincare": "notion_db_skincare",
    "inbox": "notion_db_inbox",
}


def db_id_for_category(category: str, settings: Settings) -> str:
    attr = _CATEGORY_TO_ATTR.get(category, "notion_db_inbox")
    return getattr(settings, attr)
