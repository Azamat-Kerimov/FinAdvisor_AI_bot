# FastAPI сервер для Telegram Web App
# v_01.28.26 - Рефакторинг: полная бизнес-логика, проверка подписки, AI
from fastapi import FastAPI, HTTPException, Depends, Header, Request, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import tempfile
import asyncpg
import os
from dotenv import load_dotenv
import hmac
import hashlib
import json
import uuid
import base64
import asyncio
import httpx
from datetime import datetime, timedelta

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

# GigaChat credentials
G_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
G_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
G_SCOPE = os.getenv("GIGACHAT_SCOPE")
G_AUTH_URL = os.getenv("GIGACHAT_AUTH_URL")
G_API_URL = os.getenv("GIGACHAT_API_URL")
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat:2.0.28.2")

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


async def check_premium(user_id: int) -> bool:
    """Проверить активна ли подписка"""
    db = await get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT premium_until FROM users WHERE id=$1", user_id
        )
        if not row or not row['premium_until']:
            return False
        return row['premium_until'] > datetime.now()


async def require_premium(user_id: int = Depends(get_user_id)):
    """Dependency для проверки подписки - возвращает user_id если подписка активна"""
    if not await check_premium(user_id):
        raise HTTPException(
            status_code=403,
            detail="PREMIUM_REQUIRED"
        )
    return user_id

# Pydantic models
class TransactionCreate(BaseModel):
    amount: float
    category: str
    description: Optional[str] = None

class TransactionUpdate(BaseModel):
    amount: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None

class GoalCreate(BaseModel):
    title: str
    target: float
    description: Optional[str] = None

class AssetCreate(BaseModel):
    title: str
    type: str
    amount: float

class AssetUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[float] = None

class LiabilityCreate(BaseModel):
    title: str
    type: str
    amount: float
    monthly_payment: float

class LiabilityUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[float] = None
    monthly_payment: Optional[float] = None


class TransactionImportItem(BaseModel):
    """Один элемент из AI-парсера импорта"""
    date: str  # YYYY-MM-DD
    amount: float
    category: str
    description: Optional[str] = None


class ImportApplyRequest(BaseModel):
    mode: str  # "add" | "replace"
    transactions: List[TransactionImportItem]


class ConsultationMessageRequest(BaseModel):
    message: str


# API Endpoints

# Auth endpoint (без проверки подписки)
@app.post("/api/auth/telegram")
async def auth_telegram(request: Request):
    """Авторизация через Telegram Web App initData"""
    init_data = request.headers.get("init-data") or request.headers.get("init_data")
    
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")
    
    try:
        user = validate_telegram_webapp(init_data)
        tg_id = user.get('id')
        
        if not tg_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        # Получаем или создаем пользователя с 2 бесплатными месяцами
        db = await get_db()
        async with db.acquire() as conn:
            row = await conn.fetchrow("SELECT id, premium_until FROM users WHERE tg_id=$1", tg_id)
            if not row:
                # Новый пользователь - даем 2 бесплатных месяца
                free_months_until = datetime.now() + timedelta(days=60)
                await conn.execute(
                    "INSERT INTO users (tg_id, username, created_at, premium_until) VALUES ($1, $2, NOW(), $3)",
                    tg_id, user.get('username'), free_months_until
                )
                row = await conn.fetchrow("SELECT id, premium_until FROM users WHERE tg_id=$1", tg_id)
            
            premium_until = row['premium_until']
            premium_active = premium_until and premium_until > datetime.now()
            
            return {
                "user_id": row['id'],
                "premium_until": premium_until.isoformat() if premium_until else None,
                "premium_active": premium_active
            }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error in auth_telegram: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")


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
async def get_stats(user_id: int = Depends(require_premium)):
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
async def get_transactions(
    limit: int = 100,
    month: Optional[int] = None,
    year: Optional[int] = None,
    category: Optional[str] = None,
    type_: Optional[str] = Query(None, alias="type"),  # "income" | "expense"
    user_id: int = Depends(require_premium)
):
    """Получить список транзакций с фильтрами (месяц, год, категория, тип)"""
    db = await get_db()
    async with db.acquire() as conn:
        conditions = ["user_id = $1"]
        params: List = [user_id]
        n = 2
        if month is not None and year is not None:
            from datetime import date
            start = date(year, month, 1)
            end = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
            conditions.append(f"created_at >= ${n}::timestamp")
            conditions.append(f"created_at < ${n + 1}::timestamp")
            params.extend([start, end])
            n += 2
        if category:
            conditions.append(f"category = ${n}")
            params.append(category)
            n += 1
        if type_ == "income":
            conditions.append("amount >= 0")
        elif type_ == "expense":
            conditions.append("amount < 0")
        params.append(limit)
        q = f"""
            SELECT id, amount, category, description, created_at
            FROM transactions
            WHERE {" AND ".join(conditions)}
            ORDER BY created_at DESC
            LIMIT ${n}
            """
        rows = await conn.fetch(q, *params)
        return [dict(r) for r in rows]

