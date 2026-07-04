# 複製給朋友（Gemini provider + macOS 指南）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓同一套程式碼能用設定切到 Gemini（走 OpenAI 相容端點）；提供一鍵建 Notion DB 與抓 channel id 的腳本；寫一份極詳細的 macOS 安裝指南給非技術朋友。

**Architecture:** 分類器抽出 `_make_client(settings)` 依 `classifier_provider` 回傳對應的 `AsyncOpenAI`（gemini 只換 base_url/key/model），其餘分類邏輯共用。兩個一次性腳本 + 一份 Markdown 指南。

**Tech Stack:** Python、uv、pydantic-settings（含 python-dotenv）、openai SDK、python-telegram-bot、notion-client 2.3.x。

## Global Constraints

- **provider=openai 的既有行為零改動**：`classifier_provider` 預設 `"openai"`，使用者現有 `.env` 照舊可跑。
- `openai_api_key` 改為可選（預設 `""`）；由 validator 依 provider 強制對應的 key 存在。
- 兩個腳本**不得依賴任何 `NOTION_DB_*`**（避免 chicken-egg）：直接讀 `NOTION_TOKEN` / `TELEGRAM_BOT_TOKEN` 環境變數（`load_dotenv()`）。
- Gemini 模型為 `gemini-2.5-flash`；base_url 預設 `https://generativelanguage.googleapis.com/v1beta/openai/`。
- `notion-client` 釘選 `>=2.2,<2.4`（Notion-Version 2022-06-28）；`databases.create` 只在此版本正確建立欄位。
- todo 的 `Status`（status 型）API 無法建立 → 腳本不建，指南標明手動加（Todo/Done）。
- 指南假設「使用者會在旁協助」（情境 3b），但仍需極詳細、每步附指令與「會看到什麼」。
- 每個 Task 結束跑 `uv run pytest` 全綠再 commit（腳本/文件 Task 無單元測試者，改以 `py_compile` 或全套回歸驗證）。

---

### Task 1: 分類器 provider 抽象化（config + classifier）

**Files:**
- Modify: `src/inbox_bot/config.py`
- Modify: `src/inbox_bot/classifier.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`, `tests/test_classifier.py`

**Interfaces:**
- Produces: `Settings.classifier_provider`（預設 `"openai"`）、`Settings.gemini_api_key`、`Settings.gemini_base_url`；`Settings.openai_api_key` 變可選。provider/key 不匹配時建構即拋 `ValidationError`。
- Produces: `inbox_bot.classifier._make_client(settings) -> AsyncOpenAI`；`classify()` 在 `client is None` 時改用它。

- [ ] **Step 1: 寫失敗測試（config）**

在 `tests/test_config.py` 頂部加入 `from pydantic import ValidationError`（若尚無），並於檔尾加入：

```python
def test_classifier_provider_defaults_to_openai(fake_env):
    assert Settings().classifier_provider == "openai"


def test_gemini_provider_requires_gemini_key(fake_env, monkeypatch):
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_openai_provider_requires_openai_key(fake_env, monkeypatch):
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_unknown_provider_rejected(fake_env, monkeypatch):
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "claude")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_gemini_provider_valid_without_openai_key(fake_env, monkeypatch):
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "gm-x")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s = Settings(_env_file=None)
    assert s.classifier_provider == "gemini"
    assert s.gemini_api_key == "gm-x"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_config.py -k "provider" -v`
Expected: FAIL（欄位/驗證尚未存在）

- [ ] **Step 3: 更新 config.py**

`import` 區加入 `from pydantic import model_validator`。把 `openai_api_key: str` 改為 `openai_api_key: str = ""`。在 DB id 群組之後、`classifier_model` 之前插入 provider 設定：

```python
    classifier_provider: str = "openai"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
```

在 `Settings` class 內（欄位定義之後）加入 validator：

