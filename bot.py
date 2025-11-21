#!/usr/bin/env python3
# coding: utf-8
"""
FinAdvisor - upgraded bot.py
- /consult and "💡 Консультация" button
- assets / liabilities (таблицы assets, liabilities)
- ai_context and ai_cache usage
- APScheduler weekly job
- FSM cancel buttons
- export CSV, chart PNG
"""

import os
import asyncio
import base64
import uuid
import hashlib
import tempfile
from datetime import datetime, timedelta

import asyncpg
import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

load_dotenv()

# -------------------------
# CONFIG (from .env)
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
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat:2.0.28.2")

CHART_DIR = "/tmp"
os.makedirs(CHART_DIR, exist_ok=True)

# -------------------------
# GLOBALS
# -------------------------
bot = Bot(BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

db: asyncpg.pool.Pool | None = None
scheduler = AsyncIOScheduler()

# quick in-memory pending transactions for confirmation (user_id -> data)
pending_pending = {}

# -------------------------
# UTIL: DB pool
# -------------------------
async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT, min_size=1, max_size=8
    )

# -------------------------
# GIGACHAT: token + request (async)
# -------------------------
async def get_gigachat_token():
    # Basic auth header: base64(client_id:client_secret)
    auth = f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}"
    b64 = base64.b64encode(auth.encode()).decode()
    headers = {
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4())
    }
    data = {"scope": GIGACHAT_SCOPE}
    async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
        r = await client.post(GIGACHAT_AUTH_URL, headers=headers, data=data)
        r.raise_for_status()
        j = r.json()
        return j.get("access_token")

async def gigachat_request(messages, model=GIGACHAT_MODEL):
    token = await get_gigachat_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {"model": model, "messages": messages, "temperature": 0.3}
    async with httpx.AsyncClient(verify=False, timeout=40.0) as client:
        r = await client.post(GIGACHAT_API_URL, headers=headers, json=payload)
        r.raise_for_status()
        j = r.json()
        # compatible with returned structure
        return j["choices"][0]["message"]["content"]

# -------------------------
# AI cache helpers (uses ai_cache table)
# -------------------------
def _input_hash(user_message: str, snapshot: str) -> str:
    h = hashlib.sha256((user_message.strip().lower() + "\n" + snapshot).encode("utf-8")).hexdigest()
    return h

async def get_ai_cache(user_id: int, user_message: str, snapshot: str):
    h = _input_hash(user_message, snapshot)
    row = await db.fetchrow("SELECT answer FROM ai_cache WHERE user_id=$1 AND input_hash=$2 ORDER BY created_at DESC LIMIT 1", user_id, h)
    return row["answer"] if row else None

async def save_ai_cache(user_id: int, user_message: str, snapshot: str, answer: str):
    h = _input_hash(user_message, snapshot)
    await db.execute("INSERT INTO ai_cache (user_id, input_hash, answer, created_at) VALUES ($1,$2,$3,NOW())", user_id, h, answer)

# -------------------------
# ai_context helpers
# -------------------------
async def save_context(user_id: int, role: str, content: str):
    await db.execute("INSERT INTO ai_context (user_id, role, content, created_at) VALUES ($1,$2,$3,NOW())", user_id, role, content)

