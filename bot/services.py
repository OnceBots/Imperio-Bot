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
    """Elimina del grupo los mensajes encolados y reinicia el reloj a 12 horas."""
    records = await cleanup_queue_col.find({"chat_id": chat_id}).to_list(length=1000)
    
    # Si no hay archivos, únicamente reinicia el reloj a 12 horas hacia adelante
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
            # Borrado masivo (funciona para mensajes de menos de 48h)
            await bot.delete_messages(chat_id, chunk)
            total_purged += len(chunk)
        except TelegramBadRequest as e:
            logger.warning(f"Fallo en lote en chat {chat_id} ({e}), intentando borrado individual...")
            # Fallback individual para mensajes con restricciones o más antiguos
            for mid in chunk:
                try:
                    await bot.delete_message(chat_id, mid)
                    total_purged += 1
                except Exception:
                    pass
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except Exception as e:
            logger.error(f"Error inesperado borrando en chat {chat_id}: {e}")

        await asyncio.sleep(0.5)

    # Limpiar la cola en la base de datos de los mensajes procesados
    await cleanup_queue_col.delete_many({"chat_id": chat_id, "message_id": {"$in": message_ids}})
    
    # Reiniciar el reloj de limpieza a 12 horas a partir de este instante
    await groups_col.update_one(
        {"_id": chat_id},
        {"$set": {"next_cleanup": datetime.now() + timedelta(hours=12)}}
    )
    return total_purged

async def auto_cleanup_worker(bot: Bot):
    """Revisa cada 60 segundos si algún grupo cumplió su ciclo de 12 horas."""
    while True:
        try:
            now = datetime.now()
            # Buscar grupos cuya fecha de limpieza ya venció
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
                            f"⚡ <b>Acción:</b> Limpieza Cíclica (12 Horas)\n"
                            f"🗑️ <b>Archivos purgados:</b> <code>{purged}</code>\n"
                            f"<i>Este aviso se autodestruirá en 45 segundos.</i>"
                        )
                        await asyncio.sleep(45)
                        await notice.delete()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error en auto_cleanup_worker: {e}")

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
