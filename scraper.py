import re
import urllib.parse
import feedparser
import httpx
from bs4 import BeautifulSoup
from database import save_opportunity, get_connection

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# استعلامات الرصد الحي والمستمر في المملكة العربية السعودية
SEARCH_QUERIES = [
    '("سدايا" OR "أكاديمية طويق" OR "مهارات المستقبل") ("ذكاء اصطناعي" OR "علم البيانات" OR "علوم الحاسب" OR معسكر OR تدريب OR تسجيل)',
    '("شهادة خبرة" OR "تدريب على رأس العمل" OR "تمهير" OR "معسكر تدريبي") (تقنية OR برمجة OR داتا OR حاسب OR "ذكاء اصطناعي")',
    '("كاوست" OR "مسك المهارات" OR "الاتحاد السعودي للأمن السيبراني") ("ذكاء اصطناعي" OR معسكر OR تدريب OR تسجيل)',
]

# الكلمات المستبعدة تماماً لمنع الأخبار غير ذات الصلة
EXCLUDED_KEYWORDS = [
    "جبال طويق", "نادي طويق", "محمية", "كرة قدم", "مباراة", "سيارات", 
    "حادث", "أراضي", "عقارات", "سياحة", "أسهم", "طقس", "أمطار", "وفاة"
]

def normalize_arabic(text: str) -> str:
    """توحيد الحروف العربية وتجريد التشكيل لرفع دقة المطابقة"""
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"[\u064B-\u065F\u0640]", "", text)
    return text.lower()

def clean_title(raw_title: str) -> str:
    """تنظيف العنوان من أسماء الصحف والمواقع الإخبارية الملحقة"""
    cleaned = re.sub(r"\s*-\s*(وكالة الأنباء السعودية|صحيفة سبق الإلكترونية|جريدة الرياض|الشرق الأوسط|صحيفة المواطن|عاجل|سويفت نيوز|أرقام|الوطن|اليوم|البوابة التقنية|جريدة المدينة).*$", "", raw_title)
    cleaned = re.sub(r"^(ثقافي|علوم وتقنيات|عام|اقتصادي)\s*/\s*", "", cleaned)
    return cleaned.strip()

def detect_provider(text: str) -> str:
    """استنتاج الجهة المنظمة للبرنامج من النص"""
    t = normalize_arabic(text)
    if "سدايا" in t or "sdaia" in t:
        return "الهيئة السعودية للبيانات والذكاء الاصطناعي (سدايا)"
    elif "طويق" in t or "tuwaiq" in t:
        return "أكاديمية طويق"
    elif "مهارات المستقبل" in t:
        return "مبادرة مهارات المستقبل (وزارة الاتصالات MCIT)"
    elif "مسك" in t or "misk" in t:
        return "مؤسسة مسك (مسك المهارات)"
    elif "كاوست" in t or "kaust" in t:
        return "جامعة الملك عبدالله للعلوم والتقنية (كاوست)"
    elif "تمهير" in t or "هدف" in t:
        return "صندوق تنمية الموارد البشرية (هدف)"
    elif "الاتحاد السعودي للامن السيبراني" in t or "safcsp" in t:
        return "الاتحاد السعودي للأمن السيبراني والبرمجة والدرونز"
    elif "forage" in t:
        return "منصة Forage للخبرة الافتراضية"
    return "جهة وطنية معتمدة بالمملكة"

def detect_category(text: str) -> str:
    """تصنيف الفرصة بدقة عالية مع معالجة السوابق العربية (ال)"""
    t = normalize_arabic(text)
    
    # 1. الذكاء الاصطناعي (له أولوية إذا ذُكر صراحة)
    ai_patterns = [
        r'(ال)?ذكاء\s*(ال)?اصطناعي',
        r'تعلم\s*(ال)?(اله|آله)',
        r'رؤي(ه|ة)\s*(ال)?حاسوب',
        r'توليدي',
        r'\bai\b',
        r'machine\s*learning',
        r'deep\s*learning',
        r'nlp',
    ]
    for pattern in ai_patterns:
        if re.search(pattern, t):
            return "ai"
            
    # 2. علم وتحليل البيانات
    data_patterns = [
        r'(ال)?بيانات',
        r'data',
        r'power\s*bi',
        r'ذكاء\s*(ال)?اعمال',
        r'تحليل\s*(ال)?بيانات',
    ]
    for pattern in data_patterns:
        if re.search(pattern, t):
            return "data"
            
    # 3. الأمن السيبراني
    cyber_patterns = [
        r'(ال)?سيبران',
        r'cyber',
        r'امن\s*(ال)?معلومات',
        r'حماي(ه|ة)\s*(ال)?بيانات',
    ]
    for pattern in cyber_patterns:
        if re.search(pattern, t):
            return "cyber"
            
    # 4. علوم الحاسب والبرمجة
    return "cs"

