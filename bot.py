#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FinAdvisor - bot.py
Исправленная и рабочая версия под aiogram 3.x (без зависимостей на aiogram.fsm.filters)
- ai-context в PostgreSQL (таблица ai_context)
- ai-cache (таблица ai_cache)
- assets, liabilities
- transactions, goals, users
- интеграция с GigaChat (OAuth + chat completions)
- APScheduler - еженедельный отчёт
- FSM с кнопкой Отмена (универсальная маршрутизация состояний)
- команда /consult и кнопка "💡 Консультация"
- всегда включённая автосуммаризация контекста
- кеширование ответов AI
"""

import os
import asyncio
import asyncpg
import hashlib
import json
import tempfile
import uuid
import base64
from datetime import datetime, timedelta
from typing import Optional

import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

load_dotenv()

# ----------------------------
# Config from .env
# ----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))

# GigaChat OAuth details (as in your working test)
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE")
GIGACHAT_AUTH_URL = os.getenv("GIGACHAT_AUTH_URL")
GIGACHAT_API_URL = os.getenv("GIGACHAT_API_URL")
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat:2.0.28.2")

# ----------------------------
# Globals
# ----------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db: Optional[asyncpg.pool.Pool] = None
scheduler = AsyncIOScheduler()

# temp dir for charts
TMP_DIR = "/tmp"
os.makedirs(TMP_DIR, exist_ok=True)

# ----------------------------
# Keyboards
# ----------------------------
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить транзакцию", callback_data="menu_add_tx"),
         InlineKeyboardButton(text="💼 Управление капиталом", callback_data="menu_capital")],
        [InlineKeyboardButton(text="🎯 Мои цели", callback_data="menu_goals"),
         InlineKeyboardButton(text="💡 Консультация", callback_data="menu_consult")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="menu_stats"),
         InlineKeyboardButton(text="📈 График", callback_data="menu_chart")],
        [InlineKeyboardButton(text="📁 Экспорт CSV", callback_data="menu_export")]
    ])

cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]
])

confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Подтвердить ✅", callback_data="confirm_tx"),
        InlineKeyboardButton(text="Отмена ❌", callback_data="cancel_tx")
    ]
])

capital_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить актив", callback_data="cap_add_asset"),
     InlineKeyboardButton(text="➖ Добавить долг", callback_data="cap_add_liability")],
    [InlineKeyboardButton(text="📋 Показать активы/долги", callback_data="cap_show"),
     InlineKeyboardButton(text="↩️ Назад", callback_data="menu_back")]
])

# ----------------------------
# Helper: DB pool
# ----------------------------
async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT, min_size=1, max_size=6
    )

# ----------------------------
# GigaChat helpers (OAuth + request)
# ----------------------------
async def get_gigachat_token():
    """
    Request access token (client_credentials).
    Use async httpx to avoid blocking.
    """
    auth_str = f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}"
    b64 = base64.b64encode(auth_str.encode()).decode()
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
        return r.json().get("access_token")

async def gigachat_request(messages):
    """
    messages: list of {"role":..., "content":...}
    """
    token = await get_gigachat_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GIGACHAT_MODEL,
        "messages": messages,
        "temperature": 0.3
    }
    async with httpx.AsyncClient(verify=False, timeout=40.0) as client:
        r = await client.post(GIGACHAT_API_URL, headers=headers, json=payload)
        r.raise_for_status()
        j = r.json()
        if "choices" in j and j["choices"]:
            return j["choices"][0]["message"]["content"]
        # fallback whole json
        return json.dumps(j, ensure_ascii=False)

# ----------------------------
# AI cache (uses ai_cache table)
# ----------------------------
def _hash_input(user_message: str, finance_snapshot: str) -> str:
    h = hashlib.sha256((user_message.strip().lower() + "\n" + finance_snapshot).encode("utf-8"))
    return h.hexdigest()

async def get_cached_ai_reply(user_id: int, user_message: str, finance_snapshot: str):
    h = _hash_input(user_message, finance_snapshot)
    row = await db.fetchrow("SELECT answer FROM ai_cache WHERE user_id=$1 AND input_hash=$2 ORDER BY created_at DESC LIMIT 1", user_id, h)
    return row["answer"] if row else None

async def save_ai_cache(user_id: int, user_message: str, finance_snapshot: str, ai_answer: str):
    h = _hash_input(user_message, finance_snapshot)
    await db.execute("INSERT INTO ai_cache (user_id, input_hash, answer, created_at) VALUES ($1,$2,$3,NOW())", user_id, h, ai_answer)

# ----------------------------
# ai_context helpers
# ----------------------------
async def save_message(user_id: int, role: str, content: str):
    await db.execute("INSERT INTO ai_context (user_id, role, content, created_at) VALUES ($1,$2,$3,NOW())", user_id, role, content)

async def get_full_context(user_id: int):
    rows = await db.fetch("SELECT role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC", user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

# auto-summarization: always enabled (no toggle)
CONTEXT_SUMMARY_THRESHOLD = 800
CONTEXT_TRIM_TO = 300

async def maybe_summarize_context(user_id: int):
    r = await db.fetchrow("SELECT count(*)::int as c FROM ai_context WHERE user_id=$1", user_id)
    if not r:
        return
    cnt = r["c"]
    if cnt <= CONTEXT_SUMMARY_THRESHOLD:
        return
    rows = await db.fetch("SELECT id, role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC LIMIT $2", user_id, cnt - CONTEXT_TRIM_TO)
    text = "\n".join([f"{rr['role']}: {rr['content']}" for rr in rows])
    system = {"role":"system","content":"Сделай короткую (2-3 предложения) консолидированную сводку ключевых финансовых моментов и рекомендаций."}
    try:
        summary = await gigachat_request([system, {"role":"user","content":text}])
        await save_message(user_id, "system", f"SUMMARY: {summary}")
        ids = [r["id"] for r in rows]
        await db.execute("DELETE FROM ai_context WHERE id = ANY($1::int[])", ids)
    except Exception as e:
        print("summarize failed:", e)

# ----------------------------
# Finance analysis
# ----------------------------
MAX_TX_FOR_ANALYSIS = 200

async def analyze_user_finances_text(user_id: int) -> str:
    rows = await db.fetch("SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2", user_id, MAX_TX_FOR_ANALYSIS)
    if not rows:
        return "У пользователя нет транзакций."
    s = "Последние транзакции:\n"
    for r in rows:
        ts = r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else ""
        s += f"- {r['amount']}₽ | {r.get('category') or '-'} | {r.get('description') or ''} | {ts}\n"
    goals = await db.fetch("SELECT title, target, current, created_at FROM goals WHERE user_id=$1", user_id)
    if goals:
        s += "\nЦели:\n"
        for g in goals:
            s += f"- {g.get('title','Цель')}: {g['current']}/{g['target']} ₽\n"
    assets = await db.fetch("SELECT title, amount, type FROM assets WHERE user_id=$1", user_id)
    if assets:
        total_assets = sum([a["amount"] for a in assets])
        s += f"\nАктивы (итого {total_assets}₽):\n"
        for a in assets:
            s += f"- {a['title']} ({a['type']}): {a['amount']}₽\n"
    liabs = await db.fetch("SELECT title, amount, type FROM liabilities WHERE user_id=$1", user_id)
    if liabs:
        total_liabs = sum([l["amount"] for l in liabs])
        s += f"\nДолги (итого {total_liabs}₽):\n"
        for l in liabs:
            s += f"- {l['title']} ({l['type']}): {l['amount']}₽\n"
    total_assets = sum([a["amount"] for a in assets]) if assets else 0
    total_liabs = sum([l["amount"] for l in liabs]) if liabs else 0
    s += f"\nЧистый капитал: {total_assets - total_liabs}₽\n"
    return s

# ----------------------------
# AI answer generation for general messages (assistant mode)
# ----------------------------
async def generate_ai_reply(user_id: int, user_message: str) -> str:
    await save_message(user_id, "user", user_message)
    asyncio.create_task(maybe_summarize_context(user_id))
    finance_snapshot = await analyze_user_finances_text(user_id)
    cached = await get_cached_ai_reply(user_id, user_message, finance_snapshot)
    if cached:
        await save_message(user_id, "assistant", cached)
        return cached
    context = await get_full_context(user_id)
    system_prompt = (
        "Ты — профессиональный финансовый помощник. Используй историю диалога, транзакции, цели, "
        "активы и долги пользователя. Предоставь полезный, практический и краткий ответ."
    )
    messages = [{"role":"system","content":system_prompt}] + context + [{"role":"user","content":user_message}]
    try:
        ai_answer = await gigachat_request(messages)
    except Exception as e:
        print("gigachat error:", e)
        return "Извините, AI временно недоступен. Попробуйте позже."
    await save_message(user_id, "assistant", ai_answer)
    await save_ai_cache(user_id, user_message, finance_snapshot, ai_answer)
    return ai_answer

# ----------------------------
# Consultation command: /consult and menu_consult
# Short actionable step-by-step recommendations
# ----------------------------
async def generate_consultation(user_id: int) -> str:
    finance_snapshot = await analyze_user_finances_text(user_id)
    system_prompt = (
        "Ты — финансовый консультант. На основе данных пользователя (транзакции, цели, активы, долги) "
        "составь краткий практический план из 4 шагов: что сделать в ближайший месяц, что в ближайшие 6 месяцев, "
        "как улучшить бюджет и какие шаги для резервного фонда. Формат: нумерованный список."
    )
    messages = [
        {"role":"system","content":system_prompt},
        {"role":"user","content":finance_snapshot}
    ]
    try:
        answer = await gigachat_request(messages)
    except Exception as e:
        print("consult gigachat error:", e)
        return "Извините, AI временно недоступен."
    await save_message(user_id, "assistant", f"Consultation generated")
    await save_ai_cache(user_id, "CONSULT_REQUEST", finance_snapshot, answer)
    return answer

# ----------------------------
# FSMs for tx / goal / asset / liability
# ----------------------------
class TXStates(StatesGroup):
    amount = State()
    category = State()
    description = State()

class GOALStates(StatesGroup):
    target = State()
    title = State()

class AssetStates(StatesGroup):
    amount = State()
    type = State()
    title = State()

class LiabilityStates(StatesGroup):
    amount = State()
    monthly_payment = State()
    type = State()
    title = State()

# ----------------------------
# Utils: create chart (expenses pie) and net worth bar
# ----------------------------
async def create_expense_pie(user_id: int, days: int = 30):
    since = datetime.utcnow() - timedelta(days=days)
    rows = await db.fetch("SELECT amount, category FROM transactions WHERE user_id=$1 AND created_at >= $2", user_id, since)
    if not rows:
        return None
    by_cat = {}
    for r in rows:
        cat = r["category"] or "—"
        by_cat[cat] = by_cat.get(cat, 0) + float(r["amount"])
    labels = list(by_cat.keys())
    sizes = list(by_cat.values())
    fname = f"{TMP_DIR}/pie_{user_id}_{int(datetime.utcnow().timestamp())}.png"
    plt.figure(figsize=(6,6))
    plt.pie(sizes, labels=labels, autopct='%1.1f%%')
    plt.title(f"Категории расходов ({days}дн)")
    plt.tight_layout()
    plt.savefig(fname)
    plt.close()
    return fname

async def create_networth_bar(user_id: int):
    assets = await db.fetch("SELECT title, amount FROM assets WHERE user_id=$1", user_id)
    liabs = await db.fetch("SELECT title, amount FROM liabilities WHERE user_id=$1", user_id)
    fname = f"{TMP_DIR}/net_{user_id}_{int(datetime.utcnow().timestamp())}.png"
    names = []
    values = []
    if assets:
        names += [f"A: {a['title']}" for a in assets]
        values += [float(a["amount"]) for a in assets]
    if liabs:
        names += [f"L: {l['title']}" for l in liabs]
        values += [-float(l["amount"]) for l in liabs]
    if not names:
        return None
    plt.figure(figsize=(8,4))
    plt.bar(range(len(values)), values)
    plt.xticks(range(len(values)), names, rotation=45, ha='right')
    plt.title("Активы (положительные) и долги (отрицательные)")
    plt.tight_layout()
    plt.savefig(fname)
    plt.close()
    return fname

# ----------------------------
# Utility: get_or_create_user (returns internal users.id)
# ----------------------------
async def get_or_create_user(tg_id: int) -> int:
    r = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
    if r:
        return r["id"]
    row = await db.fetchrow("INSERT INTO users (tg_id, username, created_at) VALUES ($1,$2,NOW()) RETURNING id", tg_id, None)
    return row["id"]

# ----------------------------
# Handlers - callback queries and commands
# ----------------------------
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    u = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", m.from_user.id)
    if not u:
        await db.execute("INSERT INTO users (tg_id, username, created_at) VALUES ($1,$2,NOW())", m.from_user.id, m.from_user.username)
    await m.answer(
        "Привет! Я FinAdvisor — твой финансовый помощник.\n"
        "Используй меню ниже или пиши сообщение.",
        reply_markup=main_menu_kb()
    )

@dp.callback_query(F.data == "menu_back")
async def cb_menu_back(c: types.CallbackQuery):
    await c.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
    await c.answer()

@dp.callback_query(F.data == "menu_add_tx")
async def cb_menu_add_tx(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(TXStates.amount)
    await c.message.answer("Введите сумму транзакции (положительная для дохода, отрицательная для расхода).", reply_markup=cancel_kb)
    await c.answer()

@dp.callback_query(F.data == "menu_goals")
async def cb_menu_goals(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    rows = await db.fetch("SELECT id, title, target, current, created_at FROM goals WHERE user_id=$1", user_id)
    if not rows:
        await c.message.answer("Целей нет. Нажми «🎯 Мои цели» и затем /goal, чтобы добавить.")
    else:
        text = "Твои цели:\n"
        for r in rows:
            pr = (r["current"] / r["target"] * 100) if r["target"] else 0
            text += f"- {r['title']}: {r['current']}/{r['target']} ₽ ({pr:.1f}%)\n"
        await c.message.answer(text)
    await c.answer()

@dp.callback_query(F.data == "menu_consult")
async def cb_menu_consult(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    await c.message.answer("Готовлю консультацию... (короткий план из шагов).")
    ans = await generate_consultation(user_id)
    await c.message.answer(ans)
    await c.answer()

@dp.message(Command("consult"))
async def cmd_consult(m: types.Message):
    user_id = await get_or_create_user(m.from_user.id)
    await m.answer("Готовлю консультацию...")
    ans = await generate_consultation(user_id)
    await m.answer(ans)

@dp.callback_query(F.data == "menu_capital")
async def cb_menu_capital(c: types.CallbackQuery):
    await c.message.edit_text("Управление капиталом", reply_markup=capital_kb)
    await c.answer()

@dp.callback_query(F.data == "cap_add_asset")
async def cb_cap_add_asset(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(AssetStates.amount)
    await c.message.answer("Введите сумму актива (например: 150000):", reply_markup=cancel_kb)
    await c.answer()

@dp.callback_query(F.data == "cap_add_liability")
async def cb_cap_add_liability(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(LiabilityStates.amount)
    await c.message.answer("Введите сумму долга (например: 70000):", reply_markup=cancel_kb)
    await c.answer()

@dp.callback_query(F.data == "cap_show")
async def cb_cap_show(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    assets = await db.fetch("SELECT title, amount, type FROM assets WHERE user_id=$1", user_id)
    liabs = await db.fetch("SELECT title, amount, type FROM liabilities WHERE user_id=$1", user_id)
    text = ""
    total_assets = sum(a["amount"] for a in assets) if assets else 0
    total_liabs = sum(l["amount"] for l in liabs) if liabs else 0
    text += f"Активы (итого {total_assets}₽):\n"
    for a in assets:
        text += f"- {a['title']} ({a['type']}): {a['amount']}₽\n"
    text += f"\nДолги (итого {total_liabs}₽):\n"
    for l in liabs:
        text += f"- {l['title']} ({l['type']}): {l['amount']}₽\n"
    text += f"\nЧистый капитал: {total_assets - total_liabs}₽"
    await c.message.answer(text)
    img = await create_networth_bar(user_id)
    if img:
        await c.message.answer_photo(types.FSInputFile(img))
        try:
            os.remove(img)
        except Exception:
            pass
    await c.answer()

@dp.callback_query(F.data == "menu_stats")
async def cb_stats(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    since = datetime.utcnow() - timedelta(days=30)
    rows = await db.fetch("SELECT amount, category, created_at FROM transactions WHERE user_id=$1 AND created_at >= $2 ORDER BY created_at ASC", user_id, since)
    if not rows:
        await c.message.answer("Нет транзакций за последние 30 дней.")
        await c.answer()
        return
    total = sum(r["amount"] for r in rows)
    by_cat = {}
    for r in rows:
        cat = r["category"] or "—"
        by_cat[cat] = by_cat.get(cat, 0) + float(r["amount"])
    text = f"Статистика (30 дн):\nВсего: {total}₽\n\nТоп по категориям:\n"
    for cat, val in sorted(by_cat.items(), key=lambda x: -abs(x[1]))[:10]:
        text += f"- {cat}: {val}₽\n"
    await c.message.answer(text)
    await c.answer()

@dp.callback_query(F.data == "menu_chart")
async def cb_chart(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    img = await create_expense_pie(user_id, days=30)
    if not img:
        await c.message.answer("Нет данных для графика.")
    else:
        await c.message.answer_photo(types.FSInputFile(img), caption="Пирог расходов за 30 дней")
        try:
            os.remove(img)
        except Exception:
            pass
    await c.answer()

@dp.callback_query(F.data == "menu_export")
async def cb_export(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    rows = await db.fetch("SELECT id, amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at ASC", user_id)
    if not rows:
        await c.message.answer("Нет транзакций для экспорта.")
        await c.answer()
        return
    fd, path = tempfile.mkstemp(prefix=f"finances_{user_id}_", suffix=".csv")
    os.close(fd)
    with open(path, "w", encoding="utf-8", newline="") as f:
        import csv
        writer = csv.writer(f)
        writer.writerow(["id","amount","category","description","created_at"])
        for r in rows:
            writer.writerow([r["id"], r["amount"], r["category"] or "", r["description"] or "", r["created_at"].isoformat() if r["created_at"] else ""])
    await c.message.answer_document(types.FSInputFile(path), caption="Экспорт транзакций (CSV)")
    try:
        os.remove(path)
    except Exception:
        pass
    await c.answer()

@dp.callback_query(F.data == "cancel_fsm")
async def cb_cancel_fsm(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.answer("Отменено.", reply_markup=main_menu_kb())
    await c.answer()

@dp.callback_query(F.data == "confirm_tx")
async def cb_confirm_tx(c: types.CallbackQuery):
    await c.answer("Используй меню для добавления транзакции (быстрая запись поддерживается в текстовом вводе).")

@dp.callback_query(F.data == "cancel_tx")
async def cb_cancel_tx(c: types.CallbackQuery):
    await c.message.edit_text("Отменено.", reply_markup=main_menu_kb())
    await c.answer()

# ----------------------------
# Unified FSM message router
# ----------------------------
async def handle_stateful_message(m: types.Message, state: FSMContext) -> bool:
    """
    Return True if message was handled as part of FSM, False otherwise.
    This avoids using StateFilter import which can be missing in some aiogram versions.
    """
    current = await state.get_state()
    if not current:
        return False

    # TX flow
    if current == TXStates.amount.state:
        text = (m.text or "").strip()
        if text.lower() in ("отмена", "cancel"):
            await state.clear()
            await m.answer("Отменено.", reply_markup=main_menu_kb())
            return True
        try:
            amount = float(text.replace(",", "."))
        except Exception:
            await m.answer("Неверная сумма. Введите цифру, например: -2500 или 1500")
            return True
        await state.update_data(amount=amount)
        await state.set_state(TXStates.category)
        await m.answer("Введите категорию (например: продукты, транспорт).", reply_markup=cancel_kb)
        return True

    if current == TXStates.category.state:
        text = (m.text or "").strip()
        if text.lower() in ("отмена", "cancel"):
            await state.clear()
            await m.answer("Отменено.", reply_markup=main_menu_kb())
            return True
        await state.update_data(category=text)
        await state.set_state(TXStates.description)
        await m.answer("Введите описание (или '-' для пропуска).", reply_markup=cancel_kb)
        return True

    if current == TXStates.description.state:
        text = (m.text or "").strip()
        if text.lower() in ("отмена", "cancel"):
            await state.clear()
            await m.answer("Отменено.", reply_markup=main_menu_kb())
            return True
        data = await state.get_data()
        amount = data.get("amount")
        category = data.get("category")
        description = None if text == "-" else text
        user_id = await get_or_create_user(m.from_user.id)
        await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())",
                         user_id, amount, category, description)
        await save_message(user_id, "system", f"Добавлена транзакция: {amount} | {category} | {description}")
        await m.answer("Транзакция добавлена ✅", reply_markup=main_menu_kb())
        await state.clear()
        return True

    # Goal flow
    if current == GOALStates.target.state:
        text = (m.text or "").strip()
        if text.lower() in ("отмена", "cancel"):
            await state.clear()
            await m.answer("Отменено.", reply_markup=main_menu_kb())
            return True
        try:
            target = float(text.replace(",", "."))
        except Exception:
            await m.answer("Неверный формат суммы.")
            return True
        await state.update_data(target=target)
        await state.set_state(GOALStates.title)
        await m.answer("Введите название цели.", reply_markup=cancel_kb)
        return True

    if current == GOALStates.title.state:
        text = (m.text or "").strip()
        if text.lower() in ("отмена", "cancel"):
            await state.clear()
            await m.answer("Отменено.", reply_markup=main_menu_kb())
            return True
        data = await state.get_data()
        target = data.get("target")
        title = text
        user_id = await get_or_create_user(m.from_user.id)
        await db.execute("INSERT INTO goals (user_id, target, current, title, created_at) VALUES ($1,$2,0,$3,NOW())",
                         user_id, target, title)
        await save_message(user_id, "system", f"Создана цель: {title} на {target}₽")
        await m.answer("Цель добавлена ✅", reply_markup=main_menu_kb())
        await state.clear()
        return True

    # Asset flow
    if current == AssetStates.amount.state:
        text = (m.text or "").strip()
        if text.lower() in ("отмена", "cancel"):
            await state.clear()
            await m.answer("Отменено.", reply_markup=main_menu_kb())
            return True
        try:
            amount = float(text.replace(",", "."))
        except Exception:
            await m.answer("Неверная сумма.")
            return True
        await state.update_data(amount=amount)
        await state.set_state(AssetStates.type)
        await m.answer("Введите тип актива (bank, deposit, stocks, crypto, cash, other):", reply_markup=cancel_kb)
        return True

    if current == AssetStates.type.state:
        text = (m.text or "").strip()
        if text.lower() in ("отмена", "cancel"):
            await state.clear()
            await m.answer("Отменено.", reply_markup=main_menu_kb())
            return True
        await state.update_data(type=text)
        await state.set_state(AssetStates.title)
        await m.answer("Введите название (например: 'Сбер вклад'):", reply_markup=cancel_kb)
        return True

    if current == AssetStates.title.state:
        text = (m.text or "").strip()
        if text.lower() in ("отмена", "cancel"):
            await state.clear()
            await m.answer("Отменено.", reply_markup=main_menu_kb())
            return True
        data = await state.get_data()
        amount = data.get("amount")
        typ = data.get("type")
        title = text
        user_id = await get_or_create_user(m.from_user.id)
        await db.execute("INSERT INTO assets (user_id, amount, type, title, created_at) VALUES ($1,$2,$3,$4,NOW())",
                         user_id, amount, typ, title)
        await save_message(user_id, "system", f"Добавлен актив: {title} {amount}₽ ({typ})")
        await m.answer("Актив добавлен ✅", reply_markup=main_menu_kb())
        await state.clear()
        return True

    # Liability flow
    if current == LiabilityStates.amount.state:
        text = (m.text or "").strip()
        if text.lower() in ("отмена", "cancel"):
            await state.clear()
            await m.answer("Отменено.", reply_markup=main_menu_kb())
            return True
        try:
            amount = float(text.replace(",", "."))
        except Exception:
            await m.answer("Неверная сумма.")
            return True
        await state.update_data(amount=amount)
        await state.set_state(LiabilityStates.monthly_payment)
        await m.answer("Введите ежемесячный платёж (можно 0):", reply_markup=cancel_kb)
        return True

    if current == LiabilityStates.monthly_payment.state:
        text = (m.text or "").strip()
        try:
            monthly = float(text.replace(",", "."))
        except Exception:
            await m.answer("Неверный формат.")
            return True
        await state.update_data(monthly_payment=monthly)
        await state.set_state(LiabilityStates.type)
        await m.answer("Введите тип долга (loan, mortgage, credit_card, other):", reply_markup=cancel_kb)
        return True

    if current == LiabilityStates.type.state:
        text = (m.text or "").strip()
        await state.update_data(type=text)
        await state.set_state(LiabilityStates.title)
        await m.answer("Введите название долга (например: 'Кредитка Тинькофф'):", reply_markup=cancel_kb)
        return True

    if current == LiabilityStates.title.state:
        text = (m.text or "").strip()
        data = await state.get_data()
        amount = data.get("amount")
        monthly = data.get("monthly_payment")
        typ = data.get("type")
        title = text
        user_id = await get_or_create_user(m.from_user.id)
        await db.execute("INSERT INTO liabilities (user_id, amount, type, title, created_at) VALUES ($1,$2,$3,$4,NOW())",
                         user_id, amount, typ, title)
        await save_message(user_id, "system", f"Добавлен долг: {title} {amount}₽ ({typ}), платёж {monthly}₽")
        await m.answer("Долг добавлен ✅", reply_markup=main_menu_kb())
        await state.clear()
        return True

    # default: not handled
    return False

# ----------------------------
# Catch-all messages → FSM router or AI assistant
# ----------------------------
@dp.message(F.text & F.chat.type == "private")
async def catchall_private(m: types.Message, state: FSMContext):
    # First: if user is in any FSM state, route to unified handler
    handled = await handle_stateful_message(m, state)
    if handled:
        return

    # If message is a slash command, ignore (commands are handled separately)
    if m.text and m.text.startswith("/"):
        return

    # Otherwise: pass to AI assistant (generate reply)
    user_id = await get_or_create_user(m.from_user.id)
    await m.answer("Анализирую... (AI ответ может занять пару секунд)")
    reply = await generate_ai_reply(user_id, m.text or "")
    await m.answer(reply)

# ----------------------------
# Weekly report job
# ----------------------------
async def build_weekly_report_for_user(user_id: int) -> str:
    finance_data = await analyze_user_finances_text(user_id)
    assets = await db.fetch("SELECT amount FROM assets WHERE user_id=$1", user_id)
    liabs = await db.fetch("SELECT amount FROM liabilities WHERE user_id=$1", user_id)
    total_assets = sum(a["amount"] for a in assets) if assets else 0
    total_liabs = sum(l["amount"] for l in liabs) if liabs else 0
    net = total_assets - total_liabs
    text = f"Еженедельный отчёт\nАктивы: {total_assets}₽\nДолги: {total_liabs}₽\nЧистый капитал: {net}₽\n\nКраткая сводка:\n"
    text += finance_data[:2000]
    return text

async def weekly_report_job():
    users = await db.fetch("SELECT id, tg_id FROM users")
    for u in users:
        try:
            user_id = u["id"]
            tg_id = u["tg_id"]
            txt = await build_weekly_report_for_user(user_id)
            await bot.send_message(tg_id, txt)
            pie = await create_expense_pie(user_id)
            net = await create_networth_bar(user_id)
            if pie:
                await bot.send_photo(tg_id, types.FSInputFile(pie), caption="Пирог расходов")
                try: os.remove(pie)
                except: pass
            if net:
                await bot.send_photo(tg_id, types.FSInputFile(net), caption="Активы и долги")
                try: os.remove(net)
                except: pass
        except Exception as e:
            print("weekly_report error for user", u, e)

# ----------------------------
# Startup / scheduler
# ----------------------------
async def on_startup():
    global db
    db = await create_db_pool()
    # weekly Monday 09:00 UTC (adjust timezone as needed)
    scheduler.add_job(weekly_report_job, 'cron', day_of_week='mon', hour=9, minute=0, id='weekly_report')
    scheduler.start()
    print("DB connected. Scheduler started.")

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    try:
        # register startup
        dp.startup.register(on_startup)
        asyncio.run(dp.start_polling(bot))
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down")
