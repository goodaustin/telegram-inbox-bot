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

## Architecture

See `docs/specs/2026-06-28-telegram-inbox-bot-design.md`.
