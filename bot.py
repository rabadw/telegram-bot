import os
import logging
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from openai import OpenAI

# PDF + Arabic support
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

if not TOKEN or not OPENAI_API_KEY:
    raise ValueError("❌ تأكد من إعداد TOKEN و OPENAI_API_KEY في المتغيرات البيئية")

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
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    topic TEXT,
    level TEXT,
    field TEXT,
    mode TEXT
)
""")

conn.commit()

FREE_LIMIT = 5

# ========= STATES =========
LANG, MODE, LEVEL, FIELD, TOPIC, FORMAT = range(6)

# ========= HELPERS =========
def get_lang(ctx):
    return ctx.user_data.get("lang", "ar")

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

def nav_main(lang):
    return [[InlineKeyboardButton("🏠 الرئيسية", callback_data="main")]]

def nav_back_main(lang):
    return [
        [InlineKeyboardButton("⬅️ رجوع", callback_data="back")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main")]
    ]

# ========= FONT HANDLING =========
def register_font():
    # يحاول Arial أولاً ثم Amiri
    if os.path.exists("arial.ttf"):
        pdfmetrics.registerFont(TTFont("Arabic", "arial.ttf"))
        return "Arabic"
    elif os.path.exists("Amiri-Regular.ttf"):
        pdfmetrics.registerFont(TTFont("Arabic", "Amiri-Regular.ttf"))
        return "Arabic"
    else:
        # fallback (لن يدعم العربية بشكل صحيح)
        return "Helvetica"

# ========= PDF =========
def create_pdf(text, filename):
    font_name = register_font()

    doc = SimpleDocTemplate(filename)
    style = ParagraphStyle(
        name="ArabicStyle",
        fontName=font_name,
        alignment=TA_RIGHT,
        fontSize=13,
        leading=20
    )

    story = []

    for line in text.split("\n"):
        reshaped = arabic_reshaper.reshape(line)
        bidi_text = get_display(reshaped)
        story.append(Paragraph(bidi_text, style))
        story.append(Spacer(1, 10))

    doc.build(story)

# ========= DOCX =========
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
        "💡 إعداد بحوث أكاديمية احترافية\n"
        "📄 تحميل PDF و Word\n\n"
        "اختر اللغة:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return LANG

# ========= LANGUAGE =========
async def set_lang(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["lang"] = q.data.split("_")[1]

    kb = [
        [InlineKeyboardButton("📊 خطة بحث", callback_data="research")],
        [InlineKeyboardButton("📈 تحليل", callback_data="analysis")],
        [InlineKeyboardButton("🎤 عرض", callback_data="presentation")],
        [InlineKeyboardButton("❌ خروج", callback_data="exit")]
    ]

    await q.edit_message_text("🧠 اختر نوع الخدمة:", reply_markup=InlineKeyboardMarkup(kb))
    return MODE

# ========= MODE =========
async def set_mode(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["mode"] = q.data

    levels = ["دبلوم عالي","ليسانس","بكالوريوس","ماجستير","دكتوراه"]
    kb = [[InlineKeyboardButton(l, callback_data=f"level_{l}")] for l in levels]
    kb += nav_back_main(get_lang(context))

    await q.edit_message_text("🎓 اختر المستوى:", reply_markup=InlineKeyboardMarkup(kb))
    return LEVEL

# ========= LEVEL =========
async def set_level(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["level"] = q.data.replace("level_", "")

    fields = ["تقنية معلومات","هندسة","طب","اقتصاد","قانون","إدارة"]
    kb = [[InlineKeyboardButton(f, callback_data=f"field_{f}")] for f in fields]
    kb += nav_back_main(get_lang(context))

    await q.edit_message_text("📚 اختر التخصص:", reply_markup=InlineKeyboardMarkup(kb))
    return FIELD

# ========= FIELD =========
async def set_field(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["field"] = q.data.replace("field_", "")

    await q.edit_message_text("✍️ اكتب موضوعك:")
    return TOPIC

# ========= TOPIC =========
async def topic(update, context):
    user_id = str(update.effective_user.id)

    if not check_user(user_id):
        await update.message.reply_text("❌ انتهت الاستخدامات المجانية")
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

    await q.edit_message_text("⏳ جاري إنشاء المحتوى...")

    mode = context.user_data["mode"]

    if mode == "research":
        instruction = "اكتب خطة بحث أكاديمية احترافية"
    elif mode == "analysis":
        instruction = "اكتب تحليل أكاديمي معمق"
    else:
        instruction = "اكتب عرض تقديمي منظم"

    prompt = f"""
{instruction}

الموضوع: {context.user_data['topic']}
المستوى: {context.user_data['level']}
التخصص: {context.user_data['field']}

بأسلوب أكاديمي يشبه رسائل الماجستير
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        max_tokens=1200
    )

    text = res.choices[0].message.content

    filename = "output.pdf" if q.data == "pdf" else "output.docx"

    if q.data == "pdf":
        create_pdf(text, filename)
    else:
        create_doc(text, filename)

    increase_usage(str(update.effective_user.id))

    await q.message.reply_document(open(filename, "rb"))

    return ConversationHandler.END

# ========= NAV =========
async def go_main(update, context):
    return await start(update, context)

async def go_back(update, context):
    return await start(update, context)

async def exit_bot(update, context):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("👋 تم الخروج")
    return ConversationHandler.END

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(set_lang)],
            MODE: [
                CallbackQueryHandler(set_mode, pattern="^(research|analysis|presentation)$"),
                CallbackQueryHandler(exit_bot, pattern="exit")
            ],
            LEVEL: [
                CallbackQueryHandler(set_level, pattern="^level_"),
                CallbackQueryHandler(go_main, pattern="main"),
                CallbackQueryHandler(go_back, pattern="back")
            ],
            FIELD: [
                CallbackQueryHandler(set_field, pattern="^field_"),
                CallbackQueryHandler(go_main, pattern="main"),
                CallbackQueryHandler(go_back, pattern="back")
            ],
            TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, topic)
            ],
            FORMAT: [
                CallbackQueryHandler(generate, pattern="^(pdf|doc)$"),
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
