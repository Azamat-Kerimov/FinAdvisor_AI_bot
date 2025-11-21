import os
import asyncio
import asyncpg
import uuid
import base64
import csv
import datetime
import matplotlib.pyplot as plt

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from dotenv import load_dotenv

# ЗАГРУЗКА .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

G_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
G_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
G_SCOPE = os.getenv("GIGACHAT_SCOPE")
G_AUTH_URL = os.getenv("GIGACHAT_AUTH_URL")
G_API_URL = os.getenv("GIGACHAT_API_URL")

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db: asyncpg.pool.Pool = None  # Глобальная переменная пула

async def main():
    global db
    from modules.db import create_db_pool
    db = await create_db_pool()  # Инициализация пула БД в async функции
    print("DB connected.")

    from modules.handlers import *  # Импорт обработчиков после инициализации db

    from modules.utils import start_scheduler
    start_scheduler()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
