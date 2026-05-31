import asyncio
import json
import os
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ChatMemberHandler,
    ContextTypes,
)

OWNER_ID = 199134557
token = os.getenv("BOT_TOKEN")
FILE = Path("groups.json")


def load_groups():
    if FILE.exists():
        return json.loads(FILE.read_text(encoding="utf-8"))
    return {}


def save_groups(data):
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def track_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.my_chat_member.chat
    status = update.my_chat_member.new_chat_member.status

    if status in ["member", "administrator"]:
        groups = load_groups(
            import asyncio
import os
import json
import logging
import time
from functools import wraps
from pathlib import Path
from telegram import Update, ChatMember, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest

OWNER_USER_ID = 199134557
GROUPS_FILE = Path(__file__).parent / "groups.json"
ALLOWED_UPDATES = ["message", "my_chat_member", "chat_member", "callback_query"]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Storage helpers
# groups.json schema:
# {
#   "<chat_id>": {
#     "title": "اسم القروب",
#     "section": "تثبيت"
#   }
# }
# ---------------------------------------------------------------------------

def load_groups() -> dict:
    if GROUPS_FILE.exists():
        with open(GROUPS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_groups(groups: dict) -> None:
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)


def add_chat(chat_id: int, title: str, section: str) -> None:
    groups = load_groups()
    groups[str(chat_id)] = {"title": title, "section": section}
    save_groups(groups)
    logger.info("SAVED  chat_id=%s  title=%r  section=%r  total=%d",
                chat_id, title, section, len(groups))


def remove_chat(chat_id: int) -> None:
    groups = load_groups()
    if str(chat_id) in groups:
        del groups[str(chat_id)]
        save_groups(groups)
        logger.info("REMOVED  chat_id=%s  total=%d", chat_id, len(groups))


def get_section_groups(section: str) -> dict:
    """Return groups whose section matches (case-insensitive)."""
    return {
        k: v for k, v in load_groups().items()
        if v.get("section", "").strip() == section.strip()
    }


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

async def is_group_admin(update: Update) -> bool:
    member = await update.effective_chat.get_member(update.effective_user.id)
    return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)


def restricted(func):
    """Owner in private; group/channel admins in groups."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        user = update.effective_user
        if chat.type == "private":
            if user.id != OWNER_USER_ID:
                return
        else:
            if not await is_group_admin(update):
                await update.message.reply_text("هذا الأمر للمشرفين فقط")
                return
        return await func(update, context)
    return wrapper


def owner_only(func):
    """Main owner in private chat only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type != "private" or update.effective_user.id != OWNER_USER_ID:
            return
        return await func(update, context)
    return wrapper


# ---------------------------------------------------------------------------
# Broadcast helper
# ---------------------------------------------------------------------------

