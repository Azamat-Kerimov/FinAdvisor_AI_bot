#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
import asyncpg
import hashlib
import json
import tempfile
import uuid
import base64
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import matplotlib.dates as mdates



load_dotenv()

# ----------------------------
# Config from .env
# ----------------------------
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


# ----------------------------
# Helper: DB pool
# ----------------------------
async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT, min_size=1, max_size=6
    )


# GigaChat helpers (OAuth + request)

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



# -----------------------------------------------------------------------------------------------------------------------
# Глобальные настройки
# -----------------------------------------------------------------------------------------------------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db: Optional[asyncpg.pool.Pool] = None
scheduler = AsyncIOScheduler()

# temp dir for charts
TMP_DIR = "/tmp"
os.makedirs(TMP_DIR, exist_ok=True)


now_moscow = datetime.now(ZoneInfo("Europe/Moscow"))

now = datetime.now()

# Формат чисел
def format_amount(amount: float) -> str:
    return f"{int(amount):,}".replace(",", " ") + " ₽"

# Клавиатура отмены
cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="↩️ Назад", callback_data="cancel_fsm")]
])

# Utility: get_or_create_user (returns internal users.id)

async def get_or_create_user(tg_id: int) -> int:
    r = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
    if r:
        return r["id"]
    row = await db.fetchrow("INSERT INTO users (tg_id, username, created_at) VALUES ($1,$2,NOW()) RETURNING id", tg_id, None)
    return row["id"]

# Словари с эмодзи для категорий доходов и расходов
income_emojis = {
    "Заработная плата": "💼",
    "Дивиденды и купоны": "💰",
    "Прочие доходы": "🪙",
}

expense_emojis = {
    "Аренда жилья": "🏠",
    "Коммунальные платежи": "💡",
    "Рестораны и кафе": "🍽️",
    "Супермаркеты": "🛒",
    "Отдых и развлечения": "🎉",
    "Транспорт": "🚗",
    "Здоровье и красота": "💊",
    "Одежда и аксессуары": "👗",
    "Кредиты и ипотека": "🏦",
    "Прочие расходы": "📦",
}

CATEGORY_EMOJI = {**income_emojis, **expense_emojis}

# Словари с эмодзи для категорий активов и пассивов
assets_emojis = {
    "Карта и наличка": "💵💳",
    "Депозиты": "🏦",
    "Акции": "📈",
    "Криптовалюта": "🎰",
    "Недвижмость": "🏢",
    "Другое": "💼",
}

liabilities_emojis = {
    "Кредитная карта": "💳",
    "Потребительский кредит": "🏦",
    "Ипотека": "🏠",
    "Другое": "💼",
}

# Категории доходов
assets_categories = [
    "Карта и наличка",
    "Депозиты",
    "Акции",
    "Криптовалюта",
    "Недвижмость",
    "Другое"
    
]

# Категории расходов
liabilities_categories = [
    "Кредитная карта",
    "Потребительский кредит",
    "Ипотека",
    "Другое"
]



# -----------------------------------------------------------------------------------------------------------------------
# Старт + Главное меню
# -----------------------------------------------------------------------------------------------------------------------
# Старт
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    u = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", m.from_user.id)
    if not u:
        await db.execute("INSERT INTO users (tg_id, username, created_at) VALUES ($1,$2,NOW())", m.from_user.id, m.from_user.username)
    await m.answer(
        "Привет! Я FinAdvisor — твой персональный финансовый помощник.\n"
        "Вот что я могу:\n"
        "• Добавлять доходы/расходы\n"
        "• Показывать статистику\n"
        "• Счёт активов и долгов\n"
        "• Вести цели\n"
        "• Давать рекомендации\n"
        "Используй меню ниже.",
        reply_markup=main()
    )

def main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Транзакция", callback_data="menu_add_tx"),
         InlineKeyboardButton(text="🎯 Мои цели", callback_data="menu_goals")],
        [InlineKeyboardButton(text="💼 Капитал", callback_data="menu_capital"),
         InlineKeyboardButton(text="📈 Отчеты", callback_data="menu_stats")],
        # [InlineKeyboardButton(text="📊 Статистика", callback_data="menu_stats"),
         # InlineKeyboardButton(text="📈 График", callback_data="menu_chart")],
        [InlineKeyboardButton(text="💡 Личная консультация", callback_data="menu_consult")]
        # [InlineKeyboardButton(text="📁 Экспорт CSV", callback_data="menu_export"),
        # InlineKeyboardButton(text="📁 Импорт ", callback_data="menu_import")]
    ])

#Вывод главного меню 
@dp.callback_query(F.data == "cancel_fsm")
async def cb_cancel_fsm(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.answer("Отменено.", reply_markup=main())
    await c.answer()

# Команда главного меню
@dp.message(Command("main"))
async def cmd_help(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main())

# Команда Help
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
    "Вот что я могу:\n"
    "• Добавлять доходы/расходы\n"
    "• Показывать статистику\n"
    "• Счёт активов и долгов\n"
    "• Вести цели\n"
    "• Давать рекомендации\n"
    "Используй меню ниже:", reply_markup=main())
    
# -----------------------------------------------------------------------------------------------------------------------
# ➕ Добавить транзакцию
# -----------------------------------------------------------------------------------------------------------------------
class TXStates(StatesGroup):
    choose_type = State()        # выбор Доход/Расход
    choose_category = State()    # выбор категории
    amount = State()
    category = State()
    description = State()

