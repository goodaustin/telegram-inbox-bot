"""提醒 + quick-log(打卡機,不是教練)。純計數、零 AI、零追問。

對齊 specs/journal-telegram-pipeline.md B8:每日檢查各 target 本週剩餘額度,剩餘>0
才各發一則;使用者「回覆」該則或用 /g /b 補記,原文存進對應 log 檔。
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

REST_MARKER = "休"
_MSGID_FILE = "life/log/.reminder_msgids.json"
_WEEKDAY = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
# /g→健身類、/b→讀書類:先比 emoji,再比名稱關鍵字
_CMD_HINTS: dict[str, tuple[str, ...]] = {
    "g": ("💪", "健身", "運動", "gym", "fitness"),
    "b": ("📖", "讀", "書", "read", "book"),
}


def load_reminders(life_dir: str) -> dict[str, Any] | None:
    p = Path(life_dir) / "life" / "reminders.yaml"
    if not p.exists():
        return None
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return data or None


def _week_start_index(cfg: dict) -> int:
    return _WEEKDAY.get(str(cfg.get("week_start", "Mon")), 0)


def week_bounds(now: datetime, week_start_index: int = 0) -> tuple[date, date]:
    """回 (本週起日, 今天)。"""
    today = now.date()
    elapsed = (today.weekday() - week_start_index) % 7
    return today - timedelta(days=elapsed), today


def count_done(log_path: Path, start: date, today: date) -> int:
    """數 log 檔本週([start, today])的有效記錄數,排除「休」。"""
    if not log_path.exists():
        return 0
    n = 0
    for ln in log_path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or "|" not in ln:
            continue
        dstr, _, rest = ln.partition("|")
        try:
            d = date.fromisoformat(dstr.strip())
        except ValueError:
            continue
        if start <= d <= today and rest.strip() != REST_MARKER:
            n += 1
    return n


def build_reminder_messages(cfg: dict, life_dir: str, now: datetime) -> list[tuple[dict, str]]:
    """回 [(target, 訊息文字)],僅含剩餘額度>0 的項目。全達標則回空清單(整日靜默)。"""
    start, today = week_bounds(now, _week_start_index(cfg))
    days_left = 7 - (today - start).days
    out: list[tuple[dict, str]] = []
    for t in cfg.get("targets", []):
        done = count_done(Path(life_dir) / t["log_to"], start, today)
        remaining = int(t["per_week"]) - done
        if remaining <= 0:
            continue
        text = f'{t.get("emoji", "")} 本週還要{t["name"]} {remaining} 次(剩 {days_left} 天)'.strip()
        if remaining >= days_left:
            text += "\n⚠️ 從今天起每天都要做才達標"
        out.append((t, text))
    return out


def quick_log(text: str, now: datetime, log_path: Path, day_offset: int = 0) -> None:
    """以「YYYY-MM-DD | 原文」append。回什麼存什麼,不做格式檢查。"""
    d = (now + timedelta(days=day_offset)).date()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"{d.isoformat()} | {text.strip()}\n")


def target_by_name(cfg: dict, name: str) -> dict | None:
    for t in cfg.get("targets", []):
        if t.get("name") == name:
            return t
    return None


def target_for_command(cfg: dict, cmd_letter: str) -> dict | None:
    """把 /g /b 對到 yaml 裡的 target(比 emoji,再比名稱關鍵字)。"""
    hints = _CMD_HINTS.get(cmd_letter, ())
    if not hints:
        return None
    for t in cfg.get("targets", []):
        hay = f'{t.get("emoji", "")}{t.get("name", "")}{t.get("log_to", "")}'.lower()
        if any(h.lower() in hay for h in hints):
            return t
    return None


def log_path_for(cfg_target: dict, life_dir: str) -> Path:
    return Path(life_dir) / cfg_target["log_to"]


# ---------- 回覆式記錄用的 message_id → target 對照 ----------

def save_msgid_map(life_dir: str, mapping: dict[str, str]) -> None:
    p = Path(life_dir) / _MSGID_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")


def load_msgid_map(life_dir: str) -> dict[str, str]:
    p = Path(life_dir) / _MSGID_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
