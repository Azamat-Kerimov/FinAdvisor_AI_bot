#!/usr/bin/env python3
# coding: utf-8

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

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from dotenv import load_dotenv

load_dotenv()

# -------------------- CONFIG --------------------
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

CHART_TMP = "/tmp"
os.makedirs(CHART_TMP, exist_ok=True)

# -------------------- INIT --------------------
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db: asyncpg.pool.Pool = None
scheduler = AsyncIOScheduler()

# default canonical categories - expand later
CANONICAL_CATEGORIES = [
    "Такси", "Еда", "Продукты", "Развлечения", "Кафе", "Покупки", "Коммуналка", "Аренда", "Зарплата",
    "Кредиты", "Транспорт", "Медицина", "Образование", "Подарки", "Инвестиции"
]

# inline buttons
main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить транзакцию", callback_data="menu_add"),
     InlineKeyboardButton(text="💰 Счета/Долги", callback_data="menu_assets")],
    [InlineKeyboardButton(text="🎯 Мои цели", callback_data="menu_goals"),
     InlineKeyboardButton(text="📈 Графики/Отчёт", callback_data="menu_charts")],
    [InlineKeyboardButton(text="📝 Консультация (AI)", callback_data="menu_consult"),
     InlineKeyboardButton(text="📤 Экспорт CSV", callback_data="menu_export")]
])

cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Отмена ❌", callback_data="cancel")]
])

confirm_category_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да, принять", callback_data="confirm_cat"),
     InlineKeyboardButton(text="Нет, использовать как есть", callback_data="decline_cat")]
])

confirm_tx_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Подтвердить ✅", callback_data="confirm_tx"),
     InlineKeyboardButton(text="Отмена ❌", callback_data="cancel")]
])

# -------------------- HELPERS --------------------
def basic_auth_header(client_id, client_secret):
    raw = f"{client_id}:{client_secret}"
    return base64.b64encode(raw.encode()).decode()

def normalize_category_input(cat_input: str):
    """Hybrid fuzzy: try close match in CANONICAL_CATEGORIES, threshold; else capitalise."""
    if not cat_input:
        return None, False
    s = cat_input.strip()
    # direct capitalization
    candidate = s.capitalize()
    # fuzzy matching with difflib
    match = difflib.get_close_matches(s.lower(), [c.lower() for c in CANONICAL_CATEGORIES], n=1, cutoff=0.7)
    if match:
        # find original canonical with same lowercase
        canon = next((c for c in CANONICAL_CATEGORIES if c.lower() == match[0]), None)
        if canon:
            return canon, True
    # fallback: capitalise each word
    return " ".join([w.capitalize() for w in s.split()]), False

def format_datetime(dt):
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")

# -------------------- GIGACHAT --------------------
def get_gigachat_token_sync():
    headers = {
        "Authorization": f"Basic {basic_auth_header(GIGACHAT_CLIENT_ID, GIGACHAT_CLIENT_SECRET)}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4())
    }
    data = {"scope": GIGACHAT_SCOPE}
    r = requests.post(GIGACHAT_AUTH_URL, headers=headers, data=data, verify=False, timeout=20)
    r.raise_for_status()
    return r.json().get("access_token")

def gigachat_request_sync(messages):
    token = get_gigachat_token_sync()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {"model": GIGACHAT_MODEL, "messages": messages, "temperature": 0.3}
    r = requests.post(GIGACHAT_API_URL, headers=headers, json=payload, verify=False, timeout=30)
    r.raise_for_status()
    j = r.json()
    return j["choices"][0]["message"]["content"]

async def gigachat_request(messages):
    # wrapper to not block event loop - run in thread
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, gigachat_request_sync, messages)

# -------------------- DB --------------------
async def create_db_pool():
    return await asyncpg.create_pool(user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT)

# -------------------- CONTEXT --------------------
async def save_context(user_id: int, role: str, content: str):
    await db.execute("INSERT INTO ai_context (user_id, role, content, created_at) VALUES ($1,$2,$3,NOW())", user_id, role, content)

