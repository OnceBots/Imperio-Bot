async def main():
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    # Middleware para eliminar automáticamente cualquier mensaje
    # que empiece con "/" dentro de grupos y supergrupos.
    async def delete_group_commands(handler, event, data):
        chat = getattr(event, "chat", None)
        text = getattr(event, "text", None)

        if (
            chat
            and chat.type in {"group", "supergroup"}
            and text
            and text.startswith("/")
        ):
            try:
                await event.delete()
                logger.info(
                    "Comando eliminado en %s: %s",
                    chat.id,
                    text
                )
            except Exception as e:
                logger.warning(
                    "No se pudo eliminar el comando '%s': %s",
                    text,
                    e
                )

        # Importante: seguimos con el procesamiento normal del handler.
        return await handler(event, data)

    # Se ejecuta antes de los handlers, por lo que también afecta
    # a comandos que tengan handlers específicos (/ban, /mute, etc.).
    dp.message.outer_middleware(delete_group_commands)

    dp.include_router(panel.router)
    dp.include_router(admin.router)
    dp.include_router(stats.router)
    dp.include_router(help_handler.router)
    dp.include_router(traffic.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await init_db_indexes()
    await ping_db()
    await set_commands(bot)

    web_runner = await start_web_server()
    cleanup_task = asyncio.create_task(auto_cleanup_worker(bot))

    logger.info("Imperio Bot listo")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )

    finally:
        cleanup_task.cancel()

        with __import__('contextlib').suppress(asyncio.CancelledError):
            await cleanup_task

        await web_runner.cleanup()
        await close_db()
        await bot.session.close()
