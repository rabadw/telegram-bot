import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from openai import OpenAI

# ========= CONFIG =========
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_URL = "https://t.me/YourChannelName"

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

# ========= STATES =========
LANG, MODE, LEVEL, FIELD, TOPIC, FORMAT = range(6)

# ========= UI =========
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 خطة بحث", callback_data="research")],
        [InlineKeyboardButton("📈 تحليل", callback_data="analysis")],
        [InlineKeyboardButton("🎤 عرض تقديمي", callback_data="presentation")],
        [InlineKeyboardButton("❌ خروج", callback_data="exit")]
    ])

def back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main")]
    ])

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "👋 أهلاً بك في أكاديمية الباحث الليبي\n\nاختر الخدمة للبدء 👇"

    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu())

    return MODE

# ========= MODE =========
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

# ========= LEVEL =========
async def set_level(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["level"] = q.data

    await q.edit_message_text(
        "📚 اكتب تخصصك:",
        reply_markup=back_menu()
    )
    return FIELD

# ========= FIELD =========
async def set_field(update, context):
    context.user_data["field"] = update.message.text

    await update.message.reply_text(
        "✍️ اكتب موضوع البحث:",
        reply_markup=back_menu()
    )
    return TOPIC

# ========= GENERATE =========
async def generate(update, context):
    topic = update.message.text
    context.user_data["topic"] = topic

    await update.message.reply_text("⏳ جاري إنشاء المحتوى...")

    prompt = f"""
اكتب بشكل أكاديمي احترافي:

الموضوع: {topic}
المستوى: {context.user_data['level']}
التخصص: {context.user_data['field']}
نوع الطلب: {context.user_data['mode']}
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800
        )

        text = res.choices[0].message.content

    except Exception as e:
        await update.message.reply_text("❌ حدث خطأ، حاول مرة أخرى")
        return ConversationHandler.END

    await update.message.reply_text(text[:1200])

    # زر القناة
    await update.message.reply_text(
        "📌 للحصول على نماذج جاهزة ومحتوى قوي:\nانضم للقناة 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 الانضمام للقناة", url=CHANNEL_URL)]
        ])
    )

    await update.message.reply_text(
        "اختر التالي:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 PDF", callback_data="pdf"),
             InlineKeyboardButton("📝 Word", callback_data="doc")],
            [InlineKeyboardButton("🔁 طلب جديد", callback_data="main")]
        ])
    )

    return FORMAT

# ========= FILE =========
async def file_action(update, context):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text("📄 سيتم إضافة هذه الميزة قريباً")
    return FORMAT

# ========= NAVIGATION =========
async def go_main(update, context):
    return await start(update, context)

async def go_back(update, context):
    return await start(update, context)

async def exit_bot(update, context):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("👋 شكراً لاستخدامك البوت")
    return ConversationHandler.END

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MODE: [
                CallbackQueryHandler(set_mode, pattern="^(research|analysis|presentation)$"),
                CallbackQueryHandler(exit_bot, pattern="exit")
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
                CallbackQueryHandler(file_action, pattern="^(pdf|doc)$"),
                CallbackQueryHandler(go_main, pattern="main")
            ],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv)

    print("🚀 BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