# Добавляем кнопки
def build_categories_kb(cats: list):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cat, callback_data=f"tx_cat:{cat}")]
            for cat in cats
        ] + [[InlineKeyboardButton(text="↩️ Назад", callback_data="cancel_fsm")]]
    )
    
# Выбор типа транзакции
kb_tx_type = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💰 Доход", callback_data="tx_type_income")],
    [InlineKeyboardButton(text="💸 Расход", callback_data="tx_type_expense")],
    [InlineKeyboardButton(text="↩️ Назад", callback_data="cancel_fsm")]
])

# handler на “Добавить транзакцию”
@dp.callback_query(F.data == "menu_add_tx")
async def cb_menu_add_tx(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(TXStates.choose_type)
    await c.message.answer(
    "Шаг 1 из 4.\n"
    "Выберите тип транзакции:", reply_markup=kb_tx_type)
    await c.answer()

# Обработчик выбора типа (Доход / Расход)
@dp.callback_query(F.data == "tx_type_income")
async def choose_income(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(tx_type="income")
    kb = build_categories_kb(list(income_emojis.keys()))
    await state.set_state(TXStates.choose_category)
    await c.message.answer(
    "Шаг 2 из 4.\n"
    "Выберите категорию дохода:", reply_markup=kb)
    await c.answer()

@dp.callback_query(F.data == "tx_type_expense")
async def choose_expense(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(tx_type="expense")
    kb = build_categories_kb(list(expense_emojis.keys()))
    await state.set_state(TXStates.choose_category)
    await c.message.answer(
    "Шаг 2 из 4.\n"
    "Выберите категорию расхода:", reply_markup=kb)
    await c.answer()

# Обработчик выбора категории транзакции
@dp.callback_query(F.data.startswith("tx_cat:"))
async def choose_category(c: types.CallbackQuery, state: FSMContext):
    category = c.data.split("tx_cat:")[1]
    await state.update_data(category=category)

    await state.set_state(TXStates.amount)
    await c.message.answer(
    "Шаг 3 из 4.\n"
    "Введите сумму:", reply_markup=cancel_kb)
    await c.answer()

# Обработчик ввода суммы транзакции
@dp.message(TXStates.amount)
async def tx_enter_amount(msg: types.Message, state: FSMContext):
    text = msg.text.strip()
    if text.lower() in ("↩️ Назад", "cancel_fsm"):
        await state.clear()
        await msg.answer("Отменено.", reply_markup=main())
        return

    try:
        amount = float(text.replace(",", "."))
    except ValueError:
        await msg.answer("Введите корректное число, например: 1500 или -2500")
        return

    data = await state.get_data()
    tx_type = data.get("tx_type")

    # Автоматический знак
    if tx_type == "income":
        amount = abs(amount)
    else:
        amount = -abs(amount)

    # Сохраняем сумму в state для следующего шага (описание)
    await state.update_data(amount=amount)

    await state.set_state(TXStates.description)
    await msg.answer(
        "Шаг 4 из 4.\n"
        f"Сумма установлена: {format_amount(amount)}\n"
        "Введите описание транзакции (или '-' для пропуска):",
        reply_markup=cancel_kb
    )

# Обработчик описания транзакции
@dp.message(TXStates.description)
async def tx_enter_description(msg: types.Message, state: FSMContext):
    text = msg.text.strip()
    if text.lower() in ("↩️ Назад", "cancel_fsm"):
        await state.clear()
        await msg.answer("Отменено.", reply_markup=main())
        return

    description = None if text == "-" else text
    data = await state.get_data()
    user_id = await get_or_create_user(msg.from_user.id)

    # Записываем транзакцию в БД
    await db.execute(
        "INSERT INTO transactions (user_id, amount, category, description, created_at) "
        "VALUES ($1, $2, $3, $4, NOW())",
        user_id, data["amount"], data["category"], description
    )

    # Эмодзи для категории
    tx_type = data["tx_type"]
    cat = data["category"]
    emoji = income_emojis.get(cat) if tx_type == "income" else expense_emojis.get(cat)

    # Финальное сообщение
    await msg.answer(
        f"✅ Транзакция добавлена:\n"
        f"{emoji or ''} {cat}: {format_amount(data['amount'])}\n"
        f"{'Описание: ' + description if description else ''}",
        reply_markup=main()
    )

    await state.clear()



# -----------------------------------------------------------------------------------------------------------------------
# 🎯 Мои цели
# -----------------------------------------------------------------------------------------------------------------------
class GOALStates(StatesGroup):
    target = State()
    title = State()

# Обработчик меню целей
@dp.callback_query(F.data == "menu_goals")
async def menu_goals(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(GOALStates.target)
    await q.message.answer("Введите сумму цели:")


@dp.message(GOALStates.target)
async def goal_target(message: types.Message, state: FSMContext):
    try:
        target = float(message.text)
    except:
        await message.answer("Введите корректную сумму:")
        return

    await state.update_data(target=target)
    await state.set_state(GOALStates.title)
    await message.answer("Введите название цели:")


@dp.message(GOALStates.title)
async def goal_title(message: types.Message, state: FSMContext):
    user_id = await get_or_create_user(message.from_user.id)
    data = await state.get_data()

    await db.execute(
        "INSERT INTO goals (user_id, target, title) VALUES ($1,$2,$3)",
        user_id, data["target"], message.text
    )

    await message.answer("Цель добавлена.", reply_markup=main())
    await state.clear()

async def handle_stateful_message(m: types.Message, state: FSMContext) -> bool:
 
    current = await state.get_state()
    if not current:
        return False

    
    # Goal flow
    if current == GOALStates.target.state:
        text = (m.text or "").strip()
        if text.lower() in ("отмена", "cancel"):
            await state.clear()
            await m.answer("Отменено.", reply_markup=main())
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
            await m.answer("Отменено.", reply_markup=main())
            return True
        data = await state.get_data()
        target = data.get("target")
        title = text
        user_id = await get_or_create_user(m.from_user.id)
        await db.execute("INSERT INTO goals (user_id, target, current, title, created_at) VALUES ($1,$2,0,$3,NOW())",
                         user_id, target, title)
        await save_message(user_id, "system", f"Создана цель: {title} на {target}₽")
        await m.answer("Цель добавлена ✅", reply_markup=main())
        await state.clear()
        return True


# -----------------------------------------------------------------------------------------------------------------------
# 💼 Капитал
# -----------------------------------------------------------------------------------------------------------------------

class AssetStates(StatesGroup):
    amount = State()
    title = State()
    type = State()
    update_amount = State()


class LiabilityStates(StatesGroup):
    amount = State()
    title = State()
    type = State()
    monthly_payment = State()
    update_amount = State()

capital_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="➕ Добавить актив", callback_data="asset_add"),
        InlineKeyboardButton(text="🔄 Обновить активы", callback_data="asset_update_list")
    ],
    [
        InlineKeyboardButton(text="➕ Добавить долг", callback_data="liab_add"),
        InlineKeyboardButton(text="🔄 Обновить долги", callback_data="liab_update_list")
    ],
    [
        InlineKeyboardButton(text="📋 Мой капитал", callback_data="cap_show"),
        InlineKeyboardButton(text="↩️ Назад", callback_data="cancel_fsm")
    ]
])

