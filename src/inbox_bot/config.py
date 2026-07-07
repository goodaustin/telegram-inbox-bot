import logging
import os
from functools import lru_cache
from dotenv import find_dotenv, load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False,
        extra="ignore",
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
    confidence_threshold: float = 0.5
    timezone: str = "Asia/Taipei"
    digest_hour: int = 7
    digest_minute: int = 30
    digest_enabled: bool = True

    # 私人 life repo 絕對路徑（日記 / 名言 / 提醒 log 存放處）。
    # 留空則 /j /s /g /b 指令與提醒排程全部停用（對既有部署零影響）。
    life_dir: str = ""

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
    # Populate os.environ from .env so custom-category ids (NOTION_DB_<KEY>,
    # read via os.environ in db_id_for_category) resolve at runtime. pydantic's
    # env_file only fills the model, not os.environ. usecwd=True mirrors
    # pydantic-settings' env_file=".env", which is resolved relative to cwd
    # (default find_dotenv() instead walks up from this module's file location).
    load_dotenv(find_dotenv(usecwd=True))
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
    attr = _CATEGORY_TO_ATTR.get(category)
    if attr is not None:
        return getattr(settings, attr)
    # custom category → env var NOTION_DB_<KEY>
    val = os.environ.get(f"NOTION_DB_{category.upper()}")
    if val:
        return val
    log.warning("no NOTION_DB id for category %r; routing to inbox", category)
    return settings.notion_db_inbox
