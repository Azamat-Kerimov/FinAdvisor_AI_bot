-- Схема БД FinAdvisor (PostgreSQL)
-- Применить к тестовой БД: psql -U postgres -d FinAdvisor_Beta -f scripts/schema_finadvisor.sql
-- Или из корня: psql -U postgres -d FinAdvisor_Beta -f scripts/schema_finadvisor.sql

-- Пользователи (Telegram)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE,
    username TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    premium_until TIMESTAMPTZ
);

-- Категории транзакций (Расход/Доход)
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL
);

-- Маппинг категорий банка -> категория приложения
CREATE TABLE IF NOT EXISTS category_mapping (
    bank_category TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    bank_category_type TEXT NOT NULL,
    PRIMARY KEY (bank_category, bank_category_type)
);

-- Транзакции
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount NUMERIC NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_created ON transactions(user_id, created_at);

-- Цели
CREATE TABLE IF NOT EXISTS goals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target NUMERIC NOT NULL,
    current NUMERIC DEFAULT 0,
    title TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Бюджеты (лимиты по категориям)
CREATE TABLE IF NOT EXISTS budgets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    monthly_limit NUMERIC NOT NULL,
    UNIQUE (user_id, category)
);

-- Активы
CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    currency TEXT DEFAULT 'RUB',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- История значений активов (версионирование)
CREATE TABLE IF NOT EXISTS asset_values (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    amount NUMERIC NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Пассивы (долги)
CREATE TABLE IF NOT EXISTS liabilities (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    currency TEXT DEFAULT 'RUB',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- История значений пассивов
CREATE TABLE IF NOT EXISTS liability_values (
    id SERIAL PRIMARY KEY,
    liability_id INTEGER NOT NULL REFERENCES liabilities(id) ON DELETE CASCADE,
    amount NUMERIC NOT NULL,
    monthly_payment NUMERIC DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Кэш ответов AI (консультации)
CREATE TABLE IF NOT EXISTS ai_cache (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    input_hash TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Контекст сообщений AI (история для лимита консультаций)
CREATE TABLE IF NOT EXISTS ai_context (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Минимальный и расширенный набор категорий (если таблица пустая или категории отсутствуют)
INSERT INTO categories (name, type) SELECT 'Прочие расходы', 'Расход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Прочие расходы' AND type = 'Расход');
INSERT INTO categories (name, type) SELECT 'Прочие доходы', 'Доход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Прочие доходы' AND type = 'Доход');
INSERT INTO categories (name, type) SELECT 'Еда и продукты', 'Расход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Еда и продукты' AND type = 'Расход');
INSERT INTO categories (name, type) SELECT 'Транспорт', 'Расход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Транспорт' AND type = 'Расход');
INSERT INTO categories (name, type) SELECT 'Жильё и коммуналка', 'Расход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Жильё и коммуналка' AND type = 'Расход');
INSERT INTO categories (name, type) SELECT 'Здоровье', 'Расход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Здоровье' AND type = 'Расход');
INSERT INTO categories (name, type) SELECT 'Развлечения', 'Расход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Развлечения' AND type = 'Расход');
INSERT INTO categories (name, type) SELECT 'Одежда и обувь', 'Расход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Одежда и обувь' AND type = 'Расход');
INSERT INTO categories (name, type) SELECT 'Связь и интернет', 'Расход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Связь и интернет' AND type = 'Расход');
INSERT INTO categories (name, type) SELECT 'Образование', 'Расход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Образование' AND type = 'Расход');
INSERT INTO categories (name, type) SELECT 'Зарплата', 'Доход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Зарплата' AND type = 'Доход');
INSERT INTO categories (name, type) SELECT 'Подработка', 'Доход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Подработка' AND type = 'Доход');
INSERT INTO categories (name, type) SELECT 'Инвестиции и дивиденды', 'Доход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Инвестиции и дивиденды' AND type = 'Доход');
INSERT INTO categories (name, type) SELECT 'Подарки и возвраты', 'Доход' WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Подарки и возвраты' AND type = 'Доход');

