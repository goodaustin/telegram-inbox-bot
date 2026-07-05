# Friend Windows 11 Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Windows 11 replication package for the telegram-inbox-bot friend: config-driven custom categories the friend can add/remove himself, a `DIGEST_ENABLED` off-switch, and a Traditional-Chinese Windows guide (markdown + printable HTML).

**Architecture:** Built-in 10 categories stay hard-coded and untouched. A new thin "custom categories" layer (`custom_categories.toml` + `categories.py`) feeds extra categories into the classifier enum/prompt, the DB-id lookup, the Notion property builder, and the provisioning script. A `DIGEST_ENABLED` flag gates the weekly-digest scheduler. All changes are backward-compatible: no toml + `DIGEST_ENABLED=true` (defaults) → Shao's existing bot behaves identically.

**Tech Stack:** Python 3.11+ (stdlib `tomllib` for reading TOML), pydantic-settings, pytest, python-telegram-bot, notion-client, apscheduler, Windows `winget`/`schtasks`/batch.

## Global Constraints

- Python floor: `>=3.11` (use stdlib `tomllib`; no third-party TOML dep).
- Built-in 10 categories (`restaurant, place, todo, article, quote, apparel, skincare, photo, funny, inbox`) — their enum, prompt text, Notion field schema, and provisioning must NOT change.
- `notion-client >=2.2,<2.4` (Notion-Version 2022-06-28) — unchanged.
- Backward compatibility is mandatory: absent `custom_categories.toml` and `DIGEST_ENABLED` default `True` must reproduce current behavior exactly. All existing tests must stay green.
- Custom-category key rule: `^[a-z][a-z0-9_]*$`, unique, must not collide with a built-in key.
- Custom-category env var name: `NOTION_DB_<KEY.upper()>`.
- Custom-category standard Notion fields (exact, in this order): `Name` (title), `Notes` (rich_text), `Tags` (multi_select), `Source` (url), `Date Added` (date).
- All friend-facing docs are Traditional Chinese. The friend guide must contain NO reminder/digest content of any kind.
- Repo root path in code: `Path(__file__).resolve().parents[2]` from within `src/inbox_bot/`.

---

## File Structure

**Create:**
- `custom_categories.toml` — friend-editable list of extra categories (ships with a commented example, zero active entries).
- `src/inbox_bot/categories.py` — single source of truth for category keys; loads/validates custom categories; renders the prompt section.
- `tests/test_provision_notion.py` — tests for the provisioning helper.

**Modify (schema):**
- `src/inbox_bot/schemas.py` — `ClassifierResult.category` accepts any key in `all_category_keys()` (built-ins + custom) instead of the fixed `Category` Literal, while still rejecting unknown categories. The `Category` Literal and `CATEGORY_FIELD_SCHEMAS` (built-ins only) stay as-is.
- `windows/run_bot.bat` — self-restarting launcher for Windows autostart.
- `docs/friend-setup-windows.md` — Traditional-Chinese Windows guide.
- `docs/friend-setup-windows.html` — printable self-contained HTML version.
- `tests/test_categories.py` — tests for the registry module.

**Modify:**
- `src/inbox_bot/config.py` — add `digest_enabled`; custom-key path in `db_id_for_category`; ignore extra env.
- `src/inbox_bot/classifier.py` — build category enum + JSON instruction + prompt from `categories`.
- `src/inbox_bot/notion_writer.py` — `build_properties` standard-field branch for custom keys.
- `src/inbox_bot/main.py` — schedule digest only when `digest_enabled`.
- `scripts/provision_notion.py` — `add` subcommand to provision custom tables.
- `.env.example` — add `DIGEST_ENABLED=true`.

---

## Task 1: `categories.py` registry + `custom_categories.toml` template

**Files:**
- Create: `src/inbox_bot/categories.py`
- Create: `custom_categories.toml`
- Test: `tests/test_categories.py`

**Interfaces:**
- Consumes: nothing (foundational).
- Produces:
  - `BUILTIN_KEYS: list[str]` — the 10 built-in keys in canonical order.
  - `class CategoryConfigError(Exception)`.
  - `@dataclass(frozen=True) class CustomCategory` with fields `key: str`, `name: str`, `hint: str` and property `env_var -> str` (= `f"NOTION_DB_{self.key.upper()}"`).
  - `load_custom_categories(path: Path | None = None) -> list[CustomCategory]` — reads TOML at `path` (default: repo-root `custom_categories.toml`); returns `[]` if the file is missing or has no `[[category]]`; raises `CategoryConfigError` on invalid entries.
  - `get_custom_categories() -> list[CustomCategory]` — cached default-path loader.
  - `all_category_keys(customs: list[CustomCategory] | None = None) -> list[str]` — `BUILTIN_KEYS + [c.key for c in customs]` (customs default via `get_custom_categories()`).
  - `custom_category_keys(customs: list[CustomCategory] | None = None) -> set[str]`.
  - `render_custom_prompt_section(customs: list[CustomCategory] | None = None) -> str` — returns `""` if no customs, else a `## 你自訂的分類` markdown block.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_categories.py
import textwrap
from pathlib import Path
import pytest
from inbox_bot.categories import (
    BUILTIN_KEYS, CustomCategory, CategoryConfigError,
    load_custom_categories, all_category_keys, custom_category_keys,
    render_custom_prompt_section,
)


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "custom_categories.toml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_missing_file_returns_empty(tmp_path):
    assert load_custom_categories(tmp_path / "nope.toml") == []


def test_empty_file_returns_empty(tmp_path):
    p = _write(tmp_path, "# only comments\n")
    assert load_custom_categories(p) == []