def is_valid_opportunity(title: str, summary: str) -> bool:
    """التحقق من أن الخبر يمثل فرصة تدريبية أو معسكراً أو شهادة حقيقية"""
    combined = normalize_arabic(f"{title} {summary}")
    
    # فحص الكلمات المستبعدة
    for ex in EXCLUDED_KEYWORDS:
        if normalize_arabic(ex) in combined:
            return False
            
    # التحقق من وجود كلمات تدل على إطلاق أو تسجيل أو معسكر أو تدريب
    action_words = [
        "معسكر", "تسجيل", "تدريب", "شهاده", "شهادات", "منحه", "منح", "هاكثون", "تحدي", 
        "اطلاق", "تعلن", "فتح باب التقديم", "برنامج", "خبره", "تاهيل", "تمهير", "مسار"
    ]
    has_action = any(w in combined for w in action_words)
    
    # التحقق من وجود كلمات تقنية
    tech_words = [
        "ذكاء", "بيانات", "حاسب", "برمج", "تقني", "سيبران", 
        "سحاب", "تطوير", "ai", "data", "cyber", "software", "كود", "دبلوم", "ماجستير"
    ]
    has_tech = any(w in combined for w in tech_words)
    
    return has_action and has_tech

def fetch_rss_feed(feed_url: str):
    """جلب وتحليل عناصر تغذية RSS مع دعم Headers حقيقية"""
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=12) as client:
            res = client.get(feed_url)
            if res.status_code == 200:
                return feedparser.parse(res.text)
    except Exception as e:
        print(f"Error fetching feed {feed_url}: {e}")
    return None

def scan_sources() -> list[dict]:
    """
    فحص جميع المصادر واكتشاف الفرص والشهادات الجديدة
    تعيد قائمة بجميع الفرص الجديدة التي تم إدخالها بنجاح في قاعدة البيانات
    """
    new_opportunities = []
    
    for query in SEARCH_QUERIES:
        encoded_query = urllib.parse.quote(query)
        feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ar&gl=SA&ceid=SA:ar"
        feed = fetch_rss_feed(feed_url)
        
        if not feed or not feed.entries:
            continue
            
        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            url = entry.get("link", "")
            
            clean_summary = BeautifulSoup(summary, "html.parser").get_text(strip=True) if summary else ""
            
            if not is_valid_opportunity(title, clean_summary):
                continue
                
            cleaned_title = clean_title(title)
            provider = detect_provider(f"{title} {clean_summary}")
            category = detect_category(f"{title} {clean_summary}")
            
            opp_dict = {
                "title": cleaned_title,
                "provider": provider,
                "category": category,
                "cert_type": "شهادة معتمدة / تدريب على رأس العمل 📜",
                "cost": "مجاني 100% 🆓",
                "mode": "عن بُعد / حضوري (بحسب الإعلان الرسمي) 🌐",
                "duration": "محدد في تفاصيل التسجيل",
                "description": clean_summary if clean_summary else f"إعلان رسمي لفرصة ومعسكر تدريبي معتمد من {provider}.",
                "requirements": "• الإلمام بالأساسيات التقنية والشغف بالتعلم\n• التقديم متاح للسعوديين والمقيمين المستوفين للشروط\n• التسجيل عبر الرابط الرسمي المرفق",
                "url": url
            }
            
            is_new, opp_id = save_opportunity(opp_dict)
            if is_new:
                opp_dict["id"] = opp_id
                new_opportunities.append(opp_dict)
                
    return new_opportunities

def reclassify_existing_opportunities():
    """إعادة تصنيف السجلات الحالية في قاعدة البيانات لضمان دقة التصنيف"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, provider, description FROM opportunities")
        rows = cursor.fetchall()
        updated = 0
        for row in rows:
            combined = f"{row['title']} {row['provider']} {row['description']}"
            new_cat = detect_category(combined)
            new_prov = detect_provider(combined)
            cursor.execute("UPDATE opportunities SET category = ?, provider = ? WHERE id = ?", (new_cat, new_prov, row["id"]))
            updated += 1
        conn.commit()
    return updated

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print("Testing scanner & reclassification...")
    reclassified = reclassify_existing_opportunities()
    print(f"Reclassified {reclassified} existing opportunities.")
    found = scan_sources()
    print(f"Discovered {len(found)} new opportunities in this run.")
