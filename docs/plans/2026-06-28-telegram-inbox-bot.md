# Telegram Inbox Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal Telegram → Claude vision → Notion pipeline that auto-categorizes screenshots into 7 lists with a weekly Sunday digest.

**Architecture:** Single Python daemon on Mac Studio. `bot.py` long-polls Telegram, hands `channel_post` updates to `classifier.py` (one Claude vision call returns structured JSON via forced tool-use), which `notion_writer.py` dispatches to the right Notion DB. `digest.py` runs Sunday 07:30 Asia/Taipei via APScheduler. Launchd `KeepAlive`s the whole thing.

**Tech Stack:** Python 3.11+, `python-telegram-bot ^21`, `anthropic ^0.40`, `notion-client ^2`, `apscheduler ^3`, `pydantic ^2`, `pydantic-settings ^2`, `uv`, `pytest` + `pytest-asyncio` + `freezegun`.

## Global Constraints

- **Python:** 3.11+ (uses `zoneinfo` stdlib and `tomllib`)
- **Timezone:** All scheduled times and date math use `ZoneInfo("Asia/Taipei")`
- **Classifier model:** `claude-haiku-4-5-20251001` (cheap, fast, sufficient for screenshots; can swap to Sonnet by changing one config var)
- **Forced JSON output:** Classifier uses Anthropic's `tool_choice={"type": "tool", "name": "classify_item"}` — never parse free-form text
- **Secrets:** Only in `.env`, never committed (already in `.gitignore`)
- **Async:** Bot handlers and Notion calls are async; tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- **Commits:** Each task ends with a commit; messages prefixed `feat:`, `test:`, or `chore:`

---

## File Structure

```
~/Projects/telegram-inbox-bot/
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore                    (already exists)
├── README.md                     (setup guide for future-you)
├── src/
│   └── inbox_bot/
│       ├── __init__.py
│       ├── config.py             — pydantic-settings env loader
│       ├── schemas.py            — pydantic models for 8 categories
│       ├── classifier.py         — Claude vision call
│       ├── notion_writer.py      — DB dispatcher + payload builder
│       ├── bot.py                — telegram handler logic (no main loop)
│       ├── digest.py             — Sunday digest job
│       ├── main.py               — entrypoint: starts bot + scheduler
│       └── prompts/
│           └── classify.md       — version-controlled Claude system prompt
├── tests/
│   ├── conftest.py
│   ├── fixtures/                 — real screenshot samples
│   ├── test_config.py
│   ├── test_schemas.py
│   ├── test_classifier.py
│   ├── test_notion_writer.py
│   ├── test_bot.py
│   └── test_digest.py
├── launchd/
│   └── com.shao.telegram-inbox.plist
├── logs/                         (gitignored, created at runtime)
└── docs/
    ├── specs/
    │   └── 2026-06-28-telegram-inbox-bot-design.md
    └── plans/
        └── 2026-06-28-telegram-inbox-bot.md     (this file)
```

**Why this shape:** `src/inbox_bot/` keeps the package importable for tests without `sys.path` hacks. One file per responsibility (≤200 lines each). The `main.py` is pure wiring — all real logic lives in modules that take inputs and return outputs, which is what makes tests easy.

---

## Task 1: User-side setup (manual, no code)

**Files:**
- Create: `.env` (locally, gitignored)

**Interfaces:**
- Produces: A working `.env` file with all secrets + IDs that every later task depends on

This task has no test — it's account setup you have to do once. All later tasks assume `.env` is populated.

- [ ] **Step 1: Create the Telegram bot**

Open Telegram, search `@BotFather`. Send:
```
/newbot
```
Pick a name (e.g. "Shao's Inbox") and username (must end in `bot`, e.g. `shao_inbox_bot`). BotFather replies with an HTTP API token like `7891234567:AAH...`. Save it.

- [ ] **Step 2: Create the private channel and add the bot**

In Telegram: `New Channel` → make it **Private** → name it (e.g. "Inbox"). Open channel info → `Administrators` → `Add Admin` → search your bot's username → grant it: `Post Messages`, `Edit Messages of Others`, `Delete Messages`. Save.

- [ ] **Step 3: Find the channel's numeric ID**

In Telegram open your channel and send any test message (e.g. "hi"). Then in browser:
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```
Look in the JSON response for `"chat":{"id":-1001234567890,...}`. The negative number starting with `-100` is your `TELEGRAM_CHANNEL_ID`. Save it.

- [ ] **Step 4: Create the Notion integration**

Go to https://www.notion.so/profile/integrations → `New integration` → name it "Inbox Bot" → workspace = your personal workspace → type = Internal → capabilities = Read + Update + Insert content + No user info. Submit. Copy the `Internal Integration Secret` (starts with `secret_` or `ntn_`).

- [ ] **Step 5: Create 8 Notion databases**

In Notion create a new page "📥 Inbox". Inside it, create 8 inline databases with these exact names and properties (copy schemas from spec §"Notion Database Schemas"):

1. `🍴 餐廳` — Name (title), City/Area (select), Cuisine (multi-select), Maps Link (url), Notes (text), Source (url), Date Added (date)
2. `📍 想去的地點` — Name, City/Country, Type, Maps Link, Notes, Source, Date Added
3. `✅ 待辦事項` — Task (title), Deadline (date), Status (status: Todo/Doing/Done), Notes, Source, Date Added
4. `📖 待讀文章` — Title (title), URL (url), Publisher (text), Summary (text), Read? (checkbox), Source (url), Date Added
5. `💬 名言` — Quote (title), Author (text), Tags (multi-select), Source (url), Date Added
6. `👗 服飾` — Item (title), Brand, Type (select), Price (number), URL, Notes, Source, Date Added
7. `💄 保養` — Product (title), Brand, Category (select), Price (number), URL, Notes, Source, Date Added
8. `🗂 Inbox` — Raw Text (title), Reason (text), Source (url), Date Added

For each DB: click `···` top-right → `Connections` → `Add connections` → select "Inbox Bot" integration. Then click `···` → `Copy link to view` → the ID is the 32-char hex blob in the URL (e.g. `https://www.notion.so/myws/8a2c4f...?v=...` → `8a2c4f...`).

