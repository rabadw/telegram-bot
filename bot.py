import os
import logging
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from openai import OpenAI

# PDF & DOC
from docx import Document
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

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

FREE_LIMIT = 5

# ========= STATES =========
LANG, LEVEL, FIELD, TOPIC, FORMAT = range(5)

# ========= HELPERS =========
def get_lang(ctx):
    return ctx.user_data.get("lang", "ar")

def check_limit(user_id):
    cursor.execute("SELECT requests FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users VALUES (?,0)", (user_id,))
        conn.commit()
        return True
    return row[0] < FREE_LIMIT

def increase_usage(user_id):
    cursor.execute("UPDATE users SET requests=requests+1 WHERE user_id=?", (user_id,))
    conn.commit()

# ========= FILE GENERATION =========
def create_pdf(text, filename):
    doc = SimpleDocTemplate(filename)
    style = ParagraphStyle(name="Arabic", alignment=TA_RIGHT, fontSize=12, leading=18)
    story = []
    for line in text.split("\n"):
        story.append(Paragraph(line, style))
        story.append(Spacer(1, 10))
    doc.build(story)

def create_doc(text, filename):
    doc = Document()
    doc.add_heading("بحث أكاديمي", 0)
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(filename)

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["lang"] = "ar"

    kb = [[
        InlineKeyboardButton("🇱🇾 العربية", callback_data="lang_ar"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    ]]

    await update.message.reply_text(
        "🎓 أكاديمية الباحث\n\n"
        "يساعدك هذا البوت في إعداد بحوث أكاديمية احترافية\n"
        "📄 يمكنك تحميل النتائج PDF أو Word\n\nاختر اللغة:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return LANG

# ========= LANGUAGE =========
async def set_lang(update, context):
    q = update.callback_query
    await q.answer()

    lang = q.data.split("_")[1]
    context.user_data["lang"] = lang

    levels = ["دبلوم عالي","ليسانس","بكالوريوس","ماجستير","دكتوراه"]

    kb = [[InlineKeyboardButton(l, callback_data=f"level_{l}")] for l in levels]
    kb.append([InlineKeyboardButton("❌ خروج", callback_data="exit")])

    await q.edit_message_text("🎓 اختر المستوى:", reply_markup=InlineKeyboardMarkup(kb))
    return LEVEL

# ========= LEVEL =========
async def set_level(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["level"] = q.data.replace("level_","")

    fields = ["تقنية معلومات","هندسة","طب","اقتصاد","قانون","إدارة"]

    kb = [[InlineKeyboardButton(f, callback_data=f"field_{f}")] for f in fields]
    kb.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back")])
    kb.append([InlineKeyboardButton("❌ خروج", callback_data="exit")])

    await q.edit_message_text("📚 اختر التخصص:", reply_markup=InlineKeyboardMarkup(kb))
    return FIELD

# ========= FIELD =========
async def set_field(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["field"] = q.data.replace("field_","")

    await q.edit_message_text("✍️ اكتب موضوعك:")
    return TOPIC

# ========= TOPIC =========
async def topic(update, context):
    user_id = str(update.effective_user.id)

    if not check_limit(user_id):
        await update.message.reply_text("❌ انتهت المحاولات المجانية")
        return ConversationHandler.END

    context.user_data["topic"] = update.message.text

    kb = [
        [InlineKeyboardButton("📄 PDF", callback_data="pdf")],
        [InlineKeyboardButton("📝 Word", callback_data="doc")],
        [InlineKeyboardButton("❌ خروج", callback_data="exit")]
    ]

    await update.message.reply_text("📁 اختر نوع الملف:", reply_markup=InlineKeyboardMarkup(kb))
    return FORMAT

# ========= GENERATE =========
async def generate(update, context):
    q = update.callback_query
    await q.answer()

    await q.edit_message_text("⏳ جاري التحليل...")

    prompt = f"""
اكتب محتوى أكاديمي احترافي:
الموضوع: {context.user_data['topic']}
المستوى: {context.user_data['level']}
التخصص: {context.user_data['field']}

يشمل:
مقدمة، مشكلة، أسئلة، منهجية، خاتمة
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        max_tokens=900
    )

    text = res.choices[0].message.content

    filename = "output.pdf" if q.data=="pdf" else "output.docx"

    if q.data=="pdf":
        create_pdf(text, filename)
    else:
        create_doc(text, filename)

    increase_usage(str(update.effective_user.id))

    await q.message.reply_document(open(filename,"rb"))

    return ConversationHandler.END

# ========= NAV =========
async def exit_bot(update, context):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("👋 تم الخروج")
    return ConversationHandler.END

async def back(update, context):
    return await start(update, context)

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
                CallbackQueryHandler(back, pattern="back"),
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
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
