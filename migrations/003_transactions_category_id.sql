-- Замена текстовой категории на category_id в таблице transactions
-- Выполнять ПОСЛЕ 002_categories.sql и после заполнения category_mapping (seed).
-- Выполнить: psql -U user -d dbname -f migrations/003_transactions_category_id.sql

-- 1. Добавить колонку category_id (nullable)
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES categories(id);

-- 2. Заполнить category_id по совпадению имени категории (только если есть колонка category)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'transactions' AND column_name = 'category') THEN
    UPDATE transactions t
    SET category_id = c.id
    FROM categories c
    WHERE c.name = TRIM(NULLIF(t.category, ''))
      AND t.category_id IS NULL;
    UPDATE transactions t SET category_id = (SELECT id FROM categories WHERE name = 'Прочие доходы' LIMIT 1) WHERE t.category_id IS NULL AND t.amount >= 0;
    UPDATE transactions t SET category_id = (SELECT id FROM categories WHERE name = 'Прочие расходы' LIMIT 1) WHERE t.category_id IS NULL AND t.amount < 0;
    ALTER TABLE transactions ALTER COLUMN category_id SET NOT NULL;
    ALTER TABLE transactions DROP COLUMN category;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_transactions_category_id ON transactions(category_id);
