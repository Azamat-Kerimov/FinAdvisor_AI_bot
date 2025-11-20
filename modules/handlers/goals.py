# modules/handlers/goals.py
from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from modules.utils import normalize_category

cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Отмена", callback_data="cancel_fsm")]
])

class GoalStates(StatesGroup):
    waiting_target = State()
    waiting_title = State()

async def register_handlers(dp, get_or_create_user, db_pool):
    """
    Регистрирует обработчики для работы с целями:
    - /goal (через FSM)
    - /goals (список целей)
    - /goal_update <id> (обновить current)
    - /goal_remove <id>
    """

    @dp.message(Command("goal"))
    async def cmd_goal(message: types.Message, state: FSMContext):
        await state.set_state(GoalStates.waiting_target)
        await message.answer("Введите сумму цели (числом):", reply_markup=cancel_kb)

    @dp.message(GoalStates.waiting_target)
    async def goal_target(message: types.Message, state: FSMContext):
        txt = message.text.strip().replace(",", ".")
        try:
            target = float(txt)
        except:
            await message.answer("Неверная сумма, введите число:")
            return
        await state.update_data(target=target)
        await state.set_state(GoalStates.waiting_title)
        await message.answer("Введите название цели:", reply_markup=cancel_kb)

    @dp.message(GoalStates.waiting_title)
    async def goal_title(message: types.Message, state: FSMContext):
        data = await state.get_data()
        title = message.text.strip()
        user_id = await get_or_create_user(message.from_user.id)
        await db_pool.execute(
            "INSERT INTO goals (user_id, target, current, title, created_at) VALUES ($1,$2,0,$3,NOW())",
            user_id, data["target"], title
        )
        await message.answer("Цель добавлена ✅")
        await state.clear()

    @dp.message(Command("goals"))
    async def list_goals(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)
        rows = await db_pool.fetch("SELECT id, title, target, current, created_at FROM goals WHERE user_id=$1 ORDER BY id ASC", user_id)
        if not rows:
            await message.answer("У вас пока нет целей.")
            return
        text = "Ваши цели:\n\n"
        for r in rows:
            pct = int(round((float(r['current']) / float(r['target']))*100)) if r['target'] else 0
            status = "✅" if pct >= 100 else f"{pct}%"
            text += f"ID:{r['id']} • {r['title']} — {int(r['current'])}/{int(r['target'])}₽ ({status})\n"
        await message.answer(text)

    @dp.message(Command("goal_update"))
    async def cmd_goal_update(message: types.Message):
        # usage: /goal_update <id> <amount_to_add>
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("Использование: /goal_update <id> <amount_to_add> (пример: /goal_update 3 5000)")
            return
        try:
            gid = int(parts[1])
            add = float(parts[2])
        except:
            await message.answer("Неверные параметры.")
            return
        user_id = await get_or_create_user(message.from_user.id)
        # ensure goal belongs to user
        row = await db_pool.fetchrow("SELECT id, current, target FROM goals WHERE id=$1 AND user_id=$2", gid, user_id)
        if not row:
            await message.answer("Цель не найдена.")
            return
        new_current = float(row['current']) + add
        await db_pool.execute("UPDATE goals SET current=$1 WHERE id=$2", new_current, gid)
        await message.answer(f"Цель обновлена: {int(new_current)}/{int(row['target'])}₽")
    
    @dp.message(Command("goal_remove"))
    async def cmd_goal_remove(message: types.Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("Использование: /goal_remove <id>")
            return
        try:
            gid = int(parts[1])
        except:
            await message.answer("Неверный ID.")
            return
        user_id = await get_or_create_user(message.from_user.id)
        res = await db_pool.execute("DELETE FROM goals WHERE id=$1 AND user_id=$2", gid, user_id)
        await message.answer("Цель удалена (если она существовала).")

    @dp.callback_query(lambda c: c.data == "cancel_fsm")
    async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await call.message.answer("Действие отменено.")
        await call.answer()
