# Telegram Inbox Bot — Windows 11 安裝指南（給朋友版）

這份文件會帶你一步一步，把一個「自動整理機器人」裝到你的 Windows 11 電腦上。
**你不需要任何程式背景**，照著抄就好；每一步都會告訴你要貼什麼指令、以及「成功的話你會看到什麼」。Shao 會在旁邊陪你，卡住隨時喊。

> 小提示：文件裡凡是灰底的方框（像下面這種）都是「指令」，請整段複製、貼到終端機、按 Enter。
>
> ```powershell
> 這是一段指令
> ```

---

## 0. 這是什麼／你要準備什麼

**這個機器人在做什麼？**
你在 Telegram 一個「只有你自己的頻道」裡貼東西（截圖、網址、一句話、餐廳名⋯⋯），機器人會自動判斷這是哪一類（餐廳？待辦？想讀的文章？），然後幫你分門別類存進 Notion 的表格裡，並在原訊息下面回你一個 emoji ✅ 和一條 Notion 連結。**成品就是：你在頻道貼截圖 → 它自動歸檔到 Notion。**

**這些名詞先認識一下（後面第一次用到會再解釋一次）：**
- **Telegram**：一款通訊 App，跟 LINE 類似，但可以放「機器人」。
- **Notion**：一個做筆記／資料庫的網站 App，我們用它當「儲存櫃」。
- **終端機（Terminal）**：Windows 內建的一個「打指令的黑框框」程式，等一下大部分步驟都在這裡貼指令。

**你需要準備：**
- [ ] 一台 **Windows 11 電腦**，而且它要能「長時間開著、不關機、不睡眠」——因為機器人要一直待命收訊息。（放家裡角落插著電就好。）
- [ ] 一個 **Google 帳號**（等一下拿一把免費的 AI 金鑰要用）。
- [ ] 一個 **Notion 帳號**（免費方案就夠）。
- [ ] 你手機上的 **Telegram** App（用來建機器人和頻道）。
- [ ] 大約 **40 分鐘**，加一點耐心。

**怎麼打開終端機？**
按 **開始功能表**（螢幕左下角視窗圖示），直接打字輸入「終端機」，會跳出「終端機」App，按 Enter 打開。（也可以按鍵盤的 `Win + X`，再點選單裡的「終端機」。）會跳出一個黑底、可以打字的視窗——這就是終端機，之後說「貼進終端機」都是指它。

---

## 1. 裝工具（uv、git）

我們要先在 Windows 上裝兩樣東西。它們是什麼不重要，你只要知道：**uv** 是「跑這支 Python 機器人的引擎」；**git** 是「下載程式碼的工具」。Windows 11 內建一個叫 **winget** 的「幫你裝其他軟體的軟體」，我們直接用它裝。

### 1a. 安裝 uv

```powershell
winget install --id=astral-sh.uv -e
```

**你會看到什麼：** 跑一段下載／安裝訊息，最後回到可以打字的狀態、沒有紅色 error。中途如果跳出「使用者帳戶控制」視窗問你要不要允許，點「是」。

### 1b. 安裝 git

```powershell
winget install --id=Git.Git -e
```

**你會看到什麼：** 同樣跑一段安裝訊息，最後回到可打字狀態。

### 1c. 驗證（重要：先把終端機關掉重開）

⚠️ **裝完要把終端機視窗整個關掉、重新打開**，剛裝好的工具才會被電腦「認得」（這叫 PATH 更新）。重開後貼：

```powershell
uv --version
```

```powershell
git --version
```

**成功長這樣：** 分別印出像 `uv 0.x.x`、`git version 2.x.x` 的版本號。

> **如果 `winget` 說找不到指令 → 這樣解：**
> 開啟「Microsoft Store」，搜尋並更新「應用程式安裝程式（App Installer）」，更新完再重試一次上面的 `winget install`。

---

## 2. 取得程式碼

我們要把機器人的程式抄一份到你的電腦上。

```powershell
git clone https://github.com/goodaustin/telegram-inbox-bot.git "$env:USERPROFILE\telegram-inbox-bot"
```

**你會看到什麼：** 一段 `Cloning into ...`、進度百分比跑完，回到可打字狀態。你的使用者資料夾下就多了一個 `telegram-inbox-bot` 資料夾。