- [ ] **Step 6: Write the `.env` file**

In `~/Projects/telegram-inbox-bot/.env`:
```bash
TELEGRAM_BOT_TOKEN=7891234567:AAH...
TELEGRAM_CHANNEL_ID=-1001234567890
ANTHROPIC_API_KEY=sk-ant-...
NOTION_TOKEN=ntn_...
NOTION_DB_RESTAURANT=8a2c4f...
NOTION_DB_PLACE=...
NOTION_DB_TODO=...
NOTION_DB_ARTICLE=...
NOTION_DB_QUOTE=...
NOTION_DB_APPAREL=...
NOTION_DB_SKINCARE=...
NOTION_DB_INBOX=...
CLASSIFIER_MODEL=claude-haiku-4-5-20251001
CONFIDENCE_THRESHOLD=0.6
TIMEZONE=Asia/Taipei
DIGEST_HOUR=7
DIGEST_MINUTE=30
```

- [ ] **Step 7: Sanity check**

```bash
cat ~/Projects/telegram-inbox-bot/.env | grep -c '^[A-Z_]\+='
```
Expected output: `15` (one line per env var).

No commit — `.env` is gitignored.

---

## Task 2: Project scaffold (`pyproject.toml`, package layout)

**Files:**
- Create: `pyproject.toml`, `src/inbox_bot/__init__.py`, `tests/conftest.py`, `tests/__init__.py`, `.env.example`, `README.md`
- Modify: none

**Interfaces:**
- Consumes: nothing
- Produces: `uv run pytest` runs (with zero tests); `from inbox_bot import config` resolves

- [ ] **Step 1: Write `pyproject.toml`**

`~/Projects/telegram-inbox-bot/pyproject.toml`:
```toml
[project]
name = "inbox-bot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "python-telegram-bot>=21.0,<22",
    "anthropic>=0.40,<1",
    "notion-client>=2.2,<3",
    "apscheduler>=3.10,<4",
    "pydantic>=2.5,<3",
    "pydantic-settings>=2.1,<3",
    "httpx>=0.27,<1",
]

[dependency-groups]
dev = [
    "pytest>=8.0,<9",
    "pytest-asyncio>=0.23,<1",
    "freezegun>=1.4,<2",
    "respx>=0.21,<1",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
testpaths = ["tests"]

[tool.uv]
package = false
```

- [ ] **Step 2: Create package skeleton**

```bash
cd ~/Projects/telegram-inbox-bot
mkdir -p src/inbox_bot/prompts tests/fixtures
touch src/inbox_bot/__init__.py tests/__init__.py tests/conftest.py
```

- [ ] **Step 3: Write `.env.example`**

Same keys as Task 1 Step 6 but with placeholder values:
```bash
TELEGRAM_BOT_TOKEN=replace_me
TELEGRAM_CHANNEL_ID=-100xxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-...
NOTION_TOKEN=ntn_...
NOTION_DB_RESTAURANT=
NOTION_DB_PLACE=
NOTION_DB_TODO=
NOTION_DB_ARTICLE=
NOTION_DB_QUOTE=
NOTION_DB_APPAREL=
NOTION_DB_SKINCARE=
NOTION_DB_INBOX=
CLASSIFIER_MODEL=claude-haiku-4-5-20251001
CONFIDENCE_THRESHOLD=0.6
TIMEZONE=Asia/Taipei
DIGEST_HOUR=7
DIGEST_MINUTE=30
```

- [ ] **Step 4: Write minimal `README.md`**

```markdown
# Telegram Inbox Bot

Personal inbox: Telegram channel → Claude vision → Notion (7 categorized lists + fallback Inbox). Weekly Sunday 07:30 digest of open todos and unread articles.

## Setup

See `docs/plans/2026-06-28-telegram-inbox-bot.md` Task 1 for one-time account setup (Telegram bot, Notion integration, 8 DBs). Then:

```bash
uv sync
cp .env.example .env  # fill in real values
uv run python -m inbox_bot.main
```

## Deployment

Mac Studio + launchd. Plist at `launchd/com.shao.telegram-inbox.plist`. Load with:
```bash
cp launchd/com.shao.telegram-inbox.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.shao.telegram-inbox.plist
```

## Testing

```bash
uv run pytest          # all unit tests (mocked)
uv run pytest -m smoke # real API smoke tests (manual; costs $)
```

## Architecture

See `docs/specs/2026-06-28-telegram-inbox-bot-design.md`.
```

- [ ] **Step 5: Install deps and verify**

```bash
cd ~/Projects/telegram-inbox-bot && uv sync
```
Expected: creates `.venv/` and `uv.lock`, no errors.

