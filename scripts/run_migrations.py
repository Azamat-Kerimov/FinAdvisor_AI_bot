#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Применить миграции 002 и 003 к БД.
Требует: DATABASE_URL в .env или в окружении.
Запуск: python scripts/run_migrations.py
"""
import os
import sys
import asyncio

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "migrations")


async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Задайте DATABASE_URL в .env или в окружении")
        sys.exit(1)

    try:
        import asyncpg
    except ImportError:
        print("Установите asyncpg: pip install asyncpg")
        sys.exit(1)

    conn = await asyncpg.connect(db_url)
    try:
        for name in ["002_categories.sql", "003_transactions_category_id.sql"]:
            path = os.path.join(MIGRATIONS_DIR, name)
            if not os.path.exists(path):
                print(f"Пропуск (файл не найден): {name}")
                continue
            with open(path, "r", encoding="utf-8") as f:
                sql = f.read()
            print(f"Выполняю {name}...")
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if not stmt or stmt.startswith("--"):
                    continue
                await conn.execute(stmt)
            print(f"  OK: {name}")
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    finally:
        await conn.close()
    print("Миграции применены.")


if __name__ == "__main__":
    asyncio.run(main())
