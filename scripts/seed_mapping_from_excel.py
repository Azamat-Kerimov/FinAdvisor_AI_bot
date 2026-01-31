#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка маппинга категорий из Excel «Справочник Транзакций.xlsx».
Колонка IN — категория из СберОнлайна/Т-Банка, вторая колонка — категория приложения (имя).
Требует: 002_categories.sql уже применён, в таблице categories есть строки.
Запуск: python scripts/seed_mapping_from_excel.py "путь/к/Справочник Транзакций.xlsx"
       или: python scripts/seed_mapping_from_excel.py   (по умолчанию ~/Desktop/Справочник Транзакций.xlsx)
"""
import os
import sys
import asyncio

# Загрузка .env для DATABASE_URL
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_excel_path():
    if len(sys.argv) > 1:
        return sys.argv[1]
    for base in [os.path.expanduser("~"), os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")]:
        path = os.path.join(base, "Справочник Транзакций.xlsx")
        if os.path.exists(path):
            return path
    return None

async def main():
    excel_path = get_excel_path()
    if not excel_path or not os.path.exists(excel_path):
        print("Файл не найден. Укажите путь: python seed_mapping_from_excel.py <path/to/Справочник Транзакций.xlsx>")
        sys.exit(1)

    try:
        import openpyxl
    except ImportError:
        print("Установите openpyxl: pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    sheet = wb.active
    rows = list(sheet.iter_rows(values_only=True))
    wb.close()

    if not rows:
        print("Лист пуст")
        sys.exit(1)

    headers = [str(h).strip().lower() if h is not None else "" for h in rows[0]]
    col_in = None
    col_out = None
    for i, h in enumerate(headers):
        if not h:
            continue
        if h == "in" or "in" in h and "категор" in h:
            col_in = i
        if h in ("out", "категория", "категория приложения", "to") or ("категор" in h and "out" in h):
            col_out = i
    if col_in is None:
        col_in = 0
    if col_out is None:
        col_out = 1 if len(headers) > 1 else 0

    pairs = []
    for r in rows[1:]:
        if len(r) <= max(col_in, col_out):
            continue
        bank = r[col_in]
        out_name = r[col_out]
        if bank is None and out_name is None:
            continue
        bank_key = str(bank).strip().lower() if bank else ""
        out_key = str(out_name).strip() if out_name else ""
        if not bank_key or not out_key:
            continue
        pairs.append((bank_key, out_key))

    if not pairs:
        print("Нет строк для загрузки (колонки IN и категория приложения)")
        sys.exit(1)

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Задайте DATABASE_URL (или DATABASE_URL в .env)")
        sys.exit(1)

    try:
        import asyncpg
    except ImportError:
        print("Установите asyncpg: pip install asyncpg")
        sys.exit(1)

    conn = await asyncpg.connect(db_url)
    try:
        inserted = 0
        for bank_key, out_name in pairs:
            r = await conn.execute(
                """
                INSERT INTO category_mapping (bank_category, category_id)
                SELECT $1, c.id FROM categories c WHERE c.name = $2
                ON CONFLICT (bank_category) DO UPDATE SET category_id = EXCLUDED.category_id
                """,
                bank_key, out_name
            )
            if "INSERT" in r:
                inserted += 1
        print(f"Обработано записей маппинга: {len(pairs)}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
