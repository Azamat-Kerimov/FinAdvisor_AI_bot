import os
import asyncio
import asyncpg
import base64
import uuid
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import httpx

load_dotenv()

# ==============================================
# ENV
# ==============================================
BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE")
GIGACHAT_AUTH_URL = os.getenv("GIGACHAT_AUTH_URL")
GIGACHAT_API_URL = os.getenv("GIGACHAT_API_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db = None

# ==============================================
# DB INIT
# ==============================================
async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT
    )

# ==============================================
# GIGACHAT: получение токена (как в test_gigachat.py)
# ==============================================
async def get_gigachat_token():
    auth_str = f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Authorization": f"Basic {b64_auth}",
        "RqUID": str(uuid.uuid4())
    }

    data = {"scope": GIGACHAT_SCOPE}

    async with httpx.AsyncClient(verify=False, timeout=20) as client:
        resp = await client.post(GIGACHAT_AUTH_URL, headers=headers, data=data)
        resp.raise_for_status()
        return resp.json()["access_token"]

# ==============================================
# GIGACHAT: отправка сообщений
# ==============================================
async def gigachat_request(messages):
    token = await get_gigachat_token()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    payload = {
        "model": "GigaChat:1.0.26.20",
        "messages": messages
    }

    async with httpx.AsyncClient(verify=False, timeout=40) as client:
        resp = await client.post(GIGACHAT_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

# ==============================================
# AI CONTEXT
# ==============================================
async def get_full_context(user_id):
    rows = await db.fetch("""
        SELECT role, content FROM ai_context
        WHERE user_id=$1 ORDER BY id ASC
    """, user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

async def save_message(user_id, role, content):
    await db.execute("""
        INSERT INTO ai_context (user_id, role, content)
        VALUES ($1, $2, $3)
    """, user_id, role, content)

# ==============================================
# ANALYZE USER FINANCES
# ==============================================
async def analyze_user_finances(user_id):
    tx = await db.fetch("""
        SELECT amount, created_at FROM transactions
        WHERE user_id=$1 ORDER BY created_at DESC LIMIT 200
    """, user_id)

    text = "Последние транзакции:\n"
    if not tx:
        text += "Нет транзакций.\n"
    else:
        for t in tx:
            text += f"- {t['amount']}₽ ({t['created_at']})\n"

    goals = await db.fetch("""
        SELECT target, current, created_at FROM goals
        WHERE user_id=$1
    """, user_id)

    if goals:
        text += "\nЦели:\n"
        for g in goals:
            text += f"- {g['current']} / {g['target']}₽ ({g['created_at']})\n"

    return text

# ==============================================
# AI MAIN LOGIC
# ==============================================
async def generate_ai_reply(user_id, user_message):
    await save_message(user_id, "user", user_message)

    context = await get_full_context(user_id)
    finance_data = await analyze_user_finances(user_id)

    system_prompt = f"""
Ты — умный финансовый ассистент.
Используй историю диалога, транзакции и цели пользователя.

Данные:
{finance_data}

Дай персональный совет.
"""

    messages = [{"role": "system", "content": system_prompt}] + context
    messages.append({"role": "user", "content": user_message})

    reply = await gigachat_request(messages)
    await save_message(user_id, "assistant", reply)
    return reply

# ==============================================
# FSM STATES
# ==============================================
class AddTransaction(StatesGroup):
    waiting_amount = State()
    waiting_category = State()
    waiting_description = State()

class AddGoal(StatesGroup):
    waiting_target = State()
    waiting_title = State()

# ==============================================
# USER REGISTRATION
# ==============================================
async def get_or_create_user(tg_id):
    row = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]

    row = await db.fetchrow("""
        INSERT INTO users (tg_id)
        VALUES ($1) RETURNING id
    """, tg_id)
    return row["id"]

# ==============================================
# COMMANDS
# ==============================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await get_or_create_user(message.from_user.id)
    await message.answer(
        "Привет! Я финансовый ассистент.\n"
        "Можешь задавать вопросы или использовать команды:\n"
        "/add — добавить транзакцию\n"
        "/goal — добавить цель\n"
        "/help — помощь"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "/start — запуск бота\n"
        "/add — добавить транзакцию\n"
        "/goal — добавить цель\n"
        "/help — помощь"
    )

# ==============================================
# /add — ДОБАВЛЕНИЕ ТРАНЗАКЦИИ
# ==============================================
@dp.message(Command("add"))
async def cmd_add(message: types.Message, state: FSMContext):
    await state.set_state(AddTransaction.waiting_amount)
    await message.answer("Введите сумму транзакции:")

@dp.message(AddTransaction.waiting_amount)
async def add_amount(message: types.Message, state: FSMContext):
    if not message.text.replace(".", "", 1).isdigit():
        return await message.answer("Введите число:")
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

# ==============================================
# /goal — ДОБАВЛЕНИЕ ЦЕЛИ
# ==============================================
@dp.message(Command("goal"))
async def cmd_goal(message: types.Message, state: FSMContext):
    await state.set_state(AddGoal.waiting_target)
    await message.answer("Введите сумму цели:")

@dp.message(AddGoal.waiting_target)
async def goal_target(message: types.Message, state: FSMContext):
    if not message.text.replace(".", "", 1).isdigit():
        return await message.answer("Введите корректное число:")
    await state.update_data(target=float(message.text))
    await state.set_state(AddGoal.waiting_title)
    await message.answer("Введите название цели:")

@dp.message(AddGoal.waiting_title)
async def goal_title(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = await get_or_create_user(message.from_user.id)

    await db.execute("""
        INSERT INTO goals (user_id, target, current)
        VALUES ($1, $2, 0)
    """, user_id, data["target"])

    await message.answer("Цель сохранена ✅")
    await state.clear()

# ==============================================
# CATCH-ALL AI
# ==============================================
@dp.message()
async def handle_msg(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    reply = await generate_ai_reply(user_id, message.text)
    await message.answer(reply)

# ==============================================
# RUN BOT
# ==============================================
async def main():
    global db
    db = await create_db_pool()
    print("DB connected! Bot working.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
