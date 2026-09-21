from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set
from motor.motor_asyncio import AsyncIOMotorClient
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from bot.config import MONGO_URI, OWNER_IDS

client = AsyncIOMotorClient(MONGO_URI)
db = client.imperio_bot

groups_col = db.groups
stats_col = db.stats
admins_col = db.admins
warns_col = db.warns
cleanup_queue_col = db.cleanup_queue

_ADMIN_CACHE: Dict[Tuple[int, int], Tuple[bool, datetime]] = {}
_BLACKLIST_CACHE: Dict[int, Tuple[List[str], datetime]] = {}
_PROMOTED_STAFF_CACHE: Set[Tuple[int, int]] = set()
CACHE_TTL = timedelta(minutes=5)

async def init_db_indexes():
    await cleanup_queue_col.create_index([("chat_id", 1), ("message_id", 1)])
    await stats_col.create_index([("chat_id", 1), ("week", 1), ("count", -1)])

async def is_admin(chat_id: int, user_id: int, bot: Bot) -> bool:
    if user_id in OWNER_IDS:
        return True

    now = datetime.now()
    cache_key = (chat_id, user_id)
    if cache_key in _ADMIN_CACHE:
        is_adm, expiry = _ADMIN_CACHE[cache_key]
        if now < expiry:
            return is_adm

    group_data = await groups_col.find_one({"_id": chat_id}, {"authorized_users": 1})
    if group_data and user_id in group_data.get("authorized_users", []):
        _ADMIN_CACHE[cache_key] = (True, now + CACHE_TTL)
        return True

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        result = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
        _ADMIN_CACHE[cache_key] = (result, now + CACHE_TTL)
        return result
    except Exception:
        return False

async def get_cached_blacklist(chat_id: int) -> List[str]:
    now = datetime.now()
    if chat_id in _BLACKLIST_CACHE:
        words, expiry = _BLACKLIST_CACHE[chat_id]
        if now < expiry:
            return words

    group_data = await groups_col.find_one({"_id": chat_id}, {"blacklist": 1})
    words = group_data.get("blacklist", []) if group_data else []
    _BLACKLIST_CACHE[chat_id] = (words, now + CACHE_TTL)
    return words

def invalidate_blacklist_cache(chat_id: int):
    _BLACKLIST_CACHE.pop(chat_id, None)

def invalidate_admin_cache(chat_id: int, user_id: int):
    _ADMIN_CACHE.pop((chat_id, user_id), None)
    _PROMOTED_STAFF_CACHE.discard((chat_id, user_id))

async def promote_staff(bot: Bot, chat_id: int, user_id: int, custom_title: str = "Staff") -> bool:
    try:
        await bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_restrict_members=True,
            can_invite_users=True,
            can_pin_messages=True,
            can_manage_video_chats=True,
            can_promote_members=True,
            can_change_info=False,
            is_anonymous=False
        )
        if custom_title:
            try:
                await bot.set_chat_administrator_custom_title(
                    chat_id=chat_id,
                    user_id=user_id,
                    custom_title=custom_title[:16]
                )
            except TelegramBadRequest:
                pass
        return True
    except Exception:
        return False
