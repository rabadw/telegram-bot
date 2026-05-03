import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from openai import OpenAI
from docx import Document

# ===== CONFIG =====
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_URL = "https://t.me/YourChannelName"

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

LANG, MODE, LEVEL, FIELD, TOPIC, FORMAT = range(6)

# ===== HELPERS =====
def split_text(text, size=3500):
    return [text[i:i+size] for i in range(0, len(text), size)]

def detect_mode(text):
    t = text.lower()
    if "تحليل" in t:
        return "analysis"
    if "عرض" in t:
        return "presentation"
    return "research"

# ===== MENUS =====
def lang_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇱🇾 العربية", callback_data="ar"),
         InlineKeyboardButton("🇬🇧 English", callback_data="en")]
    ])

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 خطة بحث", callback_data="research")],
        [InlineKeyboardButton("📈 تحليل", callback_data="analysis")],
        [InlineKeyboardButton("🎤 عرض", callback_data="presentation")]
    ])

def nav():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="back"),
         InlineKeyboardButton("🏠 الرئيسية", callback_data="main")]
    ])

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 أهلاً بك\nاختر اللغة:",
        reply_markup=lang_menu()
    )
    return LANG

# ===== SMART ENTRY =====
async def smart_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # إذا جديد
    if "lang" not in context.user_data:
        return await start(update, context)

    # اختيار mode تلقائي
    if "mode" not in context.user_data:
        context.user_data["mode"] = detect_mode(text)
        await update.message.reply_text("🎓 اختر المستوى:", reply_markup=main_menu())
        return MODE

    # تخصص
    if "field" not in context.user_data:
        context.user_data["field"] = text
        await update.message.reply_text("✍️ اكتب موضوع البحث:")
        return TOPIC

    # الموضوع
    return await generate(update, context)

# ===== LANG =====
async def set_lang(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["lang"] = q.data

    await q.edit_message_text("اختر الخدمة:", reply_markup=main_menu())
    return MODE

# ===== MODE =====
async def set_mode(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["mode"] = q.data

    await q.edit_message_text(
        "🎓 اختر المستوى:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ليسانس", callback_data="bachelor")],
            [InlineKeyboardButton("ماجستير", callback_data="master")]
        ])
    )
    return LEVEL

# ===== LEVEL =====
async def set_level(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["level"] = q.data

    await q.edit_message_text("📚 اكتب تخصصك:")
    return FIELD

# ===== GENERATE =====
async def generate(update, context):
    topic = update.message.text
    context.user_data["topic"] = topic

    await update.message.reply_text("⏳ جاري التوليد...")

    prompt = f"""
اكتب محتوى أكاديمي كامل:

الموضوع: {topic}
التخصص: {context.user_data['field']}
المستوى: {context.user_data['level']}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2500
    )

    text = res.choices[0].message.content
    context.user_data["last"] = text

    for part in split_text(text):
        await update.message.reply_text(part)

    await update.message.reply_text(
        "📌 اختر:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Word", callback_data="doc")],
            [InlineKeyboardButton("🔁 جديد", callback_data="main")]
        ])
    )

    return FORMAT

# ===== FILE =====
async def file_action(update, context):
    q = update.callback_query
    await q.answer()

    doc = Document()
    doc.add_paragraph(context.user_data["last"])
    doc.save("research.docx")

    await q.message.reply_document(open("research.docx", "rb"))

    await q.message.reply_text(
        "🚀 للمزيد:\nانضم للقناة 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 القناة", url=CHANNEL_URL)]
        ])
    )

    return FORMAT

# ===== MAIN NAV =====
async def go_main(update, context):
    q = update.callback_query
    await q.answer()
    return await start(update, context)

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, smart_entry)
        ],
        states={
            LANG: [CallbackQueryHandler(set_lang)],
            MODE: [CallbackQueryHandler(set_mode)],
            LEVEL: [CallbackQueryHandler(set_level)],
            FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, smart_entry)],
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate)],
            FORMAT: [
                CallbackQueryHandler(file_action, pattern="doc"),
                CallbackQueryHandler(go_main, pattern="main")
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)

    print("🚀 BOT FULLY WORKING")
    app.run_polling()

if __name__ == "__main__":
    main()
