# bot.py — улучшенная версия с smart-parser, подтверждением и /stats
import os
import re
import io
import math
import base64
import uuid
import asyncio
import asyncpg
from datetime import datetime, timedelta
from functools import partial

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import httpx
import matplotlib.pyplot as plt

load_dotenv()

# ---------------------------
# Конфигурация
# ---------------------------
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

# параметры
CONTEXT_SUMMARY_THRESHOLD = 400      # если записей > этого -> делаем summarization
CONTEXT_TRIM_COUNT = 200            # сколько удалить после суммаризации
GIGACHAT_MODEL = "GigaChat:1.0.26.20"
MAX_TRANSACTIONS_FOR_ANALYSIS = 200

# ---------------------------
# Инициализация бота и DB pool
# ---------------------------
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

db = None

async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT
    )

# ---------------------------
# Временное хранилище подтверждаемой транзакции
# {user_id: {"amount":..., "category":..., "description":...}}
# ---------------------------
pending_tx = {}

# ---------------------------
# GigaChat: получение токена (Basic Auth Base64, как в тесте)
# ---------------------------
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

# ---------------------------
# GigaChat: отправка сообщений
# ---------------------------
async def gigachat_request(messages):
    token = await get_gigachat_token()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {"model": GIGACHAT_MODEL, "messages": messages}
    async with httpx.AsyncClient(verify=False, timeout=40) as client:
        resp = await client.post(GIGACHAT_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

# ---------------------------
# AI-контекст (Postgres)
# ---------------------------
async def save_message(user_id, role, content):
    await db.execute(
        "INSERT INTO ai_context (user_id, role, content) VALUES ($1, $2, $3)",
        user_id, role, content
    )

async def get_context_count(user_id):
    r = await db.fetchrow("SELECT count(*)::int AS c FROM ai_context WHERE user_id=$1", user_id)
    return r["c"] if r else 0

async def get_full_context(user_id):
    rows = await db.fetch("SELECT role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC", user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

# если контекст слишком длинный — суммаризируем старые сообщения, вставляем summary и удаляем старые
async def ensure_compact_context(user_id):
    cnt = await get_context_count(user_id)
    if cnt <= CONTEXT_SUMMARY_THRESHOLD:
        return
    # берем старые сообщения, которые будем суммировать
    rows = await db.fetch("SELECT id, role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC LIMIT $2", user_id, cnt - CONTEXT_TRIM_COUNT)
    if not rows:
        return
    text = ""
    for r in rows:
        text += f"{r['role']}: {r['content']}\n"
    # отправляем запрос на суммаризацию (помним: это платно — используем аккуратно)
    system = {"role":"system","content":"Сделай краткое summary предыдущей истории (несколько предложений). Будь максимально сжатым и сохрани ключевые факты и финансовые выводы."}
    messages = [system, {"role":"user","content":text}]
    try:
        summary = await gigachat_request(messages)
        # вставляем system-summary в контекст
        await save_message(user_id, "system", f"SUMMARY: {summary}")
        # удаляем старые сообщения
        ids = [r["id"] for r in rows]
        await db.execute("DELETE FROM ai_context WHERE id = ANY($1::int[])", ids)
    except Exception as e:
        # если что-то пошло не так — не удаляем ничего
        print("Summarize failed:", e)

# ---------------------------
# Анализ транзакций
# ---------------------------
async def analyze_user_finances(user_id):
    rows = await db.fetch(
        "SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2",
        user_id, MAX_TRANSACTIONS_FOR_ANALYSIS
    )
    if not rows:
        return "У пользователя нет транзакций."
    text = "Последние транзакции (последние записи):\n"
    for r in rows:
        ts = r["created_at"].strftime("%Y-%m-%d")
        text += f"- {r['amount']}₽ | {r['category'] or '—'} | {r['description'] or ''} | {ts}\n"
    # цели
    goals = await db.fetch("SELECT id, target, current, title, created_at FROM goals WHERE user_id=$1", user_id)
    if goals:
        text += "\nЦели:\n"
        for g in goals:
            pr = (g["current"] / g["target"] * 100) if g["target"] else 0
            text += f"- {g['title'] if 'title' in g else 'Цель'}: {g['current']}/{g['target']}₽ ({pr:.1f}%)\n"
    return text

# ---------------------------
# Smart-парсер транзакции
# поддерживает: "+1500", "-200", "1500 еда", "1.5k salary", "1 500 000", "2млн", "150k", ","
# ---------------------------
UNIT_MAP = {
    "k": 1_000, "к": 1_000,
    "m": 1_000_000, "м": 1_000_000, "млн": 1_000_000
}

def parse_amount_token(s: str):
    s = s.strip().lower().replace(" ", "").replace("\u2009","")
    # find sign
    sign = 1
    if s.startswith("+"):
        sign = 1; s = s[1:]
    elif s.startswith("-"):
        sign = -1; s = s[1:]
    # replace comma with dot
    s = s.replace(",", ".")
    # units suffix
    m = re.match(r"^([\d\.]+)([a-zа-яё%]*)$", s)
    if not m:
        raise ValueError("не удалось распознать сумму")
    num = float(m.group(1))
    unit = m.group(2)
    multiplier = 1
    if unit:
        # handle '150k', '1.5млн', 'к'
        for k,v in UNIT_MAP.items():
            if unit.startswith(k):
                multiplier = v
                break
    amount = num * multiplier * sign
    return int(round(amount))

def smart_parse_free_text(text: str):
    """
    возвращает (amount:int, category:str or None, description:str or None)
    """
    text = text.strip()
    # try to find amount token anywhere: look for number with optional signs and units
    amount_token_match = re.search(r"([+-]?\s*\d[\d\s\.,]*(?:[kkmмлн]|к|м|млн|k|m|K|M)?)", text, re.IGNORECASE)
    if not amount_token_match:
        return None
    token = amount_token_match.group(1)
    try:
        amount = parse_amount_token(token)
    except Exception:
        return None
    # remove token from text
    left = (text[:amount_token_match.start()] + text[amount_token_match.end():]).strip()
    if not left:
        return (amount, None, None)
    # guess category as first word
    parts = left.split()
    category = parts[0]
    description = left
    return (amount, category, description)

# ---------------------------
# Пользовательские функции
# ---------------------------
async def get_or_create_user(tg_id):
    row = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]
    row = await db.fetchrow("INSERT INTO users (tg_id, created_at) VALUES ($1, NOW()) RETURNING id", tg_id)
    return row["id"]

# ---------------------------
# Команды
# ---------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = await get_or_create_user(message.from_user.id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("Добавить транзакцию", callback_data="ui_add"),
             InlineKeyboardButton("Мои цели", callback_data="ui_goals")],
            [InlineKeyboardButton("Статистика /stats", callback_data="ui_stats"),
             InlineKeyboardButton("Помощь /help", callback_data="ui_help")]
        ]
    )
    await message.answer(
        "Привет — я финансовый ассистент.\n"
        "Могу считать бюджет, давать советы и следить за целями. Нажми кнопку или напиши сообщение.\n"
        "Примеры ввода транзакции: `-2500 кофе`, `+150000 зарплата`, `1.5k groceries`",
        reply_markup=kb
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Команды:\n"
        "/start — приветствие\n"
        "/add — добавить транзакцию\n"
        "/goal — добавить цель\n"
        "/stats — сводка расходов\n"
        "/balance — баланс по целям"
    )