```python
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS（含既有測試）

- [ ] **Step 5: 寫失敗測試（classifier `_make_client`）**

在 `tests/test_classifier.py` 檔尾加入：

```python
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
```

- [ ] **Step 6: 跑測試確認失敗**

Run: `uv run pytest tests/test_classifier.py -k make_client -v`
Expected: FAIL（`_make_client` 不存在）

- [ ] **Step 7: 更新 classifier.py**

在 `_load_system_prompt` 之前（或 `classify` 之前）加入：

```python
def _make_client(settings: Settings) -> AsyncOpenAI:
    if settings.classifier_provider == "gemini":
        return AsyncOpenAI(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
        )
    return AsyncOpenAI(api_key=settings.openai_api_key)
```

把 `classify` 內：

```python
    if client is None:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
```

改為：

```python
    if client is None:
        client = _make_client(settings)
```

- [ ] **Step 8: 跑測試確認通過**

Run: `uv run pytest tests/test_classifier.py -v`
Expected: PASS

- [ ] **Step 9: 更新 .env.example**

在 `OPENAI_API_KEY=...` 行後、`CLASSIFIER_MODEL=` 相關處，加入：

```
# 分類器 provider：openai 或 gemini
CLASSIFIER_PROVIDER=openai
# provider=gemini 時填（Google AI Studio 取得）
GEMINI_API_KEY=
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```

並把既有 `CLASSIFIER_MODEL=gpt-4.1-mini` 那行後加一行註解：`# gemini 時改為 gemini-2.5-flash`。

- [ ] **Step 10: 跑全套測試**

Run: `uv run pytest`
Expected: 全綠

- [ ] **Step 11: Commit**

```bash
git add src/inbox_bot/config.py src/inbox_bot/classifier.py .env.example tests/test_config.py tests/test_classifier.py
git commit -m "feat: pluggable classifier provider (openai/gemini via OpenAI-compat)"
```

---

### Task 2: 輔助腳本（provision_notion.py + get_channel_id.py）

**Files:**
- Create: `scripts/provision_notion.py`
- Create: `scripts/get_channel_id.py`

**Interfaces:**
- `provision_notion.py`：`argv[1]` = 母頁面 id；讀 `NOTION_TOKEN`；建 10 個 DB；印出 `NOTION_DB_*=<id>`。
- `get_channel_id.py`：讀 `TELEGRAM_BOT_TOKEN`；長輪詢；收到頻道訊息後印 `TELEGRAM_CHANNEL_ID=<id>`。

- [ ] **Step 1: 建 `scripts/provision_notion.py`**

