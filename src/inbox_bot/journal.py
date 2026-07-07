"""純文字日記管線:寫入 journal/YYYY/YYYY-MM-DD.md,以及 /s 查詢。

設計對齊 specs/journal-telegram-pipeline.md Part B:檢索交給程式(規則日期解析 +
grep),理解交給 AI(僅在需要彙整時呼叫,純單日查詢跳過 AI)。日記內容只有在使用者
主動 /s 時才送 AI,絕不排程外送。
"""
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from inbox_bot.classifier import _make_client
from inbox_bot.config import Settings

_MOOD_RE = re.compile(r"#mood:([^\s#]+)")
_TAG_RE = re.compile(r"#(?!mood:)([^\s#]+)")
_MAX_HIT_LINES = 120  # /s 送 AI 前的命中行數上限,避免超量


# ---------- 寫入 ----------

def resolve_journal_date(now: datetime) -> date:
    """凌晨 03:00 前的訊息歸前一日(夜貓緩衝)。"""
    if now.hour < 3:
        return (now - timedelta(days=1)).date()
    return now.date()


def extract_meta(text: str) -> tuple[list[str], str | None]:
    """從內文抽 #tag 與 #mood:XX。內文本身保留原樣(hashtag 留在文中,Obsidian 風格)。"""
    mood_m = _MOOD_RE.search(text)
    mood = mood_m.group(1) if mood_m else None
    tags = list(dict.fromkeys(_TAG_RE.findall(text)))  # 去重、保序
    return tags, mood


def _fmt_tag_list(tags: list[str]) -> str:
    return "[" + ", ".join(dict.fromkeys(tags)) + "]"


def _build_frontmatter(d: date, mood: str | None, tags: list[str], entries: int) -> str:
    return (
        "---\n"
        f"date: {d.isoformat()}\n"
        f"mood: {mood or ''}\n"
        f"tags: {_fmt_tag_list(tags)}\n"
        "location:\n"
        f"entries: {entries}\n"
        "---\n"
    )


def _split_frontmatter(content: str) -> tuple[list[str] | None, str]:
    """回 (frontmatter 行清單, body 原文)。無 frontmatter 則 (None, content)。"""
    lines = content.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                body = "\n".join(lines[i + 1:])
                return lines[1:i], body
    return None, content


