#!/usr/bin/env python3
# coding: utf-8

# =========================
# FinAdvisor — part 1/4
# (imports, config, init, GigaChat, DB, helpers, FSM states)
# =========================

import os
import asyncio
import asyncpg
import requests
import uuid
import base64
import csv
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import difflib
import math
import re
import json
import tempfile

# Matplotlib (use Agg – headless)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Scheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Aiogram 3.x
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# dotenv
from dotenv import load_dotenv

# Load .env
load_dotenv()

# =========================
# CONFIG
# =========================

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
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat:2.0.28.2")

# temp path for charts
CHART_TMP = "/tmp"
os.makedirs(CHART_TMP, exist_ok=True)

# canonical categories list (initial)
CANONICAL_CATEGORIES = [
    "Такси", "Еда", "Продукты", "Развлечения", "Кафе", "Покупки", "Коммуналка", "Аренда",
    "Зарплата", "Кредиты", "Транспорт", "Медицина", "Образование", "Подарки", "Инвестиции",
    "Прочее"
]

# =========================
# GLOBALS
# =========================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db: asyncpg.pool.Pool | None = None
scheduler = AsyncIOScheduler()

# simple in-memory AI cache (input_hash -> answer)
ai_cache = {}

# =========================
# UTIL: auth header for GigaChat
# =========================

def basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}"
    b64 = base64.b64encode(raw.encode()).decode()
    return b64

# =========================
# GIGACHAT: sync helpers and executor wrapper
# - We call sync code in threadpool to avoid blocking.
# =========================

def get_gigachat_token_sync() -> str:
    """
    Request token via OAuth (synchronous).
    Uses application/x-www-form-urlencoded body (as required).
    """
    if not (GIGACHAT_CLIENT_ID and GIGACHAT_CLIENT_SECRET and GIGACHAT_AUTH_URL and GIGACHAT_SCOPE):
        raise RuntimeError("GigaChat credentials not set in env")

    headers = {
        "Authorization": f"Basic {basic_auth_header(GIGACHAT_CLIENT_ID, GIGACHAT_CLIENT_SECRET)}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
    }
    data = {"scope": GIGACHAT_SCOPE}
    resp = requests.post(GIGACHAT_AUTH_URL, headers=headers, data=data, verify=False, timeout=20)
    resp.raise_for_status()
    j = resp.json()
    token = j.get("access_token")
    if not token:
        raise RuntimeError("No access_token in GigaChat auth response")
    return token

def gigachat_request_sync(messages: list) -> str:
    token = get_gigachat_token_sync()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model": GIGACHAT_MODEL,
        "messages": messages,
        "temperature": 0.3
    }
    resp = requests.post(GIGACHAT_API_URL, headers=headers, json=payload, verify=False, timeout=30)
    resp.raise_for_status()
    j = resp.json()
    # defensive parsing
    try:
        return j["choices"][0]["message"]["content"]
    except Exception:
        return json.dumps(j)  # fallback

async def gigachat_request(messages: list) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, gigachat_request_sync, messages)

# =========================
# DB pool init
# =========================

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

# =========================
# DB - get/create user (guard when db == None)
# =========================

async def get_or_create_user(tg_id: int) -> int:
    global db
    if db is None:
        raise RuntimeError("DB not initialized")
    row = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]
    row = await db.fetchrow("INSERT INTO users (tg_id, created_at, summarization_enabled) VALUES ($1, NOW(), TRUE) RETURNING id", tg_id)
    return row["id"]

# =========================
# AI CONTEXT storage helpers
# =========================

async def save_context(user_id: int, role: str, content: str):
    global db
    if db is None:
        raise RuntimeError("DB not initialized")
    await db.execute("INSERT INTO ai_context (user_id, role, content, created_at) VALUES ($1,$2,$3,NOW())", user_id, role, content)

