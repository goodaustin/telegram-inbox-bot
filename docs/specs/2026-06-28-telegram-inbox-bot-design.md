# Telegram Inbox Bot — Design Spec

**Date:** 2026-06-28
**Owner:** shao
**Status:** Draft — awaiting user review

---

## Problem

I screenshot a lot of things on my phone (restaurants I want to try, places I want to travel to, todos, articles to read, quotes, clothes, skincare). They pile up in my Camera Roll and I forget them. I want to:

1. Throw them into one place from my phone (Telegram).
2. Have them auto-categorized and stored in structured, searchable lists.
3. Get weekly nudges so todos and reading don't slip.
4. For places, get a one-tap link to Google Maps.

## Goals

- **One inbox**: Share-sheet from phone → Telegram channel → done.
- **Zero manual triage** in 90%+ of cases. Low-confidence items land in an "Inbox" DB for me to fix manually.
- **Searchable lists by category and region** in Notion, viewable on phone.
- **Weekly Sunday morning nudge** so I actually act on todos and read what I saved.

## Non-Goals

- Not building an Apple Shortcut or iOS app. Telegram's share-sheet is the entry point.
- Not handling video or audio. Images + text only.
- Not building cross-device sync logic. Notion handles that.
- Not building a web UI. Notion is the UI.

---

## Architecture

```
[📱 iPhone]
    │ share to Telegram channel
    ▼
[Telegram Channel (private, bot is admin)]
    │ long-polling (no inbound port needed)
    ▼
[Mac Studio: bot.py daemon under launchd]
    │
    ├─→ classifier.py  →  Claude Vision API
    │                     returns JSON: {category, fields, confidence}
    │
    ├─→ notion_writer.py  →  dispatches to 1 of 8 Notion DBs
    │                        adds Maps link + Telegram source link
    │
    └─→ digest.py  (apscheduler, Sunday 07:30 Asia/Taipei)
                   →  query Notion → format → push to Telegram channel
```

**Why this shape:**
- Long-polling means the Mac Studio doesn't need a public IP or port-forward.
- One Claude vision call per message does OCR + classification + field extraction together → fewer failure points and cheaper than chaining OCR + text classifier.
- Sunday-only digest avoids notification fatigue while still catching what I added during the week.

---

## Components

| Module | Responsibility | Key dependency |
|---|---|---|
| `bot.py` | Telegram long-polling, receive `channel_post` updates, download image, hand off to classifier | `python-telegram-bot` |
| `classifier.py` | Single Claude vision API call. Returns `{category, fields, confidence, raw_text}` | `anthropic` |
| `notion_writer.py` | Map `category` → DB ID. Build properties payload. Write page. Return Notion page URL. | `notion-client` |
| `digest.py` | Scheduled job. Query Notion for open todos + unread articles. Format and post to channel. | `apscheduler` |
| `config.py` | Load `.env`, expose typed settings | `pydantic-settings` |
| `schemas.py` | Dataclasses for each category's field shape (used by classifier prompt + Notion writer) | stdlib |

Each module is independently testable. `bot.py` is the only one with side effects against the live Telegram API; the others take dicts in and return dicts out.

---

## Data Flow (per incoming message)

1. Telegram pushes `channel_post` update (long-polling).
2. `bot.py` extracts: `message_id`, `caption` (if any), `photo` (largest size) or `text`.
3. If photo: download to `/tmp/<message_id>.jpg`.
4. Build Claude vision request:
   - System prompt: "Classify this screenshot or text into one of: restaurant, place, todo, article, quote, apparel, skincare. Extract structured fields. Also return a `confidence` float (0-1) reflecting how sure you are about the category. If confidence < 0.6, set category=inbox."
   - User content: image (base64) + caption text.
   - Response format: strict JSON matching `schemas.py` (using Anthropic's tool-use forced output for reliability).
5. Parse JSON. Validate against schema. On parse failure: retry once with stricter prompt; on second failure: route to Inbox DB.
6. `notion_writer.dispatch(category, fields)`:
   - Look up DB ID from `CATEGORY_TO_DB` map.
   - Add computed fields:
     - `Maps Link`: `https://www.google.com/maps/search/?api=1&query=<urlencode(name + ' ' + city)>` (restaurants + places only)
     - `Source`: `https://t.me/c/<channel_id_short>/<message_id>` (deep link to original Telegram message)
     - `Date Added`: now in Asia/Taipei
     - `Deadline` (todos only): now + 7 days
   - Create Notion page. For images: upload the downloaded file via Notion's `file_upload` API and attach it as a page block (Telegram file URLs expire in 1 hour so external URL won't work).