@app.post("/api/transactions")
async def create_transaction(transaction: TransactionCreate, user_id: int = Depends(require_premium)):
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

@app.put("/api/transactions/{tx_id}")
async def update_transaction(
    tx_id: int,
    body: TransactionUpdate,
    user_id: int = Depends(require_premium)
):
    """Редактировать транзакцию"""
    db = await get_db()
    async with db.acquire() as conn:
        if body.amount is not None:
            await conn.execute(
                "UPDATE transactions SET amount=$1 WHERE id=$2 AND user_id=$3",
                body.amount, tx_id, user_id
            )
        if body.category is not None:
            await conn.execute(
                "UPDATE transactions SET category=$1 WHERE id=$2 AND user_id=$3",
                body.category, tx_id, user_id
            )
        if body.description is not None:
            await conn.execute(
                "UPDATE transactions SET description=$1 WHERE id=$2 AND user_id=$3",
                body.description, tx_id, user_id
            )
        return {"status": "ok"}

@app.delete("/api/transactions/{tx_id}")
async def delete_transaction(tx_id: int, user_id: int = Depends(require_premium)):
    """Удалить транзакцию"""
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "DELETE FROM transactions WHERE id=$1 AND user_id=$2",
            tx_id, user_id
        )
        return {"status": "ok"}


# --- Импорт транзакций из файла (PDF, Excel, изображения) + AI-парсер ---