進到資料夾裡：

```powershell
cd "$env:USERPROFILE\telegram-inbox-bot"
```

**你會看到什麼：** 沒有任何訊息（沒消息就是好消息）。這代表你「人」已經站在專案資料夾裡了，之後所有指令都要在這個狀態下貼。

> ⚠️ **從這裡開始，每次打開新的終端機視窗，都要先貼一次 `cd "$env:USERPROFILE\telegram-inbox-bot"`**，確定自己站對地方。
>
> **想確認自己站對地方？** 貼 `pwd`，應該印出結尾是 `\telegram-inbox-bot` 的路徑。

---

## 3. 建立你的 Telegram 機器人（拿 token）

**token 是什麼？** 就是機器人的「密碼／通行證」，程式要靠它才能用你的機器人身分收發訊息。

步驟（在手機的 Telegram App 裡做）：
1. 在 Telegram 搜尋框輸入 **`@BotFather`**，點開那個有藍色勾勾的官方帳號。
2. 送出 **`/newbot`**。
3. 它會問機器人的**顯示名稱**（隨便取，例如 `我的收納機器人`）。
4. 再問機器人的**使用者名稱**，這個必須以 `bot` 結尾（例如 `my_inbox_2026_bot`）。若說被用過，換一個。
5. 成功後，BotFather 會回你一段文字，裡面有一行 **token**，長得像 `8123456789:AAG-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`。

**先把這串 token 複製起來、貼到你自己的備忘錄暫存**，等一下第 5 步要填進設定檔。

⚠️ **token 不要外流、不要截圖貼到公開群組。** 誰拿到它就能冒充你的機器人。

---

## 4. 建一個私人頻道，並把機器人設成管理員

**為什麼要頻道？** 機器人會「監看」這個頻道，你貼進去的東西它才收得到。設成管理員它才有權限在你的貼文底下回覆。

步驟（在手機 Telegram 裡）：
1. 點右上角的鉛筆／「＋」→ **新建頻道（New Channel）**。
2. 取個名字（例如 `我的 Inbox`），類型選 **Private（私人）**。
3. 建好後進入頻道 → 點頻道名稱進**頻道設定** → **Administrators（管理員）** → **Add Admin（新增管理員）**。
4. 在搜尋框輸入你剛剛那隻機器人的使用者名稱，點它加入。
5. 權限保持預設即可（要確保它有 **Post Messages / 貼文** 的權限，預設就有）。存檔。

**成功長這樣：** 頻道的管理員名單裡出現你的機器人名字。

⚠️ **這步很容易漏：如果沒把機器人設成管理員，它完全收不到你頻道的訊息，後面一定失敗。**

---

## 5. 建立設定檔 `.env`（先填 token）

**`.env` 是什麼？** 就是一個純文字的「設定清單」，裡面放各種金鑰和參數。程式啟動時會去讀它。

先複製一份範本出來（確認你在專案資料夾裡）：

```powershell
copy .env.example .env
```

**你會看到什麼：** 印出 `已複製 1 個檔案`（或類似訊息）。資料夾裡多了一個 `.env` 檔。

用記事本打開它：

```powershell
notepad .env
```

**你會看到什麼：** 跳出「記事本」程式，顯示一堆 `名稱=值` 的行。

**現在，先只填一個東西**——把你第 3 步拿到的 token，填到 `TELEGRAM_BOT_TOKEN=` 後面（等號後面直接接，不要留空格、不要加引號）：

```
TELEGRAM_BOT_TOKEN=8123456789:AAG-你的真實token
```

其餘欄位等一下會一步一步回來填。**改完記得存檔**（`Ctrl + S`）。

下面是你**最終**這份 `.env` 大概會長的樣子（現在還不用全填，貼出來讓你心裡有底）。注意這是**朋友版（用 Gemini 當分類器）**，所以 `CLASSIFIER_PROVIDER=gemini`、`CLASSIFIER_MODEL=gemini-2.5-flash`，**`OPENAI_API_KEY` 這行留空就好**，而且 `DIGEST_ENABLED=false`：

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

> ⚠️ 範本原本是 `CLASSIFIER_PROVIDER=openai`、有 `OPENAI_API_KEY=sk-...` 和 `DIGEST_ENABLED=true`——照上面改掉，把最後一行維持成 `DIGEST_ENABLED=false` 即可。

