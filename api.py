# FastAPI сервер для Telegram Web App
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncpg
import os
from dotenv import load_dotenv
import hmac
import hashlib
import json

load_dotenv()

app = FastAPI()

# CORS для Telegram Web App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
BOT_TOKEN = os.getenv("BOT_TOKEN")

db_pool: Optional[asyncpg.Pool] = None

async def get_db():
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(
            user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
            host=DB_HOST, port=DB_PORT, min_size=1, max_size=6
        )
    return db_pool

# Telegram Web App validation
def validate_telegram_webapp(init_data: str) -> dict:
    """Проверка подписи Telegram Web App"""
    try:
        # Парсим initData
        params = {}
        for item in init_data.split('&'):
            if '=' in item:
                key, value = item.split('=', 1)
                params[key] = value
        
        # Проверяем hash
        hash_value = params.pop('hash', '')
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(params.items()))
        
        secret_key = hmac.new(
            "WebAppData".encode(), 
            BOT_TOKEN.encode(), 
            hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if calculated_hash != hash_value:
            raise HTTPException(status_code=401, detail="Invalid hash")
        
        # Парсим user
        user_str = params.get('user', '')
        user = json.loads(user_str) if user_str else {}
        
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Validation error: {str(e)}")

async def get_user_id(init_data: Optional[str] = Header(None, alias="init-data")) -> int:
    """Получить user_id из Telegram Web App"""
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")
    
    user = validate_telegram_webapp(init_data)
    tg_id = user.get('id')
    
    if not tg_id:
        raise HTTPException(status_code=401, detail="Invalid user")
    
    # Получаем или создаем пользователя
    db = await get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
        if not row:
            await conn.execute(
                "INSERT INTO users (tg_id, username, created_at) VALUES ($1, $2, NOW())",
                tg_id, user.get('username')
            )
            row = await conn.fetchrow("SELECT id FROM users WHERE tg_id=$1", tg_id)
        return row['id']

# Pydantic models
class TransactionCreate(BaseModel):
    amount: float
    category: str
    description: Optional[str] = None

class GoalCreate(BaseModel):
    title: str
    target: float
    description: Optional[str] = None

class AssetCreate(BaseModel):
    title: str
    type: str
    amount: float

class LiabilityCreate(BaseModel):
    title: str
    type: str
    amount: float
    monthly_payment: float

# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Главная страница Web App"""
    with open("webapp/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/static/{file_path:path}")
async def static_files(file_path: str):
    """Статические файлы"""
    return FileResponse(f"webapp/static/{file_path}")

# Статистика
@app.get("/api/stats")
async def get_stats(user_id: int = Depends(get_user_id)):
    """Получить статистику за текущий месяц"""
    from datetime import datetime
    now = datetime.now()
    since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT amount, category, created_at
            FROM transactions
            WHERE user_id=$1 AND created_at >= $2
            ORDER BY created_at ASC
            """,
            user_id, since
        )
        
        income_by_cat = {}
        expense_by_cat = {}
        
        for r in rows:
            amount = float(r["amount"])
            cat = r["category"] or "—"
            if amount >= 0:
                income_by_cat[cat] = income_by_cat.get(cat, 0) + amount
            else:
                expense_by_cat[cat] = expense_by_cat.get(cat, 0) + (-amount)
        
        total_income = sum(income_by_cat.values())
        total_expense = sum(expense_by_cat.values())
        
        return {
            "total_income": total_income,
            "total_expense": total_expense,
            "income_by_category": income_by_cat,
            "expense_by_category": expense_by_cat
        }

# Транзакции
@app.get("/api/transactions")
async def get_transactions(limit: int = 10, user_id: int = Depends(get_user_id)):
    """Получить список транзакций"""
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, amount, category, description, created_at
            FROM transactions
            WHERE user_id=$1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id, limit
        )
        return [dict(r) for r in rows]

@app.post("/api/transactions")
async def create_transaction(transaction: TransactionCreate, user_id: int = Depends(get_user_id)):
    """Создать транзакцию"""
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO transactions (user_id, amount, category, description, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            user_id, transaction.amount, transaction.category, transaction.description
        )
        return {"status": "ok"}

@app.delete("/api/transactions/{tx_id}")
async def delete_transaction(tx_id: int, user_id: int = Depends(get_user_id)):
    """Удалить транзакцию"""
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "DELETE FROM transactions WHERE id=$1 AND user_id=$2",
            tx_id, user_id
        )
        return {"status": "ok"}

# Цели
@app.get("/api/goals")
async def get_goals(user_id: int = Depends(get_user_id)):
    """Получить список целей"""
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, target, current, description
            FROM goals
            WHERE user_id=$1
            ORDER BY id
            """,
            user_id
        )
        return [dict(r) for r in rows]

