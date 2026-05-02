import os
import logging
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from openai import OpenAI

# PDF + Arabic
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
import arabic_reshaper
from bidi.algorithm import get_display

# DOCX
from docx import Document

# ========= CONFIG =========
CHANNEL_URL = "https://t.me/LibyanResearchAcademy"  # ضع رابط قناتك هنا
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not TOKEN or not OPENAI_API_KEY:
    raise ValueError("Set TOKEN and OPENAI_API_KEY env vars")

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

# ========= DATABASE =========
conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    requests INTEGER DEFAULT 0
)
""")
conn.commit()
FREE_LIMIT = 6

# ========= STATES =========
LANG, MODE, LEVEL, FIELD, TOPIC_HELP, TITLE_SELECT, TOPIC, FORMAT = range(8)

# ========= HELPERS =========
def kb(rows): return InlineKeyboardMarkup(rows)

def nav_row():
    return [
        InlineKeyboardButton("⬅️ رجوع", callback_data="back"),
        InlineKeyboardButton("🏠 الرئيسية", callback_data="main"),
        InlineKeyboardButton("❌ خروج", callback_data="exit"),
    ]

def check_user(uid):
    cursor.execute("SELECT requests FROM users WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    if not r:
        cursor.execute("INSERT INTO users VALUES (?,0)", (uid,))
        conn.commit()
        return True
    return r[0] < FREE_LIMIT

def inc_user(uid):
    cursor.execute("UPDATE users SET requests=requests+1 WHERE user_id=?", (uid,))
    conn.commit()

# ========= FONT =========
def register_font():
    if os.path.exists("arial.ttf"):
        pdfmetrics.registerFont(TTFont("Arabic", "arial.ttf"))
        return "Arabic"
    elif os.path.exists("Amiri-Regular.ttf"):
        pdfmetrics.registerFont(TTFont("Arabic", "Amiri-Regular.ttf"))
        return "Arabic"
    return "Helvetica"

# ========= PDF =========
def create_pdf(text, filename):
    font_name = register_font()
    style = ParagraphStyle(
        name="ArabicStyle",
        fontName=font_name,
        alignment=TA_RIGHT,
        fontSize=13,
        leading=20
    )
    doc = SimpleDocTemplate(filename)
    story = []
    for line in text.split("\n"):
        reshaped = arabic_reshaper.reshape(line)
        bidi_text = get_display(reshaped)
        story.append(Paragraph(bidi_text, style))
        story.append(Spacer(1, 10))
    doc.build(story)

# ========= DOC =========
def create_doc(text, filename):
    d = Document()
    d.add_heading("بحث أكاديمي", 0)
    for line in text.split("\n"):
        d.add_paragraph(line)
    d.save(filename)

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🎓 أكاديمية الباحث\n\n"
        "🧠 نساعدك في:\n"
        "• اختيار الموضوع وصياغة عنوان دقيق\n"
        "• إعداد خطة بحث / تحليل / عرض\n"
        "• تنزيل PDF أو Word\n\n"
        "اختر اللغة:",
        reply_markup=kb([
            [InlineKeyboardButton("🇱🇾 العربية", callback_data="lang_ar"),
             InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
        ])
    )
    return LANG

# ========= NAV =========
async def go_main(update, context):
    if update.callback_query:
        await update.callback_query.answer()
    return await start(update, context)

async def go_back(update, context):
    q = update.callback_query
    await q.answer()
    # رجوع خطوة واحدة للخلف بشكل بسيط:
    prev = context.user_data.get("prev_state", LANG)
    # نعيد توجيه بسيط حسب الحالة السابقة
    if prev == MODE:
        return await set_lang(update, context)
    if prev == LEVEL:
        return await set_mode(update, context)
    if prev == FIELD:
        return await set_level(update, context)
    if prev == TOPIC_HELP:
        return await set_field(update, context)
    if prev == TITLE_SELECT:
        return await topic_help_prompt(update, context)
    return await start(update, context)

async def exit_bot(update, context):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("👋 تم الخروج. اكتب /start للبدء مجددًا")
    return ConversationHandler.END

# ========= LANGUAGE =========
async def set_lang(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["lang"] = q.data.split("_")[1]
    context.user_data["prev_state"] = LANG

    await q.edit_message_text(
        "🧠 اختر نوع الخدمة:",
        reply_markup=kb([
            [InlineKeyboardButton("📊 خطة بحث", callback_data="research")],
            [InlineKeyboardButton("📈 تحليل", callback_data="analysis")],
            [InlineKeyboardButton("🎤 عرض تقديمي", callback_data="presentation")],
            nav_row()
        ])
    )
    return MODE

# ========= MODE =========
async def set_mode(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["mode"] = q.data
    context.user_data["prev_state"] = MODE

    levels = ["دبلوم عالي","ليسانس","بكالوريوس","ماجستير","دكتوراه"]
    await q.edit_message_text(
        "🎓 اختر المستوى:",
        reply_markup=kb([[InlineKeyboardButton(l, callback_data=f"level_{l}")] for l in levels] + [nav_row()])
    )
    return LEVEL

# ========= LEVEL =========
async def set_level(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["level"] = q.data.replace("level_", "")
    context.user_data["prev_state"] = LEVEL

    fields = ["تقنية معلومات","هندسة","طب","اقتصاد","قانون","إدارة","علوم اجتماعية","تربية"]
    await q.edit_message_text(
        "📚 اختر التخصص:",
        reply_markup=kb([[InlineKeyboardButton(f, callback_data=f"field_{f}")] for f in fields] + [nav_row()])
    )
    return FIELD

# ========= FIELD =========
async def set_field(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["field"] = q.data.replace("field_", "")
    context.user_data["prev_state"] = FIELD

    # الانتقال لمرحلة مساعدة اختيار الموضوع
    return await topic_help_prompt(update, context)

# ========= TOPIC HELP =========
async def topic_help_prompt(update, context):
    q = update.callback_query
    if q:
        await q.answer()
        await q.edit_message_text(
            "💡 اكتب فكرة عامة أو كلمات مفتاحية (مثال: الذكاء الاصطناعي في التعليم)،\n"
            "وسأقترح لك عناوين دقيقة:",
            reply_markup=kb([nav_row()])
        )
    else:
        await update.message.reply_text(
            "💡 اكتب فكرة عامة أو كلمات مفتاحية:",
            reply_markup=kb([nav_row()])
        )
    context.user_data["prev_state"] = TOPIC_HELP
    return TOPIC_HELP

async def topic_help(update, context):
    # اقتراح عناوين
    user_text = update.message.text
    context.user_data["seed"] = user_text

    await update.message.reply_text("⏳ جارٍ اقتراح عناوين دقيقة...")

    prompt = f"""
