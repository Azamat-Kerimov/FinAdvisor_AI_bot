# modules/handlers/assets.py
from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from modules.db import create_db_pool

cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="cancel_fsm")]])

class AssetStates(StatesGroup):
    amount = State()
    title = State()
    type = State()

async def register_handlers(dp, get_or_create_user, db_pool):
    @dp.message(Command("asset_add"))
    async def cmd_asset_add(message: types.Message, state: FSMContext):
        await state.set_state(AssetStates.amount)
        await message.answer("Введите сумму актива:", reply_markup=cancel_kb)

    @dp.message(AssetStates.amount)
    async def asset_amount(message: types.Message, state: FSMContext):
        try:
            a = float(message.text)
        except:
            await message.answer("Неверная сумма, попробуйте ещё раз:")
            return
        await state.update_data(amount=a)
        await state.set_state(AssetStates.title)
        await message.answer("Название актива (например: 'Текущий счет'):", reply_markup=cancel_kb)

    @dp.message(AssetStates.title)
    async def asset_title(message: types.Message, state: FSMContext):
        await state.update_data(title=message.text)
        await state.set_state(AssetStates.type)
        await message.answer("Тип (cash/deposit/invest):", reply_markup=cancel_kb)

    @dp.message(AssetStates.type)
    async def asset_type(message: types.Message, state: FSMContext):
        data = await state.get_data()
        user_id = await get_or_create_user(message.from_user.id)
        await db_pool.execute("INSERT INTO assets (user_id, title, amount, type, created_at) VALUES ($1,$2,$3,$4,NOW())",
                              user_id, data['title'], data['amount'], message.text)
        await message.answer("Актив добавлен ✅")
        await state.clear()

    # liabilities
    @dp.message(Command("debt_add"))
    async def cmd_debt_add(message: types.Message, state: FSMContext):
        await message.answer("Добавление долга: используйте /debt_add для запуска. Дальше аналогично asset_add.")