def test_loads_valid_category(tmp_path):
    p = _write(tmp_path, """
        [[category]]
        key = "recipe"
        name = "食譜"
        hint = "食譜、料理作法"
    """)
    cats = load_custom_categories(p)
    assert cats == [CustomCategory(key="recipe", name="食譜", hint="食譜、料理作法")]
    assert cats[0].env_var == "NOTION_DB_RECIPE"


def test_key_colliding_with_builtin_rejected(tmp_path):
    p = _write(tmp_path, """
        [[category]]
        key = "todo"
        name = "待辦2"
        hint = "x"
    """)
    with pytest.raises(CategoryConfigError, match="todo"):
        load_custom_categories(p)


def test_duplicate_custom_key_rejected(tmp_path):
    p = _write(tmp_path, """
        [[category]]
        key = "recipe"
        name = "食譜"
        hint = "x"
        [[category]]
        key = "recipe"
        name = "食譜B"
        hint = "y"
    """)
    with pytest.raises(CategoryConfigError, match="recipe"):
        load_custom_categories(p)


@pytest.mark.parametrize("bad", ["Recipe", "my recipe", "3recipe", "recipe!", ""])
def test_invalid_key_shape_rejected(tmp_path, bad):
    p = _write(tmp_path, f"""
        [[category]]
        key = "{bad}"
        name = "x"
        hint = "y"
    """)
    with pytest.raises(CategoryConfigError):
        load_custom_categories(p)


def test_missing_name_or_hint_rejected(tmp_path):
    p = _write(tmp_path, """
        [[category]]
        key = "recipe"
        name = ""
        hint = "y"
    """)
    with pytest.raises(CategoryConfigError, match="recipe"):
        load_custom_categories(p)


def test_all_and_custom_keys():
    cats = [CustomCategory(key="recipe", name="食譜", hint="h")]
    assert all_category_keys(cats) == BUILTIN_KEYS + ["recipe"]
    assert custom_category_keys(cats) == {"recipe"}
    assert "inbox" in BUILTIN_KEYS


def test_render_prompt_section():
    assert render_custom_prompt_section([]) == ""
    cats = [CustomCategory(key="recipe", name="食譜", hint="食譜、料理作法")]
    section = render_custom_prompt_section(cats)
    assert "你自訂的分類" in section
    assert "recipe" in section
    assert "食譜" in section
    assert "食譜、料理作法" in section
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_categories.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'inbox_bot.categories'`.

- [ ] **Step 3: Write `categories.py`**

```python
# src/inbox_bot/categories.py
import re
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BUILTIN_KEYS: list[str] = [
    "restaurant", "place", "todo", "article", "quote",
    "apparel", "skincare", "photo", "funny", "inbox",
]

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "custom_categories.toml"


class CategoryConfigError(Exception):
    pass


@dataclass(frozen=True)
class CustomCategory:
    key: str
    name: str
    hint: str

    @property
    def env_var(self) -> str:
        return f"NOTION_DB_{self.key.upper()}"


def load_custom_categories(path: Path | None = None) -> list[CustomCategory]:
    path = _DEFAULT_PATH if path is None else path
    if not path.exists():
        return []
    with path.open("rb") as f:
        data = tomllib.load(f)
    raw = data.get("category", [])
    cats: list[CustomCategory] = []
    seen: set[str] = set()
    for i, entry in enumerate(raw):
        key = entry.get("key", "")
        name = entry.get("name", "")
        hint = entry.get("hint", "")
        if not isinstance(key, str) or not _KEY_RE.match(key):
            raise CategoryConfigError(
                f"custom_categories.toml 第 {i + 1} 塊：key {key!r} 不合法"
                "（需小寫英文開頭、只含小寫英數與底線）"
            )
        if key in BUILTIN_KEYS:
            raise CategoryConfigError(f"custom_categories.toml：key {key!r} 與內建分類衝突")
        if key in seen:
            raise CategoryConfigError(f"custom_categories.toml：key {key!r} 重複")
        if not (isinstance(name, str) and name.strip()):
            raise CategoryConfigError(f"custom_categories.toml：分類 {key!r} 的 name 不可空白")
        if not (isinstance(hint, str) and hint.strip()):
            raise CategoryConfigError(f"custom_categories.toml：分類 {key!r} 的 hint 不可空白")
        seen.add(key)
        cats.append(CustomCategory(key=key, name=name.strip(), hint=hint.strip()))
    return cats


@lru_cache
def get_custom_categories() -> list[CustomCategory]:
    return load_custom_categories()


def all_category_keys(customs: list[CustomCategory] | None = None) -> list[str]:
    customs = get_custom_categories() if customs is None else customs
    return BUILTIN_KEYS + [c.key for c in customs]


def custom_category_keys(customs: list[CustomCategory] | None = None) -> set[str]:
    customs = get_custom_categories() if customs is None else customs
    return {c.key for c in customs}


def render_custom_prompt_section(customs: list[CustomCategory] | None = None) -> str:
    customs = get_custom_categories() if customs is None else customs
    if not customs:
        return ""
    lines = ["\n\n## 你自訂的分類\n"]
    for c in customs:
        lines.append(
            f"- **{c.key}**（{c.name}）— {c.hint}。"
            "Extract: name（標題）, notes（一行備註，可空）, tags（主題標籤陣列，可空）。"
        )
    return "\n".join(lines)
