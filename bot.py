# bot.py — улучшенная версия с меню, inline-кнопками и AI-анализом
import os
import re
import uuid
import base64
import asyncio
from datetime import datetime, timedelta
from functools import partial

import asyncpg
import httpx
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

# -------------------------
# Конфигурация
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))

GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE")
GIGACHAT_AUTH_URL = os.getenv("GIGACHAT_AUTH_URL")
GIGACHAT_API_URL = os.getenv("GIGACHAT_API_URL")

# параметры поведения
GIGACHAT_MODEL = "GigaChat:1.0.26.20"
MAX_TRANSACTIONS_FOR_ANALYSIS = 200
CONTEXT_SUMMARY_THRESHOLD = 400
CONTEXT_TRIM_COUNT = 200

# -------------------------
# Инициализация
# -------------------------
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

db = None  # пул подключений asyncpg будет присвоен при старте

# временное хранилище подтверждаемой транзакции (пока пользователь не подтвердил)
pending_tx = {}  # {tg_id: {"amount":..., "category":..., "description":...}}

# -------------------------
# Вспомогательные функции
# -------------------------
async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT,
        min_size=1,
        max_size=10
    )

# -------------------------
# GigaChat: получение токена и запрос
# -------------------------
async def get_gigachat_token():
    """Получаем access_token через Basic Auth (как в тесте)."""
    auth_str = f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}"
    b64 = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Authorization": f"Basic {b64}",
        "RqUID": str(uuid.uuid4())
    }
    data = {"scope": GIGACHAT_SCOPE}
    async with httpx.AsyncClient(verify=False, timeout=20) as client:
        resp = await client.post(GIGACHAT_AUTH_URL, headers=headers, data=data)
        resp.raise_for_status()
        j = resp.json()
        return j.get("access_token")

async def gigachat_request(messages):
    """Отправляем messages (list) в GigaChat и возвращаем ответ (строку)."""
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
        # безопасно извлекаем ответ
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            return str(data)

# -------------------------
# AI-контекст (Postgres)
# -------------------------
async def save_message(user_id, role, content):
    """Сохраняем роль ("user"/"assistant"/"system") и текст в ai_context."""
    await db.execute(
        "INSERT INTO ai_context (user_id, role, content, created_at) VALUES ($1, $2, $3, NOW())",
        user_id, role, content
    )

