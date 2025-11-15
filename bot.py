import os
import asyncio
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
import httpx

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

GIGACHAT_API_KEY = os.getenv("GIGACHAT_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# -----------------------------
# ИНИЦИАЛИЗАЦИЯ БАЗЫ
# -----------------------------
async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT
    )

db = None


# -----------------------------------------------------------
# GIGACHAT: функция отправки сообщения и получения ответа
# -----------------------------------------------------------
async def gigachat_request(messages: list):
    """Отправляет диалог в GigaChat и возвращает ответ."""

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        headers = {
            "Authorization": f"Bearer {GIGACHAT_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "GigaChat",
            "messages": messages,
            "temperature": 0.9
        }

        r = await client.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            json=payload,
            headers=headers
        )

        data = r.json()

        return data["choices"][0]["message"]["content"]


# -----------------------------------------------------------
# ПОЛУЧЕНИЕ ПОЛНОГО АИ-КОНТЕКСТА ИСТОРИИ
# -----------------------------------------------------------
async def get_full_context(user_id):
    rows = await db.fetch("""
        SELECT role, content
        FROM ai_context
        WHERE user_id = $1
        ORDER BY id ASC
    """, user_id)

    messages = [{"role": row["role"], "content": row["content"]} for row in rows]
    return messages


# -----------------------------------------------------------
# СОХРАНЕНИЕ КОНТЕКСТА
# -----------------------------------------------------------
async def save_message(user_id, role, content):
    await db.execute("""
        INSERT INTO ai_context (user_id, role, content)
        VALUES ($1, $2, $3)
    """, user_id, role, content)


# -----------------------------------------------------------
# АНАЛИЗ ТРАНЗАКЦИЙ ДЛЯ СОВЕТА
# -----------------------------------------------------------
async def analyze_user_finances(user_id):
    """Формирует текстовый отчет по транзакциям для GigaChat."""
    rows = await db.fetch("""
        SELECT amount, created_at
        FROM transactions
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 200
    """, user_id)

    if not rows:
        return "У пользователя нет транзакций."

    text = "Последние транзакции пользователя:\n"
    for r in rows:
        text += f"- {r['amount']}₽ ({r['created_at']})\n"

    # цели
    goals = await db.fetch("""
        SELECT target, current, created_at
        FROM goals
        WHERE user_id = $1
    """, user_id)

    if goals:
        text += "\nЦели пользователя:\n"
        for g in goals:
            text += f"- Цель: {g['current']} / {g['target']}₽ (создано: {g['created_at']})\n"

    return text


# -----------------------------------------------------------
# ГЛАВНЫЙ АИ-ОТВЕТ
# -----------------------------------------------------------
async def generate_ai_reply(user_id, user_message):
    """Объединяет контекст + историю транзакций + сообщение пользователя."""

    # сохраняем user message
    await save_message(user_id, "user", user_message)

    # загружаем весь контекст
    context = await get_full_context(user_id)

    # добавляем анализ транзакций
    finance_data = await analyze_user_finances(user_id)

    system_prompt = f"""
Ты — умный финансовый ассистент.
Используй всю историю диалога, а также анализ транзакций и целей пользователя.

Вот данные пользователя:
{finance_data}

Давай полезный, персонализированный финансовый совет.
"""

    messages = [
        {"role": "system", "content": system_prompt}
    ]
    messages += context
    messages.append({"role": "user", "content": user_message})

    # запрос к GigaChat
    ai_answer = await gigachat_request(messages)

    # сохраняем ответ бота
    await save_message(user_id, "assistant", ai_answer)

    return ai_answer


# -----------------------------------------------------------
# РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ
# -----------------------------------------------------------
async def get_or_create_user(tg_id):
    row = await db.fetchrow("SELECT * FROM users WHERE tg_id=$1", tg_id)

    if row:
        return row["id"]

    row = await db.fetchrow("""
        INSERT INTO users (tg_id)
        VALUES ($1)
        RETURNING id
    """, tg_id)

    return row["id"]


# -----------------------------------------------------------
# ОБРАБОТЧИК /start
# -----------------------------------------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)

    await message.answer("Привет! Я финансовый ассистент. Задай мне любой вопрос, и я помогу!")


# -----------------------------------------------------------
# ГЛАВНЫЙ ОБРАБОТЧИК ВСЕХ СООБЩЕНИЙ
# -----------------------------------------------------------
@dp.message()
async def handle_msg(message: types.Message):
    user_id = await get_or_create_user(message.from_user.id)

    user_text = message.text

    reply = await generate_ai_reply(user_id, user_text)

    await message.answer(reply)


# -----------------------------------------------------------
# СТАРТ БОТА
# -----------------------------------------------------------
async def main():
    global db
    db = await create_db_pool()
    print("DB connected. Bot started.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