```

- [ ] **Step 4: Create the `custom_categories.toml` template**

```toml
# custom_categories.toml
# 在這裡新增你自己的資料庫分類。
# 每一塊 [[category]] 就是一個新資料庫。複製一整塊、改三個地方即可，存檔後重啟機器人。
#
# 範例：想收集食譜，就照下面新增一塊（把每行開頭的 # 拿掉）：
#
# [[category]]
# key  = "recipe"        # 英文小寫代號，不能有空格；會對應 .env 的 NOTION_DB_RECIPE
# name = "食譜"           # 在 Notion 顯示的表格名稱
# hint = "食譜、料理作法、想煮的菜、菜單截圖"   # 告訴 AI 什麼東西該歸到這一類
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_categories.py -v`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add src/inbox_bot/categories.py custom_categories.toml tests/test_categories.py
git commit -m "feat: custom-category registry (categories.py + custom_categories.toml)"
```

---

## Task 1B: `schemas.py` — allow custom categories in `ClassifierResult`

**Files:**
- Modify: `src/inbox_bot/schemas.py`
- Test: `tests/test_schemas.py`

**Why:** `ClassifierResult.category` is currently `Category` (a `Literal` of the 10 built-ins). A custom category like `"recipe"` would raise `ValidationError` and break the whole feature. Loosen the field to `str` with a validator that accepts anything in `all_category_keys()` (built-ins + custom) and rejects the rest — preserving the "reject a hallucinated category" safety. Keep the `Category` Literal and `CATEGORY_FIELD_SCHEMAS` untouched (they are consumed by `test_bot.py::test_category_emoji_covers_all_categories` via `get_args(Category)` and by `test_schemas.py`).

**Interfaces:**
- Consumes: `categories.all_category_keys()` (Task 1), imported lazily inside the validator to avoid any import cycle.
- Produces: `ClassifierResult` accepting built-in + custom category keys; rejecting unknown ones with `ValidationError`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_schemas.py`)

```python
def test_classifier_result_accepts_builtin_category():
    r = ClassifierResult(category="todo", confidence=0.9, raw_text="x")
    assert r.category == "todo"


def test_classifier_result_rejects_unknown_category():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ClassifierResult(category="not_a_category", confidence=0.9, raw_text="x")


def test_classifier_result_accepts_custom_category(monkeypatch):
    import inbox_bot.categories as cats
    from inbox_bot.categories import CustomCategory
    monkeypatch.setattr(cats, "get_custom_categories",
                        lambda: [CustomCategory("recipe", "食譜", "h")])
    r = ClassifierResult(category="recipe", confidence=0.9, raw_text="x")
    assert r.category == "recipe"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_schemas.py -k "accepts_custom or rejects_unknown or accepts_builtin" -v`
Expected: FAIL — `accepts_custom` raises `ValidationError` (Literal rejects `"recipe"`).

- [ ] **Step 3: Edit `schemas.py`**

Add `field_validator` to the import and change the field. Keep `Category` and `CATEGORY_FIELD_SCHEMAS` exactly as they are.

```python
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

Category = Literal[
    "restaurant", "place", "todo", "article",
    "quote", "apparel", "skincare", "photo", "funny", "inbox",
]


class ClassifierResult(BaseModel):
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    raw_text: str
    fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        from inbox_bot.categories import all_category_keys
        if v not in all_category_keys():
            raise ValueError(f"unknown category: {v!r}")
        return v
```

(Leave `CATEGORY_FIELD_SCHEMAS` unchanged below the class.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: PASS (new + existing).

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/schemas.py tests/test_schemas.py
git commit -m "feat: ClassifierResult.category accepts custom categories"
```

---

## Task 2: `config.py` — `digest_enabled` + custom-key DB lookup

**Files:**
- Modify: `src/inbox_bot/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing new (reads custom db-ids straight from `os.environ`).
- Produces:
  - `Settings.digest_enabled: bool = True`.
  - `db_id_for_category(category, settings)` now returns `os.environ["NOTION_DB_<KEY>"]` for a non-built-in key when that env var is set, else `settings.notion_db_inbox`.
  - `Settings.model_config` gains `extra="ignore"` so unrecognized `NOTION_DB_*` env vars don't raise.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_config.py`)

```python
def test_digest_enabled_defaults_true(fake_env, monkeypatch):
    monkeypatch.delenv("DIGEST_ENABLED", raising=False)
    assert Settings(_env_file=None).digest_enabled is True


def test_digest_enabled_false_from_env(fake_env, monkeypatch):
    monkeypatch.setenv("DIGEST_ENABLED", "false")
    assert Settings(_env_file=None).digest_enabled is False


def test_db_id_for_custom_category_reads_env(fake_env, monkeypatch):
    monkeypatch.setenv("NOTION_DB_RECIPE", "db_recipe")
    s = Settings()
    assert db_id_for_category("recipe", s) == "db_recipe"


def test_db_id_for_custom_without_env_falls_back_to_inbox(fake_env, monkeypatch):
    monkeypatch.delenv("NOTION_DB_RECIPE", raising=False)
    s = Settings()
    assert db_id_for_category("recipe", s) == "db_inbox"


def test_extra_notion_db_env_does_not_break_settings(fake_env, monkeypatch):
    monkeypatch.setenv("NOTION_DB_RECIPE", "db_recipe")
    s = Settings()  # must not raise on the extra env var
    assert s.notion_db_inbox == "db_inbox"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -k "digest_enabled or custom or extra_notion" -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'digest_enabled'` and custom lookups returning `db_inbox` prematurely / or extra-env errors depending on pydantic default.

- [ ] **Step 3: Edit `config.py`**

Add `import os` and `import logging` at top; add a module logger `log = logging.getLogger(__name__)`.

In `SettingsConfigDict(...)` add `extra="ignore"`:

