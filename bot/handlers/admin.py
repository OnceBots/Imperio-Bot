import asyncio
from datetime import datetime, timedelta
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.enums import ChatMemberStatus
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatPermissions,
    CallbackQuery,
    ChatMemberAdministrator
)
from bot.database import (
    is_admin,
    warns_col,
    admins_col,
    groups_col,
    promote_staff,
    _ADMIN_CACHE,
    _PROMOTED_STAFF_CACHE
)

router = Router()

@router.message(Command("promotestaff"))
async def promotestaff_cmd(message: Message, bot: Bot):
    if message.chat.type not in ["group", "supergroup"]:
        return
    if not await is_admin(message.chat.id, message.from_user.id, bot):
        return

    args = message.text.split()[1:]
    target_id = None
    target_name = "Operador"
    tag = "Staff"

    if message.reply_to_message:
        target = message.reply_to_message.from_user
        if target.is_bot:
            return await message.reply("🛑 No puedes promover a un bot.")
        target_id = target.id
        target_name = target.first_name or "Operador"
        if args:
            tag = " ".join(args)[:16]
    elif args and args[0].isdigit():
        target_id = int(args[0])
        try:
            u_info = await bot.get_chat(target_id)
            target_name = u_info.first_name or "Operador"
        except Exception:
            pass
        if len(args) > 1:
            tag = " ".join(args[1:])[:16]

    if target_id:
        await groups_col.update_one(
            {"_id": message.chat.id},
            {
                "$addToSet": {"authorized_users": target_id},
                "$set": {f"staff_details.{target_id}": {"name": target_name, "date": datetime.now().strftime("%d/%m/%Y")}}
            },
            upsert=True
        )
        _ADMIN_CACHE.pop((message.chat.id, target_id), None)
        _PROMOTED_STAFF_CACHE.add((message.chat.id, target_id))

        success = await promote_staff(bot, message.chat.id, target_id, custom_title=tag)
        try:
            await message.delete()
        except Exception:
            pass

        if success:
            notice = await message.answer(
                f"👑 <b>STAFF OFICIAL ASIGNADO</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Operador:</b> <code>{target_name}</code> (<code>{target_id}</code>)\n"
                f"🏷️ <b>Etiqueta:</b> <code>{tag}</code>\n"
                f"⚡ <b>Facultades:</b> Moderación y edición de etiquetas activa."
            )
        else:
            notice = await message.answer("⚠️ Guardado en base de datos, pero falló la promoción en Telegram.")

        await asyncio.sleep(7)
        await notice.delete()
        return

    try:
        await message.delete()
    except Exception:
        pass

    group_data = await groups_col.find_one({"_id": message.chat.id}, {"authorized_users": 1})
    staff_ids = group_data.get("authorized_users", []) if group_data else []

    if not staff_ids:
        notice = await message.answer("⚠️ No hay miembros registrados en el Staff de este grupo.")
        await asyncio.sleep(5)
        await notice.delete()
        return

    status_msg = await message.answer(f"⏳ <i>Actualizando permisos de {len(staff_ids)} miembro(s) del Staff...</i>")
    updated, skipped, failed = 0, 0, 0
    for uid in staff_ids:
        try:
            member = await bot.get_chat_member(message.chat.id, uid)
            if member.status == ChatMemberStatus.CREATOR:
                skipped += 1
                continue

            if isinstance(member, ChatMemberAdministrator) and getattr(member, "can_promote_members", False):
                skipped += 1
                _PROMOTED_STAFF_CACHE.add((message.chat.id, uid))
                continue

            ok = await promote_staff(bot, message.chat.id, uid, custom_title="Staff")
            if ok:
                updated += 1
                _PROMOTED_STAFF_CACHE.add((message.chat.id, uid))
            else:
                failed += 1
            await asyncio.sleep(0.3)
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"👑 <b>ACTUALIZACIÓN GENERAL DE STAFF</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Ascendidos / Actualizados:</b> <code>{updated}</code>\n"
        f"⏩ <b>Ya tenían permisos completos:</b> <code>{skipped}</code>\n"
        f"❌ <b>Errores:</b> <code>{failed}</code>\n\n"
        f"<i>Todos los miembros del Staff ahora cuentan con permisos de administración y edición de etiquetas.</i>"
    )
    await asyncio.sleep(8)
    await status_msg.delete()

@router.message(Command("panel"))
async def link_group_panel(message: Message, bot: Bot):
    if message.chat.type not in ["group", "supergroup"] or not await is_admin(message.chat.id, message.from_user.id, bot):
        return

    await admins_col.update_one(
        {"_id": message.from_user.id},
        {"$set": {"active_group": message.chat.id, "group_title": message.chat.title}},
        upsert=True
    )
    bot_info = await bot.me()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚡ Abrir Consola Central", url=f"https://t.me/{bot_info.username}?start=panel")
    ]])
    await message.reply(
        f"┌── <b>TERMINAL ADMINISTRATIVO</b>\n"
        f"│ <b>Jurisdicción:</b> <code>{message.chat.title}</code>\n"
        f"│ <b>Operador:</b> <code>{message.from_user.first_name}</code>\n"
        f"└── <b>Estado:</b> <code>SESIÓN SINCRONIZADA</code>",
        reply_markup=kb
    )

