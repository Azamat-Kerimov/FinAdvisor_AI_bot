from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from modules.utils import smart_parse_free_text, normalize_category

cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Отмена", callback_data="cancel_fsm")]
])

class TxStates(StatesGroup):
    amount = State()
    category = State()
    desc = State()

def register_tx_handlers(dp, get_or_create_user, db_pool, save_message):
    """
    Привязываем хендлеры к dispatcher (dp).
    """

    @dp.message(Command("add"))
    async def cmd_add(message: types.Message, state: FSMContext):
        await state.set_state(TxStates.amount)
        await message.answer("Введите сумму (например: -2500 или 1500):", reply_markup=cancel_kb)

    @dp.message(TxStates.amount)
    async def handle_amount(message: types.Message, state: FSMContext):
        txt = message.text.strip()
        parsed = smart_parse_free_text(txt)

        if parsed:
            amount, cat, desc = parsed
            if cat:
                cat = normalize_category(cat)

            user_id = await get_or_create_user(message.from_user.id)

            async with db_pool.acquire() as connection:
                await connection.execute(
                    "INSERT INTO transactions (user_id, amount, category, description, created_at)"
                    " VALUES ($1,$2,$3,$4,NOW())",
                    user_id, amount, cat, desc
                )

            await save_message(user_id, "system", f"Добавлена транзакция: {amount} | {cat} | {desc}")
            await message.answer("Транзакция добавлена ✅")
            await state.clear()
            return

        try:
            amount = float(txt)
        except:
            await message.answer("Не смог распознать сумму, введите ещё раз или нажмите Отмена.")
            return

        await state.update_data(amount=amount)
        await state.set_state(TxStates.category)
        await message.answer("Введите категорию (или '-' для пропуска):", reply_markup=cancel_kb)

    @dp.message(TxStates.category)
    async def handle_category(message: types.Message, state: FSMContext):
        txt = message.text.strip()
        cat = None if txt == "-" else normalize_category(txt)

        await state.update_data(category=cat)
        await state.set_state(TxStates.desc)
        await message.answer("Введите описание (или '-' для пропуска):", reply_markup=cancel_kb)

    @dp.message(TxStates.desc)
    async def handle_desc(message: types.Message, state: FSMContext):
        data = await state.get_data()
        desc = None if message.text.strip() == "-" else message.text.strip()

        user_id = await get_or_create_user(message.from_user.id)

        async with db_pool.acquire() as connection:
            await connection.execute(
                "INSERT INTO transactions (user_id, amount, category, description, created_at)"
                " VALUES ($1,$2,$3,$4,NOW())",
                user_id, data['amount'], data.get('category'), desc
            )

        await save_message(user_id, "system", f"Добавлена транзакция: {data['amount']} | {data.get('category')} | {desc}")
        await message.answer("Транзакция добавлена ✅")
        await state.clear()

    @dp.callback_query(lambda c: c.data == "cancel_fsm")
    async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await call.message.answer("Действие отменено.")
        await call.answer()
