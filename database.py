import sqlite3
import hashlib
from datetime import datetime
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """تهيئة جداول قاعدة البيانات إذا لم تكن موجودة"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # جدول المشتركين
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_active INTEGER DEFAULT 1,
                category_filter TEXT DEFAULT 'all',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول الفرص والشهادات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT UNIQUE,
                title TEXT NOT NULL,
                provider TEXT NOT NULL,
                category TEXT NOT NULL,
                cert_type TEXT NOT NULL,
                cost TEXT DEFAULT 'مجاني 100% 🆓',
                mode TEXT DEFAULT 'عن بُعد (Online)',
                duration TEXT,
                description TEXT,
                requirements TEXT,
                url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # جدول سجلات الإشعارات المرسلة لمنع التكرار
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id INTEGER,
                target_id TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
            )
        """)
        
        # جدول القنوات والقروبات المسجلة للبث التلقائي
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                title TEXT,
                username TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        conn.commit()

# تهيئة الجداول تلقائياً عند استيراد الوحدة
init_db()

def generate_uid(title: str, provider: str, url: str) -> str:
    """إنشاء معرف فريد للفرصة لمنع تكرار الإدخال"""
    raw = f"{title.strip().lower()}|{provider.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]

def add_subscriber(user_id: int, username: str = "", first_name: str = "") -> bool:
    """تسجيل مستخدم جديد أو إعادة تفعيله"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subscribers (user_id, username, first_name, is_active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                is_active = 1
        """, (user_id, username, first_name))
        conn.commit()
        return True

def set_subscriber_status(user_id: int, is_active: bool):
    """تفعيل أو تعطيل التنبيهات للمستخدم"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE subscribers SET is_active = ? WHERE user_id = ?", (1 if is_active else 0, user_id))
        conn.commit()

def get_subscriber(user_id: int):
    """جلب بيانات مشترك محدد"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subscribers WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def get_active_subscribers():
    """جلب قائمة جميع المشتركين النشطين لاستقبال التنبيهات"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, category_filter FROM subscribers WHERE is_active = 1")
        return cursor.fetchall()

def save_opportunity(data: dict) -> tuple[bool, int]:
    """
    حفظ فرصة جديدة في قاعدة البيانات
    العودة: (هل هي فرصة جديدة تماماً؟, معرف الفرصة)
    """
    uid = data.get("uid") or generate_uid(data["title"], data["provider"], data["url"])
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO opportunities (
                    uid, title, provider, category, cert_type, cost, mode,
                    duration, description, requirements, url, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                uid,
                data["title"],
                data["provider"],
                data.get("category", "cs"),
                data.get("cert_type", "شهادة خبرة معتمدة 📜"),
                data.get("cost", "مجاني 100% 🆓"),
                data.get("mode", "عن بُعد (Online) 🌐"),
                data.get("duration", "مرن / بحسب وتيرتك"),
                data.get("description", "برنامج تدريبي وتطبيقي يمنح شهادة خبرة وإنجاز عملية."),
                data.get("requirements", "• شغف بالتعلم والتقنية\n• جهاز حاسب واتصال بالإنترنت"),
                data["url"]
            ))
            conn.commit()
            return True, cursor.lastrowid
        except sqlite3.IntegrityError:
            # موجودة مسبقاً
            cursor.execute("SELECT id FROM opportunities WHERE uid = ?", (uid,))
            row = cursor.fetchone()
            return False, (row["id"] if row else -1)

def get_latest_opportunities(category: str = "all", limit: int = 10, offset: int = 0):
    """جلب أحدث الفرص المتاحة حسب التصنيف أو للجميع"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if category and category != "all":
            cursor.execute("""
                SELECT * FROM opportunities 
                WHERE is_active = 1 AND category = ?
                ORDER BY id DESC LIMIT ? OFFSET ?
            """, (category, limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM opportunities 
                WHERE is_active = 1
                ORDER BY id DESC LIMIT ? OFFSET ?
            """, (limit, offset))
        return cursor.fetchall()

def get_total_opportunities_count(category: str = "all") -> int:
    """حساب إجمالي عدد الفرص المتاحة"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if category and category != "all":
            cursor.execute("SELECT COUNT(*) as cnt FROM opportunities WHERE is_active = 1 AND category = ?", (category,))
        else:
            cursor.execute("SELECT COUNT(*) as cnt FROM opportunities WHERE is_active = 1")
        row = cursor.fetchone()
        return row["cnt"] if row else 0

def get_opportunity_by_id(opp_id: int):
    """جلب تفاصيل فرصة بواسطة معرفها"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,))
        return cursor.fetchone()

def search_opportunities(query: str, limit: int = 10):
    """البحث في الفرص باستخدام كلمات مفتاحية"""
    term = f"%{query.strip()}%"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM opportunities 
            WHERE is_active = 1 AND (
                title LIKE ? OR provider LIKE ? OR description LIKE ? OR requirements LIKE ?
            )
            ORDER BY id DESC LIMIT ?
        """, (term, term, term, term, limit))
        return cursor.fetchall()

def is_notification_sent(opportunity_id: int, target_id: str) -> bool:
    """التحقق مما إذا تم إرسال إشعار هذه الفرصة للهدف سابقاً"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sent_logs WHERE opportunity_id = ? AND target_id = ?", (opportunity_id, str(target_id)))
        return cursor.fetchone() is not None

def log_notification_sent(opportunity_id: int, target_id: str):
    """تسجيل إرسال الإشعار لمنع تكراره مستقبلاً"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sent_logs (opportunity_id, target_id) VALUES (?, ?)", (opportunity_id, str(target_id)))
        conn.commit()

def get_stats():
    """إحصائيات النظام وقاعدة البيانات"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total_opps FROM opportunities")
        total_opps = cursor.fetchone()["total_opps"]
        
        cursor.execute("SELECT COUNT(*) as total_subs FROM subscribers WHERE is_active = 1")
        total_subs = cursor.fetchone()["total_subs"]
        
        cursor.execute("SELECT category, COUNT(*) as cnt FROM opportunities GROUP BY category")
        cats = {row["category"]: row["cnt"] for row in cursor.fetchall()}
        
        return {
            "total_opportunities": total_opps,
            "active_subscribers": total_subs,
            "categories": cats
        }

def add_channel(channel_id: str, title: str = "", username: str = "") -> bool:
    """تسجيل قناة أو مجموعة للبث التلقائي"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO channels (channel_id, title, username, is_active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(channel_id) DO UPDATE SET
                title = excluded.title,
                username = excluded.username,
                is_active = 1
        """, (str(channel_id), title, username))
        conn.commit()
        return True

def remove_channel(channel_id: str):
    """إلغاء تفعيل القناة عند مغادرة البوت أو إزالة الصلاحيات"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE channels SET is_active = 0 WHERE channel_id = ?", (str(channel_id),))
        conn.commit()

def get_active_channels():
    """جلب جميع القنوات النشطة للبث التلقائي"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT channel_id, title, username FROM channels WHERE is_active = 1")
        return cursor.fetchall()
