import os
import logging
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from openai import OpenAI

# FILES
from docx import Document
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# ========= CONFIG =========
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

# ========= DATABASE =========
conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    requests INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    topic TEXT,
    level TEXT,
    field TEXT
)
""")

conn.commit()

# ========= STATES =========
LANG, LEVEL, FIELD, TOPIC, FORMAT = range(5)

# ========= LIMIT =========
FREE_LIMIT = 5

def check_limit(user_id):
    cursor.execute("SELECT requests FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO users(user_id, requests) VALUES (?, 0)", (user_id,))
        conn.commit()
        return True

    return row[0] < FREE_LIMIT

def increase_usage(user_id):
    cursor.execute("UPDATE users SET requests = requests + 1 WHERE user_id=?", (user_id,))
    conn.commit()

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    kb = [[
        InlineKeyboardButton("🇱🇾 العربية", callback_data="ar"),
        InlineKeyboardButton("🇬🇧 English", callback_data="en")
    ]]

    await update.message.reply_text(
        "🎓 أكاديمية الباحث\n\n"
        "💡 هذا البوت يساعدك في إعداد بحوث أكاديمية احترافية.\n"
        "📄 يمكنك تحميل النتائج PDF أو Word.\n\n"
        "اختر اللغة:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return LANG

# ========= LANGUAGE =========
async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["lang"] = q.data

    kb = [
        [InlineKeyboardButton("بكالوريوس", callback_data="bachelor")],
        [InlineKeyboardButton("ماجستير", callback_data="master")],
        [InlineKeyboardButton("دكتوراه", callback_data="phd")],
        [InlineKeyboardButton("❌ خروج", callback_data="exit")]
    ]

    await q.edit_message_text("🎓 اختر المستوى:", reply_markup=InlineKeyboardMarkup(kb))
    return LEVEL

# ========= LEVEL =========
async def set_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["level"] = q.data

    kb = [
        [InlineKeyboardButton("تقنية معلومات", callback_data="IT")],
        [InlineKeyboardButton("هندسة", callback_data="ENG")],
        [InlineKeyboardButton("طب", callback_data="MED")],
        [InlineKeyboardButton("❌ خروج", callback_data="exit")]
    ]

    await q.edit_message_text("📚 اختر التخصص:", reply_markup=InlineKeyboardMarkup(kb))
    return FIELD

# ========= FIELD =========
async def set_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["field"] = q.data

    await q.edit_message_text("✍️ اكتب موضوعك:")
    return TOPIC

# ========= TOPIC =========
async def topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if not check_limit(user_id):
        await update.message.reply_text("❌ انتهت المحاولات المجانية اليوم")
        return ConversationHandler.END

    context.user_data["topic"] = update.message.text

    kb = [
        [InlineKeyboardButton("📄 PDF", callback_data="pdf")],
        [InlineKeyboardButton("📝 Word", callback_data="doc")],
        [InlineKeyboardButton("❌ خروج", callback_data="exit")]
    ]

    await update.message.reply_text("📁 اختر نوع الملف:")
    await update.message.reply_text("اختر:", reply_markup=InlineKeyboardMarkup(kb))

    return FORMAT

# ========= GENERATE =========
async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    format_type = q.data
    topic = context.user_data["topic"]

    await q.edit_message_text("⏳ جاري إنشاء الملف...")

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": topic}],
        max_tokens=800
    )

    text = res.choices[0].message.content

    file_path = f"{topic}.pdf" if format_type == "pdf" else f"{topic}.docx"

    # ========= PDF =========
    if format_type == "pdf":
        doc = SimpleDocTemplate(file_path)
        styles = getSampleStyleSheet()
        story = [Paragraph(text, styles["Normal"])]
        doc.build(story)

    # ========= DOC =========
    else:
        document = Document()
        document.add_heading(topic, 0)
        document.add_paragraph(text)
        document.save(file_path)

    increase_usage(str(update.effective_user.id))

    await q.message.reply_document(open(file_path, "rb"))

    return ConversationHandler.END

# ========= EXIT =========
async def exit_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    await q.edit_message_text("👋 تم الخروج\nيمكنك العودة لاحقًا")
    return ConversationHandler.END

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(set_lang)],
            LEVEL: [
                CallbackQueryHandler(set_level),
                CallbackQueryHandler(exit_bot, pattern="exit")
            ],
            FIELD: [
                CallbackQueryHandler(set_field),
                CallbackQueryHandler(exit_bot, pattern="exit")
            ],
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, topic)],
            FORMAT: [
                CallbackQueryHandler(generate),
                CallbackQueryHandler(exit_bot, pattern="exit")
            ],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv)

    print("🚀 BOT RUNNING...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
