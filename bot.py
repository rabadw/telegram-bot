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

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 خطة بحث", callback_data="research")],
        [InlineKeyboardButton("📈 تحليل", callback_data="analysis")],
        [InlineKeyboardButton("🎤 عرض تقديمي", callback_data="presentation")]
    ])

def nav_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main")]
    ])

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "👋 أهلاً بك في أكاديمية الباحث الليبي\n\nاختر الخدمة 👇"

    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu())

    return MODE

# ===== AUTO START =====
async def auto_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        return await start(update, context)

# ===== MODE =====
async def set_mode(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["mode"] = q.data

    await q.edit_message_text(
        "🎓 اختر المستوى:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ليسانس", callback_data="bachelor")],
            [InlineKeyboardButton("دبلوم عالي", callback_data="diploma")],
            [InlineKeyboardButton("ماجستير", callback_data="master")],
            [InlineKeyboardButton("دكتوراه", callback_data="phd")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ])
    )
    return LEVEL

# ===== LEVEL =====
async def set_level(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["level"] = q.data

    await q.edit_message_text("📚 اكتب تخصصك:", reply_markup=nav_menu())
    return FIELD

# ===== FIELD =====
async def set_field(update, context):
    context.user_data["field"] = update.message.text

    await update.message.reply_text("✍️ اكتب موضوع البحث:", reply_markup=nav_menu())
    return TOPIC

# ===== GENERATE =====
async def generate(update, context):
    topic = update.message.text
    context.user_data["topic"] = topic

    await update.message.reply_text("⏳ جاري إعداد البحث الكامل...")

    prompt = f"""
اكتب بحث أكاديمي احترافي شامل يتضمن:
عنوان + مقدمة + مشكلة + أهداف + أهمية + منهجية + دراسات سابقة + تحليل + نتائج + توصيات + مراجع

الموضوع: {topic}
التخصص: {context.user_data['field']}
المستوى: {context.user_data['level']}
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2500
        )

        text = res.choices[0].message.content
        context.user_data["last"] = text

    except Exception as e:
        await update.message.reply_text("❌ حدث خطأ أثناء التوليد")
        return ConversationHandler.END

    for part in split_text(text):
        await update.message.reply_text(part)

    await update.message.reply_text(
        "📌 اختر ما تريد:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 تحميل Word", callback_data="doc")],
            [InlineKeyboardButton("🔁 طلب جديد", callback_data="main")]
        ])
    )

    return FORMAT

# ===== FILE =====
async def file_action(update, context):
    q = update.callback_query
    await q.answer()

    doc = Document()
    doc.add_paragraph(context.user_data.get("last", "لا يوجد محتوى"))

    file_path = "research.docx"
    doc.save(file_path)

    await q.message.reply_document(open(file_path, "rb"))

    await q.message.reply_text(
        "🎯 هل تريد تطوير بحثك أكثر؟\nانضم للقناة 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 القناة", url=CHANNEL_URL)]
        ])
    )

    return FORMAT

# ===== NAVIGATION =====
async def go_main(update, context):
    return await start(update, context)

async def go_back(update, context):
    return await start(update, context)

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # auto start لأي رسالة
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_start), group=0)

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MODE: [
                CallbackQueryHandler(set_mode),
            ],
            LEVEL: [
                CallbackQueryHandler(set_level),
                CallbackQueryHandler(go_back, pattern="back")
            ],
            FIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_field)
            ],
            TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, generate)
            ],
            FORMAT: [
                CallbackQueryHandler(file_action, pattern="doc"),
                CallbackQueryHandler(go_main, pattern="main")
            ],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv)

    print("🚀 BOT WORKING PERFECTLY")
    app.run_polling()

if __name__ == "__main__":
    main()
