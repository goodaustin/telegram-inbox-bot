"""一次性：在 photo DB 的同一個 parent page 底下建立「好笑的東西」DB。

用法： uv run python scripts/create_funny_db.py
需在 notion-client >=2.2,<2.4（Notion-Version 2022-06-28）下執行。
"""
import asyncio
from notion_client import AsyncClient
from inbox_bot.config import get_settings


async def main() -> None:
    s = get_settings()
    client = AsyncClient(auth=s.notion_token)

    # 找一個現有 DB 的上層 page，把新 DB 建在同一層
    ref = await client.databases.retrieve(database_id=s.notion_db_photo)
    parent = ref["parent"]
    if parent.get("type") != "page_id":
        raise SystemExit(
            f"photo DB 的 parent 不是 page（是 {parent.get('type')}）。"
            "請手動提供一個 page_id 當 parent。"
        )
    page_id = parent["page_id"]

    db = await client.databases.create(
        parent={"type": "page_id", "page_id": page_id},
        title=[{"type": "text", "text": {"content": "好笑的東西"}}],
        properties={
            "Name": {"title": {}},
            "Tags": {"multi_select": {}},
            "Notes": {"rich_text": {}},
            "Source": {"url": {}},
            "Date Added": {"date": {}},
        },
    )
    print("好笑的東西 DB 已建立。")
    print("NOTION_DB_FUNNY=" + db["id"].replace("-", ""))


if __name__ == "__main__":
    asyncio.run(main())
