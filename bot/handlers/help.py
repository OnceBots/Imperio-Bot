from __future__ import annotations

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from .common import require_group_operator
from ..keyboards import help_kb, back_kb

router = Router()

COMMANDS_TEXT = (
"<b>🏛️ IMPERIO OTOMANO — AYUDA</b>\n"
"━━━━━━━━━━━━━━━━━━\n"
"<b>🛡️ Moderación</b>\n"
"/del — borra el mensaje al que respondes\n"
"/ban — banea al usuario respondido\n"
"/unban ID — quita el baneo\n"
"/mute [30m|2h|1d] — silencia\n"
"/unmute — quita el silencio\n"
"/warn — suma una advertencia\n"
"/unwarn — elimina sus advertencias\n"
"/delall — menú para purgar/expulsar\n"
"/pin — fija el mensaje respondido\n\n"
"<b>👑 Staff y etiquetas</b>\n"
"/promotestaff [ID] [título]\n"
"/etiqueta TEXTO (alias /tag /titulo)\n\n"
"<b>📊 Estadísticas</b>\n"
"/aportes — aportes multimedia de la semana\n"
"/topaportes — top semanal\n\n"
"<b>📢 Difusión</b>\n"
"/s TEXTO — publica como el bot y borra el comando\n"
".s TEXTO — alias rápido\n\n"
"<b>📜 Normas y panel</b>\n"
"/leyes o /reglas — reglas temporales\n"
"/panel — abre el panel de administración\n"
"/help /ayuda /comandos — esta ayuda\n\n"
"<i>El bot también puede eliminar automáticamente mensajes de servicio si la función está activa.</i>"
)

@router.message(CommandStart())
async def start(message: Message, bot: Bot):
    if message.chat.type != "private":
        return
    await message.answer(
        "🏛️ <b>Imperio Otomano</b>\n\n"
        "Bot de administración para tu grupo.\n"
        "Usa <code>/panel</code> dentro del grupo para vincularlo y luego abre la consola privada.\n\n"
        "Escribe <code>/help</code> para ver los comandos."
    )

@router.message(Command("help", "ayuda", "comandos"))
async def help_cmd(message: Message, bot: Bot):
    if message.chat.type == "private":
        return await message.answer(COMMANDS_TEXT)
    if not await require_group_operator(message, bot):
        return
    await message.reply(COMMANDS_TEXT)

@router.callback_query(F.data.startswith("menu_help:"))
async def menu_help(call: CallbackQuery, bot: Bot):
    group_id = int(call.data.split(":")[1])
    if not await require_group_operator(call, bot, group_id): return
    await call.answer()
    await call.message.edit_text("📖 <b>AYUDA TÁCTICA</b>\n\nElige una categoría o consulta todos los comandos.", reply_markup=help_kb(group_id))

@router.callback_query(F.data.startswith("help:"))
async def help_category(call: CallbackQuery, bot: Bot):
    _, category, group_id_s = call.data.split(":")
    group_id = int(group_id_s)
    if not await require_group_operator(call, bot, group_id): return
    texts = {
        "mod": "🛡️ <b>MODERACIÓN</b>\n\n<code>/del</code> responde a un mensaje.\n<code>/ban</code> / <code>/unban ID</code>.\n<code>/mute 30m</code> / <code>/unmute</code>.\n<code>/warn</code> / <code>/unwarn</code>.\n<code>/delall</code> abre purga por usuario.\n<code>/pin</code> fija un mensaje.",
        "staff": "👑 <b>STAFF</b>\n\n<code>/promotestaff</code> con respuesta o ID añade al Staff y lo promociona con permisos limitados.\n<code>/etiqueta</code>, <code>/tag</code> y <code>/titulo</code> modifican el título del administrador cuando Telegram lo permite.",
        "clean": "🧹 <b>LIMPIEZA</b>\n\nSe borran automáticamente mensajes de servicio configurables. También hay una cola de multimedia para la purga automática periódica.",
        "filter": "🚫 <b>FILTROS</b>\n\nEl filtro de palabras se gestiona desde el panel. El anti-enlaces puede activarse/desactivarse desde configuración.",
        "stats": "📊 <b>ESTADÍSTICAS</b>\n\n<code>/aportes</code> muestra tu semana actual y <code>/topaportes</code> muestra el ranking.",
        "config": "⚙️ <b>CONFIGURACIÓN</b>\n\nDesde el panel puedes controlar limpieza de servicio, anti-bot, filtros y permisos del chat.",
        "all": COMMANDS_TEXT,
    }
    await call.answer()
    await call.message.edit_text(texts.get(category, COMMANDS_TEXT), reply_markup=help_kb(group_id) if category != "all" else back_kb(group_id))

