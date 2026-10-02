from __future__ import annotations
from aiogram import Bot
from aiogram.types import Message, CallbackQuery
from ..database import is_admin
from ..utils import is_group

async def require_group_operator(event: Message | CallbackQuery, bot: Bot, group_id: int | None = None) -> bool:
    if isinstance(event, Message):
        if not is_group(event): return False
        chat_id = event.chat.id
        user_id = event.from_user.id if event.from_user else 0
    else:
        if group_id is None: return False
        chat_id = group_id
        user_id = event.from_user.id
    ok = await is_admin(chat_id, user_id, bot)
    if not ok:
        try: await event.answer("🛑 No tienes permisos para esta función.", show_alert=True)
        except Exception: pass
    return ok

async def require_real_admin(event: Message | CallbackQuery, bot: Bot, group_id: int | None = None) -> bool:
    from ..database import is_real_admin
    if isinstance(event, Message):
        if not is_group(event): return False
        chat_id = event.chat.id; user_id = event.from_user.id if event.from_user else 0
    else:
        if group_id is None: return False
        chat_id = group_id; user_id = event.from_user.id
    ok = await is_real_admin(chat_id, user_id, bot)
    if not ok:
        try: await event.answer("🛑 Se requiere ser administrador del grupo.", show_alert=True)
        except Exception: pass
    return ok
