from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    telegram_bot_token: str
    telegram_channel_id: int
    openai_api_key: str = ""
    notion_token: str

    notion_db_restaurant: str
    notion_db_place: str
    notion_db_todo: str
    notion_db_article: str
    notion_db_quote: str
    notion_db_apparel: str
    notion_db_skincare: str
    notion_db_photo: str
    notion_db_funny: str
    notion_db_inbox: str

    classifier_provider: str = "openai"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    classifier_model: str = "gpt-4.1-mini"
    confidence_threshold: float = 0.6
    timezone: str = "Asia/Taipei"
    digest_hour: int = 7
    digest_minute: int = 30

    @model_validator(mode="after")
    def _check_provider_key(self) -> "Settings":
        if self.classifier_provider == "openai":
            if not self.openai_api_key:
                raise ValueError("classifier_provider=openai requires OPENAI_API_KEY")
        elif self.classifier_provider == "gemini":
            if not self.gemini_api_key:
                raise ValueError("classifier_provider=gemini requires GEMINI_API_KEY")
        else:
            raise ValueError(f"unknown classifier_provider: {self.classifier_provider!r}")
        return self


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
    "photo": "notion_db_photo",
    "funny": "notion_db_funny",
    "inbox": "notion_db_inbox",
}


def db_id_for_category(category: str, settings: Settings) -> str:
    attr = _CATEGORY_TO_ATTR.get(category, "notion_db_inbox")
    return getattr(settings, attr)