async def get_full_context(user_id: int):
    rows = await db.fetch("SELECT role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC", user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

# Always-on summarization: simple auto-trim when context grows too large (optional)
CONTEXT_TRIM_THRESHOLD = 800
CONTEXT_TRIM_KEEP = 400

async def maybe_summarize_context(user_id: int):
    # if rows count > threshold, summarize oldest portion and replace with a short system summary
    cnt_row = await db.fetchrow("SELECT count(*)::int AS c FROM ai_context WHERE user_id=$1", user_id)
    if not cnt_row:
        return
    cnt = cnt_row["c"]
    if cnt <= CONTEXT_TRIM_THRESHOLD:
        return
    take = cnt - CONTEXT_TRIM_KEEP
    rows = await db.fetch("SELECT id, role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC LIMIT $2", user_id, take)
    if not rows:
        return
    text = "\n".join([f"{r['role']}: {r['content']}" for r in rows])
    system = {"role": "system", "content": "Сделай компактное (2-3 предложения) резюме ключевых финансовых моментов."}
    try:
        summary = await gigachat_request([system, {"role":"user","content":text}])
        # save summary as system note
        await save_context(user_id, "system", f"SUMMARY: {summary}")
        ids = [r["id"] for r in rows]
        # delete old rows by ids
        await db.execute("DELETE FROM ai_context WHERE id = ANY($1::int[])", ids)
    except Exception as e:
        print("summarize failed:", e)

# -------------------------
# Transactions & auto-categorization helpers
# -------------------------
def parse_amount_token(s: str) -> int:
    # accept numbers with optional k/m suffix, commas, spaces
    s0 = s.strip().lower().replace(" ", "").replace(",", ".")
    if s0.endswith("k"):
        return int(float(s0[:-1]) * 1000)
    if s0.endswith("m"):
        return int(float(s0[:-1]) * 1_000_000)
    return int(float(s0))

CATEGORY_KEYWORDS = {
    "еда": ["кофе", "ресторан", "пятёрочка", "ашан", "магнит", "кфс", "макдоналдс"],
    "такси": ["такси", "uber", "bolt", "yandex"],
    "продукты": ["продукт", "огурец", "хлеб"],
    "развлечения": ["кино", "театр", "музей"],
}

def guess_category(text: str):
    if not text:
        return None
    s = text.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in s:
                return cat
    return None

async def analyze_user_finances_text(user_id: int, limit: int = 100):
    rows = await db.fetch("SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2", user_id, limit)
    if not rows:
        return "Нет транзакций."
    text = "Последние транзакции:\n"
    for r in rows:
        ts = r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else ""
        text += f"- {r['amount']}₽ | {r.get('category') or '—'} | {r.get('description') or ''} | {ts}\n"
    # goals
    goals = await db.fetch("SELECT title, target, current, created_at FROM goals WHERE user_id=$1", user_id)
    if goals:
        text += "\nЦели:\n"
        for g in goals:
            text += f"- {g.get('title','Цель')}: {g['current']}/{g['target']} ₽\n"
    # assets / liabilities brief
    assets = await db.fetch("SELECT title, amount, type FROM assets WHERE user_id=$1", user_id)
    if assets:
        text += "\nАктивы:\n"
        for a in assets:
            text += f"- {a['title']} ({a['type']}): {a['amount']} ₽\n"
    liabs = await db.fetch("SELECT title, amount, type FROM liabilities WHERE user_id=$1", user_id)
    if liabs:
        text += "\nДолги:\n"
        for l in liabs:
            text += f"- {l['title']} ({l['type']}): {l['amount']} ₽\n"
    return text

# -------------------------
# User helpers
# -------------------------
async def get_or_create_user(tg_id: int):
    row = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]
    row = await db.fetchrow("INSERT INTO users (tg_id, created_at) VALUES ($1,NOW()) RETURNING id", tg_id)
    return row["id"]

# -------------------------
# Keyboards
# -------------------------
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить расход", callback_data="menu_add")],
        [InlineKeyboardButton(text="🎯 Мои цели", callback_data="menu_goals"), InlineKeyboardButton(text="💡 Консультация", callback_data="menu_consult")],
        [InlineKeyboardButton(text="💼 Управление капиталом", callback_data="menu_capital"), InlineKeyboardButton(text="📈 График", callback_data="menu_chart")],
        [InlineKeyboardButton(text="📤 Экспорт CSV", callback_data="menu_export"), InlineKeyboardButton(text="📊 Отчёт", callback_data="menu_report")]
    ])