def build_capital_category_kb(categories: list[str], emojis: dict[str, str], prefix: str) -> InlineKeyboardMarkup:
    rows = []
    for cat in categories:
        emoji = emojis.get(cat, "")
        text = f"{emoji} {cat}" if emoji else cat
        rows.append(
            [InlineKeyboardButton(text=text, callback_data=f"{prefix}{cat}")]
        )
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="menu_capital")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# -------- CAPITAL MENU --------

@dp.callback_query(F.data == "menu_capital")
async def main_capital_menu(c: types.CallbackQuery):

    await c.message.edit_text(f" (здесь место для текущих активов) \nУправление капиталом:", reply_markup=capital_kb)
    
    await c.answer()

# ============================
#         ASSETS
# ============================
async def create_asset(user_id: int, title: str, typ: str, amount: float, currency: str = "RUB") -> int:
    """Создаёт актив + первую запись стоимости"""
    row = await db.fetchrow(
        """
        INSERT INTO assets (user_id, type, title, currency, created_at)
        VALUES ($1, $2, $3, $4, NOW())
        RETURNING id
        """,
        user_id, typ, title, currency
    )

    asset_id = row["id"]

    await db.execute(
        """
        INSERT INTO asset_values (asset_id, amount, created_at)
        VALUES ($1, $2, NOW())
        """,
        asset_id, amount
    )

    return asset_id


async def add_asset_value(asset_id: int, amount: float):
    """Добавляет новую актуализацию стоимости актива"""
    await db.execute(
        """
        INSERT INTO asset_values (asset_id, amount, created_at)
        VALUES ($1, $2, NOW())
        """,
        asset_id, amount
    )


async def get_assets_list(user_id: int):
    """Получить список активов с последней стоимостью"""
    rows = await db.fetch(
        """
        SELECT a.id AS asset_id, a.title, a.type, a.currency,
               v.amount, v.created_at AS updated_at
        FROM assets a
        LEFT JOIN LATERAL (
            SELECT amount, created_at
            FROM asset_values
            WHERE asset_id = a.id
            ORDER BY created_at DESC
            LIMIT 1
        ) v ON TRUE
        WHERE a.user_id = $1
        and v.amount >0
        ORDER BY a.type, v.amount ASC
        """,
        user_id,
    )
    return [dict(r) for r in rows]

# -------- ADD ASSET --------

@dp.callback_query(F.data == "asset_add")
async def add_asset_start(c: types.CallbackQuery, state: FSMContext):
    kb = build_capital_category_kb(assets_categories, assets_emojis, "asset_cat:")
    await c.message.edit_text("Выберите категорию актива:", reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("asset_cat:"))
async def add_asset_choose_type(c: types.CallbackQuery, state: FSMContext):
    category = c.data.split("asset_cat:", 1)[1]
    await state.update_data(type=category)
    await state.set_state(AssetStates.amount)
    await c.message.edit_text(
        f"Создание актива — {category}\nВведите стоимость:",
        reply_markup=cancel_kb,
    )
    await c.answer()


@dp.message(AssetStates.amount)
async def add_asset_amount(msg: types.Message, state: FSMContext):
    try:
        amount = float(msg.text.replace(",", "."))
    except:
        await msg.answer("Введите корректное число.")
        return

    await state.update_data(amount=amount)
    await state.set_state(AssetStates.title)
    await msg.answer("Введите название актива:", reply_markup=cancel_kb)


