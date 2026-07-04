"""抓私人頻道的 chat id。

用法：先把 bot 加進頻道並設為管理員，執行本腳本後到頻道貼任一則訊息。
 uv run python scripts/get_channel_id.py
前提：.env 已有 TELEGRAM_BOT_TOKEN。
"""
import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot


async def main() -> None:
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("找不到 TELEGRAM_BOT_TOKEN（請先在 .env 填好）")

    bot = Bot(token=token)
    print("等待中… 請到你的頻道貼任一則訊息（Ctrl+C 可結束）")
    offset = None
    async with bot:
        while True:
            updates = await bot.get_updates(offset=offset, timeout=30)
            for u in updates:
                offset = u.update_id + 1
                post = u.channel_post or u.message
                if post is not None:
                    chat = post.chat
                    print(f"\n找到了！頻道標題：{chat.title!r}")
                    print(f"TELEGRAM_CHANNEL_ID={chat.id}")
                    print("把上面這行貼進 .env。")
                    return


if __name__ == "__main__":
    asyncio.run(main())
