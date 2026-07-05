import re
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BUILTIN_KEYS: list[str] = [
    "restaurant", "place", "todo", "article", "quote",
    "apparel", "skincare", "photo", "funny", "inbox",
]

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "custom_categories.toml"


class CategoryConfigError(Exception):
    pass


@dataclass(frozen=True)
class CustomCategory:
    key: str
    name: str
    hint: str

    @property
    def env_var(self) -> str:
        return f"NOTION_DB_{self.key.upper()}"


def load_custom_categories(path: Path | None = None) -> list[CustomCategory]:
    path = _DEFAULT_PATH if path is None else path
    if not path.exists():
        return []
    with path.open("rb") as f:
        data = tomllib.load(f)
    raw = data.get("category", [])
    cats: list[CustomCategory] = []
    seen: set[str] = set()
    for i, entry in enumerate(raw):
        key = entry.get("key", "")
        name = entry.get("name", "")
        hint = entry.get("hint", "")
        if not isinstance(key, str) or not _KEY_RE.match(key):
            raise CategoryConfigError(
                f"custom_categories.toml 第 {i + 1} 塊：key {key!r} 不合法"
                "（需小寫英文開頭、只含小寫英數與底線）"
            )
        if key in BUILTIN_KEYS:
            raise CategoryConfigError(f"custom_categories.toml：key {key!r} 與內建分類衝突")
        if key in seen:
            raise CategoryConfigError(f"custom_categories.toml：key {key!r} 重複")
        if not (isinstance(name, str) and name.strip()):
            raise CategoryConfigError(f"custom_categories.toml：分類 {key!r} 的 name 不可空白")
        if not (isinstance(hint, str) and hint.strip()):
            raise CategoryConfigError(f"custom_categories.toml：分類 {key!r} 的 hint 不可空白")
        seen.add(key)
        cats.append(CustomCategory(key=key, name=name.strip(), hint=hint.strip()))
    return cats


@lru_cache
def get_custom_categories() -> list[CustomCategory]:
    return load_custom_categories()


def all_category_keys(customs: list[CustomCategory] | None = None) -> list[str]:
    customs = get_custom_categories() if customs is None else customs
    return BUILTIN_KEYS + [c.key for c in customs]


def custom_category_keys(customs: list[CustomCategory] | None = None) -> set[str]:
    customs = get_custom_categories() if customs is None else customs
    return {c.key for c in customs}


def render_custom_prompt_section(customs: list[CustomCategory] | None = None) -> str:
    customs = get_custom_categories() if customs is None else customs
    if not customs:
        return ""
    lines = ["\n\n## 你自訂的分類\n"]
    for c in customs:
        lines.append(
            f"- **{c.key}**（{c.name}）— {c.hint}。"
            "Extract: name（標題）, notes（一行備註，可空）, tags（主題標籤陣列，可空）。"
        )
    return "\n".join(lines)