# ---------------------------
# Inline UI callbacks
# ---------------------------
@dp.callback_query(lambda c: c.data == "ui_add")
async def cb_ui_add(callback: types.CallbackQuery):
    await callback.message.answer("Напиши транзакцию в одной строке, например: `-2500 кофе` или отправь /add")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "ui_stats")
async def cb_ui_stats(callback: types.CallbackQuery):
    await callback.message.answer("Выполняю /stats...")
    await callback.answer()
    # reuse /stats handler
    await cmd_stats(callback.message)

@dp.callback_query(lambda c: c.data == "ui_goals")
async def cb_ui_goals(callback: types.CallbackQuery):
    await callback.message.answer("Вот ваши цели:")
    await callback.answer()
    # list goals
    rows = await db.fetch("SELECT id, title, target, current, created_at FROM goals WHERE user_id=(SELECT id FROM users WHERE tg_id=$1)", callback.from_user.id)
    if not rows:
        await callback.message.answer("Целей не найдено.")
        return
    msg = "Ваши цели:\n"
    for r in rows:
        pr = (r["current"]/r["target"]*100) if r["target"] else 0
        msg += f"- {r.get('title','Цель')} — {r['current']}/{r['target']} ₽ ({pr:.1f}%)\n"
    await callback.message.answer(msg)

