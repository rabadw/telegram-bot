import os
import logging
import sqlite3

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)

from openai import OpenAI

# PDF + Arabic
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

import arabic_reshaper
from bidi.algorithm import get_display

# DOCX
from docx import Document

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
conn.commit()

FREE_LIMIT = 5

# ========= STATES =========
LANG, MODE, LEVEL, FIELD, TOPIC, FORMAT = range(6)

# ========= HELPERS =========
def check_user(user_id):
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

# ========= PDF =========
def create_pdf(text, filename):
    if os.path.exists("arial.ttf"):
        pdfmetrics.registerFont(TTFont("Arabic", "arial.ttf"))
    else:
        pdfmetrics.registerFont(TTFont("Arabic", "Amiri-Regular.ttf"))

    style = ParagraphStyle(
        name="Arabic",
        fontName="Arabic",
        alignment=TA_RIGHT,
        fontSize=13,
        leading=20
    )

    doc = SimpleDocTemplate(filename)
    story = []

    for line in text.split("\n"):
        reshaped = arabic_reshaper.reshape(line)
        bidi_text = get_display(reshaped)
        story.append(Paragraph(bidi_text, style))
        story.append(Spacer(1, 10))

    doc.build(story)

# ========= DOC =========
def create_doc(text, filename):
    doc = Document()
    doc.add_heading("بحث أكاديمي", 0)
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(filename)

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    kb = [[
        InlineKeyboardButton("🇱🇾 العربية", callback_data="lang_ar"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    ]]

    await update.message.reply_text(
        "🎓 أكاديمية الباحث\n\n"
        "📄 إعداد بحوث احترافية + تحليل + عرض\n\n"
        "اختر اللغة:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return LANG

# ========= LANGUAGE =========
async def set_lang(update, context):
    q = update.callback_query
    await q.answer()

    kb = [
        [InlineKeyboardButton("📊 خطة بحث", callback_data="research")],
        [InlineKeyboardButton("📈 تحليل", callback_data="analysis")],
        [InlineKeyboardButton("🎤 عرض", callback_data="presentation")]
    ]

    await q.edit_message_text("🧠 اختر الخدمة:", reply_markup=InlineKeyboardMarkup(kb))
    return MODE

# ========= MODE =========
async def set_mode(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["mode"] = q.data

    levels = ["بكالوريوس","ماجستير","دكتوراه"]

    kb = [[InlineKeyboardButton(l, callback_data=f"level_{l}")] for l in levels]

    await q.edit_message_text("🎓 اختر المستوى:", reply_markup=InlineKeyboardMarkup(kb))
    return LEVEL

# ========= LEVEL =========
async def set_level(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["level"] = q.data.replace("level_", "")

    fields = ["تقنية معلومات","هندسة","طب","اقتصاد"]

    kb = [[InlineKeyboardButton(f, callback_data=f"field_{f}")] for f in fields]

    await q.edit_message_text("📚 اختر التخصص:", reply_markup=InlineKeyboardMarkup(kb))
    return FIELD

# ========= FIELD =========
async def set_field(update, context):
    q = update.callback_query
    await q.answer()

    await q.edit_message_text("✍️ اكتب موضوعك:")
    return TOPIC

# ========= GENERATE =========
async def generate_text(context):
    prompt = f"""
اكتب محتوى أكاديمي احترافي:

الموضوع: {context.user_data['topic']}
المستوى: {context.user_data['level']}
التخصص: {context.user_data['field']}

يشمل مقدمة وتحليل وخاتمة بأسلوب جامعي
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        max_tokens=1200
    )

    return res.choices[0].message.content

# ========= TOPIC =========
async def topic(update, context):
    user_id = str(update.effective_user.id)

    if not check_user(user_id):
        await update.message.reply_text("❌ انتهت المحاولات المجانية")
        return ConversationHandler.END

    context.user_data["topic"] = update.message.text

    await update.message.reply_text("⏳ جاري التحليل...")

    text = await generate_text(context)

    context.user_data["last_result"] = text

    kb = [
        [InlineKeyboardButton("📄 PDF", callback_data="pdf")],
        [InlineKeyboardButton("📝 Word", callback_data="doc")],
        [InlineKeyboardButton("🔁 طلب جديد", callback_data="new")],
        [InlineKeyboardButton("💬 استفسار إضافي", callback_data="ask")]
    ]

    await update.message.reply_text(text[:1000])
    await update.message.reply_text("اختر:", reply_markup=InlineKeyboardMarkup(kb))

    return FORMAT

# ========= FILE =========
async def generate_file(update, context):
    q = update.callback_query
    await q.answer()

    text = context.user_data.get("last_result", "")

    filename = "output.pdf" if q.data == "pdf" else "output.docx"

    if q.data == "pdf":
        create_pdf(text, filename)
    else:
        create_doc(text, filename)

    increase_usage(str(update.effective_user.id))

    await q.message.reply_document(open(filename, "rb"))

    return FORMAT

# ========= EXTRA CHAT =========
async def extra_chat(update, context):
    user_input = update.message.text

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"أنت مساعد أكاديمي"},
            {"role":"user","content":user_input}
        ],
        max_tokens=500
    )

    await update.message.reply_text(res.choices[0].message.content)

    return FORMAT

# ========= NAV =========
async def new_request(update, context):
    return await start(update, context)

async def ask_more(update, context):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("💬 اكتب سؤالك:")
    return FORMAT

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(set_lang)],
            MODE: [CallbackQueryHandler(set_mode)],
            LEVEL: [CallbackQueryHandler(set_level)],
            FIELD: [CallbackQueryHandler(set_field)],
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, topic)],
            FORMAT: [
                CallbackQueryHandler(generate_file, pattern="^(pdf|doc)$"),
                CallbackQueryHandler(new_request, pattern="new"),
                CallbackQueryHandler(ask_more, pattern="ask"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, extra_chat)
            ],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv)
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
