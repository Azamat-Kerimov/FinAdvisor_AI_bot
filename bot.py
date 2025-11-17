#!/usr/bin/env python3
# coding: utf-8

import os
import asyncio
import asyncpg
import aiohttp
import uuid
import base64
import csv
import tempfile
from datetime import datetime, timedelta
from functools import partial
import time
import json
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram import BaseMiddleware

from dotenv import load_dotenv
from rapidfuzz import process, fuzz
import aioredis

# =========================
# Load .env
# =========================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))

GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE")
GIGACHAT_AUTH_URL = os.getenv("GIGACHAT_AUTH_URL")
GIGACHAT_API_URL = os.getenv("GIGACHAT_API_URL")
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat:2.0.28.2")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

CHART_TMP = "/tmp"
os.makedirs(CHART_TMP, exist_ok=True)

CANONICAL_CATEGORIES = [
    "Такси", "Еда", "Продукты", "Развлечения", "Кафе", "Покупки", "Коммуналка", "Аренда",
    "Зарплата", "Кредиты", "Транспорт", "Медицина", "Образование", "Подарки", "Инвестиции",
    "Прочее"
]

# =========================
# GLOBALS
# =========================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db: asyncpg.pool.Pool | None = None
scheduler = AsyncIOScheduler()
ai_cache_memory = {}  # memory cache
redis: aioredis.Redis | None = None

# =========================
# Redis Middleware для rate-limit
# =========================
class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, cooldown: int = 300):
        super().__init__()
        self.cooldown = cooldown

    async def __call__(self, handler, event: types.Message, data: dict):
        user_id = event.from_user.id
        key = f"rate_limit:{user_id}"
        last_ts = await redis.get(key) if redis else None
        now = int(time.time())
        if last_ts:
            diff = now - int(last_ts)
            if diff < self.cooldown:
                await event.answer(f"⏳ Вы уже делали запрос. Попробуйте через {self.cooldown - diff} секунд.")
                return
        if redis:
            await redis.set(key, now, ex=self.cooldown)
        return await handler(event, data)

# =========================
# User_id кеш
# =========================
async def get_cached_user_id(tg_user_id: int) -> int:
    key = f"user_id:{tg_user_id}"
    cached = await redis.get(key)
    if cached:
        return int(cached)
    uid = await get_or_create_user(tg_user_id)
    await redis.set(key, uid, ex=86400)
    return uid

# =========================
# GigaChat Client
# =========================
class GigaChatClient:
    def __init__(self):
        self.token: str | None = None
        self.token_expires: float = 0
        self.session: aiohttp.ClientSession | None = None

    async def _ensure_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def get_token(self):
        await self._ensure_session()
        if self.token and time.time() < self.token_expires:
            return self.token

        headers = {
            "Authorization": f"Basic {base64.b64encode(f'{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}'.encode()).decode()}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
        }
        data = {"scope": GIGACHAT_SCOPE}

        async with self.session.post(GIGACHAT_AUTH_URL, headers=headers, data=data, ssl=True, timeout=20) as resp:
            resp.raise_for_status()
            j = await resp.json()
        self.token = j.get("access_token")
        expires_in = j.get("expires_in", 3600)
        self.token_expires = time.time() + expires_in - 60
        return self.token

    async def request(self, messages: list):
        await self._ensure_session()
        token = await self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {"model": GIGACHAT_MODEL, "messages": messages, "temperature": 0.3}
        async with self.session.post(GIGACHAT_API_URL, headers=headers, json=payload, ssl=True, timeout=30) as resp:
            if resp.status == 401:
                self.token = None
                token = await self.get_token()
                headers["Authorization"] = f"Bearer {token}"
                async with self.session.post(GIGACHAT_API_URL, headers=headers, json=payload, ssl=True, timeout=30) as resp2:
                    resp2.raise_for_status()
                    j = await resp2.json()
            else:
                resp.raise_for_status()
                j = await resp.json()
        try:
            return j["choices"][0]["message"]["content"]
        except:
            return json.dumps(j)

giga_client = GigaChatClient()

# =========================
# DB
# =========================
async def create_db_pool():
    global db
    db = await asyncpg.create_pool(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
        host=DB_HOST, port=DB_PORT, min_size=1, max_size=10
    )

async def get_or_create_user(tg_id: int) -> int:
    global db
    row = await db.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
    if row:
        return row["id"]
    row = await db.fetchrow("INSERT INTO users (tg_id, created_at) VALUES ($1, NOW()) RETURNING id", tg_id)
    return row["id"]

# =========================
# AI CONTEXT
# =========================
async def save_context(user_id: int, role: str, content: str):
    await db.execute("INSERT INTO ai_context (user_id, role, content, created_at) VALUES ($1,$2,$3,NOW())", user_id, role, content)

async def get_context(user_id: int):
    rows = await db.fetch("SELECT role, content FROM ai_context WHERE user_id=$1 ORDER BY id ASC", user_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]

# =========================
# AI REPLY
# =========================
async def ai_reply(user_id: int, user_text: str) -> str:
    key = f"{user_id}:{hash(user_text)}"

    # сначала из Redis/DB
    cached = await db.fetchrow("SELECT answer FROM ai_cache WHERE user_id=$1 AND input_hash=$2", user_id, str(hash(user_text)))
    if cached:
        return cached["answer"]

    await save_context(user_id, "user", user_text)
    context = await get_context(user_id)
    messages = [{"role":"system","content":"Ты — финансовый ассистент. Отвечай кратко и полезно."}] + context + [{"role":"user","content":user_text}]

    answer = await giga_client.request(messages)

    # сохраняем в ai_cache
    await db.execute("INSERT INTO ai_cache (user_id,input_hash,answer,created_at) VALUES ($1,$2,$3,NOW())",
                     user_id, str(hash(user_text)), answer)
    await save_context(user_id, "assistant", answer)
    return answer

# =========================
# RapidFuzz normalize category
# =========================
def normalize_category_input(cat_input: str):
    if not cat_input:
        return None, False
    match, score, _ = process.extractOne(cat_input.strip(), CANONICAL_CATEGORIES, scorer=fuzz.ratio)
    if score > 70:
        return match, True
    return " ".join([w.capitalize() for w in cat_input.strip().split()]), False

# =========================
# Executor для генерации графиков
# =========================
async def generate_chart_async(user_id: int):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(generate_combined_chart_for_user, user_id))

# =========================
# Пример добавления таблиц и индексов
# =========================
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    amount NUMERIC,
    category TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS goals (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    title TEXT,
    target NUMERIC,
    current NUMERIC,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    name TEXT,
    amount NUMERIC,
    type TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS ai_context (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS ai_cache (
    user_id INTEGER,
    input_hash TEXT,
    answer TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
-- Индексы
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_tg_id ON users(tg_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_created ON transactions(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assets_user_id ON assets(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_context_user_created ON ai_context(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_cache_user_hash ON ai_cache(user_id, input_hash);
"""

async def init_db():
    global db
    await create_db_pool()
    async with db.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)

# =========================
# MAIN STARTUP
# =========================
async def main():
    global redis
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    dp.message.middleware(RateLimitMiddleware(cooldown=300))
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