```python
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False,
        extra="ignore",
    )
```

Add the field (next to `digest_minute`):

```python
    digest_enabled: bool = True
```

Replace `db_id_for_category` with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (new + existing, including `test_db_id_for_unknown_category_falls_back_to_inbox`).

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/config.py tests/test_config.py
git commit -m "feat: DIGEST_ENABLED flag + custom-category DB-id lookup in config"
```

---

## Task 3: `main.py` — gate digest scheduling on `digest_enabled`

**Files:**
- Modify: `src/inbox_bot/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `Settings.digest_enabled` (Task 2).
- Produces: a testable helper `register_digest_job(scheduler, settings) -> bool` that adds the `weekly_digest` job and returns `True`, or does nothing and returns `False` when `digest_enabled` is falsy.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_main.py`)

```python
from unittest.mock import MagicMock
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from inbox_bot.main import register_digest_job


def _settings(enabled: bool):
    return SimpleNamespace(
        digest_enabled=enabled, digest_hour=7, digest_minute=30,
        timezone="Asia/Taipei",
    )


def test_register_digest_job_adds_when_enabled():
    sched = MagicMock()
    assert register_digest_job(sched, _settings(True)) is True
    sched.add_job.assert_called_once()


def test_register_digest_job_skips_when_disabled():
    sched = MagicMock()
    assert register_digest_job(sched, _settings(False)) is False
    sched.add_job.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL — `ImportError: cannot import name 'register_digest_job'`.

- [ ] **Step 3: Edit `main.py`**

Extract the scheduler job registration into a helper and call it from `_run`. Replace the inline `scheduler.add_job(...)` block with:

```python
def register_digest_job(scheduler, settings) -> bool:
    if not settings.digest_enabled:
        logging.info("weekly digest disabled by config (DIGEST_ENABLED=false)")
        return False
    tz = ZoneInfo(settings.timezone)
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
    return True
```

In `_run`, replace the old `scheduler.add_job(...)` + `scheduler.get_job("weekly_digest")` logging block with:

```python
    scheduler = AsyncIOScheduler(timezone=tz)
    if register_digest_job(scheduler, settings):
        scheduler.start()
        job = scheduler.get_job("weekly_digest")
        logging.info("scheduler started; next digest: %s", job.next_run_time if job else "?")
    else:
        scheduler.start()  # started but no jobs; harmless and keeps shutdown symmetric
```

(Keep the existing `scheduler.shutdown(wait=False)` in the `finally` block.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/main.py tests/test_main.py
git commit -m "feat: skip weekly-digest scheduling when DIGEST_ENABLED=false"
```

---

## Task 4: `classifier.py` — dynamic enum + prompt from `categories`

**Files:**
- Modify: `src/inbox_bot/classifier.py`
- Test: `tests/test_classifier.py`

**Interfaces:**
- Consumes: `categories.all_category_keys()`, `categories.render_custom_prompt_section()`.
- Produces:
  - `_build_openai_tool(keys: list[str]) -> dict` — function tool whose `category.enum == keys`.
  - `_json_instruction(keys: list[str]) -> str`.
  - `classify(...)` composes the system prompt as `classify.md text + render_custom_prompt_section()` and uses `all_category_keys()` for the enum in both the OpenAI-tool and Gemini-JSON paths.
- `CLASSIFY_TOOL` stays exported (built-in enum) for reference/tests.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_classifier.py`)

```python
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
```

> Patch `get_custom_categories` (not `classifier.all_category_keys`): `all_category_keys`, `custom_category_keys`, `render_custom_prompt_section`, and the `schemas.py` validator all funnel through it, so one patch keeps them consistent.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_classifier.py -k "openai_tool or json_instruction or custom_category" -v`
Expected: FAIL — `ImportError: cannot import name '_build_openai_tool'`.

- [ ] **Step 3: Edit `classifier.py`**

Add imports:

```python
from inbox_bot.categories import all_category_keys, render_custom_prompt_section
```

Add builder functions (near the existing `_OPENAI_TOOL`):

```python
def _build_openai_tool(keys: list[str]) -> dict[str, Any]:
    schema = {
        "type": "object",
        "required": ["category", "confidence", "raw_text", "fields"],
        "properties": {
            "category": {"type": "string", "enum": keys},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "raw_text": {"type": "string"},
            "fields": {"type": "object"},
        },
    }
    return {"type": "function", "function": {
        "name": "classify_item",
        "description": CLASSIFY_TOOL["description"],
        "parameters": schema,
    }}


def _json_instruction(keys: list[str]) -> str:
    return (
        "\n\n---\n"
        "Return ONLY a single JSON object — no markdown, no code fences, no prose — "
        "with exactly these keys:\n"
        '- "category": one of ' + ", ".join(keys) + "\n"
        '- "confidence": a number from 0 to 1\n'
        '- "raw_text": a string (OCR of the image, or echo of the input text)\n'
        '- "fields": a JSON object holding the extracted fields for that category\n'
    )
```

Change `_request_args` signature to accept `keys: list[str]` and use the builders:
- Gemini path: `messages` system content = `system + _json_instruction(keys)`.
- OpenAI path: `tools=[_build_openai_tool(keys)]`.

In `classify(...)`, compute keys + prompt once. **Preserve the existing `_route_known_url(text)` short-circuit at the top of `classify()` and the whole retry/low-confidence loop exactly** — only the `system`/enum wiring changes:

```python
    # ... keep the existing _route_known_url short-circuit above, unchanged ...
    if client is None:
        client = _make_client(settings)

    keys = all_category_keys()
    system = _load_system_prompt() + render_custom_prompt_section()
    content = _build_content(image_bytes, text)
    # ... inside the retry loop, the only change is the call signature:
    args = await _request_args(client, settings, system, content, keys)
