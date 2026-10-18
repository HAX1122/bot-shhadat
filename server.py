import asyncio
import json
import logging
import os
import sys
from telegram import Update

from bot import build_application, background_monitoring_task
import config
import database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("server")

async def http_health_handler(reader, writer):
    """خادم ويب خفيف جداً للاستجابة لفحوصات الصحة (Health Checks) على Render و Railway"""
    try:
        # قراءة سطر الطلب والرؤوس
        line = await reader.readline()
        while True:
            header = await reader.readline()
            if not header or header == b"\r\n":
                break
                
        stats = database.get_stats()
        response_data = {
            "status": "online",
            "service": "Saudi Tech Certs Radar Bot",
            "bot_username": "@Shhadat7atmbot",
            "active_24_7": True,
            "stats": stats
        }
        body = json.dumps(response_data, ensure_ascii=False, indent=2).encode("utf-8")
        
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json; charset=utf-8\r\n"
            b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
            b"Connection: close\r\n"
            b"\r\n" + body
        )
        writer.write(response)
        await writer.drain()
    except Exception as e:
        logger.error(f"Error handling HTTP request: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

async def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    port = int(os.getenv("PORT", config.PORT))
    host = "0.0.0.0"
    
    logger.info(f"Starting lightweight Health Check HTTP server on {host}:{port}...")
    http_server = await asyncio.start_server(http_health_handler, host, port)
    
    logger.info("Initializing Telegram Bot...")
    app = build_application()
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    logger.info("Telegram Bot polling started successfully!")
    
    # تشغيل مهمة الرصد الدوري الخلفية
    monitor_task = asyncio.create_task(background_monitoring_task(app.bot))
    
    logger.info(">>> Bot & Web Service are now running 24/7 <<<")
    
    try:
        async with http_server:
            await http_server.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        monitor_task.cancel()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