async def get_context(user_id: int) -> list:
    global db
    if db is None:
        raise RuntimeError("DB not initialized")
    rows = await db.fetch("SELECT role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC", user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

# =========================
# FINANCE SNAPSHOT (text)
# =========================

async def finance_snapshot_text(user_id: int, limit: int = 100) -> str:
    """
    Produce compact textual snapshot for AI: transactions, goals, assets.
    """
    global db
    if db is None:
        return "Нет данных (DB не инициализирована)."

    t_rows = await db.fetch("SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2", user_id, limit)
    lines = []
    if not t_rows:
        lines.append("Транзакций нет.")
    else:
        lines.append("Последние транзакции:")
        for r in t_rows[:20]:
            amt = int(r["amount"])
            cat = (r["category"] or "Прочее").capitalize()
            dt = r["created_at"].strftime("%Y-%m-%d %H:%M")
            lines.append(f"- {amt}₽ | {cat} | {dt}")

    goals = await db.fetch("SELECT title, target, current FROM goals WHERE user_id=$1 ORDER BY created_at ASC", user_id)
    if goals:
        lines.append("\nЦели:")
        for g in goals:
            lines.append(f"- {g['title']}: {int(g['current'])}/{int(g['target'])}₽")

    assets = await db.fetch("SELECT name, amount, type FROM assets WHERE user_id=$1", user_id)
    if assets:
        lines.append("\nСчета/активы:")
        for a in assets:
            lines.append(f"- {a['name']} ({a['type']}): {int(a['amount'])}₽")

    return "\n".join(lines)

# =========================
# AI reply composition
# =========================

async def ai_reply(user_id: int, user_text: str) -> str:
    # save user message
    await save_context(user_id, "user", user_text)

    context = await get_context(user_id)
    finance_text = await finance_snapshot_text(user_id)

    system_prompt = f"Ты — персональный финансовый ассистент. Используй данные и историю диалога:\n{finance_text}\nОтвечай кратко и полезно."
    messages = [{"role":"system","content":system_prompt}] + context + [{"role":"user","content":user_text}]

    # simple caching to save API calls
    key = json.dumps(messages, ensure_ascii=False)
    if key in ai_cache:
        return ai_cache[key]

    try:
        answer = await gigachat_request(messages)
    except Exception as e:
        print("GigaChat error:", e)
        answer = "Извините, AI временно недоступен."
    # save to cache and context
    ai_cache[key] = answer
    await save_context(user_id, "assistant", answer)
    return answer

# =========================
# AMOUNT & FREE-TEXT PARSERS
# =========================

def parse_amount_token(token: str) -> int:
    """
    Parse amount tokens like:
    '2500', '2.5k', '3k', '1.2m', '1,200', '1000.50'
    Returns integer rubles (rounded).
    """
    s = token.strip().lower().replace(" ", "")
    multiplier = 1
    # suffix handling
    if s.endswith(("k","к")):
        multiplier = 1000
        s = s[:-1]
    if s.endswith(("m","м","млн")):
        multiplier = 1_000_000
        # remove non-digit/sep
        s = ''.join([c for c in s if (c.isdigit() or c in ".,")])
    s = s.replace(",", ".")
    try:
        v = float(s)
    except:
        raise ValueError("invalid amount token")
    return int(round(v * multiplier))

def smart_parse_free_text(text: str):
    """
    Try to extract first numeric amount and remaining as category/desc.
    Returns (amount:int, rest:str|None) or None if no amount found.
    """
    if not text:
        return None
    m = re.search(r"([+-]?\s*\d[\d\.,]*\s*(?:k|к|m|м|млн)?)", text, flags=re.IGNORECASE)
    if not m:
        return None
    token = m.group(1)
    try:
        amount = parse_amount_token(token)
    except:
        return None
    left = (text[:m.start()] + " " + text[m.end():]).strip()
    return amount, left or None

# =========================
# CATEGORY normalization (hybrid fuzzy + capitalisation)
# =========================

def normalize_category_input(cat_input: str):
    """
    Returns (canonical_category, matched_bool)
    matched_bool True -> matched to canonical list with high confidence
    False -> suggested normalized form (capitalized) but not confident
    """
    if not cat_input:
        return None, False
    s = cat_input.strip()
    # try direct canonical match case-insensitive
    for c in CANONICAL_CATEGORIES:
        if s.lower() == c.lower():
            return c, True
    # fuzzy match using difflib
    matches = difflib.get_close_matches(s.lower(), [c.lower() for c in CANONICAL_CATEGORIES], n=1, cutoff=0.7)
    if matches:
        # find original canonical (keep original capitalization)
        canon = next((c for c in CANONICAL_CATEGORIES if c.lower() == matches[0]), None)
        if canon:
            return canon, True
    # fallback: capitalize words
    normalized = " ".join([w.capitalize() for w in s.split()])
    return normalized, False

# =========================
# FSM STATES
# =========================

class TxStates(StatesGroup):
    waiting_amount = State()
    waiting_category = State()
    waiting_desc = State()

class GoalStates(StatesGroup):
    waiting_target = State()
    waiting_title = State()

class AssetStates(StatesGroup):
    waiting_name = State()
    waiting_amount = State()
    waiting_type = State()

# End of Part 1/4
# =========================
# PART 2/4
# UI: MAIN MENU + HANDLERS
# =========================

# Главное меню (inline)
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Цели", callback_data="menu_goals"),
            InlineKeyboardButton(text="➕ Транзакция", callback_data="add_expense")
        ],
        [
            InlineKeyboardButton(text="💼 Активы и долги", callback_data="menu_assets"),
            InlineKeyboardButton(text="📊 Графики", callback_data="menu_charts")
        ],
        [
            InlineKeyboardButton(text="📎 Отчет", callback_data="menu_report"),
            InlineKeyboardButton(text="🧠 Консультация", callback_data="menu_consult")
        ]
    ])

