import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from inbox_bot.classifier import classify, ClassifierError
from inbox_bot.config import Settings
from inbox_bot.notion_writer import write_to_notion, build_telegram_url
from inbox_bot.schemas import ClassifierResult
from inbox_bot import reminders as rem
from inbox_bot.journal import write_journal, search_journal

log = logging.getLogger(__name__)

CATEGORY_EMOJI = {
    "restaurant": "🍴", "place": "📍", "todo": "✅", "article": "📖",
    "quote": "💬", "apparel": "👗", "skincare": "💄", "photo": "📷",
    "funny": "😂", "inbox": "🗂",
}

_GB_RE = re.compile(r"^/([gb])\s+(.*)$", re.S)
_OFFSET_RE = re.compile(r"^-(\d+)\s+(.*)$", re.S)


async def _route_life_command(post, cmd: str, settings: Settings) -> bool:
    """處理 /j /s /g /b 與回覆式 quick-log。回 True 表示已處理(不再走分類→Notion)。

    只在 settings.life_dir 有設定時被呼叫。日記內容只在使用者主動 /s 時才送 AI。
    """
    life = settings.life_dir
    now = datetime.now(ZoneInfo(settings.timezone))

    # /j 日記寫入
    if cmd.startswith("/j ") or cmd.startswith("/journal "):
        body = cmd.split(None, 1)[1].strip() if " " in cmd else ""
        if body:
            write_journal(body, now, life)
            await post.reply_text("📓")
        return True

    # /s 查詢
    if cmd.startswith("/s "):
        ans = await search_journal(cmd[3:].strip(), now, life, settings)
        await post.reply_text(ans[:4000] or "沒找到")
        return True

    # /g 健身、/b 讀書 補記(支援 "/g -1 內容" 補前一天)
    m = _GB_RE.match(cmd)
    if m:
        cfg = rem.load_reminders(life)
        if cfg:
            letter, rest = m.group(1), m.group(2).strip()
            day_offset = 0
            mo = _OFFSET_RE.match(rest)
            if mo:
                day_offset, rest = -int(mo.group(1)), mo.group(2).strip()
            target = rem.target_for_command(cfg, letter)
            if target and rest:
                rem.quick_log(rest, now, rem.log_path_for(target, life), day_offset)
                await post.reply_text(target.get("emoji", "✅"))
                return True

    # 回覆式 quick-log:回覆某則提醒訊息
    reply = getattr(post, "reply_to_message", None)
    if reply is not None and cmd:
        cfg = rem.load_reminders(life)
        if cfg:
            name = rem.load_msgid_map(life).get(str(reply.message_id))
            target = rem.target_by_name(cfg, name) if name else None
            if target:
                rem.quick_log(cmd, now, rem.log_path_for(target, life), 0)
                await post.reply_text(target.get("emoji", "✅"))
                return True

    return False


async def handle_channel_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    post = update.channel_post
    if post is None:
        return

    settings: Settings = ctx.bot_data["settings"]
    text = post.text or post.caption

    # life 指令(/j /s /g /b、回覆式記錄)優先攔截;未設定 life_dir 則完全略過
    if settings.life_dir and await _route_life_command(post, (text or "").strip(), settings):
        return

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