@dp.message(AssetStates.title)
async def add_asset_title(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = await get_or_create_user(msg.from_user.id)

    asset_id = await create_asset(
        user_id=user_id,
        title=msg.text.strip(),
        typ=data["type"],
        amount=data["amount"]
    )

    await msg.answer(
        f"Актив добавлен:\n{data['type']} — {msg.text}: {int(data['amount']):,} ₽",
        reply_markup=main()
    )

    await state.clear()


# -------- UPDATE ASSET --------

@dp.callback_query(F.data == "asset_update_list")
async def asset_update_list(c: types.CallbackQuery, state: FSMContext):
    user_id = await get_or_create_user(c.from_user.id)
    assets = await get_assets_list(user_id)

    if not assets:
        await c.message.answer("Активов нет. Добавьте актив.", reply_markup=main())
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{a['type']}: {a['title']} — {int(a['amount']):,}₽",
                    callback_data=f"asset_update:{a['asset_id']}"
                )
            ]
            for a in assets
        ] + [[InlineKeyboardButton(text="↩️ Назад", callback_data="menu_capital")]]
    )

    await c.message.edit_text("Выберите актив:", reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("asset_update:"))
async def asset_update_selected(c: types.CallbackQuery, state: FSMContext):
    aid = int(c.data.split("asset_update:")[1])
    await state.update_data(asset_id=aid)
    await state.set_state(AssetStates.update_amount)
    await c.message.answer("Введите новую стоимость актива:", reply_markup=cancel_kb)
    await c.answer()


@dp.message(AssetStates.update_amount)
async def asset_update_amount(msg: types.Message, state: FSMContext):
    try:
        amount = float(msg.text.replace(",", "."))
    except:
        await msg.answer("Введите число.")
        return

    data = await state.get_data()
    await add_asset_value(data["asset_id"], amount)

    await msg.answer(
        f"Стоимость обновлена: {int(amount):,} ₽",
        reply_markup=main()
    )
    await state.clear()


# ============================
#         LIABILITIES
# ============================
async def create_liability(
    user_id: int, title: str, typ: str, amount: float, monthly_payment: float, currency: str = "RUB"
) -> int:
    """Создаёт долг + первую запись истории"""
    row = await db.fetchrow(
        """
        INSERT INTO liabilities (user_id, type, title, currency, created_at)
        VALUES ($1, $2, $3, $4, NOW())
        RETURNING id
        """,
        user_id, typ, title, currency
    )

    liability_id = row["id"]

    await db.execute(
        """
        INSERT INTO liability_values (liability_id, amount, monthly_payment, created_at)
        VALUES ($1, $2, $3, NOW())
        """,
        liability_id, amount, monthly_payment
    )

    return liability_id


async def add_liability_value(liability_id: int, amount: float, monthly_payment: float | None = None):
    """Добавляет новую актуализацию суммы долга"""
    if monthly_payment is None:
        monthly_payment = 0

    await db.execute(
        """
        INSERT INTO liability_values (liability_id, amount, monthly_payment, created_at)
        VALUES ($1, $2, $3, NOW())
        """,
        liability_id, amount, monthly_payment
    )


async def get_liabilities_list(user_id: int):
    """Получить список долгов с последней суммой и платежом"""
    rows = await db.fetch(
        """
        SELECT l.id AS liability_id, l.title, l.type, l.currency,
               v.amount, v.monthly_payment, v.created_at AS updated_at
        FROM liabilities l
        LEFT JOIN LATERAL (
            SELECT amount, monthly_payment, created_at
            FROM liability_values
            WHERE liability_id = l.id
            ORDER BY created_at DESC
            LIMIT 1
        ) v ON TRUE
        WHERE l.user_id = $1
        and v.amount >0
        ORDER BY l.type,v.amount ASC
        """,
        user_id,
    )
    return [dict(r) for r in rows]
# -------- ADD LIABILITY --------

@dp.callback_query(F.data == "liab_add")
async def liab_add_start(c: types.CallbackQuery, state: FSMContext):
    kb = build_capital_category_kb(liabilities_categories, liabilities_emojis, "liab_cat:")
    await c.message.edit_text("Выберите категорию долга:", reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("liab_cat:"))
async def liab_choose_type(c: types.CallbackQuery, state: FSMContext):
    category = c.data.split("liab_cat:", 1)[1]
    await state.update_data(type=category)
    await state.set_state(LiabilityStates.amount)
    await c.message.edit_text("Введите сумму долга:", reply_markup=cancel_kb)
    await c.answer()


@dp.message(LiabilityStates.amount)
async def liab_amount(msg: types.Message, state: FSMContext):
    try:
        amount = float(msg.text.replace(",", "."))
    except:
        await msg.answer("Введите число.")
        return

    await state.update_data(amount=amount)
    await state.set_state(LiabilityStates.monthly_payment)
    await msg.answer("Введите ежемесячный платёж:", reply_markup=cancel_kb)


@dp.message(LiabilityStates.monthly_payment)
async def liab_monthly(msg: types.Message, state: FSMContext):
    try:
        monthly = float(msg.text.replace(",", "."))
    except:
        await msg.answer("Введите число.")
        return

    await state.update_data(monthly=monthly)
    await state.set_state(LiabilityStates.title)
    await msg.answer("Введите название долга:", reply_markup=cancel_kb)


@dp.message(LiabilityStates.title)
async def liab_title(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = await get_or_create_user(msg.from_user.id)

    await create_liability(
        user_id=user_id,
        title=msg.text.strip(),
        typ=data["type"],
        amount=data["amount"],
        monthly_payment=data["monthly"]
    )

    await msg.answer("Долг добавлен.", reply_markup=main())
    await state.clear()


# -------- UPDATE LIABILITY --------

@dp.callback_query(F.data == "liab_update_list")
async def liab_update_list(c: types.CallbackQuery, state: FSMContext):
    user_id = await get_or_create_user(c.from_user.id)
    liabs = await get_liabilities_list(user_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{l['type']}: {l['title']} — {int(l['amount']):,}₽",
                    callback_data=f"liab_update:{l['liability_id']}"
                )
            ]
            for l in liabs
        ] + [[InlineKeyboardButton(text="↩️ Назад", callback_data="menu_capital")]]
    )

    await c.message.edit_text("Выберите долг:", reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("liab_update:"))
