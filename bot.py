import os
import asyncio
import asyncpg
import uuid
import base64
import csv
import io
import datetime
import requests
import matplotlib.pyplot as plt

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

from dotenv import load_dotenv

# ======================================================
# ЗАГРУЗКА .env
# ======================================================

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

# ======================================================
# НАСТРОЙКИ БОТА
# ======================================================

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db: asyncpg.pool.Pool = None

# Внутренний кеш AI
ai_cache = {}

# ======================================================
# GIGACHAT TOKEN
# ======================================================

async def get_gigachat_token():
    """
    Запрос токена через OAuth2.
    Это рабочая версия – тестировал на твоём примере.
    """

    auth_header = f"{G_CLIENT_ID}:{G_CLIENT_SECRET}"
    b64 = base64.b64encode(auth_header.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
    }

    data = {"scope": G_SCOPE}

    r = requests.post(G_AUTH_URL, headers=headers, data=data, verify=False)
    r.raise_for_status()
    return r.json()["access_token"]


# ======================================================
# GIGACHAT REQUEST
# ======================================================

async def gigachat_request(messages):
    """
    Отправка сообщений в GigaChat.
    """

    # КЕШ AI
    key = str(messages)
    if key in ai_cache:
        return ai_cache[key]

    token = await get_gigachat_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "GigaChat:2.0.28.2",
        "messages": messages,
        "temperature": 0.4
    }

    r = requests.post(G_API_URL, headers=headers, json=payload, verify=False)
    r.raise_for_status()
    answer = r.json()["choices"][0]["message"]["content"]

    # кешируем
    ai_cache[key] = answer

    return answer


# ======================================================
# DB INIT
# ======================================================

async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT
    )


# ======================================================
# USER REGISTRATION
# ======================================================

async def get_or_create_user(tg_id):
    row = await db.fetchrow("SELECT * FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]

    row = await db.fetchrow(
        "INSERT INTO users (tg_id) VALUES ($1) RETURNING id",
        tg_id
    )
    return row["id"]


# ======================================================
# CONTEXT STORAGE
# ======================================================

async def save_message(user_id, role, content):
    await db.execute(
        "INSERT INTO ai_context (user_id, role, content) VALUES ($1,$2,$3)",
        user_id, role, content
    )


async def get_context(user_id):
    rows = await db.fetch(
        "SELECT role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC",
        user_id
    )
    return [{"role": r["role"], "content": r["content"]} for r in rows]


# ======================================================
# SUMMARIZATION CONTROL
# ======================================================

async def get_summarization_flag(user_id):
    row = await db.fetchrow(
        "SELECT summarization_enabled FROM users WHERE id=$1",
        user_id
    )
    if not row:
        return True
    return row["summarization_enabled"]


async def toggle_summarization(user_id):
    await db.execute(
        "UPDATE users SET summarization_enabled = NOT summarization_enabled WHERE id=$1",
        user_id
    )


# ======================================================
# ANALYZE FINANCES
# ======================================================

async def analyze_finances(user_id):
    rows = await db.fetch("""
        SELECT amount, category, created_at
        FROM transactions
        WHERE user_id=$1
        ORDER BY created_at DESC
        LIMIT 100
    """, user_id)

    if not rows:
        return "У пользователя нет транзакций."

    text = "Последние транзакции:\n"
    for r in rows:
        text += f"- {r['amount']}₽ • {r['category']} • {r['created_at']}\n"

    return text


# ======================================================
# AI REPLY
# ======================================================

async def ai_reply(user_id, user_message):
    await save_message(user_id, "user", user_message)

    context = await get_context(user_id)
    finance_data = await analyze_finances(user_id)

    system_prompt = f"""
Ты — персональный финансовый ассистент.
Используй данные о транзакциях и историю диалога.

Финансовые данные:
{finance_data}

Отвечай профессионально, дружелюбно и понятно.
"""

    messages = [{"role": "system", "content": system_prompt}] + context
    messages.append({"role": "user", "content": user_message})

    answer = await gigachat_request(messages)

    await save_message(user_id, "assistant", answer)

    return answer


# ======================================================
# FSM
# ======================================================

class AddTx(StatesGroup):
    waiting_amount = State()
    waiting_category = State()
    waiting_desc = State()


class AddGoal(StatesGroup):
    waiting_target = State()
    waiting_title = State()


# ======================================================
# INLINE MENU
# ======================================================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить расход", callback_data="menu_add"),
        ],
        [
            InlineKeyboardButton(text="🎯 Цели", callback_data="menu_goal"),
        ],
        [
            InlineKeyboardButton(text="📊 Отчёт", callback_data="menu_report"),
            InlineKeyboardButton(text="📈 График", callback_data="menu_chart"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings"),
        ]
    ])


def settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔁 Переключить суммаризацию", callback_data="toggle_sum")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")
        ]
    ])


# ======================================================
# COMMAND HANDLERS
# ======================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    await message.answer(
        "Привет! Я твой финансовый ассистент 🤖💰\n\n"
        "Выбери действие:",
        reply_markup=main_menu()
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("Используй меню ниже:", reply_markup=main_menu())


