#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FinAdvisor bot.py
- aiogram 3.x
- uses asyncpg
- GigaChat integration via OAuth + chat completions (uses blocking requests executed in executor)
- uses DB tables as provided by user
"""

import os
import asyncio
import asyncpg
import uuid
import base64
import csv
import tempfile
import hashlib
from datetime import datetime, timedelta
from functools import partial
from typing import List, Dict

import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from dotenv import load_dotenv

load_dotenv()

# -----------------------
# CONFIG
# -----------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))

# GigaChat / OAuth params (as you used successfully)
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE")
GIGACHAT_AUTH_URL = os.getenv("GIGACHAT_AUTH_URL")
GIGACHAT_API_URL = os.getenv("GIGACHAT_API_URL")
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat:2.0.28.2")

# chart folder
CHART_DIR = "/tmp"
os.makedirs(CHART_DIR, exist_ok=True)

# -----------------------
# GLOBALS
# -----------------------
bot = Bot(BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

db: asyncpg.pool.Pool = None
scheduler = AsyncIOScheduler()

# -----------------------
# HELPERS: DB
# -----------------------
async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT, min_size=1, max_size=8
    )

async def get_or_create_user(tg_id: int) -> int:
    row = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]
    r = await db.fetchrow("INSERT INTO users (tg_id, created_at) VALUES ($1, NOW()) RETURNING id", tg_id)
    return r["id"]

# -----------------------
# GIGACHAT: blocking requests wrapped in executor
# -----------------------
def blocking_get_token():
    """
    Blocking token request (synchronous). Uses same working flow as your test script.
    """
    auth_header = f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_header.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4())
    }
    data = {"scope": GIGACHAT_SCOPE}
    # verify=False because your environment used self-signed cert; keep same behavior
    r = requests.post(GIGACHAT_AUTH_URL, headers=headers, data=data, verify=False, timeout=20)
    r.raise_for_status()
    return r.json().get("access_token")

def blocking_gigachat_call(access_token: str, messages: List[Dict]):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "model": GIGACHAT_MODEL,
        "messages": messages,
        "temperature": 0.3
    }
    r = requests.post(GIGACHAT_API_URL, headers=headers, json=payload, verify=False, timeout=30)
    r.raise_for_status()
    return r.json()

async def get_gigachat_token() -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, blocking_get_token)

async def gigachat_request(messages: List[Dict]) -> str:
    """
    Performs token acquisition and chat call in executor to avoid blocking loop.
    Uses DB ai_cache to store caching by input hash (see get/save below).
    """
    token = await get_gigachat_token()
    loop = asyncio.get_running_loop()
    j = await loop.run_in_executor(None, partial(blocking_gigachat_call, token, messages))
    # parse result safely
    choices = j.get("choices") or []
    if choices:
        msg = choices[0].get("message", {}).get("content")
        if msg:
            return msg
    # fallback: stringify
    return str(j)

# -----------------------
# AI CACHE (DB-backed)
# -----------------------
def _hash_input(user_message: str, finance_snapshot: str) -> str:
    h = (user_message or "").strip().lower() + "\n" + (finance_snapshot or "")
    return hashlib.sha256(h.encode("utf-8")).hexdigest()

async def get_cached_ai_reply_db(user_id: int, user_message: str, finance_snapshot: str):
    h = _hash_input(user_message, finance_snapshot)
    row = await db.fetchrow("SELECT answer FROM ai_cache WHERE user_id=$1 AND input_hash=$2 ORDER BY created_at DESC LIMIT 1", user_id, h)
    return row["answer"] if row else None

async def save_ai_cache_db(user_id: int, user_message: str, finance_snapshot: str, answer: str):
    h = _hash_input(user_message, finance_snapshot)
    await db.execute("INSERT INTO ai_cache (user_id, input_hash, answer, created_at) VALUES ($1,$2,$3,NOW())", user_id, h, answer)

# -----------------------
# AI CONTEXT (DB)
# -----------------------
async def save_message_context(user_id: int, role: str, content: str):
    await db.execute("INSERT INTO ai_context (user_id, role, content, created_at) VALUES ($1,$2,$3,NOW())", user_id, role, content)

async def load_full_context(user_id: int):
    rows = await db.fetch("SELECT role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC", user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

# -----------------------
# FINANCE ANALYSIS (transactions + assets + liabilities + goals)
# -----------------------
async def analyze_user_finances_text(user_id: int) -> str:
    # transactions
    rows = await db.fetch("SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT 200", user_id)
    text = ""
    if not rows:
        text += "Транзакций: нет.\n"
    else:
        text += "Последние транзакции:\n"
        for r in rows[:50]:
            created = r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else ""
            text += f"- {r['amount']}₽ | {r.get('category') or '—'} | {r.get('description') or ''} | {created}\n"

    # goals
    gs = await db.fetch("SELECT title, target, current, created_at FROM goals WHERE user_id=$1", user_id)
    if gs:
        text += "\nЦели:\n"
        for g in gs:
            text += f"- {g.get('title','Цель')}: {g['current']}/{g['target']} ₽\n"

    # assets
    assets = await db.fetch("SELECT title, type, amount FROM assets WHERE user_id=$1 ORDER BY created_at DESC", user_id)
    if assets:
        text += "\nАктивы:\n"
        for a in assets:
            text += f"- {a['title']} ({a['type']}): {a['amount']} ₽\n"
        total_assets = sum(a["amount"] for a in assets)
        text += f"Итого активов: {total_assets}₽\n"
    else:
        text += "\nАктивы: нет.\n"

    # liabilities
    liab = await db.fetch("SELECT title, type, amount FROM liabilities WHERE user_id=$1 ORDER BY created_at DESC", user_id)
    if liab:
        text += "\nДолги:\n"
        for l in liab:
            text += f"- {l['title']} ({l['type']}): {l['amount']} ₽\n"
        total_liab = sum(l["amount"] for l in liab)
        text += f"Итого долгов: {total_liab}₽\n"
    else:
        text += "\nДолги: нет.\n"

    # net worth
    total_assets = sum(a["amount"] for a in assets) if assets else 0
    total_liab = sum(l["amount"] for l in liab) if liab else 0
    net = total_assets - total_liab
    text += f"\nЧистый капитал: {net}₽\n"

    return text

# -----------------------
# AI reply builder & /consult
# -----------------------
async def generate_ai_reply(user_id: int, user_message: str) -> str:
    # try cache
    finance_snapshot = await analyze_user_finances_text(user_id)
    cached = await get_cached_ai_reply_db(user_id, user_message, finance_snapshot)
    if cached:
        await save_message_context(user_id, "assistant", cached)
        return cached

    # prepare messages (system + context + user)
    context = await load_full_context(user_id)
    system_prompt = (
        "Ты — персональный финансовый ассистент. Используй историю диалога, транзакции, активы, долги и цели."
        "Отвечай чётко и профессионально."
    )
    messages = [{"role": "system", "content": system_prompt}] + context + [{"role": "user", "content": user_message}]
    try:
        resp = await gigachat_request(messages)
    except Exception as e:
        # fallback to cache empty
        fallback = await get_cached_ai_reply_db(user_id, user_message, "")
        if fallback:
            await save_message_context(user_id, "assistant", fallback)
            return fallback
        return "Извините, AI временно недоступен. Попробуйте позже."

    await save_message_context(user_id, "assistant", resp)
    await save_ai_cache_db(user_id, user_message, finance_snapshot, resp)
    return resp

async def generate_consultation(user_id: int) -> str:
    # Short step-by-step plan based on finances
    finance_snapshot = await analyze_user_finances_text(user_id)
    # system: ask GigaChat to give short step-by-step plan
    messages = [
        {"role": "system", "content": "Ты — финансовый консультант. Дай 5 коротких и конкретных шагов для улучшения финансового состояния."},
        {"role": "user", "content": f"Вот данные пользователя:\n{finance_snapshot}\nСформируй 5 пунктов плана, каждый пункт — одно предложение."}
    ]
    try:
        resp = await gigachat_request(messages)
    except Exception:
        return "Извините, не удалось получить консультацию от AI. Попробуйте позже."
    # save assistant message to context
    await save_message_context(user_id, "assistant", resp)
    return resp

# -----------------------
# UI: keyboards
# -----------------------
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить транзакцию", callback_data="menu_add"),
         InlineKeyboardButton(text="🎯 Мои цели", callback_data="menu_goals")],
        [InlineKeyboardButton(text="💼 Управление капиталом", callback_data="menu_capital"),
         InlineKeyboardButton(text="📊 Отчёт", callback_data="menu_report")],
        [InlineKeyboardButton(text="📈 График (/chart)", callback_data="menu_chart"),
         InlineKeyboardButton(text="💡 Консультация", callback_data="menu_consult")],
        [InlineKeyboardButton(text="📤 Экспорт CSV", callback_data="menu_export")]
    ])

def cancel_kb(text="❌ Отмена"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="cancel_fsm")],
    ])

# Capital submenu
def capital_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить актив", callback_data="cap_add_asset"),
         InlineKeyboardButton(text="➕ Добавить долг", callback_data="cap_add_liab")],
        [InlineKeyboardButton(text="📋 Показать активы/долги", callback_data="cap_show"),
         InlineKeyboardButton(text="💳 Чистый капитал", callback_data="cap_net")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")]
    ])

# confirm pending transaction keyboard (when parsed quick text)
confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Подтвердить ✅", callback_data="confirm_tx"),
     InlineKeyboardButton(text="Отмена ❌", callback_data="cancel_tx")]
])

# -----------------------
# FSM states
# -----------------------
class TxStates(StatesGroup):
    amount = State()
    category = State()
    description = State()

class GoalStates(StatesGroup):
    target = State()
    title = State()

class AssetStates(StatesGroup):
    amount = State()
    typ = State()
    title = State()

class LiabStates(StatesGroup):
    amount = State()
    typ = State()
    title = State()

# -----------------------
# Quick text parsing helper (very simple)
# -----------------------
import re
UNIT_MAP = {"k": 1_000, "к": 1_000, "m": 1_000_000, "м": 1_000_000, "млн": 1_000_000}
def parse_amount_token(s: str):
    s0 = s.strip().lower().replace(" ", "").replace("\u2009","")
    s0 = s0.replace(",", ".")
    m = re.match(r"^([+-]?\d+(\.\d+)?)([a-zа-яё%]*)$", s0, re.IGNORECASE)
    if not m:
        # try to catch "1.5k"
        m2 = re.match(r"^([\d\.]+)([a-zа-я]+)$", s0, re.IGNORECASE)
        if not m2:
            raise ValueError("invalid")
        num = float(m2.group(1))
        unit = m2.group(2)
        mult = 1
        for k,v in UNIT_MAP.items():
            if unit.startswith(k):
                mult = v
                break
        return int(round(num*mult))
    num = float(m.group(1))
    unit = m.group(3) or ""
    mult = 1
    for k,v in UNIT_MAP.items():
        if unit.startswith(k):
            mult = v
            break
    return int(round(num*mult))

# -----------------------
# PENDING quick parsed tx storage
# -----------------------
pending_tx = {}

# -----------------------
# COMMANDS / CALLBACKS / HANDLERS
# -----------------------
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await get_or_create_user(m.from_user.id)
    await m.answer(
        "Привет! Я FinAdvisor — помощник по личным финансам.\n\n"
        "Можно быстро добавить транзакцию в одну строку (например: -2500 кофе) или воспользоваться меню.",
        reply_markup=main_menu_kb()
    )

@dp.callback_query(lambda c: c.data == "menu_back")
async def cb_menu_back(c: types.CallbackQuery):
    await c.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
    await c.answer()

@dp.callback_query(lambda c: c.data == "menu_report")
async def cb_menu_report(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    txt = await analyze_user_finances_text(user_id)
    await c.message.answer(txt)
    await c.answer()

@dp.callback_query(lambda c: c.data == "menu_export")
async def cb_menu_export(c: types.CallbackQuery):
    # call export handler
    await handle_export_callback(c)
    await c.answer()

@dp.callback_query(lambda c: c.data == "menu_chart")
async def cb_menu_chart(c: types.CallbackQuery):
    # call chart handler
    await cmd_chart(c.message)
    await c.answer()

@dp.callback_query(lambda c: c.data == "menu_consult")
async def cb_menu_consult(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    await c.message.answer("Готовлю короткую консультацию...")
    resp = await generate_consultation(user_id)
    await c.message.answer(resp)
    await c.answer()

# -----------------------
# Capital submenu
# -----------------------
@dp.callback_query(lambda c: c.data == "menu_capital")
async def cb_menu_capital(c: types.CallbackQuery):
    await c.message.edit_text("Управление капиталом:", reply_markup=capital_menu_kb())
    await c.answer()

@dp.callback_query(lambda c: c.data == "cap_add_asset")
async def cb_cap_add_asset(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(AssetStates.amount)
    await c.message.answer("Введите сумму актива (пример: 150000):", reply_markup=cancel_kb())
    await c.answer()

@dp.callback_query(lambda c: c.data == "cap_add_liab")
async def cb_cap_add_liab(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(LiabStates.amount)
    await c.message.answer("Введите сумму долга (пример: 500000):", reply_markup=cancel_kb())
    await c.answer()

@dp.callback_query(lambda c: c.data == "cap_show")
async def cb_cap_show(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    assets = await db.fetch("SELECT title, type, amount FROM assets WHERE user_id=$1", user_id)
    liabs = await db.fetch("SELECT title, type, amount FROM liabilities WHERE user_id=$1", user_id)
    out = "Активы:\n"
    if assets:
        for a in assets:
            out += f"- {a['title']} ({a['type']}): {a['amount']} ₽\n"
    else:
        out += "- нет\n"
    out += "\nДолги:\n"
    if liabs:
        for l in liabs:
            out += f"- {l['title']} ({l['type']}): {l['amount']} ₽\n"
    else:
        out += "- нет\n"
    # net
    tot_a = sum(a["amount"] for a in assets) if assets else 0
    tot_l = sum(l["amount"] for l in liabs) if liabs else 0
    out += f"\nЧистый капитал: {tot_a - tot_l} ₽"
    await c.message.answer(out)
    await c.answer()

@dp.callback_query(lambda c: c.data == "cap_net")
async def cb_cap_net(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    assets = await db.fetch("SELECT amount FROM assets WHERE user_id=$1", user_id)
    liabs = await db.fetch("SELECT amount FROM liabilities WHERE user_id=$1", user_id)
    tot_a = sum(a["amount"] for a in assets) if assets else 0
    tot_l = sum(l["amount"] for l in liabs) if liabs else 0
    await c.message.answer(f"Чистый капитал: {tot_a - tot_l} ₽ (активы {tot_a} ₽, долги {tot_l} ₽)")
    await c.answer()

# -----------------------
# Asset FSM
# -----------------------
@dp.message(lambda m: True, state=AssetStates.amount)
async def asset_amount(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return
    try:
        amount = parse_amount_token(message.text.strip())
    except Exception:
        await message.answer("Неверный формат суммы. Попробуйте цифрами (пример 150000).", reply_markup=cancel_kb())
        return
    await state.update_data(amount=amount)
    await state.set_state(AssetStates.typ)
    await message.answer("Укажите тип актива (bank, deposit, stocks, cash, crypto, other):", reply_markup=cancel_kb())

@dp.message(lambda m: True, state=AssetStates.typ)
async def asset_type(message: types.Message, state: FSMContext):
    await state.update_data(typ=message.text.strip())
    await state.set_state(AssetStates.title)
    await message.answer("Укажите название (например: 'Банк Точка - счет')", reply_markup=cancel_kb())

@dp.message(lambda m: True, state=AssetStates.title)
async def asset_title(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = await get_or_create_user(message.from_user.id)
    await db.execute("INSERT INTO assets (user_id, title, type, amount, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, message.text.strip(), data["typ"], data["amount"])
    await save_message_context(user_id, "system", f"Добавлен актив: {message.text.strip()} {data['amount']} ₽")
    await message.answer("Актив добавлен ✅", reply_markup=main_menu_kb())
    await state.clear()

# -----------------------
# Liability FSM
# -----------------------
@dp.message(lambda m: True, state=LiabStates.amount)
async def liab_amount(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return
    try:
        amount = parse_amount_token(message.text.strip())
    except Exception:
        await message.answer("Неверный формат суммы. Попробуйте цифрами (пример 500000).", reply_markup=cancel_kb())
        return
    await state.update_data(amount=amount)
    await state.set_state(LiabStates.typ)
    await message.answer("Укажите тип долга (loan, mortgage, credit_card, other):", reply_markup=cancel_kb())

@dp.message(lambda m: True, state=LiabStates.typ)
async def liab_type(message: types.Message, state: FSMContext):
    await state.update_data(typ=message.text.strip())
    await state.set_state(LiabStates.title)
    await message.answer("Укажите название (например: 'Ипотека Сбер')", reply_markup=cancel_kb())

@dp.message(lambda m: True, state=LiabStates.title)
async def liab_title(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = await get_or_create_user(message.from_user.id)
    await db.execute("INSERT INTO liabilities (user_id, title, type, amount, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, message.text.strip(), data["typ"], data["amount"])
    await save_message_context(user_id, "system", f"Добавлен долг: {message.text.strip()} {data['amount']} ₽")
    await message.answer("Долг добавлен ✅", reply_markup=main_menu_kb())
    await state.clear()

# -----------------------
# Cancel FSM callback
# -----------------------
@dp.callback_query(lambda c: c.data == "cancel_fsm")
async def cb_cancel_fsm(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.answer("Операция отменена.", reply_markup=main_menu_kb())
    await c.answer()

# -----------------------
# Transactions & Goals: add via menu FSM
# -----------------------
@dp.callback_query(lambda c: c.data == "menu_add")
async def cb_menu_add(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(TxStates.amount)
    await c.message.answer("Введите сумму транзакции (пример -2500 или 1500):", reply_markup=cancel_kb())
    await c.answer()

@dp.message(lambda m: True, state=TxStates.amount)
async def tx_amount(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return
    try:
        amount = parse_amount_token(message.text.strip())
    except Exception:
        await message.answer("Неверная сумма. Введите цифру или пример 1.5k:", reply_markup=cancel_kb())
        return
    await state.update_data(amount=amount)
    await state.set_state(TxStates.category)
    await message.answer("Введите категорию (или '-' чтобы пропустить):", reply_markup=cancel_kb())

@dp.message(lambda m: True, state=TxStates.category)
async def tx_category(message: types.Message, state: FSMContext):
    cat = message.text.strip()
    if cat == "-":
        cat = None
    await state.update_data(category=cat)
    await state.set_state(TxStates.description)
    await message.answer("Введите описание (или '-' чтобы пропустить):", reply_markup=cancel_kb())

@dp.message(lambda m: True, state=TxStates.description)
async def tx_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    desc = message.text.strip()
    if desc == "-":
        desc = None
    user_id = await get_or_create_user(message.from_user.id)
    await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, data["amount"], data["category"], desc)
    await save_message_context(user_id, "system", f"Добавлена транзакция: {data['amount']} {data['category']} {desc}")
    await message.answer("Транзакция добавлена ✅", reply_markup=main_menu_kb())
    await state.clear()

# Goals menu
@dp.callback_query(lambda c: c.data == "menu_goals")
async def cb_menu_goals(c: types.CallbackQuery):
    await c.message.answer("Управление целями: нажмите /goal чтобы добавить новую цель.", reply_markup=cancel_kb())
    await c.answer()

@dp.message(Command("goal"))
async def cmd_goal_start(m: types.Message, state: FSMContext):
    await state.set_state(GoalStates.target)
    await m.answer("Введите сумму цели:", reply_markup=cancel_kb())

@dp.message(lambda m: True, state=GoalStates.target)
async def goal_target(m: types.Message, state: FSMContext):
    try:
        t = parse_amount_token(m.text.strip())
    except Exception:
        await m.answer("Неверный формат суммы.", reply_markup=cancel_kb())
        return
    await state.update_data(target=t)
    await state.set_state(GoalStates.title)
    await m.answer("Название цели:", reply_markup=cancel_kb())

@dp.message(lambda m: True, state=GoalStates.title)
async def goal_title(m: types.Message, state: FSMContext):
    d = await state.get_data()
    user_id = await get_or_create_user(m.from_user.id)
    await db.execute("INSERT INTO goals (user_id, target, current, title, created_at) VALUES ($1,$2,0,$3,NOW())",
                     user_id, d["target"], m.text.strip())
    await save_message_context(user_id, "system", f"Создана цель: {m.text.strip()} {d['target']} ₽")
    await m.answer("Цель добавлена ✅", reply_markup=main_menu_kb())
    await state.clear()

# -----------------------
# Quick free-text parsing: if user sends "-2500 кофе" etc.
# -----------------------
@dp.message()
async def catch_all(message: types.Message):
    text = message.text or ""
    # ignore commands (they have handlers)
    if text.startswith("/"):
        return
    # try parse like "-2500 кофе"
    parsed = None
    try:
        # find first number token
        m = re.search(r"([+-]?\d[\d\s\.,]*[a-zA-Zа-яА-ЯкКмМлLn%]*)", text)
        if m:
            token = m.group(1)
            amt = parse_amount_token(token)
            # description is rest
            desc = (text[:m.start()] + " " + text[m.end():]).strip()
            parsed = (amt, None, desc)
    except Exception:
        parsed = None

    if parsed:
        amount, category, description = parsed
        # store pending and ask confirm
        pending_tx[message.from_user.id] = {"amount": amount, "category": category, "description": description}
        await message.answer(f"Найдено: {amount}₽ | {category or '—'} | {description or ''}\nПодтвердить?", reply_markup=confirm_kb)
        return

    # otherwise treat as AI assistant query (always-on summarization)
    user_id = await get_or_create_user(message.from_user.id)
    await message.answer("Запрашиваю ответ у AI...")
    resp = await generate_ai_reply(user_id, text)
    await message.answer(resp)

# confirm/cancel pending tx
@dp.callback_query(lambda c: c.data == "confirm_tx")
async def cb_confirm_tx(c: types.CallbackQuery):
    data = pending_tx.pop(c.from_user.id, None)
    if not data:
        await c.answer("Нет ожидающей транзакции", show_alert=True)
        return
    user_id = await get_or_create_user(c.from_user.id)
    cat = data.get("category")
    await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())",
                     user_id, data["amount"], cat, data.get("description"))
    await save_message_context(user_id, "system", f"Добавлена транзакция: {data['amount']} {cat} {data.get('description')}")
    await c.message.edit_text("Транзакция добавлена ✅")
    await c.answer()

@dp.callback_query(lambda c: c.data == "cancel_tx")
async def cb_cancel_tx(c: types.CallbackQuery):
    pending_tx.pop(c.from_user.id, None)
    await c.message.edit_text("Операция отменена.")
    await c.answer()

# -----------------------
# /consult command
# -----------------------
@dp.message(Command("consult"))
async def cmd_consult(m: types.Message):
    user_id = await get_or_create_user(m.from_user.id)
    await m.answer("Готовлю краткую консультацию...")
    resp = await generate_consultation(user_id)
    await m.answer(resp)

# -----------------------
# Chart command (expenses + assets vs liabilities)
# -----------------------
@dp.message(Command("chart"))
async def cmd_chart(m: types.Message):
    user_id = await get_or_create_user(m.from_user.id)
    since = datetime.utcnow() - timedelta(days=30)
    rows = await db.fetch("SELECT amount, created_at FROM transactions WHERE user_id=$1 AND created_at >= $2 ORDER BY created_at ASC", user_id, since)
    assets = await db.fetch("SELECT title, amount FROM assets WHERE user_id=$1", user_id)
    liabs = await db.fetch("SELECT title, amount FROM liabilities WHERE user_id=$1", user_id)

    if not rows and not assets and not liabs:
        await m.answer("Нет данных для графика.")
        return

    # expenses time series
    daily = {}
    for r in rows:
        day = r["created_at"].date().isoformat()
        daily[day] = daily.get(day, 0) + float(r["amount"])
    dates = sorted(daily.keys())
    values = [daily[d] for d in dates]

    # create figure with two subplots: time series + assets/liab bar
    fig, axs = plt.subplots(2, 1, figsize=(8, 8))
    if dates:
        axs[0].plot(dates, values, marker='o')
        axs[0].set_title("Динамика транзакций (30 дней)")
        axs[0].tick_params(axis='x', rotation=45)
    else:
        axs[0].text(0.5, 0.5, "Нет транзакций", ha='center')

    # assets vs liabilities
    labels = []
    vals = []
    for a in assets:
        labels.append(a["title"] or "asset")
        vals.append(float(a["amount"]))
    for l in liabs:
        labels.append(l["title"] or "liab")
        vals.append(-float(l["amount"]))  # show debts as negative to visualize
    if labels:
        axs[1].barh(labels, vals)
        axs[1].set_title("Активы (полож.) и долги (отриц.)")
    else:
        axs[1].text(0.5, 0.5, "Нет активов/долгов", ha='center')

    plt.tight_layout()
    fname = f"{CHART_DIR}/chart_{user_id}_{int(datetime.utcnow().timestamp())}.png"
    plt.savefig(fname)
    plt.close(fig)
    await m.answer_photo(types.FSInputFile(fname), caption="График аккаунта (30 дней)")
    try:
        os.remove(fname)
    except Exception:
        pass

# -----------------------
# EXPORT handler (callback or command)
# -----------------------
async def handle_export_callback(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    rows = await db.fetch("SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at ASC", user_id)
    if not rows:
        await c.message.answer("Нет транзакций для экспорта.")
        return
    fd, path = tempfile.mkstemp(prefix=f"finances_{user_id}_", suffix=".csv")
    os.close(fd)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["amount", "category", "description", "created_at"])
        for r in rows:
            w.writerow([r["amount"], r["category"] or "", r["description"] or "", r["created_at"].isoformat() if r["created_at"] else ""])
    await c.message.answer_document(types.FSInputFile(path), caption="Экспорт транзакций (CSV)")
    try:
        os.remove(path)
    except Exception:
        pass

# -----------------------
# Weekly report (APScheduler)
# -----------------------
async def build_weekly_report_for_user(user_id: int) -> str:
    finance = await analyze_user_finances_text(user_id)
    # totals
    since7 = datetime.utcnow() - timedelta(days=7)
    rows7 = await db.fetch("SELECT amount FROM transactions WHERE user_id=$1 AND created_at >= $2", user_id, since7)
    total7 = sum(r["amount"] for r in rows7) if rows7 else 0
    text = f"Еженедельный отчёт\nЗа 7 дней: {total7}₽\n\n{finance[:3000]}"
    return text

async def weekly_job():
    users = await db.fetch("SELECT id, tg_id FROM users")
    for u in users:
        try:
            report = await build_weekly_report_for_user(u["id"])
            await bot.send_message(u["tg_id"], report)
        except Exception:
            pass

# -----------------------
# STARTUP / SCHEDULER
# -----------------------
async def on_startup():
    global db
    db = await create_db_pool()
    # schedule weekly job: every Monday 09:00 UTC (adjust if needed)
    scheduler.add_job(weekly_job, "cron", day_of_week="mon", hour=9, minute=0, id="weekly_report")
    scheduler.start()
    print("DB connected, scheduler started.")

# attach startup handler to dispatcher and run polling properly
dp.startup.register(on_startup)

# -----------------------
# RUN
# -----------------------
if __name__ == "__main__":
    try:
        asyncio.run(dp.start_polling(bot))
    except KeyboardInterrupt:
        print("Exit")
