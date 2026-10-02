from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

LINK_REGEX = re.compile(r"(?:https?://|www\.|t\.me/|telegram\.me/|telegram\.dog/)", re.IGNORECASE)

@dataclass(frozen=True)
class Settings:
    bot_token: str
    mongo_uri: str
    db_name: str = "imperio_bot"
    owner_ids: frozenset[int] = field(default_factory=frozenset)
    port: int = 10000
    log_level: str = "INFO"
    auto_delete_service_messages: bool = True
    auto_delete_join_messages: bool = True
    auto_delete_leave_messages: bool = True
    auto_delete_pin_messages: bool = True
    auto_delete_group_change_messages: bool = True
    auto_delete_other_service_messages: bool = True
    auto_cleanup_enabled: bool = True
    auto_cleanup_hours: int = 12
    cleanup_batch_size: int = 100
    notice_ttl: int = 6
    max_warnings: int = 3
    filter_links: bool = True
    anti_bot: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        mongo_uri = os.getenv("MONGO_URI", "").strip()
        if not bot_token:
            raise ValueError("BOT_TOKEN no definido")
        if not mongo_uri:
            raise ValueError("MONGO_URI no definido")
        raw_ids = os.getenv("OWNER_IDS", "")
        owners = frozenset(int(x.strip()) for x in raw_ids.split(",") if x.strip().lstrip("-").isdigit())
        return cls(
            bot_token=bot_token,
            mongo_uri=mongo_uri,
            db_name=os.getenv("DB_NAME", "imperio_bot").strip() or "imperio_bot",
            owner_ids=owners,
            port=max(1, int(os.getenv("PORT", "10000"))),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            auto_delete_service_messages=_env_bool("AUTO_DELETE_SERVICE_MESSAGES", True),
            auto_delete_join_messages=_env_bool("AUTO_DELETE_JOIN_MESSAGES", True),
            auto_delete_leave_messages=_env_bool("AUTO_DELETE_LEAVE_MESSAGES", True),
            auto_delete_pin_messages=_env_bool("AUTO_DELETE_PIN_MESSAGES", True),
            auto_delete_group_change_messages=_env_bool("AUTO_DELETE_GROUP_CHANGE_MESSAGES", True),
            auto_delete_other_service_messages=_env_bool("AUTO_DELETE_OTHER_SERVICE_MESSAGES", True),
            auto_cleanup_enabled=_env_bool("AUTO_CLEANUP_ENABLED", True),
            auto_cleanup_hours=max(1, int(os.getenv("AUTO_CLEANUP_HOURS", "12"))),
            cleanup_batch_size=min(100, max(1, int(os.getenv("CLEANUP_BATCH_SIZE", "100")))),
            notice_ttl=max(0, int(os.getenv("NOTICE_TTL", "6"))),
            max_warnings=max(1, int(os.getenv("MAX_WARNINGS", "3"))),
            filter_links=_env_bool("FILTER_LINKS", True),
            anti_bot=_env_bool("ANTI_BOT", True),
        )

def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}

settings = Settings.from_env()

# Compatibilidad con módulos del proyecto anterior
BOT_TOKEN = settings.bot_token
MONGO_URI = settings.mongo_uri
DB_NAME = settings.db_name
OWNER_IDS = set(settings.owner_ids)
PORT = settings.port

PERM_MAPPING = {
    "msg": ("can_send_messages", "Mensajes"),
    "media": ("can_send_photos", "Fotos"),
    "video": ("can_send_videos", "Vídeos"),
    "doc": ("can_send_documents", "Documentos"),
    "audio": ("can_send_audios", "Audios"),
    "voice": ("can_send_voice_notes", "Notas de voz"),
    "poll": ("can_send_polls", "Encuestas"),
    "react": ("can_react_to_messages", "Reacciones"),
    "web": ("can_add_web_page_previews", "Vista previa"),
    "topics": ("can_manage_topics", "Temas"),
}

ADMIN_PERMS = {
    "can_delete_messages": "Borrar mensajes",
    "can_restrict_members": "Sancionar usuarios",
    "can_pin_messages": "Fijar mensajes",
    "can_promote_members": "Promover administradores",
    "can_change_info": "Modificar información",
    "can_invite_users": "Gestionar invitaciones",
    "can_manage_video_chats": "Gestionar videollamadas",
    "can_manage_topics": "Gestionar temas",
    "can_manage_tags": "Gestionar etiquetas",
}