async def liab_update_selected(c: types.CallbackQuery, state: FSMContext):
    lid = int(c.data.split("liab_update:")[1])
    await state.update_data(liability_id=lid)
    await state.set_state(LiabilityStates.update_amount)
    await c.message.answer("Введите новую сумму долга:", reply_markup=cancel_kb)
    await c.answer()


@dp.message(LiabilityStates.update_amount)
async def liab_update_amount(msg: types.Message, state: FSMContext):
    try:
        amount = float(msg.text.replace(",", "."))
    except:
        await msg.answer("Введите число.")
        return

    data = await state.get_data()
    await add_liability_value(data["liability_id"], amount)

    await msg.answer(
        f"Сумма долга обновлена: {int(amount):,} ₽",
        reply_markup=main()
    )
    await state.clear()
 
# # Показать активы/долги

# @dp.callback_query(F.data == "cap_show")
# async def cb_cap_show(c: types.CallbackQuery):
    # user_id = await get_or_create_user(c.from_user.id)
    
    # assets = await db.fetch(
        # """
        # SELECT a.id AS asset_id, a.title, a.type, a.currency,
               # v.amount, v.created_at AS updated_at
        # FROM assets a
        # LEFT JOIN LATERAL (
            # SELECT amount, created_at
            # FROM asset_values
            # WHERE asset_id = a.id
            # ORDER BY created_at DESC
            # LIMIT 1
        # ) v ON TRUE
        # WHERE a.user_id = $1
        # and v.amount >0
        # ORDER BY a.type, v.amount ASC
        # """, user_id)
    # liabs = await db.fetch(
        # """
        # SELECT l.id AS liability_id, l.title, l.type, l.currency,
               # v.amount, v.monthly_payment, v.created_at AS updated_at
        # FROM liabilities l
        # LEFT JOIN LATERAL (
            # SELECT amount, monthly_payment, created_at
            # FROM liability_values
            # WHERE liability_id = l.id
            # ORDER BY created_at DESC
            # LIMIT 1
        # ) v ON TRUE
        # WHERE l.user_id = $1
        # and v.amount >0
        # ORDER BY l.type,v.amount ASC
        # """, user_id)
    
    # total_assets = sum(a["amount"] for a in assets) if assets else 0
    # total_liabs = sum(l["amount"] for l in liabs) if liabs else 0
    # net_capital = total_assets - total_liabs

    # # --- Активы ---
    # text = f"💰 *Активы* - {int(total_assets):,}".replace(",", " ") + "₽:\n"
    # for a in assets:
        # amt = int(a["amount"])
        # text += f"- {a['type']}: {amt:,}".replace(",", " ") + f"₽ ({a['title']})\n"

    # # --- Долги ---
    # text += f"\n💸 *Долги* - {int(total_liabs):,}".replace(",", " ") + "₽:\n"
    # for l in liabs:
        # amt = int(l["amount"])
        # text += f"- {l['type']}: {amt:,}".replace(",", " ") + f"₽ ({l['title']})\n"

    # # --- Чистый капитал ---
    # if net_capital >= 0:
        # net_emoji = "🟢"
    # else:
        # net_emoji = "🔴"
    # text += f"\n *Чистый капитал: {net_emoji} * {int(net_capital):,}".replace(",", " ") + "₽" 

    # await c.message.answer(text, parse_mode="Markdown")


# -----------------------------------------------------------------------------------------------------------------------
# 📈 Отчеты
# -----------------------------------------------------------------------------------------------------------------------
async def create_expense_donut(user_id: int):
    # Текущая дата в UTC для определения начала месяца
    
    start_month = datetime(now.year, now.month, 1)
    
    # Получаем все транзакции пользователя с суммами и категориями за текущий месяц (расходы отрицательные)
    rows = await db.fetch("SELECT amount, category FROM transactions WHERE user_id=$1 AND created_at >= $2", user_id, start_month)
    if not rows:
        return None
    
    by_cat = {}
    total_expense = 0.0
    for r in rows:
        amount = float(r["amount"])
        if amount >= 0:
            continue  # учитываем только расходы (отрицательные суммы)
        cat = r["category"] or "—"
        by_cat[cat] = by_cat.get(cat, 0) + (-amount)  # делаем положительным
    
    total_expense = sum(by_cat.values())
    
    # Объединяем малые категории (меньше 5% от суммы) в "Прочее"
    threshold = total_expense * 0.05
    large_cats = {k:v for k,v in by_cat.items() if v >= threshold}
    small_cats_sum = sum(v for v in by_cat.values() if v < threshold)
    if small_cats_sum > 0:
        large_cats["Прочее"] = small_cats_sum
    
    labels = list(large_cats.keys())
    sizes = list(large_cats.values())
    
    # Создаем фигуру 6x6 для диаграммы
    fig, ax = plt.subplots(figsize=(6,6))
    
    # Основной пирог
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, pctdistance=0.85)
    
    # Рисуем "дырку" по центру (donut effect)
    centre_circle = plt.Circle((0,0),0.70,fc='white')
    fig.gca().add_artist(centre_circle)
    
    # В центре выводим сумму расходов
    ax.text(0, 0, f'{total_expense:,.0f}₽', ha='center', va='center', fontsize=18, fontweight='bold')
    
    # Заголовок и легенда сверху
    ax.set_title("Расходы по категориям в текущем месяце", y=1.05, fontsize=14)
    ax.legend(wedges, labels, bbox_to_anchor=(0.5, 1.15), loc='upper center', ncol=3)
    
    plt.tight_layout()
    
    # Сохраняем снимок
    fname = f"{TMP_DIR}/donut_expense_{user_id}_{int(now_moscow.replace(tzinfo=None).timestamp())}.png"
    plt.savefig(fname)
    plt.close(fig)
    return fname