```python
"""在指定 Notion 母頁面下建立朋友端全部 DB，印出 .env 用的 id。

用法： uv run python scripts/provision_notion.py <PARENT_PAGE_ID>
前提：.env 已有 NOTION_TOKEN；母頁面已分享給你的 integration。
需 notion-client >=2.2,<2.4（Notion-Version 2022-06-28）。
"""
import asyncio
import os
import sys
from dotenv import load_dotenv
from notion_client import AsyncClient

# env-var 名稱 -> (DB 顯示標題, properties)
DBS: dict[str, tuple[str, dict]] = {
    "NOTION_DB_RESTAURANT": ("餐廳", {
        "Name": {"title": {}}, "City/Area": {"select": {}}, "Cuisine": {"multi_select": {}},
        "Maps Link": {"url": {}}, "Notes": {"rich_text": {}}, "Source": {"url": {}},
        "Date Added": {"date": {}},
    }),
    "NOTION_DB_PLACE": ("地點", {
        "Name": {"title": {}}, "City/Country": {"select": {}}, "Type": {"select": {}},
        "Maps Link": {"url": {}}, "Notes": {"rich_text": {}}, "Source": {"url": {}},
        "Date Added": {"date": {}},
    }),
    "NOTION_DB_TODO": ("待辦", {
        "Task": {"title": {}}, "Deadline": {"date": {}}, "Notes": {"rich_text": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
        # 注意：Status（status 型）API 無法建立，請到 Notion 手動加（選項 Todo/Done）
    }),
    "NOTION_DB_ARTICLE": ("待讀待看", {
        "Title": {"title": {}}, "URL": {"url": {}}, "Publisher": {"rich_text": {}},
        "Type": {"select": {}}, "Summary": {"rich_text": {}}, "Read?": {"checkbox": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
    }),
    "NOTION_DB_QUOTE": ("金句", {
        "Quote": {"title": {}}, "Author": {"rich_text": {}}, "Tags": {"multi_select": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
    }),
    "NOTION_DB_APPAREL": ("服飾", {
        "Item": {"title": {}}, "Brand": {"rich_text": {}}, "Type": {"select": {}},
        "Price": {"number": {}}, "URL": {"url": {}}, "Notes": {"rich_text": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
    }),
    "NOTION_DB_SKINCARE": ("保養", {
        "Product": {"title": {}}, "Brand": {"rich_text": {}}, "Category": {"select": {}},
        "Price": {"number": {}}, "URL": {"url": {}}, "Notes": {"rich_text": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
    }),
    "NOTION_DB_PHOTO": ("照片", {
        "Name": {"title": {}}, "Notes": {"rich_text": {}}, "Source": {"url": {}},
        "Date Added": {"date": {}},
    }),
    "NOTION_DB_FUNNY": ("好笑的東西", {
        "Name": {"title": {}}, "Tags": {"multi_select": {}}, "Notes": {"rich_text": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
    }),
    "NOTION_DB_INBOX": ("Inbox", {
        "Raw Text": {"title": {}}, "Reason": {"rich_text": {}}, "Source": {"url": {}},
        "Date Added": {"date": {}},
    }),
}


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("用法： uv run python scripts/provision_notion.py <PARENT_PAGE_ID>")
    parent_page_id = sys.argv[1]
    load_dotenv()
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise SystemExit("找不到 NOTION_TOKEN（請先在 .env 填好）")
    client = AsyncClient(auth=token)

    lines: list[str] = []
    for env_name, (title, props) in DBS.items():
        db = await client.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": title}}],
            properties=props,
        )
        print(f"建立完成：{title}")
        lines.append(f"{env_name}={db['id'].replace('-', '')}")

    print("\n# ↓↓↓ 把下面全部貼進 .env ↓↓↓")
    print("\n".join(lines))
    print("\n提醒：到 Notion 的「待辦」DB 手動新增一個 Status 欄位（status 型，選項 Todo / Done）。")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 建 `scripts/get_channel_id.py`**

```python
"""抓私人頻道的 chat id。

用法：先把 bot 加進頻道並設為管理員，執行本腳本後到頻道貼任一則訊息。
 uv run python scripts/get_channel_id.py
前提：.env 已有 TELEGRAM_BOT_TOKEN。
"""
import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot


async def main() -> None:
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("找不到 TELEGRAM_BOT_TOKEN（請先在 .env 填好）")

    bot = Bot(token=token)
    print("等待中… 請到你的頻道貼任一則訊息（Ctrl+C 可結束）")
    offset = None
    async with bot:
        while True:
            updates = await bot.get_updates(offset=offset, timeout=30)
            for u in updates:
                offset = u.update_id + 1
                post = u.channel_post or u.message
                if post is not None:
                    chat = post.chat
                    print(f"\n找到了！頻道標題：{chat.title!r}")
                    print(f"TELEGRAM_CHANNEL_ID={chat.id}")
                    print("把上面這行貼進 .env。")
                    return


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: 語法檢查兩個腳本**

Run: `uv run python -m py_compile scripts/provision_notion.py scripts/get_channel_id.py && echo OK`
Expected: `OK`（無語法錯）

- [ ] **Step 4: 匯入相依確認（不需真 token）**

