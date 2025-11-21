from aiogram import F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from modules.db import db
from handlers import main_menu, AddTx

@dp.callback_query(F.data == "menu_add")
async def menu_add(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddTx.waiting_amount)
    await q.message.answer("Введите сумму расхода:")

@dp.message(AddTx.waiting_amount)
async def add_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
    except:
        await message.answer("Введите корректную сумму:")
        return

    await state.update_data(amount=amount)
    await state.set_state(AddTx.waiting_category)
    await message.answer("Введите категорию:")

@dp.message(AddTx.waiting_category)
async def add_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state(AddTx.waiting_desc)
    await message.answer("Введите описание:")

@dp.message(AddTx.waiting_desc)
async def add_desc(message: types.Message, state: FSMContext):
    user_id = await get_or_create_user(message.from_user.id)
    data = await state.get_data()

    await db.execute(
        "INSERT INTO transactions (user_id, amount, category, description) VALUES ($1,$2,$3,$4)",
        user_id, data["amount"], data["category"], message.text
    )

    await message.answer("Готово! Транзакция добавлена.", reply_markup=main_menu())
    await state.clear()