def _extract_text_from_file(file_path: str, content_type: str, filename: str) -> str:
    """Извлечь текст из файла для передачи в AI-парсер."""
    ext = (filename or "").lower().split(".")[-1] if "." in (filename or "") else ""
    text_parts = []

    # Excel
    if content_type and ("spreadsheet" in content_type or "excel" in content_type) or ext in ("xlsx", "xls"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    text_parts.append("\t".join(str(c) if c is not None else "" for c in row))
            wb.close()
            return "\n".join(text_parts)
        except Exception as e:
            logging.warning(f"openpyxl read failed: {e}")
            return f"Таблица (ошибка чтения): {e}"

    # PDF
    if content_type and "pdf" in content_type or ext == "pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
            return "\n".join(text_parts)
        except Exception as e:
            logging.warning(f"PDF read failed: {e}")
            return f"PDF (ошибка чтения): {e}"

    # Изображения — возвращаем заглушку; для OCR нужна отдельная библиотека
    if content_type and "image" in content_type or ext in ("png", "jpg", "jpeg"):
        return "[Изображение загружено. Распознавание изображений пока не поддерживается — загрузите PDF или Excel.]"

    return "\n".join(text_parts) if text_parts else "[Не удалось извлечь текст]"


async def _parse_transactions_with_ai(raw_text: str) -> tuple[list[dict], list[str]]:
    """Вызвать GigaChat для извлечения списка транзакций из текста. Возвращает (transactions, errors)."""
    if not raw_text or len(raw_text.strip()) < 10:
        return [], ["Мало данных для распознавания"]

    prompt = (
        "Из следующего текста (выписка, таблица, список операций) извлеки транзакции.\n"
        "Для каждой транзакции определи: дата (YYYY-MM-DD), сумма (число: положительное — доход, отрицательное — расход), "
        "категория (одно слово на русском: Еда, Транспорт, Зарплата, Развлечения, Здоровье, Жильё, Прочее и т.д.), описание (кратко).\n\n"
        "Ответь ТОЛЬКО валидным JSON-массивом объектов без комментариев, в формате:\n"
        '[{"date":"YYYY-MM-DD","amount":число,"category":"категория","description":"описание"}]\n'
        "Если транзакций нет или не удалось распознать — верни [].\n"
        "Нормализуй категории к одному из: Еда, Транспорт, Зарплата, Развлечения, Здоровье, Жильё, Маркетплейсы, Прочее (если не подходит — Прочее).\n\n"
        "Текст:\n" + raw_text[:15000]
    )
    try:
        messages = [
            {"role": "system", "content": "Ты парсер финансовых транзакций. Отвечай только JSON-массивом."},
            {"role": "user", "content": prompt}
        ]
        answer = await gigachat_request(messages)
        answer = (answer or "").strip()
        # Выделить JSON из ответа (на случай обёртки в markdown)
        if "```" in answer:
            start = answer.find("[")
            end = answer.rfind("]") + 1
            if start >= 0 and end > start:
                answer = answer[start:end]
        import re
        json_match = re.search(r"\[[\s\S]*\]", answer)
        if not json_match:
            return [], [f"AI не вернул список транзакций: {answer[:200]}"]
        data = json.loads(json_match.group())
        transactions = []
        errors = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                errors.append(f"Строка {i+1}: не объект")
                continue
            try:
                date_str = str(item.get("date", ""))[:10]
                amount = float(item.get("amount", 0))
                category = (item.get("category") or "Прочее").strip() or "Прочее"
                description = (item.get("description") or "").strip() or None
                if not date_str or len(date_str) < 10:
                    errors.append(f"Строка {i+1}: некорректная дата")
                    continue
                transactions.append({
                    "date": date_str,
                    "amount": amount,
                    "category": category,
                    "description": description
                })
            except (TypeError, ValueError) as e:
                errors.append(f"Строка {i+1}: {e}")
        return transactions, errors
    except json.JSONDecodeError as e:
        return [], [f"Ошибка разбора JSON: {e}"]
    except Exception as e:
        logging.exception("AI parse transactions")
        return [], [str(e)]


@app.post("/api/transactions/import")
async def import_transactions_file(
    file: UploadFile = File(...),
    user_id: int = Depends(require_premium)
):
    """Загрузить файл (PDF, Excel, изображение), распознать транзакции через AI. Возвращает предпросмотр (transactions + errors)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    content_type = file.content_type or ""
    suffix = ".xlsx" if "xlsx" in file.filename.lower() else (".pdf" if "pdf" in file.filename.lower() else ".bin")
    try:
        body = await file.read()
        if len(body) > 10 * 1024 * 1024:  # 10 MB
            raise HTTPException(status_code=400, detail="File too large (max 10 MB)")
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(body)
            tmp_path = tmp.name
        try:
            text = _extract_text_from_file(tmp_path, content_type, file.filename)
            transactions, errors = await _parse_transactions_with_ai(text)
            return {"transactions": transactions, "errors": errors}
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("import_transactions_file")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transactions/import/apply")
async def import_transactions_apply(
    body: ImportApplyRequest,
    user_id: int = Depends(require_premium)
):
    """Применить импорт: добавить к текущим или заменить все транзакции."""
    if body.mode not in ("add", "replace"):
        raise HTTPException(status_code=400, detail="mode must be 'add' or 'replace'")
    db = await get_db()
    async with db.acquire() as conn:
        if body.mode == "replace":
            await conn.execute("DELETE FROM transactions WHERE user_id = $1", user_id)
        for t in body.transactions:
            try:
                from datetime import datetime
                dt = datetime.strptime(t.date[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                dt = datetime.now()
            await conn.execute(
                """
                INSERT INTO transactions (user_id, amount, category, description, created_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id, t.amount, t.category, (t.description or "").strip() or None, dt
            )
    return {"status": "ok", "applied": len(body.transactions)}

# Цели
@app.get("/api/goals")
async def get_goals(user_id: int = Depends(require_premium)):
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
async def create_goal(goal: GoalCreate, user_id: int = Depends(require_premium)):
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
async def delete_goal(goal_id: int, user_id: int = Depends(require_premium)):
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
async def get_assets(user_id: int = Depends(require_premium)):
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
async def create_asset(asset: AssetCreate, user_id: int = Depends(require_premium)):
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

@app.put("/api/assets/{asset_id}")
async def update_asset(
    asset_id: int,
    body: AssetUpdate,
    user_id: int = Depends(require_premium)
):
    """Редактировать актив (добавляет новую запись в asset_values при изменении суммы)"""
    db = await get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM assets WHERE id=$1 AND user_id=$2", asset_id, user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Asset not found")
        if body.title is not None:
            await conn.execute(
                "UPDATE assets SET title=$1 WHERE id=$2", body.title, asset_id
            )
        if body.type is not None:
            await conn.execute(
                "UPDATE assets SET type=$1 WHERE id=$2", body.type, asset_id
            )
        if body.amount is not None:
            await conn.execute(
                """
                INSERT INTO asset_values (asset_id, amount, created_at)
                VALUES ($1, $2, NOW())
                """,
                asset_id, body.amount
            )
        return {"status": "ok"}

