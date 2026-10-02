from __future__ import annotations

import asyncio
from datetime import timedelta
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from aiogram.enums import ChatMemberStatus
from pymongo import ReturnDocument

from ..config import settings
from ..database import (
    is_admin, is_real_admin, is_group_owner, warns_col, groups_col, admins_col,
    add_staff, remove_staff_record, promote_staff, demote_staff, update_staff_custom_title,
    audit, get_warning_count, add_warning, invalidate_blacklist_cache, get_blacklist,
)
from ..keyboards import back_kb
from ..services import safe_delete, delete_many_safe
from ..utils import is_group, target_from_reply, parse_duration, user_label, all_permissions, locked_permissions, esc

router = Router()

async def transient_notice(message: Message, text: str, ttl: int | None = None):
    notice = await message.answer(text)
    delay = settings.notice_ttl if ttl is None else ttl
    if delay: asyncio.create_task(safe_delete_after(notice, delay))
    return notice

async def safe_delete_after(message: Message, delay: int):
    await asyncio.sleep(delay)
    try: await message.delete()
    except Exception: pass

async def ensure_target_is_not_admin(bot: Bot, message: Message, target_id: int) -> bool:
    if await is_real_admin(message.chat.id, target_id, bot):
        await transient_notice(message, "🛑 No puedes aplicar esa sanción a otro administrador.")
        return False
    return True

@router.message(Command("panel"))
async def panel_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_real_admin(message.chat.id, message.from_user.id, bot): return
    await admins_col.update_one({"_id": message.from_user.id}, {"$set": {"active_group": message.chat.id, "group_title": message.chat.title}}, upsert=True)
    me = await bot.me()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚡ Abrir consola", url=f"https://t.me/{me.username}?start=panel")]])
    await message.reply(
        f"┌── <b>PANEL IMPERIAL</b>\n│ Grupo: <code>{esc(message.chat.title)}</code>\n│ Operador: <code>{user_label(message.from_user)}</code>\n└── Estado: <b>VINCULADO</b>",
        reply_markup=kb,
    )

@router.message(Command("del"))
async def del_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_admin(message.chat.id, message.from_user.id, bot): return
    if not message.reply_to_message:
        return await transient_notice(message, "⚠️ Responde al mensaje que quieres borrar.")
    await safe_delete(bot, message.chat.id, message.reply_to_message.message_id)
    await safe_delete(bot, message.chat.id, message.message_id)
    await audit(message.chat.id, message.from_user.id, "delete_message", details=f"message={message.reply_to_message.message_id}")

@router.message(Command("ban"))
async def ban_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_admin(message.chat.id, message.from_user.id, bot): return
    target = target_from_reply(message)
    if not target: return await transient_notice(message, "⚠️ Responde al usuario que quieres banear.")
    if not await ensure_target_is_not_admin(bot, message, target.id): return
    try:
        await bot.ban_chat_member(message.chat.id, target.id, revoke_messages=True)
        await safe_delete(bot, message.chat.id, message.reply_to_message.message_id)
        await safe_delete(bot, message.chat.id, message.message_id)
        await audit(message.chat.id, message.from_user.id, "ban", target.id)
    except Exception as exc:
        await transient_notice(message, f"❌ No se pudo ejecutar el ban: <code>{esc(str(exc))}</code>")

@router.message(Command("unban"))
async def unban_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_admin(message.chat.id, message.from_user.id, bot): return
    parts = (message.text or "").split()
    user_id = message.reply_to_message.from_user.id if message.reply_to_message else (int(parts[1]) if len(parts)>1 and parts[1].isdigit() else None)
    if not user_id: return await transient_notice(message, "⚠️ Usa <code>/unban ID</code> o responde a un usuario.")
    try:
        await bot.unban_chat_member(message.chat.id, user_id, only_if_banned=True)
        await safe_delete(bot, message.chat.id, message.message_id)
        await audit(message.chat.id, message.from_user.id, "unban", user_id)
        await transient_notice(message, f"✅ Usuario <code>{user_id}</code> desbloqueado.")
    except Exception as exc:
        await transient_notice(message, f"❌ Error: <code>{esc(str(exc))}</code>")

