import os
import re
import csv
import uuid
import base64
import hashlib
import tempfile
import asyncio
from datetime import datetime, timedelta

import asyncpg
import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

# -------------------------
# Конфигурация из .env
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
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat:1.0.26.20")

# параметры
MAX_TRANSACTIONS_FOR_ANALYSIS = 200
CONTEXT_SUMMARY_THRESHOLD = 400
CONTEXT_TRIM_COUNT = 200

CHART_DIR = "/tmp"
os.makedirs(CHART_DIR, exist_ok=True)

# -------------------------
# Инициализация
# -------------------------
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

db = None  # asyncpg pool
scheduler = AsyncIOScheduler()

# in-memory pending tx for confirmation
pending_tx = {}

# simple category keywords
CATEGORY_KEYWORDS = {
    "еда": ["кофе", "еда", "ресторан", "пицца", "burger", "cafe"],
    "такси": ["такси", "uber", "bolt", "yandex"],
    "продукты": ["ашан", "магнит", "пятёрочка", "перекресток", "lenta"],
    "зарплата": ["зарлата", "зарплата", "salary", "pay"],
}

# -------------------------
# DB pool helper
# -------------------------
async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT, min_size=1, max_size=8
    )

# -------------------------
# GigaChat auth & request
# -------------------------
async def get_gigachat_token():
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
        r = await client.post(GIGACHAT_AUTH_URL, headers=headers, data=data)
        r.raise_for_status()
        return r.json().get("access_token")

async def gigachat_request(messages, model=GIGACHAT_MODEL):
    token = await get_gigachat_token()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {"model": model, "messages": messages}
    async with httpx.AsyncClient(verify=False, timeout=40) as client:
        r = await client.post(GIGACHAT_API_URL, headers=headers, json=payload)
        r.raise_for_status()
        j = r.json()
        try:
            return j["choices"][0]["message"]["content"]
        except Exception:
            return str(j)

# -------------------------
# AI context / cache / summary toggle
# -------------------------
async def save_message(user_id: int, role: str, content: str):
    await db.execute(
        "INSERT INTO ai_context (user_id, role, content, created_at) VALUES ($1,$2,$3,NOW())",
        user_id, role, content
    )