@app.post("/api/goals")
async def create_goal(goal: GoalCreate, user_id: int = Depends(get_user_id)):
    """Создать цель"""
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO goals (user_id, target, current, title, description, created_at)
            VALUES ($1, $2, 0, $3, $4, NOW())
            """,
            user_id, goal.target, goal.title, goal.description
        )
        return {"status": "ok"}

@app.delete("/api/goals/{goal_id}")
async def delete_goal(goal_id: int, user_id: int = Depends(get_user_id)):
    """Удалить цель"""
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "DELETE FROM goals WHERE id=$1 AND user_id=$2",
            goal_id, user_id
        )
        return {"status": "ok"}

# Активы
@app.get("/api/assets")
async def get_assets(user_id: int = Depends(get_user_id)):
    """Получить список активов"""
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.id AS asset_id, a.title, a.type, a.currency,
                   v.amount, v.created_at AS updated_at
            FROM assets a
            LEFT JOIN LATERAL (
                SELECT amount, created_at
                FROM asset_values
                WHERE asset_id = a.id
                ORDER BY created_at DESC
                LIMIT 1
            ) v ON TRUE
            WHERE a.user_id = $1 AND (v.amount IS NULL OR v.amount > 0)
            ORDER BY a.type, v.amount ASC
            """,
            user_id
        )
        return [dict(r) for r in rows]

@app.post("/api/assets")
async def create_asset(asset: AssetCreate, user_id: int = Depends(get_user_id)):
    """Создать актив"""
    db = await get_db()
    async with db.acquire() as conn:
        asset_id = await conn.fetchval(
            """
            INSERT INTO assets (user_id, type, title, currency, created_at)
            VALUES ($1, $2, $3, 'RUB', NOW())
            RETURNING id
            """,
            user_id, asset.type, asset.title
        )
        await conn.execute(
            """
            INSERT INTO asset_values (asset_id, amount, created_at)
            VALUES ($1, $2, NOW())
            """,
            asset_id, asset.amount
        )
        return {"status": "ok", "asset_id": asset_id}

# Долги
@app.get("/api/liabilities")
async def get_liabilities(user_id: int = Depends(get_user_id)):
    """Получить список долгов"""
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT l.id AS liability_id, l.title, l.type, l.currency,
                   v.amount, v.monthly_payment, v.created_at AS updated_at
            FROM liabilities l
            LEFT JOIN LATERAL (
                SELECT amount, monthly_payment, created_at
                FROM liability_values
                WHERE liability_id = l.id
                ORDER BY created_at DESC
                LIMIT 1
            ) v ON TRUE
            WHERE l.user_id = $1 AND (v.amount IS NULL OR v.amount > 0)
            ORDER BY l.type, v.amount ASC
            """,
            user_id
        )
        return [dict(r) for r in rows]

@app.post("/api/liabilities")
async def create_liability(liability: LiabilityCreate, user_id: int = Depends(get_user_id)):
    """Создать долг"""
    db = await get_db()
    async with db.acquire() as conn:
        liability_id = await conn.fetchval(
            """
            INSERT INTO liabilities (user_id, type, title, currency, created_at)
            VALUES ($1, $2, $3, 'RUB', NOW())
            RETURNING id
            """,
            user_id, liability.type, liability.title
        )
        await conn.execute(
            """
            INSERT INTO liability_values (liability_id, amount, monthly_payment, created_at)
            VALUES ($1, $2, $3, NOW())
            """,
            liability_id, liability.amount, liability.monthly_payment
        )
        return {"status": "ok", "liability_id": liability_id}

# Консультация
@app.get("/api/consultation")
async def get_consultation(user_id: int = Depends(get_user_id)):
    """Получить AI консультацию"""
    # Импортируем функции из bot.py
    import bot
    
    # Устанавливаем db для bot модуля
    bot.db = await get_db()
    
    consultation = await bot.generate_consultation(user_id)
    return {"consultation": consultation}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