اقترح 5 عناوين بحث أكاديمية دقيقة وقابلة للتنفيذ حول:
"{user_text}"
في تخصص {context.user_data['field']} ومستوى {context.user_data['level']}.
اكتبها مرقمة ومختصرة.
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        max_tokens=300
    )
    titles_text = res.choices[0].message.content.strip()
    # نحولها لأزرار (حتى 5)
    titles = [t.strip(" -\n\r0123456789.)(") for t in titles_text.split("\n") if t.strip()][:5]
    rows = [[InlineKeyboardButton(t[:64], callback_data=f"title_{i}")] for i, t in enumerate(titles)]
    rows.append(nav_row())

    context.user_data["titles"] = titles
    await update.message.reply_text("📌 اختر عنوانًا أو ارجع:", reply_markup=kb(rows))
    context.user_data["prev_state"] = TITLE_SELECT
    return TITLE_SELECT

# ========= TITLE SELECT =========
async def select_title(update, context):
    q = update.callback_query
    await q.answer()

    idx = int(q.data.replace("title_",""))
    title = context.user_data["titles"][idx]
    context.user_data["topic"] = title
    context.user_data["prev_state"] = TITLE_SELECT

    await q.edit_message_text(
        f"📝 تم اختيار العنوان:\n\n{title}\n\n"
        "هل تريد المتابعة لإنشاء المحتوى؟",
        reply_markup=kb([
            [InlineKeyboardButton("▶️ متابعة", callback_data="go_generate")],
            nav_row()
        ])
    )
    return TOPIC

