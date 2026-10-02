from __future__ import annotations
from datetime import datetime
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from ..database import stats_col, is_admin
from ..utils import is_group, user_label

router=Router()

def week_key() -> str:
    return datetime.now().strftime("%Y-W%V")

async def build_stats_text(chat_id:int,user_id:int,action:str="me") -> str:
    week=week_key()
    if action=="me":
        doc=await stats_col.find_one({"chat_id":chat_id,"user_id":user_id,"week":week})
        count=int(doc.get("count",0)) if doc else 0
        return f"📊 <b>MIS APORTES</b>\n\n📅 Semana: <code>{week}</code>\n📦 Multimedia: <code>{count}</code>"
    docs=await stats_col.find({"chat_id":chat_id,"week":week}).sort("count",-1).limit(10).to_list(length=10)
    if not docs: return "📊 <b>TOP APORTES</b>\n\n<i>Sin actividad esta semana.</i>"
    lines=[f"🏆 <b>TOP APORTES — {week}</b>"]
    for i,d in enumerate(docs,1): lines.append(f"{i}. <b>{d.get('name','Anónimo')}</b> — <code>{int(d.get('count',0))}</code>")
    return "\n".join(lines)

@router.message(Command("aportes"))
async def aportes(message:Message,bot:Bot):
    if not is_group(message): return
    target=message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.reply(await build_stats_text(message.chat.id,target.id,"me"))

@router.message(Command("topaportes"))
async def top(message:Message,bot:Bot):
    if not is_group(message): return
    await message.reply(await build_stats_text(message.chat.id,message.from_user.id,"top"))

@router.message(lambda m: bool((m.text or "").startswith(("/s ",".s "))) or bool((m.caption or "").startswith(("/s ",".s "))))
async def ghost_s(message:Message,bot:Bot):
    if not is_group(message) or not await is_admin(message.chat.id,message.from_user.id,bot): return
    source=message.text or message.caption or ""; body=source[3:].strip()
    try:
        if message.text: await message.answer(body)
        else: await message.copy_to(message.chat.id,caption=body)
        await message.delete()
    except Exception: pass
