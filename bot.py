# v_03.01.26 - Оптимизирован: удалены дубликаты и неиспользуемый код

import os
import asyncio
import asyncpg
import hashlib
import json
import uuid
import base64
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

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
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat:2.0.28.2")


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
    auth_str = f"{G_CLIENT_ID}:{G_CLIENT_SECRET}"
    b64 = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4())
    }
    data = {"scope": G_SCOPE}
    async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
        r = await client.post(G_AUTH_URL, headers=headers, data=data)
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
        r = await client.post(G_API_URL, headers=headers, json=payload)
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

def fmt(amount: float) -> str:
    """Форматирование числа с пробелами (без валюты)"""
    return f"{int(amount):,}".replace(",", " ")

# Получить последние транзакции
async def get_recent_transactions(user_id: int, limit: int = 10):
    """Получить последние транзакции пользователя"""
    rows = await db.fetch(
        """
        SELECT id, amount, category, description, created_at
        FROM transactions
        WHERE user_id=$1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id, limit
    )
    return rows

# Форматирование истории транзакций для отображения
async def format_recent_transactions_text(user_id: int, limit: int = 10) -> str:
    """Форматирует последние транзакции в текст"""
    rows = await get_recent_transactions(user_id, limit)
    if not rows:
        return "📜 *История транзакций:*\nНет транзакций.\n"
    
    text = "📜 *Последние транзакции:*\n\n"
    for r in rows:
        emoji = "💰" if r["amount"] >= 0 else "💸"
        date = r["created_at"].strftime("%d.%m.%Y")
        cat = r["category"] or "—"
        desc = f" — {r['description']}" if r['description'] else ""
        text += f"{emoji} {format_amount(r['amount'])} | {cat}{desc}\n"
        text += f"   📅 {date}\n\n"
    return text

# Получить страницу транзакций для пагинации
async def get_transactions_page(user_id: int, page: int = 0, per_page: int = 10):
    """Получить страницу транзакций с пагинацией"""
    offset = page * per_page
    rows = await db.fetch(
        """
        SELECT id, amount, category, description, created_at
        FROM transactions
        WHERE user_id=$1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        user_id, per_page, offset
    )
    total = await db.fetchval("SELECT COUNT(*) FROM transactions WHERE user_id=$1", user_id)
    return rows, total

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
    
    user_id = await get_or_create_user(m.from_user.id)
    recent_tx_text = await format_recent_transactions_text(user_id, limit=5)
    
    await m.answer(
        "Привет! Я FinAdvisor — твой персональный финансовый помощник.\n"
        "Вот что я могу:\n"
        "• Добавлять доходы/расходы\n"
        "• Показывать статистику\n"
        "• Счёт активов и долгов\n"
        "• Вести цели\n"
        "• Давать рекомендации\n\n"
        + recent_tx_text,
        parse_mode="Markdown",
        reply_markup=await main_kb(user_id)
    )

