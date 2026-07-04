# 專案 B：複製給朋友（Gemini + macOS）設計

日期：2026-07-04
狀態：已核可（設計階段）

## 目標

讓同一套 telegram-inbox-bot 程式碼能被朋友在他自己的 macOS 上跑起來，串他自己的
Telegram bot、Notion workspace，分類器改用 **Gemini**（免費額度）。核心原則：
**同一份程式碼，用設定切換 provider**，不做分叉副本。

朋友為非技術背景，但安裝時使用者（本專案擁有者）會在旁協助（情境 3b）。指南需極詳
細、每步附「會看到什麼畫面 / 貼哪個指令」，但可假設有人協助處理卡關。

## 範圍

1. 程式：分類器 provider 抽象化（openai / gemini），Gemini 走 OpenAI 相容端點。
2. 腳本：`provision_notion.py`（一鍵建全部 10 個 DB）、`get_channel_id.py`（抓頻道 id）。
3. 文件：`docs/friend-setup-macos.md`（從零到上線的極詳細 macOS 指南）。

## 非目標

- 不改動 provider=openai 的既有行為（使用者現有 bot 必須完全不受影響）。
- 不做 CI/雲端部署；朋友一樣是本機 launchd。
- 不自動化「帳號類」步驟（BotFather、Notion integration、Gemini key）——這些指南帶著做。

---

## 1. 程式：provider 抽象化

### config.py（Settings）
新增/調整欄位：

| 欄位 | 型別/預設 | 說明 |
|------|-----------|------|
| `classifier_provider` | `str = "openai"` | `"openai"` 或 `"gemini"` |
| `openai_api_key` | `str = ""`（改為可選） | provider=openai 時必填 |
| `gemini_api_key` | `str = ""` | provider=gemini 時必填 |
| `gemini_base_url` | `str = "https://generativelanguage.googleapis.com/v1beta/openai/"` | 可覆寫 |

驗證（pydantic `model_validator(mode="after")`）：
- provider=openai 且 `openai_api_key` 空 → 拋錯。
- provider=gemini 且 `gemini_api_key` 空 → 拋錯。
- provider 非上述兩者 → 拋錯。

`classifier_model` 沿用（預設 `gpt-4.1-mini`）；朋友的 `.env` 設 `CLASSIFIER_MODEL=gemini-2.5-flash`。

### classifier.py
抽出 `_make_client(settings) -> AsyncOpenAI`：
- provider=openai → `AsyncOpenAI(api_key=settings.openai_api_key)`
- provider=gemini → `AsyncOpenAI(api_key=settings.gemini_api_key, base_url=settings.gemini_base_url)`

`classify(..., client=None)`：`client is None` 時改呼叫 `_make_client(settings)`。其餘（system
prompt、`_build_content`、tools、forced tool_choice、retry、低信心 → inbox）**完全不變、兩
provider 共用**。

### 技術風險與退路
Gemini 相容端點對「強制指定 function 的 tool_choice」支援無法在無 key 情況下預先驗證。
- 先沿用同一條 function-calling 路徑。
- 安裝時跑 smoke test 當場驗（見指南）。
- 若 Gemini 分支不吃強制 tool_choice：退路是**僅 gemini 分支**改用
  `response_format={"type": "json_schema", ...}`（schema 對齊 `CLASSIFY_TOOL["input_schema"]`），
  openai 分支維持 function calling 不動。此退路屬「若驗證失敗才做」，不在首次實作範圍。

### 測試
- `test_config.py`：provider 預設 openai；gemini 需 gemini_api_key（缺→ValidationError）；
  openai 需 openai_api_key（缺→ValidationError）；未知 provider→ValidationError。
- `test_classifier.py`：patch `AsyncOpenAI`，斷言 provider=gemini 時以 `base_url` +
  `gemini_api_key` 建 client；provider=openai 時以 `api_key`（無 base_url）建 client。
  既有測試（傳入 mock client）不受影響。

---

## 2. 輔助腳本

### scripts/provision_notion.py
用途：在指定的 Notion 母頁面下一鍵建立全部 DB，印出 `.env` 用的 id。

- 輸入：母頁面 id（`sys.argv[1]`，或環境變數 `NOTION_PARENT_PAGE_ID`）。用 `NOTION_TOKEN`
  （由 `get_settings()` 讀取；為避免必填 DB id 造成 chicken-egg，腳本改用
  `Settings(_env_file=...)` 或直接讀 `NOTION_TOKEN` 環境變數建立 client，**不依賴任何
  `NOTION_DB_*`**）。
- 對每個類別（restaurant, place, todo, article, quote, apparel, skincare, photo, funny,
  inbox）呼叫 `databases.create`，properties 對齊 `notion_writer.build_properties` 所用欄位：

