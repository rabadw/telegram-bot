# =========================================
# Libyan Research Academy Bot - FINAL CLEAN
# =========================================

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
    raise ValueError("❌ TOKEN not found")

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY not found")

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

# ========= STATES =========
LANG, STAGE, SPEC, WORK, INPUT = range(5)

# ========= TEXT =========
TEXT = {
    "ar": {
        "lang": "🌍 اختر اللغة:",
        "start": "🎓 أكاديمية الباحث الليبي\n\nمرحباً بك 🤖",
        "start_btn": "🚀 ابدأ",
        "stage": "📊 اختر مرحلتك:",
        "spec": "📚 اختر تخصصك:",
        "work": "🧩 اختر نوع العمل:",
        "input": "✍️ اكتب موضوعك:",
        "hint": "💡 مثال: تأثير الذكاء الاصطناعي",
        "loading": "⚡ جاري التحليل...",
        "result": "🤖 النتيجة:",
        "back": "🔙 رجوع",
        "main": "🏠 الرئيسية",
        "repeat": "🔁 إعادة",
        "new": "🆕 جديد"
    },
    "en": {
        "lang": "🌍 Choose language:",
        "start": "🎓 Welcome",
        "start_btn": "🚀 Start",
        "stage": "Select stage:",
        "spec": "Select field:",
        "work": "Select work:",
        "input": "Enter topic:",
        "hint": "Example: AI in education",
        "loading": "Processing...",
        "result": "Result:",
        "back": "Back",
        "main": "Main",
        "repeat": "Repeat",
        "new": "New"
    }
}

# ========= OPTIONS =========
STAGES = {
    "ar": ["دبلوم عالي", "ليسانس", "بكالوريوس", "ماجستير", "دكتوراه"],
    "en": ["Diploma", "License", "Bachelor", "Master", "PhD"]
}

SPECS = {
    "ar": ["علوم إنسانية", "علوم اجتماعية", "هندسة", "تقنية معلومات"],
    "en": ["Humanities", "Social Sciences", "Engineering", "IT"]
}

WORKS = {
    "ar": ["خطة بحث", "تحليل", "عرض", "مراجعة أدبية"],
    "en": ["Plan", "Analysis", "Presentation", "Literature"]
}

# ========= HELPERS =========
def t(context):
    return TEXT[context.user_data.get("lang", "ar")]

def menu(items, prefix):
    return [[InlineKeyboardButton(x, callback_data=f"{prefix}_{x}")] for x in items]

def nav(context):
    T = t(context)
    return [[
        InlineKeyboardButton(T["main"], callback_data="main")
    ]]

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[
        InlineKeyboardButton("🇱🇾 العربية", callback_data="lang_ar"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    ]]
    await update.message.reply_text(TEXT["ar"]["lang"], reply_markup=InlineKeyboardMarkup(kb))
    return LANG

# ========= LANGUAGE =========
async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data.clear()
    context.user_data["lang"] = q.data.split("_")[1]

    T = t(context)
    kb = [[InlineKeyboardButton(T["start_btn"], callback_data="go")]]

    await q.edit_message_text(T["start"], reply_markup=InlineKeyboardMarkup(kb))
    return STAGE

# ========= STAGE =========
async def stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    T = t(context)

    kb = menu(STAGES[context.user_data["lang"]], "stage") + nav(context)
    await q.edit_message_text(T["stage"], reply_markup=InlineKeyboardMarkup(kb))
    return SPEC

# ========= SPEC =========
async def spec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["stage"] = q.data

    T = t(context)
    kb = menu(SPECS[context.user_data["lang"]], "spec") + nav(context)
    await q.edit_message_text(T["spec"], reply_markup=InlineKeyboardMarkup(kb))
    return WORK

# ========= WORK =========
async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["spec"] = q.data

    T = t(context)
    kb = menu(WORKS[context.user_data["lang"]], "work") + nav(context)
    await q.edit_message_text(T["work"], reply_markup=InlineKeyboardMarkup(kb))
    return INPUT

# ========= INPUT =========
async def input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["topic"] = update.message.text
    T = t(context)

    await update.message.reply_text(T["loading"])

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Topic: {context.user_data['topic']}"
            }],
            max_tokens=400
        )
        result = res.choices[0].message.content
    except Exception as e:
        result = f"Error: {e}"

    kb = [[
        InlineKeyboardButton(T["repeat"], callback_data="repeat"),
        InlineKeyboardButton(T["new"], callback_data="new")
    ]]

    await update.message.reply_text(f"{T['result']}\n\n{result}", reply_markup=InlineKeyboardMarkup(kb))
    return INPUT

# ========= NAV =========
async def go_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    return await start(update, context)

async def repeat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    T = t(context)
    await q.message.reply_text(T["input"])
    return INPUT

async def new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await go_main(update, context)

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(set_lang)],
            STAGE: [CallbackQueryHandler(stage, pattern="^go$")],
            SPEC: [CallbackQueryHandler(spec, pattern="^stage_")],
            WORK: [CallbackQueryHandler(work, pattern="^spec_")],
            INPUT: [
                CallbackQueryHandler(go_main, pattern="^main$"),
                CallbackQueryHandler(repeat, pattern="^repeat$"),
                CallbackQueryHandler(new, pattern="^new$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_handler)
            ],
        },
        fallbacks=[]
    )

    app.add_handler(conv)

    print("🚀 BOT STARTED...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()