def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]
    ])

def confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить ✅", callback_data="confirm_tx"), InlineKeyboardButton(text="Отмена ❌", callback_data="cancel_fsm")]
    ])

def capital_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить актив", callback_data="cap_add_asset"), InlineKeyboardButton(text="➕ Добавить долг", callback_data="cap_add_liab")],
        [InlineKeyboardButton(text="📋 Показать баланс", callback_data="cap_show"), InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")]
    ])

# -------------------------
# Handlers: /start /help
# -------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await get_or_create_user(message.from_user.id)
    txt = ("Привет! Я FinAdvisor — твой финансовый помощник 🤖\n\n"
           "Быстрая запись: '-2500 кофе', '+150k зарплата'\n\n"
           "Выбери действие:")
    await message.answer(txt, reply_markup=main_menu_kb())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("Команды: /consult /export /chart /start\nИли используй меню.", reply_markup=main_menu_kb())

# -------------------------
# Callback menu handlers
# -------------------------
@dp.callback_query(F.data == "menu_back")
async def cb_menu_back(q: types.CallbackQuery):
    await q.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
    await q.answer()

@dp.callback_query(F.data == "menu_add")
async def cb_menu_add(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddTx.amount)
    await q.message.answer("Введите сумму (пример: -2500 или 1500):", reply_markup=cancel_kb())
    await q.answer()

@dp.callback_query(F.data == "menu_goals")
async def cb_menu_goals(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)
    rows = await db.fetch("SELECT id, title, target, current FROM goals WHERE user_id=$1", user_id)
    if not rows:
        await q.message.answer("Целей нет. Используй меню и добавь через 'Мои цели' -> /goal")
    else:
        s = "Твои цели:\n"
        for r in rows:
            s += f"- {r['title']}: {r['current']}/{r['target']} ₽\n"
        await q.message.answer(s)
    await q.answer()

@dp.callback_query(F.data == "menu_chart")
async def cb_menu_chart(q: types.CallbackQuery):
    await q.message.answer("Генерирую график...")
    # delegate to chart handler
    await handle_chart(q.message)
    await q.answer()

@dp.callback_query(F.data == "menu_export")
async def cb_menu_export(q: types.CallbackQuery):
    await q.message.answer("Генерирую CSV...")
    await handle_export(q.message)
    await q.answer()

@dp.callback_query(F.data == "menu_report")
async def cb_menu_report(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)
    text = await analyze_user_finances_text(user_id)
    # add assets/liabilities summary
    assets = await db.fetch("SELECT title, amount FROM assets WHERE user_id=$1", user_id)
    liabs = await db.fetch("SELECT title, amount FROM liabilities WHERE user_id=$1", user_id)
    text += "\n\nАктивы:\n"
    total_assets = 0
    for a in assets:
        total_assets += a["amount"]
        text += f"- {a['title']}: {a['amount']} ₽\n"
    text += "\nДолги:\n"
    total_liab = 0
    for l in liabs:
        total_liab += l["amount"]
        text += f"- {l['title']}: {l['amount']} ₽\n"
    text += f"\nЧистый капитал: {total_assets - total_liab} ₽\n"
    await q.message.answer(text)
    await q.answer()

@dp.callback_query(F.data == "menu_capital")
async def cb_menu_capital(q: types.CallbackQuery):
    await q.message.edit_text("Управление капиталом:", reply_markup=capital_kb())
    await q.answer()

@dp.callback_query(F.data == "cap_add_asset")
async def cb_cap_add_asset(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddAsset.amount)
    await q.message.answer("Добавление актива — введите сумму (пример: 150000):", reply_markup=cancel_kb())
    await q.answer()

@dp.callback_query(F.data == "cap_add_liab")
async def cb_cap_add_liab(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddLiab.amount)
    await q.message.answer("Добавление долга — введите сумму (пример: 500000):", reply_markup=cancel_kb())
    await q.answer()

