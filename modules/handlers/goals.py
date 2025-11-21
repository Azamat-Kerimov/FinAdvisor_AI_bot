# modules/handlers/goals.py
from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from modules.utils import normalize_category

cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Отмена", callback_data="cancel_fsm")]
])

class GoalStates(StatesGroup):
    title = State()
    amount = State()

def register_goal_handlers(dp, get_or_create_user, db_pool, save_message):

    @dp.message(Command("goals"))
    async def cmd_goals(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)
        rows = await db_pool.fetch(
            "SELECT id, title, amount, progress FROM goals WHERE user_id=$1 ORDER BY id",
            user_id
        )

        if not rows:
            await message.answer("У вас ещё нет целей. Добавьте новую через /addgoal")
            return

        text = "🎯 Ваши цели:\n\n"
        for g in rows:
            text += f"• {g['title']} — {g['progress']} / {g['amount']}\n"

        await message.answer(text)

    @dp.message(Command("addgoal"))
    async def add_goal(message: types.Message, state: FSMContext):
        await state.set_state(GoalStates.title)
        await message.answer("Введите название цели:", reply_markup=cancel_kb)

    @dp.message(GoalStates.title)
    async def handle_title(message: types.Message, state: FSMContext):
        await state.update_data(title=message.text.strip())
        await state.set_state(GoalStates.amount)
        await message.answer("Введите сумму цели:", reply_markup=cancel_kb)

    @dp.message(GoalStates.amount)
    async def handle_amount(message: types.Message, state: FSMContext):
        try:
            amount = float(message.text.strip())
        except:
            await message.answer("Введите число. Попробуйте ещё раз.")
            return

        data = await state.get_data()
        title = data["title"]

        user_id = await get_or_create_user(message.from_user.id)

        await db_pool.execute(
            "INSERT INTO goals (user_id, title, amount, progress, created_at) VALUES ($1,$2,$3,0,NOW())",
            user_id, title, amount
        )

        await save_message(user_id, "system", f"Добавлена цель: {title} на сумму {amount}")

        await message.answer("Цель успешно добавлена 🎯")
        await state.clear()

    @dp.callback_query(lambda c: c.data == "cancel_fsm")
    async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await call.message.answer("Действие отменено.")
        await call.answer()
