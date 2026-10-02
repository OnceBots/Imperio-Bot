from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.asynchronous import AsyncMongoClient

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest

from .config import settings

client = AsyncMongoClient(
    settings.mongo_uri,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000,
    socketTimeoutMS=10000,
)
db = client[settings.db_name]

groups_col = db.groups
stats_col = db.stats
admins_col = db.admins
warns_col = db.warns
cleanup_queue_col = db.cleanup_queue
audit_col = db.audit_logs

_ADMIN_CACHE: dict[tuple[int, int], tuple[bool, datetime]] = {}
_BLACKLIST_CACHE: dict[int, tuple[list[str], datetime]] = {}
_PROMOTED_STAFF_CACHE: set[tuple[int, int]] = set()
CACHE_TTL = timedelta(minutes=2)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

async def init_db_indexes() -> None:
    await groups_col.create_index("_id")
    await cleanup_queue_col.create_index([("chat_id", ASCENDING), ("message_id", ASCENDING)], unique=True)
    await cleanup_queue_col.create_index("created_at", expireAfterSeconds=7 * 24 * 3600)
    await stats_col.create_index([("chat_id", ASCENDING), ("week", ASCENDING), ("count", DESCENDING)])
    await warns_col.create_index([("chat_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
    await audit_col.create_index([("chat_id", ASCENDING), ("created_at", DESCENDING)])
    await audit_col.create_index("created_at", expireAfterSeconds=180 * 24 * 3600)

async def ping_db() -> None:
    await client.admin.command("ping")

async def close_db() -> None:
    await client.close()

async def is_real_admin(chat_id: int, user_id: int, bot: Bot) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
    except Exception:
        return False

async def is_admin(chat_id: int, user_id: int, bot: Bot) -> bool:
    if user_id in settings.owner_ids:
        return True
    now = utcnow()
    key = (chat_id, user_id)
    cached = _ADMIN_CACHE.get(key)
    if cached and now < cached[1]:
        return cached[0]

    group = await groups_col.find_one({"_id": chat_id}, {"authorized_users": 1})
    if group and user_id in group.get("authorized_users", []):
        # Staff se considera operador autorizado para comandos de moderación del bot.
        _ADMIN_CACHE[key] = (True, now + CACHE_TTL)
        return True

    result = await is_real_admin(chat_id, user_id, bot)
    _ADMIN_CACHE[key] = (result, now + CACHE_TTL)
    return result

async def is_group_owner(chat_id: int, user_id: int, bot: Bot) -> bool:
    if user_id in settings.owner_ids:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status == ChatMemberStatus.CREATOR
    except Exception:
        return False

async def get_blacklist(chat_id: int) -> list[str]:
    now = utcnow()
    cached = _BLACKLIST_CACHE.get(chat_id)
    if cached and now < cached[1]:
        return list(cached[0])
    group = await groups_col.find_one({"_id": chat_id}, {"blacklist": 1})
    words = list(group.get("blacklist", [])) if group else []
    _BLACKLIST_CACHE[chat_id] = (words, now + CACHE_TTL)
    return words

def invalidate_blacklist_cache(chat_id: int) -> None:
    _BLACKLIST_CACHE.pop(chat_id, None)

def invalidate_admin_cache(chat_id: int, user_id: int) -> None:
    _ADMIN_CACHE.pop((chat_id, user_id), None)
    _PROMOTED_STAFF_CACHE.discard((chat_id, user_id))

async def get_group(chat_id: int) -> dict[str, Any]:
    group = await groups_col.find_one({"_id": chat_id})
    if not group:
        group = {"_id": chat_id, "authorized_users": [], "blacklist": [], "service_cleanup": True}
        await groups_col.insert_one(group)
    return group

async def audit(chat_id: int, actor_id: int, action: str, target_id: int | None = None, details: str = "") -> None:
    await audit_col.insert_one({
        "chat_id": chat_id,
        "actor_id": actor_id,
        "action": action,
        "target_id": target_id,
        "details": details[:500],
        "created_at": utcnow(),
    })

async def add_staff(chat_id: int, user_id: int, name: str, title: str = "Staff") -> None:
    await groups_col.update_one(
        {"_id": chat_id},
        {
            "$addToSet": {"authorized_users": user_id},
            "$set": {f"staff_details.{user_id}": {"name": name[:100], "title": title[:16], "date": utcnow().strftime("%d/%m/%Y")}},
        },
        upsert=True,
    )
    invalidate_admin_cache(chat_id, user_id)
    _PROMOTED_STAFF_CACHE.add((chat_id, user_id))

async def remove_staff_record(chat_id: int, user_id: int) -> None:
    await groups_col.update_one(
        {"_id": chat_id},
        {"$pull": {"authorized_users": user_id}, "$unset": {f"staff_details.{user_id}": ""}},
    )
    invalidate_admin_cache(chat_id, user_id)

async def promote_staff(bot: Bot, chat_id: int, user_id: int, custom_title: str = "Staff") -> bool:
    """Promoción segura: solo moderación/mensajes/fijados/videollamadas; sin invitar ni promover."""
    try:
        await bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            is_anonymous=False,
            can_manage_chat=True,
            can_delete_messages=True,
            can_restrict_members=True,
            can_manage_video_chats=True,
            can_invite_users=False,
            can_promote_members=False,
            can_change_info=False,
            can_pin_messages=True,
            can_manage_topics=False,
            can_manage_tags=False,
        )
        try:
            clean_title = "".join(ch for ch in custom_title.strip() if ord(ch) not in range(0x1F000, 0x1FAFF))[:16]
            await bot.set_chat_administrator_custom_title(chat_id=chat_id, user_id=user_id, custom_title=clean_title)
        except TelegramBadRequest:
            pass
        return True
    except Exception:
        return False

async def demote_staff(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        await bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            is_anonymous=False,
            can_manage_chat=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_manage_video_chats=False,
            can_invite_users=False,
            can_promote_members=False,
            can_change_info=False,
            can_pin_messages=False,
            can_manage_topics=False,
            can_manage_tags=False,
        )
        return True
    except Exception:
        return False

async def update_staff_custom_title(bot: Bot, chat_id: int, user_id: int, title: str) -> bool:
    clean = title.strip()[:16]
    if not clean:
        return False
    try:
        await bot.set_chat_administrator_custom_title(chat_id=chat_id, user_id=user_id, custom_title=clean)
        await groups_col.update_one({"_id": chat_id}, {"$set": {f"staff_details.{user_id}.title": clean}}, upsert=True)
        return True
    except Exception:
        return False

async def get_warning_count(chat_id: int, user_id: int) -> int:
    doc = await warns_col.find_one({"chat_id": chat_id, "user_id": user_id})
    return int(doc.get("count", 0)) if doc else 0

async def add_warning(chat_id: int, user_id: int) -> int:
    doc = await warns_col.find_one_and_update(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc.get("count", 1)) if doc else 1
