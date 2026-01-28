# Упрощенный Telegram Bot - только подписка и запуск Mini App
# v_01.28.26 - Рефакторинг: бот только для подписки и WebApp

import os
import asyncio
import asyncpg
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://finadvisor-ai.ru")

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

# Глобальные настройки
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db: Optional[asyncpg.pool.Pool] = None


async def create_db_pool():
    """Создать пул подключений к БД"""
    return await asyncpg.create_pool(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
        host=DB_HOST, port=DB_PORT, min_size=1, max_size=6
    )


async def get_or_create_user(tg_id: int) -> int:
    """Получить или создать пользователя"""
    async with db.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
        if not row:
            await conn.execute(
                "INSERT INTO users (tg_id, username, created_at) VALUES ($1, $2, NOW())",
                tg_id, None
            )
            row = await conn.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
        return row['id']


def format_premium_status(premium_until: Optional[datetime]) -> str:
    """Форматировать статус подписки"""
    if premium_until and premium_until > datetime.now():
        return f"✅ Активна до {premium_until.strftime('%d.%m.%Y')}"
    return "❌ Неактивна"


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню с кнопкой WebApp"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 Открыть FinAdvisor",
            web_app=WebAppInfo(url=WEB_APP_URL)
        )]
    ])


@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    """Команда /start - создает пользователя и показывает статус"""
    user_id = await get_or_create_user(m.from_user.id)
    
    # Получаем статус подписки
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT premium_until FROM users WHERE id=$1", user_id
        )
        premium_until = row['premium_until'] if row else None
    
    status_text = format_premium_status(premium_until)
    
    await m.answer(
        f"Привет, {m.from_user.first_name or 'пользователь'}! 👋\n\n"
        f"Я FinAdvisor — твой персональный финансовый помощник.\n\n"
        f"📊 Статус подписки: {status_text}\n\n"
        f"Нажми кнопку ниже, чтобы открыть приложение:",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command("subscribe"))
async def cmd_subscribe(m: types.Message):
    """Команда /subscribe - выбор тарифа и оплата"""
    # TODO: Реализовать Telegram Payments
    # Пока заглушка
    await m.answer(
        "💳 Оплата подписки\n\n"
        "Выберите тариф:\n"
        "• Месяц — 299 ₽\n"
        "• Год — 2990 ₽ (экономия 20%)\n\n"
        "Функционал оплаты будет добавлен в ближайшее время.",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command("status"))
async def cmd_status(m: types.Message):
    """Команда /status - показать статус подписки"""
    user_id = await get_or_create_user(m.from_user.id)
    
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT premium_until FROM users WHERE id=$1", user_id
        )
        premium_until = row['premium_until'] if row else None
    
    status_text = format_premium_status(premium_until)
    
    await m.answer(
        f"📊 Статус подписки\n\n{status_text}",
        reply_markup=get_main_keyboard()
    )


async def on_startup():
    """Инициализация при запуске"""
    global db
    db = await create_db_pool()
    print("DB connected. Bot ready.")


async def on_shutdown():
    """Очистка при остановке"""
    global db
    if db:
        await db.close()
    print("Bot stopped.")


if __name__ == "__main__":
    try:
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        asyncio.run(dp.start_polling(bot))
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down")
