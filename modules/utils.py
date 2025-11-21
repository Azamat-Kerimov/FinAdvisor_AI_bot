# modules/utils.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
import asyncio

# Предполагается, что bot создан в bot.py и импортируется
from bot import bot
from modules.db import create_db_pool
from modules.db import db

async def weekly_report():
    from modules.db import db
    users = await db.fetch("SELECT id, tg_id FROM users")

    for u in users:
        summary = await analyse_finances(u["id"])
        try:
            await bot.send_message(u["tg_id"], f"Еженедельный отчёт 📊:\n\n{summary}")
        except:
            pass

def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(weekly_report, "cron", day_of_week="mon", hour=9, minute=0)
    scheduler.start()

# Вы также можете добавить в utils.py функции для работы с базой, если нужно.