async def get_full_context(user_id):
    rows = await db.fetch("SELECT role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC", user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

async def get_context_count(user_id):
    r = await db.fetchrow("SELECT count(*)::int AS c FROM ai_context WHERE user_id=$1", user_id)
    return r["c"] if r else 0

# Простая суммаризация старых сообщений (при превышении порога)
async def ensure_compact_context(user_id):
    cnt = await get_context_count(user_id)
    if cnt <= CONTEXT_SUMMARY_THRESHOLD:
        return
    # берем самые старые записи, которые уйдут в summary
    cutoff = cnt - CONTEXT_TRIM_COUNT
    rows = await db.fetch("SELECT id, role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC LIMIT $2", user_id, cutoff)
    if not rows:
        return
    text = "\n".join([f"{r['role']}: {r['content']}" for r in rows])
    system = {"role": "system", "content": "Сделай сжатое, ключевое summary следующих записей: максимум 2-3 предложения, сохрани факты о доходах/расходах/целях."}
    messages = [system, {"role": "user", "content": text}]
    try:
        summary = await gigachat_request(messages)
        # сохраняем summary как system-сообщение
        await save_message(user_id, "system", f"SUMMARY: {summary}")
        # удалить старые
        ids = [r["id"] for r in rows]
        await db.execute("DELETE FROM ai_context WHERE id = ANY($1::int[])", ids)
    except Exception as e:
        print("Summarize failed:", e)
        # не удаляем ничего в случае ошибки

# -------------------------
# Анализ транзакций / цели
# -------------------------
async def analyze_user_finances_text(user_id):
    rows = await db.fetch(
        "SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2",
        user_id, MAX_TRANSACTIONS_FOR_ANALYSIS
    )
    if not rows:
        return "У пользователя нет транзакций."
    text = "Последние транзакции:\n"
    for r in rows:
        ts = r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else ""
        text += f"- {r['amount']}₽ | {r.get('category') or '—'} | {r.get('description') or ''} | {ts}\n"
    goals = await db.fetch("SELECT title, target, current, created_at FROM goals WHERE user_id=$1", user_id)
    if goals:
        text += "\nЦели:\n"
        for g in goals:
            pr = (g["current"]/g["target"]*100) if g["target"] else 0
            text += f"- {g.get('title','Цель')}: {g['current']}/{g['target']} ₽ ({pr:.1f}%)\n"
    return text

# -------------------------
# Smart-парсер суммы и строки
# -------------------------
UNIT_MAP = {"k": 1_000, "к": 1_000, "m": 1_000_000, "м": 1_000_000, "млн": 1_000_000}
def parse_amount_token(s: str):
    s0 = s.strip().lower().replace(" ", "").replace("\u2009", "")
    sign = 1
    if s0.startswith("+"):
        s0 = s0[1:]; sign = 1
    elif s0.startswith("-"):
        s0 = s0[1:]; sign = -1
    s0 = s0.replace(",", ".")
    m = re.match(r"^([\d\.]+)([a-zа-яё%]*)$", s0, re.IGNORECASE)
    if not m:
        raise ValueError("invalid amount")
    num = float(m.group(1))
    unit = m.group(2)
    mult = 1
    if unit:
        for k,v in UNIT_MAP.items():
            if unit.startswith(k):
                mult = v
                break
    return int(round(num * mult * sign))

def smart_parse_free_text(text: str):
    """
    Возвращает (amount:int, category:str or None, description:str or None) или None.
    """
    if not text:
        return None
    # ищем токен с числом и возможно суффиксом
    m = re.search(r"([+-]?\s*\d[\d\s\.,]*(?:k|K|m|M|к|К|м|М|млн)?)", text, re.IGNORECASE)
    if not m:
        return None
    token = m.group(1)
    try:
        amount = parse_amount_token(token)
    except Exception:
        return None
    # остаток текста без токена
    left = (text[:m.start()] + " " + text[m.end():]).strip()
    if not left:
        return (amount, None, None)
    parts = left.split()
    category = parts[0]
    description = left
    return (amount, category, description)

# -------------------------
# Пользователь / helpers
# -------------------------
async def get_or_create_user(tg_id: int):
    row = await db.fetchrow("SELECT id FROM users WHERE tg_id = $1", tg_id)
    if row:
        return row["id"]
    row = await db.fetchrow("INSERT INTO users (tg_id, created_at) VALUES ($1, NOW()) RETURNING id", tg_id)
    return row["id"]

# -------------------------
# Клавиатуры / меню
# -------------------------
def main_menu_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ Добавить транзакцию", callback_data="menu_add"),
         InlineKeyboardButton("🎯 Мои цели", callback_data="menu_goals")],
        [InlineKeyboardButton("📊 Статистика", callback_data="menu_stats"),
         InlineKeyboardButton("💬 Совет AI", callback_data="menu_ai")],
        [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")]
    ])
    return kb

confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton("Подтвердить ✅", callback_data="confirm_tx"),
     InlineKeyboardButton("Отмена ❌", callback_data="cancel_tx")]
])

# -------------------------
# Команды
# -------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = await get_or_create_user(message.from_user.id)
    text = (
        "Привет! Я твой Финансовый помощник 🤖💸\n\n"
        "— Добавляй транзакции быстро: `-2500 кофе`, `+150000 зарплата`, `1.5k grocery`.\n"
        "— Создавай цели и отслеживай прогресс.\n"
        "— Получай советы от AI на основе ваших трат и целей.\n\n"
        "Выбери действие в меню 👇"
    )
    await message.answer(text, reply_markup=main_menu_kb())

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main_menu_kb())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "Команды и подсказки:\n"
        "/start — приветствие и меню\n"
        "/menu — открыть главное меню\n"
        "/add — добавить транзакцию (пошагово)\n"
        "/goal — добавить цель\n"
        "/stats — статистика за 30 дней\n"
        "/balance — прогресс по целям\n\n"
        "Быстрая запись транзакции: просто напишите строку, например:\n"
        "`-2500 кофе`, `+150k зарплата`, `1 500 000`"
    )
    await message.answer(text, reply_markup=main_menu_kb())

