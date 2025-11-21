# bot.py
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import os

load_dotenv()

from modules.db import create_db_pool
from modules.ai import gigachat_request  # ensure import
from modules.utils import normalize_category  # ensure import

# handlers
from modules.handlers import tx as tx_mod
from modules.handlers import assets as assets_mod
from modules.handlers import reports as reports_mod
from modules.handlers import ai_handlers as ai_mod

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

async def get_or_create_user(tg_id):
    # simple helper using db pool (re-implement here)
    row = await dp['db'].fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]
    row = await dp['db'].fetchrow("INSERT INTO users (tg_id, created_at) VALUES ($1, NOW()) RETURNING id", tg_id)
    return row["id"]

async def save_message(user_id, role, content):
    await dp['db'].execute("INSERT INTO ai_context (user_id, role, content, created_at) VALUES ($1,$2,$3,NOW())",
                           user_id, role, content)

async def get_context(user_id):
    rows = await dp['db'].fetch("SELECT role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC", user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

async def analyze_finances(user_id):
    rows = await dp['db'].fetch("SELECT amount, category, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT 100", user_id)
    if not rows:
        return "У пользователя нет транзакций."
    text = "Последние транзакции:\n"
    for r in rows:
        text += f"- {int(r['amount'])}₽ • {(r['category'] or '-').capitalize()} • {r['created_at']}\n"
    return text

async def on_startup():
    pool = await create_db_pool()
    dp['db'] = pool
    # register handlers from modules (we pass dependencies)
    tx_mod.register_tx_handlers(dp, get_or_create_user, pool, save_message)
    assets_mod.register_asset_handlers(dp, get_or_create_user, pool, save_message)
    reports_mod.register_report_handlers(dp, get_or_create_user, pool, save_message)
    ai_mod.register_ai_handlers(dp, get_or_create_user, pool, save_message)
    print("Bot started, handlers registered.")

if __name__ == "__main__":
    asyncio.run(on_startup())
    asyncio.run(dp.start_polling(bot))













