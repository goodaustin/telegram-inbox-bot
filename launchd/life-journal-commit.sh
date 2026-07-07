#!/bin/bash
# 每晚提交私人 life repo(日記 + log)。由 launchd com.shao.life-journal 觸發。
# 只有實際有變更時才 commit;先不 push(要 push 就自行加 private 遠端後在此加 git push)。
LIFE_DIR="${LIFE_DIR:-$HOME/Projects/life}"
cd "$LIFE_DIR" 2>/dev/null || exit 0
[ -d .git ] || exit 0
git add -A
git diff --cached --quiet && exit 0   # 沒變更 → 不 commit
git -c user.name="shao" -c user.email="a@phcebus.com" commit -m "journal: $(date +%F)"
