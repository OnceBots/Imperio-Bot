import re
from datetime import datetime
from aiogram import Router, Bot, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatMemberStatus
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatPermissions,
    ChatMemberAdministrator
)
from bot.config import OWNER_IDS, ADMIN_PERMS, PERM_MAPPING
from bot.database import (
    admins_col,
    groups_col,
    cleanup_queue_col,
    get_cached_blacklist,
    invalidate_blacklist_cache,
    invalidate_admin_cache,
    promote_staff,
    _PROMOTED_STAFF_CACHE
)
from bot.keyboards import get_main_dashboard_kb, get_back_kb, get_permissions_kb
from bot.services import execute_cleanup

router = Router()

class PanelStates(StatesGroup):
    waiting_for_id = State()
    waiting_for_rmid = State()
    waiting_for_badword = State()

@router.message(CommandStart())
async def start_private_panel(message: Message, state: FSMContext, bot: Bot):
    if message.chat.type != "private":
        return
    await state.clear()
    admin_data = await admins_col.find_one({"_id": message.from_user.id})
    group_id = admin_data.get("active_group") if admin_data else None

    if message.from_user.id not in OWNER_IDS and not group_id:
        return await message.answer("🛑 <b>ACCESO DENEGADO:</b> No tiene autorización para este panel de control.")
    if not group_id:
        return await message.answer("⚠️ <b>SIN GRUPO VINCULADO:</b> Ejecute <code>/panel</code> dentro del grupo a administrar.")

    try:
        chat = await bot.get_chat(group_id)
        text = (
            f"┌── <b>CENTRO DE CONTROL SUPREMO</b>\n"
            f"│ 📍 <b>Jurisdicción:</b> <code>{chat.title}</code>\n"
            f"│ 🆔 <b>ID de Grupo:</b> <code>{group_id}</code>\n"
            f"│ 🛡️ <b>Operador:</b> <code>{message.from_user.first_name}</code>\n"
            f"└── <b>Conexión:</b> <code>ACTIVA (TLS 1.3)</code>\n\n"
            f"<i>Seleccione el módulo que desea gestionar:</i>"
        )
        await message.answer(text, reply_markup=get_main_dashboard_kb(group_id))
    except Exception as e:
        await message.answer(f"❌ Error al conectar con el grupo vinculado: {e}")

