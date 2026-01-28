# FastAPI сервер для Telegram Web App
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import asyncpg
import os
from dotenv import load_dotenv
import hmac
import hashlib
import json

load_dotenv()

# Настройка логирования
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI()

# Подключаем статические файлы через встроенный StaticFiles
# Это должно решить проблему с 403 Forbidden
try:
    app.mount("/static", StaticFiles(directory="webapp/static"), name="static")
except Exception as e:
    print(f"Warning: Could not mount static files: {e}")

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

# Кэш для bot_module, чтобы избежать повторного импорта
_bot_module_cache = None

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
    import urllib.parse
    
    try:
        # URL декодируем init_data (на случай, если он пришел закодированным)
        init_data_decoded = urllib.parse.unquote(init_data)
        
        # Парсим initData
        params = {}
        for item in init_data_decoded.split('&'):
            if '=' in item:
                key, value = item.split('=', 1)
                # Декодируем значение (может быть закодировано несколько раз)
                params[key] = urllib.parse.unquote(value)
        
        # Проверяем hash
        hash_value = params.pop('hash', '')
        if not hash_value:
            raise HTTPException(status_code=401, detail="Missing hash in initData")
        
        # Создаем строку для проверки (важно: сортировка по ключам)
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(params.items()))
        
        # Создаем секретный ключ
        secret_key = hmac.new(
            "WebAppData".encode(), 
            BOT_TOKEN.encode(), 
            hashlib.sha256
        ).digest()
        
        # Вычисляем хеш
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Сравниваем хеши
        if calculated_hash != hash_value:
            import logging
            logging.error(f"Hash mismatch. Expected: {hash_value}, Got: {calculated_hash}")
            logging.error(f"Data check string: {data_check_string[:100]}...")
            raise HTTPException(status_code=401, detail="Invalid hash")
        
        # Парсим user
        user_str = params.get('user', '')
        if not user_str:
            raise HTTPException(status_code=401, detail="Missing user in initData")
        
        user = json.loads(user_str) if user_str else {}
        
        return user
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=401, detail=f"Invalid user JSON: {str(e)}")
    except Exception as e:
        import logging
        logging.error(f"Validation error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=401, detail=f"Validation error: {str(e)}")

async def get_user_id(request: Request) -> int:
    """Получить user_id из Telegram Web App"""
    # Пробуем получить init-data из заголовков (nginx может передавать как init-data или init_data)
    init_data = request.headers.get("init-data") or request.headers.get("init_data")
    
    if not init_data:
        # Логируем для отладки все заголовки (безопасно)
        import logging
        logging.warning("Missing init-data header in request")
        logging.warning(f"Available headers: {list(request.headers.keys())}")
        raise HTTPException(status_code=401, detail="Missing initData. Откройте приложение через Telegram.")
    
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error in get_user_id: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")

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
    try:
        with open("webapp/index.html", "r", encoding="utf-8") as f:
            content = f.read()
            # Добавляем заголовки для предотвращения кэширования
            headers = {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
            return HTMLResponse(content=content, headers=headers)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Web App не найден</h1><p>Проверьте путь к файлу webapp/index.html</p>", status_code=500)

# Статические файлы теперь обрабатываются через app.mount("/static", ...) выше
# Этот endpoint больше не нужен, но оставляем как fallback на случай проблем
@app.get("/static/{file_path:path}")
async def static_files_fallback(file_path: str):
    """Fallback для статических файлов (если mount не работает)"""
    import mimetypes
    
    file_path_clean = file_path.split('?')[0]  # Убираем query параметры для версионирования
    full_path = f"webapp/static/{file_path_clean}"
    
    # Проверяем существование файла
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {full_path}")
    
    # Определяем MIME-тип
    mime_type, _ = mimetypes.guess_type(full_path)
    if not mime_type:
        # Определяем по расширению
        if full_path.endswith('.css'):
            mime_type = 'text/css; charset=utf-8'
        elif full_path.endswith('.js'):
            mime_type = 'application/javascript; charset=utf-8'
        elif full_path.endswith('.html'):
            mime_type = 'text/html; charset=utf-8'
        else:
            mime_type = 'application/octet-stream'
    
    # Устанавливаем заголовки для предотвращения кэширования в разработке
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Content-Type": mime_type
    }
    
    return FileResponse(full_path, headers=headers, media_type=mime_type)

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

# Кэш для bot_module, чтобы избежать повторного импорта
_bot_module_cache = None

# Консультация
@app.get("/api/consultation")
async def get_consultation(user_id: int = Depends(get_user_id)):
    """Получить AI консультацию"""
    import asyncio
    import importlib.util
    import logging
    
    async def generate_consultation_with_timeout():
        """Генерация консультации с обработкой ошибок"""
        global _bot_module_cache
        
        try:
            # Используем кэшированный модуль, если он уже загружен
            if _bot_module_cache is None:
                logging.info("Loading bot.py module (first time)...")
                
                # Загружаем bot.py как модуль
                spec = importlib.util.spec_from_file_location("bot_module", "bot.py")
                if spec is None or spec.loader is None:
                    raise ImportError("Cannot load bot.py")
                
                bot_module = importlib.util.module_from_spec(spec)
                
                # Устанавливаем db перед выполнением модуля
                bot_module.db = await get_db()
                
                # Выполняем модуль (это может занять время из-за инициализации Bot/Dispatcher)
                logging.info("Executing bot.py module...")
                spec.loader.exec_module(bot_module)
                logging.info("bot.py module loaded successfully")
                
                _bot_module_cache = bot_module
            else:
                logging.info("Using cached bot.py module")
                # Обновляем db в кэшированном модуле
                _bot_module_cache.db = await get_db()
            
            # Вызываем функцию консультации
            logging.info(f"Generating consultation for user_id={user_id}...")
            consultation = await _bot_module_cache.generate_consultation(user_id)
            logging.info("Consultation generated successfully")
            return consultation
        except Exception as e:
            logging.error(f"Error generating consultation: {e}")
            import traceback
            logging.error(traceback.format_exc())
            raise
    
    try:
        logging.info(f"Consultation request received for user_id={user_id}")
        # Устанавливаем таймаут 60 секунд для генерации консультации
        consultation = await asyncio.wait_for(
            generate_consultation_with_timeout(),
            timeout=60.0
        )
        logging.info("Consultation request completed successfully")
        return {"consultation": consultation}
    except asyncio.TimeoutError:
        logging.error("Consultation generation timeout (60s)")
        return {
            "consultation": (
                "⏱️ Генерация консультации заняла слишком много времени.\n\n"
                "Попробуйте позже или используйте команду /consult в боте Telegram."
            )
        }
    except Exception as e:
        logging.error(f"Error in consultation endpoint: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return {
            "consultation": (
                "❌ Произошла ошибка при генерации консультации.\n\n"
                "Попробуйте позже или используйте команду /consult в боте Telegram.\n\n"
                f"Ошибка: {str(e)[:100]}"
            )
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
