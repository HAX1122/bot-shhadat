import asyncio
import logging
import html
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

import config
import database
from data_seed import seed_database
import scraper

# إعداد السجلات Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# لوحة المفاتيح الرئيسية في الدردشة
MAIN_REPLY_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🚀 أحدث الفرص والشهادات"), KeyboardButton("🔍 بحث مخصص")],
        [KeyboardButton("🤖 الذكاء الاصطناعي"), KeyboardButton("📊 علم وتحليل البيانات")],
        [KeyboardButton("💻 علوم الحاسب والبرمجة"), KeyboardButton("🛡️ الأمن والتقنيات السحابية")],
        [KeyboardButton("🔔 حالة التنبيهات"), KeyboardButton("📊 إحصائيات"), KeyboardButton("ℹ️ عن البوت")]
    ],
    resize_keyboard=True
)

def format_opportunity_card(opp: dict, is_broadcast: bool = False) -> str:
    """تنسيق بطاقة الفرصة والشهادة بأسلوب احترافي وجذاب بتقنية HTML"""
    title = html.escape(opp["title"])
    provider = html.escape(opp["provider"])
    cert_type = html.escape(opp.get("cert_type", "شهادة خبرة معتمدة 📜"))
    cost = html.escape(opp.get("cost", "مجاني 100% 🆓"))
    mode = html.escape(opp.get("mode", "عن بُعد (Online) 🌐"))
    duration = html.escape(opp.get("duration", "محدد في الإعلان"))
    description = html.escape(opp.get("description", ""))
    requirements = html.escape(opp.get("requirements", ""))
    url = opp["url"]
    
    category_emojis = {
        "ai": "🤖 الذكاء الاصطناعي (AI)",
        "data": "📊 علم وتحليل البيانات (Data)",
        "cs": "💻 علوم الحاسب والبرمجيات (CS)",
        "cyber": "🛡️ الأمن السيبراني والسحابي (Cyber & Cloud)"
    }
    cat_text = category_emojis.get(opp.get("category", "cs"), "💻 تقنية الحاسب")
    
    header = "🚨 <b>فرصة وشهادة خبرة جديدة مرصودة الآن!</b>\n\n" if is_broadcast else ""
    
    text = (
        f"{header}"
        f"🎓 <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏢 <b>الجهة المنظمة:</b> {provider}\n"
        f"📂 <b>المسار التخصصي:</b> {cat_text}\n"
        f"📜 <b>نوع الشهادة:</b> {cert_type}\n"
        f"💰 <b>التكلفة:</b> {cost}\n"
        f"📍 <b>الأسلوب والمقر:</b> {mode}\n"
        f"⏳ <b>المدة:</b> {duration}\n\n"
        f"📋 <b>نبذة وتفاصيل:</b>\n{description}\n\n"
        f"📌 <b>المتطلبات والشروط:</b>\n{requirements}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <b>رابط التقديم المباشر:</b> <a href=\"{url}\">اضغط هنا للتسجيل في المنصة الرسمية</a>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>#شهادات_خبرة #السعودية #الذكاء_الاصطناعي #علم_البيانات #طويق #سدايا</i>"
    )
    return text

