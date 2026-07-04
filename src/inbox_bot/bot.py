import logging
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from inbox_bot.classifier import classify, ClassifierError
from inbox_bot.config import Settings
from inbox_bot.notion_writer import write_to_notion, build_telegram_url
from inbox_bot.schemas import ClassifierResult

log = logging.getLogger(__name__)

CATEGORY_EMOJI = {
    "restaurant": "🍴", "place": "📍", "todo": "✅", "article": "📖",
    "quote": "💬", "apparel": "👗", "skincare": "💄", "photo": "📷",
    "funny": "😂", "inbox": "🗂",
}


async def handle_channel_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    post = update.channel_post
    if post is None:
        return

    settings: Settings = ctx.bot_data["settings"]
    text = post.text or post.caption
    image_bytes: bytes | None = None

    if post.photo:
        # photo is a list of PhotoSize, increasing in resolution; take the largest
        largest = post.photo[-1]
        tg_file = await ctx.bot.get_file(largest.file_id)
        data = await tg_file.download_as_bytearray()
        image_bytes = bytes(data)

    telegram_url = build_telegram_url(post.chat.id, post.message_id)

    try:
        result = await classify(
            image_bytes=image_bytes, text=text, settings=settings,
        )
    except ClassifierError as e:
        log.warning("classifier failed: %s", e)
        result = ClassifierResult(
            category="inbox",
            confidence=0.0,
            raw_text=text or "(no text)",
            fields={"reason": f"classifier_error: {e}",
                    "original_category": "unknown"},
        )

    try:
        page_url = await write_to_notion(
            result=result,
            telegram_message_url=telegram_url,
            image_bytes=image_bytes,
            settings=settings,
        )
    except Exception as e:
        log.exception("notion write failed")
        await post.reply_text(f"❌ Notion 寫入失敗: {e}")
        return

    emoji = CATEGORY_EMOJI.get(result.category, "📥")
    if result.fields.get("reason", "").startswith("classifier_error"):
        await post.reply_text(f"❌ 分類失敗，已存入 Inbox\n{page_url}")
    elif result.category == "inbox":
        await post.reply_text(f"{emoji} 已存入 Inbox\n{page_url}")
    else:
        await post.reply_text(f"{emoji} → {page_url}")


def build_application(settings: Settings) -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["settings"] = settings
    # channel posts (not regular chats)
    app.add_handler(MessageHandler(
        filters.UpdateType.CHANNEL_POST, handle_channel_post,
    ))
    return app