```bash
uv run pytest
```
Expected: `no tests ran` (exit 5 is OK, means "no tests collected"), no import errors.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .env.example README.md src/ tests/
git commit -m "chore: project scaffold and dependencies"
```

---

## Task 3: Config loader (`config.py`)

**Files:**
- Create: `src/inbox_bot/config.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: env vars (loaded from `.env` by `pydantic-settings`)
- Produces:
  ```python
  class Settings(BaseSettings):
      telegram_bot_token: str
      telegram_channel_id: int
      anthropic_api_key: str
      notion_token: str
      notion_db_restaurant: str
      notion_db_place: str
      notion_db_todo: str
      notion_db_article: str
      notion_db_quote: str
      notion_db_apparel: str
      notion_db_skincare: str
      notion_db_inbox: str
      classifier_model: str = "claude-haiku-4-5-20251001"
      confidence_threshold: float = 0.6
      timezone: str = "Asia/Taipei"
      digest_hour: int = 7
      digest_minute: int = 30
  def get_settings() -> Settings: ...   # cached
  def db_id_for_category(category: str, settings: Settings) -> str: ...
  ```

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
uv run pytest tests/test_config.py -v
```
Expected: ImportError or all fail (module doesn't exist yet).

- [ ] **Step 3: Implement `config.py`**

`src/inbox_bot/config.py`:
```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    telegram_bot_token: str
    telegram_channel_id: int
    anthropic_api_key: str
    notion_token: str

    notion_db_restaurant: str
    notion_db_place: str
    notion_db_todo: str
    notion_db_article: str
    notion_db_quote: str
    notion_db_apparel: str
    notion_db_skincare: str
    notion_db_inbox: str

    classifier_model: str = "claude-haiku-4-5-20251001"
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
```

- [ ] **Step 4: Run tests, verify all pass**

```bash
uv run pytest tests/test_config.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/config.py tests/test_config.py
git commit -m "feat: env-backed Settings + category→DB dispatcher"
```

---

## Task 4: Schemas (`schemas.py`)

**Files:**
- Create: `src/inbox_bot/schemas.py`, `tests/test_schemas.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  ```python
  Category = Literal["restaurant", "place", "todo", "article", "quote", "apparel", "skincare", "inbox"]

  class ClassifierResult(BaseModel):
      category: Category
      confidence: float          # 0-1
      raw_text: str              # OCR'd / message text
      fields: dict[str, Any]     # category-specific structured fields

  CATEGORY_FIELD_SCHEMAS: dict[Category, list[str]]   # required field names per category
  ```

- [ ] **Step 1: Write the failing tests**

`tests/test_schemas.py`:
```python
import pytest
from pydantic import ValidationError
from inbox_bot.schemas import ClassifierResult, CATEGORY_FIELD_SCHEMAS


def test_classifier_result_accepts_restaurant():
    r = ClassifierResult(
        category="restaurant",
        confidence=0.95,
        raw_text="Tonkatsu Maisen 東京 表參道",
        fields={"name": "Maisen", "city": "東京/表參道", "cuisine": ["日料", "炸物"]},
    )
    assert r.category == "restaurant"
    assert r.fields["name"] == "Maisen"


def test_classifier_result_rejects_invalid_category():
    with pytest.raises(ValidationError):
        ClassifierResult(category="movies", confidence=0.9, raw_text="x", fields={})


def test_classifier_result_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        ClassifierResult(category="todo", confidence=1.5, raw_text="x", fields={})


def test_all_categories_have_field_schema():
    expected = {"restaurant", "place", "todo", "article", "quote",
                "apparel", "skincare", "inbox"}
    assert set(CATEGORY_FIELD_SCHEMAS.keys()) == expected


def test_inbox_schema_is_minimal():
    assert CATEGORY_FIELD_SCHEMAS["inbox"] == ["reason"]


def test_restaurant_schema_has_expected_fields():
    assert "name" in CATEGORY_FIELD_SCHEMAS["restaurant"]
    assert "city" in CATEGORY_FIELD_SCHEMAS["restaurant"]
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
uv run pytest tests/test_schemas.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `schemas.py`**

`src/inbox_bot/schemas.py`:
```python
from typing import Any, Literal
from pydantic import BaseModel, Field

Category = Literal[
    "restaurant", "place", "todo", "article",
    "quote", "apparel", "skincare", "inbox",
]


class ClassifierResult(BaseModel):
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    raw_text: str
    fields: dict[str, Any] = Field(default_factory=dict)


CATEGORY_FIELD_SCHEMAS: dict[Category, list[str]] = {
    "restaurant": ["name", "city", "cuisine", "notes"],
    "place":      ["name", "city", "type", "notes"],
    "todo":       ["task", "notes"],
    "article":    ["title", "url", "publisher", "summary"],
    "quote":      ["quote", "author", "tags"],
    "apparel":    ["item", "brand", "type", "price", "url", "notes"],
    "skincare":   ["product", "brand", "category", "price", "url", "notes"],
    "inbox":      ["reason"],
}
```

- [ ] **Step 4: Run tests, verify all pass**

```bash
uv run pytest tests/test_schemas.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/schemas.py tests/test_schemas.py
git commit -m "feat: ClassifierResult model and per-category field schemas"
```

---

## Task 5: Classifier prompt (`prompts/classify.md`)

**Files:**
- Create: `src/inbox_bot/prompts/classify.md`

**Interfaces:**
- Consumes: nothing
- Produces: a markdown file the classifier reads at import time

No test — it's content. The classifier task tests use it.

- [ ] **Step 1: Write the system prompt**

`src/inbox_bot/prompts/classify.md`:
```markdown
You are a personal inbox classifier. The user sends you screenshots from their phone (or plain text). Your job: identify the category and extract structured fields.

## Categories

