import os

# Telegram Bot Token (الافتراضي هو التوكن المزود من المستخدم، ويمكن تجاوزه عبر متغيرات البيئة)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8693907736:AAG3TOa5omrUHAPqOUjTC6W_lK6aT1Ycp1c")

# معرّف القناة أو القروب الاختياري لنشر الفرص تلقائياً (مثال: @MySaudiCertsChannel أو -100123456789)
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

# منفذ خادم الويب للاستضافة السحابية على Render/Railway/Koyeb
PORT = int(os.getenv("PORT", 8080))

# مسار قاعدة البيانات المحلية SQLite
DB_PATH = os.getenv("DB_PATH", "certs_bot.db")

# الفترة الزمنية بين كل فحص تلقائي لمصادر الفرص (بالدقائق)
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", 60))

# تصنيفات المجالات التقنية المدعومة
CATEGORIES = {
    "all": "🌐 جميع المسارات",
    "ai": "🤖 الذكاء الاصطناعي (AI)",
    "data": "📊 علم وتحليل البيانات (Data)",
    "cs": "💻 علوم الحاسب والبرمجيات (CS)",
    "cyber": "🛡️ الأمن السيبراني والحوسبة السحابية (Cyber & Cloud)",
}
