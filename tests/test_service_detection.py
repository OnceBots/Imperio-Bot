from types import SimpleNamespace
from bot.utils import is_service_message, service_category

def msg(**kwargs):
    base={k:None for k in (
        "new_chat_members","left_chat_member","chat_owner_left","chat_owner_changed","new_chat_title","new_chat_photo","delete_chat_photo","group_chat_created","supergroup_chat_created","channel_chat_created","message_auto_delete_timer_changed","migrate_to_chat_id","migrate_from_chat_id","pinned_message","boost_added","chat_background_set","forum_topic_created","forum_topic_edited","forum_topic_closed","forum_topic_reopened","general_forum_topic_hidden","general_forum_topic_unhidden","giveaway_created","giveaway","giveaway_winners","giveaway_completed","video_chat_scheduled","video_chat_started","video_chat_ended","video_chat_participants_invited","community_chat_added","community_chat_removed","community_chat_joined","checklist_tasks_added","checklist_tasks_done")}
    base.update(kwargs)
    return SimpleNamespace(**base)

def test_join_is_service():
    m=msg(new_chat_members=[object()])
    assert is_service_message(m)
    assert service_category(m)=="join"

def test_pin_is_service():
    m=msg(pinned_message=object())
    assert is_service_message(m)
    assert service_category(m)=="pin"