@app.delete("/api/assets/{asset_id}")
async def delete_asset(asset_id: int, user_id: int = Depends(require_premium)):
    """Удалить актив"""
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "DELETE FROM assets WHERE id=$1 AND user_id=$2",
            asset_id, user_id
        )
        return {"status": "ok"}

# Долги
@app.get("/api/liabilities")
async def get_liabilities(user_id: int = Depends(require_premium)):
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
async def create_liability(liability: LiabilityCreate, user_id: int = Depends(require_premium)):
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

@app.put("/api/liabilities/{liability_id}")
async def update_liability(
    liability_id: int,
    body: LiabilityUpdate,
    user_id: int = Depends(require_premium)
):
    """Редактировать долг"""
    db = await get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM liabilities WHERE id=$1 AND user_id=$2",
            liability_id, user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Liability not found")
        if body.title is not None:
            await conn.execute(
                "UPDATE liabilities SET title=$1 WHERE id=$2", body.title, liability_id
            )
        if body.type is not None:
            await conn.execute(
                "UPDATE liabilities SET type=$1 WHERE id=$2", body.type, liability_id
            )
        if body.amount is not None or body.monthly_payment is not None:
            r = await conn.fetchrow(
                "SELECT amount, monthly_payment FROM liability_values WHERE liability_id=$1 ORDER BY created_at DESC LIMIT 1",
                liability_id
            )
            amt = float(r["amount"]) if r else 0
            mp = float(r.get("monthly_payment") or 0) if r else 0
            if body.amount is not None:
                amt = body.amount
            if body.monthly_payment is not None:
                mp = body.monthly_payment
            await conn.execute(
                """
                INSERT INTO liability_values (liability_id, amount, monthly_payment, created_at)
                VALUES ($1, $2, $3, NOW())
                """,
                liability_id, amt, mp
            )
        return {"status": "ok"}

@app.delete("/api/liabilities/{liability_id}")
async def delete_liability(liability_id: int, user_id: int = Depends(require_premium)):
    """Удалить долг"""
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "DELETE FROM liabilities WHERE id=$1 AND user_id=$2",
            liability_id, user_id
        )
        return {"status": "ok"}

# ============================================
# AI Functions (GigaChat)
# ============================================

async def get_gigachat_token():
    """Получить токен доступа GigaChat"""
    auth_str = f"{G_CLIENT_ID}:{G_CLIENT_SECRET}"
    b64 = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4())
    }
    data = {"scope": G_SCOPE}
    async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
        r = await client.post(G_AUTH_URL, headers=headers, data=data)
        r.raise_for_status()
        return r.json().get("access_token")


async def gigachat_request(messages):
    """Запрос к GigaChat API"""
    token = await get_gigachat_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GIGACHAT_MODEL,
        "messages": messages,
        "temperature": 0.3
    }
    async with httpx.AsyncClient(verify=False, timeout=40.0) as client:
        r = await client.post(G_API_URL, headers=headers, json=payload)
        r.raise_for_status()
        j = r.json()
        if "choices" in j and j["choices"]:
            return j["choices"][0]["message"]["content"]
        return json.dumps(j, ensure_ascii=False)


# AI Cache helpers
def _hash_input(user_message: str, finance_snapshot: str) -> str:
    """Хеширование входных данных для кэша"""
    h = hashlib.sha256((user_message.strip().lower() + "\n" + finance_snapshot).encode("utf-8"))
    return h.hexdigest()


async def get_cached_ai_reply(user_id: int, user_message: str, finance_snapshot: str):
    """Получить ответ из кэша"""
    h = _hash_input(user_message, finance_snapshot)
    db = await get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT answer FROM ai_cache WHERE user_id=$1 AND input_hash=$2 ORDER BY created_at DESC LIMIT 1",
            user_id, h
        )
        return row["answer"] if row else None


async def save_ai_cache(user_id: int, user_message: str, finance_snapshot: str, ai_answer: str):
    """Сохранить ответ в кэш"""
    h = _hash_input(user_message, finance_snapshot)
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "INSERT INTO ai_cache (user_id, input_hash, answer, created_at) VALUES ($1,$2,$3,NOW())",
            user_id, h, ai_answer
        )


async def save_message(user_id: int, role: str, content: str):
    """Сохранить сообщение в контекст"""
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "INSERT INTO ai_context (user_id, role, content, created_at) VALUES ($1,$2,$3,NOW())",
            user_id, role, content
        )


