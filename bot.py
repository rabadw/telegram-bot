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

MODE, LEVEL, FIELD, TOPIC, FORMAT = range(5)

# ===== HELPERS =====
def split_text(text, size=3500):
    return [text[i:i+size] for i in range(0, len(text), size)]

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك في أكاديمية الباحث الليبي\n\nاختر الخدمة 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 خطة بحث", callback_data="research")],
            [InlineKeyboardButton("📈 تحليل", callback_data="analysis")],
            [InlineKeyboardButton("🎤 عرض", callback_data="presentation")]
        ])
    )
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

# ===== FIELD =====
async def set_field(update, context):
    context.user_data["field"] = update.message.text
    await update.message.reply_text("✍️ اكتب موضوع البحث:")
    return TOPIC

# ===== GENERATE =====
async def generate(update, context):
    topic = update.message.text

    await update.message.reply_text("⏳ جاري إنشاء البحث الكامل...")

    prompt = f"""
اكتب بحث أكاديمي كامل ومفصل جداً يتضمن:

1. عنوان البحث
2. مقدمة قوية
3. مشكلة البحث
4. الأهداف
5. الأهمية
6. المنهجية
7. الدراسات السابقة
8. التحليل
9. النتائج
10. التوصيات
11. المراجع

بأسلوب احترافي أكاديمي واضح

الموضوع: {topic}
التخصص: {context.user_data['field']}
المستوى: {context.user_data['level']}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000
    )

    text = res.choices[0].message.content
    context.user_data["last"] = text

    # تقسيم النص
    parts = split_text(text)

    for part in parts:
        await update.message.reply_text(part)

    await update.message.reply_text(
        "📌 اختر طريقة التحميل:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Word", callback_data="doc")],
            [InlineKeyboardButton("🔁 طلب جديد", callback_data="restart")]
        ])
    )

    return FORMAT

# ===== FILE =====
async def file_action(update, context):
    q = update.callback_query
    await q.answer()

    doc = Document()
    doc.add_paragraph(context.user_data["last"])

    file_path = "research.docx"
    doc.save(file_path)

    await q.message.reply_document(document=open(file_path, "rb"))

    return FORMAT

# ===== RESTART =====
async def restart(update, context):
    q = update.callback_query
    await q.answer()
    return await start(update, context)

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MODE: [CallbackQueryHandler(set_mode)],
            LEVEL: [CallbackQueryHandler(set_level)],
            FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_field)],
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate)],
            FORMAT: [
                CallbackQueryHandler(file_action, pattern="doc"),
                CallbackQueryHandler(restart, pattern="restart")
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)

    print("🚀 BOT READY")
    app.run_polling()

if __name__ == "__main__":
    main()