# Кнопка "Отмена" — используется в интерактивах
def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

# =========================
# START
# =========================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = await get_or_create_user(message.from_user.id)
    text = (
        "Привет! Я твой персональный финансовый ассистент 🤖💰\n\n"
        "Я помогу тебе:\n"
        "• Вести расходы\n"
        "• Управлять целями\n"
        "• Отслеживать активы и долги\n"
        "• Получать отчеты и рекомендации\n\n"
        "Выбери действие ниже 👇"
    )
    await message.answer(text, reply_markup=main_menu_kb())

# =========================
# CANCEL (универсальная)
# =========================

@dp.callback_query(F.data == "cancel")
async def cancel_any(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Действие отменено.", reply_markup=main_menu_kb())
    await call.answer()

# =========================
# ADD EXPENSE — START
# =========================

@dp.callback_query(F.data == "add_expense")
async def add_expense_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Введите сумму расхода:", reply_markup=cancel_kb())
    await state.set_state(TxStates.waiting_amount)
    await call.answer()

# ========== TX: STEP 1 — amount ==========

@dp.message(TxStates.waiting_amount)
async def tx_get_amount(message: types.Message, state: FSMContext):
    parsed = smart_parse_free_text(message.text)
    if parsed:
        amount, rest = parsed
        await state.update_data(amount=amount)
        if rest:
            # rest – вероятно категория или описание
            cat, confident = normalize_category_input(rest)
            if confident:
                await state.update_data(category=cat)
                await message.answer(
                    f"Категория определена как <b>{cat}</b>.\nТеперь введите описание (необязательно):",
                    reply_markup=cancel_kb(),
                    parse_mode="HTML"
                )
                await state.set_state(TxStates.waiting_desc)
                return
            else:
                await message.answer(
                    f"Введите категорию расхода (предположено: <b>{cat}</b>):",
                    reply_markup=cancel_kb(),
                    parse_mode="HTML"
                )
                await state.set_state(TxStates.waiting_category)
                return
        else:
            await message.answer(
                "Введите категорию расхода:",
                reply_markup=cancel_kb()
            )
            await state.set_state(TxStates.waiting_category)
            return

    # no parse
    try:
        amount = parse_amount_token(message.text)
    except:
        await message.answer("Не смог понять сумму, попробуйте еще раз.")
        return
    await state.update_data(amount=amount)
    await message.answer("Введите категорию расхода:", reply_markup=cancel_kb())
    await state.set_state(TxStates.waiting_category)

# ========== TX: STEP 2 — category ==========

@dp.message(TxStates.waiting_category)
async def tx_get_category(message: types.Message, state: FSMContext):
    cat, confident = normalize_category_input(message.text)
    if not confident:
        await state.update_data(category=cat)
        await message.answer(
            f"Категория уточнена как <b>{cat}</b>. Теперь введите описание (необязательно):",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )
    else:
        await state.update_data(category=cat)
        await message.answer(
            f"Категория: <b>{cat}</b>.\nВведите описание (необязательно):",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )
    await state.set_state(TxStates.waiting_desc)

# ========== TX: STEP 3 — description and save ==========

@dp.message(TxStates.waiting_desc)
async def tx_get_desc(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = await get_or_create_user(message.from_user.id)

    desc = message.text.strip() if message.text else None
    amount = user_data["amount"]
    category = user_data["category"]

    await db.execute(
        "INSERT INTO transactions (user_id, amount, category, description, created_at) "
        "VALUES ($1,$2,$3,$4,NOW())",
        user_id, amount, category, desc
    )

    await state.clear()
    await message.answer(
        f"Добавлен расход: {amount}₽ • {category}" +
        (f" • {desc}" if desc else ""),
        reply_markup=main_menu_kb()
    )

# =========================
# GOALS (create/update/list)
# =========================

@dp.callback_query(F.data == "menu_goals")
async def cb_goals(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    rows = await db.fetch("SELECT id, title, target, current FROM goals WHERE user_id=$1 ORDER BY created_at ASC",
                          call.from_user.id)
    if not rows:
        txt = "У вас пока нет целей.\nДобавить новую?"
    else:
        txt = "Ваши цели:\n\n"
        for g in rows:
            txt += f"• <b>{g['title']}</b>: {int(g['current'])}/{int(g['target'])}₽\n"
        txt += "\nДобавить новую цель?"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ Добавить цель", callback_data="goal_add")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_main")]
    ])
    await call.message.edit_text(txt, parse_mode="HTML", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "goal_add")
