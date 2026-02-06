-- Миграция: для category_mapping, если есть колонка id без DEFAULT — задать DEFAULT nextval.
-- Нужна, если при импорте Excel ошибка: "значение NULL в столбце id отношения category_mapping".
-- Безопасно запускать повторно.

DO $$
DECLARE
  has_id_col boolean;
  seq_name text;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'category_mapping' AND column_name = 'id'
  ) INTO has_id_col;

  IF NOT has_id_col THEN
    RETURN; -- в схеме нет id, ничего не делаем
  END IF;

  seq_name := pg_get_serial_sequence('public.category_mapping', 'id');
  IF seq_name IS NULL THEN
    seq_name := 'public.category_mapping_id_seq';
    EXECUTE 'CREATE SEQUENCE IF NOT EXISTS category_mapping_id_seq';
  END IF;
  EXECUTE format('ALTER TABLE category_mapping ALTER COLUMN id SET DEFAULT nextval(%L)', seq_name);
  -- Чтобы не было конфликтов при следующих INSERT
  EXECUTE format('SELECT setval(%L, GREATEST((SELECT COALESCE(max(id), 0) FROM category_mapping) + 1, 1))', seq_name);
END $$;

-- Если в category_mapping есть колонка created_at без DEFAULT — задать DEFAULT NOW()
DO $$
DECLARE
  has_created_at boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'category_mapping' AND column_name = 'created_at'
  ) INTO has_created_at;

  IF has_created_at THEN
    ALTER TABLE category_mapping ALTER COLUMN created_at SET DEFAULT NOW();
  END IF;
END $$;
