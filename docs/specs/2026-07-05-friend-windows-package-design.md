# 專案 C：複製給朋友（Windows 11 + 自訂分類 + 無提醒）設計

日期：2026-07-05
狀態：設計中（待核可）

## 目標

再給一位朋友同一套 telegram-inbox-bot，但這次是 **Windows 11**，且對象是**完全沒學過
電腦的中年人**（安裝時本專案擁有者 Shao 會在旁協助，但指南要盡量讓對方能獨立照做）。
相對於既有的 macOS + Gemini 版本，本次三項差異：

1. **平台改 Windows 11**：工具、終端機、編輯器、路徑、開機自動啟動全部換成 Windows 做法。
2. **完全移除提醒功能**：週日 07:30 digest 不排程、不出現在指南任何一處。
3. **新增「自己增減子資料庫」能力**：朋友能自行新增/移除他要的分類（例如「食譜」），
   全程只改一個設定檔 + `.env`，不碰 Python。

核心原則同前：**同一份程式碼，用設定切換**，不做分叉副本；**Shao 自己的 bot 行為零受影響**。

## 範圍

1. 程式：自訂分類設定檔驅動（新增 `custom_categories.toml` + `categories.py` 註冊模組）；
   `DIGEST_ENABLED` 開關。
2. 腳本：`provision_notion.py` 加「只建新自訂表」模式。
3. 啟動器：`windows\run_bot.bat`（含當掉自動重跑迴圈）。
4. 文件：`docs/friend-setup-windows.md`（繁中、極詳細、Windows 版、含自訂分類一節、無提醒）。
5. 交付：`docs/friend-setup-windows.html`（精美、可列印/存 PDF 的自包含 HTML）。
6. `.env.example` 加 `DIGEST_ENABLED`。

## 非目標

- 不改動內建 10 個分類的行為與 schema（Shao 現有 bot 必須完全不受影響）。
- 不把內建 10 類搬進設定檔（風險高、欄位複雜）；設定檔只承載**朋友自訂**的分類。
- 不支援朋友自行「刪除內建分類」（那需要動程式）——用不到的內建分類指南教他放著不理。
- 不做 CI/雲端；朋友一樣本機執行。
- 不自動化帳號類步驟（BotFather、Notion integration、Gemini key）——指南帶著做。
- 不改 provider 抽象化既有行為；朋友一樣用 Gemini（免費額度）。

---

## 1. 程式：自訂分類設定檔驅動

### 設計原則

內建 10 類（restaurant / place / todo / article / quote / apparel / skincare / photo /
funny / inbox）**維持寫死在程式中不動**。新增一層「自訂分類」機制,只承載朋友額外要的
分類,每個自訂分類套用一套固定的**標準欄位**,朋友因此不需要理解 Notion 欄位型別。

朋友要碰的檔案只有兩個:`custom_categories.toml` 與 `.env`。

### 1a. `custom_categories.toml`（新檔,repo 根目錄）

Python 3.11 內建 `tomllib` 可讀（唯讀即可,我們只讀不寫）。範例內容:

```toml
# 在這裡新增你自己的資料庫分類。
# 每一塊 [[category]] 就是一個新資料庫。複製一整塊、改三個地方即可,存檔後重啟機器人。
#
# 範例（想收集食譜就把下面兩行的 # 拿掉,或照著新增一塊）:
# [[category]]
# key  = "recipe"        # 英文小寫代號,不能有空格;會對應 .env 的 NOTION_DB_RECIPE
# name = "食譜"           # 在 Notion 顯示的表格名稱
# hint = "食譜、料理作法、想煮的菜、菜單截圖"   # 告訴 AI 什麼東西該歸到這一類
```

- 檔案不存在或沒有任何 `[[category]]` → 視為零個自訂分類（等同目前行為）。
- 每個自訂分類的**標準欄位**（provision 與寫入都用這一套）:
  - `Name`（title）← AI 抽出的 `name`（沒有就用 raw_text 開頭）
  - `Notes`（rich_text）← AI 抽出的 `notes`
  - `Tags`（multi_select）← AI 抽出的 `tags`
  - `Source`（url）← Telegram 訊息連結
  - `Date Added`（date）← 當下時間

