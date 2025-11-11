from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
import os
import asyncio
from db import get_connection

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== /start =====
@dp.message(commands=["start"])
async def start(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or "no_name"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO users (tg_id, username) VALUES (%s, %s) ON CONFLICT (tg_id) DO NOTHING RETURNING id",
        (tg_id, username)
    )
    result = cursor.fetchone()
    conn.commit()
    cursor.close()
    conn.close()

    if result:
        await message.answer(f"Привет, {username}! Ты зарегистрирован в FinAdvisor.")
    else:
        await message.answer(f"Привет, {username}! Ты уже зарегистрирован.")

# ===== Запуск бота =====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())