def _parse_tag_list(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [t.strip() for t in raw.split(",") if t.strip()]


def _update_frontmatter(content: str, new_mood: str | None, new_tags: list[str]) -> str:
    """entries +1、tags 併集、mood 有新值則覆蓋。回整份更新後內容(含 body)。"""
    fm, body = _split_frontmatter(content)
    if fm is None:
        return content
    fields: dict[str, str] = {}
    order: list[str] = []
    for ln in fm:
        k, _, v = ln.partition(":")
        k = k.strip()
        if k:
            fields[k] = v.strip()
            order.append(k)
    # entries
    try:
        entries = int(fields.get("entries", "0")) + 1
    except ValueError:
        entries = 1
    fields["entries"] = str(entries)
    # tags 併集
    merged = _parse_tag_list(fields.get("tags", "[]")) + new_tags
    fields["tags"] = _fmt_tag_list(merged)
    # mood:有新值才覆蓋
    if new_mood:
        fields["mood"] = new_mood
    for k in ("date", "mood", "tags", "location", "entries"):
        if k not in order:
            order.append(k)
    new_fm = "\n".join(f"{k}: {fields.get(k, '')}" for k in order)
    return f"---\n{new_fm}\n---\n{body}"


def write_journal(text: str, now: datetime, life_dir: str, day_offset: int = 0) -> Path:
    """append 一則日記到當日檔案(不存在則建 frontmatter)。回寫入的檔案路徑。

    day_offset:0=今天(套夜貓規則);負數=補記過去某天(如 -1=昨天),
    此時直接用該日曆日、跳過凌晨3點規則,並在段落標題標註 [補記]。
    """
    if day_offset:
        d = (now + timedelta(days=day_offset)).date()
    else:
        d = resolve_journal_date(now)
    tags, mood = extract_meta(text)
    fpath = Path(life_dir) / "journal" / str(d.year) / f"{d.isoformat()}.md"
    fpath.parent.mkdir(parents=True, exist_ok=True)
    header = f"## {now.strftime('%H:%M')}" + (" [補記]" if day_offset else "")
    entry = f"{header}\n{text}\n"
    if not fpath.exists():
        fpath.write_text(_build_frontmatter(d, mood, tags, 1) + "\n" + entry, encoding="utf-8")
    else:
        updated = _update_frontmatter(fpath.read_text(encoding="utf-8"), mood, tags)
        fpath.write_text(updated.rstrip() + "\n\n" + entry, encoding="utf-8")
    return fpath


# ---------- 查詢(/s) ----------

_DATE_ISO_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_DATE_YM_RE = re.compile(r"(\d{4})-(\d{1,2})(?!-)")


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # 週一起算


def parse_date_range(query: str, now: datetime) -> tuple[date, date] | None:
    """規則解析查詢中的相對日期詞。回 (start, end) 含端點,無則 None。"""
    today = now.date()
    m = _DATE_ISO_RE.search(query)
    if m:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return (d, d)
    m = _DATE_YM_RE.search(query)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        start = date(y, mo, 1)
        end = date(y + (mo == 12), (mo % 12) + 1, 1) - timedelta(days=1)
        return (start, end)
    # 相對詞(順序重要:長詞/特例先判)
    if "前天" in query:
        d = today - timedelta(days=2)
        return (d, d)
    if "昨天" in query or "昨日" in query:
        d = today - timedelta(days=1)
        return (d, d)
    if "今天" in query or "今日" in query:
        return (today, today)
    if any(w in query for w in ("最近一週", "最近七天", "近七日", "近一週", "過去一週", "最近一周")):
        return (today - timedelta(days=6), today)
    if any(w in query for w in ("最近一個月", "近一個月", "過去一個月", "最近30天", "最近三十天")):
        return (today - timedelta(days=29), today)
    if any(w in query for w in ("上週", "上星期", "上禮拜", "上周")):
        ws = _week_start(today) - timedelta(days=7)
        return (ws, ws + timedelta(days=6))
    if any(w in query for w in ("這週", "本週", "這星期", "這禮拜", "本周", "這周")):
        return (_week_start(today), today)
    if any(w in query for w in ("上個月", "上月")):
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return (last_prev.replace(day=1), last_prev)
    if any(w in query for w in ("這個月", "本月", "這月")):
        return (today.replace(day=1), today)
    if "今年" in query:
        return (date(today.year, 1, 1), today)
    return None


_DATE_WORDS = [
    "前天", "昨天", "昨日", "今天", "今日", "最近一週", "最近七天", "近七日", "近一週",
    "過去一週", "最近一周", "最近一個月", "近一個月", "過去一個月", "最近30天", "最近三十天",
    "上週", "上星期", "上禮拜", "上周", "這週", "本週", "這星期", "這禮拜", "本周", "這周",
    "上個月", "上月", "這個月", "本月", "這月", "今年", "摘要", "彙整", "整理", "的", "心情",
]


def _keywords(query: str) -> str:
    """把日期詞/贅詞剝掉,留下真正的關鍵字。"""
    s = _DATE_ISO_RE.sub(" ", query)
    s = _DATE_YM_RE.sub(" ", s)
    for w in _DATE_WORDS:
        s = s.replace(w, " ")
    return s.strip()


def _journal_files_in_range(root: Path, rng: tuple[date, date] | None) -> list[Path]:
    jroot = root / "journal"
    if not jroot.exists():
        return []
    if rng is None:
        return sorted(jroot.rglob("*.md"))
    start, end = rng
    out = []
    d = start
    while d <= end:
        f = jroot / str(d.year) / f"{d.isoformat()}.md"
        if f.exists():
            out.append(f)
        d += timedelta(days=1)
    return out


def _grep_hits(files: list[Path], keywords: str) -> list[str]:
    """回命中段落(含檔名標記)。keywords 為空則回各檔全文(供日期範圍瀏覽)。"""
    terms = [t for t in keywords.split() if t]
    hits: list[str] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        if not terms:
            hits.append(f"# {f.stem}\n{text}")
            continue
        for ln in text.splitlines():
            if any(t in ln for t in terms):
                hits.append(f"{f.stem}: {ln.strip()}")
                if len(hits) >= _MAX_HIT_LINES:
                    return hits
    return hits


async def search_journal(
    query: str,
    now: datetime,
    life_dir: str,
    settings: Settings,
    client: AsyncOpenAI | None = None,
) -> str:
    root = Path(life_dir)
    rng = parse_date_range(query, now)
    kw = _keywords(query)

    # 純單日查詢(如 /s 昨天):直接回原文,跳過 AI 省成本
    if rng and rng[0] == rng[1] and not kw:
        files = _journal_files_in_range(root, rng)
        if not files:
            return "沒找到"
        return files[0].read_text(encoding="utf-8").strip()

    files = _journal_files_in_range(root, rng)
    quotes_dir = root / "life" / "quotes"
    if quotes_dir.exists():
        files += sorted(quotes_dir.glob("*.md"))
    hits = _grep_hits(files, kw)
    if not hits:
        return "沒找到"

    if client is None:
        client = _make_client(settings)
    content = "\n".join(hits)[:8000]
    system = (
        "你是使用者私人日記的查詢助手。只根據下方提供的日記/名言內容回答使用者的問題,"
        "簡潔、用繁體中文。若提供的內容裡沒有答案,直接回「沒找到」。不要揣測、不要說教、"
        "不要補充日記裡沒有的資訊。"
    )
    resp = await client.chat.completions.create(
        model=settings.classifier_model,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"問題:{query}\n\n可用內容:\n{content}"},
        ],
    )
    return (resp.choices[0].message.content or "沒找到").strip()
