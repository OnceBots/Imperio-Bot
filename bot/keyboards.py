from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from bot.config import PERM_MAPPING

def get_main_dashboard_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔒 Cerrar Chat", callback_data=f"lock_confirm_{group_id}"),
            InlineKeyboardButton(text="🔓 Abrir Chat", callback_data=f"unlock_confirm_{group_id}")
        ],
        [
            InlineKeyboardButton(text="⚙️ Permisos", callback_data=f"perms_{group_id}"),
            InlineKeyboardButton(text="🔍 Auditoría", callback_data=f"botperms_{group_id}")
        ],
        [
            InlineKeyboardButton(text="🧹 Purga Automática", callback_data=f"cleanmenu_{group_id}"),
            InlineKeyboardButton(text="🚫 Filtro Palabras", callback_data=f"badwords_{group_id}")
        ],
        [
            InlineKeyboardButton(text="👑 Gestión Staff", callback_data=f"staffmenu_{group_id}"),
            InlineKeyboardButton(text="📖 Guía de Mando", callback_data=f"help_{group_id}")
        ]
    ])

def get_back_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Regresar al Panel", callback_data=f"back_{group_id}")]
    ])

def get_permissions_kb(group_id: int, perms: ChatPermissions) -> InlineKeyboardMarkup:
    buttons, row = [], []
    for key, (attr, name) in PERM_MAPPING.items():
        icon = "🟢" if getattr(perms, attr, False) else "🔴"
        row.append(InlineKeyboardButton(text=f"{icon} {name}", callback_data=f"tp_{group_id}_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ Volver", callback_data=f"back_{group_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