def build_card_buttons(opp: dict) -> InlineKeyboardMarkup:
    """إنشاء أزرار التسجيل والمشاركة للفرصة"""
    keyboard = [
        [InlineKeyboardButton("🔗 التقديم والتسجيل في المنصة الرسمية", url=opp["url"])],
        [
            InlineKeyboardButton("📢 مشاركة الفرصة", switch_inline_query=opp["title"]),
            InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_home")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_list_buttons(category: str, page: int, total_pages: int, opp: dict) -> InlineKeyboardMarkup:
    """إنشاء أزرار التصفح والانتقال المباشر بين الفرص مع رابط التقديم الفوري"""
    row_nav = []
    if page > 1:
        row_nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"nav_{category}_{page - 1}"))
    row_nav.append(InlineKeyboardButton(f"📄 {page} / {total_pages}", callback_data="ignore"))
    if page < total_pages:
        row_nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"nav_{category}_{page + 1}"))
        
    keyboard = [
        [InlineKeyboardButton("🔗 التقديم والتسجيل المباشر في المنصة الرسمية", url=opp["url"])],
        row_nav,
        [
            InlineKeyboardButton("📢 مشاركة الشهادة", switch_inline_query=opp["title"]),
            InlineKeyboardButton("🔙 رجوع للتصنيفات", callback_data="categories_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الترحيب بالمستخدم وتسجيله في قاعدة بيانات التنبيهات الفورية"""
    user = update.effective_user
    database.add_subscriber(user.id, user.username or "", user.first_name or "")
    
    welcome_text = (
        f"أهلاً بك يا <b>{html.escape(user.first_name)}</b> في <b>رادار شهادات الخبرة والمعسكرات التقنية المجانية بالمملكة</b> 🇸🇦⚡\n\n"
        f"🎯 <b>وظيفة هذا البوت:</b>\n"
        f"يرصد لك على مدار الساعة (24/7) أي <b>شهادة خبرة مجانية أو معسكر تدريبي أو فرصة تدريب على رأس العمل</b> في:\n"
        f"• 🤖 الذكاء الاصطناعي (AI & Machine Learning)\n"
        f"• 📊 علم وتحليل البيانات (Data Science & Analytics)\n"
        f"• 💻 علوم الحاسب والبرمجيات (Computer Science & SE)\n"
        f"• 🛡️ الأمن السيبراني والحوسبة السحابية (Cybersecurity & Cloud)\n\n"
        f"📡 <b>المصادر المرصودة:</b>\n"
        f"أكاديمية طويق، سدايا (SDAIA)، مهارات المستقبل (MCIT)، مؤسسة مسك، صندوق هدف (تمهير/دروب)، كاوست، ومنصات الخبرة الافتراضية العالمية المعتمدة (Forage/Google/BCG/JPMorgan).\n\n"
        f"🔔 <b>تم تفعيل التنبيهات التلقائية لحسابك!</b> ستصلك أي فرصة أو شهادة جديدة فور صدورها برابط التسجيل والشروط والمتطلبات.\n\n"
        f"👇 اختر مساراً للتصفح الآن أو استخدم الأزرار بالأسفل:"
    )
    
    stats = database.get_stats()
    cats = stats.get("categories", {})
    ai_count = cats.get("ai", 0)
    data_count = cats.get("data", 0)
    cs_count = cats.get("cs", 0)
    cyber_count = cats.get("cyber", 0)
    total_count = stats.get("total_opportunities", 0)
    
    inline_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🚀 استعراض كافة الشهادات المعتمدة ({total_count})", callback_data="nav_all_1")],
        [
            InlineKeyboardButton(f"🤖 الذكاء الاصطناعي ({ai_count})", callback_data="nav_ai_1"),
            InlineKeyboardButton(f"📊 علم البيانات ({data_count})", callback_data="nav_data_1")
        ],
        [
            InlineKeyboardButton(f"💻 علوم الحاسب ({cs_count})", callback_data="nav_cs_1"),
            InlineKeyboardButton(f"🛡️ الأمن السيبراني ({cyber_count})", callback_data="nav_cyber_1")
        ],
        [
            InlineKeyboardButton("🔍 بحث مخصص بالكلمات", callback_data="ask_search"),
            InlineKeyboardButton("🔄 فحص فوري للمنصات", callback_data="check_now")
        ]
    ])
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=MAIN_REPLY_KEYBOARD,
        parse_mode=ParseMode.HTML
    )
    await update.message.reply_text(
        "🗂️ <b>لوحة التصفح السريع للمسارات:</b>",
        reply_markup=inline_kb,
        parse_mode=ParseMode.HTML
    )

async def show_opportunity_page(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, page: int):
    """عرض صفحة لفرصة محددة مع أزرار التنقل ورابط التقديم المباشر"""
    query = update.callback_query
    total_count = database.get_total_opportunities_count(category)
    if total_count == 0:
        msg = "⚠️ لا توجد شهادات مسجلة حالياً في هذا المسار. جاري الرصد المستمر..."
        if query:
            await query.answer()
            await query.edit_message_text(msg)
        else:
            await update.effective_message.reply_text(msg)
        return
        
    page = max(1, min(page, total_count))
    opps = database.get_latest_opportunities(category=category, limit=1, offset=page - 1)
    if not opps:
        return
        
    opp = dict(opps[0])
    text = format_opportunity_card(opp)
    reply_markup = build_list_buttons(category, page, total_count, opp)
    
    if query:
        await query.answer()
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
    else:
        await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML, disable_web_page_preview=False)