async def create_goals_progress_bar(user_id: int):
    goals = await db.fetch("SELECT title, target, current FROM goals WHERE user_id=$1", user_id)
    if not goals:
        return None
    
    titles = []
    progress = []
    full_done = []
    
    for g in goals:
        titles.append(g["title"])
        if g["target"] == 0:
            pct = 0
        else:
            pct = min(int(round(g["current"] / g["target"] * 100)), 100)
        progress.append(pct)
        full_done.append(pct == 100)
    
    fig, ax = plt.subplots(figsize=(8, len(goals) * 0.6 + 1))
    
    y_pos = np.arange(len(goals))
    ax.barh(y_pos, progress, color='green', edgecolor='black')
    ax.barh(y_pos, [100 - p for p in progress], left=progress, color='lightgray', edgecolor='black')
    
    # Подписи по оси Y — названия целей
    ax.set_yticks(y_pos)
    ax.set_yticklabels(titles, fontsize=10)
    ax.invert_yaxis()  # чтобы первая цель сверху
    
    # Добавляем процентовки и галочки у целей
    for i, (p, done) in enumerate(zip(progress, full_done)):
        ax.text(p + 2, i, f"{p}%", va='center', fontsize=9)
        if done:
            ax.text(102, i, "✔", va='center', fontsize=12, color='green', fontweight='bold')
    
    ax.set_xlim(0, 110)
    ax.set_xlabel('Выполнение цели (%)')
    ax.set_title('Прогресс по целям', fontsize=14)
    plt.tight_layout()
    
    fname = f"{TMP_DIR}/goals_progress_{user_id}_{int(now_moscow.replace(tzinfo=None).timestamp())}.png"
    plt.savefig(fname)
    plt.close(fig)
    return fname


async def create_weekly_balance_chart(user_id: int):
    from datetime import datetime, timedelta
    import matplotlib.dates as mdates
    import pandas as pd

    one_year_ago = now_moscow.replace(tzinfo=None) - timedelta(days=365)

    assets = await db.fetch(
        "SELECT amount, created_at FROM assets WHERE user_id=$1 AND created_at >= $2 ORDER BY created_at ASC",
        user_id, one_year_ago
    )
    liabs = await db.fetch(
        "SELECT amount, created_at FROM liabilities WHERE user_id=$1 AND created_at >= $2 ORDER BY created_at ASC",
        user_id, one_year_ago
    )

    if not assets and not liabs:
        return None

    df_assets = pd.DataFrame([(a['created_at'].date(), float(a['amount'])) for a in assets], columns=['date','amount'])
    df_liabs = pd.DataFrame([(l['created_at'].date(), -float(l['amount'])) for l in liabs], columns=['date','amount'])

    df_assets['date'] = pd.to_datetime(df_assets['date'])
    df_liabs['date'] = pd.to_datetime(df_liabs['date'])
    df_assets.set_index('date', inplace=True)
    df_liabs.set_index('date', inplace=True)

    weekly_assets = df_assets.groupby(pd.Grouper(freq='W-MON'))['amount'].sum().reindex(
        pd.date_range(one_year_ago.date(), now_moscow.replace(tzinfo=None).date(), freq='W-MON'),
        fill_value=0
    )
    weekly_liabs = df_liabs.groupby(pd.Grouper(freq='W-MON'))['amount'].sum().reindex(
        pd.date_range(one_year_ago.date(), now_moscow.replace(tzinfo=None).date(), freq='W-MON'),
        fill_value=0
    )

    net_worth = weekly_assets + weekly_liabs

    fig, ax = plt.subplots(figsize=(12,6))

    ax.bar(weekly_assets.index, weekly_assets.values, width=4, color='green', label='Активы')
    ax.bar(weekly_liabs.index, weekly_liabs.values, width=4, color='red', label='Долги')

    for dt, net in zip(net_worth.index, net_worth.values):
        ax.text(dt, net, f"{int(net):,}", ha='center', va='bottom' if net >= 0 else 'top', fontsize=8, rotation=90)

    ax.set_title("Баланс по неделям за последний год")
    ax.set_xlabel("Дата (понедельник недели)")
    ax.set_ylabel("Сумма (₽)")
    ax.legend()

    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    plt.xticks(rotation=45)
    plt.tight_layout()

    fname = f"{TMP_DIR}/weekly_balance_{user_id}_{int(now_moscow.replace(tzinfo=None).timestamp())}.png"
    plt.savefig(fname)
    plt.close(fig)
    return fname

async def create_asset_history_chart(asset_id: int):
    hist = await get_asset_history(asset_id)
    if not hist or len(hist) < 1:
        return None
    dates = [h["created_at"].date() for h in hist]
    vals = [h["amount"] for h in hist]

    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(dates, vals, marker='o')
    ax.set_title("Динамика стоимости актива")
    ax.set_xlabel("Дата")
    ax.set_ylabel("Стоимость (₽)")
    fig.autofmt_xdate()
    plt.tight_layout()
    fname = f"{TMP_DIR}/asset_history_{asset_id}_{int(now_moscow.replace(tzinfo=None).timestamp())}.png"
    plt.savefig(fname)
    plt.close(fig)
    return fname

