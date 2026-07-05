import textwrap
from pathlib import Path
import pytest
from inbox_bot.categories import (
    BUILTIN_KEYS, CustomCategory, CategoryConfigError,
    load_custom_categories, all_category_keys, custom_category_keys,
    render_custom_prompt_section,
)


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "custom_categories.toml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_missing_file_returns_empty(tmp_path):
    assert load_custom_categories(tmp_path / "nope.toml") == []


def test_empty_file_returns_empty(tmp_path):
    p = _write(tmp_path, "# only comments\n")
    assert load_custom_categories(p) == []


def test_loads_valid_category(tmp_path):
    p = _write(tmp_path, """
        [[category]]
        key = "recipe"
        name = "食譜"
        hint = "食譜、料理作法"
    """)
    cats = load_custom_categories(p)
    assert cats == [CustomCategory(key="recipe", name="食譜", hint="食譜、料理作法")]
    assert cats[0].env_var == "NOTION_DB_RECIPE"


def test_key_colliding_with_builtin_rejected(tmp_path):
    p = _write(tmp_path, """
        [[category]]
        key = "todo"
        name = "待辦2"
        hint = "x"
    """)
    with pytest.raises(CategoryConfigError, match="todo"):
        load_custom_categories(p)


def test_duplicate_custom_key_rejected(tmp_path):
    p = _write(tmp_path, """
        [[category]]
        key = "recipe"
        name = "食譜"
        hint = "x"
        [[category]]
        key = "recipe"
        name = "食譜B"
        hint = "y"
    """)
    with pytest.raises(CategoryConfigError, match="recipe"):
        load_custom_categories(p)


@pytest.mark.parametrize("bad", ["Recipe", "my recipe", "3recipe", "recipe!", ""])
def test_invalid_key_shape_rejected(tmp_path, bad):
    p = _write(tmp_path, f"""
        [[category]]
        key = "{bad}"
        name = "x"
        hint = "y"
    """)
    with pytest.raises(CategoryConfigError):
        load_custom_categories(p)


def test_missing_name_or_hint_rejected(tmp_path):
    p = _write(tmp_path, """
        [[category]]
        key = "recipe"
        name = ""
        hint = "y"
    """)
    with pytest.raises(CategoryConfigError, match="recipe"):
        load_custom_categories(p)


def test_all_and_custom_keys():
    cats = [CustomCategory(key="recipe", name="食譜", hint="h")]
    assert all_category_keys(cats) == BUILTIN_KEYS + ["recipe"]
    assert custom_category_keys(cats) == {"recipe"}
    assert "inbox" in BUILTIN_KEYS


def test_render_prompt_section():
    assert render_custom_prompt_section([]) == ""
    cats = [CustomCategory(key="recipe", name="食譜", hint="食譜、料理作法")]
    section = render_custom_prompt_section(cats)
    assert "你自訂的分類" in section
    assert "recipe" in section
    assert "食譜" in section
    assert "食譜、料理作法" in section
