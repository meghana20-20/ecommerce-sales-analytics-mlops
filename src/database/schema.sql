-- =============================================================================
-- E-COMMERCE RETAIL DATA WAREHOUSE SCHEMA (STAR SCHEMA & ANALYTICAL MARTS)
-- Compatible with PostgreSQL and SQLite / DuckDB
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. DIMENSIONAL TABLES
-- -----------------------------------------------------------------------------

-- Customer Dimension
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key INTEGER PRIMARY KEY,
    customer_id BIGINT UNIQUE,
    customer_code VARCHAR(64) NOT NULL,
    gender VARCHAR(16),
    age_group VARCHAR(32),
    loyalty_tier VARCHAR(32),
    signup_date DATE,
    preferred_device VARCHAR(32),
    country VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product Dimension
CREATE TABLE IF NOT EXISTS dim_product (
    product_key INTEGER PRIMARY KEY,
    stock_code VARCHAR(64) UNIQUE,
    description TEXT,
    category VARCHAR(64),
    unit_price_nominal NUMERIC(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Geography Dimension
CREATE TABLE IF NOT EXISTS dim_geography (
    geography_key INTEGER PRIMARY KEY,
    country_name VARCHAR(64) UNIQUE,
    region VARCHAR(64),
    market_tier VARCHAR(32)
);

-- Date Dimension
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY, -- YYYYMMDD
    full_date DATE UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    day INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

-- -----------------------------------------------------------------------------
-- 2. FACT TABLES
-- -----------------------------------------------------------------------------

-- Sales Fact Table
CREATE TABLE IF NOT EXISTS fact_sales (
    sales_key INTEGER PRIMARY KEY,
    invoice_no VARCHAR(32) NOT NULL,
    customer_key INTEGER NOT NULL,
    product_key INTEGER NOT NULL,
    geography_key INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    invoice_timestamp TIMESTAMP NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    is_cancelled BOOLEAN DEFAULT FALSE,
    batch_id VARCHAR(64),
    FOREIGN KEY (customer_key) REFERENCES dim_customer (customer_key),
    FOREIGN KEY (product_key) REFERENCES dim_product (product_key),
    FOREIGN KEY (geography_key) REFERENCES dim_geography (geography_key),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key)
);

-- Customer Retention Fact Table
CREATE TABLE IF NOT EXISTS fact_customer_retention (
    retention_key INTEGER PRIMARY KEY,
    customer_key INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    cohort_month VARCHAR(7) NOT NULL, -- YYYY-MM
    order_sequence INTEGER NOT NULL,
    days_since_prior_order INTEGER,
    order_value NUMERIC(12, 2) NOT NULL,
    is_repeat_customer BOOLEAN NOT NULL,
    FOREIGN KEY (customer_key) REFERENCES dim_customer (customer_key),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key)
);

-- -----------------------------------------------------------------------------
-- 3. ANALYTICAL DATA MARTS
-- -----------------------------------------------------------------------------

-- Sales Performance Mart
CREATE TABLE IF NOT EXISTS mart_sales_performance (
    mart_id INTEGER PRIMARY KEY,
    date_key INTEGER NOT NULL,
    year_month VARCHAR(7) NOT NULL,
    country_name VARCHAR(64) NOT NULL,
    total_revenue NUMERIC(14, 2) NOT NULL,
    total_orders INTEGER NOT NULL,
    total_units_sold INTEGER NOT NULL,
    average_order_value NUMERIC(10, 2) NOT NULL,
    unique_customers INTEGER NOT NULL,
    cancelled_orders_count INTEGER NOT NULL,
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key)
);

-- Customer RFM Mart
CREATE TABLE IF NOT EXISTS mart_customer_rfm (
    customer_key INTEGER PRIMARY KEY,
    customer_id BIGINT UNIQUE,
    recency_days INTEGER NOT NULL,
    frequency INTEGER NOT NULL,
    monetary_total NUMERIC(14, 2) NOT NULL,
    r_score INTEGER NOT NULL,
    f_score INTEGER NOT NULL,
    m_score INTEGER NOT NULL,
    rfm_score VARCHAR(8) NOT NULL,
    customer_segment VARCHAR(64) NOT NULL,
    loyalty_tier VARCHAR(32),
    last_order_date DATE,
    FOREIGN KEY (customer_key) REFERENCES dim_customer (customer_key)
);

-- -----------------------------------------------------------------------------
-- 4. ETL AUDIT & DATA QUALITY LOGS
-- -----------------------------------------------------------------------------

-- Ingestion & ETL Audit Trail
CREATE TABLE IF NOT EXISTS etl_audit_log (
    audit_id INTEGER PRIMARY KEY,
    batch_id VARCHAR(64) NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    extraction_timestamp TIMESTAMP NOT NULL,
    raw_row_count INTEGER NOT NULL,
    cleaned_row_count INTEGER NOT NULL,
    rejected_row_count INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL,
    execution_duration_sec NUMERIC(8, 2) NOT NULL,
    notes TEXT
);

-- Rejected Records Log
CREATE TABLE IF NOT EXISTS etl_rejection_log (
    rejection_id INTEGER PRIMARY KEY,
    batch_id VARCHAR(64) NOT NULL,
    invoice_no VARCHAR(32),
    stock_code VARCHAR(64),
    quantity NUMERIC(10, 2),
    unit_price NUMERIC(10, 2),
    customer_id VARCHAR(64),
    rejection_reason VARCHAR(128) NOT NULL,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 5. PERFORMANCE INDEXES
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_fact_sales_date ON fact_sales (date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer ON fact_sales (customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product ON fact_sales (product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_geo ON fact_sales (geography_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_invoice ON fact_sales (invoice_no);
CREATE INDEX IF NOT EXISTS idx_retention_cust_cohort ON fact_customer_retention (customer_key, cohort_month);
CREATE INDEX IF NOT EXISTS idx_rfm_segment ON mart_customer_rfm (customer_segment);