async def analyze_user_finances_text(user_id: int) -> str:
    """Анализ финансов пользователя для AI"""
    MAX_TX_FOR_ANALYSIS = 200
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT amount, category, description, created_at FROM transactions WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2",
            user_id, MAX_TX_FOR_ANALYSIS
        )
        
        s = ""
        if rows:
            s = "Последние транзакции:\n"
            for r in rows:
                ts = r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else ""
                s += f"- {r['amount']}₽ | {r.get('category') or '-'} | {r.get('description') or ''} | {ts}\n"
        else:
            s = "У пользователя нет транзакций.\n"
        
        goals = await conn.fetch("SELECT title, target, current, created_at FROM goals WHERE user_id=$1", user_id)
        if goals:
            s += "\nЦели:\n"
            for g in goals:
                s += f"- {g.get('title','Цель')}: {g['current']}/{g['target']} ₽\n"
        
        # Активы
        assets_rows = await conn.fetch(
            """
            SELECT a.title, a.type, v.amount
            FROM assets a
            LEFT JOIN LATERAL (
                SELECT amount FROM asset_values WHERE asset_id = a.id ORDER BY created_at DESC LIMIT 1
            ) v ON TRUE
            WHERE a.user_id = $1 AND (v.amount IS NULL OR v.amount > 0)
            """,
            user_id
        )
        if assets_rows:
            total_assets = sum([a["amount"] for a in assets_rows if a["amount"]])
            s += f"\nАктивы (итого {total_assets}₽):\n"
            for a in assets_rows:
                if a["amount"]:
                    s += f"- {a['title']} ({a['type']}): {a['amount']}₽\n"
        
        # Долги
        liabs_rows = await conn.fetch(
            """
            SELECT l.title, l.type, v.amount
            FROM liabilities l
            LEFT JOIN LATERAL (
                SELECT amount FROM liability_values WHERE liability_id = l.id ORDER BY created_at DESC LIMIT 1
            ) v ON TRUE
            WHERE l.user_id = $1 AND (v.amount IS NULL OR v.amount > 0)
            """,
            user_id
        )
        if liabs_rows:
            total_liabs = sum([l["amount"] for l in liabs_rows if l["amount"]])
            s += f"\nДолги (итого {total_liabs}₽):\n"
            for l in liabs_rows:
                if l["amount"]:
                    s += f"- {l['title']} ({l['type']}): {l['amount']}₽\n"
        
        total_assets = sum([a["amount"] for a in assets_rows if a.get("amount")]) if assets_rows else 0
        total_liabs = sum([l["amount"] for l in liabs_rows if l.get("amount")]) if liabs_rows else 0
        s += f"\nЧистый капитал: {total_assets - total_liabs}₽\n"
        return s


