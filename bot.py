import os
import asyncio
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import httpx
import certifi
import requests

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

GIGACHAT_API_KEY = os.getenv("GIGACHAT_API_KEY")
GIGACHAT_AUTH_URL = os.getenv("GIGACHAT_AUTH_URL")
GIGACHAT_API_URL = os.getenv("GIGACHAT_API_URL")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# -----------------------------
# ИНИЦИАЛИЗАЦИЯ БАЗЫ
# -----------------------------
async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT
    )

db = None

# -----------------------------------------------------------
# GIGACHAT: функция для запроса токена
# -----------------------------------------------------------


async def get_gigachat_token():
    url = os.getenv("GIGACHAT_AUTH_URL")
    data = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("GIGACHAT_CLIENT_ID"),
        "client_secret": os.getenv("GIGACHAT_CLIENT_SECRET"),
        "scope": os.getenv("GIGACHAT_SCOPE"),
    }

    async with httpx.AsyncClient(verify=False) as client:
        r = await client.post(url, data=data)
        r.raise_for_status()
        resp = r.json()
        return resp["access_token"]


# -----------------------------------------------------------
# GIGACHAT: функция отправки сообщения и получения ответа
# -----------------------------------------------------------
async def gigachat_request(messages):
    token = await get_gigachat_token()

    async with httpx.AsyncClient(timeout=40.0, verify=False) as client:
        r = await client.post(
            os.getenv("GIGACHAT_API_URL"),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "model": "GigaChat-Pro",
                "messages": messages,
                "temperature": 0.3
            }
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
# -----------------------------------------------------------
# AI-КОНТЕКСТ
# -----------------------------------------------------------
async def get_full_context(user_id):
    rows = await db.fetch("""
        SELECT role, content
        FROM ai_context
        WHERE user_id = $1
        ORDER BY id ASC
    """, user_id)
    return [{"role": row["role"], "content": row["content"]} for row in rows]

async def save_message(user_id, role, content):
    await db.execute("""
        INSERT INTO ai_context (user_id, role, content)
        VALUES ($1, $2, $3)
    """, user_id, role, content)

# -----------------------------------------------------------
# АНАЛИЗ ТРАНЗАКЦИЙ
# -----------------------------------------------------------
async def analyze_user_finances(user_id):
    rows = await db.fetch("""
        SELECT amount, created_at
        FROM transactions
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 200
    """, user_id)

    text = "Последние транзакции пользователя:\n"
    if not rows:
        text += "Нет транзакций.\n"
    else:
        for r in rows:
            text += f"- {r['amount']}₽ ({r['created_at']})\n"

    goals = await db.fetch("""
        SELECT target, current, created_at
        FROM goals
        WHERE user_id = $1
    """, user_id)

    if goals:
        text += "\nЦели пользователя:\n"
        for g in goals:
            text += f"- {g['current']} / {g['target']}₽ (создано: {g['created_at']})\n"

    return text

# -----------------------------------------------------------
# ГЛАВНЫЙ AI-ОТВЕТ
# -----------------------------------------------------------
async def generate_ai_reply(user_id, user_message):
    await save_message(user_id, "user", user_message)

    context = await get_full_context(user_id)
    finance_data = await analyze_user_finances(user_id)

    system_prompt = f"""
Ты — умный финансовый ассистент.
Используй всю историю диалога и анализ транзакций и целей пользователя.

Вот данные пользователя:
{finance_data}

Дай полезный, персонализированный финансовый совет.
"""
    messages = [{"role": "system", "content": system_prompt}] + context
    messages.append({"role": "user", "content": user_message})

    ai_answer = await gigachat_request(messages)
    await save_message(user_id, "assistant", ai_answer)

    return ai_answer

# -----------------------------------------------------------
# FSM СТАНЫ ДЛЯ /add и /goal
# -----------------------------------------------------------
class AddTransaction(StatesGroup):
    waiting_amount = State()
    waiting_category = State()
    waiting_description = State()

class AddGoal(StatesGroup):
    waiting_target = State()
    waiting_title = State()

# -----------------------------------------------------------
# РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ
# -----------------------------------------------------------
async def get_or_create_user(tg_id):
    row = await db.fetchrow("SELECT * FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]
    row = await db.fetchrow("""
        INSERT INTO users (tg_id)
        VALUES ($1)
        RETURNING id
    """, tg_id)
    return row["id"]

# -----------------------------------------------------------
# ОБРАБОТЧИКИ КОМАНД
# -----------------------------------------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    await message.answer("Привет! Я финансовый ассистент. Задай мне вопрос или используй команды /add, /goal, /help.")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "/start — запуск бота\n"
        "/add — добавить транзакцию\n"
        "/goal — добавить цель\n"
        "/help — помощь по командам"
    )
    await message.answer(text)

# -----------------------------------------------------------
# /add транзакция
# -----------------------------------------------------------
@dp.message(Command("add"))
async def cmd_add(message: types.Message, state: FSMContext):
    await state.set_state(AddTransaction.waiting_amount)
    await message.answer("Введите сумму транзакции:")

@dp.message(AddTransaction.waiting_amount)
async def add_amount(message: types.Message, state: FSMContext):
    if not message.text.replace(".", "", 1).isdigit():
        await message.answer("Неверная сумма, введите цифру:")
        return
    await state.update_data(amount=float(message.text))
    await state.set_state(AddTransaction.waiting_category)
    await message.answer("Введите категорию:")

@dp.message(AddTransaction.waiting_category)
async def add_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state(AddTransaction.waiting_description)
    await message.answer("Введите описание:")

@dp.message(AddTransaction.waiting_description)
async def add_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = await get_or_create_user(message.from_user.id)
    await db.execute("""
        INSERT INTO transactions (user_id, amount, category, description)
        VALUES ($1, $2, $3, $4)
    """, user_id, data["amount"], data["category"], message.text)
    await message.answer("Транзакция добавлена ✅")
    await state.clear()

# -----------------------------------------------------------
# /goal цель
# -----------------------------------------------------------
@dp.message(Command("goal"))
async def cmd_goal(message: types.Message, state: FSMContext):
    await state.set_state(AddGoal.waiting_target)
    await message.answer("Введите сумму цели:")

@dp.message(AddGoal.waiting_target)
async def goal_target(message: types.Message, state: FSMContext):
    if not message.text.replace(".", "", 1).isdigit():
        await message.answer("Неверная сумма, введите цифру:")
        return
    await state.update_data(target=float(message.text))
    await state.set_state(AddGoal.waiting_title)
    await message.answer("Введите название цели:")

@dp.message(AddGoal.waiting_title)
async def goal_title(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = await get_or_create_user(message.from_user.id)
    await db.execute("""
        INSERT INTO goals (user_id, target, title)
        VALUES ($1, $2, $3)
    """, user_id, data["target"], message.text)
    await message.answer("Цель добавлена ✅")
    await state.clear()

# -----------------------------------------------------------
# ОБРАБОТЧИК ВСЕХ СООБЩЕНИЙ
# -----------------------------------------------------------
@dp.message()
async def handle_msg(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    reply = await generate_ai_reply(user_id, message.text)
    await message.answer(reply)

# -----------------------------------------------------------
# СТАРТ БОТА
# -----------------------------------------------------------
async def main():
    global db
    db = await create_db_pool()
    print("DB connected. Bot started.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
