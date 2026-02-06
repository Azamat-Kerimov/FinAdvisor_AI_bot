-- Расширенный набор категорий (расходы и доходы). Выполнить один раз после schema_finadvisor.sql.
-- INSERT только если такой пары (name, type) ещё нет.

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