async def goal_add_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Введите сумму цели:", reply_markup=cancel_kb())
    await state.set_state(GoalStates.waiting_target)
    await call.answer()

@dp.message(GoalStates.waiting_target)
async def goal_get_target(message: types.Message, state: FSMContext):
    try:
        amount = parse_amount_token(message.text)
    except:
        await message.answer("Не могу понять сумму, попробуйте снова.")
        return
    await state.update_data(target=amount)
    await message.answer("Введите название цели:", reply_markup=cancel_kb())
    await state.set_state(GoalStates.waiting_title)

@dp.message(GoalStates.waiting_title)
async def goal_get_title(message: types.Message, state: FSMContext):
    user_id = await get_or_create_user(message.from_user.id)
    data = await state.get_data()
    target = data["target"]
    title = message.text.strip().capitalize()

    await db.execute(
        "INSERT INTO goals (user_id, title, target, current, created_at) VALUES ($1,$2,$3,0,NOW())",
        user_id, title, target
    )
    await state.clear()
    await message.answer(f"Цель <b>{title}</b> добавлена!", parse_mode="HTML", reply_markup=main_menu_kb())

# =========================
# ASSETS (add/list)
# =========================

@dp.callback_query(F.data == "menu_assets")
async def cb_assets(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    rows = await db.fetch("SELECT name, amount, type FROM assets WHERE user_id=$1", call.from_user.id)
    if not rows:
        txt = "У вас пока нет активов.\nДобавить?"
    else:
        txt = "Ваши активы:\n\n"
        for a in rows:
            txt += f"• <b>{a['name']}</b> ({a['type']}): {int(a['amount'])}₽\n"
        txt += "\nДобавить новый актив?"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("➕ Добавить актив", callback_data="asset_add")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_main")]
    ])
    await call.message.edit_text(txt, parse_mode="HTML", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "asset_add")
async def asset_add_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Введите название актива:", reply_markup=cancel_kb())
    await state.set_state(AssetStates.waiting_name)
    await call.answer()

@dp.message(AssetStates.waiting_name)
async def asset_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите сумму актива:", reply_markup=cancel_kb())
    await state.set_state(AssetStates.waiting_amount)

@dp.message(AssetStates.waiting_amount)
async def asset_amount(message: types.Message, state: FSMContext):
    try:
        amount = parse_amount_token(message.text)
    except:
        await message.answer("Не могу понять сумму, попробуйте снова.")
        return
    await state.update_data(amount=amount)
    await message.answer("Тип актива?\nНапример: депозит, карта, акции, долг и т.п.", reply_markup=cancel_kb())
    await state.set_state(AssetStates.waiting_type)

@dp.message(AssetStates.waiting_type)
async def asset_type(message: types.Message, state: FSMContext):
    user_id = await get_or_create_user(message.from_user.id)
    data = await state.get_data()

    await db.execute(
        "INSERT INTO assets (user_id, name, amount, type) VALUES ($1,$2,$3,$4)",
        user_id, data["name"], data["amount"], message.text.strip().capitalize()
    )
    await state.clear()
    await message.answer("Актив добавлен!", reply_markup=main_menu_kb())

