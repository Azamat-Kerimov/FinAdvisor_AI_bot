-- Миграция: transactions.category (TEXT) -> transactions.category_id (INTEGER)
-- Запускать, если в БД уже есть колонка category и нет category_id.
-- Безопасно запускать повторно: если category_id уже есть, шаги пропускаются.

DO $$
DECLARE
  has_category_id boolean;
  has_category boolean;
  default_cat_id int;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'transactions' AND column_name = 'category_id'
  ) INTO has_category_id;

  IF has_category_id THEN
    RETURN; -- уже мигрировано
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'transactions' AND column_name = 'category'
  ) INTO has_category;

  IF NOT has_category THEN
    RETURN; -- нет старой колонки, ничего не делаем
  END IF;

  -- Взять id первой категории как fallback для неизвестных имён
  SELECT id INTO default_cat_id FROM categories ORDER BY id LIMIT 1;
  IF default_cat_id IS NULL THEN
    INSERT INTO categories (name, type) VALUES ('Прочие расходы', 'Расход') RETURNING id INTO default_cat_id;
  END IF;

  ALTER TABLE transactions ADD COLUMN category_id INTEGER REFERENCES categories(id);
  UPDATE transactions t
  SET category_id = COALESCE(
    (SELECT c.id FROM categories c WHERE c.name = t.category LIMIT 1),
    default_cat_id
  );
  ALTER TABLE transactions ALTER COLUMN category_id SET NOT NULL;
  ALTER TABLE transactions DROP COLUMN category;
END $$;
