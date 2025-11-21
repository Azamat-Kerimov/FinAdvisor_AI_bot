from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from modules.db import db
from handlers import main_menu, AddGoal

@dp.callback_query(F.data == "menu_goal")
async def menu_goal(q: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddGoal.waiting_target)
    await q.message.answer("Введите сумму цели:")

@dp.message(AddGoal.waiting_target)
async def goal_target(message: types.Message, state: FSMContext):
    try:
        target = float(message.text)
    except:
        await message.answer("Введите корректную сумму:")
        return

    await state.update_data(target=target)
    await state.set_state(AddGoal.waiting_title)
    await message.answer("Введите название цели:")

@dp.message(AddGoal.waiting_title)
async def goal_title(message: types.Message, state: FSMContext):
    user_id = await get_or_create_user(message.from_user.id)
    data = await state.get_data()

    await db.execute(
        "INSERT INTO goals (user_id, target, title) VALUES ($1,$2,$3)",
        user_id, data["target"], message.text
    )

    await message.answer("Цель добавлена.", reply_markup=main_menu())
    await state.clear()