@dp.callback_query(lambda c: c.data == "ui_help")
async def cb_ui_help(callback: types.CallbackQuery):
    await callback.message.answer("Смотрите /help для команд.")
    await callback.answer()

# ---------------------------
# /add FSM (fallback also accepts smart free text)
# ---------------------------
class AddTxStates(StatesGroup):
    amount = State()
    category = State()
    description = State()

@dp.message(Command("add"))
async def cmd_add_start(message: types.Message, state: FSMContext):
    await state.set_state(AddTxStates.amount)
    await message.answer("Введите сумму (например: 2500 или -2500 или 1.5k):")

@dp.message(AddTxStates.amount)
async def cmd_add_amount(message: types.Message, state: FSMContext):
    txt = message.text.strip()
    # try parse free text too
    parsed = smart_parse_free_text(txt)
    if parsed:
        amount, category, description = parsed
        pending_tx[message.from_user.id] = {"amount": amount, "category": category, "description": description}
        # build confirm keyboard
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("Подтвердить ✅", callback_data="confirm_tx"),
             InlineKeyboardButton("Отмена ❌", callback_data="cancel_tx")]
        ])
        cat_text = category or "—"
        desc = description or ""
        await message.answer(f"Найдено:\nСумма: {amount}₽\nКатегория: {cat_text}\nОписание: {desc}\nПодтвердить?", reply_markup=kb)
        await state.clear()
        return

    # if not parsed ask for explicit amount
    try:
        amount = parse_amount_token(txt)
    except Exception:
        await message.answer("Не могу распознать сумму. Попробуй ещё раз (пример: 1500, -2000, 1.5k):")
        return
    await state.update_data(amount=amount)
    await state.set_state(AddTxStates.category)
    await message.answer("Введите категорию (например: еда, транспорт):")

@dp.message(AddTxStates.category)
async def cmd_add_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text.strip())
    await state.set_state(AddTxStates.description)
    await message.answer("Введите описание (или '—'):")

@dp.message(AddTxStates.description)
async def cmd_add_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    category = data.get("category") or None
    description = message.text if message.text != '—' else None
    user_id = await get_or_create_user(message.from_user.id)

    # Save tx
    await db.execute(
        "INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1, $2, $3, $4, NOW())",
        user_id, amount, category, description
    )
    await save_message(user_id, "system", f"Добавлена транзакция: {amount}₽ | {category} | {description}")
    await message.answer("Транзакция добавлена ✅\nХотите краткий анализ? (да/нет)")

    await state.clear()

# ---------------------------
# Inline confirm/cancel handlers
# ---------------------------
@dp.callback_query(lambda c: c.data == "confirm_tx")
async def cb_confirm_tx(call: types.CallbackQuery):
    user = call.from_user
    data = pending_tx.pop(user.id, None)
    if not data:
        await call.answer("Нет ожидающей транзакции.", show_alert=True)
        return
    user_id = await get_or_create_user(user.id)
    await db.execute(
        "INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1, $2, $3, $4, NOW())",
        user_id, data["amount"], data.get("category"), data.get("description")
    )
    await save_message(user_id, "system", f"Добавлена транзакция: {data['amount']}₽ | {data.get('category')} | {data.get('description')}")
    await call.message.edit_text("Транзакция подтверждена и добавлена ✅")
    # provide quick analysis
    summary = await analyze_user_finances(user_id)
    await call.message.answer("Краткий анализ:\n" + (summary if len(summary) < 1500 else summary[:1400] + "..."))
    await call.answer()

@dp.callback_query(lambda c: c.data == "cancel_tx")
async def cb_cancel_tx(call: types.CallbackQuery):
    pending_tx.pop(call.from_user.id, None)
    await call.message.edit_text("Операция отменена.")
    await call.answer()

