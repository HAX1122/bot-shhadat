import asyncio
import html
import logging
import sys
import httpx

import config
import database
from data_seed import seed_database
import scraper
from bot import format_opportunity_card

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("cli_monitor")

def send_telegram_message(token: str, chat_id: str, text: str, url: str) -> bool:
    """إرسال رسالة عبر Telegram Bot API مع زر التقديم المباشر"""
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "🔗 التقديم والتسجيل في المنصة الرسمية", "url": url}]
            ]
        }
    }
    try:
        res = httpx.post(endpoint, json=payload, timeout=15)
        if res.status_code == 200:
            return True
        else:
            logger.error(f"Telegram API error ({res.status_code}): {res.text}")
    except Exception as e:
        logger.error(f"Network error sending to {chat_id}: {e}")
    return False

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    logger.info("Initializing database...")
    seed_database()
    
    logger.info("Starting sources scan...")
    new_opps = scraper.scan_sources()
    logger.info(f"Scan finished. Found {len(new_opps)} new opportunities.")
    
    if not new_opps:
        print("No new opportunities detected in this scan.")
        return 0
        
    subscribers = database.get_active_subscribers()
    channel_id = config.TELEGRAM_CHANNEL_ID.strip() if config.TELEGRAM_CHANNEL_ID else None
    
    sent_count = 0
    for opp in new_opps:
        opp_id = opp["id"]
        card_text = format_opportunity_card(opp, is_broadcast=True)
        target_url = opp["url"]
        
        # 1. إرسال للقناة الرسمية إن كانت محددة
        if channel_id and not database.is_notification_sent(opp_id, channel_id):
            if send_telegram_message(config.TELEGRAM_BOT_TOKEN, channel_id, card_text, target_url):
                database.log_notification_sent(opp_id, channel_id)
                sent_count += 1
                logger.info(f"Broadcasted opp #{opp_id} to channel {channel_id}")
                
        # 2. إرسال للمشتركين النشطين
        for sub in subscribers:
            user_id = str(sub["user_id"])
            if not database.is_notification_sent(opp_id, user_id):
                if send_telegram_message(config.TELEGRAM_BOT_TOKEN, user_id, card_text, target_url):
                    database.log_notification_sent(opp_id, user_id)
                    sent_count += 1
                    logger.info(f"Sent opp #{opp_id} to user {user_id}")
                    
    print(f"Successfully processed {len(new_opps)} new opportunities and sent {sent_count} notifications.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
