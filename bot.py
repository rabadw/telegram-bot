# =========================================
# Libyan Research Academy Bot - PRO CLEAN
# =========================================

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from openai import OpenAI

# ========= CONFIG =========
import os
from openai import OpenAI
import logging

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

# ========= STATES =========
LANG, STAGE, SPEC, WORK, INPUT = range(5)

# ========= TEXTS =========
TEXTS = {
    "ar": {
        "choose_lang": "🌍 اختر اللغة:",
        "start": "🎓 أكاديمية الباحث الليبي\n\nمرحباً بك 🤖",
        "start_btn": "🚀 ابدأ الآن",
        "stage": "📊 اختر مرحلتك الدراسية:",
        "spec": "📚 اختر تخصصك:",
        "work": "🧩 اختر نوع العمل:",
        "input": "✍️ اكتب موضوعك:",
        "input_hint": "💡 مثال: تأثير الذكاء الاصطناعي على التعليم",
        "loading": "⚡ يتم تجهيز الرد...",
        "result": "🤖 التوجيه الأكاديمي:",
        "back": "🔙 رجوع",
        "main": "🏠 الرئيسية",
        "skip": "⏭ تخطي",
        "repeat": "🔁 إعادة بنفس الإعدادات",
        "new": "🆕 موضوع جديد"
    },
    "en": {
        "choose_lang": "🌍 Choose language:",
        "start": "🎓 Libyan Research Academy\n\nWelcome 🤖",
        "start_btn": "🚀 Start",
        "stage": "📊 Select your stage:",
        "spec": "📚 Select your field:",
        "work": "🧩 Select work type:",
        "input": "✍️ Enter your topic:",
        "input_hint": "💡 Example: AI in education",
        "loading": "⚡ Preparing response...",
        "result": "🤖 Academic Guidance:",
        "back": "🔙 Back",
        "main": "🏠 Main",
        "skip": "⏭ Skip",
        "repeat": "🔁 Repeat",
        "new": "🆕 New Topic"
    }
}

# ========= OPTIONS =========
OPTIONS = {
    "stage": {
        "ar": [
            ("دبلوم عالي", "diploma"),
            ("ليسانس", "license"),
            ("بكالوريوس", "bachelor"),
            ("ماجستير", "master"),
            ("دكتوراه", "phd")
        ],
        "en": [
            ("Higher Diploma", "diploma"),
            ("License", "license"),
            ("Bachelor", "bachelor"),
            ("Master", "master"),
            ("PhD", "phd")
        ]
    },
    "spec": {
        "ar": [
            ("علوم إنسانية", "human"),
            ("علوم اجتماعية", "social"),
            ("إدارة واقتصاد", "business"),
            ("قانون", "law"),
            ("علوم صحية", "health"),
            ("هندسة", "engineering"),
            ("تقنية معلومات", "it")
        ],
        "en": [
            ("Humanities", "human"),
            ("Social Sciences", "social"),
            ("Business & Economics", "business"),
            ("Law", "law"),
            ("Health Sciences", "health"),
            ("Engineering", "engineering"),
            ("IT", "it")
        ]
    },
    "work": {
        "ar": [
            ("خطة بحث", "plan"),
            ("تحليل بيانات", "analysis"),
            ("عرض تقديمي", "presentation"),
            ("مراجعة أدبية", "literature")
        ],
        "en": [
            ("Research Plan", "plan"),
            ("Data Analysis", "analysis"),
            ("Presentation", "presentation"),
            ("Literature Review", "literature")
        ]
    }
}

# ========= HELPERS =========
def t(context):
    return TEXTS[context.user_data.get("lang", "ar")]

def btns(items, prefix):
    return [[InlineKeyboardButton(name, callback_data=f"{prefix}_{val}")]
            for name, val in items]

def nav_row(context, back=None):
    # back: "stage" | "spec" | "work" | None
    T = t(context)
    row = []
    if back:
        row.append(InlineKeyboardButton(T["back"], callback_data=f"back_{back}"))
    row.append(InlineKeyboardButton(T["main"], callback_data="main"))
    return [row]

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[
        InlineKeyboardButton("🇱🇾 العربية", callback_data="lang_ar"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
    ]]
    await update.message.reply_text(TEXTS["ar"]["choose_lang"],
                                    reply_markup=InlineKeyboardMarkup(kb))
    return LANG

# ========= LANGUAGE =========
async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    lang = q.data.split("_")[1]
    context.user_data.clear()
    context.user_data["lang"] = lang
    T = t(context)
    kb = [[InlineKeyboardButton(T["start_btn"], callback_data="go_stage")]]
    await q.edit_message_text(T["start"], reply_markup=InlineKeyboardMarkup(kb))
    return STAGE

# ========= SHOW STAGE =========
async def show_stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    T = t(context)
    kb = btns(OPTIONS["stage"][context.user_data["lang"]], "stage")
    kb += nav_row(context)  # main only
    await q.edit_message_text(T["stage"], reply_markup=InlineKeyboardMarkup(kb))
    return SPEC

