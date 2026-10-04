from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
)

from bot.config import settings
from bot.database import (
    init_db_indexes,
    ping_db,
    close_db,
    is_admin,
)
from bot.services import start_web_server, auto_cleanup_worker
from bot.handlers import admin, panel, traffic, stats, help as help_handler


logging.basicConfig(
    level=getattr(settings, "log_level", logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("ImperioMain")


async def set_commands(bot: Bot):
    group_cmds = [
        BotCommand(command="help", description="Ayuda y comandos"),
        BotCommand(command="panel", description="Abrir panel administrativo"),
        BotCommand(command="promotestaff", description="Registrar/promover Staff"),
        BotCommand(command="del", description="Eliminar mensaje respondido"),
        BotCommand(command="ban", description="Banear usuario"),
        BotCommand(command="unban", description="Quitar baneo"),
        BotCommand(command="mute", description="Silenciar usuario"),
        BotCommand(command="unmute", description="Quitar silencio"),
        BotCommand(command="warn", description="Advertir usuario"),
        BotCommand(command="unwarn", description="Quitar advertencias"),
        BotCommand(command="delall", description="Purga de usuario"),
        BotCommand(command="pin", description="Fijar mensaje"),
        BotCommand(command="unpin", description="Quitar fijados"),
        BotCommand(command="etiqueta", description="Cambiar título Staff"),
        BotCommand(command="aportes", description="Ver aportes"),
        BotCommand(command="topaportes", description="Top aportes"),
        BotCommand(command="leyes", description="Mostrar reglas"),
        BotCommand(command="s", description="Difusión como bot"),
    ]

    await bot.set_my_commands(
        group_cmds,
        scope=BotCommandScopeAllGroupChats(),
    )

    await bot.set_my_commands(
        [
            BotCommand(
                command="start",
                description="Abrir Imperio Bot",
            ),
            BotCommand(
                command="help",
                description="Ver ayuda",
            ),
        ],
        scope=BotCommandScopeAllPrivateChats(),
    )


async def main():
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
    )

    dp = Dispatcher()

    # =========================================================
    # ELIMINAR COMANDOS DE USUARIOS NORMALES
    # =========================================================
    #
    # Funcionamiento:
    #
    # - Owner / administrador / Staff autorizado:
    #       El comando sigue hacia el handler normalmente.
    #
    # - Usuario normal:
    #       El comando se elimina y NO se ejecuta.
    #
    # Solo se aplica en grupos y supergrupos.
    # =========================================================
    async def delete_group_commands(handler, event, data):
        chat = getattr(event, "chat", None)
        text = getattr(event, "text", None)
        user = getattr(event, "from_user", None)

        # -----------------------------------------------------
        # Solo nos interesan:
        #   - grupos / supergrupos
        #   - mensajes de texto
        #   - mensajes que comiencen con /
        #   - usuarios válidos
        # -----------------------------------------------------
        if not (
            chat
            and chat.type in {"group", "supergroup"}
            and text
            and text.startswith("/")
            and user
        ):
            return await handler(event, data)

        # -----------------------------------------------------
        # Comprobar permisos mediante la función del proyecto.
        #
        # is_admin() reconoce:
        #   - Owner configurado
        #   - Staff autorizado
        #   - Administradores de Telegram
        #   - Creador del grupo
        # -----------------------------------------------------
        try:
            user_is_admin = await is_admin(
                chat.id,
                user.id,
                bot,
            )

        except Exception as e:
            # Por seguridad, si falla la comprobación de permisos,
            # NO permitimos ejecutar el comando.
            logger.warning(
                "Error comprobando permisos del usuario %s "
                "en chat %s para el comando '%s': %s",
                user.id,
                chat.id,
                text,
                e,
            )

            try:
                await event.delete()

                logger.info(
                    "Comando eliminado por fallo de comprobación "
                    "de permisos | chat=%s | user=%s | text=%s",
                    chat.id,
                    user.id,
                    text,
                )

            except Exception as delete_error:
                logger.warning(
                    "No se pudo eliminar el comando '%s': %s",
                    text,
                    delete_error,
                )

            return

        # =====================================================
        # USUARIO COMÚN
        # =====================================================
        if not user_is_admin:
            try:
                await event.delete()

                logger.info(
                    "Comando de usuario eliminado | "
                    "chat=%s | user=%s | text=%s",
                    chat.id,
                    user.id,
                    text,
                )

            except Exception as e:
                logger.warning(
                    "No se pudo eliminar el comando '%s': %s",
                    text,
                    e,
                )

            # NO continuar al handler.
            # El usuario común no puede ejecutar comandos.
            return

        # =====================================================
        # ADMIN / STAFF / OWNER
        # =====================================================
        #
        # No eliminamos el mensaje aquí.
        #
        # Dejamos que el router correspondiente procese:
        #
        # /ban
        # /mute
        # /warn
        # /panel
        # /del
        # etc.
        #
        # Los propios handlers administrativos ya eliminan
        # el mensaje de comando cuando corresponde.
        # =====================================================
        logger.debug(
            "Comando permitido | chat=%s | user=%s | text=%s",
            chat.id,
            user.id,
            text,
        )

        return await handler(event, data)

    # Middleware externo:
    # se ejecuta antes de los handlers.
    dp.message.outer_middleware(delete_group_commands)

    # =========================================================
    # ROUTERS
    # =========================================================
    dp.include_router(panel.router)
    dp.include_router(admin.router)
    dp.include_router(stats.router)
    dp.include_router(help_handler.router)
    dp.include_router(traffic.router)

    # =========================================================
    # INICIALIZACIÓN
    # =========================================================
    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await init_db_indexes()
    await ping_db()
    await set_commands(bot)

    web_runner = await start_web_server()

    cleanup_task = asyncio.create_task(
        auto_cleanup_worker(bot)
    )

    logger.info("Imperio Bot listo")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )

    finally:
        cleanup_task.cancel()

        with __import__("contextlib").suppress(
            asyncio.CancelledError
        ):
            await cleanup_task

        await web_runner.cleanup()
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot detenido")