```

Leave the old module-level `_OPENAI_TOOL`, `_CATEGORY_ENUM`, `_JSON_INSTRUCTION` in place OR remove them if now unused — remove `_JSON_INSTRUCTION`/`_OPENAI_TOOL`/`_CATEGORY_ENUM` only after confirming nothing else imports them (`grep -rn "_OPENAI_TOOL\|_JSON_INSTRUCTION\|_CATEGORY_ENUM" src tests`). Keep `CLASSIFY_TOOL`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_classifier.py -v`
Expected: PASS (new + existing).

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/classifier.py tests/test_classifier.py
git commit -m "feat: classifier enum/prompt built from category registry (custom-aware)"
```

---

## Task 5: `notion_writer.py` — standard fields for custom categories

**Files:**
- Modify: `src/inbox_bot/notion_writer.py`
- Test: `tests/test_notion_writer.py`

**Interfaces:**
- Consumes: `categories.custom_category_keys()`.
- Produces: `build_properties(category, fields, telegram_url, maps_link, now)` returns the standard-field dict `{Name, Notes, Tags, Source, Date Added}` for any `category` in `custom_category_keys()`; built-in branches unchanged; inbox fallback unchanged.

- [ ] **Step 1: Write the failing test** (append to `tests/test_notion_writer.py`)

```python
from datetime import datetime
from zoneinfo import ZoneInfo
import inbox_bot.notion_writer as nw
from inbox_bot.notion_writer import build_properties


def test_custom_category_uses_standard_fields(monkeypatch):
    monkeypatch.setattr(nw, "custom_category_keys", lambda customs=None: {"recipe"})
    now = datetime(2026, 7, 5, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="recipe",
        fields={"name": "番茄炒蛋", "notes": "簡單", "tags": ["家常", "蛋"]},
        telegram_url="https://t.me/c/1/2",
        maps_link=None,
        now=now,
    )
    assert set(props) == {"Name", "Notes", "Tags", "Source", "Date Added"}
    assert props["Name"]["title"][0]["text"]["content"] == "番茄炒蛋"
    assert [t["name"] for t in props["Tags"]["multi_select"]] == ["家常", "蛋"]
    assert props["Source"]["url"] == "https://t.me/c/1/2"


def test_unknown_noncustom_category_still_inbox_fallback(monkeypatch):
    monkeypatch.setattr(nw, "custom_category_keys", lambda customs=None: set())
    now = datetime(2026, 7, 5, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties("mystery", {"reason": "x"}, "u", None, now)
    assert "Raw Text" in props  # inbox schema
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_notion_writer.py -k "custom_category or noncustom" -v`
Expected: FAIL — custom category currently falls through to inbox schema (`"Name"` not present / `"Raw Text"` present).

- [ ] **Step 3: Edit `notion_writer.py`**

Add import:

```python
from inbox_bot.categories import custom_category_keys
```

In `build_properties`, insert BEFORE the `# inbox fallback` return:

```python
    if category in custom_category_keys():
        return {
            "Name": _title(g("name", "")),
            "Notes": _text(g("notes", "")),
            "Tags": _multi(g("tags") or []),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_notion_writer.py -v`
Expected: PASS (new + existing).

- [ ] **Step 5: Commit**

```bash
git add src/inbox_bot/notion_writer.py tests/test_notion_writer.py
git commit -m "feat: write custom-category items with standard Notion fields"
```

---

## Task 6: `provision_notion.py` — `add` subcommand for custom tables

**Files:**
- Modify: `scripts/provision_notion.py`
- Test: `tests/test_provision_notion.py` (create)

**Interfaces:**
- Consumes: `categories.load_custom_categories()`.
- Produces:
  - Module-level `STANDARD_PROPS: dict` (the 5 standard Notion properties).
  - `build_env_lines_for_customs(customs) -> list[str]` — pure helper returning `["NOTION_DB_RECIPE=<placeholder>"]`-style lines is NOT needed; instead expose `custom_db_definitions(customs) -> list[tuple[str, str, dict]]` returning `(env_var, title, props)` per custom category, so the async create loop and tests share one source. Built-in `DBS` and full-provision behavior unchanged.
  - CLI: `provision_notion.py <PARENT>` → build 10 built-ins (unchanged). `provision_notion.py add <PARENT>` → create custom tables from `custom_categories.toml`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_provision_notion.py
from inbox_bot.categories import CustomCategory
import importlib.util, pathlib

spec = importlib.util.spec_from_file_location(
    "provision_notion",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "provision_notion.py",
)
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)