### 1b. `categories.py`（新模組）

單一載入點,供其他模組取用:

- `load_custom_categories() -> list[CustomCategory]`
  - 讀 `custom_categories.toml`（路徑相對 repo 根;找不到回空 list）。
  - 每筆驗證:`key` 必填、小寫、`^[a-z][a-z0-9_]*$`、不得與內建 10 類 key 衝突、彼此不重複；
    `name`、`hint` 必填非空。任一不合法 → 啟動時明確報錯（訊息指出哪個 key 錯在哪）。
  - `CustomCategory` 具 `key`、`name`、`hint`、`env_var`（= `NOTION_DB_<KEY 大寫>`）。
- `all_category_keys() -> list[str]`：內建 keys + 自訂 keys（`inbox` 恆為 fallback）。
- `custom_category_keys() -> set[str]`：判斷某 key 是否為自訂。
- `render_custom_prompt_section() -> str`：把自訂分類組成一段附加提示（見 §1d）。

> 快取:啟動時載入一次即可（沿用 `lru_cache` 風格）。朋友改完 toml 需重啟才生效——
> 指南會明講。

### 1c. `config.py` 調整

- 新增 `digest_enabled: bool = True`（見 §2）。
- `db_id_for_category(category, settings)`:
  - 內建 key → 沿用現有 `_CATEGORY_TO_ATTR` 對應。
  - 自訂 key → 讀環境變數 `NOTION_DB_<KEY 大寫>`（透過 `os.environ`,因為 pydantic
    Settings 是固定欄位；自訂 db-id 不進 Settings）。取不到或空 → 退回 `notion_db_inbox`
    並記一筆 warning（避免整支程式因少填一個 id 而崩）。
- Settings 對自訂 db-id 用 `model_config` 的 `extra="ignore"`,確保 `.env` 裡多出的
  `NOTION_DB_RECIPE=...` 不會讓 pydantic 報 "extra fields"。

### 1d. `classifier.py` 調整

- enum 來源改為 `all_category_keys()`（內建 + 自訂）。
- 系統提示 = `classify.md` 內文 + `render_custom_prompt_section()` + 既有 `_JSON_INSTRUCTION`。
  附加段落形如:

  ```
  ## 你自訂的分類
  - **recipe**（食譜）— 食譜、料理作法、想煮的菜、菜單截圖。Extract: name（標題/菜名）,
    notes（一行備註,可空）, tags（主題標籤陣列,可空）。
  ```

- `_JSON_INSTRUCTION` 內的 category 清單同樣改用 `all_category_keys()`,使 Gemini JSON
  模式也認得自訂類。

### 1e. `notion_writer.py` 調整

- `build_properties`:自訂 key（`category in custom_category_keys()`）→ 走**通用標準欄位**
  builder（Name/Notes/Tags/Source/Date Added）。內建 key 分支完全不動。
- Google Maps link 邏輯（僅 restaurant/place）不變。

### 1f. `provision_notion.py` 調整（加「只建新自訂表」模式）

- 沿用現有「一鍵建 10 個內建表」行為（無第二參數時）。
- 新增用法:`uv run python scripts/provision_notion.py add <PARENT_PAGE_ID>`
  - 讀 `custom_categories.toml`,對每個自訂分類用**標準欄位 schema** 建表,
    印出 `NOTION_DB_<KEY>=<id>` 讓朋友貼進 `.env`。
  - （初版可全建；是否略過已存在的表為 nice-to-have,實作階段再定。）

### digest.py 注意

`digest.py` 依賴 `notion_db_todo`、`notion_db_article` 兩個內建分類。朋友端 digest 關閉
（§2）故不受影響;內建分類也不會被移除,無需改 `digest.py`。

---

## 2. `DIGEST_ENABLED` 開關

- `config.py`:`digest_enabled: bool = True`（預設開 → Shao 的 bot 行為不變）。
- `main.py`:僅在 `settings.digest_enabled` 為真時 `scheduler.add_job(... weekly_digest ...)`;
  為假時記一行 log「digest disabled by config」並**完全不排程**。
