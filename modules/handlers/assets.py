# modules/handlers/assets.py
from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Отмена", callback_data="cancel_fsm")]
])

class AssetStates(StatesGroup):
    title = State()
    amount = State()
    type = State()

def register_asset_handlers(dp, get_or_create_user, db_pool, save_message):

    # вывести список активов
    @dp.message(Command("assets"))
    async def cmd_assets(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)
        rows = await db_pool.fetch(
            "SELECT id, title, amount, type FROM assets WHERE user_id=$1 ORDER BY id",
            user_id
        )

        if not rows:
            await message.answer("У вас пока нет активов. Используйте /addasset для добавления.")
            return

        text = "💼 Ваши активы:\n\n"
        for a in rows:
            text += f"• {a['title']} — {a['amount']} ({a['type']})\n"

        await message.answer(text)

    # добавить актив
    @dp.message(Command("addasset"))
    async def add_asset(message: types.Message, state: FSMContext):
        await state.set_state(AssetStates.title)
        await message.answer("Введите название актива:", reply_markup=cancel_kb)

    @dp.message(AssetStates.title)
    async def handle_title(message: types.Message, state: FSMContext):
        await state.update_data(title=message.text.strip())
        await state.set_state(AssetStates.amount)
        await message.answer("Введите сумму:", reply_markup=cancel_kb)

    @dp.message(AssetStates.amount)
    async def handle_amount(message: types.Message, state: FSMContext):
        try:
            amount = float(message.text.strip())
        except:
            await message.answer("Введите число.")
            return

        await state.update_data(amount=amount)
        await state.set_state(AssetStates.type)
        await message.answer("Введите тип актива (cash/deposit/invest):", reply_markup=cancel_kb)

    @dp.message(AssetStates.type)
    async def handle_type(message: types.Message, state: FSMContext):
        asset_type = message.text.strip()

        data = await state.get_data()
        user_id = await get_or_create_user(message.from_user.id)

        await db_pool.execute(
            "INSERT INTO assets (user_id, title, amount, type, created_at) "
            "VALUES ($1,$2,$3,$4,NOW())",
            user_id, data["title"], data["amount"], asset_type
        )

        await save_message(
            user_id,
            "system",
            f"Добавлен актив: {data['title']} | {data['amount']} | {asset_type}"
        )

        await message.answer("Актив добавлен 💼")
        await state.clear()

    # отмена FSM
    @dp.callback_query(lambda c: c.data == "cancel_fsm")
    async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await call.message.answer("Действие отменено.")
        await call.answer()