# =========================
# BACK MAIN
# =========================

@dp.callback_query(F.data == "back_main")
async def back_main(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
    await call.answer()

# =========================
# EXPORT CSV
# =========================

@dp.callback_query(F.data == "menu_report")
async def menu_report(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("⬇️ Экспорт CSV", callback_data="export_csv")],
        [InlineKeyboardButton("📄 Генерировать отчет", callback_data="generate_report")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_main")]
    ])
    await call.message.edit_text("Отчеты и экспорт данных:", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "export_csv")
async def export_csv(call: types.CallbackQuery):
    user_id = await get_or_create_user(call.from_user.id)
    rows = await db.fetch(
        "SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at ASC",
        user_id
    )
    if not rows:
        await call.message.edit_text("Нет данных для экспорта.", reply_markup=main_menu_kb())
        await call.answer()
        return

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    with open(tmp.name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["amount", "category", "description", "created_at"])
        for r in rows:
            writer.writerow([
                int(r["amount"]),
                r["category"],
                r["description"] or "",
                r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            ])

    file = FSInputFile(tmp.name, filename="transactions.csv")
    await call.message.answer_document(file, caption="Ваш CSV-файл 📎", reply_markup=main_menu_kb())
    await call.answer()

# END of PART 2/4
# =========================
# PART 3/4
# Charts, table reports, AI consult, report generation handlers
# =========================

# Helper: safe DB fetch
async def safe_fetch(query: str, *args):
    global db
    if db is None:
        return []
    return await db.fetch(query, *args)

