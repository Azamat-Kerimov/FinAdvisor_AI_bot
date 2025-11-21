from aiogram import types
from modules.db import db

from modules.db import save_message, get_context, analyze_finances
from modules.ai import gigachat_request

async def ai_reply(user_id, user_message):
    await save_message(user_id, "user", user_message)

    context = await get_context(user_id)
    finance_data = await analyze_finances(user_id)

    system_prompt = f"""
[translate:Ты — персональный финансовый ассистент.]
[translate:Используй данные о транзакциях и историю диалога.]

[translate:Финансовые данные:]
{finance_data}

[translate:Отвечай профессионально, дружелюбно и понятно.]
"""

    messages = [{"role": "system", "content": system_prompt}] + context
    messages.append({"role": "user", "content": user_message})

    answer = await gigachat_request(messages)

    await save_message(user_id, "assistant", answer)

    return answer

from aiogram.filters import Command
from aiogram import F, types
from aiogram.dispatcher.filters import Text
from aiogram.fsm.context import FSMContext

from handlers import main_menu, get_or_create_user, toggle_summarization

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    await message.answer(
        "[translate:Привет! Я твой финансовый ассистент 🤖💰]\n\n"
        "[translate:Выбери действие:]",
        reply_markup=main_menu()
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("[translate:Используй меню ниже:]", reply_markup=main_menu())

@dp.message(Command("export"))
async def cmd_export(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)
    rows = await db.fetch(
        "SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1",
        user_id
    )

    filename = f"export_{user_id}.csv"
    import csv
    from aiogram.types import FSInputFile

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["amount", "category", "description", "created_at"])
        for r in rows:
            writer.writerow([r["amount"], r["category"], r["description"], r["created_at"]])

    await message.answer_document(FSInputFile(filename))

from aiogram import F

@dp.callback_query(F.data == "menu_back")
async def back_to_menu(q: types.CallbackQuery):
    await q.message.edit_text("[translate:Главное меню:]", reply_markup=main_menu())

@dp.callback_query(F.data == "menu_settings")
async def open_settings(q: types.CallbackQuery):
    await q.message.edit_text("[translate:Настройки:]", reply_markup=settings_menu())

@dp.callback_query(F.data == "toggle_sum")
async def toggle_sum_cb(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)
    await toggle_summarization(user_id)
    await q.answer("[translate:Переключено!]")
    await q.message.edit_text("[translate:Настройки:]", reply_markup=settings_menu())

