-- Миграция: логирование действий пользователей
-- Применить: psql -U postgres -d FinAdvisor_Beta -f scripts/migrate_user_actions.sql

CREATE TABLE IF NOT EXISTS user_actions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_actions_user_created ON user_actions(user_id, created_at);