- **restaurant** — a place to eat (restaurant, cafe, bar, dessert shop). Extract: name, city (format "城市/區域", e.g. "台北/信義"), cuisine (array of tags), notes (1 line if anything notable).
- **place** — a non-food location to visit (tourist attraction, museum, shop, hotel, activity). Extract: name, city (format "城市/國家"), type (one of: 景點/活動/購物/自然/住宿/其他), notes.
- **todo** — a task or reminder. Extract: task (imperative sentence), notes.
- **article** — something to read later (article URL, book title, social-media post title). Extract: title, url (if visible in screenshot), publisher (媒體名稱), summary (one line in user's language).
- **quote** — an inspirational quote or memorable line. Extract: quote (the text), author (if known), tags (array of themes).
- **apparel** — clothing, shoes, accessories to potentially buy. Extract: item (name/description), brand, type (one of: 上衣/下著/鞋/包/配件/外套), price (number, no currency), url, notes.
- **skincare** — skincare or beauty products to potentially buy. Extract: product (name), brand, category (one of: 潔顏/化妝水/精華/乳液/面膜/防曬/其他), price, url, notes.
- **inbox** — when you cannot classify with confidence. Extract: reason (one line: why uncertain).

## Confidence

Return a `confidence` float 0-1. If < 0.6, the system will route to **inbox** regardless of category. Be honest — guessing wrong is worse than dropping to inbox.

## Rules

- Output ONLY the structured tool call. Do not add prose.
- If multiple categories plausibly fit (e.g. a screenshot of a restaurant article), pick the dominant intent. Mostly food → restaurant. Mostly read-this → article.
- For Asian languages: keep names in original script. Don't translate.
- If the screenshot is just a UI with no extractable content (lock screen, settings page, blank chat), category=inbox, reason="no extractable content".
- Always fill `raw_text` with everything readable from the image (OCR), or echo the input text.
```

- [ ] **Step 2: Commit**

```bash
git add src/inbox_bot/prompts/classify.md
git commit -m "feat: classifier system prompt"
```

---

## Task 6: Classifier (`classifier.py`)

**Files:**
- Create: `src/inbox_bot/classifier.py`, `tests/test_classifier.py`

**Interfaces:**
- Consumes: `Settings` from `config.py`, `ClassifierResult` and `CATEGORY_FIELD_SCHEMAS` from `schemas.py`, the prompt file from Task 5
- Produces:
  ```python
  async def classify(
      *,
      image_bytes: bytes | None,
      text: str | None,
      settings: Settings,
      client: AsyncAnthropic | None = None,  # injectable for tests
  ) -> ClassifierResult
  ```
  - Calls Claude vision with the prompt + image and/or text
  - Uses tool-use forced output (`tool_choice={"type":"tool","name":"classify_item"}`)
  - On `confidence < settings.confidence_threshold`: returns result with `category="inbox"` and original category preserved in `fields["original_category"]`
  - On API failure: retries once; if still failing, raises `ClassifierError`

- [ ] **Step 1: Write the failing tests**

`tests/test_classifier.py`:
```python
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


def test_classify_tool_schema_includes_all_categories():
    enum = CLASSIFY_TOOL["input_schema"]["properties"]["category"]["enum"]
    assert set(enum) == {"restaurant", "place", "todo", "article",
                         "quote", "apparel", "skincare", "inbox"}
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
uv run pytest tests/test_classifier.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `classifier.py`**

`src/inbox_bot/classifier.py`:
```python
import asyncio
import base64
from importlib import resources
from typing import Any
from anthropic import AsyncAnthropic
from inbox_bot.config import Settings
from inbox_bot.schemas import ClassifierResult


class ClassifierError(Exception):
    pass


CLASSIFY_TOOL: dict[str, Any] = {
    "name": "classify_item",
    "description": "Classify an inbox item and extract structured fields.",
    "input_schema": {
        "type": "object",
        "required": ["category", "confidence", "raw_text", "fields"],
        "properties": {
            "category": {
                "type": "string",
                "enum": ["restaurant", "place", "todo", "article",
                         "quote", "apparel", "skincare", "inbox"],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "raw_text": {"type": "string"},
            "fields": {"type": "object"},
        },
    },
}


def _load_system_prompt() -> str:
    return resources.files("inbox_bot.prompts").joinpath("classify.md").read_text(encoding="utf-8")


def _build_content(image_bytes: bytes | None, text: str | None) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    if image_bytes:
        parts.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(image_bytes).decode("ascii"),
            },
        })
    if text:
        parts.append({"type": "text", "text": text})
    if not parts:
        parts.append({"type": "text", "text": "(empty)"})
    return parts


async def classify(
    *,
    image_bytes: bytes | None,
    text: str | None,
    settings: Settings,
    client: AsyncAnthropic | None = None,
) -> ClassifierResult:
    if client is None:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    system = _load_system_prompt()
    content = _build_content(image_bytes, text)

    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            resp = await client.messages.create(
                model=settings.classifier_model,
                max_tokens=1024,
                system=system,
                tools=[CLASSIFY_TOOL],
                tool_choice={"type": "tool", "name": "classify_item"},
                messages=[{"role": "user", "content": content}],
            )
            tool_block = next(
                (b for b in resp.content if getattr(b, "type", None) == "tool_use"),
                None,
            )
            if tool_block is None:
                raise ClassifierError("no tool_use block in response")

            result = ClassifierResult(**tool_block.input)
            if result.confidence < settings.confidence_threshold:
                return ClassifierResult(
                    category="inbox",
                    confidence=result.confidence,
                    raw_text=result.raw_text,
                    fields={
                        "original_category": result.category,
                        "reason": "low_confidence",
                        **result.fields,
                    },
                )
            return result
        except Exception as e:
            last_err = e
            if attempt == 1:
                await asyncio.sleep(2)
                continue
            raise ClassifierError(f"classifier failed after retry: {e}") from e

    raise ClassifierError(f"unreachable: {last_err}")
```

- [ ] **Step 4: Run tests, verify all pass**

```bash
uv run pytest tests/test_classifier.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/classifier.py tests/test_classifier.py
git commit -m "feat: Claude vision classifier with forced tool-use + retry"
```

---

## Task 7: Notion writer (`notion_writer.py`)

**Files:**
- Create: `src/inbox_bot/notion_writer.py`, `tests/test_notion_writer.py`

**Interfaces:**
- Consumes: `Settings`, `ClassifierResult` (with `category` and `fields`)
- Produces:
  ```python
  class NotionWriteError(Exception): ...

  async def write_to_notion(
      *,
      result: ClassifierResult,
      telegram_message_url: str,
      image_bytes: bytes | None,
      settings: Settings,
      client: AsyncClient | None = None,   # notion_client.AsyncClient
  ) -> str   # returns the created page URL
  # Retries up to 3x with exponential backoff (1s, 2s, 4s).
  # On final failure: appends a JSON record to logs/failed_writes.jsonl, raises NotionWriteError.

  def build_maps_link(name: str, city: str) -> str
  def build_telegram_url(channel_id: int, message_id: int) -> str
  def build_properties(category: str, fields: dict, telegram_url: str,
                       maps_link: str | None, now: datetime) -> dict
  ```

- [ ] **Step 1: Write the failing tests**

`tests/test_notion_writer.py`:
```python
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
        "ANTHROPIC_API_KEY": "x", "NOTION_TOKEN": "x",
        "NOTION_DB_RESTAURANT": "db_rest", "NOTION_DB_PLACE": "db_place",
        "NOTION_DB_TODO": "db_todo", "NOTION_DB_ARTICLE": "db_article",
        "NOTION_DB_QUOTE": "db_quote", "NOTION_DB_APPAREL": "db_apparel",
        "NOTION_DB_SKINCARE": "db_skincare", "NOTION_DB_INBOX": "db_inbox",
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
    assert props["Status"]["status"]["name"] == "Todo"


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
    monkeypatch.setattr("inbox_bot.notion_writer._BACKOFF_SECONDS", (0, 0, 0))
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
    monkeypatch.setattr("inbox_bot.notion_writer._BACKOFF_SECONDS", (0, 0, 0))
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
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
uv run pytest tests/test_notion_writer.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `notion_writer.py`**

`src/inbox_bot/notion_writer.py`:
```python
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, quote
from zoneinfo import ZoneInfo
from notion_client import AsyncClient
from inbox_bot.config import Settings, db_id_for_category
from inbox_bot.schemas import ClassifierResult

log = logging.getLogger(__name__)

_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0)
_FAILED_WRITES_PATH = Path(__file__).resolve().parents[2] / "logs" / "failed_writes.jsonl"