async def get_full_context(user_id: int):
    rows = await db.fetch("SELECT role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC", user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

async def get_context_count(user_id: int):
    r = await db.fetchrow("SELECT count(*)::int AS c FROM ai_context WHERE user_id=$1", user_id)
    return r["c"] if r else 0

async def summarize_old_context(user_id: int):
    # summarization only if user enabled it
    enabled = await is_summarization_enabled(user_id)
    if not enabled:
        return
    cnt = await get_context_count(user_id)
    if cnt <= CONTEXT_SUMMARY_THRESHOLD:
        return
    cutoff = cnt - CONTEXT_TRIM_COUNT
    rows = await db.fetch("SELECT id, role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC LIMIT $2", user_id, cutoff)
    if not rows:
        return
    text = "\n".join([f"{r['role']}: {r['content']}" for r in rows])
    system = {"role":"system","content":"Сделай компактное summary (2-3 предложения) ключевых финансовых моментов."}
    try:
        summary = await gigachat_request([system, {"role":"user","content":text}])
        await save_message(user_id, "system", f"SUMMARY: {summary}")
        ids = [r["id"] for r in rows]
        await db.execute("DELETE FROM ai_context WHERE id = ANY($1::int[])", ids)
    except Exception as e:
        print("Summarize failed:", e)

# user settings table functions (summarization toggle)
async def ensure_user_setting(user_id: int):
    await db.execute("INSERT INTO user_settings (user_id, summarization_enabled) VALUES ($1, TRUE) ON CONFLICT (user_id) DO NOTHING", user_id)

async def set_summarization(user_id: int, enabled: bool):
    await ensure_user_setting(user_id)
    await db.execute("UPDATE user_settings SET summarization_enabled = $1 WHERE user_id = $2", enabled, user_id)

async def is_summarization_enabled(user_id: int):
    row = await db.fetchrow("SELECT summarization_enabled FROM user_settings WHERE user_id=$1", user_id)
    if row is None:
        # default true
        await ensure_user_setting(user_id)
        return True
    return row["summarization_enabled"]

# -------------------------
# AI cache: hash by user_message + finance snapshot
# -------------------------
def _hash_input(user_message: str, finance_snapshot: str):
    return hashlib.sha256((user_message.strip().lower() + "\n" + finance_snapshot).encode('utf-8')).hexdigest()

async def get_cached_ai_reply(user_id: int, user_message: str, finance_snapshot: str):
    h = _hash_input(user_message, finance_snapshot)
    row = await db.fetchrow("SELECT answer FROM ai_cache WHERE user_id=$1 AND input_hash=$2 ORDER BY created_at DESC LIMIT 1", user_id, h)
    return row["answer"] if row else None

async def save_ai_cache(user_id: int, user_message: str, finance_snapshot: str, ai_answer: str):
    h = _hash_input(user_message, finance_snapshot)
    await db.execute("INSERT INTO ai_cache (user_id, input_hash, answer, created_at) VALUES ($1,$2,$3,NOW())", user_id, h, ai_answer)

# -------------------------
# Transactions: parsing & categorization & analysis
# -------------------------
UNIT_MAP = {"k": 1_000, "к": 1_000, "m": 1_000_000, "м": 1_000_000, "млн": 1_000_000}
def parse_amount_token(s: str):
    s0 = s.strip().lower().replace(" ", "").replace("\u2009","")
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
    return int(round(num*mult*sign))

def categorize_by_keywords(text: str):
    if not text:
        return None
    s = text.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in s:
                return cat
    return None

def smart_parse_free_text(text: str):
    if not text:
        return None
    m = re.search(r"([+-]?\s*\d[\d\s\.,]*(?:k|K|m|M|к|К|м|М|млн)?)", text, re.IGNORECASE)
    if not m:
        return None
    token = m.group(1)
    try:
        amount = parse_amount_token(token)
    except Exception:
        return None
    left = (text[:m.start()] + " " + text[m.end():]).strip()
    if not left:
        return (amount, None, None)
    parts = left.split()
    category = parts[0]
    description = left
    guessed = categorize_by_keywords(left)
    if guessed and not category:
        category = guessed
    return (amount, category, description)

async def analyze_user_finances_text(user_id: int):
    rows = await db.fetch("SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2", user_id, MAX_TRANSACTIONS_FOR_ANALYSIS)
    if not rows:
        return "У пользователя нет транзакций."
    text = "Последние транзакции:\n"
    for r in rows:
        ts = r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else ""
        text += f"- {r['amount']}₽ | {r.get('category') or '—'} | {r.get('description') or ''} | {ts}\n"
    goals = await db.fetch("SELECT title, target, current FROM goals WHERE user_id=$1", user_id)
    if goals:
        text += "\nЦели:\n"
        for g in goals:
            pr = (g["current"]/g["target"]*100) if g["target"] else 0
            text += f"- {g.get('title','Цель')}: {g['current']}/{g['target']} ₽ ({pr:.1f}%)\n"
    return text

# -------------------------
# User helpers
# -------------------------
async def get_or_create_user(tg_id: int):
    row = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]
    row = await db.fetchrow("INSERT INTO users (tg_id, created_at) VALUES ($1, NOW()) RETURNING id", tg_id)
    return row["id"]

# -------------------------
# Keyboards (menu)
# -------------------------
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ Добавить транзакцию", callback_data="menu_add"),
         InlineKeyboardButton("🎯 Мои цели", callback_data="menu_goals")],
        [InlineKeyboardButton("📊 Статистика", callback_data="menu_stats"),
         InlineKeyboardButton("📈 График (/chart)", callback_data="menu_chart")],
        [InlineKeyboardButton("💬 Совет AI", callback_data="menu_ai"),
         InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings")]
    ])

confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton("Подтвердить ✅", callback_data="confirm_tx"),
     InlineKeyboardButton("Отмена ❌", callback_data="cancel_tx")]
])

# -------------------------
# Commands & callbacks
# -------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await get_or_create_user(message.from_user.id)
    text = (
        "Привет! Я — FinAdvisor, твой финансовый помощник 🤖💸\n\n"
        "Быстрая запись: `-2500 кофе`, `+150k зарплата`, `1.5k groceries`.\n"
        "Выбери действие в меню ниже:"
    )
    await message.answer(text, reply_markup=main_menu_kb())

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main_menu_kb())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "/start /menu /add /goal /stats /balance /chart /export /summary on|off\n"
        "Быстрая запись: `-2500 кофе`, `+150k зарплата`"
    )

# menu callbacks
@dp.callback_query(lambda c: c.data == "menu_add")
async def cb_menu_add(call: types.CallbackQuery):
    await call.message.answer("Отправь транзакцию в одной строке, например: `-2500 кофе` или нажми /add")
    await call.answer()