async def get_context_messages(user_id: int):
    rows = await db.fetch("SELECT role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC", user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

# -------------------- FINANCE ANALYSIS --------------------
async def finance_snapshot_text(user_id: int, limit=100):
    rows = await db.fetch("SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2", user_id, limit)
    if not rows:
        return "У пользователя нет транзакций."
    lines = []
    for r in rows:
        cat = (r["category"] or "").capitalize()
        lines.append(f"{r['amount']}₽ | {cat} | {format_datetime(r['created_at'])}")
    # goals
    goals = await db.fetch("SELECT title, target, current FROM goals WHERE user_id=$1", user_id)
    if goals:
        lines.append("\nЦели:")
        for g in goals:
            lines.append(f"{g['title']}: {g['current']}/{g['target']}")
    # assets/debts
    assets = await db.fetch("SELECT name, amount, type FROM assets WHERE user_id=$1", user_id)
    if assets:
        lines.append("\nСчета/Активы:")
        for a in assets:
            lines.append(f"{a['name']} ({a['type']}): {a['amount']}")
    return "\n".join(lines)

# -------------------- AI reply --------------------
async def generate_ai_reply(user_id: int, user_text: str):
    # save user message
    await save_context(user_id, "user", user_text)
    # gather context
    context = await get_context_messages(user_id)
    finance_text = await finance_snapshot_text(user_id)
    system_prompt = f"Ты финансовый ассистент. Используй историю диалога и данные:\n{finance_text}\nОтвечай кратко и полезно."
    messages = [{"role":"system","content":system_prompt}] + context + [{"role":"user","content":user_text}]
    try:
        ans = await gigachat_request(messages)
    except Exception as e:
        print("GigaChat error:", e)
        ans = "Извините, AI временно недоступен."
    await save_context(user_id, "assistant", ans)
    return ans

# -------------------- TRANSACTIONS HELPERS --------------------
def parse_amount_token(token: str):
    # simple parse: allow commas/dots and k/m suffix
    s = token.strip().lower().replace(" ", "")
    multiplier = 1
    if s.endswith("k") or s.endswith("к"):
        multiplier = 1000
        s = s[:-1]
    if s.endswith("m") or s.endswith("м") or s.endswith("млн"):
        multiplier = 1_000_000
        # drop letters
        s = ''.join([c for c in s if (c.isdigit() or c == '.' or c == ',')])
    s = s.replace(",", ".")
    try:
        v = float(s)
    except:
        raise ValueError("invalid amount")
    return int(round(v * multiplier))

# quick free-text parser: finds first numeric token
import re
def smart_parse_free_text(text: str):
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
    # remove token from text
    left = (text[:m.start()] + " " + text[m.end():]).strip()
    return amount, left or None

# -------------------- FSM STATES --------------------
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

# -------------------- USER HELPERS --------------------
async def get_or_create_user(tg_id: int):
    row = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]
    r = await db.fetchrow("INSERT INTO users (tg_id, created_at, summarization_enabled) VALUES ($1,NOW(),TRUE) RETURNING id", tg_id)
    return r["id"]

# -------------------- MENU HANDLERS --------------------
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await get_or_create_user(m.from_user.id)
    await m.answer(
        "Привет! Я FinAdvisor — твой финансовый помощник.\n\n"
        "Выбери действие в меню:",
        reply_markup=main_kb
    )

@dp.callback_query(F.data == "menu_add")
async def cb_menu_add(q: types.CallbackQuery):
    await q.message.answer("Отправь сумму и категорию в одной строке (пример: `-2500 кофе`) или нажми 'Добавить транзакцию' ниже.", reply_markup=cancel_kb)
    await q.answer()

@dp.callback_query(F.data == "menu_goals")
async def cb_menu_goals(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)
    rows = await db.fetch("SELECT id, title, target, current FROM goals WHERE user_id=$1", user_id)
    if not rows:
        await q.message.answer("Целей нет. Создать можно через /goal", reply_markup=main_kb)
    else:
        text = "Цели:\n"
        for r in rows:
            pct = int(round((r["current"] / r["target"] * 100) if r["target"] else 0))
            text += f"- {r['title']}: {r['current']}/{r['target']} ₽ ({pct}%)\n"
        await q.message.answer(text, reply_markup=main_kb)
    await q.answer()

