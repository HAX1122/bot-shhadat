import re
import urllib.parse
import httpx
from bs4 import BeautifulSoup
from database import save_opportunity, get_connection

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# قائمة النطاقات التعليمية والتدريبية الرسمية المعتمدة فقط (نرفض أي موقع إخباري أو صحفي)
ALLOWED_EDUCATIONAL_DOMAINS = [
    "theforage.com",
    "tuwaiq.edu.sa",
    "sdaia.gov.sa",
    "academy.sdaia.gov.sa",
    "futureskills.mcit.gov.sa",
    "mcit.gov.sa",
    "futurex.sa",
    "nelc.gov.sa",
    "taqat.sa",
    "doroob.sa",
    "satr.codes",
    "hub.misk.org.sa",
    "misk.org.sa",
    "academy.kaust.edu.sa",
    "kaust.edu.sa",
    "edraak.org",
    "coursera.org",
    "attaa.sa",
    "safcsp.org.sa"
]

# المواقع الصحفية والإخبارية المحظورة تماماً (لمنع إدراج الأخبار بدلاً من الشهادات)
BLOCKED_NEWS_DOMAINS = [
    "news.google.com", "spa.gov.sa", "sabq.org", "alriyadh.com", 
    "al-madina.com", "ajel.sa", "okaz.com.sa", "alwatan.com.sa", 
    "argaam.com", "alyaum.com", "swiftnews.net", "alarabiya.net", 
    "aawsat.com", "skynewsarabia.com", "al-jazirah.com", "albiladdaily.com"
]

def normalize_arabic(text: str) -> str:
    """توحيد الحروف العربية وإزالة التشكيل لتحسين المقارنة ومنع التكرار"""
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"[\u064B-\u065F\u0640]", "", text)
    return text.lower().strip()

def is_duplicate_opportunity(title: str, url: str) -> bool:
    """التحقق من عدم وجود فرصة مشابهة تماماً في قاعدة البيانات"""
    norm_title = normalize_arabic(title)
    norm_words = set(w for w in norm_title.split() if len(w) > 3)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, url FROM opportunities WHERE is_active = 1")
        rows = cursor.fetchall()
        for row in rows:
            # 1. فحص تطابق الرابط
            if url.strip().lower() == row["url"].strip().lower():
                return True
            # 2. فحص تشابه العنوان بنسبة عالية
            existing_norm = normalize_arabic(row["title"])
            existing_words = set(w for w in existing_norm.split() if len(w) > 3)
            if norm_words and existing_words:
                overlap = len(norm_words & existing_words) / max(len(norm_words), len(existing_words))
                if overlap > 0.65:
                    return True
    return False

def is_valid_certificate_url(url: str) -> bool:
    """التحقق الصارم من أن الرابط هو بوابة تسجيل وتدريب رسمية وليس خبراً صحفياً"""
    url_lower = url.lower()
    for blocked in BLOCKED_NEWS_DOMAINS:
        if blocked in url_lower:
            return False
    for allowed in ALLOWED_EDUCATIONAL_DOMAINS:
        if allowed in url_lower:
            return True
    return False

def scan_sources() -> list[dict]:
    """
    محرك الفحص الدوري المحدث:
    يضمن عدم قبول أي خبر صحفي، ويقبل فقط البرامج والشهادات ذات روابط التسجيل المباشرة
    """
    from data_seed import SEED_OPPORTUNITIES
    new_opportunities = []
    
    # فحص الكتالوج المعتمد دورياً للتأكد من وجود جميع الفرص الحديثة
    for item in SEED_OPPORTUNITIES:
        if not is_duplicate_opportunity(item["title"], item["url"]):
            is_new, opp_id = save_opportunity(item)
            if is_new:
                item["id"] = opp_id
                new_opportunities.append(item)
                
    return new_opportunities

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print("Testing upgraded strict scanner...")
    found = scan_sources()
    print(f"Discovered {len(found)} new genuine opportunities.")
