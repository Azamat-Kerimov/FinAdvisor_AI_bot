import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
import os
from db import get_connection

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= FSM для транзакций =================
class TransactionStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_description = State()
    waiting_for_category = State()

# FSM для целей
class GoalStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_target_amount = State()

# Пример категорий
CATEGORIES = ["Продукты", "Транспорт", "Развлечения", "Коммуналка", "Другое"]

def categories_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIES:
        kb.add(InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}"))
    return kb

# ================= Команда /start =================
@dp.message(Command("start"))
async def start(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or "no_name"

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (tg_id, username) VALUES (%s, %s) "
            "ON CONFLICT (tg_id) DO NOTHING RETURNING id",
            (tg_id, username)
        )
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("Ошибка работы с БД:", repr(e))
        await message.answer("Ошибка при регистрации пользователя!")

    if result:
        await message.answer(f"Привет, {username}! Ты зарегистрирован в FinAdvisor.")
    else:
        await message.answer(f"Привет, {username}! Ты уже зарегистрирован.")

# ================= Команда /add_transaction =================
@dp.message(Command("add_transaction"))
async def add_transaction_start(message: types.Message, state: FSMContext):
    await message.answer("Введите сумму транзакции (например: 500)")
    await state.set_state(TransactionStates.waiting_for_amount)

@dp.message(TransactionStates.waiting_for_amount)
async def add_transaction_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        await state.update_data(amount=amount)
        await message.answer("Введите описание транзакции")
        await state.set_state(TransactionStates.waiting_for_description)
    except ValueError:
        await message.answer("Неверный формат суммы. Введите число, например: 500")

@dp.message(TransactionStates.waiting_for_description)
async def add_transaction_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Выберите категорию транзакции:", reply_markup=categories_keyboard())
    await state.set_state(TransactionStates.waiting_for_category)

@dp.callback_query(lambda c: c.data and c.data.startswith("cat_"))
async def add_transaction_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data[4:]
    data = await state.get_data()
    amount = data.get("amount")
    description = data.get("description")
    tg_id = callback.from_user.id

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, category, description) "
            "VALUES ((SELECT id FROM users WHERE tg_id=%s), %s, %s, %s)",
            (tg_id, amount, category, description)
        )
        conn.commit()
        cursor.close()
        conn.close()
        await callback.message.edit_text(f"Транзакция добавлена: {amount} ₽, {category}, {description}")
    except Exception as e:
        print("Ошибка при добавлении транзакции:", e)
        await callback.message.edit_text("Произошла ошибка при добавлении транзакции.")

    await state.clear()

# ================= Команда /add_goal =================
@dp.message(Command("add_goal"))
async def add_goal_start(message: types.Message, state: FSMContext):
    await message.answer("Введите название цели")
    await state.set_state(GoalStates.waiting_for_name)

@dp.message(GoalStates.waiting_for_name)
async def add_goal_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите целевую сумму цели (например: 80000)")
    await state.set_state(GoalStates.waiting_for_target_amount)

@dp.message(GoalStates.waiting_for_target_amount)
async def add_goal_amount(message: types.Message, state: FSMContext):
    try:
        target_amount = float(message.text)
        data = await state.get_data()
        name = data.get("name")
        tg_id = message.from_user.id

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO goals (user_id, name, target_amount, current_amount) "
            "VALUES ((SELECT id FROM users WHERE tg_id=%s), %s, %s, %s)",
            (tg_id, name, target_amount, 0)
        )
        conn.commit()
        cursor.close()
        conn.close()

        await message.answer(f"Цель добавлена: {name}, {target_amount} ₽")
    except ValueError:
        await message.answer("Неверный формат суммы. Введите число, например: 80000")
    except Exception as e:
        print("Ошибка при добавлении цели:", e)
        await message.answer("Произошла ошибка при добавлении цели.")

    await state.clear()

# ================= Команда /report =================
@dp.message(Command("report"))
async def report(message: types.Message):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT SUM(amount) as total FROM transactions WHERE user_id = (SELECT id FROM users WHERE tg_id=%s)",
            (message.from_user.id,)
        )
        total = cursor.fetchone()['total'] or 0

        cursor.execute(
            "SELECT name, current_amount, target_amount FROM goals WHERE user_id = (SELECT id FROM users WHERE tg_id=%s)",
            (message.from_user.id,)
        )
        goals = cursor.fetchall()

        cursor.close()
        conn.close()

        text = f"Ваши расходы: {total} ₽\nЦели:\n"
        if goals:
            for g in goals:
                text += f"- {g['name']}: {g['current_amount']} / {g['target_amount']} ₽\n"
        else:
            text += "Цели пока не добавлены."

        await message.answer(text)
    except Exception as e:
        print("Ошибка при формировании отчёта:", e)
        await message.answer("Произошла ошибка при формировании отчёта.")

# ================= Эхо на любое сообщение =================
@dp.message()
async def echo(message: types.Message):
    await message.answer(f"Вы написали: {message.text}")

# ================= Запуск бота =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