改完先存檔。現在你的 `.env` 裡應該至少 token 已填好，這樣才能做下一步。

---

## 6. 抓「頻道 ID」

**頻道 ID 是什麼？** 是那個頻道的一組數字身分證（長得像 `-1001234567890`），程式要知道它才知道該監看哪個頻道。我們用一支小腳本自動抓。

> ⚠️ 這一步**一定要先做完第 3、4、5 步**（token 已填進 `.env`、機器人已是頻道管理員），否則抓不到。

確認你人在專案資料夾（`cd "$env:USERPROFILE\telegram-inbox-bot"`），然後執行：

```powershell
uv run python scripts/get_channel_id.py
```

**你會看到什麼：** 印出一行 `等待中… 請到你的頻道貼任一則訊息（Ctrl+C 可結束）`。程式會停在那裡等你。

現在**到手機那個頻道，隨便貼一句話**（例如打 `test` 送出）。

**成功長這樣：** 終端機馬上多印出：

```
找到了！頻道標題：'我的 Inbox'
TELEGRAM_CHANNEL_ID=-1001234567890
把上面這行貼進 .env。
```

把那行 `TELEGRAM_CHANNEL_ID=-100...` 複製，貼進 `.env` 取代原本的 `TELEGRAM_CHANNEL_ID=` 那行，**存檔**。

> **如果一直停在「等待中」、貼了訊息也沒反應 → 這樣解：**
> 十之八九是第 4 步的機器人**沒設成管理員**，或設錯頻道。回去第 4 步檢查。改好後在終端機按 `Ctrl+C` 停掉腳本，重跑一次。

---

## 7. 建立 Notion Integration + 母頁面

這一段要在**電腦瀏覽器**裡做。我們要（a）幫程式辦一張「Notion 通行證」，（b）在 Notion 開一個空頁面當「總櫃子」，並允許那張通行證進去。

### 7a. 建 Integration，拿 Notion token

**Integration 是什麼？** 就是「允許程式存取你 Notion 的授權」，它會給你一串 token（通行證）。

1. 用瀏覽器打開：**https://www.notion.so/my-integrations**
2. 點 **`+ New integration`（新建）**。
3. 取個名字（例如 `Inbox Bot`），關聯的工作區選你自己的，其他預設。建立。
4. 建好後頁面上會有 **`Internal Integration Token`**（有時要點 `Show` 才顯示），是一串 `ntn_...` 開頭的字。點旁邊複製。

**把這串貼進 `.env` 的 `NOTION_TOKEN=` 後面，存檔。**

### 7b. 建母頁面，並分享給 Integration

**母頁面是什麼？** 一個空白 Notion 頁面，等一下腳本會把 10 個表格全部建在它底下，方便集中管理。

1. 在 Notion 左側 **`+ New page`** 建一個新頁面，標題隨意（例如 `我的 Inbox`）。
2. 打開這個頁面，點**右上角的 `•••`（三個點）** → 找到 **`Connections`（連結）／`+ Add connections`** → 選你剛剛建的那個 integration（例如 `Inbox Bot`）→ 確認 `Confirm`。

**成功長這樣：** Connections 清單裡出現你的 integration 名字。

⚠️ **這步（把母頁面分享給 integration）一定要在下一步 provision 之前做完**，否則程式沒權限在裡面建表格，會直接失敗。

### 7c. 複製「母頁面 id」

看瀏覽器上方那條網址，最後面會有一長串英數字（32 個字元，可能中間夾著 `-`）。那一段就是**母頁面 id**。
例如網址 `https://www.notion.so/我的-Inbox-1a2b3c4d5e6f7890abcd1234ef567890`，其中 `1a2b3c4d5e6f7890abcd1234ef567890` 就是母頁面 id。**先複製起來**，下一步要用。

---

## 8. 一鍵建立所有表格

現在用一支腳本，在母頁面底下自動建好 10 個表格。回到終端機（確認在 `$env:USERPROFILE\telegram-inbox-bot`），把 `<母頁面id>` 換成你上一步複製的那串：

```powershell
uv run python scripts/provision_notion.py <母頁面id>
```

**成功長這樣：** 會逐行印出 `建立完成：餐廳`、`建立完成：地點`⋯⋯，最後印出一整段：