# ---------------------------
# /goal FSM
# ---------------------------
class GoalStates(StatesGroup):
    target = State()
    title = State()

@dp.message(Command("goal"))
async def cmd_goal_start(message: types.Message, state: FSMContext):
    await state.set_state(GoalStates.target)
    await message.answer("Введите сумму цели (например: 100000):")

@dp.message(GoalStates.target)
async def cmd_goal_target(message: types.Message, state: FSMContext):
    try:
        target = parse_amount_token(message.text.strip())
    except Exception:
        await message.answer("Неверный формат суммы. Попробуйте ещё раз.")
        return
    await state.update_data(target=target)
    await state.set_state(GoalStates.title)
    await message.answer("Введите название цели:")

@dp.message(GoalStates.title)
async def cmd_goal_title(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = message.text.strip()
    user_id = await get_or_create_user(message.from_user.id)
    await db.execute("INSERT INTO goals (user_id, target, current, title, created_at) VALUES ($1, $2, 0, $3, NOW())", user_id, data["target"], title)
    await save_message(user_id, "system", f"Создана цель: {title} на {data['target']}₽")
    await message.answer(f"Цель '{title}' добавлена ✅")
    await state.clear()

# ---------------------------
# /stats - сводка расходов / баланс
# ---------------------------
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    # суммарно за 30 дней
    since = datetime.utcnow() - timedelta(days=30)
    rows = await db.fetch("SELECT amount, category FROM transactions WHERE user_id=$1 AND created_at >= $2", user_id, since)
    if not rows:
        await message.answer("Нет транзакций за последние 30 дней.")
        return
    total = sum(r["amount"] for r in rows)
    by_cat = {}
    for r in rows:
        cat = r["category"] or "—"
        by_cat[cat] = by_cat.get(cat, 0) + r["amount"]
    msg = f"Статистика (30 дней):\nВсего: {total}₽\n"
    top = sorted(by_cat.items(), key=lambda x: -abs(x[1]))[:8]
    for cat, val in top:
        msg += f"- {cat}: {val}₽\n"
    await message.answer(msg)

# /balance - прогресс по целям
@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    goals = await db.fetch("SELECT id, title, target, current FROM goals WHERE user_id=$1", user_id)
    if not goals:
        await message.answer("Целей пока нет.")
        return
    out = "Цели:\n"
    for g in goals:
        pr = (g["current"] / g["target"] * 100) if g["target"] else 0
        out += f"- {g.get('title','Цель')}: {g['current']}/{g['target']} ₽ ({pr:.1f}%)\n"
    await message.answer(out)

# ---------------------------
# Catch-all: AI обработчик всех текстовых сообщений
# ---------------------------
@dp.message()
async def handle_all(message: types.Message):
    # ignore commands (they are handled above)
    if message.text and message.text.startswith("/"):
        return

    user_id = await get_or_create_user(message.from_user.id)

    # когда контекст растёт — делаем summarization (асинхронно, не блокируя)
    asyncio.create_task(ensure_compact_context(user_id))

    # prepare context + finance data
    context = await get_full_context(user_id)
    finance = await analyze_user_finances(user_id)
    system_prompt = (
        "Ты — умный финансовый ассистент. Используй историю диалога и данные транзакций/целей.\n"
        f"Данные пользователя:\n{finance}\n\n"
        "Ответь кратко (3-6 предложений) и дай 3 практических шага."
    )
    messages = [{"role":"system","content":system_prompt}] + context + [{"role":"user","content":message.text}]

    # отправляем запрос в GigaChat (в отдельном потоке)
    try:
        reply = await gigachat_request(messages)
    except Exception as e:
        print("GigaChat error:", e)
        await message.answer("Ошибка AI-сервиса. Попробуй позже.")
        return

    # сохраняем диалог в контекст и отвечаем
    await save_message(user_id, "assistant", reply)
    # структурируем: разделим на короткий вывод и рекомендации (если есть)
    # отправляем ответ
    await message.answer(reply)

# ---------------------------
# Startup
# ---------------------------
async def main():
    global db
    db = await create_db_pool()
    print("DB connected. Bot started.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
