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

### To stop / restart the daemon

```bash
launchctl unload ~/Library/LaunchAgents/com.shao.telegram-inbox.plist
launchctl load   ~/Library/LaunchAgents/com.shao.telegram-inbox.plist
```

### Logs

- App: `logs/bot.log` (rotated daily, 14 days kept)
- launchd: `logs/launchd.out.log`, `logs/launchd.err.log`

## ⚠️ Dependency constraint: `notion-client` pinned `>=2.2,<2.4`

Do **not** upgrade `notion-client` to 2.4+. This Notion workspace is on the new
**data-sources API**, and notion-client 2.4.0+ defaults to Notion-Version
`2025-09-03`, which breaks this codebase in three ways:

- `databases.create(properties=...)` silently ignores `properties` (DBs come out
  as empty shells with only a Name column)
- `databases.query` is removed (replaced by `data_sources.query`)
- `pages.create(parent={"database_id": ...})` fails (needs `data_source_id` parent)

All of `notion_writer.py` and `digest.py` use the classic `database_id` parent +
`databases.query`, which only work under Notion-Version `2022-06-28` (the default
in notion-client 2.3.x). If you ever need to upgrade, migrate the code to the
data-sources API instead of bumping the pin.

> The `Status` property on the todo DB must be created **by hand in the Notion UI**
> (status-type properties cannot be created via either API version). It needs
> options `Todo` and `Done`.

## Architecture

See `docs/specs/2026-06-28-telegram-inbox-bot-design.md`.