- `.env.example`:新增 `DIGEST_ENABLED=true`。
- 朋友 `.env`:`DIGEST_ENABLED=false` → 零提醒。指南整份不出現 digest / 週日摘要字眼,
  `.env` 範本也拿掉 `DIGEST_HOUR` / `DIGEST_MINUTE`（留著無害但避免混淆）。

---

## 3. Windows 11 指南（`docs/friend-setup-windows.md`）

沿用 macOS 版的敘事骨架與語氣（每步:要貼什麼指令 → 會看到什麼 → 卡住怎麼解 →
關鍵處放大警告),但針對「沒學過電腦」再加白話。平台對應:

| 主題 | macOS 版 | Windows 11 版 |
|------|----------|---------------|
| 裝工具 | Homebrew → `brew install uv git` | 內建 `winget`:`winget install --id=astral-sh.uv -e`、`winget install --id=Git.Git -e` |
| 終端機 | Terminal（Spotlight） | 「終端機」/「PowerShell」（開始功能表搜尋;或 Win+X → 終端機） |
| 取得程式碼 | `git clone ... ~/telegram-inbox-bot` | `git clone ... $env:USERPROFILE\telegram-inbox-bot`;`cd $env:USERPROFILE\telegram-inbox-bot` |
| 改 `.env` | `open -e .env` | `notepad .env`（避免 Explorer 隱藏副檔名的雷） |
| 查 uv 路徑 | `which uv` | `where.exe uv` |
| 家目錄 | `echo $HOME` | `echo $env:USERPROFILE`（`C:\Users\你的名字`） |
| 開機自動啟動 | launchd plist + bootstrap | `windows\run_bot.bat` + `schtasks`（見 §4） |
| 別睡眠 | 系統設定→鎖定畫面 | 設定 → 系統 → 電源 → 螢幕與睡眠 → 睡眠設「永不」 |

### 章節結構（草案）

0. 這是什麼 / 準備什麼（Windows 版:一台長開的 Win11 電腦、Google 帳號、Notion 帳號、手機 Telegram）
1. 裝工具（winget 裝 uv、git）
2. 取得程式碼（clone + cd）
3. 建 Telegram 機器人（拿 token）
4. 建私人頻道 + 設機器人為管理員
5. 建 `.env`（先填 token;範本標明 `CLASSIFIER_PROVIDER=gemini`、`DIGEST_ENABLED=false`,無 digest 欄位）
6. 抓頻道 ID（`get_channel_id.py`）
7. 建 Notion Integration + 母頁面
8. 一鍵建 10 個內建表（`provision_notion.py`）
9. 手動幫「待辦」加 `Status` 欄位（同 macOS,重要）
10. 拿 Gemini 金鑰
11. 裝套件 + 冒煙測試（`uv sync` → 前景試跑 → 頻道貼圖驗證）
12. 設開機自動啟動（`run_bot.bat` + `schtasks`,見 §4）
13. **【新】自己新增/移除一個子資料庫（以「食譜」為例）** — 見 §5
14. 疑難排解速查表（Windows 版）
15. 收工檢查清單

「沒學過電腦」強化:名詞第一次出現白話解釋、每節開頭一句「這步在做什麼/為什麼」、
關鍵地雷用 ⚠️ 放大、多用「你會看到……就代表成功」。**全份無任何提醒/摘要內容。**

---

## 4. 開機自動啟動（方案一:`run_bot.bat` + `schtasks`）

### 4a. `windows\run_bot.bat`（新檔,repo 內附）