-- Маппинг категорий Сбера/Т-Банка в категории приложения (чтобы операции не уходили все в «Прочее»)
INSERT INTO category_mapping (bank_category, category_id, bank_category_type)
SELECT 'зарплата', id, 'Доход' FROM categories WHERE name = 'Зарплата' AND type = 'Доход' LIMIT 1
ON CONFLICT (bank_category, bank_category_type) DO NOTHING;
INSERT INTO category_mapping (bank_category, category_id, bank_category_type)
SELECT 'переводы от людей', id, 'Доход' FROM categories WHERE name = 'Подработка' AND type = 'Доход' LIMIT 1
ON CONFLICT (bank_category, bank_category_type) DO NOTHING;
INSERT INTO category_mapping (bank_category, category_id, bank_category_type)
SELECT 'возврат', id, 'Доход' FROM categories WHERE name = 'Подарки и возвраты' AND type = 'Доход' LIMIT 1
ON CONFLICT (bank_category, bank_category_type) DO NOTHING;
INSERT INTO category_mapping (bank_category, category_id, bank_category_type)
SELECT 'пополнение', id, 'Доход' FROM categories WHERE name = 'Прочие доходы' AND type = 'Доход' LIMIT 1
ON CONFLICT (bank_category, bank_category_type) DO NOTHING;
INSERT INTO category_mapping (bank_category, category_id, bank_category_type)
SELECT 'еда', id, 'Расход' FROM categories WHERE name = 'Еда и продукты' AND type = 'Расход' LIMIT 1
ON CONFLICT (bank_category, bank_category_type) DO NOTHING;
INSERT INTO category_mapping (bank_category, category_id, bank_category_type)
SELECT 'транспорт', id, 'Расход' FROM categories WHERE name = 'Транспорт' AND type = 'Расход' LIMIT 1
ON CONFLICT (bank_category, bank_category_type) DO NOTHING;
INSERT INTO category_mapping (bank_category, category_id, bank_category_type)
SELECT 'здоровье', id, 'Расход' FROM categories WHERE name = 'Здоровье' AND type = 'Расход' LIMIT 1
ON CONFLICT (bank_category, bank_category_type) DO NOTHING;
INSERT INTO category_mapping (bank_category, category_id, bank_category_type)
SELECT 'развлечения', id, 'Расход' FROM categories WHERE name = 'Развлечения' AND type = 'Расход' LIMIT 1
ON CONFLICT (bank_category, bank_category_type) DO NOTHING;
INSERT INTO category_mapping (bank_category, category_id, bank_category_type)
SELECT 'связь', id, 'Расход' FROM categories WHERE name = 'Связь и интернет' AND type = 'Расход' LIMIT 1
ON CONFLICT (bank_category, bank_category_type) DO NOTHING;
INSERT INTO category_mapping (bank_category, category_id, bank_category_type)
SELECT 'зачисления', id, 'Доход' FROM categories WHERE name = 'Прочие доходы' AND type = 'Доход' LIMIT 1
ON CONFLICT (bank_category, bank_category_type) DO NOTHING;
INSERT INTO category_mapping (bank_category, category_id, bank_category_type)
SELECT 'списание', id, 'Расход' FROM categories WHERE name = 'Прочие расходы' AND type = 'Расход' LIMIT 1
ON CONFLICT (bank_category, bank_category_type) DO NOTHING;

-- Для теста: один пользователь с подпиской (user_id=1, для X-Test-User-Id)
-- Раскомментируйте, если в тестовой БД нет пользователей:
-- INSERT INTO users (id, tg_id, username, created_at, premium_until)
-- VALUES (1, 0, 'test', NOW(), NOW() + INTERVAL '1 year')
-- ON CONFLICT (id) DO UPDATE SET premium_until = NOW() + INTERVAL '1 year';
