from __future__ import annotations

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from bot.config import settings
from bot.database import init_db_indexes, ping_db, close_db
from bot.services import start_web_server, auto_cleanup_worker
from bot.handlers import admin, panel, traffic, stats, help as help_handler

logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO), format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger=logging.getLogger("ImperioMain")

async def set_commands(bot:Bot):
    group_cmds=[
        BotCommand(command="help",description="Ayuda y comandos"),
        BotCommand(command="panel",description="Abrir panel administrativo"),
        BotCommand(command="promotestaff",description="Registrar/promover Staff"),
        BotCommand(command="del",description="Eliminar mensaje respondido"),
        BotCommand(command="ban",description="Banear usuario"),
        BotCommand(command="unban",description="Quitar baneo"),
        BotCommand(command="mute",description="Silenciar usuario"),
        BotCommand(command="unmute",description="Quitar silencio"),
        BotCommand(command="warn",description="Advertir usuario"),
        BotCommand(command="unwarn",description="Quitar advertencias"),
        BotCommand(command="delall",description="Purga de usuario"),
        BotCommand(command="pin",description="Fijar mensaje"),
        BotCommand(command="unpin",description="Quitar fijados"),
        BotCommand(command="etiqueta",description="Cambiar título Staff"),
        BotCommand(command="aportes",description="Ver aportes"),
        BotCommand(command="topaportes",description="Top aportes"),
        BotCommand(command="leyes",description="Mostrar reglas"),
        BotCommand(command="s",description="Difusión como bot"),
    ]
    await bot.set_my_commands(group_cmds,scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands([BotCommand(command="start",description="Abrir Imperio Bot"),BotCommand(command="help",description="Ver ayuda")],scope=BotCommandScopeAllPrivateChats())

async def main():
    bot=Bot(token=settings.bot_token,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp=Dispatcher()
    dp.include_router(panel.router)
    dp.include_router(admin.router)
    dp.include_router(stats.router)
    dp.include_router(help_handler.router)
    dp.include_router(traffic.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await init_db_indexes()
    await ping_db()
    await set_commands(bot)
    web_runner=await start_web_server()
    cleanup_task=asyncio.create_task(auto_cleanup_worker(bot))
    logger.info("Imperio Bot listo")
    try:
        await dp.start_polling(bot,allowed_updates=dp.resolve_used_update_types())
    finally:
        cleanup_task.cancel()
        with __import__('contextlib').suppress(asyncio.CancelledError): await cleanup_task
        await web_runner.cleanup()
        await close_db()
        await bot.session.close()

if __name__=="__main__":
    try: asyncio.run(main())
    except (KeyboardInterrupt,SystemExit): logger.info("Bot detenido")
