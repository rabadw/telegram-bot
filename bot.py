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

# ========= DATABASE =========
conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()
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
LANG, LEVEL, FIELD, TOPIC = range(4)

# ========= TEXT =========
def t(lang, key):
    texts = {
        "ar": {
            "start": "🎓 مرحباً بك في أكاديمية الباحث\n\nهذا البوت يساعدك في:\n- إعداد خطة بحث\n- تحليل موضوع\n\nاضغط للبدء:",
            "choose_lang": "🌍 اختر اللغة:",
            "choose_level": "🎓 اختر المستوى:",
            "choose_field": "📚 اختر التخصص:",
            "enter_topic": "✍️ اكتب موضوعك:",
            "processing": "⏳ جاري إعداد محتوى أكاديمي احترافي...",
            "back": "⬅️ رجوع",
            "main": "🏠 الرئيسية"
        },
        "en": {
            "start": "🎓 Research Assistant Bot\n\nHelps you with:\n- Research plans\n- Analysis\n\nStart below:",
            "choose_lang": "Choose language:",
            "choose_level": "Choose level:",
            "choose_field": "Choose field:",
            "enter_topic": "Enter topic:",
            "processing": "Processing...",
            "back": "Back",
            "main": "Main"
        }
    }
    return texts.get(lang, texts["ar"])[key]

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lang"] = "ar"  # افتراضي عربي

    kb = [[
        InlineKeyboardButton("🇱🇾 العربية", callback_data="ar"),
        InlineKeyboardButton("🇬🇧 English", callback_data="en")
    ]]

    await update.message.reply_text(
        t("ar", "start"),
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return LANG

# ========= LANGUAGE =========
async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["lang"] = q.data
    lang = q.data

    kb = [
        [InlineKeyboardButton("بكالوريوس", callback_data="bachelor")],
        [InlineKeyboardButton("ماجستير", callback_data="master")],
        [InlineKeyboardButton("دكتوراه", callback_data="phd")]
    ]

    await q.edit_message_text(
        t(lang, "choose_level"),
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return LEVEL

# ========= LEVEL =========
async def set_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["level"] = q.data
    lang = context.user_data["lang"]

    kb = [
        [InlineKeyboardButton("تقنية معلومات", callback_data="IT")],
        [InlineKeyboardButton("هندسة", callback_data="Engineering")],
        [InlineKeyboardButton("علوم اجتماعية", callback_data="Social")],
        [InlineKeyboardButton("علوم إنسانية", callback_data="Humanities")],
    ]

    await q.edit_message_text(
        t(lang, "choose_field"),
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return FIELD

# ========= FIELD =========
async def set_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["field"] = q.data
    lang = context.user_data["lang"]

    await q.edit_message_text(t(lang, "enter_topic"))
    return TOPIC

# ========= TOPIC =========
async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text
    lang = context.user_data["lang"]
    level = context.user_data["level"]
    field = context.user_data["field"]

    # حفظ في قاعدة البيانات
    cursor.execute(
        "INSERT INTO requests (user_id, topic, level, field) VALUES (?, ?, ?, ?)",
        (str(update.effective_user.id), topic, level, field)
    )
    conn.commit()

    await update.message.reply_text(t(lang, "processing"))

    prompt = f"""
    اكتب محتوى أكاديمي احترافي حول الموضوع التالي:
    الموضوع: {topic}
    المستوى: {level}
    التخصص: {field}

    يجب أن يحتوي:
    - مقدمة
    - مشكلة البحث
    - أسئلة البحث
    - المنهجية
    - خاتمة
    """

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800
        )
        reply = res.choices[0].message.content
    except Exception as e:
        reply = f"Error: {e}"

    kb = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="restart")]]

    await update.message.reply_text(reply, reply_markup=InlineKeyboardMarkup(kb))

    return ConversationHandler.END

# ========= RESTART =========
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    return await start(q, context)

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(set_lang)],
            LEVEL: [CallbackQueryHandler(set_level)],
            FIELD: [CallbackQueryHandler(set_field)],
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic)],
        },
        fallbacks=[CallbackQueryHandler(restart, pattern="restart")]
    )

    app.add_handler(conv)

    print("🚀 BOT RUNNING...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
