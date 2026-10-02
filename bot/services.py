from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from aiohttp import web
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from .config import settings
from .database import cleanup_queue_col, groups_col, utcnow, audit

logger = logging.getLogger("Imperio.services")

async def safe_delete(bot: Bot, chat_id: int, message_id: int) -> bool:
    try:
        await bot.delete_message(chat_id, message_id)
        return True
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after)
        try:
            await bot.delete_message(chat_id, message_id)
            return True
        except Exception:
            return False
    except Exception:
        return False

async def delete_many_safe(bot: Bot, chat_id: int, message_ids: list[int]) -> int:
    total = 0
    for i in range(0, len(message_ids), 100):
        chunk = message_ids[i:i+100]
        try:
            await bot.delete_messages(chat_id=chat_id, message_ids=chunk)
            total += len(chunk)
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await bot.delete_messages(chat_id=chat_id, message_ids=chunk)
                total += len(chunk)
            except Exception:
                for mid in chunk:
                    if await safe_delete(bot, chat_id, mid): total += 1
        except Exception:
            for mid in chunk:
                if await safe_delete(bot, chat_id, mid): total += 1
    return total

async def enqueue_media(chat_id: int, message_id: int) -> None:
    await cleanup_queue_col.update_one(
        {"chat_id": chat_id, "message_id": message_id},
        {"$setOnInsert": {"created_at": utcnow()}},
        upsert=True,
    )
    await groups_col.update_one(
        {"_id": chat_id, "next_cleanup": {"$exists": False}},
        {"$set": {"next_cleanup": utcnow() + timedelta(hours=settings.auto_cleanup_hours)}},
        upsert=True,
    )

async def execute_cleanup(bot: Bot, chat_id: int) -> int:
    docs = await cleanup_queue_col.find({"chat_id": chat_id}).sort("message_id", 1).limit(5000).to_list(length=5000)
    if not docs:
        await groups_col.update_one({"_id": chat_id}, {"$set": {"next_cleanup": utcnow() + timedelta(hours=settings.auto_cleanup_hours)}}, upsert=True)
        return 0

    ids = [int(d["message_id"]) for d in docs]
    removed = 0
    successful_ids: list[int] = []
    for i in range(0, len(ids), settings.cleanup_batch_size):
        chunk = ids[i:i+settings.cleanup_batch_size]
        count = await delete_many_safe(bot, chat_id, chunk)
        removed += count
        # Telegram puede omitir mensajes inexistentes; retiramos la cola solo después de intentar el lote.
        successful_ids.extend(chunk)
        await asyncio.sleep(0.15)

    if successful_ids:
        await cleanup_queue_col.delete_many({"chat_id": chat_id, "message_id": {"$in": successful_ids}})
    await groups_col.update_one(
        {"_id": chat_id},
        {"$set": {"next_cleanup": utcnow() + timedelta(hours=settings.auto_cleanup_hours)}},
        upsert=True,
    )
    await audit(chat_id, 0, "auto_cleanup", details=f"removed={removed}")
    return removed

async def auto_cleanup_worker(bot: Bot) -> None:
    while True:
        try:
            if settings.auto_cleanup_enabled:
                now = utcnow()
                async for group in groups_col.find({"next_cleanup": {"$lte": now}}):
                    try:
                        await execute_cleanup(bot, int(group["_id"]))
                    except Exception:
                        logger.exception("Fallo en limpieza automática de %s", group.get("_id"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker de limpieza caído temporalmente")
        await asyncio.sleep(60)

async def delayed_delete(bot: Bot, chat_id: int, message_id: int, delay: int) -> None:
    if delay > 0:
        await asyncio.sleep(delay)
    await safe_delete(bot, chat_id, message_id)

async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "imperio-otomano-bot"})

async def start_web_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", settings.port).start()
    return runner