- 切到專案目錄、以完整 uv 路徑執行 `uv run python -m inbox_bot.main`。
- 含「當掉自動重跑」迴圈（等同 macOS launchd `KeepAlive`）:

  ```bat
  @echo off
  cd /d "%~dp0.."
  :loop
  uv run python -m inbox_bot.main
  echo [%date% %time%] bot exited, restarting in 5s...
  timeout /t 5 /nobreak >nul
  goto loop
  ```

  （`%~dp0..` = bat 所在的 `windows\` 的上一層 = 專案根,免寫死使用者名稱。）

### 4b. 用 `schtasks` 註冊為「登入時自動執行」

指南提供一行可複製指令（把使用者名稱/路徑用變數帶入,盡量免手改）:

```
schtasks /create /tn "TelegramInboxBot" /tr "\"%USERPROFILE%\telegram-inbox-bot\windows\run_bot.bat\"" /sc onlogon /rl limited /f
```

- `/sc onlogon` = 登入時啟動;`run_bot.bat` 的迴圈負責當掉重啟 → 兩者互補不衝突。
- 驗證:`schtasks /query /tn "TelegramInboxBot"`。
- 首次可 `schtasks /run /tn "TelegramInboxBot"` 立即啟動,不必登出登入。
- 視窗處理:預設會有一個終端機視窗;指南說明可最小化,不要關閉（關掉=停掉機器人）。
  （進階隱藏視窗為 nice-to-have,初版不做,以免增加非技術者的困惑。）

---

## 5. 指南第 13 節:自己增減子資料庫（以「食譜」為例）

四步,全程複製貼上,不碰 Python:

1. **描述你的新分類**:`notepad custom_categories.toml`,複製一塊 `[[category]]`,
   改 `key`（如 `recipe`）、`name`（如 `食譜`）、`hint`（何時該歸這類）。存檔。
2. **建 Notion 表格**:回終端機跑
   `uv run python scripts/provision_notion.py add <你的母頁面id>`,
   會印出 `NOTION_DB_RECIPE=xxxx`。
3. **接上 id**:`notepad .env`,把上一步那行 `NOTION_DB_RECIPE=...` 貼進去,存檔。
4. **重啟機器人**:`schtasks /end /tn "TelegramInboxBot"` 然後
   `schtasks /run /tn "TelegramInboxBot"`（或重開機）。之後貼食譜截圖就會自動進「食譜」表。

**移除**:把 `custom_categories.toml` 裡那塊 `[[category]]` 刪掉 → 重啟。舊 Notion 表格
若不要,自己到 Notion 刪。（`.env` 的那行留著無害。）

附「常見錯誤」小方塊:key 有空格/大寫、忘了重啟、母頁面 id 貼錯、忘了先建表就貼 id。

---

## 6. 交付:精美可列印版（`docs/friend-setup-windows.html`）

- 單一自包含 HTML:內嵌 CSS、不依賴外部資源（可離線開/列印）。
- 設計:大字級、清楚步驟卡片、彩色提醒框（提示/警告/成功長這樣）、指令用等寬框、
  A4 `@media print` 樣式（分頁合理、隱藏互動元素）。繁體中文。
- 用途:Shao 用瀏覽器開 → Ctrl+P 直接列印,或「另存為 PDF」交給朋友邊看邊操作。
- 內容與 `.md` 指南一致（同一份資訊的精美版）。

---

## 影響檔案清單

**新增**
- `custom_categories.toml`
- `src/inbox_bot/categories.py`
- `windows/run_bot.bat`
- `docs/friend-setup-windows.md`
- `docs/friend-setup-windows.html`

**修改**
- `src/inbox_bot/config.py`（`digest_enabled`;`db_id_for_category` 支援自訂;`extra="ignore"`）
- `src/inbox_bot/classifier.py`（enum + 提示改用 `all_category_keys()` / 自訂段落）
- `src/inbox_bot/notion_writer.py`（`build_properties` 自訂類走通用欄位）
- `src/inbox_bot/main.py`（`digest_enabled` 才排程）
- `scripts/provision_notion.py`（`add` 子模式）
- `.env.example`（`DIGEST_ENABLED=true`）

## 測試

- `test_categories.py`:合法/非法 toml 驗證、與內建衝突偵測、env_var 命名。
- `test_config.py`:`db_id_for_category` 自訂 key 路徑;`digest_enabled` 預設 True。
- `test_classifier.py`:enum 含自訂 key;提示附加段落存在。
- `test_notion_writer.py`:自訂類走標準欄位 builder。
- `test_main.py`:`digest_enabled=False` 時不註冊 weekly_digest job。
- 既有測試全數維持綠燈（確認內建行為零回歸）。

## 對 Shao 現有 bot 的相容性保證

- 無 `custom_categories.toml` → 行為與現在完全相同。
- `DIGEST_ENABLED` 預設 True → 週日 digest 照排。
- 內建 10 類的 enum、提示、欄位、provision 全數不動。