class NotionWriteError(Exception):
    pass


def build_maps_link(name: str, city: str) -> str:
    q = f"{name} {city}".strip()
    return f"https://www.google.com/maps/search/?api=1&query={quote(q)}"


def build_telegram_url(channel_id: int, message_id: int) -> str:
    # Channels start with -100; strip the "-100" prefix for t.me/c/ URLs
    short = str(channel_id).removeprefix("-100")
    return f"https://t.me/c/{short}/{message_id}"


def _title(value: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": value[:2000]}}]}


def _text(value: str) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": value[:2000]}}]}


def _select(value: str) -> dict[str, Any]:
    return {"select": {"name": value[:100]}}


def _multi(values: list[str]) -> dict[str, Any]:
    return {"multi_select": [{"name": v[:100]} for v in values]}


def _url(value: str) -> dict[str, Any]:
    return {"url": value or None}


def _date(dt: datetime) -> dict[str, Any]:
    return {"date": {"start": dt.isoformat()}}


def _number(value: Any) -> dict[str, Any]:
    try:
        return {"number": float(value) if value not in (None, "") else None}
    except (TypeError, ValueError):
        return {"number": None}


def _status(name: str) -> dict[str, Any]:
    return {"status": {"name": name}}


def _checkbox(value: bool) -> dict[str, Any]:
    return {"checkbox": value}


def build_properties(
    category: str,
    fields: dict[str, Any],
    telegram_url: str,
    maps_link: str | None,
    now: datetime,
) -> dict[str, dict[str, Any]]:
    g = fields.get  # shorthand

    if category == "restaurant":
        return {
            "Name": _title(g("name", "")),
            "City/Area": _select(g("city", "未知")),
            "Cuisine": _multi(g("cuisine") or []),
            "Maps Link": _url(maps_link or ""),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "place":
        return {
            "Name": _title(g("name", "")),
            "City/Country": _select(g("city", "未知")),
            "Type": _select(g("type", "其他")),
            "Maps Link": _url(maps_link or ""),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "todo":
        deadline = now + timedelta(days=7)
        return {
            "Task": _title(g("task", "")),
            "Deadline": _date(deadline),
            "Status": _status("Todo"),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "article":
        return {
            "Title": _title(g("title", "")),
            "URL": _url(g("url", "")),
            "Publisher": _text(g("publisher", "")),
            "Summary": _text(g("summary", "")),
            "Read?": _checkbox(False),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "quote":
        return {
            "Quote": _title(g("quote", "")),
            "Author": _text(g("author", "")),
            "Tags": _multi(g("tags") or []),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "apparel":
        return {
            "Item": _title(g("item", "")),
            "Brand": _text(g("brand", "")),
            "Type": _select(g("type", "其他")),
            "Price": _number(g("price")),
            "URL": _url(g("url", "")),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    if category == "skincare":
        return {
            "Product": _title(g("product", "")),
            "Brand": _text(g("brand", "")),
            "Category": _select(g("category", "其他")),
            "Price": _number(g("price")),
            "URL": _url(g("url", "")),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
    # inbox fallback
    return {
        "Raw Text": _title(g("raw_text", "") or fields.get("reason", "")),
        "Reason": _text(f"{g('reason', 'unknown')} (was: {g('original_category', '—')})"),
        "Source": _url(telegram_url),
        "Date Added": _date(now),
    }


async def write_to_notion(
    *,
    result: ClassifierResult,
    telegram_message_url: str,
    image_bytes: bytes | None,
    settings: Settings,
    client: AsyncClient | None = None,
) -> str:
    if client is None:
        client = AsyncClient(auth=settings.notion_token)

    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)

    maps_link = None
    if result.category in ("restaurant", "place"):
        maps_link = build_maps_link(
            result.fields.get("name", ""),
            result.fields.get("city", ""),
        )

    # inbox fallback needs raw_text in fields so build_properties can title it
    fields = dict(result.fields)
    if result.category == "inbox":
        fields.setdefault("raw_text", result.raw_text)

    properties = build_properties(
        category=result.category,
        fields=fields,
        telegram_url=telegram_message_url,
        maps_link=maps_link,
        now=now,
    )

    db_id = db_id_for_category(result.category, settings)

    # Children: include OCR'd text as a paragraph block for searchability
    children = []
    if result.raw_text:
        children.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text",
                "text": {"content": result.raw_text[:2000]}}]},
        })

    last_err: Exception | None = None
    for attempt, delay in enumerate(_BACKOFF_SECONDS, start=1):
        try:
            page = await client.pages.create(
                parent={"database_id": db_id},
                properties=properties,
                children=children,
            )
            return page["url"]
        except Exception as e:
            last_err = e
            log.warning("notion write attempt %d failed: %s", attempt, e)
            if attempt < len(_BACKOFF_SECONDS):
                await asyncio.sleep(delay)

    # all retries exhausted — append to failed_writes.jsonl
    _FAILED_WRITES_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": now.isoformat(),
        "category": result.category,
        "fields": result.fields,
        "raw_text": result.raw_text,
        "telegram_url": telegram_message_url,
        "error": str(last_err),
    }
    with _FAILED_WRITES_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    raise NotionWriteError(f"notion write failed after 3 retries: {last_err}") from last_err
```

> **Note:** Image upload via Notion's `file_upload` API is intentionally NOT implemented in v1. The `raw_text` paragraph block + Telegram source link covers the search/recall need. Image attachment is in §"Future" of the spec.

- [ ] **Step 4: Run tests, verify all pass**

```bash
uv run pytest tests/test_notion_writer.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/notion_writer.py tests/test_notion_writer.py
git commit -m "feat: notion writer with per-category property builders"
```

---

## Task 8: Bot handler (`bot.py`)

**Files:**
- Create: `src/inbox_bot/bot.py`, `tests/test_bot.py`

**Interfaces:**
- Consumes: `Settings`, `classify` from classifier, `write_to_notion` + `build_telegram_url` from notion_writer
- Produces:
  ```python
  async def handle_channel_post(update, context) -> None
  def build_application(settings: Settings) -> Application
  ```
  - `handle_channel_post` extracts message_id + caption + photo/text, calls classifier, calls notion_writer, replies with `✅ <emoji> → <notion url>` or `❌ 分類失敗，已存入 Inbox`
  - `build_application` wires the handler into a `telegram.ext.Application` for long-polling

- [ ] **Step 1: Write the failing tests**

`tests/test_bot.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from inbox_bot.bot import handle_channel_post, CATEGORY_EMOJI
from inbox_bot.config import Settings
from inbox_bot.schemas import ClassifierResult


@pytest.fixture
def settings(monkeypatch):
    for k, v in {
        "TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHANNEL_ID": "-1001234567890",
        "ANTHROPIC_API_KEY": "x", "NOTION_TOKEN": "x",
        "NOTION_DB_RESTAURANT": "a", "NOTION_DB_PLACE": "b",
        "NOTION_DB_TODO": "c", "NOTION_DB_ARTICLE": "d",
        "NOTION_DB_QUOTE": "e", "NOTION_DB_APPAREL": "f",
        "NOTION_DB_SKINCARE": "g", "NOTION_DB_INBOX": "h",
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
    assert "❌" in reply or "Inbox" in reply
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
uv run pytest tests/test_bot.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `bot.py`**

`src/inbox_bot/bot.py`:
```python
import logging
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from inbox_bot.classifier import classify, ClassifierError
from inbox_bot.config import Settings
from inbox_bot.notion_writer import write_to_notion, build_telegram_url
from inbox_bot.schemas import ClassifierResult

log = logging.getLogger(__name__)

CATEGORY_EMOJI = {
    "restaurant": "🍴", "place": "📍", "todo": "✅", "article": "📖",
    "quote": "💬", "apparel": "👗", "skincare": "💄", "inbox": "🗂",
}


async def handle_channel_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    post = update.channel_post
    if post is None:
        return

    settings: Settings = ctx.bot_data["settings"]
    text = post.text or post.caption
    image_bytes: bytes | None = None

    if post.photo:
        # photo is a list of PhotoSize, increasing in resolution; take the largest
        largest = post.photo[-1]
        tg_file = await ctx.bot.get_file(largest.file_id)
        data = await tg_file.download_as_bytearray()
        image_bytes = bytes(data)

    telegram_url = build_telegram_url(post.chat.id, post.message_id)

    try:
        result = await classify(
            image_bytes=image_bytes, text=text, settings=settings,
        )
    except ClassifierError as e:
        log.warning("classifier failed: %s", e)
        result = ClassifierResult(
            category="inbox",
            confidence=0.0,
            raw_text=text or "(no text)",
            fields={"reason": f"classifier_error: {e}",
                    "original_category": "unknown"},
        )

    try:
        page_url = await write_to_notion(
            result=result,
            telegram_message_url=telegram_url,
            image_bytes=image_bytes,
            settings=settings,
        )
    except Exception as e:
        log.exception("notion write failed")
        await post.reply_text(f"❌ Notion 寫入失敗: {e}")
        return

    emoji = CATEGORY_EMOJI.get(result.category, "📥")
    if result.category == "inbox":
        await post.reply_text(f"{emoji} 已存入 Inbox\n{page_url}")
    else:
        await post.reply_text(f"{emoji} → {page_url}")


def build_application(settings: Settings) -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["settings"] = settings
    # channel posts (not regular chats)
    app.add_handler(MessageHandler(
        filters.UpdateType.CHANNEL_POST, handle_channel_post,
    ))
    return app
```

- [ ] **Step 4: Run tests, verify all pass**

```bash
uv run pytest tests/test_bot.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/bot.py tests/test_bot.py
git commit -m "feat: telegram channel_post handler with classifier+notion wiring"
```

---

## Task 9: Sunday digest (`digest.py`)

**Files:**
- Create: `src/inbox_bot/digest.py`, `tests/test_digest.py`

**Interfaces:**
- Consumes: `Settings`, notion `AsyncClient`, telegram `Bot`
- Produces:
  ```python
  async def query_open_todos(client, settings) -> list[dict]   # {task, deadline, status}
  async def query_unread_articles(client, settings, limit=10) -> list[dict]  # {title, publisher}
  def format_digest(now, todos, articles, articles_db_id) -> str
  async def send_digest(settings, *, telegram_bot=None, notion_client=None) -> None
  ```

- [ ] **Step 1: Write the failing tests**

`tests/test_digest.py`:
```python
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
        "ANTHROPIC_API_KEY": "x", "NOTION_TOKEN": "x",
        "NOTION_DB_RESTAURANT": "a", "NOTION_DB_PLACE": "b",
        "NOTION_DB_TODO": "c", "NOTION_DB_ARTICLE": "d",
        "NOTION_DB_QUOTE": "e", "NOTION_DB_APPAREL": "f",
        "NOTION_DB_SKINCARE": "g", "NOTION_DB_INBOX": "h",
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
    assert "待讀 (2 篇)" in msg
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
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
uv run pytest tests/test_digest.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `digest.py`**

`src/inbox_bot/digest.py`:
```python
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo
from notion_client import AsyncClient as NotionAsyncClient
from telegram import Bot
from inbox_bot.config import Settings

log = logging.getLogger(__name__)


async def query_open_todos(client: NotionAsyncClient, settings: Settings) -> list[dict[str, Any]]:
    resp = await client.databases.query(
        database_id=settings.notion_db_todo,
        filter={"property": "Status", "status": {"does_not_equal": "Done"}},
        sorts=[{"property": "Deadline", "direction": "ascending"}],
    )
    todos = []
    for row in resp.get("results", []):
        props = row.get("properties", {})
        title = props.get("Task", {}).get("title", [])
        task = title[0]["plain_text"] if title else "(untitled)"
        deadline = (props.get("Deadline", {}).get("date") or {}).get("start", "")
        todos.append({"task": task, "deadline": deadline})
    return todos


async def query_unread_articles(
    client: NotionAsyncClient, settings: Settings, limit: int = 10
) -> list[dict[str, Any]]:
    resp = await client.databases.query(
        database_id=settings.notion_db_article,
        filter={"property": "Read?", "checkbox": {"equals": False}},
        sorts=[{"property": "Date Added", "direction": "descending"}],
        page_size=limit,
    )
    articles = []
    for row in resp.get("results", []):
        props = row.get("properties", {})
        t = props.get("Title", {}).get("title", [])
        title = t[0]["plain_text"] if t else "(untitled)"
        p = props.get("Publisher", {}).get("rich_text", [])
        publisher = p[0]["plain_text"] if p else ""
        articles.append({"title": title, "publisher": publisher})
    return articles


def _format_date(d: str) -> str:
    # "2026-06-30" → "6/30"
    try:
        dt = datetime.fromisoformat(d)
        return f"{dt.month}/{dt.day}"
    except ValueError:
        return d


def format_digest(
    now: datetime,
    todos: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    articles_db_id: str,
) -> str:
    today = now.date()
    overdue = [t for t in todos if t["deadline"] and datetime.fromisoformat(t["deadline"]).date() < today]
    this_week = [t for t in todos if t["deadline"] and today <= datetime.fromisoformat(t["deadline"]).date() <= today + timedelta(days=7)]
    later = [t for t in todos if t["deadline"] and datetime.fromisoformat(t["deadline"]).date() > today + timedelta(days=7)]

    weekday_name = "週日"  # this only ever runs on Sunday
    lines = [f"☀️ 早安 — 本週清單 ({weekday_name} {now.month}/{now.day})",
             "─" * 18]

    if overdue:
        lines.append(f"\n⚠️ 已過期 ({len(overdue)})")
        for t in overdue:
            lines.append(f"• {_format_date(t['deadline'])} - {t['task']}")

    if this_week:
        lines.append(f"\n📅 本週到期 ({len(this_week)})")
        for t in this_week:
            lines.append(f"• {_format_date(t['deadline'])} - {t['task']}")

    if later:
        lines.append(f"\n📆 之後 ({len(later)})")
        for t in later[:5]:
            lines.append(f"• {_format_date(t['deadline'])} - {t['task']}")

    if not (overdue or this_week or later):
        lines.append("\n✨ 沒有待辦事項")

    if articles:
        lines.append(f"\n📖 待讀 ({len(articles)} 篇)")
        for a in articles[:5]:
            pub = f"({a['publisher']})" if a["publisher"] else ""
            lines.append(f"• 「{a['title']}」{pub}")
        if len(articles) > 5:
            lines.append(f"   👉 全部: https://www.notion.so/{articles_db_id.replace('-', '')}")
    else:
        lines.append("\n📭 沒有待讀文章")

    return "\n".join(lines)


async def send_digest(
    settings: Settings,
    *,
    telegram_bot: Bot | None = None,
    notion_client: NotionAsyncClient | None = None,
) -> None:
    if notion_client is None:
        notion_client = NotionAsyncClient(auth=settings.notion_token)
    if telegram_bot is None:
        telegram_bot = Bot(token=settings.telegram_bot_token)

    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)

    todos = await query_open_todos(notion_client, settings)
    articles = await query_unread_articles(notion_client, settings)

    text = format_digest(now, todos, articles, articles_db_id=settings.notion_db_article)

    try:
        await telegram_bot.send_message(
            chat_id=settings.telegram_channel_id,
            text=text,
        )
    except Exception:
        log.exception("digest send failed")
        # last-ditch: still raise so apscheduler logs it
        raise
```

- [ ] **Step 4: Run tests, verify all pass**

```bash
uv run pytest tests/test_digest.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/digest.py tests/test_digest.py
git commit -m "feat: weekly Sunday digest builder + sender"
```

---

## Task 10: Main entrypoint (`main.py`)

**Files:**
- Create: `src/inbox_bot/main.py`
- Modify: none

**Interfaces:**
- Consumes: `Settings`, `build_application`, `send_digest`
- Produces: a runnable module: `uv run python -m inbox_bot.main`

No new unit tests — the modules it wires are all tested. Run the smoke check at the end.

- [ ] **Step 1: Implement `main.py`**

`src/inbox_bot/main.py`:
```python
import asyncio
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from inbox_bot.bot import build_application
from inbox_bot.config import get_settings
from inbox_bot.digest import send_digest


def _setup_logging() -> None:
    logs_dir = Path(__file__).resolve().parents[2] / "logs"
    logs_dir.mkdir(exist_ok=True)
    handler = TimedRotatingFileHandler(
        logs_dir / "bot.log", when="midnight", backupCount=14, encoding="utf-8",
    )
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(fmt)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[handler, stream])
    # quiet noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)


