BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    price INTEGER NOT NULL CHECK (price > 0),
    stock INTEGER NOT NULL CHECK (stock >= 0)
) STRICT;

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
) STRICT;

CREATE TABLE IF NOT EXISTS sale_items (
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price INTEGER NOT NULL CHECK (unit_price > 0),
    PRIMARY KEY (sale_id, product_id)
) STRICT, WITHOUT ROWID;

CREATE TRIGGER IF NOT EXISTS check_sale_stock
BEFORE INSERT ON sale_items
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (SELECT 1 FROM products WHERE id = NEW.product_id)
            THEN RAISE(ABORT, 'PRODUCT_NOT_FOUND')
        WHEN (SELECT stock FROM products WHERE id = NEW.product_id) < NEW.quantity
            THEN RAISE(ABORT, 'INSUFFICIENT_STOCK')
    END;
END;

CREATE TRIGGER IF NOT EXISTS reduce_stock
AFTER INSERT ON sale_items
BEGIN
    UPDATE products SET stock = stock - NEW.quantity WHERE id = NEW.product_id;
END;

CREATE VIEW IF NOT EXISTS sale_totals AS
SELECT sales.id, sales.created_at, SUM(sale_items.quantity) AS quantity,
       SUM(sale_items.quantity * sale_items.unit_price) AS total
FROM sales JOIN sale_items ON sales.id = sale_items.sale_id
GROUP BY sales.id;

INSERT INTO products (id, name, price, stock) VALUES
    (1, 'Стул «Лофт»', 3500, 10),
    (2, 'Стол «Орион»', 12500, 5),
    (3, 'Диван «Уют»', 44900, 3),
    (4, 'Шкаф «Сканди»', 23900, 4),
    (5, 'Стул «Лира»', 5900, 8),
    (6, 'Стул «Облако»', 7900, 6),
    (7, 'Стул «Ретро»', 6900, 7),
    (8, 'Стул «Милан»', 8500, 5),
    (9, 'Стол «Круг»', 24900, 4),
    (10, 'Стол «Бьянко»', 34900, 3),
    (11, 'Стол «Норд»', 28900, 4),
    (12, 'Стол «Риф»', 19900, 6),
    (13, 'Диван «Нимбус»', 59900, 3),
    (14, 'Диван «Янтарь»', 49900, 4),
    (15, 'Диван «Модуль»', 74900, 2),
    (16, 'Диван «Вельвет»', 54900, 3),
    (17, 'Шкаф «Лён»', 26900, 5),
    (18, 'Шкаф «Орех»', 38900, 3),
    (19, 'Шкаф «Зеркало»', 32900, 4),
    (20, 'Шкаф «Шалфей»', 35900, 3),
    (21, 'Кровать «Дюна»', 29900, 5),
    (22, 'Кровать «Роза»', 38900, 3),
    (23, 'Кровать «Тайга»', 42900, 4),
    (24, 'Кровать «Луна»', 44900, 3),
    (25, 'Кровать «Линия»', 24900, 6)
ON CONFLICT(id) DO NOTHING;

COMMIT;