async def create_portfolio_history_chart(user_id: int, days: int = 365):
    # собираем net-worth по дням: суммарная последняя оценка каждого актива на дату
    import pandas as pd
    assets = await db.fetch("SELECT id FROM assets WHERE user_id=$1", user_id)
    if not assets:
        return None
    # собрать все values за период
    cutoff = now_moscow.replace(tzinfo=None) - timedelta(days=days)
    rows = await db.fetch("""
       SELECT av.asset_id, av.amount, av.created_at
       FROM asset_values av
       JOIN assets a ON a.id = av.asset_id
       WHERE a.user_id = $1 AND av.created_at >= $2
       ORDER BY av.created_at ASC
    """, user_id, cutoff)
    if not rows:
        return None
    df = pd.DataFrame([{"asset_id": r["asset_id"], "amount": float(r["amount"]), "created_at": r["created_at"].date()} for r in rows])
    # агрегируем: для каждой даты берем сумму последних значений каждого актива в этот день
    # упрощённый способ: группируем по (asset_id, date) берём последний amount, затем суммируем по дате
    df_grouped = df.groupby(["asset_id", "created_at"]).last().reset_index()
    daily = df_grouped.groupby("created_at")["amount"].sum().reset_index()
    dates = pd.to_datetime(daily["created_at"])
    vals = daily["amount"]

    fig, ax = plt.subplots(figsize=(12,5))
    ax.plot(dates, vals, marker='o')
    ax.set_title("Динамика чистого капитала")
    ax.set_xlabel("Дата")
    ax.set_ylabel("Сумма (₽)")
    fig.autofmt_xdate()
    plt.tight_layout()
    fname = f"{TMP_DIR}/portfolio_history_{user_id}_{int(now_moscow.replace(tzinfo=None).timestamp())}.png"
    plt.savefig(fname)
    plt.close(fig)
    return fname