@router.message(Command("mute"))
async def mute_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_admin(message.chat.id, message.from_user.id, bot): return
    target = target_from_reply(message)
    if not target: return await transient_notice(message, "⚠️ Responde al usuario que quieres silenciar.")
    if not await ensure_target_is_not_admin(bot, message, target.id): return
    duration = parse_duration((message.text or "").split()[1] if len((message.text or "").split())>1 else None)
    until = timedelta(minutes=duration)
    try:
        await bot.restrict_chat_member(message.chat.id, target.id, permissions=ChatPermissions(can_send_messages=False), until_date=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)+until)
        await safe_delete(bot, message.chat.id, message.reply_to_message.message_id)
        await safe_delete(bot, message.chat.id, message.message_id)
        await audit(message.chat.id, message.from_user.id, "mute", target.id, f"minutes={duration}")
        await transient_notice(message, f"🔇 <b>Silenciado</b> <code>{user_label(target)}</code> por <code>{duration} min</code>.")
    except Exception as exc:
        await transient_notice(message, f"❌ Error: <code>{esc(str(exc))}</code>")

@router.message(Command("unmute"))
async def unmute_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_admin(message.chat.id, message.from_user.id, bot): return
    target = target_from_reply(message)
    if not target: return await transient_notice(message, "⚠️ Responde al usuario que quieres reactivar.")
    try:
        await bot.restrict_chat_member(message.chat.id, target.id, permissions=ChatPermissions(**all_permissions()))
        await safe_delete(bot, message.chat.id, message.message_id)
        await audit(message.chat.id, message.from_user.id, "unmute", target.id)
        await transient_notice(message, f"🔊 Restricción quitada a <code>{user_label(target)}</code>.")
    except Exception as exc:
        await transient_notice(message, f"❌ Error: <code>{esc(str(exc))}</code>")

@router.message(Command("warn"))
async def warn_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_admin(message.chat.id, message.from_user.id, bot): return
    target = target_from_reply(message)
    if not target: return await transient_notice(message, "⚠️ Responde al usuario al que quieres advertir.")
    if not await ensure_target_is_not_admin(bot, message, target.id): return
    count = await add_warning(message.chat.id, target.id)
    await safe_delete(bot, message.chat.id, message.reply_to_message.message_id)
    await safe_delete(bot, message.chat.id, message.message_id)
    await audit(message.chat.id, message.from_user.id, "warn", target.id, f"count={count}")
    if count >= settings.max_warnings:
        try:
            await bot.ban_chat_member(message.chat.id, target.id, revoke_messages=True)
            await warns_col.delete_one({"chat_id": message.chat.id, "user_id": target.id})
            await transient_notice(message, f"🚨 <b>Límite alcanzado</b>: <code>{user_label(target)}</code> fue expulsado tras {settings.max_warnings} advertencias.")
        except Exception as exc:
            await transient_notice(message, f"❌ Falló la sanción final: <code>{esc(str(exc))}</code>")
    else:
        await transient_notice(message, f"⚠️ Advertencia <code>{count}/{settings.max_warnings}</code> para <code>{user_label(target)}</code>.")

@router.message(Command("unwarn"))
async def unwarn_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_admin(message.chat.id, message.from_user.id, bot): return
    target = target_from_reply(message)
    if not target: return await transient_notice(message, "⚠️ Responde al usuario.")
    await warns_col.delete_one({"chat_id": message.chat.id, "user_id": target.id})
    await safe_delete(bot, message.chat.id, message.message_id)
    await audit(message.chat.id, message.from_user.id, "unwarn", target.id)
    await transient_notice(message, f"🕊️ Historial de faltas restablecido para <code>{user_label(target)}</code>.")

@router.message(Command("delall"))
async def delall_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_admin(message.chat.id, message.from_user.id, bot): return
    target = target_from_reply(message)
    if not target: return await transient_notice(message, "⚠️ Responde al usuario cuyo historial quieres purgar.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Purgar historial", callback_data=f"purge:messages:{message.chat.id}:{target.id}" )],
        [InlineKeyboardButton(text="🔨 Purgar + banear", callback_data=f"purge:ban:{message.chat.id}:{target.id}" )],
        [InlineKeyboardButton(text="❌ Cancelar", callback_data=f"purge:cancel:{message.chat.id}:{target.id}" )],
    ])
    await message.reply(f"🧹 <b>PURGA DE USUARIO</b>\nObjetivo: <code>{user_label(target)}</code>\n\nLa API de bots no permite recorrer arbitrariamente todo el historial por usuario; las opciones aquí usan la purga revocable/soportada por Telegram.", reply_markup=kb)

