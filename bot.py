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

# ===== STATES =====
LANG, MODE, LEVEL, FIELD, TOPIC, FORMAT = range(6)

# ===== HELPERS =====
def split_text(text, size=3500):
    return [text[i:i+size] for i in range(0, len(text), size)]

# ===== MENUS =====
def lang_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇱🇾 العربية", callback_data="lang_ar"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ])

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 خطة بحث", callback_data="mode_research")],
        [InlineKeyboardButton("📈 تحليل", callback_data="mode_analysis")],
        [InlineKeyboardButton("🎤 عرض تقديمي", callback_data="mode_presentation")]
    ])

def level_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ليسانس", callback_data="level_bachelor")],
        [InlineKeyboardButton("ماجستير", callback_data="level_master")],
        [InlineKeyboardButton("دكتوراه", callback_data="level_phd")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main")]
    ])

def nav_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="back"),
         InlineKeyboardButton("🏠 الرئيسية", callback_data="main")]
    ])

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "👋 أهلاً بك في أكاديمية الباحث الليبي\n\nاختر اللغة:",
        reply_markup=lang_menu()
    )
    return LANG

# ===== AUTO ENTRY =====
async def auto_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data:
        return await start(update, context)

    if "field" not in context.user_data:
        context.user_data["field"] = update.message.text
        await update.message.reply_text("✍️ اكتب موضوع البحث:", reply_markup=nav_menu())
        return TOPIC

    return await generate(update, context)

# ===== LANGUAGE =====
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

    await q.edit_message_text("🎓 اختر المستوى:", reply_markup=level_menu())
    return LEVEL

# ===== LEVEL =====
async def set_level(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["level"] = q.data

    await q.edit_message_text("📚 اكتب تخصصك:", reply_markup=nav_menu())
    return FIELD

# ===== GENERATE =====
async def generate(update, context):
    topic = update.message.text
    context.user_data["topic"] = topic

    await update.message.reply_text("⏳ جاري إعداد البحث...")

    prompt = f"""
اكتب بحث أكاديمي احترافي كامل يتضمن:
عنوان + مقدمة + مشكلة + أهداف + أهمية + منهجية + تحليل + نتائج + توصيات + مراجع

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

    except Exception:
        await update.message.reply_text("❌ حدث خطأ، حاول مرة أخرى")
        return ConversationHandler.END

    for part in split_text(text):
        await update.message.reply_text(part)

    await update.message.reply_text(
        "📌 اختر التالي:",
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
    doc.save("research.docx")

    await q.message.reply_document(open("research.docx", "rb"))

    await q.message.reply_text(
        "🚀 للمزيد من النماذج الاحترافية:\nانضم للقناة 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 القناة", url=CHANNEL_URL)]
        ])
    )

    return FORMAT

# ===== NAVIGATION =====
async def go_main(update, context):
    q = update.callback_query
    await q.answer()
    return await start(update, context)

async def go_back(update, context):
    q = update.callback_query
    await q.answer()

    await q.edit_message_text("🎓 اختر المستوى:", reply_markup=level_menu())
    return LEVEL

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, auto_entry)
        ],
        states={
            LANG: [CallbackQueryHandler(set_lang)],
            MODE: [CallbackQueryHandler(set_mode)],
            LEVEL: [CallbackQueryHandler(set_level), CallbackQueryHandler(go_main, pattern="main")],
            FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, auto_entry)],
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate)],
            FORMAT: [
                CallbackQueryHandler(file_action, pattern="doc"),
                CallbackQueryHandler(go_main, pattern="main")
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)

    print("🚀 BOT READY & STABLE")
    app.run_polling()

if __name__ == "__main__":
    main()