async def cmd_latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أحدث الفرص المتاحة لجميع المسارات"""
    await show_opportunity_page(update, context, "all", 1)

async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_opportunity_page(update, context, "ai", 1)

async def cmd_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_opportunity_page(update, context, "data", 1)

async def cmd_cs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_opportunity_page(update, context, "cs", 1)

async def cmd_cyber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_opportunity_page(update, context, "cyber", 1)

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات الفرص والمشتركين"""
    stats = database.get_stats()
    cats = stats["categories"]
    text = (
        f"📊 <b>إحصائيات رادار الشهادات والفرص التقنية</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>إجمالي الفرص والشهادات المرصودة:</b> {stats['total_opportunities']} فرصة\n"
        f"👥 <b>عدد المشتركين النشطين بالتنبيهات:</b> {stats['active_subscribers']} مشترك\n\n"
        f"📂 <b>توزيع الفرص بحسب المسار:</b>\n"
        f"• 🤖 الذكاء الاصطناعي (AI): {cats.get('ai', 0)} فرصة\n"
        f"• 📊 علم وتحليل البيانات (Data): {cats.get('data', 0)} فرصة\n"
        f"• 💻 علوم الحاسب والبرمجة (CS): {cats.get('cs', 0)} فرصة\n"
        f"• 🛡️ الأمن والتقنيات السحابية: {cats.get('cyber', 0)} فرصة\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱️ الرصد يعمل آلياً كل 60 دقيقة من مصادر التدريب الوطنية المعتمدة."
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التحكم بتفعيل أو إلغاء التنبيهات الفورية"""
    user_id = update.effective_user.id
    sub = database.get_subscriber(user_id)
    is_active = bool(sub["is_active"]) if sub else False
    
    # تبديل الحالة
    new_state = not is_active
    database.set_subscriber_status(user_id, new_state)
    
    status_icon = "مفعلة 🔔✅" if new_state else "معطلة 🔕"
    text = (
        f"تم تعديل حالة الإشعارات لحسابك بنجاح:\n"
        f"حالة التنبيهات الفورية: <b>{status_icon}</b>\n\n"
        f"{'ستصلك رسالة فورية عند رصد أي شهادة أو معسكر جديد!' if new_state else 'لن تصلك تنبيهات تلقائية. يمكنك تفعيلها في أي وقت بالنقر على نفس الزر.'}"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إجراء فحص فوري للمصادر وتحديث قاعدة البيانات"""
    msg = await update.effective_message.reply_text("🔄 جاري فحص جميع المنصات والمصادر الرسمية الآن... الرجاء الانتظار ثوانٍ معدودة.")
    found = scraper.scan_sources()
    
    if found:
        text = f"✅ <b>اكتمل الفحص!</b> تم العثور على <b>{len(found)}</b> فرصة وشهادة تدريبية جديدة وإضافتها للقاعدة بنجاح."
    else:
        text = "✅ <b>اكتمل الفحص!</b> جميع الفرص الحالية محدثة، ولم تصدر إعلانات جديدة غير مرصودة في الدقائق الأخيرة."
        
    await msg.edit_text(text, parse_mode=ParseMode.HTML)
    if found:
        # عرض أول فرصة مكتشفة
        card = format_opportunity_card(found[0])
        kb = build_card_buttons(found[0])
        await update.effective_message.reply_text(card, reply_markup=kb, parse_mode=ParseMode.HTML)

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التعامل مع نصوص الأزرار النصية والبحث"""
    text = update.message.text.strip()
    
    if text == "🚀 أحدث الفرص والشهادات":
        await cmd_latest(update, context)
    elif text == "🤖 الذكاء الاصطناعي":
        await cmd_ai(update, context)
    elif text == "📊 علم وتحليل البيانات":
        await cmd_data(update, context)
    elif text == "💻 علوم الحاسب والبرمجة":
        await cmd_cs(update, context)
    elif text == "🛡️ الأمن والتقنيات السحابية":
        await cmd_cyber(update, context)
    elif text == "🔔 حالة التنبيهات":
        await cmd_alerts(update, context)
    elif text == "📊 إحصائيات":
        await cmd_stats(update, context)
    elif text == "🔍 بحث مخصص":
        context.user_data["waiting_for_search"] = True
        await update.message.reply_text("🔍 اكتب الكلمة المفتاحية للبحث (مثال: <code>سدايا</code>، <code>طويق</code>، <code>بايثون</code>، <code>تمهير</code>، <code>عن بعد</code>):", parse_mode=ParseMode.HTML)
    elif text == "ℹ️ عن البوت":
        about_text = (
            f"ℹ️ <b>عن رادار الشهادات والفرص التقنية في السعودية</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"هذا البوت مصمم لرصد وتجميع كافة <b>شهادات الخبرة المجانية والمعسكرات التدريبية المعتمدة</b> في مجالات:\n"
            f"البيانات (Data)، الذكاء الاصطناعي (AI)، وعلوم الحاسب (CS).\n\n"
            f"✨ <b>مميزات البوت:</b>\n"
            f"• مجاني 100% ولا يتطلب أي رسوم.\n"
            f"• فحص دوري مستمر على مدار 24 ساعة.\n"
            f"• يرسل الرابط المباشر والمتطلبات الرسمية والجهة المنظمة.\n"
            f"• إمكانية ربطه بالقنوات والقروبات للبث المباشر التلقائي.\n\n"
            f"📢 <b>لربط البوت بقناتك:</b> أضف البوت مشرفاً (Admin) في قناتك وسيقوم بالنشر التلقائي فور رصد أي فرصة!"
        )
        await update.message.reply_text(about_text, parse_mode=ParseMode.HTML)
    elif context.user_data.get("waiting_for_search"):
        context.user_data["waiting_for_search"] = False
        results = database.search_opportunities(text, limit=5)
        if not results:
            await update.message.reply_text(f"لم يتم العثور على نتائج تطابق: <b>{html.escape(text)}</b>.\nجرب كلمة أخرى مثل: ذكاء، سدايا، طويق، بايثون.", parse_mode=ParseMode.HTML)
            return
            
        await update.message.reply_text(f"🔍 تم العثور على <b>{len(results)}</b> فرصة تطابق: <b>{html.escape(text)}</b>", parse_mode=ParseMode.HTML)
        for row in results:
            opp = dict(row)
            card = format_opportunity_card(opp)
            kb = build_card_buttons(opp)
            await update.message.reply_text(card, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        # بحث مباشر عن النص المرسل
        results = database.search_opportunities(text, limit=3)
        if results:
            await update.message.reply_text(f"🔎 نتائج البحث عن <b>{html.escape(text)}</b>:", parse_mode=ParseMode.HTML)
            for row in results:
                opp = dict(row)
                card = format_opportunity_card(opp)
                kb = build_card_buttons(opp)
                await update.message.reply_text(card, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("الرجاء اختيار أحد المسارات من الأزرار أو كتابة كلمة مفتاحية للبحث.", reply_markup=MAIN_REPLY_KEYBOARD)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة النقر على الأزرار الشفافة Inline Buttons"""
    query = update.callback_query
    data = query.data
    
    if data == "ignore":
        await query.answer()
        return
        
    if data.startswith("nav_"):
        parts = data.split("_")
        category = parts[1]
        page = int(parts[2])
        await show_opportunity_page(update, context, category, page)
        return
        
    if data.startswith("open_url_"):
        opp_id = int(data.replace("open_url_", ""))
        opp = database.get_opportunity_by_id(opp_id)
        if opp:
            await query.answer()
            await query.message.reply_text(
                f"🔗 <b>رابط التقديم الرسمي لـ {html.escape(opp['title'])}:</b>\n{opp['url']}",
                parse_mode=ParseMode.HTML
            )
        return
        
    if data == "ask_search":
        await query.answer()
        context.user_data["waiting_for_search"] = True
        await query.message.reply_text("🔍 اكتب الكلمة التي تبحث عنها (مثال: سدايا، طويق، ذكاء، علم البيانات):")
        return
        
    if data == "check_now":
        await query.answer()
        await cmd_check(update, context)
        return
        
    if data == "menu_home":
        await query.answer()
        await cmd_start(update, context)
        return
        
    if data == "categories_menu":
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 جميع المسارات", callback_data="nav_all_1")],
            [InlineKeyboardButton("🤖 الذكاء الاصطناعي", callback_data="nav_ai_1")],
            [InlineKeyboardButton("📊 علم وتحليل البيانات", callback_data="nav_data_1")],
            [InlineKeyboardButton("💻 علوم الحاسب والبرمجة", callback_data="nav_cs_1")],
            [InlineKeyboardButton("🛡️ الأمن والتقنيات السحابية", callback_data="nav_cyber_1")]
        ])
        await query.edit_message_text("📂 <b>اختر المسار التخصصي للتصفح:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

async def broadcast_new_opportunity(bot, opp: dict):
    """إرسال الفرصة الجديدة لكافة المشتركين والقناة المسجلة مع منع التكرار"""
    opp_id = opp["id"]
    text = format_opportunity_card(opp, is_broadcast=True)
    kb = build_card_buttons(opp)
    
    # 1. الإرسال إلى القناة إن وجدت
    if config.TELEGRAM_CHANNEL_ID:
        channel_id = config.TELEGRAM_CHANNEL_ID.strip()
        if not database.is_notification_sent(opp_id, channel_id):
            try:
                await bot.send_message(
                    chat_id=channel_id,
                    text=text,
                    reply_markup=kb,
                    parse_mode=ParseMode.HTML
                )
                database.log_notification_sent(opp_id, channel_id)
                logger.info(f"Broadcasted opp #{opp_id} to channel {channel_id}")
            except Exception as e:
                logger.error(f"Failed to broadcast to channel {channel_id}: {e}")
                
    # 2. الإرسال إلى المشتركين النشطين
    subscribers = database.get_active_subscribers()
    for sub in subscribers:
        user_id = sub["user_id"]
        if not database.is_notification_sent(opp_id, str(user_id)):
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=kb,
                    parse_mode=ParseMode.HTML
                )
                database.log_notification_sent(opp_id, str(user_id))
                await asyncio.sleep(0.05) # حماية من حدود التليجرام
            except Exception as e:
                logger.warning(f"Could not send notification to user {user_id}: {e}")