# ========= GENERATE =========
async def do_generate(update, context):
    q = update.callback_query
    await q.answer()

    user_id = str(update.effective_user.id)
    if not check_user(user_id):
        await q.edit_message_text("❌ انتهت المحاولات المجانية")
        return ConversationHandler.END

    await q.edit_message_text("⏳ جارٍ إنشاء المحتوى...")

    mode = context.user_data["mode"]

    if mode == "research":
        instruction = "اكتب خطة بحث أكاديمية مفصلة"
    elif mode == "analysis":
        instruction = "اكتب تحليل أكاديمي معمق"
    else:
        instruction = "اكتب عرض تقديمي منظم بنقاط"

    prompt = f"""
{instruction}

العنوان: {context.user_data['topic']}
المستوى: {context.user_data['level']}
التخصص: {context.user_data['field']}

اكتب بأسلوب أكاديمي احترافي.
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=900
    )

    text = res.choices[0].message.content
    context.user_data["last"] = text

    # إرسال النتيجة
    await q.message.reply_text(text[:1200])

    # زر القناة
    await q.message.reply_text(
        "━━━━━━━━━━━━━━━\n"
        "🔥 هذا مجرد جزء من النتيجة\n\n"
        "📌 للحصول على:\n"
        "• نماذج بحوث جاهزة\n"
        "• أفكار بحث احترافية\n"
        "• شروحات مبسطة خطوة بخطوة\n\n"
        "🚀 طوّر مستواك الآن وابدأ بشكل صحيح",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 الانضمام للقناة", url=CHANNEL_URL)]
        ])
    )

    # الخيارات
    await q.message.reply_text(
        "اختر الإجراء:",
        reply_markup=kb([
            [
                InlineKeyboardButton("📄 PDF", callback_data="pdf"),
                InlineKeyboardButton("📝 Word", callback_data="doc")
            ],
            [
                InlineKeyboardButton("🔁 طلب جديد", callback_data="new"),
                InlineKeyboardButton("💬 استفسار إضافي", callback_data="ask")
            ],
            nav_row()
        ])
    )

    inc_user(user_id)
    return FORMAT
# ========= FILE =========
async def make_file(update, context):
    q = update.callback_query
    await q.answer()

    text = context.user_data.get("last","")
    filename = "output.pdf" if q.data == "pdf" else "output.docx"

    if q.data == "pdf":
        create_pdf(text, filename)
    else:
        create_doc(text, filename)

    await q.message.reply_document(open(filename, "rb"))
    return FORMAT

# ========= EXTRA CHAT =========
async def ask_more(update, context):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("💬 اكتب سؤالك:")
    return FORMAT

async def extra_chat(update, context):
    user_input = update.message.text
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"أنت مساعد أكاديمي محترف"},
            {"role":"user","content":user_input}
        ],
        max_tokens=400
    )
    await update.message.reply_text(res.choices[0].message.content)
    return FORMAT

# ========= NEW =========
async def new_req(update, context):
    return await start(update, context)

# ========= MAIN =========def main():
    def main():
        app = ApplicationBuilder().token(TOKEN).build()

    # التشغيل التلقائي
    app.add_handler(MessageHandler(filters.ALL, auto_start), group=0)

        conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [
                CallbackQueryHandler(set_lang),
                CallbackQueryHandler(go_main, pattern="main"),
                CallbackQueryHandler(exit_bot, pattern="exit")
            ],
            MODE: [
                CallbackQueryHandler(set_mode, pattern="^(research|analysis|presentation)$"),
                CallbackQueryHandler(go_main, pattern="main"),
                CallbackQueryHandler(go_back, pattern="back"),
                CallbackQueryHandler(exit_bot, pattern="exit")
            ],
            LEVEL: [
                CallbackQueryHandler(set_level, pattern="^level_"),
                CallbackQueryHandler(go_main, pattern="main"),
                CallbackQueryHandler(go_back, pattern="back"),
                CallbackQueryHandler(exit_bot, pattern="exit")
            ],
            FIELD: [
                CallbackQueryHandler(set_field, pattern="^field_"),
                CallbackQueryHandler(go_main, pattern="main"),
                CallbackQueryHandler(go_back, pattern="back"),
                CallbackQueryHandler(exit_bot, pattern="exit")
            ],
            TOPIC_HELP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, topic_help),
                CallbackQueryHandler(go_main, pattern="main"),
                CallbackQueryHandler(go_back, pattern="back"),
                CallbackQueryHandler(exit_bot, pattern="exit")
            ],
            TITLE_SELECT: [
                CallbackQueryHandler(select_title, pattern="^title_"),
                CallbackQueryHandler(go_main, pattern="main"),
                CallbackQueryHandler(go_back, pattern="back"),
                CallbackQueryHandler(exit_bot, pattern="exit")
            ],
            TOPIC: [
                CallbackQueryHandler(do_generate, pattern="go_generate"),
                CallbackQueryHandler(go_main, pattern="main"),
                CallbackQueryHandler(go_back, pattern="back"),
                CallbackQueryHandler(exit_bot, pattern="exit")
            ],
            FORMAT: [
                CallbackQueryHandler(make_file, pattern="^(pdf|doc)$"),
                CallbackQueryHandler(new_req, pattern="new"),
                CallbackQueryHandler(ask_more, pattern="ask"),
                CallbackQueryHandler(go_main, pattern="main"),
                CallbackQueryHandler(go_back, pattern="back"),
                CallbackQueryHandler(exit_bot, pattern="exit"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, extra_chat)
            ],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv)

    print("🚀 BOT RUNNING...")
    app.run_polling(close_loop=False)
    
if __name__ == "__main__":
    main()
