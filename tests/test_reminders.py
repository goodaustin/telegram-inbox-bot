from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from inbox_bot.reminders import (
    load_reminders, week_bounds, count_done, build_reminder_messages, quick_log,
    target_for_command, target_by_name, log_path_for, save_msgid_map, load_msgid_map,
)

TZ = ZoneInfo("Asia/Taipei")
CFG = {
    "week_start": "Mon",
    "check_times": {"weekday": "16:00", "weekend": "09:00"},
    "targets": [
        {"name": "健身", "per_week": 3, "log_to": "life/log/fitness.md", "emoji": "💪"},
        {"name": "讀書", "per_week": 2, "log_to": "life/log/reading.md", "emoji": "📖"},
    ],
}


def _dt(y, mo, d, h=16, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=TZ)


def _seed(tmp_path, rel, lines):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_week_bounds_monday_start():
    # 2026-07-08 週三 → 本週起 2026-07-06(週一)
    assert week_bounds(_dt(2026, 7, 8), 0) == (_dt(2026, 7, 6).date(), _dt(2026, 7, 8).date())


def test_count_done_excludes_rest_and_other_weeks(tmp_path):
    p = _seed(tmp_path, "life/log/fitness.md", [
        "2026-07-06 | 肩推",       # 本週
        "2026-07-07 | 休",         # 本週但休息 → 不計
        "2026-07-07 | 腿",         # 本週
        "2026-06-30 | 上週的",     # 上週 → 不計
    ])
    start, today = week_bounds(_dt(2026, 7, 8), 0)
    assert count_done(p, start, today) == 2


def test_build_messages_remaining_and_urgency(tmp_path):
    _seed(tmp_path, "life/log/fitness.md", ["2026-07-06 | 肩"])  # 健身已 1 次
    # 週五 2026-07-10:days_left = 7-4 = 3;健身剩 3-1=2(2<3 不緊迫);讀書剩 2(2>=3? 否 → 但 2>=days_left3? 否)
    msgs = build_reminder_messages(CFG, str(tmp_path), _dt(2026, 7, 10))
    texts = {t["name"]: msg for t, msg in msgs}
    assert "還要健身 2 次" in texts["健身"]
    assert "剩 3 天" in texts["健身"]
    assert "讀書" in texts  # 讀書 0 次 → 剩 2


def test_build_messages_urgency_flag(tmp_path):
    # 週六 2026-07-11:days_left = 7-5 = 2;健身 0 次 → 剩 3 >= 2 → ⚠️
    msgs = build_reminder_messages(CFG, str(tmp_path), _dt(2026, 7, 11))
    fitness = next(m for t, m in msgs if t["name"] == "健身")
    assert "⚠️" in fitness


def test_build_messages_met_target_silent(tmp_path):
    _seed(tmp_path, "life/log/fitness.md", [
        "2026-07-06 | a", "2026-07-07 | b", "2026-07-08 | c",  # 健身達標 3
    ])
    msgs = build_reminder_messages(CFG, str(tmp_path), _dt(2026, 7, 9))
    names = [t["name"] for t, _ in msgs]
    assert "健身" not in names  # 達標不再提醒
    assert "讀書" in names


def test_quick_log_format_and_offset(tmp_path):
    log = tmp_path / "life/log/reading.md"
    quick_log("托斯卡尼艷陽下", _dt(2026, 7, 8), log)
    quick_log("補昨天", _dt(2026, 7, 8), log, day_offset=-1)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "2026-07-08 | 托斯卡尼艷陽下"
    assert lines[1] == "2026-07-07 | 補昨天"


def test_target_lookup():
    assert target_for_command(CFG, "g")["name"] == "健身"
    assert target_for_command(CFG, "b")["name"] == "讀書"
    assert target_by_name(CFG, "讀書")["emoji"] == "📖"
    assert log_path_for(CFG["targets"][0], "/x") == Path("/x/life/log/fitness.md")


def test_msgid_map_roundtrip(tmp_path):
    save_msgid_map(str(tmp_path), {"101": "健身", "102": "讀書"})
    assert load_msgid_map(str(tmp_path)) == {"101": "健身", "102": "讀書"}
    assert load_msgid_map(str(tmp_path / "nope")) == {}


def test_load_reminders_yaml(tmp_path):
    _seed(tmp_path, "life/reminders.yaml", [
        "week_start: Mon",
        "check_times: {weekday: '16:00', weekend: '09:00'}",
        "targets:",
        "  - {name: 健身, per_week: 3, log_to: life/log/fitness.md, emoji: '💪'}",
    ])
    cfg = load_reminders(str(tmp_path))
    assert cfg["check_times"]["weekday"] == "16:00"
    assert cfg["targets"][0]["name"] == "健身"
    assert load_reminders(str(tmp_path / "none")) is None
