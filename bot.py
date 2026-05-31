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
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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
        groups = load_groups()
        groups[str(chat.id)] = {
            "title": chat.title,
        }
        save_groups(groups)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت يعمل ✅")


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(ChatMemberHandler(track_groups))

    app.run_polling()


if __name__ == "__main__":
    main()