# Handlers Графики
@dp.callback_query(F.data == "menu_chart")
async def cb_chart(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    
    # 1. График расходов (donut)
    img_expense = await create_expense_donut(user_id)
    if img_expense:
        await c.message.answer_photo(types.FSInputFile(img_expense), caption="Траты за текущий месяц (donut)")
        try:
            os.remove(img_expense)
        except Exception:
            pass
    else:
        await c.message.answer("Нет данных для графика расходов.")
    
    # 2. График прогресса по целям
    img_progress = await create_goals_progress_bar(user_id)
    if img_progress:
        await c.message.answer_photo(types.FSInputFile(img_progress), caption="Прогресс по целям")
        try:
            os.remove(img_progress)
        except Exception:
            pass
    else:
        await c.message.answer("Нет данных о целях.")
        
    # 3. График баланса по неделям
    img_balance = await create_weekly_balance_chart(user_id)
    if img_balance:
        await c.message.answer_photo(types.FSInputFile(img_balance), caption="Баланс по неделям за год")
        try:
            os.remove(img_balance)
        except Exception:
            pass
    else:
        await c.message.answer("Нет данных для графика баланса.")
    
    await c.answer()

# Статистика
@dp.callback_query(F.data == "menu_stats")
async def cb_stats(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)

    
    since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = await db.fetch("""
        SELECT amount, category, created_at 
        FROM transactions 
        WHERE user_id=$1 AND created_at >= $2 
        ORDER BY created_at ASC
    """, user_id, since)

    if not rows:
        await c.message.answer("Нет транзакций в текущем месяце.")
        await c.answer()
        return

    total = sum(r["amount"] for r in rows)

    # группировка категорий
    by_cat = {}
    for r in rows:
        cat = r["category"] or "—"
        by_cat[cat] = by_cat.get(cat, 0) + float(r["amount"])

    cat_count = len(by_cat)

    # ---- Компактный режим ----
    if cat_count > 7:
        text = (
            "📊 *Статистика за текущий месяц (компактный режим)*\n"
            f"*Всего:* {int(total):,}".replace(",", " ") + " ₽\n\n"
            "🔻 Топ 5 категорий:\n"
        )


        top5 = sorted(by_cat.items(), key=lambda x: -abs(x[1]))[:5]
        for cat, val in top5:
            emoji = CATEGORY_EMOJI.get(cat, "❓")
            text += f"{emoji} *{cat}*: {int(val):,}".replace(",", " ") + " ₽\n"

        other_sum = sum(v for _, v in sorted(by_cat.items(), key=lambda x: -abs(x[1]))[5:])
        if other_sum != 0:
            text += f"\n📦 Остальные категории: {int(other_sum):,}".replace(",", " ") + " ₽\n"

        text += "\n📱 _Много категорий — включён компактный режим_"

        await c.message.answer(text, parse_mode="Markdown")
        await c.answer()
        return

    # ---- Обычный режим ----
    text = f"📊 Статистика (текущий месяц):\n*Всего:* {int(total):,}".replace(",", " ") + " ₽\n\n"
    for cat, val in sorted(by_cat.items(), key=lambda x: -abs(x[1])):
        emoji = CATEGORY_EMOJI.get(cat, "❓")
        text += f"{emoji} {cat}: {int(val):,}".replace(",", " ") + " ₽\n"

    await c.message.answer(text, parse_mode="Markdown")
    await c.answer()


# -----------------------------------------------------------------------------------------------------------------------
# 💡 Личная консультация
# -----------------------------------------------------------------------------------------------------------------------


# Кнопка консультация
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
    
    
        
    # --- График прогресса целей ---
    img = await create_goals_progress_bar(user_id)
    if img:
        await c.message.answer_photo(types.FSInputFile(img))
        try:
            os.remove(img)
        except Exception:
            pass
    
    await c.answer()



# AI cache (uses ai_cache table)

# ------------- Хеширование входных данных -------------
def _hash_input(user_message: str, finance_snapshot: str) -> str:
    # user_message — сообщение пользователя (например "Сколько у меня денег?")
    # finance_snapshot — текстовая сводка его финансов (например список транзакций)
    
    h = hashlib.sha256((user_message.strip().lower() + "\n" + finance_snapshot).encode("utf-8"))
    # Хешируем закодированную строку алгоритмом SHA256 и добавляем финсводку через перенос строки ("\n").
    return h.hexdigest()
    # Возвращает ХЭШ Например 'e3b0c44298fc1c149afbf4c8996fb924...'

# ------------- Получение ответа из кэша -------------  
async def get_cached_ai_reply(user_id: int, user_message: str, finance_snapshot: str):
    h = _hash_input(user_message, finance_snapshot) # Получаем уникальный хеш для этого набора данных
    row = await db.fetchrow("SELECT answer FROM ai_cache WHERE user_id=$1 AND input_hash=$2 ORDER BY created_at DESC LIMIT 1", user_id, h)
    # Делаем запрос к базе данных: ищем строку, где user_id равен нужному пользователю, а input_hash совпадает с нашим хешем.
    # fetchrow — достаёт только одну строку (или None, если ничего не найдено).
    return row["answer"] if row else None
    # Если строка найдена, возвращаем значение поля answer (ответ из базы), иначе возвращаем None

# ------------- Сохранение ответа в кэш -------------
async def save_ai_cache(user_id: int, user_message: str, finance_snapshot: str, ai_answer: str):
    h = _hash_input(user_message, finance_snapshot)
    await db.execute("INSERT INTO ai_cache (user_id, input_hash, answer, created_at) VALUES ($1,$2,$3,NOW())", user_id, h, ai_answer)


# ai_context helpers

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


# Finance analysis

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


# AI answer generation for general messages (assistant mode)

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


# Consultation command: /consult and menu_consult
# Short actionable step-by-step recommendations

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
        return "Извините, AI временно недоступен. Уже чиним."
    await save_message(user_id, "assistant", f"Consultation generated")
    await save_ai_cache(user_id, "CONSULT_REQUEST", finance_snapshot, answer)
    return answer


# ----------------------------
# Handlers - callback queries and commands
# ----------------------------






 






# @dp.callback_query(F.data == "menu_export")
# async def cb_export(c: types.CallbackQuery):
    # user_id = await get_or_create_user(c.from_user.id)
    # rows = await db.fetch("SELECT id, amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at ASC", user_id)
    # if not rows:
        # await c.message.answer("Нет транзакций для экспорта.")
        # await c.answer()
        # return
    # fd, path = tempfile.mkstemp(prefix=f"finances_{user_id}_", suffix=".csv")
    # os.close(fd)
    # with open(path, "w", encoding="utf-8", newline="") as f:
        # import csv
        # writer = csv.writer(f)
        # writer.writerow(["id","amount","category","description","created_at"])
        # for r in rows:
            # writer.writerow([r["id"], r["amount"], r["category"] or "", r["description"] or "", r["created_at"].isoformat() if r["created_at"] else ""])
    # await c.message.answer_document(types.FSInputFile(path), caption="Экспорт транзакций (CSV)")
    # try:
        # os.remove(path)
    # except Exception:
        # pass
    # await c.answer()


# @dp.callback_query(F.data == "stat_goals")
# async def cb_menu_goals(c: types.CallbackQuery):
    # user_id = await get_or_create_user(c.from_user.id)
    # rows = await db.fetch("SELECT id, title, target, current, created_at FROM goals WHERE user_id=$1", user_id)
    # if not rows:
        # await c.message.answer("Целей нет. Нажми «🎯 Мои цели» и затем /goal, чтобы добавить.")
    # else:
        # text = "Твои цели:\n"
        # for r in rows:
            # pr = (r["current"] / r["target"] * 100) if r["target"] else 0
            # text += f"- {r['title']}: {r['current']}/{r['target']} ₽ ({pr:.1f}%)\n"
        # await c.message.answer(text)
    # await c.answer()


# ----------------------------
# Заглушка на все неверные запросы
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

    # Otherwise: глушилка
    user_id = await get_or_create_user(m.from_user.id)
    await m.answer("Неверная команда", reply_markup=main())
    
    # # Otherwise: pass to AI assistant (generate reply)
    # user_id = await get_or_create_user(m.from_user.id)
    # await m.answer("Анализирую... (AI ответ может занять пару секунд)")
    # reply = await generate_ai_reply(user_id, m.text or "")
    # await m.answer(reply)

# ----------------------------
# Job Еженедельный отчет
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
            pie = await create_expense_donut(user_id)
            goals_progress_bar = await create_goals_progress_bar(user_id)
            net = await create_weekly_balance_chart(user_id)
            if pie:
                await bot.send_photo(tg_id, types.FSInputFile(pie), caption="Расходы по категориям в текущем месяце")
                try: os.remove(pie)
                except: pass
            if net:
                await bot.send_photo(tg_id, types.FSInputFile(net), caption="Прогресс по целям")
                try: os.remove(net)
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

