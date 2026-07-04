# 分類器類別更新（待讀待看 + 好笑的東西）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `article` 類別拓寬為「待讀待看」（文章/影片/書/電影，加一個 `type` 欄位），並新增「好笑的東西」（`funny`）類別與其 Notion DB。

**Architecture:** 沿用現有 Telegram → OpenAI 分類器 → Notion writer 管線。類別新增 = 改 `schemas.py`（型別+欄位表）、`classifier.py`（工具 enum）、`config.py`（DB 對應）、`notion_writer.py`（屬性建構）、`prompts/classify.md`（分類定義）五處。`funny` 的 Notion DB 用一次性腳本經 API 建立。

**Tech Stack:** Python 3、uv、pydantic-settings、openai SDK、notion-client 2.3.x、pytest。

## Global Constraints

- `notion-client` 釘選 `>=2.2,<2.4`（Notion-Version 2022-06-28）；`databases.create` / `pages.create(parent={"database_id": ...})` 只在此版本正確運作。
- **不改** 程式內部類別 key `article`（僅改對外顯示與 prompt 定義）。
- `article` DB 的 `Read?` checkbox、`Title`、`Publisher` 欄位必須保留（digest 依賴）。
- 中文文案需與本計畫逐字一致（Notion 屬性名、digest 字樣）。
- 每個 Task 結束跑 `uv run pytest` 全綠再 commit。

---

### Task 1: `article` 類別加入 `type` 欄位（待讀待看）

**Files:**
- Modify: `src/inbox_bot/schemas.py`
- Modify: `src/inbox_bot/notion_writer.py`
- Modify: `src/inbox_bot/prompts/classify.md`
- Modify: `src/inbox_bot/digest.py`
- Test: `tests/test_schemas.py`, `tests/test_notion_writer.py`, `tests/test_digest.py`

**Interfaces:**
- Consumes: 既有 `build_properties(category, fields, telegram_url, maps_link, now)`、`CATEGORY_FIELD_SCHEMAS`。
- Produces: `CATEGORY_FIELD_SCHEMAS["article"]` 含 `"type"`；`build_properties("article", …)` 產出含 `"Type"` select（預設 `"文章"`）。

- [ ] **Step 1: 寫失敗測試（schema 含 type）**

在 `tests/test_schemas.py` 末尾加入：

```python
def test_article_schema_includes_type():
    assert CATEGORY_FIELD_SCHEMAS["article"] == [
        "title", "url", "publisher", "summary", "type"
    ]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_schemas.py::test_article_schema_includes_type -v`
Expected: FAIL（現值缺 `"type"`）

- [ ] **Step 3: 更新 schema**

在 `src/inbox_bot/schemas.py` 把 `article` 那行改成：

```python
    "article":    ["title", "url", "publisher", "summary", "type"],
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_schemas.py::test_article_schema_includes_type -v`
Expected: PASS

- [ ] **Step 5: 寫失敗測試（build_properties 產出 Type）**

在 `tests/test_notion_writer.py` 的 `test_build_properties_article_smoke` 之後加入：

```python
def test_build_properties_article_has_type_select():
    now = datetime(2026, 7, 4, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="article",
        fields={"title": "某影片", "url": "https://youtu.be/x",
                "publisher": "某頻道", "summary": "s", "type": "影片"},
        telegram_url="https://t.me/c/1/2", maps_link=None, now=now,
    )
    assert props["Type"]["select"]["name"] == "影片"


def test_build_properties_article_type_defaults_to_文章():
    now = datetime(2026, 7, 4, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="article",
        fields={"title": "X", "url": "", "publisher": "", "summary": ""},
        telegram_url="https://t.me/c/1/2", maps_link=None, now=now,
    )
    assert props["Type"]["select"]["name"] == "文章"
```

- [ ] **Step 6: 跑測試確認失敗**

Run: `uv run pytest tests/test_notion_writer.py -k article -v`
Expected: 兩個新測試 FAIL（`KeyError: 'Type'`）

- [ ] **Step 7: 更新 notion_writer 的 article 分支**

在 `src/inbox_bot/notion_writer.py` 的 `if category == "article":` 區塊，於 `"Publisher"` 之後插入一行：

```python
    if category == "article":
        return {
            "Title": _title(g("title", "")),
            "URL": _url(g("url", "")),
            "Publisher": _text(g("publisher", "")),
            "Type": _select(g("type", "文章")),
            "Summary": _text(g("summary", "")),
            "Read?": _checkbox(False),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
```

- [ ] **Step 8: 跑測試確認通過**

Run: `uv run pytest tests/test_notion_writer.py -k article -v`
Expected: PASS（含既有 `test_build_properties_article_smoke`）