async def _run() -> None:
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)

    app = build_application(settings)

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        send_digest,
        trigger=CronTrigger(
            day_of_week="sun",
            hour=settings.digest_hour,
            minute=settings.digest_minute,
            timezone=tz,
        ),
        kwargs={"settings": settings},
        id="weekly_digest",
        replace_existing=True,
    )
    scheduler.start()
    logging.info("scheduler started; next digest: %s",
                 scheduler.get_job("weekly_digest").next_run_time)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logging.info("bot started (long-polling)")
    try:
        # block forever
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        scheduler.shutdown(wait=False)


def main() -> None:
    _setup_logging()
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logging.info("shutdown requested")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test — module imports and shows scheduler info**

Add a tiny test for the wiring:

`tests/test_main.py`:
```python
def test_main_module_imports():
    from inbox_bot import main
    assert callable(main.main)
```

```bash
uv run pytest tests/test_main.py -v
```
Expected: 1 passed.

- [ ] **Step 3: Live boot test (with real `.env`, kill after 5s)**

```bash
cd ~/Projects/telegram-inbox-bot
timeout 5 uv run python -m inbox_bot.main || true
```
Expected output includes: `scheduler started; next digest: <some Sunday at 07:30+08:00>` and `bot started (long-polling)`. Then exits on timeout (exit code 124 from `timeout`). No tracebacks.