# ---------- Charts: doughnut (expenses by category) + progress bars (goals) ----------
async def generate_combined_chart_for_user(user_id: int, days_for_transactions: int = 30) -> str:
    """
    Create an image at CHART_TMP and return path.
    Top: doughnut — expenses by category for current month (or last days)
    Bottom: horizontal progress bars — goals progress (percent)
    """
    # gather transactions
    since = datetime.utcnow() - timedelta(days=days_for_transactions)
    txs = await safe_fetch("SELECT amount, category, created_at FROM transactions WHERE user_id=$1 AND created_at >= $2", user_id, since)
    # category sums
    cat_sums = {}
    for t in txs:
        cat = (t["category"] or "Прочее").capitalize()
        cat_sums[cat] = cat_sums.get(cat, 0) + float(t["amount"])

    labels = list(cat_sums.keys())
    values = [cat_sums[k] for k in labels]

    # goals
    goals = await safe_fetch("SELECT title, target, current FROM goals WHERE user_id=$1 ORDER BY created_at ASC", user_id)

    # assets (available funds)
    assets = await safe_fetch("SELECT amount, type FROM assets WHERE user_id=$1", user_id)
    total_assets = sum([a["amount"] for a in assets if a["type"] and a["type"].lower() == "asset"]) if assets else 0
    total_debts = sum([a["amount"] for a in assets if a["type"] and a["type"].lower() == "debt"]) if assets else 0
    available = total_assets - total_debts

    # prepare figure
    fig = plt.figure(figsize=(8, 10))
    # Top: doughnut
    ax1 = fig.add_subplot(2, 1, 1)
    if not labels or sum(values) == 0:
        ax1.text(0.5, 0.5, "Нет трат за период", ha="center", va="center")
        ax1.axis("off")
    else:
        wedges, texts, autotexts = ax1.pie(values, labels=labels, autopct=lambda p: f"{int(round(p))}%", startangle=90)
        centre_circle = plt.Circle((0, 0), 0.60, fc="white")
        ax1.add_artist(centre_circle)
        ax1.set_title("Траты по категориям (последние {} дней)".format(days_for_transactions))
        total_sum = sum(values)
        ax1.text(0, 0, f"{int(round(total_sum))}₽", horizontalalignment="center", verticalalignment="center", fontsize=14, fontweight="bold")

    # Bottom: goals progress bars
    ax2 = fig.add_subplot(2, 1, 2)
    if goals:
        titles = [g["title"] for g in goals]
        targets = [float(g["target"]) for g in goals]
        currents = [float(g["current"]) for g in goals]
        percents = [int(round((c/t)*100)) if t > 0 else 0 for c,t in zip(currents, targets)]
        y_pos = list(range(len(titles)))
        for i, (title, pct, cur, tar) in enumerate(zip(titles, percents, currents, targets)):
            # background
            ax2.barh(i, 100, color="#e6e6e6", height=0.6)
            # filled
            ax2.barh(i, max(0, min(pct, 100)), color="#2ca02c", height=0.6)
            # label to the right
            label = f"{title} — {int(cur)}/{int(tar)} ₽ ({pct}%)"
            ax2.text(102, i, label, va="center", fontsize=9)
            # completed tick
            if cur >= tar and tar > 0:
                ax2.text(min(pct, 100)/2, i, "✓", ha="center", va="center", color="white", fontsize=10, fontweight="bold")
        ax2.set_yticks(y_pos)
        ax2.set_yticklabels([])
        ax2.set_xlim(0, 110)
        ax2.set_xlabel("Прогресс (%)")
        ax2.set_title(f"Прогресс по целям — доступно {int(available)}₽")
    else:
        ax2.text(0.5, 0.5, "Цели не заданы", ha="center", va="center")
        ax2.axis("off")

    plt.tight_layout()
    path = os.path.join(CHART_TMP, f"combined_{user_id}_{int(datetime.utcnow().timestamp())}.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path

# ---------- Transaction table image ----------
async def build_transactions_table_image(user_id: int, days: int = 30) -> str:
    since = datetime.utcnow() - timedelta(days=days)
    rows = await safe_fetch("SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 AND created_at >= $2 ORDER BY created_at DESC", user_id, since)
    if not rows:
        # create simple "no data" image
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.axis("off")
        ax.text(0.5, 0.5, "Нет транзакций за период", ha="center", va="center")
        path = os.path.join(CHART_TMP, f"table_{user_id}_{int(datetime.utcnow().timestamp())}.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        return path

    headers = ["Сумма", "Категория", "Описание", "Дата/Время"]
    table = []
    for r in rows:
        amt = f"{int(r['amount'])}₽"
        cat = (r['category'] or "Прочее").capitalize()
        desc = r['description'] or ""
        dt = r['created_at'].strftime("%Y-%m-%d %H:%M")
        table.append([amt, cat, desc, dt])

    # figure size depends on rows
    height = max(2, 0.35 * len(table) + 1)
    fig, ax = plt.subplots(figsize=(8, height))
    ax.axis("off")
    tbl = ax.table(cellText=table, colLabels=headers, loc="center", cellLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.1)
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("#dcdcdc")
        cell.set_linewidth(0.5)
        if row == 0:
            cell.set_text_props(weight="bold")
            cell.set_facecolor("#f5f5f5")
    plt.tight_layout()
    path = os.path.join(CHART_TMP, f"table_{user_id}_{int(datetime.utcnow().timestamp())}.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path

# ---------- Generate and send combined chart (helper used by handlers) ----------
async def generate_and_send_combined_chart_to_chat(chat_id: int, user_id: int, days: int = 30):
    try:
        path = await generate_combined_chart_for_user(user_id, days)
        await bot.send_photo(chat_id, FSInputFile(path), caption="Графики: Траты и Прогресс", reply_markup=main_menu_kb())
        try:
            os.remove(path)
        except:
            pass
    except Exception as e:
        print("generate chart error:", e)
        await bot.send_message(chat_id, "Ошибка при генерации графиков.", reply_markup=main_menu_kb())

# ---------- Build and send table ----------
async def send_transactions_table(chat_id: int, user_id: int, days: int = 30):
    try:
        path = await build_transactions_table_image(user_id, days)
        await bot.send_photo(chat_id, FSInputFile(path), caption=f"Транзакции за {days} дней", reply_markup=main_menu_kb())
        try:
            os.remove(path)
        except:
            pass
    except Exception as e:
        print("table generate error:", e)
        await bot.send_message(chat_id, "Ошибка при генерации таблицы.", reply_markup=main_menu_kb())

# ---------- Callback: generate_report ----------
@dp.callback_query(F.data == "generate_report")
async def cb_generate_report(call: types.CallbackQuery):
    await call.answer()
    user_id = await get_or_create_user(call.from_user.id)
    await call.message.answer("Генерирую отчет и графики... (несколько секунд)")
    # send table and charts
    await send_transactions_table(call.from_user.id, user_id, days=30)
    await generate_and_send_combined_chart_to_chat(call.from_user.id, user_id, days_for_transactions=30)
    await call.message.answer("Готово.", reply_markup=main_menu_kb())

# ---------- Consult: AI short plan ----------
@dp.message(Command("consult"))
async def cmd_consult(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    await message.answer("Готовлю короткий пошаговый план на основе ваших данных...")
    snapshot = await finance_snapshot_text(user_id)
    system = "Ты — финансовый советник. Составь практичный, краткий план действий (3-6 пунктов) на основе данных ниже."
    messages = [{"role":"system","content":system},{"role":"user","content":snapshot}]
    try:
        ans = await gigachat_request(messages)
    except Exception as e:
        print("consult error:", e)
        ans = "AI временно недоступен."
    await message.answer(ans, reply_markup=main_menu_kb())

# ---------- Callback: menu_charts (from Part 2) handler ----------
@dp.callback_query(F.data == "menu_charts")
async def cb_menu_charts(call: types.CallbackQuery):
    await call.answer()
    user_id = await get_or_create_user(call.from_user.id)
    await call.message.answer("Генерирую графики...")
    await generate_and_send_combined_chart_to_chat(call.from_user.id, user_id, days=30)

# ---------- Callback: quick report button (if any) ----------
@dp.callback_query(F.data == "quick_table")
async def cb_quick_table(call: types.CallbackQuery):
    await call.answer()
    user_id = await get_or_create_user(call.from_user.id)
    await call.message.answer("Генерирую таблицу транзакций...")
    await send_transactions_table(call.from_user.id, user_id, days=30)

# End of PART 3/4
# =========================
# PART 4/4
# main(), scheduler, db creation, weekly report
# =========================

# DB INIT: create tables if not exist
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    amount NUMERIC,
    category TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS goals (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    title TEXT,
    target NUMERIC,
    current NUMERIC,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    name TEXT,
    amount NUMERIC,
    type TEXT,  -- asset / debt
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_context (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    role TEXT,
    content TEXT
);
"""

async def init_db():
    """Initialize PostgreSQL connection and create tables."""
    global db
    try:
        db = await asyncpg.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            port=DB_PORT,
            min_size=1,
            max_size=5
        )
        async with db.acquire() as conn:
            await conn.execute(CREATE_TABLES_SQL)
        print("DB connected and tables ensured.")
    except Exception as e:
        print("DB init error:", e)
        raise


# ------------- WEEKLY REPORT JOB (every Monday 09:00 Europe/London) -------------
async def send_weekly_report(user_id: int):
    """Generate full report and send to user."""
    chat_id = await db.fetchval("SELECT tg_id FROM users WHERE id=$1", user_id)
    if not chat_id:
        return

    await bot.send_message(chat_id, "📊 Ваш еженедельный финансовый отчет:")

    # Table
    await send_transactions_table(chat_id, user_id, days=7)

    # Charts
    await generate_and_send_combined_chart_to_chat(chat_id, user_id, days_for_transactions=7)

    # AI recommendations
    snapshot = await finance_snapshot_text(user_id)
    system = (
        "Ты — финансовый советник. "
        "Сформируй 3–5 пунктов рекомендаций на основе данных за неделю. "
        "Коротко, без воды."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": snapshot},
    ]
    try:
        ans = await gigachat_request(messages)
    except:
        ans = "AI рекомендация недоступна."

    await bot.send_message(chat_id, ans)


async def weekly_job():
    """Iterate over all users and send the weekly report."""
    users = await db.fetch("SELECT id FROM users")
    for u in users:
        try:
            await send_weekly_report(u["id"])
        except Exception as e:
            print("Weekly report error:", e)


# ------------- MAIN STARTUP FUNCTION -------------
async def main():
    global scheduler

    # Init DB
    await init_db()

    # Start scheduler
    scheduler = AsyncIOScheduler(timezone="Europe/London")
    scheduler.add_job(
        weekly_job,
        trigger="cron",
        day_of_week="mon",
        hour=9,
        minute=0
    )
    scheduler.start()
    print("Scheduler started.")

    # Start Bot polling
    try:
        print("Bot started.")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        print("Bot stopped.")
        if scheduler:
            scheduler.shutdown()
        if db:
            await db.close()


# ------------- ENTRY POINT -------------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exited by keyboard interrupt")