- [ ] **Step 9: 改寫分類 prompt 的 article 條目**

在 `src/inbox_bot/prompts/classify.md` 把 `article` 那一條整行替換為：

```markdown
- **article**（待讀待看）— 任何想之後讀或看的東西：文章、YouTube 影片、書、電影。Extract: title（標題）, url（截圖中可見的連結）, publisher（來源：文章→媒體、影片→頻道、書→作者、電影→導演）, summary（一行，用使用者語言）, type（其一：文章/影片/書/電影/其他）。
```

- [ ] **Step 10: 更新 digest 文案 + 測試**

在 `src/inbox_bot/digest.py` 的 `format_digest`，把待讀待看兩處字樣改掉：

```python
    if articles:
        lines.append(f"\n📖 待讀待看 ({len(articles)} 篇)")
```

以及 else 分支：

```python
    else:
        lines.append("\n📭 沒有待讀待看")
```

在 `tests/test_digest.py` 的 `test_format_digest_separates_overdue_and_this_week` 把該斷言改為：

```python
    assert "待讀待看 (2 篇)" in msg
```

（`test_format_digest_empty_lists` 斷言 `"沒有待讀"` 仍是 `"沒有待讀待看"` 的子字串，不必改。）

- [ ] **Step 11: 跑全套測試**

Run: `uv run pytest`
Expected: 全綠

- [ ] **Step 12: Commit**

```bash
git add src/inbox_bot/schemas.py src/inbox_bot/notion_writer.py src/inbox_bot/prompts/classify.md src/inbox_bot/digest.py tests/test_schemas.py tests/test_notion_writer.py tests/test_digest.py
git commit -m "feat: broaden article category to 待讀待看 with type field"
```

---

### Task 2: 新增 `funny`（好笑的東西）類別

**Files:**
- Modify: `src/inbox_bot/schemas.py`
- Modify: `src/inbox_bot/classifier.py`
- Modify: `src/inbox_bot/config.py`
- Modify: `src/inbox_bot/notion_writer.py`
- Modify: `src/inbox_bot/prompts/classify.md`
- Modify: `.env.example`
- Test: `tests/test_schemas.py`, `tests/test_classifier.py`, `tests/test_config.py`, `tests/test_notion_writer.py`
- Fixtures: 所有建立 `Settings()` 的測試 fixture 需加 `NOTION_DB_FUNNY`

**Interfaces:**
- Consumes: Task 1 之產物。
- Produces:
  - `Category` 含 `"funny"`；`CATEGORY_FIELD_SCHEMAS["funny"] == ["caption", "tags", "notes"]`
  - `Settings.notion_db_funny`（必填 env `NOTION_DB_FUNNY`）
  - `db_id_for_category("funny", s) == s.notion_db_funny`
  - `build_properties("funny", …)` → `{Name(title=caption), Tags(multi), Notes(text), Source(url), Date Added(date)}`（無 Status）
  - `CLASSIFY_TOOL` enum 含 `"funny"`

- [ ] **Step 1: 更新所有測試 fixture 加入 NOTION_DB_FUNNY**

在下列每個檔案的 env fixture dict 內，`"NOTION_DB_PHOTO"` 那行之後加入 `NOTION_DB_FUNNY`：
- `tests/test_config.py`（`fake_env`）：`"NOTION_DB_FUNNY": "db_funny",`
- `tests/test_notion_writer.py`（`settings`）：`"NOTION_DB_FUNNY": "db_funny",`
- `tests/test_classifier.py`（`settings`）：`"NOTION_DB_FUNNY": "fn",`
- `tests/test_digest.py`（`settings`）：`"NOTION_DB_FUNNY": "fn",`

再 grep 確認沒有漏網的 fixture：

Run: `grep -rl "NOTION_DB_PHOTO" tests/`
對每個列出的檔案確認都已加上 `NOTION_DB_FUNNY`（若 `tests/test_main.py` / `tests/test_bot.py` 也建 `Settings()`，同樣補上）。

- [ ] **Step 2: 寫失敗測試（schema + config + classifier enum）**

在 `tests/test_schemas.py` 把 `test_all_categories_have_field_schema` 的 `expected` 集合加入 `"funny"`，並新增：

```python
def test_funny_schema_has_expected_fields():
    assert CATEGORY_FIELD_SCHEMAS["funny"] == ["caption", "tags", "notes"]
```

在 `tests/test_config.py` 的 `test_db_id_for_category_dispatches_correctly` 參數化清單加一列：

```python
    ("funny", "db_funny"),
```

在 `tests/test_classifier.py` 把 `test_classify_tool_schema_includes_all_categories` 的集合加入 `"funny"`。

