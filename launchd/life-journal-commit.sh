#!/bin/bash
# 每晚提交 + 推送私人 life repo(日記 + log)做異地備份。
# 由 launchd com.shao.life-journal 觸發(23:55)。推送到 private 遠端 goodaustin/life。
LIFE_DIR="${LIFE_DIR:-$HOME/Projects/life}"
cd "$LIFE_DIR" 2>/dev/null || exit 0
[ -d .git ] || exit 0
git add -A
if git diff --cached --quiet; then
  exit 0   # 沒變更 → 不 commit、不 push
fi
git -c user.name="shao" -c user.email="a@phcebus.com" commit -m "journal: $(date +%F)"
# 推到 private 遠端;失敗不致命(網路/認證問題下次再補),記到 err log
git push --quiet || echo "[$(date)] life backup push failed (will retry next run)"
