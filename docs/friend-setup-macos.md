# Telegram Inbox Bot — macOS 安裝指南（給朋友版）

這份文件會帶你一步一步，把一個「自動整理機器人」裝到你的 Mac 上。
**你不需要任何程式背景**，照著抄就好；每一步都會告訴你要貼什麼指令、以及「成功的話你會看到什麼」。Shao 會在旁邊陪你，卡住隨時喊。

> 小提醒：文件裡凡是灰底的方框（像下面這種）都是「指令」，請整段複製、貼到終端機、按 Enter。
>
> ```bash
> 這是一段指令
> ```

---

## 0. 這是什麼 / 你要準備什麼

**這個機器人在做什麼？**
你在 Telegram 一個「只有你自己的頻道」裡貼東西（截圖、網址、一句話、餐廳名⋯⋯），機器人會自動判斷這是哪一類（餐廳？待辦？想讀的文章？），然後幫你分門別類存進 Notion 的表格裡，並在原訊息下面回你一個 emoji ✅ 和一條 Notion 連結。**成品就是：你在頻道貼截圖 → 它自動歸檔到 Notion。**

**這些名詞先認識一下（後面第一次用到會再解釋一次）：**
- **Telegram**：一款通訊 App，跟 LINE 類似，但可以放「機器人」。
- **Notion**：一個做筆記／資料庫的網站 App，我們用它當「儲存櫃」。
- **終端機（Terminal）**：Mac 內建的一個「打指令的黑框框」程式，等一下大部分步驟都在這裡貼指令。

**你需要準備：**
- [ ] 一台 **Mac**，而且它要能「長時間開著、不關機、不睡眠」——因為機器人要一直待命收訊息。（放家裡角落插著電就好。）
- [ ] 一個 **Google 帳號**（等一下拿一把免費的 AI 金鑰要用）。
- [ ] 一個 **Notion 帳號**（免費方案就夠）。
- [ ] 你手機上的 **Telegram** App（用來建機器人和頻道）。
- [ ] 大約 **40 分鐘**，加一點耐心。

**怎麼打開終端機？**
按鍵盤的 `Command（⌘）+ 空白鍵` 叫出 Spotlight，輸入 `Terminal`，按 Enter。會跳出一個白底或黑底、可以打字的視窗——這就是終端機，之後說「貼進終端機」都是指它。

---

## 1. 安裝三個工具（Homebrew、uv、git）

我們要先在 Mac 上裝三樣東西。它們是什麼不重要，你只要知道：**Homebrew** 是「幫你裝其他軟體的軟體」；**uv** 是「跑這支 Python 機器人的引擎」；**git** 是「下載程式碼的工具」。

### 1a. 安裝 Homebrew

把下面這段整段貼進終端機，按 Enter：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**你會看到什麼：** 它會先問你要不要繼續、可能要你輸入 Mac 的開機密碼（打密碼時螢幕不會顯示任何字，這是正常的，打完按 Enter 就好）。接著會跑一兩分鐘、跑出一堆綠色/黑色的字。最後看到 `Installation successful!` 就代表成功。

⚠️ **重要——照著畫面把 brew 加進 PATH：** 安裝完成後，終端機最下方會有一小段 `Next steps:`，裡面有**兩行**要你複製執行的指令（通常長得像下面這樣，但**請以你畫面上顯示的為準**）：

```bash
echo >> /Users/你的使用者名稱/.zprofile
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> /Users/你的使用者名稱/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

把**你畫面上那幾行**複製貼上、按 Enter。這一步是讓終端機「認得」brew 這個指令。

**驗證有沒有裝好：**

```bash
brew --version
```

**成功長這樣：** 印出像 `Homebrew 4.x.x` 的版本號。

> **如果出現 `command not found: brew` → 這樣解：**
> 代表上面「加進 PATH」那步沒做到。把終端機視窗**整個關掉、重新打開**再試一次 `brew --version`。還是不行就找 Shao，把上面那兩行 `echo ...` 手動貼一次。

### 1b. 安裝 uv

```bash
brew install uv
```

**你會看到什麼：** 跑一段安裝訊息，最後回到可以打字的狀態、沒有紅色 error。

**驗證：**

```bash
uv --version
```

**成功長這樣：** 印出像 `uv 0.x.x` 的版本號。

### 1c. 安裝 git

```bash
brew install git
```

**驗證：**

```bash
git --version
```

**成功長這樣：** 印出像 `git version 2.x.x`。

---

## 2. 取得程式碼

我們要把機器人的程式抄一份到你的 Mac 上。有兩種方式，**擇一**即可。

### 方式 A：用網址下載（如果 Shao 有給你一個 REPO 網址）

> ⚠️ **REPO 網址目前未知——請向 Shao 索取。** 他會給你一串像 `https://github.com/xxx/telegram-inbox-bot.git` 的網址，把下面指令裡的 `<REPO_URL>` 換成那串。