async def main_kb(user_id: int = None):
    """Главное меню с последними транзакциями"""
    kb = [
        [InlineKeyboardButton(text="➕ Транзакция", callback_data="menu_add_tx"),
         InlineKeyboardButton(text="🎯 Мои цели", callback_data="menu_goals")],
        [InlineKeyboardButton(text="💼 Капитал", callback_data="menu_capital"),
         InlineKeyboardButton(text="📈 Отчеты", callback_data="menu_charts")],
        [InlineKeyboardButton(text="💡 Личная консультация", callback_data="menu_consult")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def main():
    """Простое главное меню (для обратной совместимости)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Транзакция", callback_data="menu_add_tx"),
         InlineKeyboardButton(text="🎯 Мои цели", callback_data="menu_goals")],
        [InlineKeyboardButton(text="💼 Капитал", callback_data="menu_capital"),
         InlineKeyboardButton(text="📈 Отчеты", callback_data="menu_charts")],
        [InlineKeyboardButton(text="💡 Личная консультация", callback_data="menu_consult")]
    ])

#Вывод главного меню 
@dp.callback_query(F.data == "cancel_fsm")
async def cb_cancel_fsm(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = await get_or_create_user(c.from_user.id)
    await c.message.edit_text("Главное меню", reply_markup=await main_kb(user_id))
    await c.answer()

# Команда главного меню
@dp.message(Command("main"))
async def cmd_help(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    recent_tx_text = await format_recent_transactions_text(user_id, limit=5)
    await message.answer(
        "Главное меню:\n\n" + recent_tx_text,
        parse_mode="Markdown",
        reply_markup=await main_kb(user_id)
    )

# Команда Help
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    await message.answer(
        "Вот что я могу:\n"
        "• Добавлять доходы/расходы\n"
        "• Показывать статистику\n"
        "• Счёт активов и долгов\n"
        "• Вести цели\n"
        "• Давать рекомендации\n"
        "Используй меню ниже:",
        reply_markup=await main_kb(user_id)
    )
    
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
def build_categories_kb(categories: dict):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{emoji} {cat}",
                    callback_data=f"tx_cat:{cat}"
                )
            ]
            for cat, emoji in categories.items()
        ] + [
            [InlineKeyboardButton(text="↩️ Назад", callback_data="cancel_fsm")]
        ]
    )

# Выбор типа транзакции
def build_tx_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Доход", callback_data="tx_type_income")],
        [InlineKeyboardButton(text="💸 Расход", callback_data="tx_type_expense")],
        [InlineKeyboardButton(text="📜 История транзакций", callback_data="menu_tx_history")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="cancel_fsm")]
    ])

# handler на “Добавить транзакцию”
@dp.callback_query(F.data == "menu_add_tx")
async def cb_menu_add_tx(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(TXStates.choose_type)
    user_id = await get_or_create_user(c.from_user.id)
    
    # Показываем статистику за текущий месяц перед выбором типа
    stats_text = await build_text_stats(user_id)
    
    await c.message.edit_text(
        stats_text + "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Шаг 1 из 4.\n"
        "Выберите тип транзакции:",
        parse_mode="Markdown",
        reply_markup=build_tx_type_kb()
    )
    await c.answer()

# Обработчик выбора типа (Доход / Расход)
@dp.callback_query(F.data == "tx_type_income")
async def choose_income(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(tx_type="income")
    kb = build_categories_kb(income_emojis)   # ← передаем словарь
    await state.set_state(TXStates.choose_category)
    await c.message.edit_text(
        "Шаг 2 из 4.\nВыберите категорию дохода:",
        reply_markup=kb
    )
    await c.answer()

@dp.callback_query(F.data == "tx_type_expense")
async def choose_expense(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(tx_type="expense")
    kb = build_categories_kb(expense_emojis)
    await state.set_state(TXStates.choose_category)
    await c.message.edit_text(
        "Шаг 2 из 4.\nВыберите категорию расхода:",
        reply_markup=kb
    )
    await c.answer()

# Обработчик выбора категории транзакции
@dp.callback_query(F.data.startswith("tx_cat:"))
async def choose_category(c: types.CallbackQuery, state: FSMContext):
    category = c.data.split("tx_cat:")[1]
    await state.update_data(category=category)

    await state.set_state(TXStates.amount)
    await c.message.edit_text(
        "Шаг 3 из 4.\n"
        "Введите сумму (например: 1500 или 1500.50):",
        reply_markup=cancel_kb
    )
    await c.answer()

# Обработчик ввода суммы транзакции
@dp.message(TXStates.amount)
async def tx_enter_amount(msg: types.Message, state: FSMContext):
    text = msg.text.strip()
    if text.lower() in ("↩️ Назад", "cancel_fsm"):
        await state.clear()
        user_id = await get_or_create_user(msg.from_user.id)
        await msg.answer("Отменено.", reply_markup=await main_kb(user_id))
        return

    try:
        amount = float(text.replace(",", "."))
        if amount <= 0:
            await msg.answer(
                "❌ Сумма должна быть положительным числом.\n"
                "Пример: 1500 или 1500.50",
                reply_markup=cancel_kb
            )
            return
    except ValueError:
        await msg.answer(
            "❌ Неверный формат суммы.\n"
            "Введите корректное число (например: 1500 или 1500.50):",
            reply_markup=cancel_kb
        )
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
        user_id = await get_or_create_user(msg.from_user.id)
        await msg.answer("Отменено.", reply_markup=await main_kb(user_id))
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
        reply_markup=await main_kb(user_id)
    )

    await state.clear()

# -----------------------------------------------------------------------------------------------------------------------
# 📜 История транзакций
# -----------------------------------------------------------------------------------------------------------------------
class TXEditStates(StatesGroup):
    edit_amount = State()
    edit_category = State()
    edit_description = State()

# Меню истории транзакций
@dp.callback_query(F.data == "menu_tx_history")
async def menu_tx_history(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    await show_transactions_history(c, user_id, 0)

# Показать историю транзакций с пагинацией
@dp.callback_query(F.data.startswith("tx_history:"))
async def show_transactions_history_cb(c: types.CallbackQuery):
    page = int(c.data.split(":")[1])
    user_id = await get_or_create_user(c.from_user.id)
    await show_transactions_history(c, user_id, page)

async def show_transactions_history(c: types.CallbackQuery, user_id: int, page: int = 0):
    """Показать страницу истории транзакций"""
    rows, total = await get_transactions_page(user_id, page, per_page=10)
    
    if not rows:
        await c.message.edit_text("📜 История транзакций пуста.", reply_markup=await main_kb(user_id))
        await c.answer()
        return
    
    text = "📜 *История транзакций*\n\n"
    for r in rows:
        emoji = "💰" if r["amount"] >= 0 else "💸"
        date = r["created_at"].strftime("%d.%m.%Y %H:%M")
        cat = r["category"] or "—"
        desc = f" — {r['description']}" if r['description'] else ""
        text += f"{emoji} {format_amount(r['amount'])} | {cat}{desc} | 📅 {date}\n"
    
    total_pages = (total + 9) // 10 if total > 0 else 1
    kb_buttons = []
    
    # Кнопки для каждой транзакции
    for r in rows[:5]:  # Показываем кнопки только для первых 5 на странице
        tx_id = r["id"]
        date_short = r["created_at"].strftime("%d.%m")
        cat = r["category"] or "—"
        # Сокращаем категорию если слишком длинная
        cat_short = cat[:12] + "..." if len(cat) > 15 else cat
        amount_str = format_amount(r['amount'])
        # Формируем текст кнопки: сумма | категория | дата
        button_text = f"✏️ {amount_str} | {cat_short} | {date_short}"
        # Ограничиваем длину текста кнопки (Telegram ограничение ~64 символа)
        if len(button_text) > 60:
            button_text = f"✏️ {amount_str} | {cat_short[:10]} | {date_short}"
        kb_buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"tx_edit:{tx_id}"
            )
        ])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"tx_history:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"tx_history:{page+1}"))
    if nav_buttons:
        kb_buttons.append(nav_buttons)
    
    kb_buttons.append([InlineKeyboardButton(text="↩️ Главное меню", callback_data="cancel_fsm")])
    
    text += f"*Страница {page+1} из {total_pages}*"
    await c.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    )
    await c.answer()

# Редактирование транзакции
@dp.callback_query(F.data.startswith("tx_edit:"))
async def tx_edit_menu(c: types.CallbackQuery):
    tx_id = int(c.data.split(":")[1])
    row = await db.fetchrow(
        "SELECT id, amount, category, description, created_at FROM transactions WHERE id=$1",
        tx_id
    )
    
    if not row:
        await c.answer("Транзакция не найдена")
        return
    
    emoji = "💰" if row["amount"] >= 0 else "💸"
    date = row["created_at"].strftime("%d.%m.%Y %H:%M")
    text = (
        f"✏️ *Редактирование транзакции*\n\n"
        f"{emoji} {format_amount(row['amount'])}\n"
        f"Категория: {row['category'] or '—'}\n"
        f"Описание: {row['description'] or '—'}\n"
        f"Дата: {date}\n\n"
        f"Что хотите изменить?"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Изменить сумму", callback_data=f"tx_edit_amount:{tx_id}")],
        [InlineKeyboardButton(text="📁 Изменить категорию", callback_data=f"tx_edit_cat:{tx_id}")],
        [InlineKeyboardButton(text="📝 Изменить описание", callback_data=f"tx_edit_desc:{tx_id}")],
        [InlineKeyboardButton(text="🗑 Удалить транзакцию", callback_data=f"tx_delete:{tx_id}")],
        [InlineKeyboardButton(text="↩️ Назад к истории", callback_data="menu_tx_history")]
    ])
    
    await c.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await c.answer()

# Удаление транзакции с подтверждением
@dp.callback_query(F.data.startswith("tx_delete:"))
async def tx_delete(c: types.CallbackQuery):
    tx_id = int(c.data.split(":")[1])
    row = await db.fetchrow(
        "SELECT amount, category, description FROM transactions WHERE id=$1",
        tx_id
    )
    
    if not row:
        await c.answer("Транзакция не найдена")
        return
    
    emoji = "💰" if row["amount"] >= 0 else "💸"
    text = (
        f"⚠️ *Подтверждение удаления*\n\n"
        f"Вы уверены, что хотите удалить транзакцию:\n"
        f"{emoji} {format_amount(row['amount'])} | {row['category'] or '—'}\n"
        f"{'Описание: ' + row['description'] if row['description'] else ''}\n\n"
        f"Это действие нельзя отменить."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"tx_delete_confirm:{tx_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"tx_edit:{tx_id}")]
    ])
    
    await c.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await c.answer()

@dp.callback_query(F.data.startswith("tx_delete_confirm:"))
async def tx_delete_confirm(c: types.CallbackQuery):
    tx_id = int(c.data.split(":")[1])
    await db.execute("DELETE FROM transactions WHERE id=$1", tx_id)
    await c.message.edit_text("✅ Транзакция удалена.", reply_markup=await main_kb(await get_or_create_user(c.from_user.id)))
    await c.answer()

# Изменение суммы транзакции
@dp.callback_query(F.data.startswith("tx_edit_amount:"))
async def tx_edit_amount_start(c: types.CallbackQuery, state: FSMContext):
    tx_id = int(c.data.split(":")[1])
    await state.update_data(tx_id=tx_id)
    await state.set_state(TXEditStates.edit_amount)
    await c.message.answer(
        "Введите новую сумму (например: 1500 или 1500.50):",
        reply_markup=cancel_kb
    )
    await c.answer()

@dp.message(TXEditStates.edit_amount)
async def tx_edit_amount_finish(msg: types.Message, state: FSMContext):
    try:
        amount = float(msg.text.replace(",", "."))
    except ValueError:
        await msg.answer(
            "❌ Неверный формат суммы.\n"
            "Введите корректное число (например: 1500 или 1500.50):",
            reply_markup=cancel_kb
        )
        return
    
    data = await state.get_data()
    tx_id = data["tx_id"]
    
    # Определяем знак на основе текущей транзакции
    current = await db.fetchrow("SELECT amount FROM transactions WHERE id=$1", tx_id)
    if current:
        # Сохраняем знак
        if current["amount"] < 0:
            amount = -abs(amount)
        else:
            amount = abs(amount)
    
    await db.execute("UPDATE transactions SET amount=$1 WHERE id=$2", amount, tx_id)
    await msg.answer("✅ Сумма обновлена.", reply_markup=await main_kb(await get_or_create_user(msg.from_user.id)))
    await state.clear()

# Изменение описания транзакции
@dp.callback_query(F.data.startswith("tx_edit_desc:"))
async def tx_edit_desc_start(c: types.CallbackQuery, state: FSMContext):
    tx_id = int(c.data.split(":")[1])
    await state.update_data(tx_id=tx_id)
    await state.set_state(TXEditStates.edit_description)
    await c.message.answer(
        "Введите новое описание (или '-' для удаления):",
        reply_markup=cancel_kb
    )
    await c.answer()

@dp.message(TXEditStates.edit_description)
async def tx_edit_desc_finish(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    tx_id = data["tx_id"]
    description = None if msg.text.strip() == "-" else msg.text.strip()
    
    await db.execute("UPDATE transactions SET description=$1 WHERE id=$2", description, tx_id)
    await msg.answer("✅ Описание обновлено.", reply_markup=await main_kb(await get_or_create_user(msg.from_user.id)))
    await state.clear()

# Изменение категории транзакции
@dp.callback_query(F.data.startswith("tx_edit_cat:"))
async def tx_edit_cat_start(c: types.CallbackQuery, state: FSMContext):
    tx_id = int(c.data.split(":")[1])
    row = await db.fetchrow("SELECT amount FROM transactions WHERE id=$1", tx_id)
    
    if not row:
        await c.answer("Транзакция не найдена")
        return
    
    await state.update_data(tx_id=tx_id)
    
    # Определяем тип транзакции
    if row["amount"] >= 0:
        kb = build_categories_kb(income_emojis)
        text = "Выберите новую категорию дохода:"
    else:
        kb = build_categories_kb(expense_emojis)
        text = "Выберите новую категорию расхода:"
    
    await c.message.answer(text, reply_markup=kb)
    await state.set_state(TXEditStates.edit_category)
    await c.answer()

@dp.callback_query(TXEditStates.edit_category, F.data.startswith("tx_cat:"))
async def tx_edit_cat_finish(c: types.CallbackQuery, state: FSMContext):
    category = c.data.split("tx_cat:")[1]
    data = await state.get_data()
    tx_id = data["tx_id"]
    
    await db.execute("UPDATE transactions SET category=$1 WHERE id=$2", category, tx_id)
    await c.message.answer("✅ Категория обновлена.", reply_markup=await main_kb(await get_or_create_user(c.from_user.id)))
    await state.clear()
    await c.answer()

# -----------------------------------------------------------------------------------------------------------------------
# 🎯 Мои цели
# -----------------------------------------------------------------------------------------------------------------------
class GOALStates(StatesGroup):
    target = State()
    title = State()
    description = State()

class GOAL_EDIT(StatesGroup):
    edit_title = State()
    edit_target = State()
    edit_desc = State()

def goals_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Новая цель", callback_data="goal_new")],
            [InlineKeyboardButton(text="✏️ Обновить цели", callback_data="goal_update_list")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="cancel_fsm")]
        ]
    )

def goal_edit_kb(goal_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"goal_edit_title:{goal_id}")],
            [InlineKeyboardButton(text="💰 Изменить сумму", callback_data=f"goal_edit_target:{goal_id}")],
            [InlineKeyboardButton(text="📄 Изменить описание", callback_data=f"goal_edit_desc:{goal_id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"goal_delete:{goal_id}")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="goal_update_list")]
        ]
    )

# Форматирование и прогресс цели

async def get_net_capital(user_id: int) -> float:
    # Суммарные активы
    assets = await db.fetch("""
        SELECT v.amount 
        FROM assets a
        JOIN LATERAL (
            SELECT amount FROM asset_values WHERE asset_id = a.id ORDER BY created_at DESC LIMIT 1
        ) v ON TRUE
        WHERE a.user_id=$1
    """, user_id)

    total_assets = sum([float(a["amount"]) for a in assets]) if assets else 0

    # Суммарные долги
    liabs = await db.fetch("""
        SELECT v.amount 
        FROM liabilities l
        JOIN LATERAL (
            SELECT amount FROM liability_values WHERE liability_id = l.id ORDER BY created_at DESC LIMIT 1
        ) v ON TRUE
        WHERE l.user_id=$1
    """, user_id)

    total_liabs = sum([float(l["amount"]) for l in liabs]) if liabs else 0

    return total_assets - total_liabs

# "Мои цели" → показываем текущие цели + меню
@dp.callback_query(F.data == "menu_goals")
async def menu_goals(c: types.CallbackQuery, state: FSMContext):
    user_id = await get_or_create_user(c.from_user.id)
    goals = await db.fetch("""
        SELECT id, title, target, current, description 
        FROM goals 
        WHERE user_id=$1 
        ORDER BY id
    """, user_id)

    if goals:
        net_cap = await get_net_capital(user_id)

        text = "🎯 *Ваши цели:*\n\n"

        for g in goals:
            title = g["title"]
            target = float(g["target"])

            percent = net_cap / target

            # целевой текст
            target_fmt = fmt(target) + " ₽"

            # процент
            if percent >= 1:
                progress = "Цель достигнута! 🎉"
            else:
                progress = f"{round(percent * 100)}%"

            text += f"• *{title}* — {target_fmt} ({progress})\n"

    else:
        text = "У вас пока нет целей."

    await c.message.edit_text(
        text + "\n\nЧто хотите сделать?",
        reply_markup=goals_menu_kb(),
        parse_mode="Markdown"
    )
    await c.answer()
    
# Шаг 1 — сумма:
@dp.callback_query(F.data == "goal_new")
async def goal_new_start(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(GOALStates.target)
    await c.message.edit_text("Введите сумму цели:", reply_markup=cancel_kb)
    await c.answer()
    
# Шаг 2 — название:
@dp.message(GOALStates.target)
async def goal_target(msg: types.Message, state: FSMContext):
    try:
        target = float(msg.text.replace(",", "."))
    except:
        await msg.answer("Введите корректную сумму.")
        return

    await state.update_data(target=target)
    await state.set_state(GOALStates.title)
    await msg.answer("Введите название цели:", reply_markup=cancel_kb)

# Шаг 3 — описание (необязательно):
@dp.message(GOALStates.title)
async def goal_title(msg: types.Message, state: FSMContext):
    await state.update_data(title=msg.text.strip())
    await state.set_state(GOALStates.description)
    await msg.answer("Введите описание цели (можно пропустить):", reply_markup=cancel_kb)

# Создание цели:
@dp.message(GOALStates.description)
async def goal_description(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = await get_or_create_user(msg.from_user.id)

    await db.execute(
        """INSERT INTO goals (user_id, target, current, title, description, created_at)
           VALUES ($1,$2,0,$3,$4,NOW())""",
        user_id, data["target"], data["title"], msg.text.strip()
    )

    user_id = await get_or_create_user(msg.from_user.id)
    await msg.answer("🎯 Цель успешно создана!", reply_markup=await main_kb(user_id))
    await state.clear()

# Кнопка "Обновить цели"
@dp.callback_query(F.data == "goal_update_list")
async def goals_update_list(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)

    goals = await db.fetch("""
        SELECT id, title, target, current, description
        FROM goals
        WHERE user_id=$1
        ORDER BY id
    """, user_id)

    if not goals:
        await c.message.edit_text("У вас пока нет целей.", reply_markup=goals_menu_kb())
        return

    # считаем капитал
    net_cap = await get_net_capital(user_id)

    def fmt(x: float) -> str:
        return f"{int(x):,}".replace(",", " ")

    text = "🎯 *Ваши цели:*\n\n"

    kb_buttons = []

    for g in goals:
        gid = g["id"]
        title = g["title"]
        target = float(g["target"])

        percent = net_cap / target
        target_fmt = fmt(target) + " ₽"

        # форматируем прогресс
        if percent >= 1:
            progress = "Цель достигнута! 🎉"
        else:
            progress = f"{round(percent * 100)}%"

        text += f"• *{title}* — {target_fmt} ({progress})\n"

        # кнопка для выбора цели
        kb_buttons.append([
            InlineKeyboardButton(
                text=f"{title}",
                callback_data=f"goal_edit:{gid}"
            )
        ])

    # добавляем кнопку назад
    kb_buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="menu_goals")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    await c.message.edit_text(
        text + "\nВыберите цель для редактирования:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await c.answer()
    
# Редактирование цели    
@dp.callback_query(F.data.startswith("goal_edit:"))
async def goal_edit(c: types.CallbackQuery):
    goal_id = int(c.data.split(":")[1])
    row = await db.fetchrow("SELECT * FROM goals WHERE id=$1", goal_id)

    text = (f"🎯 *{row['title']}*\n"
            f"Цель: {row['current']:,} / {row['target']:,} ₽\n\n"
            f"Описание: {row['description'] or '—'}")

    await c.message.edit_text(text, reply_markup=goal_edit_kb(goal_id), parse_mode="Markdown")
    await c.answer()

# Изменить название
@dp.callback_query(F.data.startswith("goal_edit_title:"))
async def goal_edit_title_start(c: types.CallbackQuery, state: FSMContext):
    gid = int(c.data.split(":")[1])
    await state.update_data(goal_id=gid)
    await state.set_state(GOAL_EDIT.edit_title)
    await c.message.edit_text("Введите новое название:", reply_markup=cancel_kb)
    await c.answer()

@dp.message(GOAL_EDIT.edit_title)
async def goal_edit_title_finish(msg: types.Message, state: FSMContext):
    gid = (await state.get_data())["goal_id"]
    await db.execute("UPDATE goals SET title=$1, updated_at=NOW() WHERE id=$2",
                     msg.text.strip(), gid)
    user_id = await get_or_create_user(msg.from_user.id)
    await msg.answer("Название обновлено!", reply_markup=await main_kb(user_id))
    await state.clear()    
    
# Изменить сумму 
@dp.callback_query(F.data.startswith("goal_edit_target:"))
async def goal_edit_target_start(c: types.CallbackQuery, state: FSMContext):
    gid = int(c.data.split(":")[1])
    await state.update_data(goal_id=gid)
    await state.set_state(GOAL_EDIT.edit_target)
    await c.message.edit_text("Введите новую сумму цели:", reply_markup=cancel_kb)
    await c.answer()

@dp.message(GOAL_EDIT.edit_target)
async def goal_edit_target_finish(msg: types.Message, state: FSMContext):
    try:
        target = float(msg.text.replace(",", "."))
    except:
        await msg.answer("Введите корректное число.")
        return

    gid = (await state.get_data())["goal_id"]
    await db.execute("UPDATE goals SET target=$1, updated_at=NOW() WHERE id=$2",
                     target, gid)
    user_id = await get_or_create_user(msg.from_user.id)
    await msg.answer("Сумма цели обновлена.", reply_markup=await main_kb(user_id))
    await state.clear()

# Изменить описание    
@dp.callback_query(F.data.startswith("goal_edit_desc:"))
async def goal_edit_desc_start(c: types.CallbackQuery, state: FSMContext):
    gid = int(c.data.split(":")[1])
    await state.update_data(goal_id=gid)
    await state.set_state(GOAL_EDIT.edit_desc)
    await c.message.edit_text("Введите новое описание:", reply_markup=cancel_kb)
    await c.answer()
    
@dp.message(GOAL_EDIT.edit_desc)
async def goal_edit_desc_finish(msg: types.Message, state: FSMContext):
    gid = (await state.get_data())["goal_id"]
    await db.execute("UPDATE goals SET description=$1, updated_at=NOW() WHERE id=$2",
                     msg.text.strip(), gid)
    user_id = await get_or_create_user(msg.from_user.id)
    await msg.answer("Описание обновлено.", reply_markup=await main_kb(user_id))
    await state.clear()

# Удаление цели с подтверждением
@dp.callback_query(F.data.startswith("goal_delete:"))
async def goal_delete(c: types.CallbackQuery):
    gid = int(c.data.split(":")[1])
    row = await db.fetchrow("SELECT title FROM goals WHERE id=$1", gid)
    
    if not row:
        await c.answer("Цель не найдена")
        return
    
    # Показываем подтверждение
    await c.message.edit_text(
        f"⚠️ *Подтверждение удаления*\n\n"
        f"Вы уверены, что хотите удалить цель:\n"
        f"*{row['title']}*?\n\n"
        f"Это действие нельзя отменить.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"goal_delete_confirm:{gid}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"goal_edit:{gid}")]
        ])
    )
    await c.answer()

@dp.callback_query(F.data.startswith("goal_delete_confirm:"))
async def goal_delete_confirm(c: types.CallbackQuery):
    gid = int(c.data.split(":")[1])
    await db.execute("DELETE FROM goals WHERE id=$1", gid)
    user_id = await get_or_create_user(c.from_user.id)
    await c.message.edit_text("✅ Цель удалена.", reply_markup=await main_kb(user_id))
    await c.answer() 
 
 
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

    await message.answer("Цель добавлена.", reply_markup=await main_kb(user_id))
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
            user_id = await get_or_create_user(m.from_user.id)
            await m.answer("Отменено.", reply_markup=await main_kb(user_id))
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
            user_id = await get_or_create_user(m.from_user.id)
            await m.answer("Отменено.", reply_markup=await main_kb(user_id))
            return True
        data = await state.get_data()
        target = data.get("target")
        title = text
        user_id = await get_or_create_user(m.from_user.id)
        await db.execute("INSERT INTO goals (user_id, target, current, title, created_at) VALUES ($1,$2,0,$3,NOW())",
                         user_id, target, title)
        await save_message(user_id, "system", f"Создана цель: {title} на {target}₽")
        await m.answer("Цель добавлена ✅", reply_markup=await main_kb(user_id))
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

async def render_capital_text(user_id: int) -> str:
    assets = await get_assets_list(user_id)
    liabs = await get_liabilities_list(user_id)

    total_assets = sum(x["amount"] for x in assets)
    total_liabs = sum(x["amount"] for x in liabs)
    net_capital = total_assets - total_liabs

    net_emoji = "🟢" if net_capital >= 0 else "🔴"

    text = "💰 *Активы:*\n"
    if assets:
        for a in assets:
            text += f"• {a['type']} — {fmt(a['amount'])} ₽ ({a['title']})\n"
    else:
        text += "• Нет активов\n"

    text += "\n💸 *Долги:*\n"
    if liabs:
        for l in liabs:
            text += f"• {l['type']} — {fmt(l['amount'])} ₽ ({l['title']})\n"
    else:
        text += "• Нет долгов\n"

    text += f"\n*Чистый капитал: {net_emoji} {fmt(net_capital)} ₽*"

    return text


@dp.callback_query(F.data == "menu_capital")
async def main_capital_menu(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)

    text = await render_capital_text(user_id)
    text += "\n\nЧто хотите сделать?"

    await c.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=capital_kb
    )
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
        reply_markup=await main_kb(user_id)
    )

    await state.clear()


# -------- UPDATE ASSET --------

@dp.callback_query(F.data == "asset_update_list")
async def asset_update_list(c: types.CallbackQuery, state: FSMContext):
    user_id = await get_or_create_user(c.from_user.id)
    assets = await get_assets_list(user_id)

    if not assets:
        await c.message.answer("Активов нет. Добавьте актив.", reply_markup=await main_kb(user_id))
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
    await c.message.edit_text("Введите новую стоимость актива (0, если хотите удалить):", reply_markup=cancel_kb)
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

    user_id = await get_or_create_user(msg.from_user.id)
    await msg.answer(
        f"Стоимость обновлена: {int(amount):,} ₽",
        reply_markup=await main_kb(user_id)
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

    await msg.answer("Долг добавлен.", reply_markup=await main_kb(user_id))
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
    await c.message.edit_text("Введите новую сумму долга (0, если хотите удалить):", reply_markup=cancel_kb)
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

    user_id = await get_or_create_user(msg.from_user.id)
    await msg.answer(
        f"Сумма долга обновлена: {int(amount):,} ₽",
        reply_markup=await main_kb(user_id)
    )
    await state.clear()


# -----------------------------------------------------------------------------------------------------------------------
# 📈 Отчеты
# -----------------------------------------------------------------------------------------------------------------------
# ---------- Вспомогательные функции ----------


async def get_goals_text(user_id: int) -> str:
    """Красивый список целей — как ты просил."""
    goals = await db.fetch("SELECT title, target, current FROM goals WHERE user_id=$1", user_id)
    if not goals:
        return "🎯 *Ваши цели:* \n• Нет целей\n"

    text = "🎯 *Ваши цели:*\n\n"
    assets = await get_assets_list(user_id)
    liabs = await get_liabilities_list(user_id)
    net_capital = sum(a["amount"] for a in assets) - sum(l["amount"] for l in liabs)

    for g in goals:
        title = g["title"]
        target = g["target"]
        if target <= 0:
            text += f"• {title} — некорректная цель\n"
            continue

        pct = net_capital / target * 100
        pct_int = int(pct)

        if pct >= 100:
            text += f"• {title} — {fmt(target)} ₽ *(Цель достигнута!)*\n"
        else:
            text += f"• {title} — {fmt(target)} ₽ ({pct_int}%)\n"

    return text


# ---------------------------------------------------------
# 1. Текстовая статистика по доходам и расходам
# ---------------------------------------------------------
async def build_text_stats(user_id: int) -> str:
    since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = await db.fetch(
        """
        SELECT amount, category, created_at
        FROM transactions
        WHERE user_id=$1 AND created_at >= $2
        ORDER BY created_at ASC
        """,
        user_id,
        since,
    )

    if not rows:
        return "📊 *Статистика за текущий месяц:*\nНет транзакций.\n"

    income_by_cat = {}
    expense_by_cat = {}

    for r in rows:
        amount = float(r["amount"])
        cat = r["category"] or "—"
        if amount >= 0:
            income_by_cat[cat] = income_by_cat.get(cat, 0) + amount
        else:
            expense_by_cat[cat] = expense_by_cat.get(cat, 0) + (-amount)

    total_income = sum(income_by_cat.values())
    total_expense = sum(expense_by_cat.values())

    text = "📊 *Статистика (текущий месяц):*\n"
    text += f"*Доходы всего:* {fmt(total_income)} ₽\n"
    text += f"*Расходы всего:* {fmt(total_expense)} ₽\n\n"

    if income_by_cat:
        text += "💰 *Доходы по категориям:*\n"
        for cat, val in sorted(income_by_cat.items(), key=lambda x: -x[1]):
            emoji = CATEGORY_EMOJI.get(cat, "❓")
            text += f"{emoji} {cat}: {fmt(val)} ₽\n"
        text += "\n"

    if expense_by_cat:
        text += "💸 *Расходы по категориям:*\n"
        for cat, val in sorted(expense_by_cat.items(), key=lambda x: -x[1]):
            emoji = CATEGORY_EMOJI.get(cat, "❓")
            text += f"{emoji} {cat}: {fmt(val)} ₽\n"

    return text


# ---------------------------------------------------------
# 2. Donut расходов
# ---------------------------------------------------------
async def create_expense_donut(user_id: int):
    start_month = datetime(now.year, now.month, 1)

    rows = await db.fetch(
        "SELECT amount, category FROM transactions WHERE user_id=$1 AND created_at >= $2",
        user_id,
        start_month,
    )
    if not rows:
        return None

    by_cat = {}
    for r in rows:
        amount = float(r["amount"])
        if amount >= 0:
            continue
        cat = r["category"] or "—"
        by_cat[cat] = by_cat.get(cat, 0) + (-amount)

    if not by_cat:
        return None

    total_expense = sum(by_cat.values())
    threshold = total_expense * 0.05

    large_cats = {k: v for k, v in by_cat.items() if v >= threshold}
    small_sum = sum(v for v in by_cat.values() if v < threshold)
    if small_sum > 0:
        large_cats["Прочее"] = small_sum

    labels = list(large_cats.keys())
    sizes = list(large_cats.values())

    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct="%1.1f%%", startangle=90, pctdistance=0.85
    )

    centre_circle = plt.Circle((0, 0), 0.70, fc="white")
    fig.gca().add_artist(centre_circle)

    ax.text(
        0,
        0,
        f"{total_expense:,.0f}₽",
        ha="center",
        va="center",
        fontsize=18,
        fontweight="bold",
    )

    ax.set_title("Расходы за месяц", y=1.05, fontsize=14)

    fname = f"{TMP_DIR}/donut_expense_{user_id}_{int(datetime.now().timestamp())}.png"
    plt.savefig(fname)
    plt.close(fig)
    return fname


# ---------------------------------------------------------
# 3. Прогресс целей (bar chart)
# ---------------------------------------------------------
async def create_goals_progress_bar(user_id: int):
    goals = await db.fetch("SELECT title, target, current FROM goals WHERE user_id=$1", user_id)
    if not goals:
        return None

    titles = []
    progress = []

    assets = await get_assets_list(user_id)
    liabs = await get_liabilities_list(user_id)
    net_capital = sum(a["amount"] for a in assets) - sum(l["amount"] for l in liabs)

    for g in goals:
        titles.append(g["title"])
        if g["target"] <= 0:
            progress.append(0)
        else:
            pct = min(int(net_capital / g["target"] * 100), 100)
            progress.append(pct)

    fig, ax = plt.subplots(figsize=(8, len(goals) * 0.6 + 1))
    y = np.arange(len(goals))

    ax.barh(y, progress, color="green")
    ax.barh(y, [100 - p for p in progress], left=progress, color="lightgray")

    ax.set_yticks(y)
    ax.set_yticklabels(titles)
    ax.invert_yaxis()

    for i, p in enumerate(progress):
        ax.text(p + 2, i, f"{p}%", va="center")

    ax.set_xlim(0, 110)
    ax.set_title("Прогресс по целям")

    fname = f"{TMP_DIR}/goals_progress_{user_id}_{int(datetime.now().timestamp())}.png"
    plt.savefig(fname)
    plt.close(fig)
    return fname
# ---------------------------------------------------------
# 4. История портфеля (финансовый путь по неделям)
# ---------------------------------------------------------
async def create_portfolio_history_chart(user_id: int, weeks: int = 26):
    cutoff = now_moscow.replace(tzinfo=None) - timedelta(weeks=weeks)
    
    # Генерируем список воскресений (концов недель) от cutoff до сегодня
    current_date = cutoff.date()
    end_date = now_moscow.replace(tzinfo=None).date()
    sundays = []
    
    # Находим первое воскресенье после cutoff
    days_until_sunday = (6 - current_date.weekday()) % 7
    if days_until_sunday == 0 and current_date.weekday() == 6:
        first_sunday = current_date
    else:
        first_sunday = current_date + timedelta(days=days_until_sunday)
    
    # Собираем все воскресенья до сегодня
    sunday = first_sunday
    while sunday <= end_date:
        sundays.append(sunday)
        sunday += timedelta(days=7)
    
    if not sundays:
        return None
    
    # Для каждого воскресенья получаем баланс активов и долгов на конец этого дня
    weekly_data = []
    
    for sunday_date in sundays:
        # Получаем все активы с последним значением на дату конца недели или раньше
        asset_rows = await db.fetch(
            """
            SELECT a.id, COALESCE(v.amount, 0) as amount
            FROM assets a
            LEFT JOIN LATERAL (
                SELECT amount
                FROM asset_values
                WHERE asset_id = a.id
                  AND created_at::date <= $1
                ORDER BY created_at DESC
                LIMIT 1
            ) v ON TRUE
            WHERE a.user_id = $2
            """,
            sunday_date,
            user_id,
        )
        
        # Получаем все долги с последним значением на дату конца недели или раньше
        liab_rows = await db.fetch(
            """
            SELECT l.id, COALESCE(v.amount, 0) as amount
            FROM liabilities l
            LEFT JOIN LATERAL (
                SELECT amount
                FROM liability_values
                WHERE liability_id = l.id
                  AND created_at::date <= $1
                ORDER BY created_at DESC
                LIMIT 1
            ) v ON TRUE
            WHERE l.user_id = $2
            """,
            sunday_date,
            user_id,
        )
        
        total_assets = sum(float(r["amount"]) for r in asset_rows if r["amount"] and float(r["amount"]) > 0)
        total_liabs = sum(float(r["amount"]) for r in liab_rows if r["amount"] and float(r["amount"]) > 0)
        
        weekly_data.append({
            "date": sunday_date,
            "assets": total_assets,
            "liabs": total_liabs,
            "net": total_assets - total_liabs
        })
    
    if not weekly_data:
        return None
    
    # Создаем DataFrame
    weekly = pd.DataFrame(weekly_data)
    weekly["created_at"] = pd.to_datetime(weekly["date"])
    
    dates = weekly["created_at"]
    assets_vals = weekly["assets"]
    liabs_vals = weekly["liabs"]
    net_vals = weekly["net"]

    dates = weekly["created_at"]
    assets_vals = weekly["amount_assets"]
    liabs_vals = weekly["amount_liabs"]
    net_vals = assets_vals - liabs_vals

    # --- График: столбцы активов/долгов + линия Net Worth ---
    fig, ax = plt.subplots(figsize=(14, 6))
    x = np.arange(len(dates))
    bar_width = 0.6

    # Активы (зелёные столбцы)
    bars_assets = ax.bar(
        x,
        assets_vals,
        bar_width,
        color="#2ecc71",
        label="Активы",
        zorder=2,
    )

    # Долги (красные столбцы вниз)
    bars_liabs = ax.bar(
        x,
        -liabs_vals,
        bar_width,
        color="#e74c3c",
        label="Долги",
        zorder=2,
    )

    # Линия Net Worth
    line_net, = ax.plot(
        x,
        net_vals,
        color="#8e44ad",
        marker="o",
        linestyle="--",
        linewidth=2,
        label="Net Worth",
        zorder=3,
    )

    # Подписи по оси X: конец недели в формате "ДД.ММ.ГГ"
    ax.set_xticks(x)
    ax.set_xticklabels(
        [d.strftime("%d.%m.%y") for d in dates],
        rotation=45,
        ha="right",
    )

    # Сетка и оси
    ax.set_ylabel("Сумма (₽)")
    ax.set_title("Финансовый путь (по неделям)")
    ax.grid(True, axis="y", linestyle="--", alpha=0.3, zorder=1)

    # Делимитеры по Y чуть с запасом
    min_y = min(
        -liabs_vals.min() if len(liabs_vals) > 0 else 0,
        net_vals.min() if len(net_vals) > 0 else 0,
    )
    max_y = max(
        assets_vals.max() if len(assets_vals) > 0 else 0,
        net_vals.max() if len(net_vals) > 0 else 0,
    )
    margin = (max_y - min_y) * 0.1 if max_y != min_y else 1
    ax.set_ylim(min_y - margin, max_y + margin)

    # Формат чисел как в других отчетах
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, pos: fmt(x) + " ₽")
    )

    # Подписи над/под столбцами активов и долгов
    for rect in bars_assets:
        height = rect.get_height()
        if height <= 0:
            continue
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            height + margin * 0.02,
            fmt(height),
            ha="center",
            va="bottom",
            fontsize=8,
            color="#145a32",
        )

    for rect in bars_liabs:
        height = rect.get_height()
        if height >= 0:
            continue
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            height - margin * 0.02,
            "-" + fmt(abs(height)),
            ha="center",
            va="top",
            fontsize=8,
            color="#922b21",
        )

    # Подписи на линии Net Worth
    for xi, yi in zip(x, net_vals):
        ax.text(
            xi,
            yi + margin * 0.03,
            fmt(yi),
            ha="center",
            va="bottom",
            fontsize=8,
            color="#4a235a",
        )

    # Легенда вне области графика
    legend = ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
        frameon=False,
    )

    fig.tight_layout()

    fname = f"{TMP_DIR}/portfolio_history_{user_id}_{int(datetime.now().timestamp())}.png"
    plt.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    return fname

# ---------------------------------------------------------
# ОБЪЕДИНЁННЫЙ ОБРАБОТЧИК ОТЧЁТОВ (3 сообщения)
# ---------------------------------------------------------
@dp.callback_query(F.data == "menu_charts")
async def menu_charts(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    
    # Показываем индикатор прогресса
    await c.message.answer("⏳ Генерирую отчет...")
    await bot.send_chat_action(c.message.chat.id, "typing")

    # 1. Статистика + donut
    stats_text = await build_text_stats(user_id)
    img_donut = await create_expense_donut(user_id)

    if img_donut:
        await c.message.answer(stats_text, parse_mode="Markdown")
        await c.message.answer_photo(
            types.FSInputFile(img_donut),
            caption="Траты за месяц",
        )
        os.remove(img_donut)
    else:
        await c.message.answer(stats_text, parse_mode="Markdown")

    # 2. Цели (текст) + график прогресса
    goals_text = await get_goals_text(user_id)
    img_goals = await create_goals_progress_bar(user_id)

    if img_goals:
        await c.message.answer(goals_text, parse_mode="Markdown")
        await c.message.answer_photo(
            types.FSInputFile(img_goals),
            caption="Прогресс целей",
        )
        os.remove(img_goals)
    else:
        await c.message.answer(goals_text, parse_mode="Markdown")

    # 3. Активы/долги (render_capital_text) + история портфеля по неделям
    cap_text = await render_capital_text(user_id)
    img_hist = await create_portfolio_history_chart(user_id)

    if img_hist:
        await c.message.answer(cap_text, parse_mode="Markdown")
        await c.message.answer_photo(
            types.FSInputFile(img_hist),
            caption="Динамика чистого капитала по неделям",
        )
        os.remove(img_hist)
    else:
        await c.message.answer(cap_text, parse_mode="Markdown", reply_markup=await main_kb(user_id))
    
    # После всех отчетов показываем главное меню
    await c.message.answer("📊 Отчет сгенерирован", reply_markup=await main_kb(user_id))

    await c.answer()
# -----------------------------------------------------------------------------------------------------------------------
# 💡 Личная консультация
# -----------------------------------------------------------------------------------------------------------------------


# Кнопка консультация
@dp.callback_query(F.data == "menu_consult")
async def cb_menu_consult(c: types.CallbackQuery):
    user_id = await get_or_create_user(c.from_user.id)
    await c.answer()  # Отвечаем на callback сразу
    
    # Отправляем сообщение о начале анализа
    status_msg = await c.message.answer("🤔 Анализирую ваши финансы... (это займет несколько секунд)")
    await bot.send_chat_action(c.message.chat.id, "typing")
    
    try:
        ans = await generate_consultation(user_id)
        # Редактируем сообщение с результатом и добавляем главное меню
        user_id = await get_or_create_user(c.from_user.id)
        await status_msg.edit_text(ans, parse_mode="Markdown", reply_markup=await main_kb(user_id))
    except Exception as e:
        print(f"Ошибка при генерации консультации: {e}")
        await status_msg.edit_text(
            f"❌ Произошла ошибка при генерации консультации.\n"
            f"Попробуйте позже или обратитесь в поддержку.\n\n"
            f"Ошибка: {str(e)}"
        )

@dp.message(Command("consult"))
async def cmd_consult(m: types.Message):
    user_id = await get_or_create_user(m.from_user.id)
    status_msg = await m.answer("🤔 Анализирую ваши финансы... (это займет несколько секунд)")
    await bot.send_chat_action(m.chat.id, "typing")
    
    try:
        ans = await generate_consultation(user_id)
        await status_msg.edit_text(ans, parse_mode="Markdown", reply_markup=await main_kb(user_id))
    except Exception as e:
        print(f"Ошибка при генерации консультации: {e}")
        await status_msg.edit_text(
            f"❌ Произошла ошибка при генерации консультации.\n"
            f"Попробуйте позже или обратитесь в поддержку.\n\n"
            f"Ошибка: {str(e)}"
        )



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
    s = ""
    if rows:
        s = "Последние транзакции:\n"
        for r in rows:
            ts = r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else ""
            s += f"- {r['amount']}₽ | {r.get('category') or '-'} | {r.get('description') or ''} | {ts}\n"
    else:
        s = "У пользователя нет транзакций.\n"
    
    goals = await db.fetch("SELECT title, target, current, created_at FROM goals WHERE user_id=$1", user_id)
    if goals:
        s += "\nЦели:\n"
        for g in goals:
            s += f"- {g.get('title','Цель')}: {g['current']}/{g['target']} ₽\n"
    
    # Получаем активы с последними значениями
    assets = await get_assets_list(user_id)
    if assets:
        total_assets = sum([a["amount"] for a in assets])
        s += f"\nАктивы (итого {total_assets}₽):\n"
        for a in assets:
            s += f"- {a['title']} ({a['type']}): {a['amount']}₽\n"
    
    # Получаем долги с последними значениями
    liabs = await get_liabilities_list(user_id)
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
    try:
        finance_snapshot = await analyze_user_finances_text(user_id)
        
        # Если нет данных, возвращаем базовую консультацию
        if not finance_snapshot or "нет транзакций" in finance_snapshot.lower() and "нет активов" in finance_snapshot.lower():
            return (
                "📊 *Ваша финансовая консультация*\n\n"
                "У вас пока нет финансовых данных для анализа.\n\n"
                "Рекомендации для начала:\n"
                "1. Начните вести учет доходов и расходов\n"
                "2. Добавьте информацию о ваших активах\n"
                "3. Установите финансовые цели\n"
                "4. Регулярно обновляйте данные\n\n"
                "После добавления данных вы получите персональные рекомендации!"
            )
        
        system_prompt = (
            "Ты — персональный финансовый консультант.\n"
            "Проанализируй финансовые данные пользователя и подготовь структурированные, "
            "понятные и практичные рекомендации.\n\n"
        
            "ОБЯЗАТЕЛЬНО проанализируй и используй в выводах:\n"
            "1. ТРАНЗАКЦИИ — доходы и расходы, основные паттерны, категории с наибольшими тратами "
            "(указывай суммы и примеры).\n"
            "2. ЦЕЛИ — финансовые цели пользователя и текущий прогресс по ним.\n"
            "3. АКТИВЫ — текущее состояние капитала и источники дохода.\n"
            "4. ДОЛГИ — обязательства, их размер и влияние на бюджет.\n\n"
        
            "ФОРМАТ ОТВЕТА (строго соблюдай структуру):\n\n"
        
            "📊 *Текущее финансовое положение*\n"
            "(краткая сводка в 2-3 предложениях)\n\n"
        
            "💰 *Доходы и расходы*\n"
            "• Доходы: [сумма] ₽ ([категории])\n"
            "• Расходы: [сумма] ₽ ([топ-3 категории с суммами])\n"
            "• Остаток: [сумма] ₽\n\n"
        
            "🎯 *Финансовые цели*\n"
            "(список целей с прогрессом в формате: Название — [текущее]/[целевое] ₽ ([процент]%))\n\n"
        
            "💼 *Активы и долги*\n"
            "• Активы: [сумма] ₽ ([список])\n"
            "• Долги: [сумма] ₽ ([список])\n"
            "• Чистый капитал: [сумма] ₽\n\n"
        
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        
            "📋 *Практический план действий*\n\n"
        
            "*1️⃣ Ближайший месяц*\n"
            "• [Конкретное действие 1 с суммой экономии]\n"
            "• [Конкретное действие 2 с суммой экономии]\n"
            "• [Конкретное действие 3 с суммой экономии]\n\n"
        
            "*2️⃣ Горизонт 6 месяцев*\n"
            "• [Шаг 1 для долгосрочных целей]\n"
            "• [Шаг 2 для работы с инвестициями/долгами]\n"
            "• [Шаг 3 для увеличения доходов]\n\n"
        
            "*3️⃣ Оптимизация бюджета*\n"
            "• [Категория 1]: сократить с [сумма] до [сумма] ₽ (экономия [сумма] ₽)\n"
            "• [Категория 2]: перераспределить [сумма] ₽ на [цель]\n"
            "• [Категория 3]: [конкретная рекомендация]\n\n"
        
            "*4️⃣ Резервный фонд*\n"
            "• Рекомендуемый размер: [сумма] ₽ (3-6 месячных расходов)\n"
            "• Откладывать: [сумма] ₽ ежемесячно\n"
            "• Срок накопления: [количество] месяцев\n"
            "• Приоритет: [высокий/средний/низкий] с учетом текущих долгов\n\n"
        
            "ТРЕБОВАНИЯ:\n"
            "- Используй Markdown форматирование (*жирный*, списки)\n"
            "- Каждый пункт на новой строке\n"
            "- Всегда указывай конкретные суммы\n"
            "- Избегай длинных абзацев — используй списки\n"
            "- Будь конкретным и практичным\n"
            "- Не используй общие фразы типа 'пересмотреть' без конкретики\n\n"
        
            "🚨 КРИТИЧЕСКИ ВАЖНО - ФОРМАТ ЧИСЕЛ (ОБЯЗАТЕЛЬНО СОБЛЮДАЙ):\n"
            "- ВСЕГДА используй формат с пробелами: 200 000 ₽, 1 500 000 ₽, 12 000 000 ₽\n"
            "- ЗАПРЕЩЕНО использовать научную нотацию (2.7E+5, 1.5E+4 - ЗАПРЕЩЕНО!)\n"
            "- ЗАПРЕЩЕНО использовать точки как разделители (12.000.000 - ЗАПРЕЩЕНО!)\n"
            "- ЗАПРЕЩЕНО показывать знаки после запятой (15.000 - ЗАПРЕЩЕНО!)\n"
            "- ПРАВИЛЬНО: 270 000 ₽ (не 2.7E+5, не 270000, не 270.000)\n"
            "- ПРАВИЛЬНО: 77 000 ₽ (не 7.7E+4, не 77000, не 77.000)\n"
            "- ПРАВИЛЬНО: 15 000 ₽ (не 1.5E+4, не 15000, не 15.000)\n"
            "- ПРАВИЛЬНО: 12 000 000 ₽ (не 12.000.000, не 12000000)\n"
            "- Всегда округляй до целых чисел, без десятичных знаков\n"
            "- Формат: [число с пробелами] ₽ (например: 200 000 ₽, 1 500 000 ₽)\n\n"
        
            "Отвечай на русском языке.\n"
            "Стиль — деловой, дружелюбный, понятный."
        )
        messages = [
            {"role":"system","content":system_prompt},
            {"role":"user","content":finance_snapshot}
        ]
        
        answer = await gigachat_request(messages)
        
        if not answer or len(answer.strip()) == 0:
            return "Извините, не удалось сгенерировать консультацию. Попробуйте позже."
        
        await save_message(user_id, "assistant", f"Consultation generated")
        await save_ai_cache(user_id, "CONSULT_REQUEST", finance_snapshot, answer)
        return answer
        
    except Exception as e:
        print(f"Ошибка при генерации консультации: {e}")
        import traceback
        traceback.print_exc()
        return (
            "❌ *Ошибка при генерации консультации*\n\n"
            "Извините, произошла техническая ошибка.\n"
            "Попробуйте позже или обратитесь в поддержку."
        )


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
    await m.answer("Неверная команда", reply_markup=await main_kb(user_id))

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
            if pie:
                await bot.send_photo(tg_id, types.FSInputFile(pie), caption="Расходы по категориям в текущем месяце")
                try: 
                    os.remove(pie)
                except: 
                    pass
            
            goals_img = await create_goals_progress_bar(user_id)
            if goals_img:
                await bot.send_photo(tg_id, types.FSInputFile(goals_img), caption="Прогресс по целям")
                try: 
                    os.remove(goals_img)
                except: 
                    pass
            
            portfolio_img = await create_portfolio_history_chart(user_id)
            if portfolio_img:
                await bot.send_photo(tg_id, types.FSInputFile(portfolio_img), caption="Динамика чистого капитала")
                try: 
                    os.remove(portfolio_img)
                except: 
                    pass
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


