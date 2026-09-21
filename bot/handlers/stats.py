import json
import urllib.parse
from datetime import datetime
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message
from bot.database import stats_col, is_admin

router = Router()

@router.message(Command("aportes"))
async def user_stats_cmd(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        return
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    current_week = datetime.now().strftime("%Y-W%V")

    stat = await stats_col.find_one({"chat_id": message.chat.id, "user_id": target.id, "week": current_week})
    count = stat.get("count", 0) if stat else 0

    await message.reply(
        f"┌── <b>MÉTRICAS DE APORTES</b>\n"
        f"│ 👤 <b>Colaborador:</b> <code>{target.first_name}</code>\n"
        f"│ 📅 <b>Semana:</b> <code>{current_week}</code>\n"
        f"└── 📦 <b>Envíos multimedia:</b> <code>{count}</code>"
    )

@router.message(Command("topaportes"))
async def top_stats_cmd(message: Message, bot: Bot):
    current_week = datetime.now().strftime("%Y-W%V")
    cursor = stats_col.find({"chat_id": message.chat.id, "week": current_week}).sort("count", -1).limit(10)
    top_users = await cursor.to_list(length=10)

    if not top_users:
        return await message.reply("📉 <b>Sin actividad:</b> No hay aportes registrados durante esta semana.")

    total_aportes = sum(u.get("count", 0) for u in top_users)
    week_num = datetime.now().strftime("%V")
    year_num = datetime.now().year

    text = (
        "🏛️ <b>CUADRO DE HONOR IMPERIAL</b> 🏛️\n"
        f"⚔️ <i>Semana {week_num} • Ciclo {year_num}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    x_labels, data_points = [], []
    bg_colors, border_colors = [], []

    for idx, user in enumerate(top_users, 1):
        raw_name = user.get("name", "Anónimo")
        safe_name = raw_name.replace("<", "&lt;").replace(">", "&gt;")[:14]
        u_count = user.get("count", 0)

        if idx == 1:
            badge = "🥇"
            bg = "rgba(245, 158, 11, 0.85)"
            border = "#FDE047"
        elif idx == 2:
            badge = "🥈"
            bg = "rgba(148, 163, 184, 0.85)"
            border = "#F1F5F9"
        elif idx == 3:
            badge = "🥉"
            bg = "rgba(217, 119, 6, 0.85)"
            border = "#FBBF24"
        else:
            badge = f"#{idx:02d}"
            bg = "rgba(225, 29, 72, 0.75)"
            border = "#FB7185"

        text += f"{badge} <b>{safe_name}</b> ➜ <code>{u_count:,}</code> aportes\n"
        x_labels.append(f"{badge}\n{safe_name[:8]}")
        data_points.append(u_count)
        bg_colors.append(bg)
        border_colors.append(border)

    text += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Volumen Élite:</b> <code>{total_aportes:,}</code> envíos acumulados\n"
        "👑 <i>¡Honor y gloria a los pilares del Imperio!</i>"
    )

    datasets = []
    if len(data_points) >= 2:
        point_radii = [0] * (len(data_points) - 1) + [6]
        datasets.append({
            "type": "line",
            "data": data_points,
            "borderColor": "#FBBF24",
            "borderWidth": 3,
            "fill": False,
            "tension": 0.35,
            "pointRadius": point_radii,
            "pointBackgroundColor": "#F59E0B",
            "pointBorderColor": "#FFFFFF",
            "pointBorderWidth": 2,
            "order": 1
        })

    datasets.append({
        "type": "bar",
        "data": data_points,
        "backgroundColor": bg_colors,
        "borderColor": border_colors,
        "borderWidth": 1.5,
        "borderRadius": 8,
        "borderSkipped": "bottom",
        "maxBarThickness": 48,
        "barPercentage": 0.6,
        "categoryPercentage": 0.7,
        "order": 2
    })

    chart_config = {
        "type": "bar",
        "data": {
            "labels": x_labels,
            "datasets": datasets
        },
        "options": {
            "legend": {"display": False},
            "layout": {
                "padding": {"top": 40, "bottom": 10, "left": 20, "right": 20}
            },
            "plugins": {
                "datalabels": {
                    "display": True,
                    "anchor": "end",
                    "align": "top",
                    "offset": 6,
                    "color": "#F8FAFC",
                    "font": {"size": 13, "weight": "bold"}
                }
            },
            "scales": {
                "xAxes": [{
                    "gridLines": {
                        "display": False,
                        "drawBorder": True,
                        "color": "#475569",
                        "lineWidth": 2
                    },
                    "ticks": {
                        "fontColor": "#CBD5E1",
                        "fontSize": 12,
                        "fontStyle": "bold"
                    }
                }],
                "yAxes": [{
                    "display": False,
                    "ticks": {
                        "beginAtZero": True,
                        "suggestedMax": max(data_points, default=5) * 1.25
                    }
                }]
            }
        }
    }

    encoded = urllib.parse.quote(json.dumps(chart_config))
    url = f"https://quickchart.io/chart?c={encoded}&w=680&h=380&bkg=rgb(15,23,42)"
    try:
        await bot.send_photo(chat_id=message.chat.id, photo=url, caption=text)
    except Exception:
        await message.reply(text)

@router.message(F.text.startswith(("/s ", ".s ")) | F.caption.startswith(("/s ", ".s ")))
async def ghost_broadcast_cmd(message: Message, bot: Bot):
    if message.chat.type in ["group", "supergroup"] and await is_admin(message.chat.id, message.from_user.id, bot):
        try:
            if message.text:
                content = message.text[3:].strip()
                await message.answer(content)
            elif message.caption:
                caption = message.caption[3:].strip()
                await message.copy_to(chat_id=message.chat.id, caption=caption)
            await message.delete()
        except Exception:
            pass