```bash
git clone <REPO_URL> ~/telegram-inbox-bot
```

**你會看到什麼：** 一段 `Cloning into ...`、進度百分比跑完，回到可打字狀態。你的家目錄下就多了一個 `telegram-inbox-bot` 資料夾。

### 方式 B：用隨身碟 / AirDrop 複製資料夾（如果 Shao 直接把整個資料夾給你）

請 Shao 用 **AirDrop 或隨身碟** 把整個 `telegram-inbox-bot` 資料夾傳給你，然後**把它放到你的「家目錄」**（也就是 Finder 側邊欄那個有小房子圖示、名字是你使用者名稱的位置）。放好後，最終路徑要是 `~/telegram-inbox-bot`。

### 兩種方式都要做的最後一步：進到資料夾裡

```bash
cd ~/telegram-inbox-bot
```

**你會看到什麼：** 沒有任何訊息（沒消息就是好消息）。這代表你「人」已經站在專案資料夾裡了，之後所有指令都要在這個狀態下貼。

> ⚠️ **從這裡開始，每次打開新的終端機視窗，都要先貼一次 `cd ~/telegram-inbox-bot`**，確定自己站對地方。
>
> **想確認自己站對地方？** 貼 `pwd`，應該印出結尾是 `/telegram-inbox-bot` 的路徑。

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

先複製一份範本出來：

```bash
cp .env.example .env
```

**你會看到什麼：** 沒有訊息（成功）。資料夾裡多了一個 `.env` 檔。

用文字編輯器打開它：

```bash
open -e .env
```

**你會看到什麼：** 跳出「文字編輯」程式，顯示一堆 `名稱=值` 的行。

**現在，先只填一個東西**——把你第 3 步拿到的 token，填到 `TELEGRAM_BOT_TOKEN=` 後面（等號後面直接接，不要留空格、不要加引號）：

```
TELEGRAM_BOT_TOKEN=8123456789:AAG-你的真實token
```

其餘欄位等一下會一步一步回來填。**改完記得存檔**（`Command + S`）。

下面是你**最終**這份 `.env` 大概會長的樣子（現在還不用全填，貼出來讓你心裡有底）。注意這是**朋友版（用 Gemini 當分類器）**，所以 `CLASSIFIER_PROVIDER=gemini`、`CLASSIFIER_MODEL=gemini-2.5-flash`，而 **`OPENAI_API_KEY` 這行留空就好**：

```
TELEGRAM_BOT_TOKEN=剛剛 BotFather 給的
TELEGRAM_CHANNEL_ID=（第 6 步用腳本抓）
OPENAI_API_KEY=
CLASSIFIER_PROVIDER=gemini
GEMINI_API_KEY=（第 9 步取得）
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
CONFIDENCE_THRESHOLD=0.6
TIMEZONE=Asia/Taipei
DIGEST_HOUR=7
DIGEST_MINUTE=30
```

> ⚠️ 範本裡原本有 `CLASSIFIER_PROVIDER=openai`、`CLASSIFIER_MODEL=gpt-4.1-mini`——**你要把它們改成上面那樣（gemini / gemini-2.5-flash）**。`OPENAI_API_KEY=sk-proj-...` 那行請清空成 `OPENAI_API_KEY=`。

改完先存檔。現在你的 `.env` 裡應該至少 token 已填好，這樣才能做下一步。

---

## 6. 抓「頻道 ID」

**頻道 ID 是什麼？** 是那個頻道的一組數字身分證（長得像 `-1001234567890`），程式要知道它才知道該監看哪個頻道。我們用一支小腳本自動抓。

> ⚠️ 這一步**一定要先做完第 3、4、5 步**（token 已填進 `.env`、機器人已是頻道管理員），否則抓不到。

確認你人在專案資料夾（`cd ~/telegram-inbox-bot`），然後執行：

```bash
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

現在用一支腳本，在母頁面底下自動建好 10 個表格。回到終端機（確認在 `~/telegram-inbox-bot`），把 `<母頁面id>` 換成你上一步複製的那串：

```bash
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

