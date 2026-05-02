import os
import logging
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from openai import OpenAI

# ========= CONFIG =========
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

CHANNEL_URL = "https://t.me/YourChannelName"

# ========= DATABASE =========
conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    requests INTEGER DEFAULT 0
)
""")
conn.commit()
FREE_LIMIT = 5

# ========= STATES =========
LANG, MODE, LEVEL, FIELD, TOPIC, FORMAT = range(6)

# ========= HELPERS =========
def kb(rows):
    return InlineKeyboardMarkup(rows)

def nav_row():
    return [
        InlineKeyboardButton("🏠 الرئيسية", callback_data="main"),
        InlineKeyboardButton("❌ خروج", callback_data="exit"),
    ]

def check_user(uid):
    cursor.execute("SELECT requests FROM users WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    if not r:
        cursor.execute("INSERT INTO users VALUES (?,0)", (uid,))
        conn.commit()
        return True
    return r[0] < FREE_LIMIT

def inc_user(uid):
    cursor.execute("UPDATE users SET requests=requests+1 WHERE user_id=?", (uid,))
    conn.commit()

# ========= AUTO START =========
async def auto_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "started" not in context.user_data:
        context.user_data["started"] = True
        return await start(update, context)

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك في أكاديمية الباحث\n\nاختر اللغة:",
        reply_markup=kb([
            [InlineKeyboardButton("🇱🇾 العربية", callback_data="ar"),
             InlineKeyboardButton("🇬🇧 English", callback_data="en")]
        ])
    )
    return LANG

# ========= FLOW =========
async def set_lang(update, context):
    q = update.callback_query
    await q.answer()

    await q.edit_message_text(
        "اختر الخدمة:",
        reply_markup=kb([
            [InlineKeyboardButton("📊 خطة بحث", callback_data="research")],
            [InlineKeyboardButton("📈 تحليل", callback_data="analysis")],
            nav_row()
        ])
    )
    return MODE

async def set_mode(update, context):
    q = update.callback_query
    await q.answer()

    await q.edit_message_text(
        "اختر المستوى:",
        reply_markup=kb([
            [InlineKeyboardButton("ليسانس", callback_data="level")],
            [InlineKeyboardButton("ماجستير", callback_data="level")],
            nav_row()
        ])
    )
    return LEVEL

async def set_level(update, context):
    q = update.callback_query
    await q.answer()

    await q.edit_message_text(
        "اكتب موضوع البحث:",
        reply_markup=kb([nav_row()])
    )
    return TOPIC

# ========= GENERATE =========
async def generate(update, context):
    user_id = str(update.effective_user.id)

    if not check_user(user_id):
        await update.message.reply_text("❌ انتهت المحاولات المجانية")
        return ConversationHandler.END

    topic = update.message.text

    await update.message.reply_text("⏳ جاري التحليل...")

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"اكتب خطة بحث عن {topic}"}],
        max_tokens=500
    )

    text = res.choices[0].message.content

    await update.message.reply_text(text[:1200])

    # زر القناة
    await update.message.reply_text(
        "📌 للحصول على المزيد:\nانضم للقناة 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 القناة", url=CHANNEL_URL)]
        ])
    )

    inc_user(user_id)
    return FORMAT

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL, auto_start), group=0)

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(set_lang)],
            MODE: [CallbackQueryHandler(set_mode)],
            LEVEL: [CallbackQueryHandler(set_level)],
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv)

    print("🚀 BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
