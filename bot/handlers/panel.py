from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from aiogram import Router, Bot, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, ChatPermissions
from aiogram.enums import ChatMemberStatus

from ..config import settings, OWNER_IDS, PERM_MAPPING
from ..database import (
    admins_col, groups_col, get_group, is_admin, is_real_admin, is_group_owner,
    get_blacklist, invalidate_blacklist_cache, invalidate_admin_cache,
    add_staff, remove_staff_record, promote_staff, demote_staff, _PROMOTED_STAFF_CACHE,
    audit,
)
from ..keyboards import main_kb, back_kb, clean_kb, filter_kb, staff_kb, security_kb, stats_kb, rules_kb, permissions_kb
from ..services import execute_cleanup
from ..utils import all_permissions, locked_permissions, esc, user_label

router = Router()

class PanelStates(StatesGroup):
    waiting_staff_id = State()
    waiting_staff_remove_id = State()
    waiting_badwords = State()

async def can_panel(call: CallbackQuery, bot: Bot, group_id: int) -> bool:
    ok = await is_admin(group_id, call.from_user.id, bot)
    if not ok:
        await call.answer("🛑 No tienes permisos.", show_alert=True)
    return ok

@router.message(CommandStart())
async def start_panel(message: Message, state: FSMContext, bot: Bot):
    if message.chat.type != "private": return
    await state.clear()
    admin = await admins_col.find_one({"_id": message.from_user.id})
    group_id = admin.get("active_group") if admin else None
    if not group_id and message.from_user.id not in OWNER_IDS:
        return await message.answer("🛑 No tienes un grupo vinculado. Ejecuta /panel dentro del grupo.")
    if not group_id and message.from_user.id in OWNER_IDS:
        return await message.answer("⚙️ Eres Owner, pero aún no has vinculado un grupo. Ejecuta /panel en el grupo.")
    try:
        chat = await bot.get_chat(group_id)
        await message.answer(
            f"🏛️ <b>CENTRO DE CONTROL — IMPERIO OTOMANO</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>Grupo:</b> <code>{esc(chat.title)}</code>\n"
            f"🆔 <code>{group_id}</code>\n"
            f"👤 <b>Operador:</b> <code>{user_label(message.from_user)}</code>\n\n"
            "Selecciona un módulo:",
            reply_markup=main_kb(group_id),
        )
    except Exception as exc:
        await message.answer(f"❌ No se pudo cargar el grupo: <code>{esc(str(exc))}</code>")

@router.callback_query(F.data.startswith("home:"))
async def home(call: CallbackQuery, state: FSMContext, bot: Bot):
    group_id = int(call.data.split(":")[1])
    await state.clear()
    if not await can_panel(call, bot, group_id): return
    await call.answer()
    await call.message.edit_text("🏛️ <b>CENTRO DE CONTROL</b>\n\nSelecciona un módulo.", reply_markup=main_kb(group_id))

@router.callback_query(F.data.startswith("menu_mod:"))
async def menu_mod(call: CallbackQuery, bot: Bot):
    from ..keyboards import mod_kb
    gid=int(call.data.split(":")[1]);
    if not await can_panel(call, bot, gid): return
    await call.answer(); await call.message.edit_text("🛡️ <b>MODERACIÓN</b>\n\nComandos de moderación rápida:", reply_markup=mod_kb(gid))

@router.callback_query(F.data.startswith("menu_clean:"))
async def menu_clean(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[1]);
    if not await can_panel(call, bot, gid): return
    await call.answer(); await call.message.edit_text("🧹 <b>LIMPIEZA</b>\n\nControla la limpieza de servicio y la cola multimedia.", reply_markup=clean_kb(gid))

@router.callback_query(F.data.startswith("menu_filter:"))
async def menu_filter(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[1]);
    if not await can_panel(call, bot, gid): return
    await call.answer(); await call.message.edit_text("🚫 <b>FILTROS</b>\n\nGestiona palabras y anti-enlaces.", reply_markup=filter_kb(gid))

@router.callback_query(F.data.startswith("menu_staff:"))
async def menu_staff(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[1]);
    if not await is_real_admin(gid, call.from_user.id, bot): return await call.answer("🛑 Solo administradores.", show_alert=True)
    await call.answer(); await call.message.edit_text("👑 <b>STAFF</b>\n\nLos administradores pueden gestionar el Staff; el Staff no puede promover a otros.", reply_markup=staff_kb(gid))