@dp.callback_query(F.data == "cap_show")
async def cb_cap_show(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)
    assets = await db.fetch("SELECT title, amount, type FROM assets WHERE user_id=$1", user_id)
    liabs = await db.fetch("SELECT title, amount, type FROM liabilities WHERE user_id=$1", user_id)
    text = "Активы:\n"
    total_assets = 0
    for a in assets:
        total_assets += a["amount"]
        text += f"- {a['title']} ({a['type']}): {a['amount']} ₽\n"
    text += "\nДолги:\n"
    total_liab = 0
    for l in liabs:
        total_liab += l["amount"]
        text += f"- {l['title']} ({l['type']}): {l['amount']} ₽\n"
    text += f"\nЧистый капитал: {total_assets - total_liab} ₽"
    await q.message.answer(text)
    await q.answer()

@dp.callback_query(F.data == "menu_consult")
async def cb_menu_consult(q: types.CallbackQuery):
    # open consult: prompt user to ask or run /consult
    await q.message.answer("Напиши свой вопрос или вызови команду /consult для автоматической рекомендаций.")
    await q.answer()

# -------------------------
# FSMs: Add transaction, assets, liabilities, goals
# -------------------------
class AddTx(StatesGroup):
    amount = State()
    category = State()
    desc = State()

class AddAsset(StatesGroup):
    amount = State()
    type = State()
    title = State()

class AddLiab(StatesGroup):
    amount = State()
    monthly = State()
    title = State()

class AddGoal(StatesGroup):
    target = State()
    title = State()

# Cancel callback for FSMs
@dp.callback_query(F.data == "cancel_fsm")
async def cb_cancel_fsm(q: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await q.message.answer("Операция отменена.", reply_markup=main_menu_kb())
    await q.answer()

# Add transaction flow
@dp.message(AddTx.amount)
async def tx_amount(message: types.Message, state: FSMContext):
    txt = message.text.strip()
    try:
        amt = parse_amount_token(txt) if txt else None
    except Exception:
        try:
            amt = int(float(txt.replace(",", ".")))
        except:
            await message.answer("Неверная сумма. Введите число.")
            return
    await state.update_data(amount=amt)
    await state.set_state(AddTx.category)
    await message.answer("Категория (или '-' для пропуска):", reply_markup=cancel_kb())

@dp.message(AddTx.category)
async def tx_category(message: types.Message, state: FSMContext):
    cat = message.text.strip()
    if cat == "-":
        cat = None
    await state.update_data(category=cat)
    await state.set_state(AddTx.desc)
    await message.answer("Описание (или '-' для пропуска):", reply_markup=cancel_kb())

@dp.message(AddTx.desc)
async def tx_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = await get_or_create_user(message.from_user.id)
    category = data.get("category") or guess_category(message.text)
    desc = message.text.strip() if message.text.strip() != "-" else None
    await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, data["amount"], category, desc)
    await save_context(user_id, "system", f"Добавлена транзакция: {data['amount']} | {category} | {desc}")
    await message.answer("Транзакция добавлена ✅", reply_markup=main_menu_kb())
    await state.clear()

# Add asset flow
@dp.message(AddAsset.amount)
async def asset_amount(message: types.Message, state: FSMContext):
    try:
        amt = int(float(message.text.strip().replace(",", ".")))
    except:
        await message.answer("Неверная сумма. Попробуйте ещё раз.")
        return
    await state.update_data(amount=amt)
    await state.set_state(AddAsset.type)
    await message.answer("Тип актива (bank/deposit/stocks/crypto/cash/other):", reply_markup=cancel_kb())

@dp.message(AddAsset.type)
async def asset_type(message: types.Message, state: FSMContext):
    t = message.text.strip()
    await state.update_data(type=t)
    await state.set_state(AddAsset.title)
    await message.answer("Название актива (например 'Счёт в Тинькофф'):", reply_markup=cancel_kb())