async def generate_consultation(user_id: int) -> str:
    """Генерация финансовой консультации"""
    try:
        finance_snapshot = await analyze_user_finances_text(user_id)
        
        # Если нет данных
        if not finance_snapshot or ("нет транзакций" in finance_snapshot.lower() and "нет активов" in finance_snapshot.lower()):
            return (
                "📊 *Ваша финансовая консультация*\n\n"
                "У вас пока нет финансовых данных для анализа.\n\n"
                "Рекомендации для начала:\n"
                "1. Начните вести учет доходов и расходов\n"
                "2. Добавьте информацию о ваших активах\n"
                "3. Установите финансовые цели\n"
                "4. Регулярно обновляйте данные\n\n"
                "После добавления данных вы получите персональные рекомендации!"
            )
        
        # Проверяем кэш
        cached = await get_cached_ai_reply(user_id, "CONSULT_REQUEST", finance_snapshot)
        if cached:
            return cached
        
        system_prompt = (
            "Ты — персональный финансовый консультант.\n"
            "Проанализируй финансовые данные пользователя и подготовь структурированные, "
            "понятные и практичные рекомендации.\n\n"
        
            "ОБЯЗАТЕЛЬНО проанализируй и используй в выводах:\n"
            "1. ТРАНЗАКЦИИ — доходы и расходы, основные паттерны, категории с наибольшими тратами "
            "(указывай суммы и примеры).\n"
            "2. ЦЕЛИ — финансовые цели пользователя и текущий прогресс по ним.\n"
            "3. АКТИВЫ — текущее состояние капитала и источники дохода.\n"
            "4. ДОЛГИ — обязательства, их размер и влияние на бюджет.\n\n"
        
            "ФОРМАТ ОТВЕТА (строго соблюдай структуру):\n\n"
        
            "📊 *Текущее финансовое положение*\n"
            "(краткая сводка в 2-3 предложениях)\n\n"
        
            "💰 *Доходы и расходы*\n"
            "• Доходы: [сумма] ₽ ([категории])\n"
            "• Расходы: [сумма] ₽ ([топ-3 категории с суммами])\n"
            "• Остаток: [сумма] ₽\n\n"
        
            "🎯 *Финансовые цели*\n"
            "(список целей с прогрессом в формате: Название — [текущее]/[целевое] ₽ ([процент]%))\n\n"
        
            "💼 *Активы и долги*\n"
            "• Активы: [сумма] ₽ ([список])\n"
            "• Долги: [сумма] ₽ ([список])\n"
            "• Чистый капитал: [сумма] ₽\n\n"
        
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        
            "📋 *Практический план действий*\n\n"
        
            "*1️⃣ Ближайший месяц*\n"
            "• [Конкретное действие 1 с суммой экономии]\n"
            "• [Конкретное действие 2 с суммой экономии]\n"
            "• [Конкретное действие 3 с суммой экономии]\n\n"
        
            "*2️⃣ Горизонт 6 месяцев*\n"
            "• [Шаг 1 для долгосрочных целей]\n"
            "• [Шаг 2 для работы с инвестициями/долгами]\n"
            "• [Шаг 3 для увеличения доходов]\n\n"
        
            "*3️⃣ Оптимизация бюджета*\n"
            "• [Категория 1]: сократить с [сумма] до [сумма] ₽ (экономия [сумма] ₽)\n"
            "• [Категория 2]: перераспределить [сумма] ₽ на [цель]\n"
            "• [Категория 3]: [конкретная рекомендация]\n\n"
        
            "*4️⃣ Резервный фонд*\n"
            "• Рекомендуемый размер: [сумма] ₽ (3-6 месячных расходов)\n"
            "• Откладывать: [сумма] ₽ ежемесячно\n"
            "• Срок накопления: [количество] месяцев\n"
            "• Приоритет: [высокий/средний/низкий] с учетом текущих долгов\n\n"
        
            "ТРЕБОВАНИЯ:\n"
            "- Используй Markdown форматирование (*жирный*, списки)\n"
            "- Каждый пункт на новой строке\n"
            "- Всегда указывай конкретные суммы\n"
            "- Избегай длинных абзацев — используй списки\n"
            "- Будь конкретным и практичным\n"
            "- Не используй общие фразы типа 'пересмотреть' без конкретики\n\n"
        
            "🚨 КРИТИЧЕСКИ ВАЖНО - ФОРМАТ ЧИСЕЛ (ОБЯЗАТЕЛЬНО СОБЛЮДАЙ):\n"
            "- ВСЕГДА используй формат с пробелами: 200 000 ₽, 1 500 000 ₽, 12 000 000 ₽\n"
            "- ЗАПРЕЩЕНО использовать научную нотацию (2.7E+5, 1.5E+4 - ЗАПРЕЩЕНО!)\n"
            "- ЗАПРЕЩЕНО использовать точки как разделители (12.000.000 - ЗАПРЕЩЕНО!)\n"
            "- ЗАПРЕЩЕНО показывать знаки после запятой (15.000 - ЗАПРЕЩЕНО!)\n"
            "- ПРАВИЛЬНО: 270 000 ₽ (не 2.7E+5, не 270000, не 270.000)\n"
            "- ПРАВИЛЬНО: 77 000 ₽ (не 7.7E+4, не 77000, не 77.000)\n"
            "- ПРАВИЛЬНО: 15 000 ₽ (не 1.5E+4, не 15000, не 15.000)\n"
            "- ПРАВИЛЬНО: 12 000 000 ₽ (не 12.000.000, не 12000000)\n"
            "- Всегда округляй до целых чисел, без десятичных знаков\n"
            "- Формат: [число с пробелами] ₽ (например: 200 000 ₽, 1 500 000 ₽)\n\n"
        
            "Отвечай на русском языке.\n"
            "Стиль — деловой, дружелюбный, понятный."
        )
        messages = [
            {"role":"system","content":system_prompt},
            {"role":"user","content":finance_snapshot}
        ]
        
        answer = await gigachat_request(messages)
        
        if not answer or len(answer.strip()) == 0:
            return "Извините, не удалось сгенерировать консультацию. Попробуйте позже."
        
        await save_message(user_id, "assistant", f"CONSULTATION: {answer}")
        await save_ai_cache(user_id, "CONSULT_REQUEST", finance_snapshot, answer)
        return answer
        
    except Exception as e:
        logging.error(f"Ошибка при генерации консультации: {e}")
        import traceback
        traceback.print_exc()
        return (
            "❌ *Ошибка при генерации консультации*\n\n"
            "Извините, произошла техническая ошибка.\n"
            "Попробуйте позже или обратитесь в поддержку."
        )