Run: `uv run python -c "import ast; ast.parse(open('scripts/provision_notion.py').read()); ast.parse(open('scripts/get_channel_id.py').read()); print('parsed')"`
Expected: `parsed`

（真正建 DB / 抓 id 需真 token，於朋友安裝時執行，屬指南範圍。）

- [ ] **Step 5: Commit**

```bash
git add scripts/provision_notion.py scripts/get_channel_id.py
git commit -m "chore: add provision_notion + get_channel_id helper scripts for replication"
```

---

### Task 3: macOS 安裝指南 `docs/friend-setup-macos.md`

**Files:**
- Create: `docs/friend-setup-macos.md`

**Interfaces:** 無程式介面；輸出一份 Markdown 文件。

**寫作要求（給實作者）：**
- 語氣：對非技術讀者、繁體中文、口語但精確。每個技術步驟都要有：要貼的**指令**（放 code block）、以及**「你會看到什麼 / 成功長怎樣」**一句。
- 每個名詞第一次出現時用一句白話解釋（例：「終端機 Terminal 就是打指令的黑框框」）。
- 假設使用者會在旁協助卡關，但步驟本身要能照抄。
- 每個「帳號類」步驟給出**確切網址**與**點哪個按鈕**。
- 適當使用 checklist、⚠️ 提醒、以及「如果出現 X 錯誤 → 這樣解」小方塊。

- [ ] **Step 1: 撰寫指南，需包含下列章節與確切內容**

依序寫出這些章節（標題可潤飾）：

1. **這是什麼 / 要準備什麼**：一支長期開著能收訊息的 Mac、一個 Google 帳號、一個 Notion 帳號、約 40 分鐘；成品＝在 Telegram 頻道貼截圖會自動分類進 Notion。
2. **安裝工具**：
   - Homebrew：`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`，裝完照畫面提示把 brew 加進 PATH；驗證 `brew --version`。
   - uv：`brew install uv`；驗證 `uv --version`。
   - git：`brew install git`；驗證 `git --version`。
3. **取得程式碼**：`git clone <REPO_URL> ~/telegram-inbox-bot`（或用隨身碟複製整個資料夾到家目錄）；`cd ~/telegram-inbox-bot`。標明實際 REPO_URL 由使用者提供／或用複製資料夾方式。
4. **建 Telegram bot**：在 Telegram 找 `@BotFather` → `/newbot` → 取名 → 拿到一串 token（像 `8xxxx:AA...`）。⚠️ token 不要外流。
5. **建頻道 + 設 bot 管理員**：新建一個「私人頻道」→ 頻道設定 → Administrators → Add Admin → 搜尋你的 bot → 加入（給它貼文權限）。
6. **抓 channel id**：先把 token 填進 `.env`（見下一步的 `.env` 建立方式）；執行 `uv run python scripts/get_channel_id.py`，然後到頻道貼一句「test」；腳本會印 `TELEGRAM_CHANNEL_ID=-100...`，貼進 `.env`。
7. **建 `.env`**：`cp .env.example .env`，用文字編輯器打開；說明每個欄位。給出朋友版本的樣板（provider=gemini）：
   ```
   TELEGRAM_BOT_TOKEN=剛剛 BotFather 給的
   TELEGRAM_CHANNEL_ID=（下一步用腳本抓）
   NOTION_TOKEN=（第 8 步取得）
   CLASSIFIER_PROVIDER=gemini
   GEMINI_API_KEY=（第 10 步取得）
   CLASSIFIER_MODEL=gemini-2.5-flash
   NOTION_DB_...=（第 9 步腳本產生）
   ```
   （OPENAI_API_KEY 朋友端留空即可。）
