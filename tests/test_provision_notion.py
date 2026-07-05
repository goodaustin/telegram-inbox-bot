from inbox_bot.categories import CustomCategory
import importlib.util, pathlib

spec = importlib.util.spec_from_file_location(
    "provision_notion",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "provision_notion.py",
)
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)


def test_custom_db_definitions_shape():
    cats = [CustomCategory(key="recipe", name="食譜", hint="h")]
    defs = provision.custom_db_definitions(cats)
    assert len(defs) == 1
    env_var, title, props = defs[0]
    assert env_var == "NOTION_DB_RECIPE"
    assert title == "食譜"
    assert set(props) == {"Name", "Notes", "Tags", "Source", "Date Added"}
    assert props["Name"] == {"title": {}}
    assert props["Tags"] == {"multi_select": {}}