# Отчеты
@app.get("/api/reports")
async def get_reports(user_id: int = Depends(require_premium)):
    """Получить отчеты (3 графика с пояснениями)"""
    db = await get_db()
    async with db.acquire() as conn:
        # График 1: Расходы по категориям за текущий месяц
        now = datetime.now()
        since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        expense_rows = await conn.fetch(
            """
            SELECT category, SUM(ABS(amount)) as total
            FROM transactions
            WHERE user_id=$1 AND created_at >= $2 AND amount < 0
            GROUP BY category
            ORDER BY total DESC
            LIMIT 10
            """,
            user_id, since
        )
        
        expense_by_cat = {r['category'] or 'Прочее': float(r['total']) for r in expense_rows}
        total_expenses = sum(expense_by_cat.values())
        
        # График 2: Прогресс по целям
        goals_rows = await conn.fetch(
            """
            SELECT title, target, current
            FROM goals
            WHERE user_id=$1
            ORDER BY id
            """,
            user_id
        )
        
        goals_data = [
            {
                'title': g['title'],
                'target': float(g['target']),
                'current': float(g['current']),
                'progress': min(100, (float(g['current']) / float(g['target']) * 100) if g['target'] > 0 else 0)
            }
            for g in goals_rows
        ]
        
        # График 3: Динамика капитала за последние 12 недель
        weeks_data = []
        for i in range(11, -1, -1):
            week_end = now - timedelta(weeks=i)
            # Находим воскресенье недели
            days_since_monday = (week_end.weekday()) % 7
            sunday = week_end - timedelta(days=days_since_monday) + timedelta(days=6)
            sunday = sunday.replace(hour=23, minute=59, second=59)
            
            # Получаем активы на эту дату
            assets_rows = await conn.fetch(
                """
                SELECT a.id, COALESCE(
                    (SELECT amount FROM asset_values 
                     WHERE asset_id = a.id AND created_at <= $2 
                     ORDER BY created_at DESC LIMIT 1), 0
                ) as amount
                FROM assets a
                WHERE a.user_id = $1
                """,
                user_id, sunday
            )
            total_assets = sum(float(r['amount']) for r in assets_rows)
            
            # Получаем долги на эту дату
            liabs_rows = await conn.fetch(
                """
                SELECT l.id, COALESCE(
                    (SELECT amount FROM liability_values 
                     WHERE liability_id = l.id AND created_at <= $2 
                     ORDER BY created_at DESC LIMIT 1), 0
                ) as amount
                FROM liabilities l
                WHERE l.user_id = $1
                """,
                user_id, sunday
            )
            total_liabs = sum(float(r['amount']) for r in liabs_rows)
            
            net_capital = total_assets - total_liabs
            weeks_data.append({
                'week': sunday.strftime('%d.%m'),
                'assets': total_assets,
                'liabilities': total_liabs,
                'net_capital': net_capital
            })
        
        return {
            "chart1": {
                "title": "Расходы по категориям за текущий месяц",
                "description": f"Общая сумма расходов: {total_expenses:,.0f} ₽".replace(',', ' '),
                "data": expense_by_cat
            },
            "chart2": {
                "title": "Прогресс по финансовым целям",
                "description": f"Всего целей: {len(goals_data)}",
                "data": goals_data
            },
            "chart3": {
                "title": "Динамика чистого капитала за последние 12 недель",
                "description": f"Текущий чистый капитал: {weeks_data[-1]['net_capital']:,.0f} ₽".replace(',', ' ') if weeks_data else "Нет данных",
                "data": weeks_data
            }
        }


