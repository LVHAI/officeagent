CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('standard', 'silver', 'gold', 'platinum')),
    total_spent NUMERIC(14, 2) NOT NULL DEFAULT 0,
    last_purchase_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customer_orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    order_amount NUMERIC(14, 2) NOT NULL CHECK (order_amount >= 0),
    order_status TEXT NOT NULL CHECK (order_status IN ('paid', 'cancelled', 'refunded')),
    ordered_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_customers_region ON customers(region);
CREATE INDEX IF NOT EXISTS idx_customers_total_spent ON customers(total_spent DESC);
CREATE INDEX IF NOT EXISTS idx_customer_orders_customer_time
    ON customer_orders(customer_id, ordered_at DESC);

INSERT INTO customers (
    customer_id, name, email, region, level, total_spent, last_purchase_at
) VALUES
    ('C001', '张伟', 'zhang.wei@example.com', 'East China', 'platinum', 128800.00, '2026-08-15T10:00:00Z'),
    ('C002', '李娜', 'li.na@example.com', 'East China', 'gold', 76200.00, '2026-07-28T14:30:00Z'),
    ('C003', '王强', 'wang.qiang@example.com', 'South China', 'silver', 35600.00, '2026-08-10T09:15:00Z'),
    ('C004', '陈静', 'chen.jing@example.com', 'North China', 'gold', 68400.00, '2026-06-18T16:20:00Z'),
    ('C005', '赵磊', 'zhao.lei@example.com', 'East China', 'standard', 9800.00, '2026-03-12T11:10:00Z'),
    ('C006', '刘洋', 'liu.yang@example.com', 'South China', 'platinum', 115500.00, '2026-08-19T08:40:00Z'),
    ('C007', '杨雪', 'yang.xue@example.com', 'West China', 'silver', 27400.00, '2026-05-21T13:05:00Z'),
    ('C008', '黄涛', 'huang.tao@example.com', 'East China', 'gold', 59300.00, '2026-07-05T17:45:00Z'),
    ('C009', '周敏', 'zhou.min@example.com', 'North China', 'standard', 12600.00, '2026-04-09T10:25:00Z'),
    ('C010', '吴刚', 'wu.gang@example.com', 'South China', 'gold', 81700.00, '2026-08-02T15:00:00Z')
ON CONFLICT (customer_id) DO UPDATE SET
    name = EXCLUDED.name,
    email = EXCLUDED.email,
    region = EXCLUDED.region,
    level = EXCLUDED.level,
    total_spent = EXCLUDED.total_spent,
    last_purchase_at = EXCLUDED.last_purchase_at;

INSERT INTO customer_orders (order_id, customer_id, order_amount, order_status, ordered_at) VALUES
    ('O1001', 'C001', 42800.00, 'paid', '2026-06-01T10:00:00Z'),
    ('O1002', 'C001', 36000.00, 'paid', '2026-07-12T12:00:00Z'),
    ('O1003', 'C001', 50000.00, 'paid', '2026-08-15T10:00:00Z'),
    ('O1004', 'C002', 32000.00, 'paid', '2026-05-20T09:30:00Z'),
    ('O1005', 'C002', 44200.00, 'paid', '2026-07-28T14:30:00Z'),
    ('O1006', 'C003', 18000.00, 'paid', '2026-06-15T11:20:00Z'),
    ('O1007', 'C003', 17600.00, 'paid', '2026-08-10T09:15:00Z'),
    ('O1008', 'C004', 68400.00, 'paid', '2026-06-18T16:20:00Z'),
    ('O1009', 'C005', 9800.00, 'paid', '2026-03-12T11:10:00Z'),
    ('O1010', 'C006', 51500.00, 'paid', '2026-06-20T08:40:00Z'),
    ('O1011', 'C006', 64000.00, 'paid', '2026-08-19T08:40:00Z'),
    ('O1012', 'C007', 27400.00, 'paid', '2026-05-21T13:05:00Z'),
    ('O1013', 'C008', 29300.00, 'paid', '2026-06-05T17:45:00Z'),
    ('O1014', 'C008', 30000.00, 'paid', '2026-07-05T17:45:00Z'),
    ('O1015', 'C009', 12600.00, 'paid', '2026-04-09T10:25:00Z'),
    ('O1016', 'C010', 39700.00, 'paid', '2026-06-02T15:00:00Z'),
    ('O1017', 'C010', 42000.00, 'paid', '2026-08-02T15:00:00Z')
ON CONFLICT (order_id) DO UPDATE SET
    customer_id = EXCLUDED.customer_id,
    order_amount = EXCLUDED.order_amount,
    order_status = EXCLUDED.order_status,
    ordered_at = EXCLUDED.ordered_at;
