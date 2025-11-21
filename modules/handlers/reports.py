from aiogram import F, types

from modules.db import db
from handlers import analyze_finances, get_or_create_user

@dp.callback_query(F.data == "menu_report")
async def menu_report(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)
    r = await analyze_finances(user_id)
    await q.message.answer(r)

@dp.callback_query(F.data == "menu_chart")
async def chart_cb(q: types.CallbackQuery):
    user_id = await get_or_create_user(q.from_user.id)

    rows = await db.fetch("""
        SELECT amount, category
        FROM transactions
        WHERE user_id=$1 AND created_at >= now() - interval '30 days'
    """, user_id)

    if not rows:
        await q.message.answer("Нет данных для графика.")
        return

    categories = {}
    for r in rows:
        categories[r["category"]] = categories.get(r["category"], 0) + float(r["amount"])

    labels = list(categories.keys())
    values = list(categories.values())

    import matplotlib.pyplot as plt
    from aiogram.types import FSInputFile

    plt.figure(figsize=(6, 6))
    plt.pie(values, labels=labels, autopct='%1.1f%%')

    filename = f"chart_{user_id}.png"
    plt.savefig(filename)
    plt.close()

    await q.message.answer_photo(FSInputFile(filename))
