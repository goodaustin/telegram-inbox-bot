#!/bin/bash
# Reload the Telegram inbox bot launchd agent (run once after reboot / re-login).
# Plan B: bootstrap directly from the project folder because ~/Library/LaunchAgents
# is root-owned and not user-writable on this machine.
set -e
PLIST="$HOME/Projects/telegram-inbox-bot/launchd/com.shao.telegram-inbox.plist"
UID_NUM=$(id -u)
launchctl bootout  "gui/$UID_NUM/com.shao.telegram-inbox" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST"
echo "Loaded. Current state:"
launchctl list | grep telegram-inbox || echo "  (NOT found — check $PLIST)"