# Консультация - история
@app.get("/api/consultation/history")
async def get_consultation_history(user_id: int = Depends(require_premium)):
    """Получить историю консультаций"""
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT content, created_at
            FROM ai_context
            WHERE user_id=$1 AND role='assistant' AND content LIKE 'CONSULTATION:%'
            ORDER BY created_at DESC
            LIMIT 10
            """,
            user_id
        )
        return [{"content": r['content'].replace('CONSULTATION: ', ''), "date": r['created_at'].isoformat()} for r in rows]


# Консультация - проверка лимита
async def check_consultation_limit(user_id: int) -> tuple[bool, int]:
    """Проверить лимит консультаций (5 в месяц)
    
    Returns:
        tuple[bool, int]: (can_request, requests_used)
    """
    db = await get_db()
    now = datetime.now()
    since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    async with db.acquire() as conn:
        count = await conn.fetchval(
            """
            SELECT COUNT(*) 
            FROM ai_context
            WHERE user_id=$1 AND role='assistant' 
            AND content LIKE 'CONSULTATION:%'
            AND created_at >= $2
            """,
            user_id, since
        )
        return count < 5, count


# Консультация
@app.get("/api/consultation")
async def get_consultation(user_id: int = Depends(require_premium)):
    """Получить AI консультацию (лимит 5 в месяц)"""
    # Проверяем лимит
    can_request, requests_used = await check_consultation_limit(user_id)
    
    if not can_request:
        return {
            "consultation": None,
            "error": f"Лимит консультаций исчерпан. Использовано: {requests_used}/5 в этом месяце.",
            "limit_reached": True,
            "requests_used": requests_used
        }
    
    try:
        logging.info(f"Consultation request received for user_id={user_id} ({requests_used + 1}/5)")
        consultation = await asyncio.wait_for(
            generate_consultation(user_id),
            timeout=60.0
        )
        logging.info("Consultation request completed successfully")
        return {
            "consultation": consultation,
            "requests_used": requests_used + 1,
            "limit_reached": False
        }
    except asyncio.TimeoutError:
        logging.error("Consultation generation timeout (60s)")
        return {
            "consultation": (
                "⏱️ Генерация консультации заняла слишком много времени.\n\n"
                "Попробуйте позже."
            )
        }
    except Exception as e:
        logging.error(f"Error in consultation endpoint: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return {
            "consultation": (
                "❌ Произошла ошибка при генерации консультации.\n\n"
                "Попробуйте позже.\n\n"
                f"Ошибка: {str(e)[:100]}"
            )
        }


# Консультация — ввод целей через сообщение (AI извлекает цели и сохраняет в goals)
async def _extract_goals_from_message(user_message: str) -> list[dict]:
    """Вызвать GigaChat для извлечения финансовых целей из текста. Возвращает список { title, target, description }."""
    prompt = (
        "Пользователь написал сообщение о своих финансовых целях. Извлеки из текста цели.\n\n"
        "Цель — это намерение с суммой и/или сроком, например: накопить 1 000 000 за 2 года, "
        "пассивный доход 50 000 в месяц, погасить долг 200 000.\n\n"
        "Ответь ТОЛЬКО валидным JSON-массивом объектов без комментариев:\n"
        '[{"title":"краткое название цели","target":число_в_рублях,"description":"описание или срок"}]'
        "\nЕсли целей нет — верни []. target — целевая сумма в рублях (число)."
    )
    try:
        messages = [
            {"role": "system", "content": "Ты извлекаешь финансовые цели из текста. Отвечай только JSON-массивом."},
            {"role": "user", "content": prompt + "\n\nСообщение пользователя:\n" + (user_message or "")[:2000]}
        ]
        answer = await gigachat_request(messages)
        answer = (answer or "").strip()
        import re
        json_match = re.search(r"\[[\s\S]*\]", answer)
        if not json_match:
            return []
        data = json.loads(json_match.group())
        result = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                title = str(item.get("title") or "Цель").strip() or "Цель"
                target = float(item.get("target", 0))
                if target <= 0:
                    continue
                description = (item.get("description") or "").strip() or None
                result.append({"title": title, "target": target, "description": description})
            except (TypeError, ValueError):
                continue
        return result
    except (json.JSONDecodeError, Exception):
        return []


@app.post("/api/consultation/message")
async def consultation_message(
    body: ConsultationMessageRequest,
    user_id: int = Depends(require_premium)
):
    """Отправить сообщение в консультацию: AI извлекает цели и сохраняет в goals."""
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    await save_message(user_id, "user", message)
    goals_added = []
    try:
        extracted = await _extract_goals_from_message(message)
        db = await get_db()
        async with db.acquire() as conn:
            for g in extracted:
                await conn.execute(
                    "INSERT INTO goals (user_id, target, current, title, description, created_at) VALUES ($1, $2, 0, $3, $4, NOW())",
                    user_id, g["target"], g["title"], g.get("description")
                )
                goals_added.append({"title": g["title"], "target": g["target"]})
    except Exception as e:
        logging.exception("consultation_message extract goals")
    reply = "Сообщение принято."
    if goals_added:
        reply = f"Цели добавлены: {', '.join(g['title'] + ' — ' + str(int(g['target'])) + ' ₽' for g in goals_added)}."
    return {"goals_added": goals_added, "reply": reply}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