@router.callback_query(F.data.startswith("back_"))
async def back_to_dashboard(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    group_id = int(callback.data.split("_")[1])
    try:
        chat = await bot.get_chat(group_id)
        text = (
            f"┌── <b>CENTRO DE CONTROL SUPREMO</b>\n"
            f"│ 📍 <b>Jurisdicción:</b> <code>{chat.title}</code>\n"
            f"│ 🆔 <b>ID de Grupo:</b> <code>{group_id}</code>\n"
            f"└── <i>Panel listo para operar:</i>"
        )
        await callback.message.edit_text(text, reply_markup=get_main_dashboard_kb(group_id))
    except Exception:
        await callback.answer("Error cargando el menú principal.", show_alert=True)

@router.callback_query(F.data.startswith("lock_confirm_"))
async def lock_confirm_cb(callback: CallbackQuery):
    group_id = int(callback.data.split("_")[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Confirmar Cierre Inmediato", callback_data=f"execute_lock_{group_id}")],
        [InlineKeyboardButton(text="◀️ Cancelar", callback_data=f"back_{group_id}")]
    ])
    await callback.message.edit_text(
        "🔒 <b>MODO ESTRICTO: CIERRE DE CHAT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "¿Confirmas que deseas bloquear la escritura para todos los miembros estándar?",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("execute_lock_"))
async def execute_lock_cb(callback: CallbackQuery, bot: Bot):
    group_id = int(callback.data.split("_")[2])
    try:
        await bot.set_chat_permissions(group_id, ChatPermissions(can_send_messages=False))
        await callback.answer("🔒 Grupo bloqueado exitosamente.", show_alert=False)
        await callback.message.edit_text("✅ <b>MODO ESTRICTO ACTIVADO:</b> El chat ha sido cerrado para los miembros.", reply_markup=get_back_kb(group_id))
    except Exception as e:
        await callback.answer(f"Error: {e}", show_alert=True)

@router.callback_query(F.data.startswith("unlock_confirm_"))
async def unlock_confirm_cb(callback: CallbackQuery):
    group_id = int(callback.data.split("_")[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Confirmar Apertura", callback_data=f"execute_unlock_{group_id}")],
        [InlineKeyboardButton(text="◀️ Cancelar", callback_data=f"back_{group_id}")]
    ])
    await callback.message.edit_text(
        "🔓 <b>MODO LIBRE: APERTURA DE CHAT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "¿Confirmas que deseas restaurar la capacidad de enviar mensajes a todos los usuarios?",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("execute_unlock_"))
async def execute_unlock_cb(callback: CallbackQuery, bot: Bot):
    group_id = int(callback.data.split("_")[2])
    try:
        await bot.set_chat_permissions(
            group_id,
            ChatPermissions(
                can_send_messages=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_documents=True,
                can_send_audios=True,
                can_send_voice_notes=True,
                can_send_other_messages=True
            )
        )
        await callback.answer("🔓 Grupo abierto al público.", show_alert=False)
        await callback.message.edit_text("✅ <b>MODO LIBRE ACTIVADO:</b> El chat se encuentra abierto.", reply_markup=get_back_kb(group_id))
    except Exception as e:
        await callback.answer(f"Error: {e}", show_alert=True)

@router.callback_query(F.data.startswith("perms_"))
async def show_perms_cb(callback: CallbackQuery, bot: Bot):
    group_id = int(callback.data.split("_")[1])
    chat = await bot.get_chat(group_id)
    perms = chat.permissions or ChatPermissions()
    await callback.message.edit_text("⚙️ <b>MATRIZ DE PERMISOS DEL GRUPO</b>\nPulse para alternar estados:", reply_markup=get_permissions_kb(group_id, perms))

@router.callback_query(F.data.startswith("tp_"))
async def toggle_perm_cb(callback: CallbackQuery, bot: Bot):
    _, group_id_str, key = callback.data.split("_", 2)
    group_id = int(group_id_str)
    try:
        chat = await bot.get_chat(group_id)
        cur = chat.permissions or ChatPermissions()
        p_dict = cur.model_dump()
        target_attr = PERM_MAPPING[key][0]
        p_dict[target_attr] = not p_dict.get(target_attr, False)
        new_perms = ChatPermissions(**p_dict)
        await bot.set_chat_permissions(group_id, new_perms)
        await callback.answer("⚡ Permiso sincronizado.")
        await callback.message.edit_reply_markup(reply_markup=get_permissions_kb(group_id, new_perms))
    except Exception as e:
        await callback.answer(f"Fallo al actualizar permisos: {e}", show_alert=True)

@router.callback_query(F.data.startswith("botperms_"))
async def show_bot_perms_cb(callback: CallbackQuery, bot: Bot):
    group_id = int(callback.data.split("_")[1])
    try:
        me = await bot.me()
        member = await bot.get_chat_member(group_id, me.id)
        text = "🤖 <b>AUDITORÍA DE CAPACIDADES DEL BOT</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for attr, label in ADMIN_PERMS.items():
            status = "🟢" if getattr(member, attr, False) else "🔴"
            text += f"{status} <b>{label}</b>\n"
        await callback.message.edit_text(text, reply_markup=get_back_kb(group_id))
    except Exception as e:
        await callback.answer(f"Error consultando bot: {e}", show_alert=True)

@router.callback_query(F.data.startswith("staffmenu_"))
async def staff_menu_cb(callback: CallbackQuery):
    group_id = int(callback.data.split("_")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Añadir Staff", callback_data=f"addid_{group_id}"),
            InlineKeyboardButton(text="➖ Remover Staff", callback_data=f"rmid_{group_id}")
        ],
        [
            InlineKeyboardButton(text="🔄 Sincronizar Permisos Staff", callback_data=f"syncstaffmenu_{group_id}"),
            InlineKeyboardButton(text="👑 Lista de Staff", callback_data=f"viewstaff_{group_id}")
        ],
        [InlineKeyboardButton(text="◀️ Volver al Panel", callback_data=f"back_{group_id}")]
    ])
    await callback.message.edit_text("👥 <b>GESTIÓN DE STAFF INTERNO</b>\nElija una operación:", reply_markup=kb)

@router.callback_query(F.data.startswith("syncstaffmenu_"))
async def sync_staff_menu_cb(callback: CallbackQuery, bot: Bot):
    group_id = int(callback.data.split("_")[1])
    await callback.answer("⏳ Actualizando permisos en silencio...", show_alert=False)

    group_data = await groups_col.find_one({"_id": group_id}, {"authorized_users": 1})
    staff_ids = group_data.get("authorized_users", []) if group_data else []

    updated, skipped, failed = 0, 0, 0
    for uid in staff_ids:
        try:
            member = await bot.get_chat_member(group_id, uid)
            if member.status == ChatMemberStatus.CREATOR:
                skipped += 1
                continue
            if isinstance(member, ChatMemberAdministrator) and getattr(member, "can_promote_members", False):
                skipped += 1
                _PROMOTED_STAFF_CACHE.add((group_id, uid))
                continue

            ok = await promote_staff(bot, group_id, uid, custom_title="Staff")
            if ok:
                updated += 1
                _PROMOTED_STAFF_CACHE.add((group_id, uid))
            else:
                failed += 1
            await asyncio.sleep(0.3)
        except Exception:
            failed += 1

    await callback.message.edit_text(
        f"⚡ <b>Sincronización de Staff Finalizada</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Actualizados (etiquetas activas):</b> <code>{updated}</code>\n"
        f"• <b>Sin cambios necesarios:</b> <code>{skipped}</code>\n"
        f"• <b>Errores / Fallos:</b> <code>{failed}</code>\n\n"
        f"<i>Todos los miembros del Staff ahora cuentan con permisos de administración y edición de etiquetas.</i>",
        reply_markup=get_back_kb(group_id)
    )

@router.callback_query(F.data.startswith("addid_"))
async def add_staff_start(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.split("_")[1])
    await state.set_state(PanelStates.waiting_for_id)
    await state.update_data(group_id=group_id, msg_id=callback.message.message_id)
    await callback.message.edit_text(
        "✍️ <b>Envía el Telegram User ID del nuevo operador.</b>\n"
        "<i>Se le otorgará rango administrativo en Telegram con permisos para editar etiquetas de miembros.</i>",
        reply_markup=get_back_kb(group_id)
    )

@router.message(PanelStates.waiting_for_id)
async def add_staff_finish(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    group_id, msg_id = data["group_id"], data["msg_id"]
    await message.delete()

    if not message.text.strip().isdigit():
        await state.clear()
        return

    new_id = int(message.text.strip())
    try:
        user_info = await bot.get_chat(new_id)
        name = user_info.first_name or "Desconocido"
    except Exception:
        name = "Operador"

    await groups_col.update_one(
        {"_id": group_id},
        {
            "$addToSet": {"authorized_users": new_id},
            "$set": {f"staff_details.{new_id}": {"name": name, "date": datetime.now().strftime("%d/%m/%Y")}}
        },
        upsert=True
    )
    invalidate_admin_cache(group_id, new_id)
    _PROMOTED_STAFF_CACHE.add((group_id, new_id))
    await state.clear()

    promoted = await promote_staff(bot, group_id, new_id, custom_title="Staff")
    promo_status = "y ascendido en Telegram con control de etiquetas" if promoted else "(guardado en base de datos; revisa permisos del bot)"

    await bot.edit_message_text(
        f"✅ <b>Personal Registrado:</b>\n<code>{name}</code> (<code>{new_id}</code>) fue agregado al Staff {promo_status}.",
        chat_id=message.chat.id,
        message_id=msg_id,
        reply_markup=get_main_dashboard_kb(group_id)
    )

@router.callback_query(F.data.startswith("rmid_"))
async def remove_staff_start(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.split("_")[1])
    await state.set_state(PanelStates.waiting_for_rmid)
    await state.update_data(group_id=group_id, msg_id=callback.message.message_id)
    await callback.message.edit_text("✍️ <b>Envía el ID numérico del usuario a revocar:</b>", reply_markup=get_back_kb(group_id))

@router.message(PanelStates.waiting_for_rmid)
async def remove_staff_finish(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    group_id, msg_id = data["group_id"], data["msg_id"]
    await message.delete()

    if not message.text.strip().isdigit():
        return

    target_id = int(message.text.strip())
    await groups_col.update_one(
        {"_id": group_id},
        {
            "$pull": {"authorized_users": target_id},
            "$unset": {f"staff_details.{target_id}": ""}
        }
    )
    invalidate_admin_cache(group_id, target_id)
    await state.clear()

    try:
        await bot.promote_chat_member(
            chat_id=group_id,
            user_id=target_id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False
        )
    except Exception:
        pass

    await bot.edit_message_text(f"🗑️ <b>Privilegios Revocados:</b>\nID <code>{target_id}</code> removido del Staff.", chat_id=message.chat.id, message_id=msg_id, reply_markup=get_main_dashboard_kb(group_id))

@router.callback_query(F.data.startswith("viewstaff_"))
async def view_staff_list(callback: CallbackQuery):
    group_id = int(callback.data.split("_")[1])
    group = await groups_col.find_one({"_id": group_id})
    staff_ids = group.get("authorized_users", []) if group else []

    if not staff_ids:
        return await callback.answer("ℹ️ No hay operadores registrados.", show_alert=True)

    staff_details = group.get("staff_details", {})
    text = "👑 <b>NÓMINA DE STAFF REGISTRADO</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for uid in staff_ids:
        detail = staff_details.get(str(uid), {})
        name = detail.get("name", "Operador")
        date_reg = detail.get("date", "Preexistente")
        text += f"👤 <b>{name}</b> | <code>{uid}</code>\n📅 <i>Alta: {date_reg}</i>\n\n"

    await callback.message.edit_text(text, reply_markup=get_back_kb(group_id))

@router.callback_query(F.data.startswith("badwords_"))
async def badwords_view(callback: CallbackQuery):
    group_id = int(callback.data.split("_")[1])
    words = await get_cached_blacklist(group_id)
    formatted_words = ", ".join([f"<code>{w}</code>" for w in words]) if words else "<i>Lista vacía.</i>"
    text = (
        f"🚫 <b>FILTRO DE PALABRAS PROHIBIDAS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{formatted_words}\n\n"
        f"<i>Los mensajes que contengan estos términos exactos serán destruidos.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Añadir Palabras en Masa", callback_data=f"addword_{group_id}")],
        [InlineKeyboardButton(text="🗑️ Vaciar Lista Negra", callback_data=f"clearwords_{group_id}")],
        [InlineKeyboardButton(text="◀️ Volver", callback_data=f"back_{group_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data.startswith("addword_"))
async def badwords_add_start(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.split("_")[1])
    await state.set_state(PanelStates.waiting_for_badword)
    await state.update_data(group_id=group_id, msg_id=callback.message.message_id)
    await callback.message.edit_text("✍️ <b>Envía las palabras a bloquear (separadas por comas o saltos de línea):</b>", reply_markup=get_back_kb(group_id))

@router.message(PanelStates.waiting_for_badword)
async def badwords_add_finish(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    group_id, msg_id = data["group_id"], data["msg_id"]
    await message.delete()

    raw_words = [w.strip().lower() for w in re.split(r'[,\n]+', message.text) if len(w.strip()) > 1]
    if raw_words:
        await groups_col.update_one({"_id": group_id}, {"$addToSet": {"blacklist": {"$each": raw_words}}}, upsert=True)
        invalidate_blacklist_cache(group_id)

    await state.clear()
    await bot.edit_message_text(f"✅ <b>Filtro Actualizado:</b> Se indexaron <code>{len(raw_words)}</code> términos.", chat_id=message.chat.id, message_id=msg_id, reply_markup=get_main_dashboard_kb(group_id))

@router.callback_query(F.data.startswith("clearwords_"))
async def clear_badwords(callback: CallbackQuery):
    group_id = int(callback.data.split("_")[1])
    await groups_col.update_one({"_id": group_id}, {"$set": {"blacklist": []}})
    invalidate_blacklist_cache(group_id)
    await callback.answer("🧹 Lista negra vaciada.", show_alert=False)
    await callback.message.edit_text("✅ <b>Filtro reiniciado:</b> Se eliminaron todas las palabras prohibidas.", reply_markup=get_back_kb(group_id))

# --- MÓDULO DE PURGA INMEDIATA Y CUENTA REGRESIVA ---
@router.callback_query(F.data.startswith("cleanmenu_"))
async def cleanup_menu(callback: CallbackQuery, bot: Bot):
    group_id = int(callback.data.split("_")[1])
    now = datetime.now()
    
    # 1. Contar archivos pendientes
    pending_count = await cleanup_queue_col.count_documents({"chat_id": group_id})

    # 2. Obtener o reparar la fecha de la próxima limpieza
    group_doc = await groups_col.find_one({"_id": group_id})
    next_time = group_doc.get("next_cleanup") if group_doc else None

    # Si no existe la fecha o ya expiró, programar a 12 horas desde ahora
    if not next_time or next_time <= now:
        next_time = now + timedelta(hours=12)
        await groups_col.update_one(
            {"_id": group_id},
            {"$set": {"next_cleanup": next_time}},
            upsert=True
        )

    # 3. Cálculo exacto del tiempo restante
    remaining_seconds = max(0, int((next_time - now).total_seconds()))
    hours = remaining_seconds // 3600
    minutes = (remaining_seconds % 3600) // 60

    text = (
        f"🧹 <b>MÓDULO DE PURGA Y MANTENIMIENTO</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Archivos en cola:</b> <code>{pending_count}</code> elementos\n"
        f"⏱️ <b>Próxima purga en:</b> <code>{hours}h {minutes}m</code>\n"
        f"🔄 <i>Ciclo programado: Cada 12 Horas</i>\n\n"
        f"<i>Nota: La purga destruirá todo el contenido multimedia acumulado en el grupo.</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Actualizar Reloj", callback_data=f"cleanmenu_{group_id}")],
        [InlineKeyboardButton(text="⚡ Forzar Purga Inmediata", callback_data=f"forceclean_{group_id}")],
        [InlineKeyboardButton(text="◀️ Volver al Panel", callback_data=f"back_{group_id}")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.answer(f"⏱️ Tiempo restante: {hours}h {minutes}m")

@router.callback_query(F.data.startswith("forceclean_"))
async def force_clean_action(callback: CallbackQuery, bot: Bot):
    group_id = int(callback.data.split("_")[1])
    await callback.answer("⚡ Ejecutando purga en el grupo...", show_alert=False)
    
    purged = await execute_cleanup(group_id, bot)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Volver a Limpieza", callback_data=f"cleanmenu_{group_id}")]
    ])
    await callback.message.edit_text(
        f"✅ <b>PURGA COMPLETADA CON ÉXITO</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🗑️ <b>Archivos eliminados del chat:</b> <code>{purged}</code>\n"
        f"⏱️ <b>Nuevo ciclo:</b> Reloj reiniciado a 12 horas.",
        reply_markup=kb
    )
    
@router.callback_query(F.data.startswith("help_"))
async def guide_menu(callback: CallbackQuery):
    group_id = int(callback.data.split("_")[1])
    text = (
        "📖 <b>MANUAL TÁCTICO DE OPERACIONES</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "• <code>/panel</code>: Invoca la consola central en privado.\n"
        "• <code>/promotestaff</code>: Actualiza al Staff o promueve a uno por ID/respuesta.\n"
        "• <code>/del</code>: Elimina el mensaje referenciado.\n"
        "• <code>/ban</code>: Expulsa permanentemente a un usuario.\n"
        "• <code>/unban [ID]</code>: Revoca una expulsión activa.\n"
        "• <code>/mute [30m/2h]</code>: Restringe el habla de forma temporal.\n"
        "• <code>/unmute</code>: Levanta la restricción de voz.\n"
        "• <code>/warn</code> / <code>/unwarn</code>: Gestión de faltas (3 = Ban).\n"
        "• <code>/delall</code>: Menú de purga exhaustiva de un usuario.\n"
        "• <code>/s [texto]</code>: Emite un mensaje fantasma oficial del bot.\n"
        "• <code>/aportes</code>: Estadísticas individuales de multimedia.\n"
        "• <code>/topaportes</code>: Ranking semanal con gráfico de barras.\n"
        "• <code>/leyes</code>: Proclama el reglamento durante 30 segundos."
    )
    await callback.message.edit_text(text, reply_markup=get_back_kb(group_id))
