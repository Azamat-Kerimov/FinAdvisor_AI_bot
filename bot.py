import asyncio
import os
import json
from collections import defaultdict
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from openai import OpenAI
from db import get_connection

# ================= Настройки окружения =================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)

# Полная история общения (вся, без ограничений)
user_contexts = defaultdict(list)

# ================= FSM для ручных действий =================
class TransactionStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_description = State()
    waiting_for_category = State()

class GoalStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_target_amount = State()

# ================= Категории =================
CATEGORIES = ["Продукты", "Транспорт", "Развлечения", "Коммуналка", "Другое"]

def categories_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIES:
        kb.add(InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}"))
    return kb

# ================= Команда /start =================
@dp.message(Command("start"))
async def start(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or "no_name"

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (tg_id, username) VALUES (%s, %s) "
            "ON CONFLICT (tg_id) DO NOTHING RETURNING id",
            (tg_id, username)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("Ошибка работы с БД:", repr(e))
        await message.answer("Ошибка при регистрации пользователя!")
        return

    user_contexts[tg_id].clear()
    await message.answer(f"Привет, {username}! Я FinAdvisor 🤖 — твой финансовый помощник. Можешь писать мне в свободной форме, например:\n\n• «добавь трату 200 на кофе»\n• «создай цель 100000 на отпуск»\n• «обнови цель отпуск, добавь 5000»")

# ================= Команда /report =================
@dp.message(Command("report"))
async def report(message: types.Message):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT SUM(amount) as total FROM transactions WHERE user_id = (SELECT id FROM users WHERE tg_id=%s)",
            (message.from_user.id,)
        )
        total = cursor.fetchone()['total'] or 0

        cursor.execute(
            "SELECT title, current, target FROM goals WHERE user_id = (SELECT id FROM users WHERE tg_id=%s)",
            (message.from_user.id,)
        )
        goals = cursor.fetchall()

        cursor.close()
        conn.close()

        text = f"📊 Общие расходы: {total} ₽\n🎯 Цели:\n"
        if goals:
            for g in goals:
                text += f"- {g['title']}: {g['current']} / {g['target']} ₽\n"
        else:
            text += "Цели пока не добавлены."

        await message.answer(text)
    except Exception as e:
        print("Ошибка при формировании отчёта:", e)
        await message.answer("⚠ Ошибка при формировании отчёта.")

# ================= AI-помощник с действиями =================
@dp.message()
async def ai_smart_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # сохраняем историю общения
    user_contexts[user_id].append({"role": "user", "content": text})

    # достаём финансовые данные
    user_summary = ""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT SUM(amount) as total FROM transactions WHERE user_id = (SELECT id FROM users WHERE tg_id=%s)", (user_id,))
        total = cursor.fetchone()['total'] or 0

        cursor.execute("SELECT title, current, target FROM goals WHERE user_id = (SELECT id FROM users WHERE tg_id=%s)", (user_id,))
        goals = cursor.fetchall()

        cursor.close()
        conn.close()

        goal_info = "\n".join([f"- {g['title']}: {g['current']}/{g['target']} ₽" for g in goals]) or "Целей нет."
        user_summary = f"Пользователь потратил {total} ₽. Цели:\n{goal_info}"
    except Exception as e:
        print("Ошибка при запросе данных из БД:", e)
        user_summary = "Нет данных о пользователе."

    # GPT-инструкция: возвращай JSON с действием
    system_prompt = f"""
Ты — финансовый ассистент FinAdvisor.
Ты можешь либо ответить пользователю текстом, либо предложить действие в JSON.

Если пользователь просит добавить трату, создать или обновить цель, возвращай JSON строго в формате:
{{"action": "add_transaction", "amount": 200, "description": "кофе", "category": "Продукты"}}
{{"action": "add_goal", "title": "Отпуск", "target": 100000}}
{{"action": "update_goal", "title": "Отпуск", "add": 5000}}

Если пользователь просто задаёт вопрос — верни обычный текст.

Данные пользователя:
{user_summary}
"""

    messages = [{"role": "system", "content": system_prompt}] + user_contexts[user_id]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.4
        )

        ai_response = response.choices[0].message.content.strip()

        # если GPT вернул JSON — выполняем действие
        if ai_response.startswith("{"):
            try:
                action = json.loads(ai_response)
                await handle_ai_action(message, action)
            except Exception as e:
                print("Ошибка парсинга JSON:", e)
                await message.answer("⚠ Ошибка обработки команды.")
        else:
            await message.answer(ai_response)
            user_contexts[user_id].append({"role": "assistant", "content": ai_response})

    except Exception as e:
        print("Ошибка AI:", e)
        await message.answer("⚠ Ошибка AI. Попробуйте позже.")

# ================= Выполнение действий из AI =================
async def handle_ai_action(message: types.Message, action: dict):
    user_id = message.from_user.id
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if action["action"] == "add_transaction":
            cursor.execute(
                "INSERT INTO transactions (user_id, amount, category, description) VALUES ((SELECT id FROM users WHERE tg_id=%s), %s, %s, %s)",
                (user_id, action["amount"], action.get("category", "Другое"), action.get("description", ""))
            )
            conn.commit()
            await message.answer(f"✅ Добавлена трата {action['amount']} ₽ ({action.get('description', '')})")

        elif action["action"] == "add_goal":
            cursor.execute(
                "INSERT INTO goals (user_id, title, target, current) VALUES ((SELECT id FROM users WHERE tg_id=%s), %s, %s, 0)",
                (user_id, action["title"], action["target"])
            )
            conn.commit()
            await message.answer(f"🎯 Цель добавлена: {action['title']} ({action['target']} ₽)")

        elif action["action"] == "update_goal":
            cursor.execute(
                "UPDATE goals SET current = current + %s WHERE user_id=(SELECT id FROM users WHERE tg_id=%s) AND title=%s",
                (action["add"], user_id, action["title"])
            )
            conn.commit()
            await message.answer(f"📈 Цель {action['title']} обновлена (+{action['add']} ₽)")

        else:
            await message.answer("🤔 Неизвестное действие.")
    except Exception as e:
        print("Ошибка при выполнении действия:", e)
        await message.answer("⚠ Не удалось выполнить действие.")
    finally:
        cursor.close()
        conn.close()

# ================= Запуск =================
async def main():
    print("🤖 FinAdvisor AI Bot запущен с полным контекстом и действиями.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
