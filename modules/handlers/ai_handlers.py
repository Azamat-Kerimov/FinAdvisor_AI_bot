# modules/handlers/ai_handlers.py
from aiogram import types
from aiogram.filters import Command
from modules.ai import gigachat_request
from modules.db import create_db_pool

async def register_handlers(dp, get_or_create_user, db_pool, save_message, get_context, analyze_finances):
    @dp.message(Command("consult"))
    async def cmd_consult(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)
        finance_text = await analyze_finances(user_id)
        system = {"role":"system","content":"Ты — краткий финансовый консультант. Дай 3-5 практических шагов, формат нумерованного списка."}
        user = {"role":"user","content": f"Данные пользователя:\n{finance_text}\nДай короткий план из шагов."}
        try:
            res = await gigachat_request([system, user])
        except Exception:
            res = "AI временно недоступен. Попробуйте позже."
        await message.answer("Рекомендации:\n" + res)

    # AI fallback handler for any text message
    @dp.message()
    async def catch_all(message: types.Message):
        # ignore commands
        if message.text and message.text.startswith("/"):
            return
        user_id = await get_or_create_user(message.from_user.id)
        finance_text = await analyze_finances(user_id)
        system = {"role":"system","content":"Ты — персональный финансовый ассистент. Даём краткий ответ и 2-3 шага."}
        user = {"role":"user","content": f"{finance_text}\nВопрос: {message.text}"}
        try:
            res = await gigachat_request([system, user])
        except Exception:
            res = "AI временно недоступен."
        await message.answer(res)
        await save_message(user_id, "user", message.text)
        await save_message(user_id, "assistant", res)