**為什麼要手動加？** Notion 的「Status（狀態）」型欄位有個技術限制，剛剛的腳本**沒辦法**自動幫「待辦」建這種欄位，所以要你親手加一個。**沒加的話，之後所有「待辦」類的東西都會存不進去，每週摘要也會壞掉。**

在 Notion：
1. 打開母頁面底下那個 **「待辦」** 表格。
2. 在表格右邊點 **`+`（新增 property／新增欄位）**。
3. 欄位名稱打 **`Status`**（就是英文 Status，開頭大寫）。
4. 型別（Type）選 **`Status`**（注意：是狀態型「Status」，不是文字型、不是 Select）。
5. 建好後它會自帶三個預設選項：**`Not started`、`In progress`、`Done`**。**保持原樣就好，什麼都不要改。**

⚠️⚠️ **絕對不要把選項改名。**
- 機器人存待辦時會寫入狀態 **`Not started`**；每週摘要會用 **`Done`** 來過濾已完成的。
- 這種 Status 欄位**在寫入時無法自動新建不存在的選項**，所以只要你把 `Not started` 或 `Done` 改名成別的字（例如改成 `Todo`），機器人一寫就會失敗。**保留 Notion 給你的預設英文選項即可。**

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

先安裝程式需要的套件（確認你在 `~/telegram-inbox-bot`）：

```bash
uv sync
```

**成功長這樣：** 跑出一段安裝／同步套件的訊息，最後沒有紅色 error，回到可打字狀態。

接著在前景啟動機器人：

```bash
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

## 12. 設定開機自動啟動（launchd）

**這是什麼？** 前面是你手動開著才會跑。這一步讓 Mac **每次開機就自動把機器人叫起來**，而且它萬一當掉會自動重開，你就不用管了。**launchd** 是 macOS 內建的「開機自動執行」管理員。

### 12a. 先查兩個資訊

查 `uv` 的完整路徑（等一下要填進設定檔）：

```bash
which uv
```

**你會看到什麼：** 印出一條路徑，通常是 `/opt/homebrew/bin/uv`。**把它記下來。**

查你的家目錄完整路徑：

```bash
echo $HOME
```

**你會看到什麼：** 像 `/Users/你的使用者名稱`。記下來。

### 12b. 複製並修改設定檔（plist）

專案裡已經有一份 Shao 用的範本 `launchd/com.shao.telegram-inbox.plist`。**先複製成你自己的一份**（把 `shao` 換成你的名字或代號，例如 `alex`）：

```bash
cp launchd/com.shao.telegram-inbox.plist launchd/com.alex.telegram-inbox.plist
```

用編輯器打開你這份：

```bash
open -e launchd/com.alex.telegram-inbox.plist
```

裡面**要改的地方**（照著改，其它別動）：
- `<key>Label</key>` 下面那行的 `com.shao.telegram-inbox` → 改成 `com.alex.telegram-inbox`（和檔名一致）。
- 所有出現 `/Users/shao/Projects/telegram-inbox-bot` 的路徑 → 改成你的實際路徑 `/Users/你的使用者名稱/telegram-inbox-bot`（就是 `echo $HOME` 那個路徑再加 `/telegram-inbox-bot`）。這會出現在 `WorkingDirectory`、`StandardOutPath`、`StandardErrorPath` 三處。
- `ProgramArguments` 裡第一行 `/opt/homebrew/bin/uv` → 若你 `which uv` 查到的不是這個，改成你查到的那條。
- `EnvironmentVariables` 的 `PATH` 裡若有 `/Users/shao/.local/bin`，把 `shao` 換成你的使用者名稱。

⚠️ **注意：** 這份範本假設程式在 `~/telegram-inbox-bot`（也就是家目錄下）。如果你第 2 步是照本文放的，路徑就會對。改完**存檔**。

### 12c. 把設定檔放到 LaunchAgents 並載入

先把它放進 macOS 指定的資料夾：

```bash
mkdir -p ~/Library/LaunchAgents
cp launchd/com.alex.telegram-inbox.plist ~/Library/LaunchAgents/
```

**你會看到什麼：** 沒有訊息（成功）。

⚠️ **已知地雷（很重要）：** 網路上很多教學叫你用 `launchctl load`／`unload`，但這台環境常常會回 `Input/output error`。**不要用 load/unload**，改用底下的 `bootout` + `bootstrap`。而且 `bootstrap` **偶爾自己也會 I/O error**，這是已知現象，**重試 2～3 次**通常就成功。

下面這段已經幫你包好「先卸載舊的、再載入、失敗自動重試 3 次」，**把 `com.alex.telegram-inbox` 換成你的 Label**，然後整段貼進終端機：

```bash
LABEL=com.alex.telegram-inbox
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM=$(id -u)