@dp.callback_query(lambda c: c.data == "menu_goals")
async def cb_menu_goals(call: types.CallbackQuery):
    user_id = await get_or_create_user(call.from_user.id)
    rows = await db.fetch("SELECT id, title, target, current FROM goals WHERE user_id=$1", user_id)
    if not rows:
        await call.message.answer("Целей не найдено. Создать можно через /goal")
    else:
        msg = "Ваши цели:\n"
        for r in rows:
            pr = (r["current"]/r["target"]*100) if r["target"] else 0
            msg += f"- {r.get('title','Цель')}: {r['current']}/{r['target']} ₽ ({pr:.1f}%)\n"
        await call.message.answer(msg)
    await call.answer()

@dp.callback_query(lambda c: c.data == "menu_stats")
async def cb_menu_stats(call: types.CallbackQuery):
    await call.message.answer("Запрашиваю статистику...")
    await cmd_stats(call.message)
    await call.answer()

@dp.callback_query(lambda c: c.data == "menu_chart")
async def cb_menu_chart(call: types.CallbackQuery):
    await call.message.answer("Генерирую график...")
    await cmd_chart(call.message)
    await call.answer()

@dp.callback_query(lambda c: c.data == "menu_ai")
async def cb_menu_ai(call: types.CallbackQuery):
    await call.message.answer("Напиши вопрос ассистенту:")
    await call.answer()

@dp.callback_query(lambda c: c.data == "menu_settings")
async def cb_menu_settings(call: types.CallbackQuery):
    user_id = await get_or_create_user(call.from_user.id)
    enabled = await is_summarization_enabled(user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(("Отключить" if enabled else "Включить") + " суммаризацию", callback_data="toggle_summary")],
        [InlineKeyboardButton("Назад в меню", callback_data="menu_back")]
    ])
    await call.message.answer(f"Суммаризация контекста: {'включена' if enabled else 'отключена'}", reply_markup=kb)
    await call.answer()

@dp.callback_query(lambda c: c.data == "toggle_summary")
async def cb_toggle_summary(call: types.CallbackQuery):
    user_id = await get_or_create_user(call.from_user.id)
    enabled = await is_summarization_enabled(user_id)
    await set_summarization(user_id, not enabled)
    await call.message.answer(f"Суммаризация теперь {'включена' if not enabled else 'отключена'}.")
    await call.answer()

@dp.callback_query(lambda c: c.data == "menu_back")
async def cb_menu_back(call: types.CallbackQuery):
    await call.message.answer("Главное меню:", reply_markup=main_menu_kb())
    await call.answer()

# -------------------------
# /add FSM and quick free-text
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
    parsed = smart_parse_free_text(txt)
    if parsed:
        amount, category, description = parsed
        if not category:
            category = categorize_by_keywords(description or "")
        pending_tx[message.from_user.id] = {"amount": amount, "category": category, "description": description}
        await message.answer(f"Найдено: {amount}₽ | {category or '—'} | {description or ''}\nПодтвердить?", reply_markup=confirm_kb)
        await state.clear()
        return
    try:
        amount = parse_amount_token(txt)
    except Exception:
        await message.answer("Не могу распознать сумму. Попробуйте ещё раз (пример: 1500, -2000, 1.5k):")
        return
    await state.update_data(amount=amount)
    await state.set_state(AddStates.category)
    await message.answer("Введите категорию (или '-' чтобы пропустить):")

@dp.message(AddStates.category)
async def add_category_handler(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text.strip() if message.text.strip() != "-" else None)
    await state.set_state(AddStates.description)
    await message.answer("Введите описание (или '-' чтобы пропустить):")

@dp.message(AddStates.description)
async def add_description_handler(message: types.Message, state: FSMContext):
    d = await state.get_data()
    amount = d.get("amount")
    category = d.get("category") or None
    description = message.text.strip() if message.text.strip() != "-" else None
    user_id = await get_or_create_user(message.from_user.id)
    if not category:
        category = categorize_by_keywords(description or "")
    await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, amount, category, description)
    await save_message(user_id, "system", f"Добавлена транзакция: {amount}₽ | {category} | {description}")
    await message.answer("Транзакция добавлена ✅\nХочешь краткий анализ? Отправь 'да' или /stats")
    await state.clear()