@router.callback_query(F.data.startswith("purge:"))
async def purge_cb(call: CallbackQuery, bot: Bot):
    _, action, chat_s, target_s = call.data.split(":")
    chat_id = int(chat_s); target_id = int(target_s)
    if not await is_admin(chat_id, call.from_user.id, bot):
        return await call.answer("🛑 Sin permisos.", show_alert=True)
    if action == "cancel":
        await call.message.delete(); return await call.answer()
    try:
        await bot.ban_chat_member(chat_id, target_id, revoke_messages=True)
        if action == "messages":
            await bot.unban_chat_member(chat_id, target_id, only_if_banned=True)
            text = "🧹 <b>Mensajes recientes revocados.</b> El usuario no queda baneado."
        else:
            text = "🔨 <b>Purga + ban completados.</b>"
        await audit(chat_id, call.from_user.id, "purge", target_id, action)
        await call.message.edit_text(text, reply_markup=back_kb(chat_id))
        await call.answer("Listo")
    except Exception as exc:
        await call.answer(f"Error: {exc}", show_alert=True)

@router.message(Command("pin"))
async def pin_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_admin(message.chat.id, message.from_user.id, bot): return
    if not message.reply_to_message: return await transient_notice(message, "⚠️ Responde al mensaje que quieres fijar.")
    try:
        await bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id, disable_notification=True)
        await safe_delete(bot, message.chat.id, message.message_id)
        await audit(message.chat.id, message.from_user.id, "pin", details=f"message={message.reply_to_message.message_id}")
    except Exception as exc:
        await transient_notice(message, f"❌ No se pudo fijar: <code>{esc(str(exc))}</code>")

@router.message(Command("unpin"))
async def unpin_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_admin(message.chat.id, message.from_user.id, bot): return
    try:
        await bot.unpin_all_chat_messages(message.chat.id)
        await safe_delete(bot, message.chat.id, message.message_id)
        await audit(message.chat.id, message.from_user.id, "unpin_all")
    except Exception as exc:
        await transient_notice(message, f"❌ No se pudo quitar el fijado: <code>{esc(str(exc))}</code>")

@router.message(Command("etiqueta", "tag", "titulo"))
async def tag_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_admin(message.chat.id, message.from_user.id, bot): return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await transient_notice(message, "⚠️ Uso: <code>/etiqueta Mi Título</code>")
    ok = await update_staff_custom_title(bot, message.chat.id, message.from_user.id, parts[1])
    await safe_delete(bot, message.chat.id, message.message_id)
    await transient_notice(message, "✅ Etiqueta actualizada." if ok else "❌ Telegram no permitió cambiar la etiqueta.")

@router.message(Command("promotestaff"))
async def promotestaff_cmd(message: Message, bot: Bot):
    if not is_group(message) or not await is_real_admin(message.chat.id, message.from_user.id, bot): return
    parts = (message.text or "").split()
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target and len(parts) > 1 and parts[1].isdigit():
        try:
            member = await bot.get_chat_member(message.chat.id, int(parts[1]))
            target = member.user
        except Exception:
            target = None

    # Compatibilidad con el comportamiento original: sin objetivo sincroniza a todo el Staff existente.
    if not target:
        group = await groups_col.find_one({"_id": message.chat.id}, {"authorized_users": 1, "staff_details": 1})
        staff_ids = group.get("authorized_users", []) if group else []
        if not staff_ids:
            return await transient_notice(message, "ℹ️ No hay miembros registrados en el Staff.")
        ok = failed = 0
        for uid in staff_ids:
            try:
                detail = group.get("staff_details", {}).get(str(uid), {}) if group else {}
                title = detail.get("title", "Staff")
                if await promote_staff(bot, message.chat.id, int(uid), title): ok += 1
                else: failed += 1
            except Exception:
                failed += 1
        await safe_delete(bot, message.chat.id, message.message_id)
        await audit(message.chat.id, message.from_user.id, "sync_staff", details=f"ok={ok};failed={failed}")
        return await transient_notice(message, f"🔄 <b>Staff sincronizado:</b> ✅ <code>{ok}</code> · ❌ <code>{failed}</code>")

    if target.is_bot: return await transient_notice(message, "🛑 No se promocionan bots como Staff.")
    title = " ".join(parts[2:]).strip()[:16] if len(parts)>2 else "Staff"
    await add_staff(message.chat.id, target.id, getattr(target, "first_name", None) or "Operador", title)
    promoted = await promote_staff(bot, message.chat.id, target.id, title)
    await safe_delete(bot, message.chat.id, message.message_id)
    await audit(message.chat.id, message.from_user.id, "promote_staff", target.id, title)
    await transient_notice(message, f"👑 <b>Staff registrado:</b> <code>{user_label(target)}</code> — {'promovido' if promoted else 'guardado; revisa permisos del bot'}.")