# -------------------------
# Callback handlers (menu)
# -------------------------
@dp.callback_query(lambda c: c.data == "menu_add")
async def cb_menu_add(call: types.CallbackQuery):
    await call.message.answer("Отправь транзакцию в одной строке, например: `-2500 кофе` или нажми /add")
    await call.answer()

@dp.callback_query(lambda c: c.data == "menu_goals")
async def cb_menu_goals(call: types.CallbackQuery):
    user_id = await get_or_create_user(call.from_user.id)
    rows = await db.fetch("SELECT id, title, target, current FROM goals WHERE user_id=$1", user_id)
    if not rows:
        await call.message.answer("Целей не найдено. Чтобы создать — нажмите /goal")
        await call.answer()
        return
    text = "Ваши цели:\n"
    for r in rows:
        pr = (r["current"]/r["target"]*100) if r["target"] else 0
        text += f"- {r.get('title','Цель')}: {r['current']}/{r['target']} ₽ ({pr:.1f}%)\n"
    await call.message.answer(text)
    await call.answer()

@dp.callback_query(lambda c: c.data == "menu_stats")
async def cb_menu_stats(call: types.CallbackQuery):
    await call.message.answer("Запрашиваю статистику...")
    await call.answer()
    # reuse stats handler
    await cmd_stats(call.message)

@dp.callback_query(lambda c: c.data == "menu_ai")
async def cb_menu_ai(call: types.CallbackQuery):
    await call.message.answer("Напишите вопрос ассистенту (например: 'Как оптимизировать расходы?'):")
    await call.answer()

@dp.callback_query(lambda c: c.data == "menu_help")
async def cb_menu_help(call: types.CallbackQuery):
    await call.message.answer("/help — список команд")
    await call.answer()

# -------------------------
# /add - FSM + быстрый ввод
# -------------------------
class AddStates(StatesGroup):
    amount = State()
    category = State()
    description = State()

@dp.message(Command("add"))
async def cmd_add_start(message: types.Message, state: FSMContext):
    await state.set_state(AddStates.amount)
    await message.answer("Введите сумму (пример: 2500, -2500, 1.5k):")

@dp.message(AddStates.amount)
async def add_amount_handler(message: types.Message, state: FSMContext):
    txt = message.text.strip()
    # попытка smart parse одной строкой
    parsed = smart_parse_free_text(txt)
    if parsed:
        amount, category, description = parsed
        pending_tx[message.from_user.id] = {"amount": amount, "category": category, "description": description}
        cat_text = category or "—"
        desc_text = description or ""
        await message.answer(f"Найдено:\nСумма: {amount}₽\nКатегория: {cat_text}\nОписание: {desc_text}\nПодтвердить?", reply_markup=confirm_kb)
        await state.clear()
        return
    # иначе ожидаем ввод суммы
    try:
        amount = parse_amount_token(txt)
    except Exception:
        await message.answer("Не могу распознать сумму. Попробуйте ещё раз (пример: 1500, -2000, 1.5k):")
        return
    await state.update_data(amount=amount)
    await state.set_state(AddStates.category)
    await message.answer("Введите категорию (например: еда, транспорт):")

@dp.message(AddStates.category)
async def add_category_handler(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text.strip())
    await state.set_state(AddStates.description)
    await message.answer("Введите описание (или введите '-' чтобы пропустить):")

@dp.message(AddStates.description)
async def add_description_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    category = data.get("category") or None
    description = message.text.strip() if message.text.strip() != "-" else None
    user_id = await get_or_create_user(message.from_user.id)
    await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, amount, category, description)
    await save_message(user_id, "system", f"Добавлена транзакция: {amount}₽ | {category} | {description}")
    await message.answer("Транзакция добавлена ✅\nХотите краткий анализ? Отправьте 'да' или нажмите /stats")
    await state.clear()

