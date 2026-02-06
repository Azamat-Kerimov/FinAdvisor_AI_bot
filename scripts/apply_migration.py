#!/usr/bin/env python3
"""
Применить миграцию (один SQL-файл целиком). Подходит для DO $$ ... $$ блоков.
Использование: python scripts/apply_migration.py scripts/migrate_transactions_category_to_id.sql
Из корня проекта, с настроенным .env.
"""
import asyncio
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

import asyncpg

DB_NAME = os.getenv("DB_NAME", "").strip()
DB_USER = os.getenv("DB_USER", "").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD") or ""
DB_HOST = os.getenv("DB_HOST", "localhost").strip()
DB_PORT = os.getenv("DB_PORT", "5432").strip()


def main():
    if len(sys.argv) < 2:
        print("Укажите файл миграции: python scripts/apply_migration.py scripts/migrate_transactions_category_to_id.sql", file=sys.stderr)
        sys.exit(1)
    if not DB_NAME or not DB_USER:
        print("В .env задайте DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT.", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.isabs(path):
        path = os.path.join(PROJECT_ROOT, path)
    if not os.path.isfile(path):
        print(f"Файл не найден: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()

    async def run():
        conn = await asyncpg.connect(
            user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
            host=DB_HOST, port=DB_PORT,
        )
        try:
            await conn.execute(sql)
        finally:
            await conn.close()

    asyncio.run(run())
    print("Миграция применена:", path)


if __name__ == "__main__":
    main()
