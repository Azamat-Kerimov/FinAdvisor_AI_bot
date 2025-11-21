import os
import asyncio
import asyncpg
import uuid
import base64
import csv
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
# GIGACHAT TOKEN (без изменений, рабочий код)
# ======================================================

async def get_gigachat_token():
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

async def gigachat_request(messages):
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
# ANALYZE FINANCES + BALANCE
# ======================================================

async def get_balance(user_id):
    assets_sum = await db.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM assets WHERE user_id=$1", user_id)
    liabilities_sum = await db.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM liabilities WHERE user_id=$1", user_id)
    balance = assets_sum - liabilities_sum
    return balance, assets_sum, liabilities_sum

async def analyze_finances(user_id):
    rows = await db.fetch("""
        SELECT amount, category, created_at
        FROM transactions
        WHERE user_id=$1
        ORDER BY created_at DESC
        LIMIT 100
    """, user_id)

    balance, assets_sum, liabilities_sum = await get_balance(user_id)

    if not rows:
        text = "У пользователя нет транзакций.\n"
    else:
        text = "Последние транзакции:\n"
        for r in rows:
            text += f"- {r['amount']}₽ • {r['category']} • {r['created_at'].strftime('%Y-%m-%d')}\n"

    text += f"\nБаланс:\nАктивы: {assets_sum}₽\nОбязательства: {liabilities_sum}₽\nИтог: {balance}₽"
    return text

# ======================================================
# AI REPLY WITH SUMMARY ALWAYS ENABLED
# ======================================================

async def ai_reply(user_id, user_message):
    await save_message(user_id, "user", user_message)

    context = await get_context(user_id)
    finance_data = await analyze_finances(user_id)

    # Суммаризация всегда включена, удалить возможность переключения
    system_prompt = f"""
Ты — персональный финансовый ассистент.
Используй данные о транзакциях, балансах и историю диалога.

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
# NEW: CONSULT COMMAND - краткие рекомендации на основе данных
# ======================================================

@dp.message(Command("consult"))
async def cmd_consult(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)

    context = await get_context(user_id)
    finance_data = await analyze_finances(user_id)

    system_prompt = f"""
Ты — профессиональный финансовый консультант.
Используй данные о транзакциях, балансах и историю диалога.

