-- Колонка bank_category_type: «Доход» или «Расход» для маппинга (для «Прочее» — две строки)
ALTER TABLE category_mapping ADD COLUMN IF NOT EXISTS bank_category_type VARCHAR(20);

-- Заполнить по типу целевой категории
UPDATE category_mapping m
SET bank_category_type = CASE WHEN c.type = 'income' THEN 'Доход' ELSE 'Расход' END
FROM categories c
WHERE c.id = m.category_id AND m.bank_category_type IS NULL;

UPDATE category_mapping SET bank_category_type = 'Расход' WHERE bank_category_type IS NULL;

ALTER TABLE category_mapping DROP CONSTRAINT IF EXISTS chk_bank_category_type;
ALTER TABLE category_mapping ADD CONSTRAINT chk_bank_category_type CHECK (bank_category_type IN ('Доход', 'Расход'));
ALTER TABLE category_mapping ALTER COLUMN bank_category_type SET NOT NULL;
ALTER TABLE category_mapping DROP CONSTRAINT IF EXISTS category_mapping_bank_category_key;
ALTER TABLE category_mapping DROP CONSTRAINT IF EXISTS category_mapping_bank_category_type_key;
ALTER TABLE category_mapping ADD CONSTRAINT category_mapping_bank_category_type_key UNIQUE (bank_category, bank_category_type);
CREATE INDEX IF NOT EXISTS idx_category_mapping_bank_type ON category_mapping(LOWER(TRIM(bank_category)), bank_category_type);