@router.message(Command("del"))
async def delete_cmd(message: Message, bot: Bot):
    if message.chat.type in ["group", "supergroup"] and await is_admin(message.chat.id, message.from_user.id, bot):
        if message.reply_to_message:
            try:
                await message.reply_to_message.delete()
                await message.delete()
            except Exception:
                pass

@router.message(Command("ban"))
async def ban_cmd(message: Message, bot: Bot):
    if message.chat.type not in ["group", "supergroup"] or not await is_admin(message.chat.id, message.from_user.id, bot):
        return
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        return await message.reply("⚠️ Debe responder al mensaje del usuario que desea expulsar.")
    if await is_admin(message.chat.id, target.id, bot):
        return await message.reply("🛑 No es posible sancionar a otro administrador.")

    try:
        await bot.ban_chat_member(message.chat.id, target.id)
        await message.reply_to_message.delete()
        notice = await message.answer(
            f"🚫 <b>SENTENCIA EJECUTADA</b>\n"
            f"👤 <b>Infractor:</b> <code>{target.first_name}</code> (<code>{target.id}</code>)\n"
            f"⚖️ <b>Sanción:</b> Expulsión permanente (BAN)."
        )
        await message.delete()
        await asyncio.sleep(5)
        await notice.delete()
    except Exception:
        pass

@router.message(Command("unban"))
async def unban_cmd(message: Message, bot: Bot):
    if message.chat.type not in ["group", "supergroup"] or not await is_admin(message.chat.id, message.from_user.id, bot):
        return
    parts = message.text.split()
    user_id = message.reply_to_message.from_user.id if message.reply_to_message else (int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None)
    if not user_id:
        return await message.reply("⚠️ Especifique el ID numérico o responda al usuario a readmitir.")

    try:
        await bot.unban_chat_member(message.chat.id, user_id, only_if_banned=True)
        notice = await message.answer(f"✅ <b>AMNISTÍA CONCEDIDA:</b> Usuario <code>{user_id}</code> desbloqueado.")
        await message.delete()
        await asyncio.sleep(5)
        await notice.delete()
    except Exception as e:
        await message.reply(f"❌ Error al revocar sanción: {e}")

@router.message(Command("mute"))
async def mute_cmd(message: Message, bot: Bot):
    if message.chat.type not in ["group", "supergroup"] or not await is_admin(message.chat.id, message.from_user.id, bot):
        return
    if not message.reply_to_message:
        return await message.reply("⚠️ Responda al usuario que desea silenciar.")
    target = message.reply_to_message.from_user
    if await is_admin(message.chat.id, target.id, bot):
        return await message.reply("🛑 No puede silenciar a un administrador.")

    args = message.text.split()
    duration_minutes = 60
    if len(args) > 1:
        param = args[1].lower()
        if param.endswith("m") and param[:-1].isdigit():
            duration_minutes = int(param[:-1])
        elif param.endswith("h") and param[:-1].isdigit():
            duration_minutes = int(param[:-1]) * 60
        elif param.endswith("d") and param[:-1].isdigit():
            duration_minutes = int(param[:-1]) * 1440
        elif param.isdigit():
            duration_minutes = int(param)

    until = datetime.now() + timedelta(minutes=duration_minutes)
    try:
        await bot.restrict_chat_member(
            message.chat.id,
            target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until
        )
        await message.reply_to_message.delete()
        notice = await message.answer(
            f"🤐 <b>ORDEN DE SILENCIO</b>\n"
            f"👤 <b>Usuario:</b> <code>{target.first_name}</code>\n"
            f"⏱️ <b>Duración:</b> <code>{duration_minutes} min</code>"
        )
        await message.delete()
        await asyncio.sleep(5)
        await notice.delete()
    except Exception:
        pass