def test_custom_db_definitions_shape():
    cats = [CustomCategory(key="recipe", name="食譜", hint="h")]
    defs = provision.custom_db_definitions(cats)
    assert len(defs) == 1
    env_var, title, props = defs[0]
    assert env_var == "NOTION_DB_RECIPE"
    assert title == "食譜"
    assert set(props) == {"Name", "Notes", "Tags", "Source", "Date Added"}
    assert props["Name"] == {"title": {}}
    assert props["Tags"] == {"multi_select": {}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_provision_notion.py -v`
Expected: FAIL — `AttributeError: module 'provision_notion' has no attribute 'custom_db_definitions'`.

- [ ] **Step 3: Edit `provision_notion.py`**

Add at top: `from inbox_bot.categories import load_custom_categories, CustomCategory`.

Add module-level:

```python
STANDARD_PROPS: dict = {
    "Name": {"title": {}},
    "Notes": {"rich_text": {}},
    "Tags": {"multi_select": {}},
    "Source": {"url": {}},
    "Date Added": {"date": {}},
}


def custom_db_definitions(customs: list["CustomCategory"]) -> list[tuple[str, str, dict]]:
    return [(c.env_var, c.name, dict(STANDARD_PROPS)) for c in customs]
```

Rewrite `main()` to branch on `add`:

```python
async def main() -> None:
    argv = sys.argv[1:]
    add_mode = bool(argv) and argv[0] == "add"
    if add_mode:
        argv = argv[1:]
    if not argv:
        raise SystemExit(
            "用法：\n"
            "  建全部內建表：uv run python scripts/provision_notion.py <PARENT_PAGE_ID>\n"
            "  只建自訂表：  uv run python scripts/provision_notion.py add <PARENT_PAGE_ID>"
        )
    parent_page_id = argv[0]
    load_dotenv()
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise SystemExit("找不到 NOTION_TOKEN（請先在 .env 填好）")
    client = AsyncClient(auth=token)

    if add_mode:
        customs = load_custom_categories()
        if not customs:
            raise SystemExit("custom_categories.toml 沒有任何分類；請先在裡面新增一塊 [[category]]")
        defs = custom_db_definitions(customs)
    else:
        defs = [(env, title, props) for env, (title, props) in DBS.items()]

    lines: list[str] = []
    for env_name, title, props in defs:
        db = await client.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": title}}],
            properties=props,
        )
        print(f"建立完成：{title}")
        lines.append(f"{env_name}={db['id'].replace('-', '')}")

    print("\n# ↓↓↓ 把下面全部貼進 .env ↓↓↓")
    print("\n".join(lines))
    if not add_mode:
        print("\n提醒：到 Notion 的「待辦」DB 手動新增一個 Status 欄位（status 型）。")
        print("      保留 Notion 的預設選項即可（Not started / In progress / Done）——")
        print("      bot 會寫入狀態「Not started」、每週摘要會過濾「Done」，請勿改成 Todo/Done。")
```

- [ ] **Step 4: Run test to verify it passes + full suite**

Run: `uv run pytest tests/test_provision_notion.py -v && uv run pytest -q`
Expected: PASS (new test) and the whole suite green.

- [ ] **Step 5: Commit**

```bash
git add scripts/provision_notion.py tests/test_provision_notion.py
git commit -m "feat: provision_notion 'add' mode builds custom-category tables"
```

---

## Task 7: `.env.example` — add `DIGEST_ENABLED`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Edit `.env.example`**

Insert after the `TIMEZONE=Asia/Taipei` line:

```
# 週日摘要提醒開關：true=啟用（預設）；朋友端不要提醒就設 false
DIGEST_ENABLED=true
```

Leave `DIGEST_HOUR` / `DIGEST_MINUTE` as-is (harmless when disabled).

- [ ] **Step 2: Verify**

Run: `grep DIGEST_ENABLED .env.example`
Expected: prints the new line.

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "docs: add DIGEST_ENABLED to .env.example"
```

---

## Task 8: `windows/run_bot.bat` — self-restarting launcher

**Files:**
- Create: `windows/run_bot.bat`

- [ ] **Step 1: Create the file** (exact content — CRLF not required, cmd tolerates LF)

```bat
@echo off
REM 自動啟動並在當掉時自動重跑的機器人啟動器。
REM 此檔位於專案的 windows\ 資料夾；%~dp0.. 會回到專案根目錄。
cd /d "%~dp0.."
:loop
echo [%date% %time%] 啟動機器人...
uv run python -m inbox_bot.main
echo [%date% %time%] 機器人結束，5 秒後重新啟動... (要永久停止請關閉此視窗)
timeout /t 5 /nobreak >nul
goto loop
```

- [ ] **Step 2: Verify it exists and reads correctly**

Run: `cat windows/run_bot.bat`
Expected: prints the batch content above.

- [ ] **Step 3: Commit**

```bash
git add windows/run_bot.bat
git commit -m "feat: windows/run_bot.bat self-restarting launcher"
```

---

## Task 9: `docs/friend-setup-windows.md` — Traditional-Chinese Windows guide

**Files:**
- Create: `docs/friend-setup-windows.md`
- Reference: `docs/friend-setup-macos.md` (adapt tone/structure), spec §3–§5.

**This task authors documentation.** Adapt the macOS guide's structure and beginner-friendly voice, applying the Windows substitutions and the two behavioral changes (no digest, custom categories). The technical substance below is EXACT and must appear verbatim; adapt the surrounding prose from the macOS guide.

- [ ] **Step 1: Write the guide** with these sections and exact commands:

**Front matter / intro:** same reassuring tone as macOS版; note grey boxes are commands to paste into 終端機. Add: 對象是完全沒學過電腦的人 → 每個名詞第一次出現都白話解釋、每節開頭一句「這步在做什麼、為什麼」。

**0. 這是什麼／準備什麼** — 一台長時間開機的 Windows 11 電腦、Google 帳號、Notion 帳號、手機 Telegram。開終端機：開始功能表輸入「終端機」按 Enter（或按 `Win + X` → 點「終端機」）。

**1. 裝工具（uv、git）** — Windows 11 內建 winget：
```
winget install --id=astral-sh.uv -e
```
```
winget install --id=Git.Git -e
```
驗證（**裝完要把終端機關掉重開**，PATH 才會更新）：
```
uv --version
```
```
git --version
```
> 卡住：若 `winget` 說找不到，開啟「Microsoft Store」更新「應用程式安裝程式」後再試。