# Inline confirm/cancel for pending_tx
@dp.callback_query(lambda c: c.data == "confirm_tx")
async def cb_confirm_tx(call: types.CallbackQuery):
    data = pending_tx.pop(call.from_user.id, None)
    if not data:
        await call.answer("Нет ожидающей транзакции.", show_alert=True)
        return
    user_id = await get_or_create_user(call.from_user.id)
    await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, data["amount"], data.get("category"), data.get("description"))
    await save_message(user_id, "system", f"Добавлена транзакция: {data['amount']}₽ | {data.get('category')} | {data.get('description')}")
    await call.message.edit_text("Транзакция подтверждена и добавлена ✅")
    # краткий анализ
    summary = await analyze_user_finances_text(user_id)
    await call.message.answer("Краткий анализ:\n" + (summary[:1500] + "..." if len(summary) > 1500 else summary))
    await call.answer()

@dp.callback_query(lambda c: c.data == "cancel_tx")
async def cb_cancel_tx(call: types.CallbackQuery):
    pending_tx.pop(call.from_user.id, None)
    await call.message.edit_text("Операция отменена.")
    await call.answer()

# -------------------------
# /goal FSM
# -------------------------
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
    await db.execute("INSERT INTO goals (user_id, target, current, title, created_at) VALUES ($1,$2,0,$3,NOW())",
                     user_id, data["target"], title)
    await save_message(user_id, "system", f"Создана цель: {title} на {data['target']}₽")
    await message.answer(f"Цель '{title}' добавлена ✅")
    await state.clear()

# -------------------------
# /stats и /balance
# -------------------------
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    since = datetime.utcnow() - timedelta(days=30)
    rows = await db.fetch("SELECT amount, category, created_at FROM transactions WHERE user_id=$1 AND created_at >= $2", user_id, since)
    if not rows:
        await message.answer("Нет транзакций за последние 30 дней.")
        return
    total = sum(r["amount"] for r in rows)
    by_cat = {}
    for r in rows:
        cat = r["category"] or "—"
        by_cat[cat] = by_cat.get(cat, 0) + r["amount"]
    text = f"Статистика за 30 дней:\nВсего: {total}₽\n"
    top = sorted(by_cat.items(), key=lambda x: -abs(x[1]))[:8]
    for cat, val in top:
        text += f"- {cat}: {val}₽\n"
    await message.answer(text)

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    goals = await db.fetch("SELECT id, title, target, current FROM goals WHERE user_id=$1", user_id)
    if not goals:
        await message.answer("Целей пока нет.")
        return
    out = "Прогресс по целям:\n"
    for g in goals:
        pr = (g["current"]/g["target"]*100) if g["target"] else 0
        out += f"- {g.get('title','Цель')}: {g['current']}/{g['target']} ₽ ({pr:.1f}%)\n"
    await message.answer(out)

# -------------------------
# Catch-all: AI обработчик
# -------------------------
@dp.message()
async def handle_all(message: types.Message):
    # игнорируем команды
    if message.text and message.text.startswith("/"):
        return

    # если пользователь написал "да" после добавления — показать stats
    if message.text and message.text.strip().lower() in ("да", "yes", "ok"):
        await cmd_stats(message)
        return

    # try parse quick transaction (user typed e.g. "-2500 кофе")
    parsed = smart_parse_free_text(message.text)
    if parsed:
        amount, category, description = parsed
        pending_tx[message.from_user.id] = {"amount": amount, "category": category, "description": description}
        await message.answer(f"Найдено: {amount}₽ | {category or '—'} | {description or ''}\nПодтвердить?", reply_markup=confirm_kb)
        return

    user_id = await get_or_create_user(message.from_user.id)
    # запустить background summarization, если нужно
    asyncio.create_task(ensure_compact_context(user_id))

    # подготовка данных для AI
    finance_text = await analyze_user_finances_text(user_id)
    system_prompt = (
        "Ты — умный финансовый ассистент. Используй историю диалога и данные транзакций/целей.\n"
        f"Данные пользователя:\n{finance_text}\n\n"
        "Ответь кратко (3-6 предложений) и предложи 3 практических шага."
    )
    context = await get_full_context(user_id)
    messages = [{"role": "system", "content": system_prompt}] + context + [{"role": "user", "content": message.text}]

    try:
        reply = await gigachat_request(messages)
    except Exception as e:
        print("GigaChat error:", e)
        await message.answer("Ошибка AI-сервиса. Попробуйте позже.")
        return

    await save_message(user_id, "assistant", reply)
    await message.answer(reply)

# -------------------------
# Startup
# -------------------------
async def main():
    global db
    db = await create_db_pool()
    print("DB connected. Bot started.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