@router.message(Command("unmute"))
async def unmute_cmd(message: Message, bot: Bot):
    if message.chat.type not in ["group", "supergroup"] or not await is_admin(message.chat.id, message.from_user.id, bot):
        return
    if not message.reply_to_message:
        return await message.reply("⚠️ Responda al usuario que desea reactivar.")

    target = message.reply_to_message.from_user
    try:
        await bot.restrict_chat_member(
            message.chat.id,
            target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_documents=True,
                can_send_audios=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        notice = await message.answer(f"🔊 <b>VOZ RESTABLECIDA:</b> <code>{target.first_name}</code> puede interactuar.")
        await message.delete()
        await asyncio.sleep(5)
        await notice.delete()
    except Exception as e:
        await message.reply(f"❌ Error al levantar silencio: {e}")

@router.message(Command("warn"))
async def warn_cmd(message: Message, bot: Bot):
    if message.chat.type not in ["group", "supergroup"] or not await is_admin(message.chat.id, message.from_user.id, bot):
        return
    if not message.reply_to_message:
        return await message.reply("⚠️ Responda al usuario para aplicar una advertencia.")

    target = message.reply_to_message.from_user
    if await is_admin(message.chat.id, target.id, bot):
        return await message.reply("🛑 No puede sancionar a un administrador.")

    res = await warns_col.find_one_and_update(
        {"chat_id": message.chat.id, "user_id": target.id},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=True
    )
    warns = res.get("count", 1)

    try:
        await message.reply_to_message.delete()
        await message.delete()
    except Exception:
        pass

    if warns >= 3:
        try:
            await bot.ban_chat_member(message.chat.id, target.id)
            await warns_col.delete_one({"chat_id": message.chat.id, "user_id": target.id})
            notice = await message.answer(
                f"🚨 <b>LÍMITE DE ADVERTENCIAS (3/3)</b>\n"
                f"👤 <code>{target.first_name}</code> acumuló 3 faltas y fue expulsado definitivamente."
            )
        except Exception as e:
            notice = await message.answer(f"❌ Error al sancionar: {e}")
    else:
        notice = await message.answer(
            f"⚠️ <b>ADVERTENCIA APLICADA</b>\n"
            f"👤 <b>Usuario:</b> <code>{target.first_name}</code>\n"
            f"📊 <b>Estado:</b> <code>[{warns}/3]</code> advertencias registradas."
        )

    await asyncio.sleep(6)
    try:
        await notice.delete()
    except Exception:
        pass

@router.message(Command("unwarn"))
async def unwarn_cmd(message: Message, bot: Bot):
    if message.chat.type not in ["group", "supergroup"] or not await is_admin(message.chat.id, message.from_user.id, bot):
        return
    if not message.reply_to_message:
        return await message.reply("⚠️ Responda al usuario para perdonar sus faltas.")

    target = message.reply_to_message.from_user
    await warns_col.delete_one({"chat_id": message.chat.id, "user_id": target.id})
    notice = await message.answer(f"🕊️ <b>HISTORIAL RESTABLECIDO:</b> <code>{target.first_name}</code> está libre de faltas.")
    await message.delete()
    await asyncio.sleep(5)
    await notice.delete()

@router.message(Command("delall"))
async def delall_cmd(message: Message, bot: Bot):
    if message.chat.type not in ["group", "supergroup"] or not await is_admin(message.chat.id, message.from_user.id, bot):
        return
    if not message.reply_to_message:
        return await message.reply("⚠️ Responda al usuario cuyo historial desea purgar.")

    target = message.reply_to_message.from_user
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Purgar Mensajes Recientes", callback_data=f"purge_msgs_{target.id}")],
        [InlineKeyboardButton(text="🔨 Purgar y Expulsar Permanentemente", callback_data=f"purge_ban_{target.id}")],
        [InlineKeyboardButton(text="❌ Cancelar", callback_data=f"purge_cancel_{target.id}")]
    ])
    await message.reply(
        f"┌── <b>PROTOCOLO DE PURGA</b>\n"
        f"│ <b>Objetivo:</b> <code>{target.first_name}</code>\n"
        f"│ <b>ID:</b> <code>{target.id}</code>\n"
        f"└── <i>Seleccione el nivel de erradicación:</i>",
        reply_markup=kb
    )

@router.callback_query(lambda c: c.data.startswith("purge_"))
async def process_purge_action(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    action = parts[1]
    target_id = int(parts[2])
    chat_id = callback.message.chat.id

    if not await is_admin(chat_id, callback.from_user.id, bot):
        return await callback.answer("🛑 Permiso denegado.", show_alert=True)
    if action == "cancel":
        return await callback.message.delete()

    try:
        await bot.ban_chat_member(chat_id, target_id, revoke_messages=True)
        if action == "msgs":
            await bot.unban_chat_member(chat_id, target_id)
            await callback.message.edit_text("🧹 <b>Historial de mensajes purgado con éxito.</b>")
        else:
            await callback.message.edit_text("⚡ <b>Purga total completada:</b> Historial eliminado y usuario expulsado.")
    except Exception as e:
        await callback.message.edit_text(f"❌ Fallo en la purga: {e}")

@router.message(Command("pin"))
async def pin_cmd(message: Message, bot: Bot):
    if message.chat.type in ["group", "supergroup"] and await is_admin(message.chat.id, message.from_user.id, bot):
        if message.reply_to_message:
            try:
                await bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id)
                await message.delete()
            except Exception:
                pass

@router.message(Command("leyes", "reglas"))
async def rules_cmd(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        return
    text = (
        "🏛️ <b>CÓDIGO DE NORMAS VIGENTES</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>1.</b> Cero enlaces, spam o publicidad no autorizada.\n"
        "<b>2.</b> Respeto incondicional; tolerancia cero a acoso o disputas.\n"
        "<b>3.</b> Prohibido material explícito o contenido sensible no solicitado.\n"
        "<b>4.</b> Comercio de archivos o servicios exclusivamente bajo permiso de administración.\n"
        "<b>5.</b> Idioma de comunicación exclusivo: <b>Español</b>.\n\n"
        "<i>⏳ Este comunicado se autodestruirá automáticamente en 30 segundos.</i>"
    )
    try:
        reply_msg = await message.reply(text)
        await asyncio.sleep(30)
        await reply_msg.delete()
        await message.delete()
    except Exception:
        pass