8. **建 Notion integration + 母頁面**：到 `https://www.notion.so/my-integrations` → New integration → 拿 `Internal Integration Token`（`ntn_...`）填進 `.env` 的 `NOTION_TOKEN`；在 Notion 建一個新頁面（例如「我的 Inbox」）當容器 → 頁面右上 `...` → Connections → 加入剛建的 integration；複製該頁面網址末段的 32 碼當作母頁面 id。
9. **一鍵建 DB**：`uv run python scripts/provision_notion.py <母頁面id>`；把印出的所有 `NOTION_DB_*=...` 貼進 `.env`。
10. **手動加 todo 的 Status**：到 Notion 的「待辦」DB → 新增 property → 名稱 `Status`、型別 **Status** → 確保有選項 `Todo` 與 `Done`。⚠️ 沒加的話每週摘要會失敗。
11. **拿 Gemini API key**：到 `https://aistudio.google.com/apikey` → Create API key → 複製填進 `.env` 的 `GEMINI_API_KEY`。
12. **安裝相依 + 冒煙測試**：`uv sync`；前景啟動 `uv run python -m inbox_bot.main`；到頻道貼一張截圖 → 應看到 bot 在該則下回覆 emoji + Notion 連結，且 Notion 對應 DB 有新增。成功後 `Ctrl+C` 停掉。
    - ⚠️ **Gemini 相容性檢查**：若分類一直失敗（bot 回「分類失敗」），回報給使用者 —— 需啟用 `response_format` 退路（見 spec 風險段）。
13. **設定開機自動啟動（launchd）**：複製 `launchd/com.shao.telegram-inbox.plist` 改成朋友的 label 與路徑（把 `com.shao.` 換成他的、把程式路徑改成 `~/telegram-inbox-bot`、`uv` 路徑用 `which uv` 查）；放到 `~/Library/LaunchAgents/`；用 `launchctl bootstrap "gui/$(id -u)" <plist路徑>` 載入。
    - ⚠️ 已知雷：`launchctl load/unload` 會 `Input/output error`，改用 `bootout` + `bootstrap`；`bootstrap` 偶爾也會 I/O error，**重試 2–3 次**即可。附一段 3 次重試的指令。
14. **疑難排解**（小方塊逐條）：token 貼錯、頻道沒把 bot 設管理員、Notion 母頁面沒分享給 integration、Status 沒加、Gemini key 無效或額度、`uv` 不在 PATH、分類一直失敗（tool_choice 相容 → 啟用 response_format 退路）。

- [ ] **Step 2: 自我檢查文件**

通讀一次：每個技術步驟都有指令 code block 與「會看到什麼」；沒有殘留 `<REPO_URL>` 以外的 placeholder（REPO_URL 若未知，明確標注「向 Shao 索取」）；章節順序可照抄執行（token 先於抓 channel id、母頁面分享先於 provision、Gemini key 先於冒煙測試）。

- [ ] **Step 3: Commit**

```bash
git add docs/friend-setup-macos.md
git commit -m "docs: detailed macOS setup guide for friend replication"
```

---

## Self-Review

**Spec coverage：**
- provider 抽象化（config 欄位+validator、classifier `_make_client`、.env.example）→ Task 1 ✓
- provision_notion.py（10 DB、不依賴 DB id、todo 無 Status）→ Task 2 ✓
- get_channel_id.py → Task 2 ✓
- friend-setup-macos.md（13+ 章節、極詳細、launchd 雷、Gemini 退路）→ Task 3 ✓
- Global Constraints（openai 零改動、pin、gemini-2.5-flash）→ Global Constraints + Task 1/2 ✓

**Placeholder scan：** 除文件內明示的 `<REPO_URL>`（標注向 Shao 索取）與 `<母頁面id>`/`<PARENT_PAGE_ID>`（執行期參數）外，無 TBD。

**Type consistency：** `_make_client(settings) -> AsyncOpenAI` 於 classifier 定義與 classify 呼叫一致；`classifier_provider` 值域 `openai`/`gemini` 於 config、validator、_make_client、測試一致；provision 的欄位與 `build_properties`（Task A）一致。