На основе этих данных дай краткие рекомендации в виде пошагового плана (например, 3-5 пунктов), что пользователю делать для улучшения финансового состояния.
"""

    messages = [{"role": "system", "content": system_prompt}] + context
    messages.append({"role": "user", "content": "Дай мне рекомендации по улучшению финансов"})

    answer = await gigachat_request(messages)

    await save_message(user_id, "assistant", answer)

    await message.answer(answer)

# ======================================================
# FSM: ADD TRANSACTION (с кнопкой отмены)
# ======================================================

class AddTx(StatesGroup):
    waiting_amount = State()
    waiting_category = State()
    waiting_desc = State()

@dp.callback_query(F.data == "menu_add")
async def menu_add(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddTx.waiting_amount)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    await q.message.answer("Введите сумму расхода:", reply_markup=keyboard)

@dp.message(AddTx.waiting_amount)
async def add_amount(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu())
        return
    try:
        amount = float(message.text)
    except:
        await message.answer("Введите корректную сумму:")
        return

    await state.update_data(amount=amount)
    await state.set_state(AddTx.waiting_category)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    await message.answer("Введите категорию:", reply_markup=keyboard)

@dp.message(AddTx.waiting_category)
async def add_category(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu())
        return
    await state.update_data(category=message.text)
    await state.set_state(AddTx.waiting_desc)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    await message.answer("Введите описание:", reply_markup=keyboard)

@dp.message(AddTx.waiting_desc)
async def add_desc(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu())
        return

    user_id = await get_or_create_user(message.from_user.id)
    data = await state.get_data()

    await db.execute(
        "INSERT INTO transactions (user_id, amount, category, description) VALUES ($1,$2,$3,$4)",
        user_id, data["amount"], data["category"], message.text
    )

    await message.answer("Готово! Транзакция добавлена.", reply_markup=main_menu())
    await state.clear()

# ======================================================
# FSM: ADD GOAL (с кнопкой отмены)
# ======================================================

class AddGoal(StatesGroup):
    waiting_target = State()
    waiting_title = State()

@dp.callback_query(F.data == "menu_goal")
async def menu_goal(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddGoal.waiting_target)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    await q.message.answer("Введите сумму цели:", reply_markup=keyboard)

@dp.message(AddGoal.waiting_target)
async def goal_target(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu())
        return
    try:
        target = float(message.text)
    except:
        await message.answer("Введите корректную сумму:")
        return

    await state.update_data(target=target)
    await state.set_state(AddGoal.waiting_title)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    await message.answer("Введите название цели:", reply_markup=keyboard)

@dp.message(AddGoal.waiting_title)
async def goal_title(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu())
        return

    user_id = await get_or_create_user(message.from_user.id)
    data = await state.get_data()

    await db.execute(
        "INSERT INTO goals (user_id, target, title) VALUES ($1,$2,$3)",
        user_id, data["target"], message.text
    )

    await message.answer("Цель добавлена.", reply_markup=main_menu())
    await state.clear()

# ======================================================
# NEW: FSM для добавления Активов
# ======================================================

class AddAsset(StatesGroup):
    waiting_amount = State()
    waiting_title = State()
    waiting_type = State()

@dp.callback_query(F.data == "menu_add_asset")
async def menu_add_asset(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddAsset.waiting_amount)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    await q.message.answer("Введите сумму актива:", reply_markup=keyboard)

@dp.message(AddAsset.waiting_amount)
async def asset_amount(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu())
        return
    try:
        amount = float(message.text)
    except:
        await message.answer("Введите корректную сумму:")
        return
    await state.update_data(amount=amount)
    await state.set_state(AddAsset.waiting_title)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    await message.answer("Введите название актива:", reply_markup=keyboard)

@dp.message(AddAsset.waiting_title)
async def asset_title(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu())
        return
    await state.update_data(title=message.text)
    await state.set_state(AddAsset.waiting_type)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Банк", callback_data="asset_type_bank"),
            InlineKeyboardButton(text="Депозит", callback_data="asset_type_deposit"),
        ],
        [
            InlineKeyboardButton(text="Акции", callback_data="asset_type_stocks"),
            InlineKeyboardButton(text="Другое", callback_data="asset_type_other"),
        ],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    await message.answer("Выберите тип актива:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("asset_type_"))
async def asset_type_selected(q: types.CallbackQuery, state: FSMContext):
    asset_type = q.data[len("asset_type_"):]
    data = await state.get_data()
    user_id = await get_or_create_user(q.from_user.id)

    await db.execute(
        "INSERT INTO assets (user_id, amount, title, type, created_at) VALUES ($1, $2, $3, $4, NOW())",
        user_id, data["amount"], data["title"], asset_type
    )
    await q.message.answer("Актив добавлен.", reply_markup=main_menu())
    await state.clear()
    await q.answer()

# ======================================================
# NEW: FSM для добавления Обязательств
# ======================================================

class AddLiability(StatesGroup):
    waiting_amount = State()
    waiting_title = State()
    waiting_type = State()

@dp.callback_query(F.data == "menu_add_liability")
async def menu_add_liability(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddLiability.waiting_amount)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    await q.message.answer("Введите сумму обязательства:", reply_markup=keyboard)

@dp.message(AddLiability.waiting_amount)
async def liability_amount(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu())
        return
    try:
        amount = float(message.text)
    except:
        await message.answer("Введите корректную сумму:")
        return
    await state.update_data(amount=amount)
    await state.set_state(AddLiability.waiting_title)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    await message.answer("Введите название обязательства:", reply_markup=keyboard)

@dp.message(AddLiability.waiting_title)
async def liability_title(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu())
        return
    await state.update_data(title=message.text)
    await state.set_state(AddLiability.waiting_type)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Кредит", callback_data="liability_type_loan"),
            InlineKeyboardButton(text="Другие долги", callback_data="liability_type_other"),
        ],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    await message.answer("Выберите тип обязательства:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("liability_type_"))
async def liability_type_selected(q: types.CallbackQuery, state: FSMContext):
    liability_type = q.data[len("liability_type_"):]
    data = await state.get_data()
    user_id = await get_or_create_user(q.from_user.id)

    await db.execute(
        "INSERT INTO liabilities (user_id, amount, title, type, created_at) VALUES ($1, $2, $3, $4, NOW())",
        user_id, data["amount"], data["title"], liability_type
    )
    await q.message.answer("Обязательство добавлено.", reply_markup=main_menu())
    await state.clear()
    await q.answer()

# ======================================================
# INLINE MENU UPDATED - добавлены кнопки Активы/Обязательства
# ======================================================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить расход", callback_data="menu_add"),
            InlineKeyboardButton(text="➕ Добавить актив", callback_data="menu_add_asset"),
            InlineKeyboardButton(text="➕ Добавить обязательство", callback_data="menu_add_liability"),
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
    # Убрана настройка суммаризации, меню оставлено пустым или можно удалить вызов совсем
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")
        ]
    ])

# ======================================================
# CALLBACK HANDLERS (MENU)
# ======================================================

@dp.callback_query(F.data == "menu_back")
async def back_to_menu(q: types.CallbackQuery):
    await q.message.edit_text("Главное меню:", reply_markup=main_menu())

@dp.callback_query(F.data == "menu_settings")
async def open_settings(q: types.CallbackQuery):
    await q.message.edit_text("Настройки:", reply_markup=settings_menu())

@dp.callback_query(F.data == "cancel")
async def cancel_action(q: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await q.message.edit_text("Действие отменено.", reply_markup=main_menu())
    await q.answer()

# ======================================================
# REPORT MODIFIED (с балансом)
# ======================================================

@dp.callback_query(F.data == "menu_report")
async def menu_report(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)
    r = await analyze_finances(user_id)
    await q.message.answer(r)

# ======================================================
# MONTH CHART MODIFIED (с балансом, активы + обязательства)
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
