# 專案 A：分類器類別更新（待讀待看 + 好笑的東西）

日期：2026-07-04
狀態：已核可（設計階段）

## 目標

在現有的 Telegram → 分類器 → Notion inbox bot 上做兩項調整：

1. 把現有的 `article` 類別**拓寬**為「待讀待看」：除了文章，也涵蓋 YouTube 影片、書、電影。
2. **新增**一個類別「好笑的東西」（迷因 / 好笑截圖）。

不在本次範圍：provider 抽象化、複製給朋友（另立專案 B）。

## 非目標 / 明確不做

- 不改程式內部的類別 key `article`（只改對外顯示與 prompt 定義），以免牽動過多檔案。
- 不改動 digest 的查詢邏輯，只調整顯示字樣。
- 不動 provider（仍為 OpenAI `gpt-4.1-mini`）。

---

## A1. `article` 拓寬為「待讀待看」

### 行為
- 一則訊息若是「想之後讀或看的東西」——文章、YouTube 影片、書、電影——都歸到 `article`。
- 分類器需額外萃取一個 `type` 欄位，值為：`文章 / 影片 / 書 / 電影 / 其他`。

### 程式改動
- `schemas.py`：`CATEGORY_FIELD_SCHEMAS["article"]` 加入 `"type"`（變成 `["title", "url", "publisher", "summary", "type"]`）。
- `notion_writer.py`：`build_properties` 的 `article` 分支加入 `"Type": _select(g("type", "文章"))`。
- `prompts/classify.md`：改寫 `article` 條目定義，涵蓋四種媒介，並要求萃取 `type`；`publisher` 語意擴充（影片→頻道、書→作者、電影→導演）。
- `digest.py`：`format_digest` 中「📖 待讀 / 📭 沒有待讀文章」字樣改為「📖 待讀待看 / 📭 沒有待讀待看」。查詢邏輯（`Read?` checkbox、`Title`、`Publisher`）不變。

### 手動步驟（Notion UI，使用者操作）
- 把該 DB 標題改名為「待讀待看」（純顯示，程式以 db id 認）。
- 在該 DB 新增一個 **`Type`（select 類型）** 屬性。select 屬性本身必須先存在；選項值（文章/影片/…）會在寫入時自動建立。

### 相容性
- `Read?`、`Title`、`Publisher`、`URL`、`Summary` 欄位保留，故 digest 不受影響。
- 舊資料沒有 `Type` 值不影響任何查詢。

---

## A2. 新增類別「好笑的東西」（`funny`）

### 欄位
`caption`（標題/梗的一句話）、`tags`（主題多選，可空）、`notes`（可選一行）。

### Notion DB 結構
| 屬性 | 類型 | 來源 |
|------|------|------|
| Name | title | `caption` |
| Tags | multi_select | `tags` |
| Notes | rich_text | `notes` |
| Source | url | Telegram 訊息連結 |
| Date Added | date | 寫入時間 |

無 status 屬性 → 不需任何手動設定。

### 程式改動
- `schemas.py`：`Category` 加 `"funny"`；`CATEGORY_FIELD_SCHEMAS["funny"] = ["caption", "tags", "notes"]`。
- `classifier.py`：`CLASSIFY_TOOL` 的 `category.enum` 加 `"funny"`。
- `config.py`：新增設定欄位 `notion_db_funny`；`_CATEGORY_TO_ATTR` 加 `"funny": "notion_db_funny"`。
- `notion_writer.py`：`build_properties` 新增 `funny` 分支（依上表）。
- `.env` 與 `.env.example`：新增 `NOTION_DB_FUNNY=`。
- `prompts/classify.md`：新增 `funny` 條目，並與 `photo` 做語意區隔——`photo` 是「美感/靈感」，`funny` 是「好笑/迷因」；兩者皆可時依主要意圖判斷。

### 建立 DB 的腳本
`scripts/create_funny_db.py`：
1. 讀取 `.env`（沿用 `get_settings`）。
2. 用 `notion_client`（釘選 2.3.x，classic API）`databases.retrieve` 抓一個現有 DB（例如 `notion_db_photo`）的 `parent`，取得其上層 `page_id`。
3. 在同一個 page 底下 `databases.create` 建「好笑的東西」DB（含上表屬性，Name 為 title）。
4. 印出新 DB 的 id，提示使用者貼進 `.env` 的 `NOTION_DB_FUNNY`。

> 依賴限制：必須在 `notion-client >=2.2,<2.4`（Notion-Version 2022-06-28）下執行，`databases.create(properties=...)` 才會正確建立欄位（見 README 依賴限制章節）。

---

## 測試

沿用現有 pytest（mock）風格，補上：
- `test_schemas.py`：`funny` 在 `Category` 與 `CATEGORY_FIELD_SCHEMAS`；`article` 含 `type`。
- `test_classifier.py`：`CLASSIFY_TOOL` enum 含 `funny`。
- `test_config.py`：`db_id_for_category("funny", …)` 回傳 `notion_db_funny`。
- `test_notion_writer.py`：`build_properties("funny", …)` 產出正確屬性；`article` 分支含 `Type`。
- （可選）`test_digest.py`：字樣更新後仍通過。

`scripts/create_funny_db.py` 為一次性工具，不寫單元測試；以實際執行驗證。

## 風險 / 待驗證
- Notion 該 DB 需先手動加 `Type` select 屬性，否則 `article` 寫入會失敗。實作時在 README/指南標明此手動步驟。
- `create_funny_db.py` 依賴「現有 DB 的 parent 是一個 page」；若 parent 是 workspace 而非 page 需退回請使用者提供 page id。