7. Reply to the Telegram message: `✅ <category emoji> → <Notion page link>` so I get immediate confirmation in the channel.

---

## Notion Database Schemas

8 databases under one parent page. Each gets its own DB ID stored in `.env`.

### 1. 🍴 餐廳 (Restaurants)
| Property | Type | Notes |
|---|---|---|
| Name | Title | |
| City/Area | Select | e.g., 台北/信義, 東京/澀谷 |
| Cuisine | Multi-select | 日料, 義式, 咖啡, … |
| Maps Link | URL | auto-generated |
| Notes | Text | |
| Source | URL | Telegram deep link |
| Date Added | Date | |

### 2. 📍 想去的地點 (Places)
| Property | Type | Notes |
|---|---|---|
| Name | Title | |
| City/Country | Select | |
| Type | Select | 景點 / 活動 / 購物 / 自然 / 住宿 |
| Maps Link | URL | auto-generated |
| Notes | Text | |
| Source | URL | |
| Date Added | Date | |

### 3. ✅ 待辦事項 (Todos)
| Property | Type | Notes |
|---|---|---|
| Task | Title | |
| Deadline | Date | default = added + 7 days |
| Status | Status | Todo / Doing / Done |
| Notes | Text | |
| Source | URL | |
| Date Added | Date | |

### 4. 📖 待讀文章 (Articles)
| Property | Type | Notes |
|---|---|---|
| Title | Title | |
| URL | URL | extracted from screenshot if visible, else empty |
| Publisher | Text | 公眾號 / Substack / Twitter / … |
| Summary | Text | 1-line summary from Claude |
| Read? | Checkbox | |
| Source | URL | Telegram deep link |
| Date Added | Date | |

### 5. 💬 名言/靈感 (Quotes)
| Property | Type | Notes |
|---|---|---|
| Quote | Title | |
| Author | Text | |
| Tags | Multi-select | |
| Source | URL | |
| Date Added | Date | |

### 6. 👗 服飾 (Apparel)
| Property | Type | Notes |
|---|---|---|
| Item | Title | |
| Brand | Text | |
| Type | Select | 上衣 / 下著 / 鞋 / 包 / 配件 / 外套 |
| Price | Number | |
| URL | URL | |
| Notes | Text | |
| Source | URL | |
| Date Added | Date | |

### 7. 💄 保養 (Skincare)
| Property | Type | Notes |
|---|---|---|
| Product | Title | |
| Brand | Text | |
| Category | Select | 潔顏 / 化妝水 / 精華 / 乳液 / 面膜 / 防曬 / 其他 |
| Price | Number | |
| URL | URL | |
| Notes | Text | |
| Source | URL | |
| Date Added | Date | |

### 8. 🗂 Inbox (Fallback)
| Property | Type | Notes |
|---|---|---|
| Raw Text | Title | OCR'd text or message text |
| Reason | Text | why it landed here (low confidence / parse fail / no text) |
| Source | URL | |
| Date Added | Date | |

---

## Weekly Sunday Digest (07:30 Asia/Taipei)

`apscheduler` cron trigger fires `digest.py` every Sunday at 07:30 local. Job:

1. Query 待辦事項 DB: `Status != Done`, sorted by `Deadline`.
2. Query 待讀文章 DB: `Read? == false`, sorted by `Date Added` desc, limit 10.
3. Format markdown-style message:

```
☀️ 早安 — 本週清單 (週日 6/28)
─────────────────────────────
⚠️ 已過期 (2)
• 6/25 - 預約洗牙
• 6/27 - 回信給 Jenny

📅 本週到期 (3)
• 6/30 - 訂端午高鐵票
• 7/2  - 換護照
• 7/4  - 報名 React 課

📖 待讀 (5 篇)
• 「LLM 推論成本下降的曲線」(Substack)
• 「2026 Q2 半導體景氣...」(財訊)
• ... (再 3 篇)
   👉 全部清單: <Notion 待讀 DB 連結>
```

