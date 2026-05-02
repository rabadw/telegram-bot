import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from openai import OpenAI

# ===== CONFIG =====
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_URL = "https://t.me/YourChannelName"

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

# ===== STATES =====
MODE, LEVEL, FIELD, TOPIC = range(4)

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "👋 أهلاً بك في أكاديمية الباحث الليبي\n\nاختر الخدمة 👇"

    keyboard = [
        [InlineKeyboardButton("📊 خطة بحث", callback_data="research")],
        [InlineKeyboardButton("📈 تحليل", callback_data="analysis")],
        [InlineKeyboardButton("🎤 عرض", callback_data="presentation")]
    ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return MODE

# ===== MODE =====
async def set_mode(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["mode"] = q.data

    keyboard = [
        [InlineKeyboardButton("ليسانس", callback_data="bachelor")],
        [InlineKeyboardButton("دبلوم عالي", callback_data="diploma")],
        [InlineKeyboardButton("ماجستير", callback_data="master")],
        [InlineKeyboardButton("دكتوراه", callback_data="phd")]
    ]

    await q.edit_message_text("🎓 اختر المستوى:", reply_markup=InlineKeyboardMarkup(keyboard))
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

    await update.message.reply_text("⏳ جاري التحليل...")

    prompt = f"""
اكتب محتوى أكاديمي احترافي:

الموضوع: {topic}
المستوى: {context.user_data['level']}
التخصص: {context.user_data['field']}
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700
        )

        text = res.choices[0].message.content

    except Exception as e:
        await update.message.reply_text("❌ خطأ في التوليد")
        return ConversationHandler.END

    await update.message.reply_text(text[:1200])

    await update.message.reply_text(
        "📌 تابع القناة للمزيد 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 القناة", url=CHANNEL_URL)]
        ])
    )

    return ConversationHandler.END

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
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)

    print("🚀 BOT WORKING...")
    app.run_polling()

if __name__ == "__main__":
    main()
