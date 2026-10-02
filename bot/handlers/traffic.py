from __future__ import annotations

import asyncio
import re
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.enums import ChatMemberStatus

from ..config import settings, LINK_REGEX
from ..database import is_admin, get_blacklist, cleanup_queue_col, groups_col, stats_col, audit
from ..services import safe_delete, enqueue_media
from ..utils import is_group, contains_link, is_media, service_category

router = Router()

async def service_enabled(category: str) -> bool:
    mapping = {
        "join": settings.auto_delete_join_messages,
        "leave": settings.auto_delete_leave_messages,
        "pin": settings.auto_delete_pin_messages,
        "group_change": settings.auto_delete_group_change_messages,
        "other": settings.auto_delete_other_service_messages,
    }
    return mapping.get(category, False)

@router.message()
async def traffic_controller(message: Message, bot: Bot):
    if not is_group(message):
        return

    # 1) Mensajes de servicio: se eliminan primero, pero se conserva la defensa anti-bot en entradas.
    group = await groups_col.find_one({"_id": message.chat.id}, {"anti_bot": 1, "service_cleanup": 1, "authorized_users": 1}) or {}
    anti_bot_enabled = bool(group.get("anti_bot", settings.anti_bot))
    service_cleanup_enabled = bool(group.get("service_cleanup", settings.auto_delete_service_messages))

    if message.new_chat_members:
        if anti_bot_enabled:
            adder_is_admin = await is_admin(message.chat.id, message.from_user.id if message.from_user else 0, bot)
            for member in message.new_chat_members:
                if member.is_bot and member.id != (await bot.me()).id and not adder_is_admin:
                    try:
                        await bot.ban_chat_member(message.chat.id, member.id, revoke_messages=True)
                        await audit(message.chat.id, 0, "anti_bot", member.id)
                    except Exception:
                        pass
        if service_cleanup_enabled and await service_enabled("join"):
            await safe_delete(bot, message.chat.id, message.message_id)
        return

    if message.left_chat_member:
        if service_cleanup_enabled and await service_enabled("leave"):
            await safe_delete(bot, message.chat.id, message.message_id)
        return

    if any(getattr(message, field, None) for field in (
        "pinned_message", "new_chat_title", "new_chat_photo", "delete_chat_photo",
        "group_chat_created", "supergroup_chat_created", "channel_chat_created",
        "message_auto_delete_timer_changed", "boost_added", "chat_background_set",
        "forum_topic_created", "forum_topic_edited", "forum_topic_closed", "forum_topic_reopened",
        "general_forum_topic_hidden", "general_forum_topic_unhidden", "video_chat_scheduled",
        "video_chat_started", "video_chat_ended", "video_chat_participants_invited",
        "community_chat_added", "community_chat_removed", "community_chat_joined",
        "giveaway_created", "giveaway", "giveaway_winners", "giveaway_completed",
    )):
        category = service_category(message)
        if service_cleanup_enabled and await service_enabled(category):
            await safe_delete(bot, message.chat.id, message.message_id)
        return

    # 2) Bots intrusos.
    if message.from_user and message.from_user.is_bot and message.from_user.id != (await bot.me()).id:
        sender_is_admin = await is_admin(message.chat.id, message.from_user.id, bot)
        if not sender_is_admin:
            await safe_delete(bot, message.chat.id, message.message_id)
            try: await bot.ban_chat_member(message.chat.id, message.from_user.id, revoke_messages=True)
            except Exception: pass
            return

    # 3) Re-sincronización silenciosa de Staff persistente.
    if message.from_user and message.from_user.id in group.get("authorized_users", []):
        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            if member.status != ChatMemberStatus.CREATOR and not (getattr(member, "can_delete_messages", False) and getattr(member, "can_restrict_members", False)):
                from ..database import promote_staff
                title = group.get("staff_details", {}).get(str(message.from_user.id), {}).get("title", "Staff")
                await promote_staff(bot, message.chat.id, message.from_user.id, title)
        except Exception:
            pass

    # 4) Moderación de contenido de usuarios.
    sender_is_admin = await is_admin(message.chat.id, message.from_user.id if message.from_user else 0, bot)
    if not sender_is_admin:
        content = (message.text or message.caption or "").lower()
        words = await get_blacklist(message.chat.id)
        if words and any(re.search(rf"(?<!\w){re.escape(w.lower())}(?!\w)", content) for w in words):
            await safe_delete(bot, message.chat.id, message.message_id)
            return
        if settings.filter_links and contains_link(message):
            await safe_delete(bot, message.chat.id, message.message_id)
            return

    # 5) Cola de multimedia + estadísticas semanales.
    if is_media(message) and message.from_user:
        await enqueue_media(message.chat.id, message.message_id)
        week = __import__('datetime').datetime.now().strftime("%Y-W%V")
        await stats_col.update_one(
            {"chat_id": message.chat.id, "user_id": message.from_user.id, "week": week},
            {"$inc": {"count": 1}, "$set": {"name": message.from_user.first_name or "Anónimo"}},
            upsert=True,
        )
