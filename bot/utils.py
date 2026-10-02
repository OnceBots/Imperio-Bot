from __future__ import annotations

import html
import re
from datetime import timedelta
from aiogram.types import Message, User

DURATION_RE = re.compile(r"^(?P<value>\d{1,5})(?P<unit>[mhd]?)$", re.I)


def esc(value: str | None) -> str:
    return html.escape(value or "")


def user_label(user: User | None) -> str:
    if not user:
        return "Usuario"
    name = " ".join(x for x in [user.first_name, user.last_name] if x).strip() or "Usuario"
    return esc(name[:80])


def parse_duration(raw: str | None, default_minutes: int = 60) -> int:
    if not raw:
        return default_minutes
    m = DURATION_RE.fullmatch(raw.strip())
    if not m:
        return default_minutes
    value = int(m.group("value"))
    unit = m.group("unit").lower()
    factor = {"": 1, "m": 1, "h": 60, "d": 1440}[unit]
    return max(1, min(value * factor, 365 * 24 * 60))


def target_from_reply(message: Message) -> User | None:
    return message.reply_to_message.from_user if message.reply_to_message else None


def is_group(message: Message) -> bool:
    return message.chat.type in {"group", "supergroup"}


def get_command_args(message: Message) -> list[str]:
    return (message.text or message.caption or "").split()[1:]


def contains_link(message: Message) -> bool:
    content = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []
    if any(getattr(e, "type", None) in {"url", "text_link"} for e in entities):
        return True
    return bool(re.search(r"(?:https?://|www\.|t\.me/|telegram\.me/|telegram\.dog/)", content, re.I))


def is_media(message: Message) -> bool:
    return any((message.photo, message.video, message.document, message.audio, message.voice, message.video_note, message.animation))


def all_permissions() -> dict[str, bool]:
    return {
        "can_send_messages": True,
        "can_send_audios": True,
        "can_send_documents": True,
        "can_send_photos": True,
        "can_send_videos": True,
        "can_send_video_notes": True,
        "can_send_voice_notes": True,
        "can_send_polls": True,
        "can_send_other_messages": True,
        "can_add_web_page_previews": True,
        "can_react_to_messages": True,
        "can_manage_topics": True,
    }


def locked_permissions() -> dict[str, bool]:
    return {k: False for k in all_permissions()}


def is_service_message(message: Message) -> bool:
    fields = (
        "new_chat_members", "left_chat_member", "chat_owner_left", "chat_owner_changed",
        "new_chat_title", "new_chat_photo", "delete_chat_photo", "group_chat_created",
        "supergroup_chat_created", "channel_chat_created", "message_auto_delete_timer_changed",
        "migrate_to_chat_id", "migrate_from_chat_id", "pinned_message", "boost_added",
        "chat_background_set", "forum_topic_created", "forum_topic_edited", "forum_topic_closed",
        "forum_topic_reopened", "general_forum_topic_hidden", "general_forum_topic_unhidden",
        "giveaway_created", "giveaway", "giveaway_winners", "giveaway_completed",
        "video_chat_scheduled", "video_chat_started", "video_chat_ended",
        "video_chat_participants_invited", "managed_bot_created", "community_chat_added",
        "community_chat_removed", "community_chat_joined", "checklist_tasks_added", "checklist_tasks_done",
    )
    return any(getattr(message, field, None) for field in fields)


def service_category(message: Message) -> str:
    if message.new_chat_members:
        return "join"
    if message.left_chat_member:
        return "leave"
    if message.pinned_message:
        return "pin"
    group_fields = ("new_chat_title", "new_chat_photo", "delete_chat_photo")
    if any(getattr(message, f, None) for f in group_fields):
        return "group_change"
    return "other"
