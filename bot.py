import os
import asyncio
import asyncpg
import certifi
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
import httpx

load_dotenv()

# -----------------------------
# Параметры
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

GIGACHAT_API_KEY = os.getenv("GIGACHAT_API_KEY")
GIGACHAT_API_URL = os.getenv("GIGACHAT_API_URL")
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE")
GIGACHAT_AUTH_URL = os.getenv("GIGACHAT_AUTH_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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

# -----------------------------
# FSM: добавление транзакции
# -----------------------------
class AddTransaction(StatesGroup):
    waiting_for_amount = State()

class AddGoal(StatesGroup):
    waiting_for_title = State()
    waiting_for_target = State()

# -----------------------------
# GigaChat запрос
# -----------------------------
async def get_gigachat_token():
    """Получаем токен GigaChat"""
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            GIGACHAT_AUTH_URL,
            json={
                "grant_type": "client_credentials",
                "client_id": GIGACHAT_CLIENT_ID,
                "client_secret": GIGACHAT_CLIENT_SECRET,
                "scope": GIGACHAT_SCOPE
            }
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]

async def gigachat_request(messages):
    token = await get_gigachat_token()
    async with httpx.AsyncClient(timeout=40.0, verify=False) as client:
        
        r = await client.post(
            GIGACHAT_API_URL,
            headers={
                "Authorization": f"Bearer {token}",
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

# -----------------------------
# Работа с AI-контекстом
# -----------------------------
async def get_full_context(user_id):
    rows = await db.fetch("""
        SELECT role, content
        FROM ai_context
        WHERE user_id = $1
        ORDER BY id ASC
    """, user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

async def save_message(user_id, role, content):
    await db.execute("""
        INSERT INTO ai_context (user_id, role, content)
        VALUES ($1, $2, $3)
    """, user_id, role, content)

# -----------------------------
# Анализ транзакций
# -----------------------------
async def analyze_user_finances(user_id):
    rows = await db.fetch("""
        SELECT amount, created_at
        FROM transactions
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 200
    """, user_id)

    text = "Последние транзакции:\n"
    if not rows:
        text += "Нет транзакций.\n"
    else:
        for r in rows:
            text += f"- {r['amount']}₽ ({r['created_at']})\n"

    goals = await db.fetch("""
        SELECT title, target, current, created_at
        FROM goals
        WHERE user_id = $1
    """, user_id)
    if goals:
        text += "\nЦели:\n"
        for g in goals:
            text += f"- {g['title']}: {g['current']} / {g['target']}₽ (создано {g['created_at']})\n"

    return text

# -----------------------------
# Генерация AI ответа
# -----------------------------
async def generate_ai_reply(user_id, user_message):
    await save_message(user_id, "user", user_message)
    context = await get_full_context(user_id)
    finance_data = await analyze_user_finances(user_id)

    system_prompt = f"""
Ты — умный финансовый ассистент.
Используй всю историю диалога и анализ транзакций/целей.

Вот данные пользователя:
{finance_data}

Давай полезный, персонализированный финансовый совет.
"""
    messages = [{"role": "system", "content": system_prompt}] + context + [{"role": "user", "content": user_message}]
    ai_answer = await gigachat_request(messages)
    await save_message(user_id, "assistant", ai_answer)
    return ai_answer

# -----------------------------
# Пользователь
# -----------------------------
async def get_or_create_user(tg_id):
    row = await db.fetchrow("SELECT * FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]
    row = await db.fetchrow("INSERT INTO users (tg_id) VALUES ($1) RETURNING id", tg_id)
    return row["id"]

# -----------------------------
# /start
# -----------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    await message.answer("Привет! Я финансовый ассистент. Задай мне любой вопрос, и я помогу!")

# -----------------------------
# /help
# -----------------------------
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "/start - запуск бота\n"
        "/add - добавить транзакцию\n"
        "/goal - добавить цель\n"
        "/help - показать команды"
    )
    await message.answer(text)

# -----------------------------
# /add
# -----------------------------
@dp.message(Command("add"))
async def cmd_add(message: types.Message, state: FSMContext):
    await state.set_state(AddTransaction.waiting_for_amount)
    await message.answer("Введите сумму транзакции в рублях:")

@dp.message(AddTransaction.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите число.")
        return
    user_id = await get_or_create_user(message.from_user.id)
    await db.execute("INSERT INTO transactions (user_id, amount, created_at) VALUES ($1, $2, NOW())", user_id, amount)
    await save_message(user_id, "system", f"Пользователь добавил транзакцию: {amount}₽")
    await message.answer(f"Транзакция {amount}₽ добавлена!")
    await state.clear()

# -----------------------------
# /goal
# -----------------------------
@dp.message(Command("goal"))
async def cmd_goal(message: types.Message, state: FSMContext):
    await state.set_state(AddGoal.waiting_for_title)
    await message.answer("Введите название цели:")

@dp.message(AddGoal.waiting_for_title)
async def process_goal_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddGoal.waiting_for_target)
    await message.answer("Введите сумму цели:")

@dp.message(AddGoal.waiting_for_target)
async def process_goal_target(message: types.Message, state: FSMContext):
    try:
        target = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите число.")
        return
    user_id = await get_or_create_user(message.from_user.id)
    data = await state.get_data()
    title = data.get("title", "Цель")
    await db.execute("INSERT INTO goals (user_id, title, target, current, created_at) VALUES ($1, $2, $3, 0, NOW())", user_id, title, target)
    await save_message(user_id, "system", f"Пользователь добавил цель '{title}' на {target}₽")
    await message.answer(f"Цель '{title}' на {target}₽ добавлена!")
    await state.clear()

# -----------------------------
# Все остальные сообщения
# -----------------------------
@dp.message()
async def handle_msg(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    user_text = message.text
    reply = await generate_ai_reply(user_id, user_text)
    await message.answer(reply)

# -----------------------------
# Старт бота
# -----------------------------
async def main():
    global db
    db = await create_db_pool()
    print("DB connected. Bot started.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