@dp.callback_query(F.data == "menu_assets")
async def cb_menu_assets(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)
    rows = await db.fetch("SELECT id, name, amount, type FROM assets WHERE user_id=$1", user_id)
    if not rows:
        await q.message.answer("Счета/долги не найдены. Добавить можно через /add_asset", reply_markup=main_kb)
    else:
        text = "Счета/Активы:\n"
        for r in rows:
            text += f"- {r['name']} ({r['type']}): {r['amount']} ₽\n"
        await q.message.answer(text, reply_markup=main_kb)
    await q.answer()

@dp.callback_query(F.data == "menu_charts")
async def cb_menu_charts(q: types.CallbackQuery):
    await q.message.answer("Генерирую графики...", reply_markup=cancel_kb)
    await generate_and_send_combined_chart(q.message, q.from_user.id)
    await q.answer()

@dp.callback_query(F.data == "menu_consult")
async def cb_menu_consult(q: types.CallbackQuery):
    await q.message.answer("Готовлю короткий пошаговый план (консультацию) на основе ваших данных...")
    user_id = await get_or_create_user(q.from_user.id)
    # build prompt
    snapshot = await finance_snapshot_text(user_id= user_id if False else user_id)  # placeholder
    sys = "Ты — финансовый ассистент. Составь краткий пошаговый план (3-6 пунктов) для пользователя на основе данных ниже."
    messages = [{"role":"system","content":sys},{
        "role":"user","content": await finance_snapshot_text(user_id)
    }]
    try:
        ans = await gigachat_request(messages)
    except Exception as e:
        print("AI consult error:", e)
        ans = "Извините, AI временно недоступен."
    await q.message.answer(ans, reply_markup=main_kb)
    await q.answer()

@dp.callback_query(F.data == "menu_export")
async def cb_menu_export(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)
    rows = await db.fetch("SELECT id, amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at ASC", user_id)
    if not rows:
        await q.message.answer("Нет транзакций для экспорта.", reply_markup=main_kb)
        await q.answer()
        return
    fd, path = tempfile.mkstemp(prefix=f"finances_{user_id}_", suffix=".csv")
    os.close(fd)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id","amount","category","description","created_at"])
        for r in rows:
            writer.writerow([r["id"], r["amount"], r["category"] or "", r["description"] or "", format_datetime(r["created_at"])])
    await q.message.answer_document(types.FSInputFile(path), caption="Экспорт транзакций (CSV)")
    try:
        os.remove(path)
    except:
        pass
    await q.answer()