async def background_monitoring_task(bot):
    """مهمة الرصد الدوري الخلفية التي تعمل 24 ساعة باستمرار"""
    logger.info("Background monitoring task started (24/7 scanner).")
    while True:
        try:
            logger.info("Running scheduled scan for new opportunities...")
            new_opps = scraper.scan_sources()
            if new_opps:
                logger.info(f"Discovered {len(new_opps)} new opportunities! Broadcasting...")
                for opp in new_opps:
                    await broadcast_new_opportunity(bot, opp)
            else:
                logger.info("Scan completed. No new opportunities found.")
        except Exception as e:
            logger.error(f"Error in background monitor task: {e}")
            
        # الانتظار حتى الفحص القادم
        await asyncio.sleep(config.SCAN_INTERVAL_MINUTES * 60)

def build_application() -> Application:
    """بناء وتهيئة تطبيق التليجرام وإضافة المعالجات"""
    seed_database()
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # أوامر البوت
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("latest", cmd_latest))
    app.add_handler(CommandHandler("ai", cmd_ai))
    app.add_handler(CommandHandler("data", cmd_data))
    app.add_handler(CommandHandler("cs", cmd_cs))
    app.add_handler(CommandHandler("cyber", cmd_cyber))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("help", cmd_start))
    
    # معالجات الأزرار والنصوص
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    
    return app

async def run_bot_async():
    """تشغيل البوت مع الرصد الدوري في حلقة asyncio واحدة"""
    app = build_application()
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot is active and polling updates...")
    
    # إطلاق حلقة الرصد الدوري في الخلفية
    monitor_task = asyncio.create_task(background_monitoring_task(app.bot))
    
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        monitor_task.cancel()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

def main():
    """نقطة الدخول الرئيسية"""
    asyncio.run(run_bot_async())

if __name__ == "__main__":
    main()
