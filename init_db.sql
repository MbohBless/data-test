-- Sample database initialization script
-- This creates example tables for testing the analytical engine

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    date TIMESTAMP NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL,
    region VARCHAR(100)
);

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    country VARCHAR(100)
);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock_quantity INTEGER NOT NULL
);

-- Insert sample data for testing
INSERT INTO customers (name, email, country) VALUES
    ('John Doe', 'john@example.com', 'USA'),
    ('Jane Smith', 'jane@example.com', 'Canada'),
    ('Bob Johnson', 'bob@example.com', 'UK'),
    ('Alice Williams', 'alice@example.com', 'Australia'),
    ('Charlie Brown', 'charlie@example.com', 'USA');

INSERT INTO products (name, category, price, stock_quantity) VALUES
    ('Laptop', 'Electronics', 999.99, 50),
    ('Mouse', 'Electronics', 29.99, 200),
    ('Desk Chair', 'Furniture', 199.99, 30),
    ('Monitor', 'Electronics', 349.99, 75),
    ('Keyboard', 'Electronics', 79.99, 150);

INSERT INTO orders (customer_id, amount, date, status, region) VALUES
    (1, 105000.00, '2024-05-15', 'completed', 'North America'),
    (2, 128000.00, '2024-06-20', 'completed', 'North America'),
    (3, 95000.00, '2024-05-28', 'pending', 'Europe'),
    (4, 142000.00, '2024-07-10', 'completed', 'Asia Pacific'),
    (1, 87000.00, '2024-06-05', 'completed', 'North America'),
    (5, 115000.00, '2024-07-22', 'completed', 'North America');

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(date);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