- [ ] **Step 3: 跑測試確認失敗**

Run: `uv run pytest tests/test_schemas.py tests/test_config.py tests/test_classifier.py -k "funny or all_categories or tool_schema or dispatches" -v`
Expected: 新增/修改的斷言 FAIL

- [ ] **Step 4: 更新 schemas.py**

`Category` 加入 `"funny"`：

```python
Category = Literal[
    "restaurant", "place", "todo", "article",
    "quote", "apparel", "skincare", "photo", "funny", "inbox",
]
```

`CATEGORY_FIELD_SCHEMAS` 在 `photo` 之後加入：

```python
    "funny":      ["caption", "tags", "notes"],
```

- [ ] **Step 5: 更新 config.py**

在 `Settings` 的 `notion_db_photo` 之後加入欄位：

```python
    notion_db_funny: str
```

在 `_CATEGORY_TO_ATTR` 的 `"photo"` 之後加入：

```python
    "funny": "notion_db_funny",
```

- [ ] **Step 6: 更新 classifier.py 的工具 enum**

在 `CLASSIFY_TOOL["input_schema"]["properties"]["category"]["enum"]` 清單加入 `"funny"`（放在 `"photo"` 之後、`"inbox"` 之前）：

```python
                "enum": ["restaurant", "place", "todo", "article",
                         "quote", "apparel", "skincare", "photo", "funny", "inbox"],
```

- [ ] **Step 7: 跑測試確認通過**

Run: `uv run pytest tests/test_schemas.py tests/test_config.py tests/test_classifier.py -v`
Expected: PASS

- [ ] **Step 8: 寫失敗測試（build_properties funny）**

在 `tests/test_notion_writer.py` 的 `test_build_properties_photo_has_no_status` 之後加入：

```python
def test_build_properties_funny():
    now = datetime(2026, 7, 4, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    props = build_properties(
        category="funny",
        fields={"caption": "貓咪踩鍵盤", "tags": ["動物", "迷因"], "notes": ""},
        telegram_url="https://t.me/c/1/2",
        maps_link=None,
        now=now,
    )
    assert props["Name"]["title"][0]["text"]["content"] == "貓咪踩鍵盤"
    assert {o["name"] for o in props["Tags"]["multi_select"]} == {"動物", "迷因"}
    assert props["Source"]["url"] == "https://t.me/c/1/2"
    assert "Status" not in props
```

- [ ] **Step 9: 跑測試確認失敗**

Run: `uv run pytest tests/test_notion_writer.py::test_build_properties_funny -v`
Expected: FAIL（funny 目前落入 inbox fallback，無 `Name`/`Tags`）

- [ ] **Step 10: 更新 notion_writer.py 加入 funny 分支**

在 `notion_writer.py` 的 `if category == "photo":` 區塊之後、`# inbox fallback` 之前加入：

```python
    if category == "funny":
        return {
            "Name": _title(g("caption", "")),
            "Tags": _multi(g("tags") or []),
            "Notes": _text(g("notes", "")),
            "Source": _url(telegram_url),
            "Date Added": _date(now),
        }
```

- [ ] **Step 11: 跑測試確認通過**

Run: `uv run pytest tests/test_notion_writer.py::test_build_properties_funny -v`
Expected: PASS

- [ ] **Step 12: 新增分類 prompt 的 funny 條目**

在 `src/inbox_bot/prompts/classify.md` 的 `photo` 條目之後、`inbox` 之前加入：

```markdown
- **funny**（好笑的東西）— 迷因、好笑的截圖或圖片，主要目的是「好笑/娛樂」。與 photo 區隔：photo 是「美感/靈感」，funny 是「好笑/迷因」；兩者皆可時依主要意圖判斷。Extract: caption（一句話描述這個梗/為何好笑，用使用者語言）, tags（主題陣列，可空）, notes（可選，一行）。
```

- [ ] **Step 13: 更新 .env.example**

在 `.env.example` 的 `NOTION_DB_PHOTO=` 之後加入：

```
NOTION_DB_FUNNY=
```

- [ ] **Step 14: 跑全套測試**

Run: `uv run pytest`
Expected: 全綠

- [ ] **Step 15: Commit**

```bash
git add src/inbox_bot/schemas.py src/inbox_bot/classifier.py src/inbox_bot/config.py src/inbox_bot/notion_writer.py src/inbox_bot/prompts/classify.md .env.example tests/
git commit -m "feat: add 好笑的東西 (funny) category"
```

---

### Task 3: 建立「好笑的東西」Notion DB 並上線

**Files:**
- Create: `scripts/create_funny_db.py`
- Modify: `.env`（本機，未進版控）