@router.callback_query(F.data.startswith("menu_security:"))
async def menu_security(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[1]);
    if not await can_panel(call, bot, gid): return
    await call.answer(); await call.message.edit_text("🔐 <b>SEGURIDAD</b>\n\nControl del chat y capacidades del bot.", reply_markup=security_kb(gid))

@router.callback_query(F.data.startswith("menu_stats:"))
async def menu_stats(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[1]);
    if not await can_panel(call, bot, gid): return
    await call.answer(); await call.message.edit_text("📊 <b>ESTADÍSTICAS</b>", reply_markup=stats_kb(gid))

@router.callback_query(F.data.startswith("menu_rules:"))
async def menu_rules(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[1]);
    if not await can_panel(call, bot, gid): return
    await call.answer(); await call.message.edit_text("📜 <b>REGLAS</b>\n\nConsulta las normas del grupo.", reply_markup=rules_kb(gid))

@router.callback_query(F.data.startswith("menu_config:"))
async def menu_config(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[1]);
    if not await can_panel(call, bot, gid): return
    group=await get_group(gid)
    text=(f"⚙️ <b>CONFIGURACIÓN</b>\n━━━━━━━━━━━━━━━━━━\n"
          f"🔔 Limpieza de servicio: <b>{'ON' if group.get('service_cleanup', True) else 'OFF'}</b>\n"
          f"🤖 Anti-bot: <b>{'ON' if group.get('anti_bot', settings.anti_bot) else 'OFF'}</b>\n"
          f"🔗 Anti-enlaces global: <b>{'ON' if settings.filter_links else 'OFF (ENV)'}</b>\n"
          f"⏱️ Purga multimedia: cada <code>{settings.auto_cleanup_hours}h</code>")
    kb=security_kb(gid)
    await call.answer(); await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data.startswith("clean:status:"))
async def clean_status(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call, bot, gid): return
    count=await __import__('bot.database', fromlist=['cleanup_queue_col']).cleanup_queue_col.count_documents({"chat_id":gid})
    group=await get_group(gid)
    nxt=group.get("next_cleanup")
    remaining="no programado"
    if nxt:
        dt=nxt
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        secs=max(0,int((dt-datetime.now(timezone.utc)).total_seconds()))
        remaining=f"{secs//3600}h {(secs%3600)//60}m"
    await call.answer(); await call.message.edit_text(f"🧹 <b>ESTADO DE LIMPIEZA</b>\n\n📦 Cola multimedia: <code>{count}</code>\n⏱️ Próxima purga: <code>{remaining}</code>\n🔔 Servicio: <b>{'ON' if group.get('service_cleanup', True) else 'OFF'}</b>", reply_markup=clean_kb(gid))

@router.callback_query(F.data.startswith("clean:force:"))
async def clean_force(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call, bot, gid): return
    await call.answer("Ejecutando purga…")
    removed=await execute_cleanup(bot,gid)
    await audit(gid, call.from_user.id, "force_cleanup", details=f"removed={removed}")
    await call.message.edit_text(f"✅ <b>PURGA COMPLETADA</b>\n🗑️ Eliminados: <code>{removed}</code>", reply_markup=clean_kb(gid))

@router.callback_query(F.data.startswith("clean:queue:"))
async def clean_queue(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call, bot, gid): return
    from ..database import cleanup_queue_col
    docs=await cleanup_queue_col.find({"chat_id":gid}).sort("message_id",-1).limit(20).to_list(length=20)
    ids=[str(d['message_id']) for d in docs]
    await call.answer(); await call.message.edit_text("🧾 <b>COLA MULTIMEDIA</b>\n\n" + (", ".join(f"<code>{x}</code>" for x in ids) if ids else "<i>Vacía.</i>"), reply_markup=clean_kb(gid))

@router.callback_query(F.data.startswith("clean:toggle_service:"))
async def toggle_service(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call, bot, gid): return
    group=await get_group(gid); enabled=not group.get("service_cleanup", True)
    await groups_col.update_one({"_id":gid},{"$set":{"service_cleanup":enabled}},upsert=True)
    await call.answer(f"Limpieza de servicio: {'ON' if enabled else 'OFF'}")
    await call.message.edit_text(f"🔔 Limpieza de mensajes de servicio: <b>{'ON' if enabled else 'OFF'}</b>", reply_markup=clean_kb(gid))

