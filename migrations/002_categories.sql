-- Справочник категорий и маппинг банковских категорий (Сбер, Т-Банк) -> категория приложения
-- Выполнить: psql -U user -d dbname -f migrations/002_categories.sql

-- Таблица категорий приложения (расходы и доходы)
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('income', 'expense')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_categories_type ON categories(type);

-- Маппинг: категория из выгрузки банка (IN) -> id категории приложения
CREATE TABLE IF NOT EXISTS category_mapping (
    id SERIAL PRIMARY KEY,
    bank_category VARCHAR(512) NOT NULL UNIQUE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_category_mapping_bank ON category_mapping(LOWER(TRIM(bank_category)));
CREATE INDEX IF NOT EXISTS idx_category_mapping_category_id ON category_mapping(category_id);

-- Вставка категорий приложения (для авто-маппинга новых используем имена «Прочие доходы» / «Прочие расходы»)
INSERT INTO categories (name, type) VALUES
('Переводы людям', 'expense'),
('Кредиты и ипотека', 'expense'),
('Снятие наличных', 'expense'),
('Рестораны и кафе', 'expense'),
('Супермаркеты', 'expense'),
('Коммунальные платежи, связь, интернет', 'expense'),
('Здоровье и красота', 'expense'),
('Транспорт', 'expense'),
('Прочие расходы', 'expense'),
('Отдых и развлечения', 'expense'),
('Образование', 'expense'),
('Аренда жилья', 'expense'),
('Пополнения', 'income'),
('Дивиденды и купоны', 'income'),
('Прочие доходы', 'income'),
('Заработная плата', 'income'),
('Переводы от людей', 'income')
ON CONFLICT (name) DO NOTHING;