```
# ↓↓↓ 把下面全部貼進 .env ↓↓↓
NOTION_DB_RESTAURANT=xxxxxxxx...
NOTION_DB_PLACE=xxxxxxxx...
... (共 10 行) ...
NOTION_DB_INBOX=xxxxxxxx...

提醒：到 Notion 的「待辦」DB 手動新增一個 Status 欄位（status 型）。
```

**把那 10 行 `NOTION_DB_...=...` 全部複製，貼進 `.env`**，取代原本那 10 行空的（存檔）。回 Notion 看你的母頁面，底下應該多了 10 個表格（餐廳、地點、待辦、待讀待看、金句、服飾、保養、照片、好笑的東西、Inbox）。

> **如果出現 `找不到 NOTION_TOKEN` → 這樣解：** 第 7a 的 token 沒填進 `.env`，回去補、存檔再重跑。
>
> **如果出現權限相關的錯誤（unauthorized / could not find page）→ 這樣解：** 第 7b 沒把母頁面分享給 integration，或母頁面 id 複製錯。回去檢查。

---

## 9. 手動幫「待辦」表格加一個 Status 欄位（很重要，別做錯）

**為什麼要手動加？** Notion 的「Status（狀態）」型欄位有個技術限制，剛剛的腳本**沒辦法**自動幫「待辦」建這種欄位，所以要你親手加一個。**沒加的話，之後所有「待辦」類的東西都會存不進去。**

在 Notion：
1. 打開母頁面底下那個 **「待辦」** 表格。
2. 在表格右邊點 **`+`（新增 property／新增欄位）**。
3. 欄位名稱打 **`Status`**（就是英文 Status，開頭大寫）。
4. 型別（Type）選 **`Status`**（注意：是狀態型「Status」，不是文字型、不是 Select）。
5. 建好後它會自帶三個預設選項：**`Not started`、`In progress`、`Done`**。**保持原樣就好，什麼都不要改。**

⚠️⚠️ **絕對不要把選項改名。**
- 機器人存待辦時會寫入狀態 **`Not started`**。
- 這種 Status 欄位**在寫入時無法自動新建不存在的選項**，所以只要你把 `Not started` 改名成別的字（例如改成 `Todo`），機器人一寫就會失敗。**保留 Notion 給你的預設英文選項即可。**

**成功長這樣：** 「待辦」表格多了一欄 `Status`，點下拉會看到 `Not started / In progress / Done`。

---

## 10. 拿一把 Gemini AI 金鑰

**這是什麼？** 機器人靠 Google 的 Gemini AI 來「判斷你貼的東西是哪一類」。這需要一把免費的金鑰（API key）。

> ⚠️ 這步要在做「冒煙測試」（第 11 步）**之前**完成，否則機器人一啟動就會因為沒有金鑰而報錯。

1. 用 Google 帳號登入，打開：**https://aistudio.google.com/apikey**
2. 點 **`Create API key`（建立 API 金鑰）**。若問你要放在哪個專案，選預設／新建都可以。
3. 建好後複製那串金鑰（通常以 `AIza...` 開頭）。

**把它貼進 `.env` 的 `GEMINI_API_KEY=` 後面，存檔。**

到這裡，你的 `.env` 應該所有欄位都填好了（除了刻意留空的 `OPENAI_API_KEY`）。可以請 Shao 幫你快速掃一眼有沒有貼錯。

---

## 11. 安裝相依套件 + 冒煙測試（試跑一次）

**冒煙測試是什麼？** 就是「先在前景手動跑一次，親眼確認整條路通不通」，再談長期自動啟動。

先安裝程式需要的套件（確認你在 `$env:USERPROFILE\telegram-inbox-bot`）：

```powershell
uv sync
```

**成功長這樣：** 跑出一段安裝／同步套件的訊息，最後沒有紅色 error，回到可打字狀態。

接著在前景啟動機器人：

```powershell
uv run python -m inbox_bot.main
```

**你會看到什麼：** 印出幾行啟動 log（例如載入設定、開始輪詢之類），然後**停在那裡持續運作**（不會跳回可打字狀態，這是對的——它正在待命）。

現在**到手機那個頻道，貼一張截圖**（或一段文字）。

