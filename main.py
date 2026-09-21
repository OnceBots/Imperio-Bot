import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from bot.config import BOT_TOKEN
from bot.database import init_db_indexes
from bot.services import start_web_server, auto_cleanup_worker
from bot.handlers import admin, stats, panel, traffic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s"
)
logger = logging.getLogger("ImperioMain")

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    dp.include_router(admin.router)
    dp.include_router(stats.router)
    dp.include_router(panel.router)
    dp.include_router(traffic.router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook eliminado con éxito. Modo Polling activo.")
    except Exception as e:
        logger.error(f"Fallo al eliminar webhook: {e}")

    await init_db_indexes()
    await start_web_server()
    asyncio.create_task(auto_cleanup_worker(bot))

    logger.info("Imperio Bot inicializado y listo para producción.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot apagado ordenadamente.")
