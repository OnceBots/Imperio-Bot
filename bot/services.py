import asyncio
import logging
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from bot.config import PORT
from bot.database import cleanup_queue_col, groups_col

logger = logging.getLogger("ImperioServices")

async def execute_cleanup(chat_id: int, bot: Bot) -> int:
    records = await cleanup_queue_col.find({"chat_id": chat_id}).to_list(length=1000)
    if not records:
        await groups_col.update_one(
            {"_id": chat_id},
            {"$set": {"next_cleanup": datetime.now() + timedelta(hours=12)}},
            upsert=True
        )
        return 0

    message_ids = [r["message_id"] for r in records]
    total_purged = 0
    chunk_size = 100

    for i in range(0, len(message_ids), chunk_size):
        chunk = message_ids[i:i + chunk_size]
        try:
            await bot.delete_messages(chat_id, chunk)
            total_purged += len(chunk)
        except TelegramBadRequest:
            for mid in chunk:
                try:
                    await bot.delete_message(chat_id, mid)
                    total_purged += 1
                except Exception:
                    pass
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except Exception as e:
            logger.warning(f"Error en purga de chat {chat_id}: {e}")
        await asyncio.sleep(0.5)

    await cleanup_queue_col.delete_many({"chat_id": chat_id, "message_id": {"$in": message_ids}})
    await groups_col.update_one(
        {"_id": chat_id},
        {"$set": {"next_cleanup": datetime.now() + timedelta(hours=12)}}
    )
    return total_purged

async def auto_cleanup_worker(bot: Bot):
    while True:
        try:
            now = datetime.now()
            cursor = groups_col.find({"next_cleanup": {"$lte": now}})
            async for group in cursor:
                chat_id = group["_id"]
                purged = await execute_cleanup(chat_id, bot)
                if purged > 0:
                    try:
                        notice = await bot.send_message(
                            chat_id,
                            f"🛡️ <b>MANTENIMIENTO DEL SISTEMA</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"⚡ <b>Acción:</b> Limpieza Cíclica (12h)\n"
                            f"🗑️ <b>Archivos purgados:</b> <code>{purged}</code>\n"
                            f"<i>Este mensaje se autodestruirá en 45 segundos.</i>"
                        )
                        await asyncio.sleep(45)
                        await notice.delete()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error en worker de limpieza: {e}")
        await asyncio.sleep(60)

async def web_health_handler(_: web.Request):
    return web.Response(text="Imperio Bot Core Engine: Running Smoothly", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", web_health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
