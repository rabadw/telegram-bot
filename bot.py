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
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

# ===== STATES =====
LANG, MODE, LEVEL, FIELD, TOPIC, FORMAT = range(6)

# ===== LANGUAGE SYSTEM =====
def t(context, ar, en):
    return en if context.user_data.get("lang") == "en" else ar

# ===== MENUS =====
def lang_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇱🇾 العربية", callback_data="lang_ar"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ])

def main_menu(context):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(context,"📊 خطة بحث","📊 Research Plan"), callback_data="mode_research")],
        [InlineKeyboardButton(t(context,"📈 تحليل","📈 Analysis"), callback_data="mode_analysis")],
        [InlineKeyboardButton(t(context,"🎤 عرض تقديمي","🎤 Presentation"), callback_data="mode_presentation")]
    ])

def level_menu(context):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(context,"ليسانس","Bachelor"), callback_data="level_bachelor"),
            InlineKeyboardButton(t(context,"دبلوم عالي","Diploma"), callback_data="level_diploma")
        ],
        [
            InlineKeyboardButton(t(context,"ماجستير","Master"), callback_data="level_master"),
            InlineKeyboardButton(t(context,"دكتوراه","PhD"), callback_data="level_phd")
        ],
        [InlineKeyboardButton(t(context,"🏠 الرئيسية","🏠 Main Menu"), callback_data="main")]
    ])

def nav_menu(context):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(context,"🔙 رجوع","🔙 Back"), callback_data="back"),
            InlineKeyboardButton(t(context,"🏠 الرئيسية","🏠 Main"), callback_data="main")
        ]
    ])

# ===== HELPERS =====
def split_text(text, size=3500):
    return [text[i:i+size] for i in range(0, len(text), size)]

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["lang"] = "ar"  # افتراضي عربي

    await update.message.reply_text(
        "👋 أهلاً بك في أكاديمية الباحث الليبي\nاختر اللغة:",
        reply_markup=lang_menu()
    )
    return LANG

# ===== AUTO ENTRY =====
async def auto_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data:
        return await start(update, context)

    if context.user_data.get("await") == "field":
        context.user_data["field"] = update.message.text
        context.user_data["await"] = "topic"
        await update.message.reply_text(
            t(context,"✍️ اكتب موضوع البحث:","✍️ Enter research topic:"),
            reply_markup=nav_menu(context)
        )
        return TOPIC

    if context.user_data.get("await") == "topic":
        return await generate(update, context)

# ===== LANGUAGE =====
async def set_lang(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["lang"] = "en" if "en" in q.data else "ar"

    await q.edit_message_text(
        t(context,"اختر الخدمة:","Choose service:"),
        reply_markup=main_menu(context)
    )
    return MODE

# ===== MODE =====
async def set_mode(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["mode"] = q.data

    await q.edit_message_text(
        t(context,"🎓 اختر المستوى:","🎓 Choose level:"),
        reply_markup=level_menu(context)
    )
    return LEVEL

# ===== LEVEL =====
async def set_level(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["level"] = q.data
    context.user_data["await"] = "field"

    await q.edit_message_text(
        t(context,"📚 اكتب تخصصك:","📚 Enter your field:"),
        reply_markup=nav_menu(context)
    )
    return FIELD

# ===== GENERATE =====
async def generate(update, context):
    topic = update.message.text

    await update.message.reply_text(
        t(context,"⏳ جاري المعالجة...","⏳ Processing...")
    )

    lang_prompt = "Arabic" if context.user_data["lang"] == "ar" else "English"

    prompt = f"""
Write a full academic research in {lang_prompt} including:
title, introduction, problem, objectives, methodology, analysis, results, recommendations, references.

Topic: {topic}
Field: {context.user_data['field']}
Level: {context.user_data['level']}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        max_tokens=2500
    )

    text = res.choices[0].message.content
    context.user_data["last"] = text

    for part in split_text(text):
        await update.message.reply_text(part)

    await update.message.reply_text(
        t(context,"📌 اختر التالي:","📌 Next:"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Word", callback_data="doc")],
            [InlineKeyboardButton(t(context,"🔁 جديد","🔁 New"), callback_data="main")]
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

    await q.message.reply_document(open("research.docx","rb"))

    return FORMAT

# ===== NAV =====
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
            MessageHandler(filters.TEXT & ~filters.COMMAND, auto_entry)
        ],
        states={
            LANG: [CallbackQueryHandler(set_lang)],
            MODE: [CallbackQueryHandler(set_mode)],
            LEVEL: [CallbackQueryHandler(set_level), CallbackQueryHandler(go_main, pattern="main")],
            FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, auto_entry)],
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, auto_entry)],
            FORMAT: [
                CallbackQueryHandler(file_action, pattern="doc"),
                CallbackQueryHandler(go_main, pattern="main")
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)
    print("🚀 BOT READY")
    app.run_polling()

if __name__ == "__main__":
    main()