- [ ] **Step 4: Manual end-to-end test**

Run the bot in foreground:
```bash
cd ~/Projects/telegram-inbox-bot && uv run python -m inbox_bot.main
```
Open Telegram, post a screenshot to your channel. Expected within ~5 seconds:
- bot replies with `<emoji> → https://www.notion.so/<page>`
- Open Notion: a new row in the matching DB with extracted fields

Test each category at least once (7 categories + 1 low-confidence Inbox test by posting a deliberately ambiguous screenshot).

Ctrl-C to stop.

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/main.py tests/test_main.py
git commit -m "feat: main entrypoint wires bot + apscheduler weekly digest"
```

---

## Task 11: Launchd deployment (`launchd/com.shao.telegram-inbox.plist`)

**Files:**
- Create: `launchd/com.shao.telegram-inbox.plist`
- Modify: `README.md` (already has the load command from Task 2)

**Interfaces:** none (deployment artifact)

- [ ] **Step 1: Write the plist**

`launchd/com.shao.telegram-inbox.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.shao.telegram-inbox</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/shao/.local/bin/uv</string>
        <string>run</string>
        <string>python</string>
        <string>-m</string>
        <string>inbox_bot.main</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/shao/Projects/telegram-inbox-bot</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>

    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>StandardOutPath</key>
    <string>/Users/shao/Projects/telegram-inbox-bot/logs/launchd.out.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/shao/Projects/telegram-inbox-bot/logs/launchd.err.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/shao/.local/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