**Interfaces:**
- Consumes: `get_settings()`、`Settings.notion_db_photo`（用來找 parent page）。
- Produces: 印出新建 DB 的 id。

- [ ] **Step 1: 撰寫建 DB 腳本**

建立 `scripts/create_funny_db.py`：

```python
"""一次性：在 photo DB 的同一個 parent page 底下建立「好笑的東西」DB。

用法： uv run python scripts/create_funny_db.py
需在 notion-client >=2.2,<2.4（Notion-Version 2022-06-28）下執行。
"""
import asyncio
from notion_client import AsyncClient
from inbox_bot.config import get_settings


async def main() -> None:
    s = get_settings()
    client = AsyncClient(auth=s.notion_token)

    # 找一個現有 DB 的上層 page，把新 DB 建在同一層
    ref = await client.databases.retrieve(database_id=s.notion_db_photo)
    parent = ref["parent"]
    if parent.get("type") != "page_id":
        raise SystemExit(
            f"photo DB 的 parent 不是 page（是 {parent.get('type')}）。"
            "請手動提供一個 page_id 當 parent。"
        )
    page_id = parent["page_id"]

    db = await client.databases.create(
        parent={"type": "page_id", "page_id": page_id},
        title=[{"type": "text", "text": {"content": "好笑的東西"}}],
        properties={
            "Name": {"title": {}},
            "Tags": {"multi_select": {}},
            "Notes": {"rich_text": {}},
            "Source": {"url": {}},
            "Date Added": {"date": {}},
        },
    )
    print("好笑的東西 DB 已建立。")
    print("NOTION_DB_FUNNY=" + db["id"].replace("-", ""))


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 執行腳本建立 DB**

Run: `uv run python scripts/create_funny_db.py`
Expected: 印出一行 `NOTION_DB_FUNNY=<32碼id>`。
若報 `parent 不是 page`：改在 Notion 手動建 DB（或提供 page id）後把 id 記下。

- [ ] **Step 3: 把 id 填進 .env**

把上一步印出的 `NOTION_DB_FUNNY=<id>` 加進本機 `.env`（放在 `NOTION_DB_PHOTO=...` 之後）。

- [ ] **Step 4: 手動 Notion 步驟（待讀待看）**

在 Notion UI：
1. 把原本的 article DB 標題改名為「待讀待看」。
2. 在該 DB 新增一個名為 **`Type`** 的 **Select** 屬性（選項可留空，寫入時自動長出 文章/影片/書/電影/其他）。
3. 確認「好笑的東西」DB 已與 integration 分享（Notion 頁面右上 … → Connections → 加入你的 integration）。

- [ ] **Step 5: 本機冒煙驗證（不重載 daemon）**

確認 `.env` 已含 `NOTION_DB_FUNNY` 後，本機手動跑一次前景程序測試：

Run: `uv run python -c "from inbox_bot.config import get_settings; get_settings(); print('env ok')"`
Expected: 印出 `env ok`（代表新必填欄位 `NOTION_DB_FUNNY` 已備妥，不會啟動即崩潰）。

- [ ] **Step 6: 重載 daemon 讓新程式上線**

```bash
launchctl unload ~/Library/LaunchAgents/com.shao.telegram-inbox.plist
launchctl load   ~/Library/LaunchAgents/com.shao.telegram-inbox.plist
```

到 Telegram 頻道貼一張迷因截圖 + 一則 YouTube 連結，確認分別寫入「好笑的東西」與「待讀待看」（後者 Type 正確）。查 `logs/bot.log` 無錯誤。

- [ ] **Step 7: Commit 腳本**

```bash
git add scripts/create_funny_db.py
git commit -m "chore: add script to create 好笑的東西 Notion DB"
```

---

## Self-Review

**Spec coverage：**
- A1 拓寬 article + type 欄位 → Task 1（schema/notion_writer/prompt/digest）✓
- A1 手動改名 + Type select 屬性 → Task 3 Step 4 ✓
- A2 funny 類別（5 檔案 + prompt + env）→ Task 2 ✓
- A2 建 DB 腳本 → Task 3 ✓
- 測試更新 → Task 1、Task 2 內含 ✓
- 依賴限制 / Read? 保留 / 內部 key 不改 → Global Constraints ✓

**Placeholder scan：** 無 TBD；每個 code step 皆有完整程式碼。

**Type consistency：** `funny` 欄位 `caption/tags/notes` 於 schema、build_properties、prompt、測試一致；`Type` select 預設 `"文章"` 於 notion_writer 與測試一致；`notion_db_funny` 於 config、fixtures、db 對應一致。