**2. 取得程式碼**
```
git clone https://github.com/goodaustin/telegram-inbox-bot.git "$env:USERPROFILE\telegram-inbox-bot"
```
```
cd "$env:USERPROFILE\telegram-inbox-bot"
```
> 之後每次開新終端機都要先 `cd "$env:USERPROFILE\telegram-inbox-bot"`。確認位置：`pwd`（結尾應是 `\telegram-inbox-bot`）。

**3. 建 Telegram 機器人（拿 token）** — 同 macOS 第 3 步（BotFather → `/newbot`）。

**4. 建私人頻道 + 設機器人為管理員** — 同 macOS 第 4 步（含「沒設管理員一定失敗」警告）。

**5. 建 `.env`（先填 token）**
```
copy .env.example .env
```
```
notepad .env
```
先填 `TELEGRAM_BOT_TOKEN=`。最終 `.env` 範本（朋友版：Gemini + 不要提醒）——展示這份，並強調 `CLASSIFIER_PROVIDER=gemini`、`CLASSIFIER_MODEL=gemini-2.5-flash`、`OPENAI_API_KEY=` 留空、`DIGEST_ENABLED=false`：
```
TELEGRAM_BOT_TOKEN=剛剛 BotFather 給的
TELEGRAM_CHANNEL_ID=（第 6 步用腳本抓）
OPENAI_API_KEY=
CLASSIFIER_PROVIDER=gemini
GEMINI_API_KEY=（第 10 步取得）
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
CLASSIFIER_MODEL=gemini-2.5-flash
NOTION_TOKEN=（第 7 步取得）
NOTION_DB_RESTAURANT=（第 8 步腳本產生）
NOTION_DB_PLACE=（第 8 步腳本產生）
NOTION_DB_TODO=（第 8 步腳本產生）
NOTION_DB_ARTICLE=（第 8 步腳本產生）
NOTION_DB_QUOTE=（第 8 步腳本產生）
NOTION_DB_APPAREL=（第 8 步腳本產生）
NOTION_DB_SKINCARE=（第 8 步腳本產生）
NOTION_DB_PHOTO=（第 8 步腳本產生）
NOTION_DB_FUNNY=（第 8 步腳本產生）
NOTION_DB_INBOX=（第 8 步腳本產生）
CONFIDENCE_THRESHOLD=0.5
TIMEZONE=Asia/Taipei
DIGEST_ENABLED=false
```
> ⚠️ 範本原本是 `CLASSIFIER_PROVIDER=openai`、有 `OPENAI_API_KEY=sk-...` 和 `DIGEST_ENABLED=true`——照上面改掉。不需要提醒功能，所以 `DIGEST_ENABLED=false`。

**6. 抓頻道 ID**
```
uv run python scripts/get_channel_id.py
```
（到頻道貼一句話 → 複製印出的 `TELEGRAM_CHANNEL_ID=-100...` 貼進 `.env`。含「一直等待中 = 機器人沒設管理員」的解法。）

**7. 建 Notion Integration + 母頁面** — 同 macOS 第 7 步（含把母頁面 Connections 加 integration 的警告、複製母頁面 id）。

**8. 一鍵建 10 個內建表**
```
uv run python scripts/provision_notion.py <母頁面id>
```
（貼回 10 行 `NOTION_DB_...`。含 NOTION_TOKEN/權限錯誤解法。）

**9. 手動幫「待辦」加 `Status` 欄位** — 同 macOS 第 9 步（Status 型、保留 `Not started/In progress/Done`、絕不改名）。

**10. 拿 Gemini 金鑰** — 同 macOS 第 10 步（https://aistudio.google.com/apikey → 貼進 `GEMINI_API_KEY=`）。

**11. 裝套件 + 冒煙測試**
```
uv sync
```
```
uv run python -m inbox_bot.main
```
（頻道貼截圖 → 機器人回覆 emoji + Notion 連結；Notion 表格多一筆。確認後按 `Ctrl + C` 停。含「分類失敗 → 回報 Shao」「金鑰/額度錯誤」解法。）

**12. 設開機自動啟動（`run_bot.bat` + 工作排程器）**
先確認可手動跑起來（前一步已驗證）。註冊成「登入時自動啟動」，整段貼進終端機：
```
schtasks /create /tn "TelegramInboxBot" /tr "\"%USERPROFILE%\telegram-inbox-bot\windows\run_bot.bat\"" /sc onlogon /rl limited /f
```
立即啟動一次（不必登出）：
```
schtasks /run /tn "TelegramInboxBot"
```
查狀態：
```
schtasks /query /tn "TelegramInboxBot"
```
> 會冒出一個終端機小視窗，這是機器人本體。可以**最小化，但不要關閉**（關掉＝機器人停）。當掉時 `run_bot.bat` 會自動重開。
> 以後重開機它會自己啟動。若某次沒反應，重跑上面的 `schtasks /run` 那行即可。
別讓電腦睡眠：設定 → 系統 → 電源 → 螢幕與睡眠 → 「睡眠」全設「永不」。

**13.（新）自己新增／移除一個子資料庫（以「食譜」為例）** — 四步（spec §5），全程複製貼上：
1. `notepad custom_categories.toml` → 複製範例那塊、拿掉 `#`、改 `key="recipe"` / `name="食譜"` / `hint="..."`，存檔。
2. 建表：
```
uv run python scripts/provision_notion.py add <你的母頁面id>
```
→ 印出 `NOTION_DB_RECIPE=xxxx`。
3. `notepad .env` → 把 `NOTION_DB_RECIPE=xxxx` 貼進去存檔。
4. 重啟機器人：
```
schtasks /end /tn "TelegramInboxBot"
```
```
schtasks /run /tn "TelegramInboxBot"
```
之後貼食譜截圖就會自動歸到「食譜」表。
**移除**：把 `custom_categories.toml` 那塊刪掉 → 重啟（步驟 4）。Notion 舊表格自己去 Notion 刪。
常見錯誤小方塊：key 有空格或大寫、忘了重啟、母頁面 id 貼錯、還沒建表就先貼 id、內建 10 類用不到的放著不理即可（要真的砍內建才找 Shao）。

