#!/usr/bin/env python3
"""
Применить схему БД из schema_finadvisor.sql к базе из .env.
Запуск из корня проекта: python scripts/apply_schema.py
Или: venv\Scripts\python scripts/apply_schema.py
"""
import asyncio
import os
import sys

# Корень проекта = родитель папки scripts
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
    if not DB_NAME or not DB_USER:
        print("В .env задайте DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT.", file=sys.stderr)
        sys.exit(1)

    schema_path = os.path.join(SCRIPT_DIR, "schema_finadvisor.sql")
    if not os.path.isfile(schema_path):
        print(f"Файл не найден: {schema_path}", file=sys.stderr)
        sys.exit(1)

    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    # Убираем целые строки-комментарии и пустые; разбиваем по ";" (asyncpg выполняет по одному запросу)
    lines = []
    for line in sql.splitlines():
        s = line.strip()
        if s.startswith("--") or not s:
            continue
        lines.append(line)
    full_sql = "\n".join(lines)
    statements = [s.strip() for s in full_sql.split(";") if s.strip()]

    async def run():
        conn = await asyncpg.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            port=DB_PORT,
        )
        try:
            for st in statements:
                await conn.execute(st + ";")
        finally:
            await conn.close()

    asyncio.run(run())
    print("Схема применена.")


if __name__ == "__main__":
    main()