# confirm/cancel callbacks for pending tx
@dp.callback_query(lambda c: c.data == "confirm_tx")
async def cb_confirm_tx(call: types.CallbackQuery):
    data = pending_tx.pop(call.from_user.id, None)
    if not data:
        await call.answer("Нет ожидающей транзакции.", show_alert=True)
        return
    user_id = await get_or_create_user(call.from_user.id)
    if not data.get("category"):
        data["category"] = categorize_by_keywords(data.get("description") or "")
    await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, data["amount"], data.get("category"), data.get("description"))
    await save_message(user_id, "system", f"Добавлена транзакция: {data['amount']}₽ | {data.get('category')} | {data.get('description')}")
    await call.message.edit_text("Транзакция подтверждена и добавлена ✅")
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
    await message.answer("Введите сумму цели (пример: 100000):")

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
# /stats /balance /chart
# -------------------------
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    since = datetime.utcnow() - timedelta(days=30)
    rows = await db.fetch("SELECT amount, category, created_at FROM transactions WHERE user_id=$1 AND created_at >= $2 ORDER BY created_at ASC", user_id, since)
    if not rows:
        await message.answer("Нет транзакций за последние 30 дней.")
        return
    total = sum(r["amount"] for r in rows)
    by_cat = {}
    for r in rows:
        cat = r["category"] or "—"
        by_cat[cat] = by_cat.get(cat, 0) + r["amount"]
    msg = f"Статистика (30 дней):\nВсего: {total}₽\n\nТоп по категориям:\n"
    top = sorted(by_cat.items(), key=lambda x: -abs(x[1]))[:10]
    for cat, val in top:
        msg += f"- {cat}: {val}₽\n"
    await message.answer(msg)

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    rows = await db.fetch("SELECT title, target, current FROM goals WHERE user_id=$1", user_id)
    if not rows:
        await message.answer("Целей не найдено.")
        return
    out = "Прогресс по целям:\n"
    for r in rows:
        pr = (r["current"]/r["target"]*100) if r["target"] else 0
        out += f"- {r.get('title','Цель')}: {r['current']}/{r['target']} ₽ ({pr:.1f}%)\n"
    await message.answer(out)

