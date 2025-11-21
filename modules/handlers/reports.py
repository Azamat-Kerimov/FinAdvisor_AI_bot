import io
from aiogram import types
from aiogram.filters import Command
from aiogram.types import FSInputFile

from modules.utils import normalize_category
from modules.charts import make_expense_chart, make_goals_progress_chart


def register_report_handlers(dp, get_or_create_user, db_pool, save_message):

    @dp.message(Command("report"))
    async def cmd_report(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)

        async with db_pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT amount, category, description, created_at FROM transactions "
                "WHERE user_id=$1 ORDER BY created_at DESC LIMIT 10",
                user_id
            )
            assets = await connection.fetch(
                "SELECT title, amount, type FROM assets WHERE user_id=$1 ORDER BY id",
                user_id
            )
            liabilities = await connection.fetch(
                "SELECT title, amount, type FROM liabilities WHERE user_id=$1 ORDER BY id",
                user_id
            )

        if not rows:
            tx_table = "Транзакций пока нет."
        else:
            header = "🧾 <b>Последние транзакции</b>\n\n"
            table = "<pre>Сумма    Категория      Дата\n"
            table += "-----------------------------------\n"

            for tx in rows:
                cat = normalize_category(tx["category"]) if tx["category"] else "-"
                date = tx["created_at"].strftime("%Y-%m-%d %H:%M")
                table += f"{tx['amount']:>6}   {cat:<12}   {date}\n"

            table += "</pre>"
            tx_table = header + table

        if assets:
            assets_text = "\n\n<b>💼 Активы</b>\n"
            total_assets = sum(a["amount"] for a in assets)
            for a in assets:
                assets_text += f"• {a['title']} — {a['amount']} ({a['type']})\n"
            assets_text += f"\n<b>Всего активов:</b> {total_assets}"
        else:
            assets_text = "\n\n<b>💼 Активы:</b> нет"

        if liabilities:
            liabilities_text = "\n\n<b>💳 Долги</b>\n"
            total_liabilities = sum(l["amount"] for l in liabilities)
            for l in liabilities:
                liabilities_text += f"• {l['title']} — {l['amount']} ({l['type']})\n"
            liabilities_text += f"\n<b>Всего долгов:</b> {total_liabilities}"
        else:
            liabilities_text = "\n\n<b>💳 Долги:</b> нет"

        net = (sum(a["amount"] for a in assets) if assets else 0) - \
              (sum(l["amount"] for l in liabilities) if liabilities else 0)
        net_text = f"\n\n<b>💰 Чистый капитал:</b> {net}"

        await message.answer(
            f"{tx_table}{assets_text}{liabilities_text}{net_text}",
            parse_mode="HTML"
        )

    @dp.message(Command("chart"))
    async def cmd_chart(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)

        buf1 = await make_expense_chart(db_pool, user_id)
        file1 = FSInputFile(buf1, filename="expenses.png")

        buf2 = await make_goals_progress_chart(db_pool, user_id)
        file2 = FSInputFile(buf2, filename="goals.png")

        await message.answer("Ваши графики ↓")
        await message.answer_photo(file1)
        await message.answer_photo(file2)