**成功長這樣：**
- 機器人會在你那則貼文**底下回覆**，內容是一個分類 emoji（例如餐廳 🍽️）加上一條 Notion 連結。
- 回 Notion 看對應的表格，會**多出一筆新資料**。

確認沒問題後，在終端機按 **`Ctrl + C`** 把它停掉（我們下一步會設成自動啟動）。

> **如果機器人回你「分類失敗」或截圖後一直沒反應 → 這樣解：**
> ⚠️ 這可能是 Gemini 相容性的問題。**請把情況（螢幕上的錯誤訊息）回報給 Shao**——這種狀況需要他在程式端開啟一個叫 `response_format` 的相容退路才能解，不是你這邊能調的。先別自己亂改。
>
> **如果出現金鑰／額度相關錯誤 → 這樣解：** 檢查 `.env` 的 `GEMINI_API_KEY` 是否貼對、沒有多餘空格；或到 Google AI Studio 看金鑰是否有效／額度是否用完。

---

## 12. 設定開機自動啟動（`run_bot.bat` + 工作排程器）

**這是什麼？** 前面是你手動開著才會跑。這一步讓 Windows **每次你登入電腦就自動把機器人叫起來**，而且它萬一當掉會自動重開，你就不用管了。專案裡已經幫你準備好一個 `windows\run_bot.bat` 啟動器（它會在機器人意外結束時自動重跑），我們只要用 Windows 內建的**工作排程器（Task Scheduler）**、透過 `schtasks` 指令把它註冊成「登入時自動啟動」即可。

先確認可以手動跑起來（前一步的冒煙測試已經驗證過了）。

註冊成「登入時自動啟動」，整段貼進終端機：

```powershell
schtasks /create /tn "TelegramInboxBot" /tr "\"%USERPROFILE%\telegram-inbox-bot\windows\run_bot.bat\"" /sc onlogon /rl limited /f
```

**你會看到什麼：** 印出 `成功: 已建立排定的工作 "TelegramInboxBot"。`

立即啟動一次（不必登出、不必重開機）：

```powershell
schtasks /run /tn "TelegramInboxBot"
```

查狀態：

```powershell
schtasks /query /tn "TelegramInboxBot"
```

**成功長這樣：** `/query` 印出一個表格，「狀態」欄會顯示 `執行中` 或類似字樣。

> 執行後會冒出一個黑底終端機小視窗，這是機器人本體。可以**最小化，但不要關閉**（關掉＝機器人停）。當掉時 `run_bot.bat` 會自動重開。
> 以後重開機它會自己啟動（因為 `/sc onlogon`＝登入時執行）。若某次沒反應，重跑上面的 `schtasks /run` 那行即可。

**別讓電腦睡眠：** 設定 → 系統 → 電源 → 螢幕與睡眠 → 把「睡眠」全部改成「永不」。

---

## 13. 自己新增／移除子資料庫（以「食譜」為例）

**這是什麼、為什麼要學？** 內建只有 10 類（餐廳、地點、待辦⋯⋯），如果你想收「食譜」這種內建沒有的類別，不必找 Shao 改程式，自己照下面四步就能加一個新表格。全程複製貼上即可。

**第 1 步：編輯 `custom_categories.toml`，打開範例、拿掉註解**

```powershell
notepad custom_categories.toml
```

打開後，複製檔案裡「範例」那一整塊（`[[category]]` 那幾行），把每行開頭的 `#` 拿掉，改成：

```
[[category]]
key  = "recipe"
name = "食譜"
hint = "食譜、料理作法、想煮的菜、菜單截圖"
```

`key` 是英文小寫代號（等一下會對應 `.env` 的 `NOTION_DB_RECIPE`）；`name` 是 Notion 表格顯示的名字；`hint` 是告訴 AI「什麼樣的內容該歸到這一類」。改完存檔。

**第 2 步：用腳本建立這個新表格**

```powershell
uv run python scripts/provision_notion.py add <你的母頁面id>
```

**成功長這樣：** 印出 `NOTION_DB_RECIPE=xxxxxxxx...`。

**第 3 步：把那行貼進 `.env`**

```powershell
notepad .env
```

把 `NOTION_DB_RECIPE=xxxxxxxx...` 貼進去（新增一行），存檔。

**第 4 步：重啟機器人，讓新設定生效**

```powershell
schtasks /end /tn "TelegramInboxBot"
```