# ========= SHOW SPEC =========
async def show_spec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["stage"] = q.data
    T = t(context)
    kb = btns(OPTIONS["spec"][context.user_data["lang"]], "spec")
    kb += nav_row(context, back="stage")
    await q.edit_message_text(T["spec"], reply_markup=InlineKeyboardMarkup(kb))
    return WORK

# ========= SHOW WORK =========
async def show_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["spec"] = q.data
    T = t(context)
    kb = btns(OPTIONS["work"][context.user_data["lang"]], "work")
    kb += nav_row(context, back="spec")
    await q.edit_message_text(T["work"], reply_markup=InlineKeyboardMarkup(kb))
    return INPUT

# ========= HANDLE WORK =========
async def handle_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["work"] = q.data
    T = t(context)

    kb = [
        [InlineKeyboardButton(T["skip"], callback_data="skip")],
    ] + nav_row(context, back="work")

    await q.edit_message_text(
        f"{T['input']}\n\n{T['input_hint']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return INPUT

# ========= INPUT =========
async def input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    # منع الأوامر في هذه المرحلة
    if user_text.startswith("/"):
        await update.message.reply_text(f"{t(context)['input']}\n\n{t(context)['input_hint']}")
        return INPUT

    context.user_data["topic"] = user_text
    T = t(context)

    await update.message.reply_text(T["loading"])

    result = generate_ai(context.user_data)

    kb = [
        [
            InlineKeyboardButton(T["repeat"], callback_data="repeat"),
            InlineKeyboardButton(T["new"], callback_data="new")
        ],
        [InlineKeyboardButton(T["main"], callback_data="main")]
    ]

    await update.message.reply_text(
        f"{T['result']}\n\n{result}",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return INPUT

# ========= SKIP =========
async def skip_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["topic"] = "General academic topic"
    T = t(context)

    await q.message.reply_text(T["loading"])
    result = generate_ai(context.user_data)

    kb = [
        [
            InlineKeyboardButton(T["repeat"], callback_data="repeat"),
            InlineKeyboardButton(T["new"], callback_data="new")
        ],
        [InlineKeyboardButton(T["main"], callback_data="main")]
    ]

    await q.message.reply_text(
        f"{T['result']}\n\n{result}",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return INPUT

# ========= NAVIGATION =========
async def back_stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # رجوع لاختيار المرحلة
    q = update.callback_query; await q.answer()
    return await show_stage(update, context)

async def back_spec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # رجوع لاختيار التخصص
    q = update.callback_query; await q.answer()
    return await show_spec(update, context)

async def back_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # رجوع لاختيار نوع العمل
    q = update.callback_query; await q.answer()
    return await show_work(update, context)

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    return await start(update, context)

async def repeat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    T = t(context)
    await q.message.reply_text(f"{T['input']}\n\n{T['input_hint']}")
    return INPUT

async def new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    return await start(update, context)

# ========= AI =========
def generate_ai(data):
    # Prompt مختصر ومنظم لسرعة أفضل
    prompt = f"""
Respond in {data.get('lang','ar')}

Stage: {data.get('stage')}
Field: {data.get('spec')}
Work: {data.get('work')}
Topic: {data.get('topic')}

Provide concise structured output:
1) Analysis
2) Research Problem
3) 3 Questions
4) Methodology
5) Tips
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",  # أسرع
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {e}"

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).connect_timeout(60).read_timeout(60).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [
                CallbackQueryHandler(set_lang)
            ],
            STAGE: [
                CallbackQueryHandler(show_stage, pattern="^go_stage$"),
                CallbackQueryHandler(main_menu, pattern="^main$")
            ],
            SPEC: [
                CallbackQueryHandler(show_spec, pattern="^stage_"),
                CallbackQueryHandler(back_stage, pattern="^back_stage$"),
                CallbackQueryHandler(main_menu, pattern="^main$")
            ],
            WORK: [
                CallbackQueryHandler(show_work, pattern="^spec_"),
                CallbackQueryHandler(back_spec, pattern="^back_spec$"),
                CallbackQueryHandler(main_menu, pattern="^main$")
            ],
            INPUT: [
                CallbackQueryHandler(handle_work, pattern="^work_"),
                CallbackQueryHandler(skip_input, pattern="^skip$"),
                CallbackQueryHandler(back_work, pattern="^back_work$"),
                CallbackQueryHandler(back_spec, pattern="^back_spec$"),
                CallbackQueryHandler(back_stage, pattern="^back_stage$"),
                CallbackQueryHandler(repeat, pattern="^repeat$"),
                CallbackQueryHandler(new, pattern="^new$"),
                CallbackQueryHandler(main_menu, pattern="^main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_handler),
            ],
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    print("🚀 BOT STARTED...")
    app.run_polling()

if __name__ == "__main__":
    main()