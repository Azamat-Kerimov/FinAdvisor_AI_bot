# modules/handlers/reports.py
from aiogram import types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from datetime import datetime, timedelta
import csv
import tempfile
import os

from modules.utils import generate_donut, generate_goals_progress, generate_transactions_table_png

async def register_handlers(dp, get_or_create_user, db_pool):
    @dp.message(Command("chart"))
    async def cmd_chart(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)
        since = datetime.utcnow() - timedelta(days=30)
        rows = await db_pool.fetch("SELECT amount, category FROM transactions WHERE user_id=$1 AND created_at >= $2", user_id, since)
        if not rows:
            await message.answer("Нет транзакций за месяц.")
            return
        # aggregate
        cat_sum = {}
        for r in rows:
            cat = (r['category'] or "Другое")
            cat_sum[cat] = cat_sum.get(cat, 0) + float(r['amount'])
        fname = generate_donut(cat_sum, user_id)
        if fname:
            await message.answer_photo(FSInputFile(fname), caption="Траты по категориям за месяц")
            try: os.remove(fname)
            except: pass

    @dp.message(Command("goals_chart"))
    async def cmd_goals_chart(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)
        goals = await db_pool.fetch("SELECT title, target, current FROM goals WHERE user_id=$1 ORDER BY id ASC", user_id)
        if not goals:
            await message.answer("У вас нет целей.")
            return
        assets_sum = await db_pool.fetchval("SELECT COALESCE(SUM(amount),0) FROM assets WHERE user_id=$1", user_id)
        liabilities_sum = await db_pool.fetchval("SELECT COALESCE(SUM(amount),0) FROM liabilities WHERE user_id=$1", user_id)
        available = float(assets_sum or 0) - float(liabilities_sum or 0)
        goals_list = [{"title": g["title"], "target": float(g["target"]), "current": float(g["current"])} for g in goals]
        fname = generate_goals_progress(goals_list, available, user_id)
        await message.answer_photo(FSInputFile(fname), caption=f"Прогресс по целям. Доступно: {int(available)}₽")
        try: os.remove(fname)
        except: pass

    @dp.message(Command("export"))
    async def cmd_export(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)
        rows = await db_pool.fetch("SELECT id, amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at ASC", user_id)
        if not rows:
            await message.answer("Нет транзакций для экспорта.")
            return
        fd, path = tempfile.mkstemp(prefix=f"finances_{user_id}_", suffix=".csv")
        os.close(fd)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id","amount","category","description","created_at"])
            for r in rows:
                writer.writerow([r["id"], r["amount"], r["category"] or "", r["description"] or "", r["created_at"].isoformat() if r["created_at"] else ""])
        await message.answer_document(FSInputFile(path), caption="Экспорт CSV")
        try: os.remove(path)
        except: pass

    @dp.message(Command("report_table"))
    async def cmd_report_table(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)
        rows = await db_pool.fetch("SELECT amount, category, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT 50", user_id)
        if not rows:
            await message.answer("Нет транзакций.")
            return
        fname = generate_transactions_table_png(rows, user_id)
        await message.answer_photo(FSInputFile(fname), caption="Таблица транзакций (последние 50)")
        try: os.remove(fname)
        except: pass

    @dp.message(Command("balance"))
    async def cmd_balance(message: types.Message):
        user_id = await get_or_create_user(message.from_user.id)
        assets_sum = await db_pool.fetchval("SELECT COALESCE(SUM(amount),0) FROM assets WHERE user_id=$1", user_id)
        liabilities_sum = await db_pool.fetchval("SELECT COALESCE(SUM(amount),0) FROM liabilities WHERE user_id=$1", user_id)
        net = float(assets_sum or 0) - float(liabilities_sum or 0)
        await message.answer(f"Активы: {int(assets_sum)}₽\nДолги: {int(liabilities_sum)}₽\nNet Balance: {int(net)}₽")