@router.callback_query(F.data.startswith("filter:view:"))
async def filter_view(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call, bot, gid): return
    words=await get_blacklist(gid)
    text="🚫 <b>PALABRAS PROHIBIDAS</b>\n\n" + (", ".join(f"<code>{esc(w)}</code>" for w in words) if words else "<i>Lista vacía.</i>")
    await call.answer(); await call.message.edit_text(text, reply_markup=filter_kb(gid))

@router.callback_query(F.data.startswith("filter:add:"))
async def filter_add_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call, bot, gid): return
    await state.set_state(PanelStates.waiting_badwords); await state.update_data(group_id=gid, panel_message_id=call.message.message_id, panel_chat_id=call.message.chat.id)
    await call.answer(); await call.message.edit_text("✍️ Envía las palabras separadas por comas o líneas.", reply_markup=back_kb(gid))

@router.message(PanelStates.waiting_badwords)
async def filter_add_finish(message: Message, state: FSMContext, bot: Bot):
    data=await state.get_data(); gid=int(data["group_id"])
    if not await is_real_admin(gid,message.from_user.id,bot): return await state.clear()
    raw=message.text or ""
    words=[x.strip().lower() for x in __import__('re').split(r"[,\n]+",raw) if len(x.strip())>1]
    if words: await groups_col.update_one({"_id":gid},{"$addToSet":{"blacklist":{"$each":words}}},upsert=True)
    invalidate_blacklist_cache(gid); await state.clear();
    try: await message.delete()
    except Exception: pass
    await bot.edit_message_text(f"✅ Filtro actualizado: <code>{len(words)}</code> palabra(s).",chat_id=data["panel_chat_id"],message_id=data["panel_message_id"],reply_markup=filter_kb(gid))

@router.callback_query(F.data.startswith("filter:clear:"))
async def filter_clear(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call, bot, gid): return
    await groups_col.update_one({"_id":gid},{"$set":{"blacklist":[]}}); invalidate_blacklist_cache(gid)
    await call.answer("Lista vaciada")
    await call.message.edit_text("✅ Lista negra vaciada.",reply_markup=filter_kb(gid))

@router.callback_query(F.data.startswith("filter:links:"))
async def filter_links(call: CallbackQuery, bot: Bot):
    await call.answer("El anti-enlaces se controla por FILTER_LINKS en .env.", show_alert=True)