@dp.message(Command("chart"))
async def cmd_chart(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    since = datetime.utcnow() - timedelta(days=30)
    rows = await db.fetch("SELECT amount, created_at FROM transactions WHERE user_id=$1 AND created_at >= $2 ORDER BY created_at ASC", user_id, since)
    if not rows:
        await message.answer("Нет транзакций за последние 30 дней.")
        return
    daily = {}
    for r in rows:
        d = r["created_at"].date().isoformat()
        daily[d] = daily.get(d, 0) + float(r["amount"])
    dates = sorted(daily.keys())
    values = [daily[d] for d in dates]
    plt.figure(figsize=(10,4))
    plt.plot(dates, values, marker='o', linewidth=2)
    plt.xticks(rotation=45, ha="right")
    plt.title("Динамика расходов/доходов (30 дней)")
    plt.ylabel("Сумма (₽)")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    fname = f"{CHART_DIR}/chart_{user_id}_{int(datetime.utcnow().timestamp())}.png"
    plt.savefig(fname)
    plt.close()
    await message.answer_photo(types.FSInputFile(fname), caption="График расходов за 30 дней")

# -------------------------
# /export CSV
# -------------------------
@dp.message(Command("export"))
async def cmd_export(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    rows = await db.fetch("SELECT id, amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at ASC", user_id)
    if not rows:
        await message.answer("Нет транзакций для экспорта.")
        return
    fd, path = tempfile.mkstemp(prefix=f"finances_{user_id}_", suffix=".csv")
    os.close(fd)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id","amount","category","description","created_at"])
        for r in rows:
            writer.writerow([r["id"], r["amount"], r["category"] or "", r["description"] or "", r["created_at"].isoformat() if r["created_at"] else ""])
    await message.answer_document(types.FSInputFile(path), caption="Экспорт транзакций (CSV)")
    try:
        os.remove(path)
    except Exception:
        pass

# -------------------------
# AI generate with cache
# -------------------------
async def generate_ai_reply(user_id: int, user_message: str):
    finance_snapshot = await analyze_user_finances_text(user_id)
    cached = await get_cached_ai_reply(user_id, user_message, finance_snapshot)
    if cached:
        await save_message(user_id, "assistant", cached)
        return cached
    # background summarization
    asyncio.create_task(summarize_old_context(user_id))
    context = await get_full_context(user_id)
    system_prompt = ("Ты — умный финансовый ассистент. Используй историю диалога и данные транзакций/целей. "
                     "Дай краткий вывод (1-2 предложения) и 3 практических шага.")
    messages = [{"role":"system","content":system_prompt}] + context + [{"role":"user","content":user_message}]
    try:
        ai_answer = await gigachat_request(messages)
    except Exception as e:
        print("GigaChat error:", e)
        fallback = await get_cached_ai_reply(user_id, user_message, "")
        if fallback:
            await save_message(user_id, "assistant", fallback)
            return fallback
        return "Извините, AI временно недоступен. Попробуйте позже."
    await save_message(user_id, "assistant", ai_answer)
    await save_ai_cache(user_id, user_message, finance_snapshot, ai_answer)
    return ai_answer

# -------------------------
# Catch-all handler
# -------------------------
@dp.message()
async def handle_all(message: types.Message):
    if message.text and message.text.startswith("/"):
        return
    # quick "да" after add
    if message.text and message.text.strip().lower() in ("да","yes","ok"):
        await cmd_stats(message)
        return
    # quick add
    parsed = smart_parse_free_text(message.text or "")
    if parsed:
        amount, category, description = parsed
        if not category:
            category = categorize_by_keywords(description or "")
        pending_tx[message.from_user.id] = {"amount": amount, "category": category, "description": description}
        await message.answer(f"Найдено: {amount}₽ | {category or '—'} | {description or ''}\nПодтвердить?", reply_markup=confirm_kb)
        return
    # AI assistant flow
    user_id = await get_or_create_user(message.from_user.id)
    asyncio.create_task(summarize_old_context(user_id))
    reply = await generate_ai_reply(user_id, message.text or "")
    await message.answer(reply)

# -------------------------
# Weekly report job (APScheduler)
# -------------------------
async def build_weekly_report_for_user(user_id: int):
    # build text summary + small stats and chart
    finance_text = await analyze_user_finances_text(user_id)
    # compute totals for 7 days and 30 days
    since7 = datetime.utcnow() - timedelta(days=7)
    since30 = datetime.utcnow() - timedelta(days=30)
    rows7 = await db.fetch("SELECT amount FROM transactions WHERE user_id=$1 AND created_at >= $2", user_id, since7)
    rows30 = await db.fetch("SELECT amount FROM transactions WHERE user_id=$1 AND created_at >= $2", user_id, since30)
    total7 = sum(r["amount"] for r in rows7) if rows7 else 0
    total30 = sum(r["amount"] for r in rows30) if rows30 else 0
    text = f"Еженедельный отчёт\nЗа 7 дней: {total7}₽\nЗа 30 дней: {total30}₽\n\nКороткая сводка транзакций:\n{finance_text[:1500]}"
    return text

async def weekly_report_job():
    try:
        users = await db.fetch("SELECT id, tg_id FROM users")
        print(f"[weekly_report_job] users: {len(users)}")
        for u in users:
            try:
                user_id = u["id"]
                tg_id = u["tg_id"]
                # check if user wants to receive reports (use summarization setting as proxy; you can add separate opt-in)
                # we'll send report to all users by default
                report_text = await build_weekly_report_for_user(user_id)
                # send message
                await bot.send_message(tg_id, report_text)
                # attach small chart
                # reuse chart generation logic but send only if user has transactions
                since = datetime.utcnow() - timedelta(days=30)
                rows = await db.fetch("SELECT amount, created_at FROM transactions WHERE user_id=$1 AND created_at >= $2 ORDER BY created_at ASC", user_id, since)
                if rows:
                    daily = {}
                    for r in rows:
                        d = r["created_at"].date().isoformat()
                        daily[d] = daily.get(d, 0) + float(r["amount"])
                    dates = sorted(daily.keys())
                    values = [daily[d] for d in dates]
                    plt.figure(figsize=(10,4))
                    plt.plot(dates, values, marker='o', linewidth=2)
                    plt.xticks(rotation=45, ha="right")
                    plt.title("Динамика за 30 дней")
                    plt.tight_layout()
                    fname = f"{CHART_DIR}/weekly_{user_id}_{int(datetime.utcnow().timestamp())}.png"
                    plt.savefig(fname)
                    plt.close()
                    await bot.send_photo(tg_id, types.FSInputFile(fname), caption="График за 30 дней")
                    try:
                        os.remove(fname)
                    except Exception:
                        pass
            except Exception as e:
                print("Error while sending report to user", u, e)
    except Exception as e:
        print("weekly_report_job failed:", e)

# -------------------------
# Start / scheduler init
# -------------------------
async def on_startup():
    global db, scheduler
    db = await create_db_pool()
    # ensure settings table exists and defaults (if you haven't created table, create)
    # Note: prefer to create tables manually; here we just ensure user_settings entries created lazily.
    # Start scheduler
    scheduler.add_job(weekly_report_job, 'interval', weeks=1, next_run_time=datetime.utcnow() + timedelta(seconds=10))
    scheduler.start()
    print("DB connected and scheduler started.")

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    import os as _os
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(on_startup())
        # run polling
        asyncio.run(dp.start_polling(bot, on_startup=on_startup))
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down")
