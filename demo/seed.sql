-- ============================================================
-- InfraWhisperer Demo Database — E-Commerce Schema
-- ============================================================
-- This seed data creates a realistic e-commerce database with
-- scenarios that correlate with the K8s & Monitoring demo data
-- (payment-service outage → failed payments → stuck orders)
-- ============================================================

-- Customers
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    tier VARCHAR(20) DEFAULT 'standard'
);

-- Products
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    stock INTEGER DEFAULT 0,
    category VARCHAR(100)
);

-- Orders
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    total_amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    payment_id VARCHAR(50)
);

-- Order Items
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL
);

-- Payments
CREATE TABLE IF NOT EXISTS payments (
    id VARCHAR(50) PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    provider VARCHAR(50) DEFAULT 'stripe',
    created_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT
);

-- ============================================================
-- Seed Data
-- ============================================================

-- Customers
INSERT INTO customers (email, name, phone, tier) VALUES
('alice@example.com', 'Alice Johnson', '+1-555-0101', 'premium'),
('bob@example.com', 'Bob Smith', '+1-555-0102', 'standard'),
('carol@example.com', 'Carol Williams', '+1-555-0103', 'premium'),
('dave@example.com', 'Dave Brown', '+1-555-0104', 'standard'),
('eve@example.com', 'Eve Davis', '+1-555-0105', 'standard');

-- Products
INSERT INTO products (name, price, stock, category) VALUES
('Wireless Headphones', 79.99, 150, 'Electronics'),
('USB-C Cable Pack', 14.99, 500, 'Accessories'),
('Mechanical Keyboard', 129.99, 75, 'Electronics'),
('Laptop Stand', 45.50, 200, 'Accessories'),
('Monitor Light Bar', 39.99, 120, 'Electronics');

-- Successful historical orders
INSERT INTO orders (customer_id, total_amount, status, created_at, payment_id) VALUES
(1, 129.99, 'completed', NOW() - INTERVAL '2 days', 'pay_succ_001'),
(2, 45.50, 'completed', NOW() - INTERVAL '1 day', 'pay_succ_002'),
(3, 94.98, 'completed', NOW() - INTERVAL '12 hours', 'pay_succ_003');

-- Recent failed orders (correlate with payment-service outage)
INSERT INTO orders (customer_id, total_amount, status, created_at) VALUES
(4, 234.00, 'failed', NOW() - INTERVAL '30 minutes'),
(5, 89.99, 'failed', NOW() - INTERVAL '25 minutes'),
(1, 156.75, 'failed', NOW() - INTERVAL '20 minutes'),
(2, 67.25, 'failed', NOW() - INTERVAL '15 minutes'),
(3, 199.99, 'failed', NOW() - INTERVAL '10 minutes');

-- Pending orders (stuck because payment service is down)
INSERT INTO orders (customer_id, total_amount, status, created_at) VALUES
(4, 129.99, 'pending', NOW() - INTERVAL '5 minutes'),
(5, 45.50, 'pending', NOW() - INTERVAL '2 minutes');

-- Successful payments
INSERT INTO payments (id, order_id, amount, status, created_at) VALUES
('pay_succ_001', 1, 129.99, 'completed', NOW() - INTERVAL '2 days'),
('pay_succ_002', 2, 45.50, 'completed', NOW() - INTERVAL '1 day'),
('pay_succ_003', 3, 94.98, 'completed', NOW() - INTERVAL '12 hours');

-- Failed payments (payment gateway timeout)
INSERT INTO payments (id, order_id, amount, status, created_at, error_message) VALUES
('pay_err_001', 4, 234.00, 'failed', NOW() - INTERVAL '30 minutes', 'Payment gateway timeout — service unavailable'),
('pay_err_002', 5, 89.99, 'failed', NOW() - INTERVAL '25 minutes', 'Payment gateway timeout — service unavailable'),
('pay_err_003', 6, 156.75, 'failed', NOW() - INTERVAL '20 minutes', 'Payment gateway timeout — service unavailable'),
('pay_err_004', 7, 67.25, 'failed', NOW() - INTERVAL '15 minutes', 'Payment gateway timeout — service unavailable'),
('pay_err_005', 8, 199.99, 'failed', NOW() - INTERVAL '10 minutes', 'Payment gateway timeout — service unavailable');

-- Order Items
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 3, 1, 129.99),
(2, 4, 1, 45.50),
(3, 2, 2, 14.99),
(3, 5, 1, 39.99),
(4, 3, 1, 129.99),
(4, 4, 1, 45.50),
(4, 1, 1, 79.99);
