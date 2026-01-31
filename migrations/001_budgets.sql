-- Бюджеты по категориям (ценность «не перерасходовать»)
-- Выполнить: psql -U user -d dbname -f migrations/001_budgets.sql

CREATE TABLE IF NOT EXISTS budgets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category VARCHAR(128) NOT NULL,
    monthly_limit NUMERIC(14,2) NOT NULL CHECK (monthly_limit >= 0),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, category)
);

CREATE INDEX IF NOT EXISTS idx_budgets_user_id ON budgets(user_id);