@dp.message(AddAsset.title)
async def asset_title(message: types.Message, state: FSMContext):
    d = await state.get_data()
    user_id = await get_or_create_user(message.from_user.id)
    title = message.text.strip()
    await db.execute("INSERT INTO assets (user_id, amount, type, title, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, d["amount"], d["type"], title)
    await save_context(user_id, "system", f"Добавлен актив: {title} {d['amount']} ₽ ({d['type']})")
    await message.answer("Актив добавлен ✅", reply_markup=main_menu_kb())
    await state.clear()

# Add liability flow
@dp.message(AddLiab.amount)
async def liab_amount(message: types.Message, state: FSMContext):
    try:
        amt = int(float(message.text.strip().replace(",", ".")))
    except:
        await message.answer("Неверная сумма. Попробуйте ещё раз.")
        return
    await state.update_data(amount=amt)
    await state.set_state(AddLiab.monthly)
    await message.answer("Ежемесячный платёж (числом):", reply_markup=cancel_kb())

@dp.message(AddLiab.monthly)
async def liab_monthly(message: types.Message, state: FSMContext):
    try:
        monthly = int(float(message.text.strip().replace(",", ".")))
    except:
        await message.answer("Неверный формат. Попробуйте число.")
        return
    await state.update_data(monthly=monthly)
    await state.set_state(AddLiab.title)
    await message.answer("Название долга (например 'Ипотека Сбер'):", reply_markup=cancel_kb())

@dp.message(AddLiab.title)
async def liab_title(message: types.Message, state: FSMContext):
    d = await state.get_data()
    user_id = await get_or_create_user(message.from_user.id)
    title = message.text.strip()
    await db.execute("INSERT INTO liabilities (user_id, amount, type, title, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, d["amount"], "loan", title)
    await save_context(user_id, "system", f"Добавлен долг: {title} {d['amount']} ₽")
    await message.answer("Долг добавлен ✅", reply_markup=main_menu_kb())
    await state.clear()

# Goals (simple)
@dp.message(Command("goal"))
async def cmd_goal_start(message: types.Message, state: FSMContext):
    await state.set_state(AddGoal.target)
    await message.answer("Введите сумму цели:", reply_markup=cancel_kb())

@dp.message(AddGoal.target)
async def goal_target(message: types.Message, state: FSMContext):
    try:
        t = int(float(message.text.strip().replace(",", ".")))
    except:
        await message.answer("Введите число.")
        return
    await state.update_data(target=t)
    await state.set_state(AddGoal.title)
    await message.answer("Название цели:", reply_markup=cancel_kb())

@dp.message(AddGoal.title)
async def goal_title(message: types.Message, state: FSMContext):
    d = await state.get_data()
    user_id = await get_or_create_user(message.from_user.id)
    await db.execute("INSERT INTO goals (user_id, target, current, title, created_at) VALUES ($1,$2,0,$3,NOW())",
                     user_id, d["target"], message.text.strip())
    await save_context(user_id, "system", f"Создана цель: {message.text.strip()} на {d['target']} ₽")
    await message.answer("Цель создана ✅", reply_markup=main_menu_kb())
    await state.clear()

# -------------------------
# Confirm pending tx (for quick parse scenario)
# -------------------------
@dp.callback_query(F.data == "confirm_tx")
async def cb_confirm_tx(q: types.CallbackQuery):
    data = pending_pending.pop(q.from_user.id, None)
    if not data:
        await q.answer("Нет ожидающих данных.", show_alert=True)
        return
    user_id = await get_or_create_user(q.from_user.id)
    if not data.get("category"):
        data["category"] = guess_category(data.get("description") or "")
    await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, data["amount"], data.get("category"), data.get("description"))
    await save_context(user_id, "system", f"Добавлена транзакция: {data['amount']} | {data.get('category')} | {data.get('description')}")
    await q.message.edit_text("Транзакция добавлена ✅")
    await q.answer()

# -------------------------
# Quick free-text parse: if user sends "-2500 кофе" etc.
# -------------------------
import re
def smart_parse_free_text(text: str):
    if not text:
        return None
    m = re.search(r"([+-]?\s*\d[\d\s\.,]*(?:k|m|к|м|млн)?)", text, re.IGNORECASE)
    if not m:
        return None
    token = m.group(1).replace(" ", "")
    # normalize token
    token = token.replace(",", ".")
    try:
        amount = parse_amount_token(token)
    except:
        try:
            amount = int(float(token))
        except:
            return None
    left = (text[:m.start()] + " " + text[m.end():]).strip()
    description = left or None
    guessed_category = guess_category(left or "")
    return (amount, guessed_category, description)

@dp.message()
async def catch_all(message: types.Message):
    # ignore pure commands (handled)
    if message.text and message.text.startswith("/"):
        return
    # quick affirmative after add prompts
    if message.text and message.text.strip().lower() in ("да", "ok", "yes"):
        await message.answer("Окей — /report или /chart ?", reply_markup=main_menu_kb())
        return
    # parse free-text transaction
    parsed = smart_parse_free_text(message.text or "")
    if parsed:
        amount, cat, desc = parsed
        pending_pending[message.from_user.id] = {"amount": amount, "category": cat, "description": desc}
        await message.answer(f"Найдено: {amount}₽ | {cat or '—'} | {desc or ''}\nПодтвердить?", reply_markup=confirm_kb())
        return
    # otherwise treat as question for AI assistant: default flow — reply with AI
    user_id = await get_or_create_user(message.from_user.id)
    # background summarization trim if needed
    asyncio.create_task(maybe_summarize_context(user_id))
    # prepare messages: system + context + user
    finance_snapshot = await analyze_user_finances_text(user_id)
    sys_prompt = f"Ты — умный финансовый ассистент. Используй историю диалога и данные транзакций/активов/долгов/целей.\nДанные пользователя:\n{finance_snapshot}"
    context = await get_full_context(user_id)
    messages = [{"role":"system","content":sys_prompt}] + context + [{"role":"user","content":message.text}]
    # try cache
    cached = await get_ai_cache(user_id, message.text or "", finance_snapshot)
    if cached:
        await save_context(user_id, "assistant", cached)
        await message.answer(cached)
        return
    try:
        ans = await gigachat_request(messages)
        await save_context(user_id, "assistant", ans)
        await save_ai_cache(user_id, message.text or "", finance_snapshot, ans)
        await message.answer(ans)
    except Exception as e:
        print("GigaChat error:", e)
        await message.answer("Извините, AI недоступен. Повторите позже.")

# -------------------------
# /consult command (short step-by-step plan)
# -------------------------
@dp.message(Command("consult"))
async def cmd_consult(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    # build snapshot
    finance_snapshot = await analyze_user_finances_text(user_id)
    sys_prompt = ("Ты — персональный финансовый консультант. На основе предоставленных данных "
                  "составь краткий пошаговый план (5 шагов максимум) для улучшения финансового состояния пользователя. "
                  "Формат: нумерованный список из коротких пунктов.")
    context = await get_full_context(user_id)
    messages = [{"role":"system","content":sys_prompt}] + context + [{"role":"user","content":finance_snapshot}]
    # cache check
    cached = await get_ai_cache(user_id, "/consult", finance_snapshot)
    if cached:
        await save_context(user_id, "assistant", cached)
        await message.answer(cached)
        return
    try:
        ans = await gigachat_request(messages)
        await save_context(user_id, "assistant", ans)
        await save_ai_cache(user_id, "/consult", finance_snapshot, ans)
        await message.answer(ans)
    except Exception as e:
        print("consult error:", e)
        await message.answer("Ошибка при обращении к AI. Попробуйте позже.")

# -------------------------
# /export CSV handler
# -------------------------
@dp.message(Command("export"))
async def cmd_export(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    rows = await db.fetch("SELECT id, amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at ASC", user_id)
    if not rows:
        await message.answer("Нет транзакций для экспорта.")
        return
    fd, path = tempfile.mkstemp(prefix=f"finances_{user_id}_", suffix=".csv")
    os_close = None
    try:
        os.close(fd)
    except Exception:
        pass
    with open(path, "w", encoding="utf-8", newline="") as f:
        import csv
        w = csv.writer(f)
        w.writerow(["id","amount","category","description","created_at"])
        for r in rows:
            w.writerow([r["id"], r["amount"], r["category"] or "", r["description"] or "", r["created_at"].isoformat() if r["created_at"] else ""])
    await message.answer_document(types.FSInputFile(path), caption="Экспорт транзакций")
    try:
        os.remove(path)
    except:
        pass

# -------------------------
# Chart generation /chart
# -------------------------
@dp.message(Command("chart"))
async def cmd_chart(message: types.Message):
    await handle_chart(message)

async def handle_chart(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    since = datetime.utcnow() - timedelta(days=30)
    rows = await db.fetch("SELECT amount, created_at FROM transactions WHERE user_id=$1 AND created_at >= $2 ORDER BY created_at ASC", user_id, since)
    if not rows:
        await message.answer("Нет транзакций за 30 дней.")
        return
    daily = {}
    for r in rows:
        d = r["created_at"].date().isoformat()
        daily[d] = daily.get(d, 0) + float(r["amount"])
    dates = sorted(daily.keys())
    values = [daily[d] for d in dates]
    plt.figure(figsize=(10,4))
    plt.plot(dates, values, marker='o')
    plt.xticks(rotation=45)
    plt.title("Динамика за 30 дней")
    plt.tight_layout()
    fname = f"{CHART_DIR}/chart_{user_id}_{int(datetime.utcnow().timestamp())}.png"
    plt.savefig(fname)
    plt.close()
    await message.answer_photo(types.FSInputFile(fname), caption="График расходов/доходов (30 дней)")
    try:
        os.remove(fname)
    except:
        pass

# -------------------------
# Weekly report job (APScheduler)
# -------------------------
async def build_weekly_for_user(user):
    user_id = user["id"]
    tg_id = user["tg_id"]
    finance = await analyze_user_finances_text(user_id)
    assets = await db.fetch("SELECT title, amount FROM assets WHERE user_id=$1", user_id)
    liabs = await db.fetch("SELECT title, amount FROM liabilities WHERE user_id=$1", user_id)
    tot_assets = sum(a["amount"] for a in assets) if assets else 0
    tot_liabs = sum(l["amount"] for l in liabs) if liabs else 0
    net = tot_assets - tot_liabs
    text = f"Еженедельный отчёт:\n\n{finance}\n\nАктивы: {tot_assets} ₽\nДолги: {tot_liabs} ₽\nЧистый капитал: {net} ₽"
    # send
    try:
        await bot.send_message(tg_id, text)
    except Exception as e:
        print("send weekly failed:", e)

async def weekly_job():
    users = await db.fetch("SELECT id, tg_id FROM users")
    for u in users:
        await build_weekly_for_user(u)

def start_scheduler():
    # run weekly on Monday 09:00 UTC (adjust if needed)
    scheduler.add_job(weekly_job, 'cron', day_of_week='mon', hour=9, minute=0)
    scheduler.start()

# -------------------------
# Startup / Shutdown
# -------------------------
@dp.startup()
async def on_startup():
    global db
    db = await create_db_pool()
    print("DB connected")
    start_scheduler()

# -------------------------
# Main run
# -------------------------
if __name__ == "__main__":
    try:
        asyncio.run(dp.start_polling(bot))
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down")