4. Post as message to the Telegram channel.

**Weekday behavior:** no scheduled push. Bot is silent unless I send something.

---

## Error Handling

| Failure | Behavior |
|---|---|
| Claude API timeout / 5xx | Retry once with 2s backoff. If still failing: route to Inbox DB, reply `❌ 分類失敗，已存入 Inbox` |
| Claude returns invalid JSON | Retry once with stricter prompt. If still failing: route to Inbox with raw response in Notes |
| Claude confidence < 0.6 | Route to Inbox (do not guess wrong category) |
| Image has no extractable text | Route to Inbox with `Reason: no_ocr_text` |
| Notion API write fails | Retry 3x with exponential backoff (1s, 2s, 4s). If still failing: append to `~/Projects/telegram-inbox-bot/logs/failed_writes.jsonl` and reply with error |
| Telegram API unreachable | Log + retry (python-telegram-bot has built-in reconnect for long-polling) |
| Digest job fails | apscheduler logs the exception; bot sends a short error message to the channel (`⚠️ 週日 digest 失敗，詳見 logs`) so I notice. Bot keeps running; next Sunday's job will try again. |

---

## Testing Strategy

- **Fixtures**: `tests/fixtures/` holds 10-20 real screenshots from my Camera Roll, one or two per category, named like `restaurant_taipei_ramen.jpg`. Plus a few edge cases (low-text image, ambiguous category, multi-category screenshot).
- **`test_classifier.py`**:
  - Mocked Claude responses for deterministic dispatch tests.
  - One smoke test that hits real Claude vision on the fixture set; asserts categories match expected (run manually, not in CI).
- **`test_notion_writer.py`**: mock `notion-client`; assert correct DB ID picked and payload shape.
- **`test_digest.py`**: freeze time to a Sunday 07:30; mock Notion query response; assert message format matches snapshot.
- **`test_bot.py`**: mock Telegram update objects; assert end-to-end flow (update → classifier → writer → reply) wiring.
- **Manual integration**: send a real screenshot from my phone to a test channel and verify a Notion row appears.

---

## Project Layout

```
~/Projects/telegram-inbox-bot/
├── bot.py
├── classifier.py
├── notion_writer.py
├── digest.py
├── config.py
├── schemas.py
├── prompts/
│   └── classify.md          # Claude system prompt, version-controlled
├── tests/
│   ├── fixtures/            # real screenshots
│   └── test_*.py
├── launchd/
│   └── com.shao.telegram-inbox.plist
├── logs/                    # rotated daily, gitignored
├── docs/
│   └── specs/
│       └── 2026-06-28-telegram-inbox-bot-design.md
├── .env.example
├── .gitignore
├── pyproject.toml           # uv-managed
└── README.md
```

## Tech Stack

- **Python 3.11+**, dependencies managed with `uv`
- `python-telegram-bot ^21` (async, long-polling)
- `anthropic ^0.39` (Claude vision)
- `notion-client ^2`
- `apscheduler ^3`
- `pydantic ^2` + `pydantic-settings` for config
- `pytest` + `pytest-asyncio` for tests

## Secrets (in `.env`, never committed)

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`
- `ANTHROPIC_API_KEY`
- `NOTION_TOKEN`
- 8 × `NOTION_DB_ID_<CATEGORY>`

## Deployment

- `launchd` plist auto-starts `bot.py` on Mac Studio boot.
- Logs go to `logs/bot.log` with daily rotation (Python `RotatingFileHandler` or simple `logging.handlers.TimedRotatingFileHandler`).
- Restart on crash (launchd `KeepAlive` setting).

---

## Open Items for User Review

- [ ] Confirm the 8 DB schemas (column names, select options) match how you'd actually use them
- [ ] Confirm the Sunday digest format (does the layout look right? want anything added/removed?)
- [ ] Confirm the confidence threshold of 0.6 for Inbox routing (we can tune after first week of real use)
- [ ] Confirm tech stack choices (anything you'd swap out?)

## Future (out of scope for v1)

- Auto-archive items older than N months
- Bulk re-classify when adding a new category
- Apple Shortcut as alternative input (so I can share without opening Telegram first)
- Upgrade Google Maps search URL → Places API for exact Place IDs if accuracy becomes a problem