| DB（建議標題） | 屬性 |
|------|------|
| 餐廳 restaurant | Name(title), City/Area(select), Cuisine(multi_select), Maps Link(url), Notes(rich_text), Source(url), Date Added(date) |
| 地點 place | Name(title), City/Country(select), Type(select), Maps Link(url), Notes, Source, Date Added |
| 待辦 todo | Task(title), Deadline(date), Notes, Source, Date Added（**Status 手動加**） |
| 待讀待看 article | Title(title), URL(url), Publisher(rich_text), Type(select), Summary(rich_text), Read?(checkbox), Source, Date Added |
| 金句 quote | Quote(title), Author(rich_text), Tags(multi_select), Source, Date Added |
| 服飾 apparel | Item(title), Brand(rich_text), Type(select), Price(number), URL(url), Notes, Source, Date Added |
| 保養 skincare | Product(title), Brand(rich_text), Category(select), Price(number), URL(url), Notes, Source, Date Added |
| 照片 photo | Name(title), Notes, Source, Date Added |
| 好笑的東西 funny | Name(title), Tags(multi_select), Notes, Source, Date Added |
| Inbox inbox | Raw Text(title), Reason(rich_text), Source, Date Added |

- 輸出：逐行印出 `NOTION_DB_RESTAURANT=<id>` … 讓使用者貼進 `.env`。
- 限制：todo 的 `Status`（status 型）API 無法建立 → 指南標明手動加（Todo/Done）。
- 依賴限制：需在 `notion-client >=2.2,<2.4`（Notion-Version 2022-06-28）下執行。

### scripts/get_channel_id.py
用途：協助抓私人頻道的 chat id（非技術者痛點）。
- 用 `TELEGRAM_BOT_TOKEN`（讀環境變數，不依賴 DB id）建立 `telegram.Bot`，`get_updates`
  長輪詢；朋友在頻道貼任一則訊息後，腳本印出 `channel_post.chat.id` 與標題後結束。
- 印出後提示貼進 `.env` 的 `TELEGRAM_CHANNEL_ID`。

（兩腳本皆為一次性工具，不寫單元測試；以實際執行驗證。）

---

## 3. 指南：docs/friend-setup-macos.md

極詳細、依序、每步含「指令」與「你會看到什麼 / 下一步」。章節：

0. 這是什麼、需要準備什麼（一支能收訊息的 Mac、Google 帳號、Notion 帳號、約 40 分鐘）。
1. 安裝工具：Homebrew → uv → git（附驗證指令）。
2. 取得程式碼（clone 或複製資料夾）。
3. 用 @BotFather 建 Telegram bot、拿 token。
4. 建私人頻道、把 bot 設為管理員。
5. 用 `scripts/get_channel_id.py` 抓 channel id。
6. 建 Notion integration（notion.so/my-integrations）拿 token；建一個母頁面、分享給
   integration、複製母頁面 id。
7. 跑 `scripts/provision_notion.py <母頁面id>`，把印出的 `NOTION_DB_*` 貼進 `.env`。
8. 手動在 todo DB 加 `Status`（status 型，選項 Todo/Done）。
9. 到 aistudio.google.com/apikey 拿 Gemini API key。
10. 依 `.env.example` 填 `.env`：`CLASSIFIER_PROVIDER=gemini`、`GEMINI_API_KEY=...`、
    `CLASSIFIER_MODEL=gemini-2.5-flash`、Telegram/Notion token 與 DB id。
11. `uv sync` → smoke test：前景 `uv run python -m inbox_bot.main`，到頻道貼一張截圖，
    確認 bot 回覆且 Notion 有新增。
12. 設 launchd 開機自啟：複製並改寫 plist 的 label/路徑；用 bootout+bootstrap（含 I/O
    error 5 需重試的雷）。
13. 疑難排解：常見錯誤（token 錯、頻道權限、Gemini key、notion 分享沒做、Status 沒加、
    tool_choice 相容性 → 若分類一直失敗回報以啟用 response_format 退路）。

`.env.example` 需補上 `CLASSIFIER_PROVIDER=`、`GEMINI_API_KEY=`、`GEMINI_BASE_URL=`（附註）。

---

## 風險 / 待驗證
- **Gemini 強制 tool_choice 相容性**：安裝時 smoke test 驗；失敗則啟用 response_format 退路。
- **provision_notion 的母頁面**：必須先與 integration 分享，否則 `databases.create` 會失敗；
  指南在建母頁面後即要求分享。
- **notion-client 版本**：朋友端 `uv sync` 會依 pyproject 的 pin（>=2.2,<2.4），維持 classic API。
- **Telegram channel id**：頻道須為 `-100...` 形式；`get_channel_id.py` 直接印實際值避免手算。