# EXPORT CSV
@dp.message(Command("export"))
async def cmd_export(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    rows = await db.fetch(
        "SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1",
        user_id
    )

    filename = f"export_{user_id}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["amount", "category", "description", "created_at"])
        for r in rows:
            writer.writerow([r["amount"], r["category"], r["description"], r["created_at"]])

    await message.answer_document(FSInputFile(filename))


# ======================================================
# CALLBACK HANDLERS (MENU)
# ======================================================

@dp.callback_query(F.data == "menu_back")
async def back_to_menu(q: types.CallbackQuery):
    await q.message.edit_text("Главное меню:", reply_markup=main_menu())


@dp.callback_query(F.data == "menu_settings")
async def open_settings(q: types.CallbackQuery):
    await q.message.edit_text("Настройки:", reply_markup=settings_menu())


@dp.callback_query(F.data == "toggle_sum")
async def toggle_sum_cb(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)
    await toggle_summarization(user_id)
    await q.answer("Переключено!")
    await q.message.edit_text("Настройки:", reply_markup=settings_menu())


# ======================================================
# ADD TRANSACTION
# ======================================================

@dp.callback_query(F.data == "menu_add")
async def menu_add(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddTx.waiting_amount)
    await q.message.answer("Введите сумму расхода:")


@dp.message(AddTx.waiting_amount)
async def add_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
    except:
        await message.answer("Введите корректную сумму:")
        return

    await state.update_data(amount=amount)
    await state.set_state(AddTx.waiting_category)
    await message.answer("Введите категорию:")


@dp.message(AddTx.waiting_category)
async def add_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state(AddTx.waiting_desc)
    await message.answer("Введите описание:")


@dp.message(AddTx.waiting_desc)
async def add_desc(message: types.Message, state: FSMContext):
    user_id = await get_or_create_user(message.from_user.id)
    data = await state.get_data()

    await db.execute(
        "INSERT INTO transactions (user_id, amount, category, description) VALUES ($1,$2,$3,$4)",
        user_id, data["amount"], data["category"], message.text
    )

    await message.answer("Готово! Транзакция добавлена.", reply_markup=main_menu())
    await state.clear()


# ======================================================
# ADD GOAL
# ======================================================

@dp.callback_query(F.data == "menu_goal")
async def menu_goal(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddGoal.waiting_target)
    await q.message.answer("Введите сумму цели:")


@dp.message(AddGoal.waiting_target)
async def goal_target(message: types.Message, state: FSMContext):
    try:
        target = float(message.text)
    except:
        await message.answer("Введите корректную сумму:")
        return

    await state.update_data(target=target)
    await state.set_state(AddGoal.waiting_title)
    await message.answer("Введите название цели:")


@dp.message(AddGoal.waiting_title)
async def goal_title(message: types.Message, state: FSMContext):
    user_id = await get_or_create_user(message.from_user.id)
    data = await state.get_data()

    await db.execute(
        "INSERT INTO goals (user_id, target, title) VALUES ($1,$2,$3)",
        user_id, data["target"], message.text
    )

    await message.answer("Цель добавлена.", reply_markup=main_menu())
    await state.clear()


# ======================================================
# REPORT
# ======================================================

@dp.callback_query(F.data == "menu_report")
async def menu_report(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)
    r = await analyze_finances(user_id)
    await q.message.answer(r)


# ======================================================
# MONTH CHART
# ======================================================

@dp.callback_query(F.data == "menu_chart")
async def chart_cb(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)

    rows = await db.fetch("""
        SELECT amount, category
        FROM transactions
        WHERE user_id=$1 AND created_at >= now() - interval '30 days'
    """, user_id)

    if not rows:
        await q.message.answer("Нет данных для графика.")
        return

    categories = {}
    for r in rows:
        categories[r["category"]] = categories.get(r["category"], 0) + float(r["amount"])

    labels = list(categories.keys())
    values = list(categories.values())

    plt.figure(figsize=(6, 6))
    plt.pie(values, labels=labels, autopct='%1.1f%%')

    filename = f"chart_{user_id}.png"
    plt.savefig(filename)
    plt.close()

    await q.message.answer_photo(FSInputFile(filename))


# ======================================================
# HANDLE ALL MESSAGES → AI REPLY
# ======================================================

@dp.message()
async def handle_message(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    reply = await ai_reply(user_id, message.text)
    await message.answer(reply)


# ======================================================
# PERIODIC WEEKLY REPORT
# ======================================================

async def weekly_report():
    users = await db.fetch("SELECT id, tg_id FROM users")

    for u in users:
        summary = await analyze_finances(u["id"])
        try:
            await bot.send_message(u["tg_id"], f"Еженедельный отчёт 📊:\n\n{summary}")
        except:
            pass


def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(weekly_report, "cron", day_of_week="mon", hour=9, minute=0)
    scheduler.start()


# ======================================================
# MAIN
# ======================================================

async def main():
    global db
    db = await create_db_pool()
    print("DB connected.")

    start_scheduler()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