@dp.callback_query(F.data == "cancel")
async def cb_cancel(q: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await q.message.answer("Отменено. Возврат в меню.", reply_markup=main_kb)
    await q.answer()

# -------------------- ADD TRANSACTION FLOW --------------------
@dp.message()
async def catch_quick_add_or_chat(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    # if in FSM, route defaults
    current = await state.get_state()
    if current:
        return  # let FSM handlers manage

    # Try quick free-text transaction
    parsed = smart_parse_free_text(text)
    if parsed:
        amount, rest = parsed
        # rest may contain category/desc
        cat_guess = None
        desc = None
        if rest:
            # treat first word as category if short
            parts = rest.split()
            if parts:
                cat_guess, certain = normalize_category_input(parts[0])
                desc = rest
            else:
                cat_guess = None
        user_id = await get_or_create_user(message.from_user.id)
        # if we matched canonical with low confidence (certain False), ask confirm
        if cat_guess:
            # if cat_guess is canonical? normalize returns (canon, True/False)
            # We'll ask confirm only if canonical match was True (i.e. we changed)
            # Actually we want to ask if fuzzy matched (True means matched), but that's okay:
            # If fuzzy matched (True) — accept without asking; if False — ask.
            # Let's compute again properly:
            canon, matched = normalize_category_input(parts[0]) if rest else (None, False)
            if matched:
                # direct add
                await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())", user_id, amount, canon, desc)
                await save_context(user_id, "system", f"Добавлена транзакция: {amount} | {canon} | {desc}")
                await message.answer(f"Транзакция добавлена: {amount}₽ | {canon} | {desc}", reply_markup=main_kb)
                return
            else:
                # ask confirm
                await state.update_data(tmp_amount=amount, tmp_category=canon, tmp_desc=desc)
                await message.answer(f"Похоже вы имели в виду категорию «{canon}». Подтвердить?", reply_markup=confirm_category_kb)
                return
        else:
            # no category guess: start interactive flow
            await state.set_state(TxStates.waiting_amount)
            await message.answer("Не уверены в категории. Запускаю интерактивную запись.\nВведите сумму (пример: 2500):", reply_markup=cancel_kb)
            return

    # if not transaction - route to AI assistant
    user_id = await get_or_create_user(message.from_user.id)
    reply = await generate_ai_reply(user_id, text)
    await message.answer(reply)

@dp.callback_query(F.data == "confirm_cat")
async def cb_confirm_cat(q: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("tmp_amount")
    category = data.get("tmp_category")
    desc = data.get("tmp_desc")
    if not amount:
        await q.answer("Нечего подтверждать.", show_alert=True)
        return
    user_id = await get_or_create_user(q.from_user.id)
    await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())", user_id, amount, category, desc)
    await save_context(user_id, "system", f"Добавлена транзакция: {amount} | {category} | {desc}")
    await state.clear()
    await q.message.answer(f"Транзакция добавлена: {amount}₽ | {category} | {desc}", reply_markup=main_kb)
    await q.answer()

@dp.callback_query(F.data == "decline_cat")
async def cb_decline_cat(q: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("tmp_amount")
    desc = data.get("tmp_desc")
    # if decline - insert with original free-text category=desc first word
    # fallback: no insert, ask user for category
    await state.set_state(TxStates.waiting_category)
    await q.message.answer("Хорошо. Введите желаемую категорию вручную:", reply_markup=cancel_kb)
    await q.answer()

# FSM interactive add
@dp.message(TxStates.waiting_amount)
async def fsm_tx_amount(m: types.Message, state: FSMContext):
    txt = m.text.strip()
    try:
        amt = parse_amount_token(txt)
    except:
        await m.answer("Неверная сумма, попробуйте снова:", reply_markup=cancel_kb)
        return
    await state.update_data(amount=amt)
    await state.set_state(TxStates.waiting_category)
    await m.answer("Введите категорию:", reply_markup=cancel_kb)

@dp.message(TxStates.waiting_category)
async def fsm_tx_category(m: types.Message, state: FSMContext):
    cat_raw = m.text.strip()
    canon, matched = normalize_category_input(cat_raw)
    if not matched:
        # confirm with user
        await state.update_data(category=canon)
        await m.answer(f"Предлагаю категорию «{canon}». Подтверждаете?", reply_markup=confirm_category_kb)
        return
    await state.update_data(category=canon)
    await state.set_state(TxStates.waiting_desc)
    await m.answer("Введите описание (или '-' чтобы пропустить):", reply_markup=cancel_kb)

@dp.message(TxStates.waiting_desc)
async def fsm_tx_desc(m: types.Message, state: FSMContext):
    d = (m.text.strip() if m.text.strip() != "-" else None)
    data = await state.get_data()
    amount = data.get("amount")
    category = data.get("category")
    user_id = await get_or_create_user(m.from_user.id)
    await db.execute("INSERT INTO transactions (user_id, amount, category, description, created_at) VALUES ($1,$2,$3,$4,NOW())", user_id, amount, category, d)
    await save_context(user_id, "system", f"Добавлена транзакция: {amount} | {category} | {d}")
    await m.answer("Транзакция добавлена ✅", reply_markup=main_kb)
    await state.clear()

# -------------------- GOALS --------------------
@dp.message(Command("goal"))
async def cmd_goal_start(m: types.Message, state: FSMContext):
    await state.set_state(GoalStates.waiting_target)
    await m.answer("Введите сумму цели (пример: 100000):", reply_markup=cancel_kb)

@dp.message(GoalStates.waiting_target)
async def fsm_goal_target(m: types.Message, state: FSMContext):
    try:
        t = parse_amount_token(m.text.strip())
    except:
        await m.answer("Неверная сумма. Попробуйте снова:", reply_markup=cancel_kb)
        return
    await state.update_data(target=t)
    await state.set_state(GoalStates.waiting_title)
    await m.answer("Введите название цели:", reply_markup=cancel_kb)

@dp.message(GoalStates.waiting_title)
async def fsm_goal_title(m: types.Message, state: FSMContext):
    data = await state.get_data()
    title = m.text.strip()
    user_id = await get_or_create_user(m.from_user.id)
    await db.execute("INSERT INTO goals (user_id, target, current, title, created_at) VALUES ($1,$2,0,$3,NOW())", user_id, data["target"], title)
    await save_context(user_id, "system", f"Создана цель: {title} на {data['target']}")
    await m.answer("Цель добавлена ✅", reply_markup=main_kb)
    await state.clear()

# -------------------- ASSETS (accounts & debts) --------------------
@dp.message(Command("add_asset"))
async def cmd_add_asset_start(m: types.Message, state: FSMContext):
    await state.set_state(AssetStates.waiting_name)
    await m.answer("Введите название счёта/актива (пример: 'Тинькофф'):", reply_markup=cancel_kb)

@dp.message(AssetStates.waiting_name)
async def fsm_asset_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    await state.set_state(AssetStates.waiting_amount)
    await m.answer("Введите сумму (положительная для актива, отрицательная для долга):", reply_markup=cancel_kb)

@dp.message(AssetStates.waiting_amount)
async def fsm_asset_amount(m: types.Message, state: FSMContext):
    try:
        amt = parse_amount_token(m.text.strip())
    except:
        await m.answer("Неверная сумма. Попробуйте снова:", reply_markup=cancel_kb)
        return
    await state.update_data(amount=amt)
    await state.set_state(AssetStates.waiting_type)
    await m.answer("Введите тип: asset или debt (или нажмите 'asset'):", reply_markup=cancel_kb)

@dp.message(AssetStates.waiting_type)
async def fsm_asset_type(m: types.Message, state: FSMContext):
    t = m.text.strip().lower()
    if t not in ("asset", "debt"):
        t = "asset"
    data = await state.get_data()
    user_id = await get_or_create_user(m.from_user.id)
    await db.execute("INSERT INTO assets (user_id, name, amount, type, created_at) VALUES ($1,$2,$3,$4,NOW())", user_id, data["name"], data["amount"], t)
    await save_context(user_id, "system", f"Добавлен актив/долг: {data['name']} {data['amount']} ({t})")
    await m.answer("Записано ✅", reply_markup=main_kb)
    await state.clear()

# -------------------- GENERATE CHARTS --------------------
async def generate_and_send_combined_chart(message_or_obj, tg_user_id):
    # get user id
    user_id = await get_or_create_user(tg_user_id)
    # doughnut: expenses by category for current month
    start_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = await db.fetch("SELECT amount, category FROM transactions WHERE user_id=$1 AND created_at >= $2", user_id, start_month)
    cat_sums = {}
    for r in rows:
        cat = (r["category"] or "Прочее").capitalize()
        cat_sums[cat] = cat_sums.get(cat, 0) + float(r["amount"])
    labels = list(cat_sums.keys()) or ["Нет данных"]
    values = list(cat_sums.values()) or [1]

    # progress bars: goals vs assets total (sum of positive assets) used as "available funds"
    goals = await db.fetch("SELECT title, target, current FROM goals WHERE user_id=$1 ORDER BY created_at ASC", user_id)
    assets = await db.fetch("SELECT amount, type FROM assets WHERE user_id=$1", user_id)
    total_assets = sum([a["amount"] for a in assets if a["type"] == "asset"]) if assets else 0
    total_debts = sum([a["amount"] for a in assets if a["type"] == "debt"]) if assets else 0
    # We'll use "available" funds = total_assets - total_debts
    available = total_assets - total_debts

    # build figure with 2 subplots vertical
    fig = plt.figure(figsize=(8, 10))
    # doughnut
    ax1 = fig.add_subplot(2,1,1)
    wedges, texts, autotexts = ax1.pie(values, labels=labels, autopct=lambda pct: f"{int(round(pct))}%", startangle=90)
    # draw circle for doughnut
    centre_circle = plt.Circle((0,0),0.60,fc='white')
    ax1.add_artist(centre_circle)
    ax1.set_title("Траты по категориям (текущий месяц)")
    # add center text: total sum
    total_sum = sum(values)
    ax1.text(0,0, f"{int(round(total_sum))}₽", horizontalalignment='center', verticalalignment='center', fontsize=14, fontweight='bold')

    # progress bars for goals
    ax2 = fig.add_subplot(2,1,2)
    if goals:
        titles = [g["title"] for g in goals]
        targets = [g["target"] for g in goals]
        currents = [g["current"] for g in goals]
        # compute percents relative to target; if current >= target show complete
        percents = [int(round((c/t)*100)) if t>0 else 0 for c,t in zip(currents, targets)]
        y_pos = list(range(len(titles)))
        # bars: draw background grey, draw green overlay up to percent
        for i, (title, pct) in enumerate(zip(titles, percents)):
            # background bar
            ax2.barh(i, 100, color="#d3d3d3", edgecolor="none", height=0.6)
            # filled part
            ax2.barh(i, pct, color="#2ca02c", edgecolor="none", height=0.6)
            # text labels on right
            label = f"{title} — {currents[i]}/{targets[i]} ₽ ({pct}%)"
            ax2.text(102, i, label, va='center', fontsize=9)
            # mark completed
            if currents[i] >= targets[i]:
                ax2.text(pct/2, i, "✓", va='center', ha='center', color='white', fontsize=12, fontweight='bold')
        ax2.set_yticks(y_pos)
        ax2.set_yticklabels([])  # we printed labels to the right
        ax2.set_xlim(0, 110)
        ax2.set_xlabel("Прогресс целей (%)")
        ax2.set_title(f"Прогресс по целям — доступно {int(available)}₽")
    else:
        ax2.text(0.5, 0.5, "Цели не заданы", ha='center', va='center')
        ax2.axis('off')

    plt.tight_layout()
    fname = f"{CHART_TMP}/combined_{user_id}_{int(datetime.utcnow().timestamp())}.png"
    fig.savefig(fname)
    plt.close(fig)

    # send depending on object type
    if isinstance(message_or_obj, types.Message):
        await message_or_obj.answer_photo(FSInputFile(fname), caption="Графики: траты и прогресс по целям", reply_markup=main_kb)
    else:
        # callback_query or other
        await bot.send_photo(message_or_obj.chat.id, FSInputFile(fname), caption="Графики: траты и прогресс по целям")
    try:
        os.remove(fname)
    except:
        pass

# -------------------- TRANSACTION TABLE IMAGE --------------------
async def build_and_send_transactions_table(chat_id: int, user_id: int, days=30):
    since = datetime.utcnow() - timedelta(days=days)
    rows = await db.fetch("SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 AND created_at >= $2 ORDER BY created_at DESC", user_id, since)
    if not rows:
        await bot.send_message(chat_id, "Нет транзакций за период.", reply_markup=main_kb)
        return
    # prepare table data
    headers = ["Сумма", "Категория", "Описание", "Дата/Время"]
    table = []
    for r in rows:
        amt = f"{int(r['amount'])}₽"
        cat = (r['category'] or "Прочее").capitalize()
        desc = (r['description'] or "")
        dt = format_datetime(r['created_at'])
        table.append([amt, cat, desc, dt])
    # build matplotlib table image
    fig, ax = plt.subplots(figsize=(8, max(2, 0.4*len(table) + 1)))
    ax.axis('off')
    # create table
    tbl = ax.table(cellText=table, colLabels=headers, loc='center', cellLoc='left')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.2)
    # style: light grey grid
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("#dcdcdc")
        cell.set_linewidth(0.5)
        if row == 0:
            cell.set_text_props(weight='bold')
            cell.set_facecolor("#f5f5f5")
    plt.tight_layout()
    fname = f"{CHART_TMP}/table_{user_id}_{int(datetime.utcnow().timestamp())}.png"
    fig.savefig(fname, dpi=150)
    plt.close(fig)
    await bot.send_photo(chat_id, FSInputFile(fname), caption=f"Транзакции за {days} дней", reply_markup=main_kb)
    try:
        os.remove(fname)
    except:
        pass

# -------------------- WEEKLY REPORT JOB --------------------
async def weekly_report_job():
    # run every monday 09:00 Europe/London
    users = await db.fetch("SELECT id, tg_id FROM users")
    for u in users:
        uid = u["id"]
        tg = u["tg_id"]
        # build text summary
        since = datetime.utcnow() - timedelta(days=7)
        rows = await db.fetch("SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 AND created_at >= $2 ORDER BY created_at DESC", uid, since)
        text = f"Еженедельный отчет (последние 7 дней):\n"
        if not rows:
            text += "Транзакций нет.\n"
        else:
            # simple totals
            total = sum([r["amount"] for r in rows])
            text += f"Всего: {int(total)}₽\n\n"
        # include table image
        await bot.send_message(tg, text)
        await build_and_send_transactions_table(tg, uid, days=7)
        # include combined chart
        await generate_and_send_combined_chart(types.SimpleNamespace(chat=types.SimpleNamespace(id=tg)), uid)

# -------------------- CONSULT COMMAND --------------------
@dp.message(Command("consult"))
async def cmd_consult(m: types.Message):
    user_id = await get_or_create_user(m.from_user.id)
    await m.answer("Готовлю краткий пошаговый план (3-6 шагов)...")
    snapshot = await finance_snapshot_text(user_id)
    system = "Ты — финансовый советник. Составь краткий, практичный план из 3-6 шагов для пользователя на основе данных ниже."
    messages = [{"role":"system","content":system},{"role":"user","content":snapshot}]
    try:
        ans = await gigachat_request(messages)
    except Exception as e:
        print("consult error:", e)
        ans = "AI недоступен."
    await m.answer(ans, reply_markup=main_kb)

# -------------------- STARTUP & SCHEDULER --------------------
async def on_startup():
    global db
    db = await create_db_pool()
    print("DB connected.")
    # create tables if not exist (minimal)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        tg_id BIGINT UNIQUE,
        created_at TIMESTAMP,
        summarization_enabled BOOLEAN DEFAULT TRUE
    );
    """)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        user_id INT REFERENCES users(id),
        amount NUMERIC,
        category TEXT,
        description TEXT,
        created_at TIMESTAMP
    );
    """)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id SERIAL PRIMARY KEY,
        user_id INT REFERENCES users(id),
        target NUMERIC,
        current NUMERIC DEFAULT 0,
        title TEXT,
        created_at TIMESTAMP
    );
    """)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id SERIAL PRIMARY KEY,
        user_id INT REFERENCES users(id),
        name TEXT,
        amount NUMERIC,
        type TEXT,
        created_at TIMESTAMP
    );
    """)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS ai_context (
        id SERIAL PRIMARY KEY,
        user_id INT,
        role TEXT,
        content TEXT,
        created_at TIMESTAMP
    );
    """)
    # ai_cache optional
    await db.execute("""
    CREATE TABLE IF NOT EXISTS ai_cache (
        id SERIAL PRIMARY KEY,
        user_id INT,
        input_hash TEXT,
        answer TEXT,
        created_at TIMESTAMP
    );
    """)
    # start scheduler
    tz = ZoneInfo("Europe/London")
    scheduler.add_job(weekly_report_job, "cron", day_of_week="mon", hour=9, minute=0, timezone=tz)
    scheduler.start()
    print("Scheduler started.")

# -------------------- RUN --------------------
if __name__ == "__main__":
    import signal
    loop = asyncio.get_event_loop()
    loop.create_task(on_startup())
    try:
        asyncio.run(dp.start_polling(bot))
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down")
