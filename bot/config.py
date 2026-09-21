import os
import re
from typing import Set
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("CRÍTICO: BOT_TOKEN no definido en .env")

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("CRÍTICO: MONGO_URI no definido en .env")

PORT = int(os.getenv("PORT", "10000"))
raw_owners = os.getenv("OWNER_IDS", "")
OWNER_IDS: Set[int] = {int(x.strip()) for x in raw_owners.split(",") if x.strip().isdigit()}

LINK_REGEX = re.compile(r'(https?://|www\.|t\.me/|telegram\.me/)', re.IGNORECASE)

PERM_MAPPING = {
    "msg": ("can_send_messages", "Mensajes"),
    "media": ("can_send_photos", "Multimedia"),
    "doc": ("can_send_documents", "Documentos"),
    "voice": ("can_send_voice_notes", "Notas de Voz"),
    "poll": ("can_send_polls", "Encuestas"),
    "web": ("can_add_web_page_previews", "Vista Previa"),
    "info": ("can_change_info", "Info Grupo"),
    "inv": ("can_invite_users", "Invitaciones"),
    "pin": ("can_pin_messages", "Fijar Mensajes")
}

ADMIN_PERMS = {
    "can_delete_messages": "Borrar Mensajes",
    "can_restrict_members": "Sancionar Usuarios",
    "can_promote_members": "Promover / Editar Etiquetas",
    "can_change_info": "Modificar Ajustes",
    "can_invite_users": "Gestionar Enlaces",
    "can_pin_messages": "Fijar Mensajes"
}
