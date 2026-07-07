from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

from inbox_bot.journal import (
    resolve_journal_date, extract_meta, write_journal, parse_date_range, search_journal,
)

TZ = ZoneInfo("Asia/Taipei")


def _dt(y, mo, d, h=12, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=TZ)


def test_night_owl_buffer():
    assert resolve_journal_date(_dt(2026, 7, 7, 2, 30)) == _dt(2026, 7, 6).date()
    assert resolve_journal_date(_dt(2026, 7, 7, 15, 0)) == _dt(2026, 7, 7).date()


def test_extract_meta_tags_and_mood():
    tags, mood = extract_meta("今天很累 #mood:平靜 練了 #健身 也讀了 #工作 的書")
    assert mood == "平靜"
    assert tags == ["健身", "工作"]  # #mood:平靜 不被當 tag


def test_write_journal_new_file_frontmatter(tmp_path):
    p = write_journal("第一則 #mood:開心 #工作", _dt(2026, 7, 6, 21, 34), str(tmp_path))
    assert p == tmp_path / "journal" / "2026" / "2026-07-06.md"
    content = p.read_text(encoding="utf-8")
    assert "date: 2026-07-06" in content
    assert "mood: 開心" in content
    assert "工作" in content
    assert "## 21:34" in content
    assert "entries: 1" in content


def test_write_journal_appends_and_counts(tmp_path):
    write_journal("第一則", _dt(2026, 7, 6, 21, 34), str(tmp_path))
    p = write_journal("第二則 #健身", _dt(2026, 7, 6, 23, 10), str(tmp_path))
    content = p.read_text(encoding="utf-8")
    assert content.count("## ") == 2
    assert "## 23:10" in content
    assert "entries: 2" in content
    assert "健身" in content


def test_write_journal_backdate(tmp_path):
    # 今天 7/7 補記昨天(-1)→ 應寫進 2026-07-06.md 且標 [補記]
    p = write_journal("昨天漏記的", _dt(2026, 7, 7, 10, 5), str(tmp_path), day_offset=-1)
    assert p == tmp_path / "journal" / "2026" / "2026-07-06.md"
    content = p.read_text(encoding="utf-8")
    assert "date: 2026-07-06" in content
    assert "## 10:05 [補記]" in content
    assert "昨天漏記的" in content


def test_parse_date_range():
    now = _dt(2026, 7, 8, 15)  # 2026-07-08 是週三
    assert parse_date_range("昨天的事", now) == (_dt(2026, 7, 7).date(), _dt(2026, 7, 7).date())
    assert parse_date_range("2026-07-06 那天", now) == (_dt(2026, 7, 6).date(), _dt(2026, 7, 6).date())
    assert parse_date_range("這個月健身", now) == (_dt(2026, 7, 1).date(), _dt(2026, 7, 8).date())
    # 上週 = 6/29(週一)~7/5(週日)
    assert parse_date_range("上週心情", now) == (_dt(2026, 6, 29).date(), _dt(2026, 7, 5).date())
    assert parse_date_range("隨便打的關鍵字", now) is None


async def test_search_pure_date_returns_raw_no_ai(tmp_path):
    write_journal("昨天做了什麼", _dt(2026, 7, 6, 20, 0), str(tmp_path))
    now = _dt(2026, 7, 7, 10)
    # client 不給;純單日查詢不該呼叫 AI
    ans = await search_journal("昨天", now, str(tmp_path), settings=SimpleNamespace())
    assert "昨天做了什麼" in ans


async def test_search_keyword_uses_ai(tmp_path):
    write_journal("今天跟 Brady 吃飯 #吃飯", _dt(2026, 7, 6, 20, 0), str(tmp_path))
    now = _dt(2026, 7, 8, 10)
    msg = MagicMock(); msg.content = "你 7/6 跟 Brady 吃飯。"
    choice = MagicMock(); choice.message = msg
    resp = MagicMock(); resp.choices = [choice]
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=resp)
    settings = SimpleNamespace(classifier_model="gpt-4.1-mini")
    ans = await search_journal("Brady", now, str(tmp_path), settings=settings, client=client)
    assert "Brady" in ans
    client.chat.completions.create.assert_awaited_once()


async def test_search_no_hits(tmp_path):
    (tmp_path / "journal").mkdir()
    ans = await search_journal("完全不存在xyz", _dt(2026, 7, 8), str(tmp_path), settings=SimpleNamespace())
    assert ans == "沒找到"