- [ ] **Step 2: Verify `uv` path matches your install**

```bash
which uv
```
If not `/Users/shao/.local/bin/uv`, update the `ProgramArguments` first entry to match.

- [ ] **Step 3: Install and load (on Mac Studio)**

```bash
cp ~/Projects/telegram-inbox-bot/launchd/com.shao.telegram-inbox.plist \
   ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.shao.telegram-inbox.plist
launchctl list | grep com.shao.telegram-inbox
```
Expected: a line like `12345  0  com.shao.telegram-inbox` (PID, last exit code 0, label).

- [ ] **Step 4: Verify it's actually running**

```bash
tail -f ~/Projects/telegram-inbox-bot/logs/bot.log
```
Expected: `scheduler started; next digest: <Sunday>` then `bot started (long-polling)`. Ctrl-C the tail.

Post a screenshot to Telegram — verify Notion row appears.

- [ ] **Step 5: Document unload command in README**

Append to `README.md`:
```markdown
### To stop / restart the daemon

```bash
launchctl unload ~/Library/LaunchAgents/com.shao.telegram-inbox.plist
launchctl load   ~/Library/LaunchAgents/com.shao.telegram-inbox.plist
```

### Logs

- App: `logs/bot.log` (rotated daily, 14 days kept)
- launchd: `logs/launchd.out.log`, `logs/launchd.err.log`
```

- [ ] **Step 6: Commit**

```bash
git add launchd/com.shao.telegram-inbox.plist README.md
git commit -m "chore: launchd plist for KeepAlive deployment"
```

---

## Done criteria

- [ ] All 11 tasks committed
- [ ] `uv run pytest` shows ~20+ tests passing
- [ ] launchctl shows daemon running on Mac Studio
- [ ] Manual: posting a restaurant screenshot creates a row in 🍴 餐廳 with Maps Link in <10s
- [ ] Manual: posting an ambiguous lock-screen image lands in 🗂 Inbox
- [ ] Manual (after first Sunday): receive the 07:30 digest in Telegram
