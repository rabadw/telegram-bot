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

if not TOKEN or not OPENAI_API_KEY:
    raise ValueError("❌ تأكد من TOKEN و OPENAI_API_KEY")

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
TEXT = {
    "ar": {
        "start": "🎓 أكاديمية الباحث الليبي\n\n"
                 "هذا البوت يساعدك في إعداد:\n"
                 "- خطط بحث\n- تحليل أكاديمي\n\nاضغط لاختيار اللغة:",
        "level": "🎓 اختر مستواك الدراسي:",
        "field": "📚 اختر تخصصك:",
        "topic": "✍️ اكتب موضوعك:",
        "processing": "⏳ جاري إعداد محتوى أكاديمي احترافي...",
        "main": "🏠 الرئيسية",
        "back": "🔙 رجوع"
    },
    "en": {
        "start": "🎓 Research Assistant Bot\n\nChoose language:",
        "level": "Choose level:",
        "field": "Choose field:",
        "topic": "Enter topic:",
        "processing": "Processing...",
        "main": "Main",
        "back": "Back"
    }
}

# ========= DATA =========
LEVELS = {
    "ar": ["دبلوم عالي", "ليسانس", "بكالوريوس", "ماجستير", "دكتوراه"],
    "en": ["Diploma", "License", "Bachelor", "Master", "PhD"]
}

FIELDS = {
    "ar": [
        "تقنية معلومات",
        "هندسة",
        "طب",
        "علوم اقتصادية",
        "علوم اجتماعية",
        "علوم إنسانية",
        "إدارة أعمال",
        "قانون"
    ],
    "en": [
        "IT",
        "Engineering",
        "Medicine",
        "Economics",
        "Social Sciences",
        "Humanities",
        "Business",
        "Law"
    ]
}

# ========= HELPERS =========
def get_lang(context):
    return context.user_data.get("lang", "ar")

def nav_buttons(lang):
    return [[InlineKeyboardButton(TEXT[lang]["main"], callback_data="main")]]

def back_main(lang):
    return [
        [InlineKeyboardButton(TEXT[lang]["back"], callback_data="back")],
        [InlineKeyboardButton(TEXT[lang]["main"], callback_data="main")]
    ]

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["lang"] = "ar"

    kb = [[
        InlineKeyboardButton("🇱🇾 العربية", callback_data="lang_ar"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    ]]

    await update.message.reply_text(
        TEXT["ar"]["start"],
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return LANG

# ========= LANGUAGE =========
async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    lang = q.data.split("_")[1]
    context.user_data["lang"] = lang

    kb = [[InlineKeyboardButton(l, callback_data=f"level_{l}")]
          for l in LEVELS[lang]] + nav_buttons(lang)

    await q.edit_message_text(
        TEXT[lang]["level"],
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return LEVEL

# ========= LEVEL =========
async def set_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["level"] = q.data.replace("level_", "")
    lang = get_lang(context)

    kb = [[InlineKeyboardButton(f, callback_data=f"field_{f}")]
          for f in FIELDS[lang]] + back_main(lang)

    await q.edit_message_text(
        TEXT[lang]["field"],
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return FIELD

# ========= FIELD =========
async def set_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["field"] = q.data.replace("field_", "")
    lang = get_lang(context)

    kb = back_main(lang)

    await q.edit_message_text(
        TEXT[lang]["topic"],
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return TOPIC

# ========= TOPIC =========
async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text
    lang = get_lang(context)

    # حفظ
    cursor.execute(
        "INSERT INTO requests (user_id, topic, level, field) VALUES (?, ?, ?, ?)",
        (str(update.effective_user.id),
         topic,
         context.user_data["level"],
         context.user_data["field"])
    )
    conn.commit()

    await update.message.reply_text(TEXT[lang]["processing"])

    prompt = f"""
اكتب بحث أكاديمي احترافي حول:
الموضوع: {topic}
المستوى: {context.user_data['level']}
التخصص: {context.user_data['field']}

يتضمن:
- مقدمة قوية
- مشكلة البحث
- أسئلة البحث
- أهمية البحث
- المنهجية
- خاتمة علمية
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        reply = res.choices[0].message.content
    except Exception as e:
        reply = f"❌ خطأ: {e}"

    kb = [
        [InlineKeyboardButton("🔁 إعادة", callback_data="repeat")],
        [InlineKeyboardButton(TEXT[lang]["main"], callback_data="main")]
    ]

    await update.message.reply_text(reply, reply_markup=InlineKeyboardMarkup(kb))
    return TOPIC

# ========= NAVIGATION =========
async def go_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    return await start(update, context)

async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = get_lang(context)

    kb = [[InlineKeyboardButton(l, callback_data=f"level_{l}")]
          for l in LEVELS[lang]] + nav_buttons(lang)

    await q.edit_message_text(
        TEXT[lang]["level"],
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return LEVEL

async def repeat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = get_lang(context)

    await q.message.reply_text(TEXT[lang]["topic"])
    return TOPIC

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(set_lang)],
            LEVEL: [
                CallbackQueryHandler(set_level, pattern="^level_"),
                CallbackQueryHandler(go_main, pattern="^main$")
            ],
            FIELD: [
                CallbackQueryHandler(set_field, pattern="^field_"),
                CallbackQueryHandler(go_back, pattern="^back$"),
                CallbackQueryHandler(go_main, pattern="^main$")
            ],
            TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic),
                CallbackQueryHandler(go_back, pattern="^back$"),
                CallbackQueryHandler(go_main, pattern="^main$"),
                CallbackQueryHandler(repeat, pattern="^repeat$")
            ],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv)

    print("🚀 BOT RUNNING...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