```powershell
schtasks /run /tn "TelegramInboxBot"
```

**成功長這樣：** 之後到頻道貼食譜截圖，機器人就會自動歸到新的「食譜」表。

**移除一個子資料庫：** 把 `custom_categories.toml` 裡那一塊刪掉（或重新加回 `#` 註解掉），然後照上面「第 4 步」重啟即可。Notion 裡舊的那個表格自己手動到 Notion 刪掉（程式不會自動刪）。

> **常見錯誤小方塊：**
> - `key` 裡有空格或大寫字母 → 一定要全小寫、不能有空格（例如 `recipe`，不能是 `Recipe` 或 `my recipe`）。
> - 改完 `.toml` 或 `.env` 忘記重啟（第 4 步）→ 新設定不會生效。
> - 母頁面 id 貼錯或漏貼 → 第 2 步會失敗，回第 7c 步重新複製一次。
> - 還沒建表（第 2 步）就先把 `NOTION_DB_RECIPE=` 貼進 `.env` → 順序反了，請先跑第 2 步拿到真正的 id 再貼。
> - 內建 10 類裡有用不到的（例如你完全不需要「服飾」）→ **放著不理即可**，不會造成任何問題；真的想整個砍掉不用，才需要找 Shao 幫忙改程式。

---

## 14. 疑難排解速查表（Windows 版）

| 症狀 | 可能原因 | 怎麼解 |
|---|---|---|
| 機器人完全沒反應、貼訊息石沉大海 | 機器人**沒設成頻道管理員** | 回第 4 步，把機器人加進頻道 Administrators |
| 抓 channel id 的腳本一直「等待中」 | 同上，或設錯頻道 | 檢查第 4 步；`Ctrl+C` 停掉重跑 |
| 啟動就報 token 相關錯誤 | `TELEGRAM_BOT_TOKEN` 貼錯／有多餘空格 | 回第 5 步，確認整串 token 正確、等號後不留空格不加引號 |
| provision 或啟動時 Notion 說沒權限 / 找不到頁面 | 母頁面**沒分享給 integration**，或母頁面 id 複製錯 | 回第 7b／7c 檢查 |
| 「待辦」類存不進去 | **「待辦」表格沒加 `Status` 欄位**，或選項被改名 | 回第 9 步，加 `Status`（Status 型），保留預設 `Not started/In progress/Done`，別改名 |
| 啟動報 Gemini 金鑰無效 / 額度用完 | `GEMINI_API_KEY` 貼錯，或免費額度用盡 | 回第 10 步重拿／檢查金鑰，到 AI Studio 看額度 |
| 貼 `uv` 或 `git` 指令說 `command not found` / 不是內部或外部命令 | 剛裝好但終端機沒重開，PATH 沒更新 | 把終端機視窗**整個關掉重開**；或確認第 1 步 `winget install` 有跑成功 |
| `schtasks /query` 找不到 `TelegramInboxBot` | 排程沒建立成功，或路徑錯誤 | 檢查 `%USERPROFILE%\telegram-inbox-bot\windows\run_bot.bat` 這個檔案是否存在；重跑第 12 步的 `schtasks /create` 那行 |
| **機器人一直回「分類失敗」** | Gemini 與程式的相容性問題 | ⚠️ **回報 Shao**——需要他在程式端開啟 `response_format` 相容退路，這不是你端能調的 |

---

## 收工檢查清單

- [ ] `uv --version` / `git --version` 都有版本號
- [ ] `.env` 全部欄位填好（token、channel id、notion token、10 個 DB id、gemini key），`OPENAI_API_KEY` 留空、`DIGEST_ENABLED=false`
- [ ] Notion 母頁面底下有 10 個表格
- [ ] 「待辦」表格有 `Status` 欄位、選項是預設的 `Not started/In progress/Done`
- [ ] 冒煙測試（第 11 步）：頻道貼截圖 → 機器人回覆 + Notion 有新資料
- [ ] `schtasks /query /tn "TelegramInboxBot"` 查得到這個工作
- [ ] 電腦設定成不睡眠、長時間開機（設定 → 系統 → 電源 → 螢幕與睡眠 → 「睡眠」設為「永不」）

全部打勾就大功告成了！有任何一步卡住，把終端機上的錯誤訊息截圖給 Shao 最快。