**14. 疑難排解速查表（Windows 版）** — 對照 macOS 版，改：`command not found`→關掉終端機重開/確認 winget 裝成功；launchd 相關列改成 `schtasks /query` 找不到 → 檢查路徑 `%USERPROFILE%\telegram-inbox-bot\windows\run_bot.bat` 是否存在。保留：沒設管理員、token 空格、Notion 權限、待辦 Status、Gemini 金鑰、分類失敗回報 Shao。

**15. 收工檢查清單** — `uv --version`/`git --version` 有版本號；`.env` 全填、`OPENAI_API_KEY` 空、`DIGEST_ENABLED=false`；Notion 母頁面 10 表；待辦有 Status；冒煙測試過；`schtasks /query /tn "TelegramInboxBot"` 有這個工作；電腦設不睡眠。**不含任何提醒相關項目。**

- [ ] **Step 2: Verify required content is present**

Run:
```bash
grep -c "DIGEST_ENABLED=false" docs/friend-setup-windows.md
grep -c "schtasks" docs/friend-setup-windows.md
grep -c "custom_categories.toml" docs/friend-setup-windows.md
grep -c "provision_notion.py add" docs/friend-setup-windows.md
! grep -iE "digest|摘要|週日|提醒" docs/friend-setup-windows.md
```
Expected: first four print counts ≥ 1; the last (negated grep for reminder words) exits 0 (i.e. NO matches — guide is reminder-free).

- [ ] **Step 3: Commit**

```bash
git add docs/friend-setup-windows.md
git commit -m "docs: Traditional-Chinese Windows 11 setup guide (no digest, custom categories)"
```

---

## Task 10: `docs/friend-setup-windows.html` — printable version

**Files:**
- Create: `docs/friend-setup-windows.html`
- Reference: `docs/friend-setup-windows.md` (same content, prettified).

**This task authors a self-contained printable HTML.** Same information as the markdown guide, styled for on-screen reading and printing.

- [ ] **Step 1: Write the HTML** with these requirements:
  - Single file, `<!DOCTYPE html>`, `<html lang="zh-Hant">`, UTF-8 meta.
  - ALL CSS inline in a `<style>` block; NO external resources (fonts/images/scripts) so it opens and prints offline.
  - Readable large type (base ≥ 16px, headings clearly larger), generous line-height, max content width ~800px centered.
  - Distinct visual treatments: numbered step cards; command blocks in a monospace box with light background; callout boxes for 提示 / ⚠️警告 / 「成功長這樣」（3 colors）.
  - `@media print { }`: white background, black text, sensible page breaks (`h2 { break-before: page }` or `.step { break-inside: avoid }`), hide nothing essential, A4-friendly margins.
  - Content mirrors all 15 sections of the markdown guide (Steps 0–15), including the exact commands from Task 9.
  - NO reminder/digest content anywhere.

- [ ] **Step 2: Verify**

Run:
```bash
grep -c "schtasks" docs/friend-setup-windows.html
grep -c "custom_categories.toml" docs/friend-setup-windows.html
grep -c "@media print" docs/friend-setup-windows.html
! grep -iE "digest|摘要|週日|提醒" docs/friend-setup-windows.html
```
Expected: first three ≥ 1; last exits 0 (no reminder words).
Also open in a browser to eyeball layout + print preview (Ctrl+P) if a browser is available.

- [ ] **Step 3: Commit**

```bash
git add docs/friend-setup-windows.html
git commit -m "docs: printable HTML version of the Windows setup guide"
```

---

## Final Verification

- [ ] **Full suite green:** `uv run pytest -q` — all pass (new + existing; confirms zero regression to Shao's built-in behavior).
- [ ] **Backward-compat smoke:** with no `custom_categories.toml` entries active and `DIGEST_ENABLED` unset, confirm `all_category_keys() == BUILTIN_KEYS` and `Settings().digest_enabled is True`.
  Run: `uv run python -c "from inbox_bot.categories import all_category_keys, BUILTIN_KEYS; assert all_category_keys()==BUILTIN_KEYS; print('ok')"`
- [ ] **Guide reminder-free:** the negated greps in Tasks 9 & 10 both pass.

## Self-Review (completed during planning)

- **Spec coverage:** §1a→T1; §1b→T1; §1c→T2; §1d→T4; §1e→T5; §1f→T6; §2→T2+T3; §3→T9; §4→T8+T9; §5→T9; §6→T10; `.env.example`→T7. Integration gap found during pre-flight and added: `ClassifierResult.category` Literal→custom (T1B). `bot.py` emoji lookup already `.get(...,"📥")`-safe → no task needed.
- **Placeholder scan:** no TBD/TODO; doc tasks (T9/T10) give exact commands verbatim + concrete section list + grep-based acceptance, not vague "write docs".
- **Type consistency:** `CustomCategory(key,name,hint)`, `env_var`, `all_category_keys`, `custom_category_keys`, `render_custom_prompt_section`, `custom_db_definitions`, `STANDARD_PROPS`, `register_digest_job`, `_build_openai_tool`, `_json_instruction` — names/signatures consistent across T1–T6.
