import re
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, Bot, F
from aiogram.enums import ChatMemberStatus, MessageEntityType
from aiogram.types import Message, ChatMemberAdministrator
from bot.config import LINK_REGEX, OWNER_IDS
from bot.database import (
    is_admin,
    get_cached_blacklist,
    cleanup_queue_col,
    groups_col,
    stats_col,
    promote_staff,
    _PROMOTED_STAFF_CACHE
)

logger = logging.getLogger("ImperioTraffic")
router = Router()

@router.message(F.new_chat_members)
async def anti_bot_guard(message: Message, bot: Bot):
    if message.chat.type not in ["group", "supergroup"]:
        return
    adder_is_admin = await is_admin(message.chat.id, message.from_user.id, bot)
    for new_member in message.new_chat_members:
        if new_member.is_bot and new_member.id != bot.id and not adder_is_admin:
            try:
                await bot.ban_chat_member(message.chat.id, new_member.id)
                alert = await message.reply(f"🛡️ <b>ANTI-BOT:</b> Se expulsó a <code>{new_member.first_name}</code>.")
                await asyncio.sleep(8)
                await alert.delete()
            except Exception:
                pass

@router.message()
async def central_message_traffic_controller(message: Message, bot: Bot):
    if message.chat.type not in ["group", "supergroup"]:
        return

    # 1. Anti-Bot intrusos
    if message.from_user.is_bot and message.from_user.id != bot.id:
        if not await is_admin(message.chat.id, message.from_user.id, bot):
            try:
                await bot.ban_chat_member(message.chat.id, message.from_user.id)
                await message.delete()
            except Exception:
                pass
            return

    # 2. AUTO-PROMOCIÓN SILENCIOSA DE STAFF AL ESCRIBIR EN EL GRUPO
    staff_cache_key = (message.chat.id, message.from_user.id)
    if staff_cache_key not in _PROMOTED_STAFF_CACHE:
        group_data = await groups_col.find_one({"_id": message.chat.id}, {"authorized_users": 1})
        authorized = group_data.get("authorized_users", []) if group_data else []

        if message.from_user.id in authorized or message.from_user.id in OWNER_IDS:
            try:
                member = await bot.get_chat_member(message.chat.id, message.from_user.id)
                if member.status != ChatMemberStatus.CREATOR:
                    if not (isinstance(member, ChatMemberAdministrator) and getattr(member, "can_promote_members", False)):
                        await promote_staff(bot, message.chat.id, message.from_user.id, custom_title="Staff")
                _PROMOTED_STAFF_CACHE.add(staff_cache_key)
            except Exception as e:
                logger.warning(f"Error en auto-promoción: {e}")

    sender_is_admin = await is_admin(message.chat.id, message.from_user.id, bot)
    content = message.text or message.caption or ""

    if not sender_is_admin and content:
        # 3. Filtro de Lista Negra
        blacklist = await get_cached_blacklist(message.chat.id)
        if blacklist:
            content_lower = content.lower()
            for pattern in blacklist:
                if re.search(rf'\b{re.escape(pattern)}\b', content_lower):
                    try:
                        await message.delete()
                        return
                    except Exception:
                        pass

        # 4. Filtro Antienlaces Exhaustivo
        has_url_entity = any(
            e.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK]
            for e in (message.entities or message.caption_entities or [])
        )
        if has_url_entity or LINK_REGEX.search(content):
            try:
                await message.delete()
                return
            except Exception:
                pass

    # 5. Encolado de multimedia para purga cíclica y estadísticas semanales
    if message.photo or message.video or message.document:
        current_week = datetime.now().strftime("%Y-W%V")
        chat_id = message.chat.id
        user_id = message.from_user.id

        # Insertar mensaje en la cola de eliminación
        await cleanup_queue_col.insert_one({
            "chat_id": chat_id,
            "message_id": message.message_id,
            "created_at": datetime.now()
        })

        # Asegurar que el grupo tenga un temporizador de 12h activo
        group_data = await groups_col.find_one({"_id": chat_id}, {"next_cleanup": 1})
        if not group_data or not group_data.get("next_cleanup"):
            await groups_col.update_one(
                {"_id": chat_id},
                {"$set": {"next_cleanup": datetime.now() + timedelta(hours=12)}},
                upsert=True
            )

        # Sumar aporte a las estadísticas
        await stats_col.update_one(
            {"chat_id": chat_id, "user_id": user_id, "week": current_week},
            {
                "$inc": {"count": 1},
                "$set": {"name": message.from_user.first_name}
            },
            upsert=True
        )
