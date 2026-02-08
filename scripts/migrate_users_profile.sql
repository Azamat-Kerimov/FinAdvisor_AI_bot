-- Миграция: профиль пользователя (пол, дата рождения, семейное положение, дети, город)
-- Применить: psql -U postgres -d FinAdvisor_Beta -f scripts/migrate_users_profile.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS birth_date DATE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS marital_status TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS children_count INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS city TEXT;

-- Чек-листы из консультации (действия с галочкой)
CREATE TABLE IF NOT EXISTS user_consultation_actions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_text TEXT NOT NULL,
    done BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_consultation_actions_user ON user_consultation_actions(user_id);

-- Цель на этот месяц (фокус от ИИ)
CREATE TABLE IF NOT EXISTS user_focus_goal (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    target_amount NUMERIC NOT NULL,
    for_month INTEGER NOT NULL,
    for_year INTEGER NOT NULL,
    achieved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, for_month, for_year)
);
CREATE INDEX IF NOT EXISTS idx_focus_goal_user ON user_focus_goal(user_id);
