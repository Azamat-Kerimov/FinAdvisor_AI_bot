# modules/handlers/ai_handlers.py
from aiogram import types
from aiogram.filters import Command

from modules.ai import ask_gigachat
from modules.utils import normalize_category


def register_ai_handlers(dp, get_or_create_user, db_pool, save_message):

    # ИИ консультация
    @dp.message(Command("consult"))
    async def cmd_consult(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)

        # История транзакций
        tx = await db_pool.fetch(
            "SELECT amount, category, description FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT 200",
            user_id
        )

        # Активы/долги
        assets = await db_pool.fetch(
            "SELECT title, amount, type FROM assets WHERE user_id=$1",
            user_id
        )
        liabilities = await db_pool.fetch(
            "SELECT title, amount, type FROM liabilities WHERE user_id=$1",
            user_id
        )

        prompt = f"""
Ты — финансовый консультант.
Составь краткий пошаговый план из 5-7 пунктов.
Дай рекомендации, используя данные:

Транзакции:
{[dict(x) for x in tx]}

Активы:
{[dict(a) for a in assets]}

Долги:
{[dict(l) for l in liabilities]}
"""

        ai_answer = await ask_gigachat(prompt)
        await save_message(user_id, "assistant", ai_answer)

        await message.answer("🧠 <b>Консультация</b>\n\n" + ai_answer, parse_mode="HTML")

    # ————————————————————————
    # Автоатрибуция
    # ————————————————————————

    async def auto_categorize(user_id: int, text: str):
        prompt = f"""
Ты — система категоризации транзакций.
Пользователь ввёл текст: "{text}"

Верни JSON: {{"amount": ..., "category": "...", "description": "..."}}
Категория — одно слово, с большой буквы.
"""
        raw = await ask_gigachat(prompt)

        try:
            import json
            data = json.loads(raw)
        except:
            return None

        if data.get("category"):
            data["category"] = normalize_category(data["category"])

        return data

    return auto_categorize