async def _do_broadcast(context, targets: dict, text: str = None,
                         forward_from: dict = None) -> str:
    """
    Send to all chats in `targets`.
    Pass `text` for send_message or `forward_from` (chat_id+message_id) for forward_message.
    Returns a formatted result string.
    """
    sent, failed = 0, 0
    start = time.monotonic()
    for chat_id, info in targets.items():
        try:
            if forward_from:
                await context.bot.forward_message(
                    chat_id=int(chat_id),
                    from_chat_id=forward_from["chat_id"],
                    message_id=forward_from["message_id"],
                )
            else:
                await context.bot.send_message(chat_id=int(chat_id), text=text)
            logger.info("OK → %s (%s)", chat_id, info["title"])
            sent += 1
        except Exception as e:
            logger.warning("FAIL → %s (%s): %s", chat_id, info["title"], e)
            failed += 1
        await asyncio.sleep(0.1)

    elapsed = round(time.monotonic() - start, 1)
    lines = [f"✅ أُرسلت إلى {sent} قروب"]
    if failed:
        lines.append(f"❌ فشل في {failed}")
    lines.append(f"تم الإرسال. استغرق {elapsed} ثانية")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user

    # Only respond in private chat
    if chat.type != "private":
        return

    if user.id == OWNER_USER_ID:
        keyboard = [
            [
                InlineKeyboardButton("📢 بث للكل", callback_data="cb_broadcast_all"),
                InlineKeyboardButton("📢 بث التثبيت", callback_data="cb_broadcast_tathbeet"),
            ],
            [
                InlineKeyboardButton("📊 الأقسام", callback_data="cb_sections"),
                InlineKeyboardButton("📋 القروبات", callback_data="cb_groups"),
            ],
        ]
        text = "البوت شغال ✅\nاختر أمراً:"
    else:
        keyboard = [
            [
                InlineKeyboardButton("📋 قروباتي", callback_data="cb_mygroups"),
                InlineKeyboardButton("➕ تسجيل قروب", callback_data="cb_register_info"),
            ],
        ]
        text = "البوت شغال ✅\nاختر أمراً:"

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    # Owner-only callbacks
    if data in ("cb_broadcast_all", "cb_broadcast_tathbeet", "cb_sections", "cb_groups"):
        if user.id != OWNER_USER_ID:
            await query.edit_message_text("هذا الأمر للمالك فقط.")
            return

    if data == "cb_broadcast_all":
        await query.edit_message_text(
            "📢 *بث للكل*\nأرسل الأمر مع النص:\n`/broadcast_all نص الرسالة`",
            parse_mode="Markdown",
        )

    elif data == "cb_broadcast_tathbeet":
        await query.edit_message_text(
            "📢 *بث التثبيت*\nأرسل الأمر مع النص:\n`/broadcast_tathbeet نص الرسالة`",
            parse_mode="Markdown",
        )

    elif data == "cb_sections":
        groups = load_groups()
        if not groups:
            await query.edit_message_text("لا توجد قروبات مسجلة.")
            return
        counts: dict[str, int] = {}
        for info in groups.values():
            sec = info.get("section", "غير محدد")
            counts[sec] = counts.get(sec, 0) + 1
        lines = [f"📊 *الأقسام ({len(counts)}):*"]
        for sec, count in sorted(counts.items()):
            lines.append(f"• {sec}: {count} قروب")
        lines.append(f"\nالإجمالي: {len(groups)} قروب")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")

    elif data == "cb_groups":
        groups = load_groups()
        if not groups:
            await query.edit_message_text("لا توجد قروبات مسجلة.")
            return
        lines = [f"📋 *جميع القروبات ({len(groups)}):*"]
        for chat_id, info in groups.items():
            section = info.get("section", "غير محدد")
            lines.append(f"• {info['title']}  |  {section}  |  `{chat_id}`")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")

    elif data == "cb_mygroups":
        groups = load_groups()
        if not groups:
            await query.edit_message_text(
                "لا توجد قروبات مسجلة بعد.\nاستخدم /register داخل القروب."
            )
            return
        lines = [f"📋 *القروبات المسجلة ({len(groups)}):*"]
        for chat_id, info in groups.items():
            section = info.get("section", "غير محدد")
            lines.append(f"• {info['title']}  |  {section}")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")

    elif data == "cb_register_info":
        await query.edit_message_text(
            "➕ *تسجيل قروب*\n"
            "اذهب إلى المجموعة التي تريد تسجيلها وأرسل:\n"
            "`/register`\n"
            "سيطلب منك البوت اسم القسم.",
            parse_mode="Markdown",
        )


# ── /register (two-step: ask for section) ─────────────────────────────────────

async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("استخدم هذا الأمر داخل المجموعة التي تريد تسجيلها.")
        return

    if not await is_group_admin(update):
        await update.message.reply_text("هذا الأمر للمشرفين فقط")
        return

    groups = load_groups()
    key = str(chat.id)

    if key in groups:
        info = groups[key]
        section = info.get("section", "غير محدد")
        await update.message.reply_text(
            f"هذا القروب مسجل بالفعل.\nالقسم: *{section}*",
            parse_mode="Markdown",
        )
        return

    # Store pending state and ask for section name
    context.user_data["pending_register"] = {
        "chat_id": chat.id,
        "title": chat.title or str(chat.id),
    }
    await update.message.reply_text(
        "اكتب اسم القسم تبع هذا القروب:\nمثال: تثبيت / مقارء / تحفيظ"
    )


# ── Section name reply handler (catches pending /register) ───────────────────

