import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from openai import OpenAI

# ========= CONFIG =========
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TOKEN:
    raise ValueError("❌ TOKEN missing")

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY missing")

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

# ========= STATES =========
LANG, WORK, INPUT = range(3)

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[
        InlineKeyboardButton("🇱🇾 العربية", callback_data="ar"),
        InlineKeyboardButton("🇬🇧 English", callback_data="en")
    ]]
    await update.message.reply_text("🌍 اختر اللغة:", reply_markup=InlineKeyboardMarkup(kb))
    return LANG

# ========= LANGUAGE =========
async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["lang"] = q.data

    kb = [[
        InlineKeyboardButton("خطة بحث", callback_data="plan"),
        InlineKeyboardButton("تحليل", callback_data="analysis")
    ]]

    await q.edit_message_text("اختر نوع العمل:", reply_markup=InlineKeyboardMarkup(kb))
    return WORK

# ========= WORK =========
async def set_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["work"] = q.data

    await q.edit_message_text("✍️ اكتب موضوعك:")
    return INPUT

# ========= INPUT =========
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text

    await update.message.reply_text("⚡ جاري التحليل...")

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": topic}],
            max_tokens=300
        )
        reply = res.choices[0].message.content
    except Exception as e:
        reply = f"Error: {e}"

    await update.message.reply_text(reply)
    return INPUT

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(set_lang)],
            WORK: [CallbackQueryHandler(set_work)],
            INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input)],
        },
        fallbacks=[]
    )

    app.add_handler(conv)

    print("🚀 BOT RUNNING...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()