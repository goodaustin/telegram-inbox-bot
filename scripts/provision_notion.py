"""在指定 Notion 母頁面下建立朋友端全部 DB，印出 .env 用的 id。

用法： uv run python scripts/provision_notion.py <PARENT_PAGE_ID>
前提：.env 已有 NOTION_TOKEN；母頁面已分享給你的 integration。
需 notion-client >=2.2,<2.4（Notion-Version 2022-06-28）。
"""
import asyncio
import os
import sys
from dotenv import load_dotenv
from notion_client import AsyncClient

from inbox_bot.categories import load_custom_categories, CustomCategory

# env-var 名稱 -> (DB 顯示標題, properties)
DBS: dict[str, tuple[str, dict]] = {
    "NOTION_DB_RESTAURANT": ("餐廳", {
        "Name": {"title": {}}, "City/Area": {"select": {}}, "Cuisine": {"multi_select": {}},
        "Maps Link": {"url": {}}, "Notes": {"rich_text": {}}, "Source": {"url": {}},
        "Date Added": {"date": {}},
    }),
    "NOTION_DB_PLACE": ("地點", {
        "Name": {"title": {}}, "City/Country": {"select": {}}, "Type": {"select": {}},
        "Maps Link": {"url": {}}, "Notes": {"rich_text": {}}, "Source": {"url": {}},
        "Date Added": {"date": {}},
    }),
    "NOTION_DB_TODO": ("待辦", {
        "Task": {"title": {}}, "Deadline": {"date": {}}, "Notes": {"rich_text": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
        # 注意：Status（status 型）API 無法建立，請到 Notion 手動加（預設選項 Not started/Done 即可，勿改名）
    }),
    "NOTION_DB_ARTICLE": ("待讀待看", {
        "Title": {"title": {}}, "URL": {"url": {}}, "Publisher": {"rich_text": {}},
        "Type": {"select": {}}, "Summary": {"rich_text": {}}, "Read?": {"checkbox": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
    }),
    "NOTION_DB_QUOTE": ("金句", {
        "Quote": {"title": {}}, "Author": {"rich_text": {}}, "Tags": {"multi_select": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
    }),
    "NOTION_DB_APPAREL": ("服飾", {
        "Item": {"title": {}}, "Brand": {"rich_text": {}}, "Type": {"select": {}},
        "Price": {"number": {}}, "URL": {"url": {}}, "Notes": {"rich_text": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
    }),
    "NOTION_DB_SKINCARE": ("保養", {
        "Product": {"title": {}}, "Brand": {"rich_text": {}}, "Category": {"select": {}},
        "Price": {"number": {}}, "URL": {"url": {}}, "Notes": {"rich_text": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
    }),
    "NOTION_DB_PHOTO": ("照片", {
        "Name": {"title": {}}, "Notes": {"rich_text": {}}, "Source": {"url": {}},
        "Date Added": {"date": {}},
    }),
    "NOTION_DB_FUNNY": ("好笑的東西", {
        "Name": {"title": {}}, "Tags": {"multi_select": {}}, "Notes": {"rich_text": {}},
        "Source": {"url": {}}, "Date Added": {"date": {}},
    }),
    "NOTION_DB_INBOX": ("Inbox", {
        "Raw Text": {"title": {}}, "Reason": {"rich_text": {}}, "Source": {"url": {}},
        "Date Added": {"date": {}},
    }),
}

STANDARD_PROPS: dict = {
    "Name": {"title": {}},
    "Notes": {"rich_text": {}},
    "Tags": {"multi_select": {}},
    "Source": {"url": {}},
    "Date Added": {"date": {}},
}


def custom_db_definitions(customs: list["CustomCategory"]) -> list[tuple[str, str, dict]]:
    return [(c.env_var, c.name, dict(STANDARD_PROPS)) for c in customs]


async def main() -> None:
    argv = sys.argv[1:]
    add_mode = bool(argv) and argv[0] == "add"
    if add_mode:
        argv = argv[1:]
    if not argv:
        raise SystemExit(
            "用法：\n"
            "  建全部內建表：uv run python scripts/provision_notion.py <PARENT_PAGE_ID>\n"
            "  只建自訂表：  uv run python scripts/provision_notion.py add <PARENT_PAGE_ID>"
        )
    parent_page_id = argv[0]
    load_dotenv()
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise SystemExit("找不到 NOTION_TOKEN（請先在 .env 填好）")
    client = AsyncClient(auth=token)

    if add_mode:
        customs = load_custom_categories()
        if not customs:
            raise SystemExit("custom_categories.toml 沒有任何分類；請先在裡面新增一塊 [[category]]")
        defs = custom_db_definitions(customs)
    else:
        defs = [(env, title, props) for env, (title, props) in DBS.items()]

    lines: list[str] = []
    for env_name, title, props in defs:
        db = await client.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": title}}],
            properties=props,
        )
        print(f"建立完成：{title}")
        lines.append(f"{env_name}={db['id'].replace('-', '')}")

    print("\n# ↓↓↓ 把下面全部貼進 .env ↓↓↓")
    print("\n".join(lines))
    if not add_mode:
        print("\n提醒：到 Notion 的「待辦」DB 手動新增一個 Status 欄位（status 型）。")
        print("      保留 Notion 的預設選項即可（Not started / In progress / Done）——")
        print("      bot 會寫入狀態「Not started」、每週摘要會過濾「Done」，請勿改成 Todo/Done。")


if __name__ == "__main__":
    asyncio.run(main())
