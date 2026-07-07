#!/bin/bash
# Reload the Telegram inbox bot launchd agent (run once after reboot / re-login).
# Plan B: bootstrap directly from the project folder because ~/Library/LaunchAgents
# is root-owned and not user-writable on this machine.
set -e
DIR="$HOME/Projects/telegram-inbox-bot/launchd"
UID_NUM=$(id -u)
# 兩個 agent:主 bot(KeepAlive)+ 每晚日記 commit(23:55)
for LABEL in com.shao.telegram-inbox com.shao.life-journal; do
  PLIST="$DIR/$LABEL.plist"
  launchctl bootout  "gui/$UID_NUM/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_NUM" "$PLIST"
done
echo "Loaded. Current state:"
launchctl list | grep -E "telegram-inbox|life-journal" || echo "  (NOT found — check plists in $DIR)"