async def handle_section_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catches the section name sent after /register."""
    pending = context.user_data.get("pending_register")
    if not pending:
        return

    section = update.message.text.strip()
    if not section:
        return

    del context.user_data["pending_register"]
    add_chat(pending["chat_id"], pending["title"], section)
    await update.message.reply_text(
        f"✅ تم تسجيل القروب *{pending['title']}*\n"
        f"القسم: *{section}*\n"
        f"ID: `{pending['chat_id']}`",
        parse_mode="Markdown",
    )


# ── /unregister ───────────────────────────────────────────────────────────────

async def unregister_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("استخدم هذا الأمر داخل المجموعة التي تريد إزالتها.")
        return

    if not await is_group_admin(update):
        await update.message.reply_text("هذا الأمر للمشرفين فقط")
        return

    groups = load_groups()
    key = str(chat.id)

    if key not in groups:
        await update.message.reply_text("هذا القروب غير مسجل أصلاً.")
        return

    remove_chat(chat.id)
    await update.message.reply_text("✅ تم إزالة القروب من القائمة.")


# ── /groups (owner only) ──────────────────────────────────────────────────────

@owner_only
async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    groups = load_groups()
    if not groups:
        await update.message.reply_text("لا توجد قروبات مسجلة.")
        return
    lines = [f"جميع القروبات ({len(groups)}):"]
    for chat_id, info in groups.items():
        section = info.get("section", "غير محدد")
        lines.append(f"• {info['title']}  |  القسم: {section}  |  `{chat_id}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /sections (owner only) ────────────────────────────────────────────────────

@owner_only
async def sections_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    groups = load_groups()
    if not groups:
        await update.message.reply_text("لا توجد قروبات مسجلة.")
        return

    counts: dict[str, int] = {}
    for info in groups.values():
        sec = info.get("section", "غير محدد")
        counts[sec] = counts.get(sec, 0) + 1

    lines = [f"الأقسام ({len(counts)}):"]
    for sec, count in sorted(counts.items()):
        lines.append(f"• {sec}: {count} قروب")
    lines.append(f"\nالإجمالي: {len(groups)} قروب")
    await update.message.reply_text("\n".join(lines))


# ── /broadcast (disabled) ─────────────────────────────────────────────────────

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        return
    await update.message.reply_text(
        "هذا الأمر غير متاح.\n"
        "استخدم:\n"
        "• /broadcast\\_all — إرسال لجميع القروبات\n"
        "• /broadcast\\_tathbeet — إرسال لقروبات التثبيت",
        parse_mode="Markdown",
    )


# ── /broadcast_all (owner only) ───────────────────────────────────────────────

@owner_only
async def broadcast_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        await update.message.reply_text("الاستخدام: /broadcast_all نص الرسالة")
        return
    groups = load_groups()
    if not groups:
        await update.message.reply_text("لا توجد قروبات مسجلة.")
        return
    result = await _do_broadcast(context, groups, text=text)
    await update.message.reply_text(result)


# ── /broadcast_tathbeet (owner only) ──────────────────────────────────────────

@owner_only
async def broadcast_tathbeet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        await update.message.reply_text("الاستخدام: /broadcast_tathbeet نص الرسالة")
        return
    targets = get_section_groups("تثبيت")
    if not targets:
        await update.message.reply_text("لا توجد قروبات مسجلة في قسم التثبيت.")
        return
    result = await _do_broadcast(context, targets, text=text)
    await update.message.reply_text(result)


# ── /forward (owner only — unchanged) ────────────────────────────────────────

@owner_only
async def forward_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    last = context.bot_data.get("last_message")
    if not last:
        await update.message.reply_text(
            "لا توجد رسالة محفوظة.\nأرسل أي رسالة للبوت أولاً ثم أرسل /forward"
        )
        return
    groups = load_groups()
    if not groups:
        await update.message.reply_text("لا توجد قروبات مسجلة.")
        return
    result = await _do_broadcast(context, groups, forward_from=last)
    summary = result.replace("أُرسلت", "تمت إعادة التوجيه")
    await update.message.reply_text(summary)


# ── /debug (owner only) ───────────────────────────────────────────────────────

@owner_only
async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not GROUPS_FILE.exists():
        await update.message.reply_text(
            "ملف groups.json غير موجود.\nاستخدم /register داخل مجموعة أولاً."
        )
        return
    raw = GROUPS_FILE.read_text(encoding="utf-8")
    await update.message.reply_text(
        f"محتوى groups.json:\n```json\n{raw}\n```", parse_mode="Markdown"
    )


# ── echo (owner private only — saves last message for /forward) ───────────────

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.bot_data["last_message"] = {
        "chat_id": update.message.chat_id,
        "message_id": update.message.message_id,
    }
    await update.message.reply_text(update.message.text)


# ---------------------------------------------------------------------------
# Automatic membership tracking
# ---------------------------------------------------------------------------

async def track_bot_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    event = update.my_chat_member
    chat = event.chat
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    logger.info(
        "my_chat_member | chat_id=%s | type=%s | title=%r | %s → %s",
        chat.id, chat.type, chat.title, old_status, new_status,
    )

    if chat.type not in ("group", "supergroup", "channel"):
        return

    ACTIVE = (ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    if old_status in ACTIVE and new_status not in ACTIVE:
        remove_chat(chat.id)
    elif old_status not in ACTIVE and new_status in ACTIVE:
        logger.info("Bot added to %r (%s) — waiting for /register to set section", chat.title, chat.id)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    app = (
        ApplicationBuilder()
        .token(token)
        .request(request)
        .build()
    )

    private_owner = filters.User(user_id=OWNER_USER_ID) & filters.ChatType.PRIVATE

    app.add_handler(ChatMemberHandler(track_bot_membership, ChatMemberHandler.MY_CHAT_MEMBER))

    # Section reply must come BEFORE echo so pending registrations are caught first
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.ChatType.PRIVATE,
        handle_section_reply,
    ))

    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register_command))
    app.add_handler(CommandHandler("unregister", unregister_command))
    app.add_handler(CommandHandler("groups", groups_command))
    app.add_handler(CommandHandler("sections", sections_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("broadcast_all", broadcast_all_command))
    app.add_handler(CommandHandler("broadcast_tathbeet", broadcast_tathbeet_command))
    app.add_handler(CommandHandler("forward", forward_command))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(MessageHandler(private_owner & filters.TEXT & ~filters.COMMAND, echo))

    logger.info("Bot started | owner=%s | allowed_updates=%s", OWNER_USER_ID, ALLOWED_UPDATES)

    app.run_polling(
        poll_interval=2,
        timeout=20,
        drop_pending_updates=False,
        allowed_updates=ALLOWED_UPDATES,
    )


if __name__ == "__main__":
    main()
        