# 先把可能存在的舊版本卸掉（沒有的話會安靜略過）
launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true

# 載入，最多重試 3 次（bootstrap 偶發 I/O error 5）
for i in 1 2 3; do
  if launchctl bootstrap "gui/$UID_NUM" "$PLIST"; then
    echo "載入成功（第 $i 次嘗試）"
    break
  fi
  echo "第 $i 次失敗，2 秒後重試…"
  sleep 2
done

echo "目前狀態："
launchctl list | grep telegram-inbox || echo "  （沒找到——請檢查 $PLIST 內容與路徑）"
```

**成功長這樣：** 印出 `載入成功（第 N 次嘗試）`，最後 `launchctl list | grep telegram-inbox` 那行會顯示一列，中間有你的 Label。

**最後測一次：** 到頻道再貼一則訊息，確認機器人有回覆（代表自動啟動的版本也在正常運作）。

> **如果三次都失敗、或 `launchctl list` 找不到 → 這樣解：** 多半是 plist 裡的**路徑打錯**（家目錄、程式資料夾、uv 路徑其中之一）。回 12b 對照 `echo $HOME` 和 `which uv` 的結果逐一檢查，改完把 plist 重新 `cp` 到 `~/Library/LaunchAgents/` 再跑一次上面那段。真的卡住就找 Shao。

**以後重開機怎麼辦？** 正常情況它會自己啟動。萬一某次重開後機器人沒反應，把上面 12c 那整段（設定 `LABEL` 開始）**再貼一次**即可。

---

## 13. 疑難排解速查（出問題先看這裡）

| 症狀 | 可能原因 | 怎麼解 |
|---|---|---|
| 機器人完全沒反應、貼訊息石沉大海 | 機器人**沒設成頻道管理員** | 回第 4 步，把機器人加進頻道 Administrators |
| 抓 channel id 的腳本一直「等待中」 | 同上，或設錯頻道 | 檢查第 4 步；`Ctrl+C` 停掉重跑 |
| 啟動就報 token 相關錯誤 | `TELEGRAM_BOT_TOKEN` 貼錯／有多餘空格 | 回第 5 步，確認整串 token 正確、等號後不留空格不加引號 |
| provision 或啟動時 Notion 說沒權限 / 找不到頁面 | 母頁面**沒分享給 integration**，或母頁面 id 複製錯 | 回第 7b／7c 檢查 |
| 「待辦」類存不進去、每週摘要出錯 | **「待辦」表格沒加 `Status` 欄位**，或選項被改名 | 回第 9 步，加 `Status`（Status 型），保留預設 `Not started/In progress/Done`，別改名 |
| 啟動報 Gemini 金鑰無效 / 額度用完 | `GEMINI_API_KEY` 貼錯，或免費額度用盡 | 回第 10 步重拿／檢查金鑰，到 AI Studio 看額度 |
| 貼 `uv` 指令說 `command not found` | uv 不在 PATH（通常是新終端機沒重載） | 關掉終端機重開；或確認第 1b 有裝成功（`brew install uv`） |
| **機器人一直回「分類失敗」** | Gemini 與程式的相容性問題 | ⚠️ **回報 Shao**——需要他在程式端開啟 `response_format` 相容退路，這不是你端能調的 |

---

## 收工檢查清單

- [ ] `brew --version` / `uv --version` / `git --version` 都有版本號
- [ ] `.env` 全部欄位填好（token、channel id、notion token、10 個 DB id、gemini key），`OPENAI_API_KEY` 留空
- [ ] Notion 母頁面底下有 10 個表格
- [ ] 「待辦」表格有 `Status` 欄位、選項是預設的 `Not started/In progress/Done`
- [ ] 冒煙測試（第 11 步）：頻道貼截圖 → 機器人回覆 + Notion 有新資料
- [ ] launchd 已載入（`launchctl list | grep telegram-inbox` 有一列）
- [ ] Mac 設定成不睡眠、長時間開機

全部打勾就大功告成了！有任何一步卡住，把終端機上的錯誤訊息截圖給 Shao 最快。
