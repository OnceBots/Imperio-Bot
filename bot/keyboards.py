from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from .config import PERM_MAPPING

def btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)

def main_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🛡️ Moderación", f"menu_mod:{group_id}"), btn("🧹 Limpieza", f"menu_clean:{group_id}")],
        [btn("🚫 Filtros", f"menu_filter:{group_id}"), btn("👑 Staff", f"menu_staff:{group_id}")],
        [btn("🔐 Seguridad", f"menu_security:{group_id}"), btn("📊 Estadísticas", f"menu_stats:{group_id}")],
        [btn("📜 Reglas", f"menu_rules:{group_id}"), btn("📖 Ayuda", f"menu_help:{group_id}")],
        [btn("⚙️ Configuración", f"menu_config:{group_id}")],
    ])

def back_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[btn("◀️ Panel principal", f"home:{group_id}")]])

def mod_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🔇 Silenciar", f"howto:mute:{group_id}"), btn("🔊 Quitar silencio", f"howto:unmute:{group_id}")],
        [btn("🚫 Banear", f"howto:ban:{group_id}"), btn("♻️ Desbanear", f"howto:unban:{group_id}")],
        [btn("⚠️ Advertir", f"howto:warn:{group_id}"), btn("🕊️ Quitar advertencia", f"howto:unwarn:{group_id}")],
        [btn("🗑️ /del", f"howto:del:{group_id}"), btn("🧹 /delall", f"howto:delall:{group_id}")],
        [btn("📌 /pin", f"howto:pin:{group_id}")],
        [btn("◀️ Volver", f"home:{group_id}")],
    ])

def clean_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🧹 Estado de purga", f"clean:status:{group_id}"), btn("⚡ Forzar purga", f"clean:force:{group_id}")],
        [btn("🧾 Cola multimedia", f"clean:queue:{group_id}"), btn("🧼 Servicio ON/OFF", f"clean:toggle_service:{group_id}")],
        [btn("◀️ Volver", f"home:{group_id}")],
    ])

def filter_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📋 Ver palabras", f"filter:view:{group_id}"), btn("➕ Añadir", f"filter:add:{group_id}")],
        [btn("🗑️ Vaciar lista", f"filter:clear:{group_id}"), btn("🔗 Anti-enlaces", f"filter:links:{group_id}")],
        [btn("◀️ Volver", f"home:{group_id}")],
    ])

def staff_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📋 Ver Staff", f"staff:view:{group_id}"), btn("➕ Añadir", f"staff:add:{group_id}")],
        [btn("➖ Quitar", f"staff:remove:{group_id}"), btn("🔄 Sincronizar", f"staff:sync:{group_id}")],
        [btn("◀️ Volver", f"home:{group_id}")],
    ])

def security_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🔒 Cerrar chat", f"security:lock:{group_id}"), btn("🔓 Abrir chat", f"security:unlock:{group_id}")],
        [btn("🤖 Anti-bot ON/OFF", f"security:antibot:{group_id}"), btn("🔔 Servicio ON/OFF", f"security:service:{group_id}")],
        [btn("🔍 Permisos del bot", f"security:botperms:{group_id}"), btn("⚙️ Permisos del chat", f"security:perms:{group_id}")],
        [btn("◀️ Volver", f"home:{group_id}")],
    ])

def stats_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📊 Mis aportes", f"stats:me:{group_id}"), btn("🏆 Top aportes", f"stats:top:{group_id}")],
        [btn("◀️ Volver", f"home:{group_id}")],
    ])

def rules_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📜 Ver reglas", f"rules:view:{group_id}")],
        [btn("◀️ Volver", f"home:{group_id}")],
    ])

def help_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🛡️ Moderación", f"help:mod:{group_id}"), btn("👑 Staff", f"help:staff:{group_id}")],
        [btn("🧹 Limpieza", f"help:clean:{group_id}"), btn("🚫 Filtros", f"help:filter:{group_id}")],
        [btn("📊 Estadísticas", f"help:stats:{group_id}"), btn("⚙️ Config", f"help:config:{group_id}")],
        [btn("📋 Todos los comandos", f"help:all:{group_id}")],
        [btn("◀️ Volver", f"home:{group_id}")],
    ])

def permissions_kb(group_id: int, perms: ChatPermissions) -> InlineKeyboardMarkup:
    rows = []
    for key, (attr, name) in PERM_MAPPING.items():
        value = getattr(perms, attr, False) or False
        rows.append(btn(("🟢 " if value else "🔴 ") + name, f"perm:{group_id}:{key}"))
    grid = [rows[i:i+2] for i in range(0, len(rows), 2)]
    grid.append([btn("◀️ Volver", f"security:perms:{group_id}")])
    return InlineKeyboardMarkup(inline_keyboard=grid)