@router.callback_query(F.data.startswith("staff:view:"))
async def staff_view(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await is_real_admin(gid, call.from_user.id, bot): return await call.answer("🛑 Solo administradores.",show_alert=True)
    group=await get_group(gid); ids=group.get("authorized_users",[]); details=group.get("staff_details",{})
    text="👑 <b>STAFF REGISTRADO</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for uid in ids:
        d=details.get(str(uid),{})
        text += f"👤 <b>{esc(d.get('name','Operador'))}</b>\n🆔 <code>{uid}</code>\n🏷️ <code>{esc(d.get('title','Staff'))}</code>\n\n"
    await call.answer(); await call.message.edit_text(text if ids else "👑 <b>STAFF</b>\n\n<i>No hay miembros registrados.</i>",reply_markup=staff_kb(gid))

@router.callback_query(F.data.startswith("staff:add:"))
async def staff_add_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await is_real_admin(gid, call.from_user.id, bot): return await call.answer("🛑 Solo administradores.",show_alert=True)
    await state.set_state(PanelStates.waiting_staff_id); await state.update_data(group_id=gid,panel_message_id=call.message.message_id,panel_chat_id=call.message.chat.id)
    await call.answer(); await call.message.edit_text("✍️ Envía el ID numérico del usuario que será Staff.\n\nTambién puedes usar /promotestaff desde el grupo.",reply_markup=back_kb(gid))

@router.message(PanelStates.waiting_staff_id)
async def staff_add_finish(message: Message, state: FSMContext, bot: Bot):
    data=await state.get_data(); gid=int(data["group_id"])
    if not await is_real_admin(gid,message.from_user.id,bot): return await state.clear()
    if not (message.text or "").strip().isdigit(): return
    uid=int(message.text.strip())
    try:
        info=await bot.get_chat(uid)
        name=getattr(info,"first_name",None) or getattr(info,"title",None) or "Operador"
    except Exception:
        name="Operador"
    await add_staff(gid,uid,name,"Staff"); promoted=await promote_staff(bot,gid,uid,"Staff")
    await state.clear();
    try: await message.delete()
    except Exception: pass
    await bot.edit_message_text(f"✅ <b>Staff agregado</b>\nID <code>{uid}</code> — {'promovido' if promoted else 'guardado; revisa permisos del bot'}.",chat_id=data["panel_chat_id"],message_id=data["panel_message_id"],reply_markup=staff_kb(gid))

@router.callback_query(F.data.startswith("staff:remove:"))
async def staff_remove_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await is_real_admin(gid, call.from_user.id, bot): return await call.answer("🛑 Solo administradores.",show_alert=True)
    await state.set_state(PanelStates.waiting_staff_remove_id); await state.update_data(group_id=gid,panel_message_id=call.message.message_id,panel_chat_id=call.message.chat.id)
    await call.answer(); await call.message.edit_text("✍️ Envía el ID del Staff a quitar.",reply_markup=back_kb(gid))

@router.message(PanelStates.waiting_staff_remove_id)
async def staff_remove_finish(message: Message, state: FSMContext, bot: Bot):
    data=await state.get_data(); gid=int(data["group_id"])
    if not await is_real_admin(gid,message.from_user.id,bot): return await state.clear()
    if not (message.text or "").strip().isdigit(): return
    uid=int(message.text.strip()); await remove_staff_record(gid,uid); await demote_staff(bot,gid,uid); await state.clear()
    try: await message.delete()
    except Exception: pass
    await bot.edit_message_text(f"🗑️ Staff <code>{uid}</code> revocado.",chat_id=data["panel_chat_id"],message_id=data["panel_message_id"],reply_markup=staff_kb(gid))

@router.callback_query(F.data.startswith("staff:sync:"))
async def staff_sync(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await is_real_admin(gid, call.from_user.id, bot): return await call.answer("🛑 Solo administradores.",show_alert=True)
    group=await get_group(gid); ids=group.get("authorized_users",[]); ok=failed=0
    for uid in ids:
        if await promote_staff(bot,gid,int(uid),group.get("staff_details",{}).get(str(uid),{}).get("title","Staff")): ok += 1
        else: failed += 1
    await call.answer("Sincronización completada")
    await call.message.edit_text(f"🔄 <b>STAFF SINCRONIZADO</b>\n✅ {ok}\n❌ {failed}",reply_markup=staff_kb(gid))

@router.callback_query(F.data.startswith("security:lock:"))
async def sec_lock(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call,bot,gid): return
    try:
        await bot.set_chat_permissions(gid,ChatPermissions(**locked_permissions()))
        await audit(gid,call.from_user.id,"lock_chat"); await call.answer("Chat cerrado")
        await call.message.edit_text("🔒 <b>CHAT CERRADO</b>\n\nLos miembros estándar no podrán escribir.",reply_markup=security_kb(gid))
    except Exception as exc: await call.answer(str(exc),show_alert=True)

@router.callback_query(F.data.startswith("security:unlock:"))
async def sec_unlock(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call,bot,gid): return
    try:
        await bot.set_chat_permissions(gid,ChatPermissions(**all_permissions()))
        await audit(gid,call.from_user.id,"unlock_chat"); await call.answer("Chat abierto")
        await call.message.edit_text("🔓 <b>CHAT ABIERTO</b>\n\nPermisos estándar restaurados.",reply_markup=security_kb(gid))
    except Exception as exc: await call.answer(str(exc),show_alert=True)

@router.callback_query(F.data.startswith("security:antibot:"))
async def sec_antibot(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call,bot,gid): return
    group=await get_group(gid); enabled=not group.get("anti_bot",settings.anti_bot)
    await groups_col.update_one({"_id":gid},{"$set":{"anti_bot":enabled}},upsert=True)
    await call.answer(f"Anti-bot: {'ON' if enabled else 'OFF'}")
    await call.message.edit_text(f"🤖 <b>Anti-bot:</b> {'ON' if enabled else 'OFF'}",reply_markup=security_kb(gid))

@router.callback_query(F.data.startswith("security:service:"))
async def sec_service(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call,bot,gid): return
    group=await get_group(gid); enabled=not group.get("service_cleanup",True)
    await groups_col.update_one({"_id":gid},{"$set":{"service_cleanup":enabled}},upsert=True)
    await call.answer(f"Servicio: {'ON' if enabled else 'OFF'}")
    await call.message.edit_text(f"🔔 <b>Mensajes de servicio:</b> {'ON' if enabled else 'OFF'}",reply_markup=security_kb(gid))

@router.callback_query(F.data.startswith("security:botperms:"))
async def botperms(call: CallbackQuery, bot: Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call,bot,gid): return
    me=await bot.me(); member=await bot.get_chat_member(gid,me.id)
    labels={"can_delete_messages":"Borrar mensajes","can_restrict_members":"Sancionar","can_pin_messages":"Fijar","can_promote_members":"Promover","can_change_info":"Cambiar info","can_invite_users":"Invitar","can_manage_topics":"Temas"}
    text="🤖 <b>PERMISOS DEL BOT</b>\n━━━━━━━━━━━━━━━━━━\n" + "\n".join(f"{'🟢' if getattr(member,k,False) else '🔴'} {v}" for k,v in labels.items())
    await call.answer(); await call.message.edit_text(text,reply_markup=security_kb(gid))

@router.callback_query(F.data.startswith("security:perms:"))
async def chatperms(call: CallbackQuery,bot:Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call,bot,gid): return
    chat=await bot.get_chat(gid); perms=chat.permissions or ChatPermissions()
    await call.answer(); await call.message.edit_text("⚙️ <b>PERMISOS DEL CHAT</b>\n\nPulsa un permiso para alternarlo.",reply_markup=permissions_kb(gid,perms))

@router.callback_query(F.data.startswith("perm:"))
async def perm_toggle(call: CallbackQuery,bot:Bot):
    _, gid_s, key=call.data.split(":"); gid=int(gid_s)
    if not await can_panel(call,bot,gid): return
    if key not in PERM_MAPPING: return await call.answer("Permiso desconocido",show_alert=True)
    attr=PERM_MAPPING[key][0]; chat=await bot.get_chat(gid); cur=chat.permissions or ChatPermissions(); data=cur.model_dump(); data[attr]=not bool(data.get(attr,False))
    try:
        new=ChatPermissions(**data); await bot.set_chat_permissions(gid,new); await call.answer("Actualizado"); await call.message.edit_reply_markup(reply_markup=permissions_kb(gid,new))
    except Exception as exc: await call.answer(str(exc),show_alert=True)

@router.callback_query(F.data.startswith("stats:"))
async def panel_stats(call: CallbackQuery,bot:Bot):
    _, action, gid_s=call.data.split(":"); gid=int(gid_s)
    if not await can_panel(call,bot,gid): return
    from .stats import build_stats_text
    await call.answer(); await call.message.edit_text(await build_stats_text(gid,call.from_user.id,action),reply_markup=stats_kb(gid))

@router.callback_query(F.data.startswith("rules:view:"))
async def rules_view(call: CallbackQuery,bot:Bot):
    gid=int(call.data.split(":")[2]);
    if not await can_panel(call,bot,gid): return
    await call.answer(); await call.message.edit_text("📜 <b>CÓDIGO DE NORMAS</b>\n━━━━━━━━━━━━━━━━━━\n1. Cero spam, enlaces o publicidad no autorizada.\n2. Respeto entre miembros.\n3. No contenido sensible no solicitado.\n4. Comercio solo con autorización.\n5. Usa español en el chat.",reply_markup=rules_kb(gid))

@router.callback_query(F.data.startswith("howto:"))
async def howto(call: CallbackQuery,bot:Bot):
    _, cmd, gid_s=call.data.split(":"); gid=int(gid_s)
    if not await can_panel(call,bot,gid): return
    text={
        "mute":"<code>/mute 30m</code> respondiendo al usuario.",
        "unmute":"<code>/unmute</code> respondiendo al usuario.",
        "ban":"<code>/ban</code> respondiendo al usuario.",
        "unban":"<code>/unban ID</code> o respondiendo al usuario.",
        "warn":"<code>/warn</code> respondiendo al usuario.",
        "unwarn":"<code>/unwarn</code> respondiendo al usuario.",
        "del":"<code>/del</code> respondiendo al mensaje.",
        "delall":"<code>/delall</code> respondiendo al usuario.",
        "pin":"<code>/pin</code> respondiendo al mensaje.",
    }.get(cmd,"Consulta /help")
    await call.answer(); await call.message.edit_text("🛡️ <b>AYUDA</b>\n\n"+text,reply_markup=main_kb(gid))
