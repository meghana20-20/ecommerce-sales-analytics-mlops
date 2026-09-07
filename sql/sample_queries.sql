-- =============================================================================
-- SAMPLE ANALYTICAL QUERIES FOR E-COMMERCE DATA WAREHOUSE & MARTS
-- Demonstrates Star Schema joins, aggregations, and business metrics
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Executive Monthly Revenue, Order Volume, and Average Order Value (AOV)
-- -----------------------------------------------------------------------------
SELECT 
    d.year,
    d.month_name,
    COUNT(DISTINCT f.invoice_no) AS total_orders,
    SUM(f.quantity) AS total_units_sold,
    ROUND(SUM(f.total_amount), 2) AS gross_revenue_gbp,
    ROUND(AVG(f.total_amount), 2) AS average_line_item_value,
    ROUND(SUM(f.total_amount) / NULLIF(COUNT(DISTINCT f.invoice_no), 0), 2) AS average_order_value_gbp
FROM fact_sales f
JOIN dim_date d ON f.date_key = d.date_key
WHERE f.is_cancelled = FALSE
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- -----------------------------------------------------------------------------
-- 2. Top 10 Revenue Generating Products with Product Category
-- -----------------------------------------------------------------------------
SELECT 
    p.stock_code,
    p.description,
    p.category,
    SUM(f.quantity) AS units_sold,
    ROUND(SUM(f.total_amount), 2) AS total_revenue_gbp,
    ROUND(AVG(f.unit_price), 2) AS avg_unit_price
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
WHERE f.is_cancelled = FALSE
GROUP BY p.product_key, p.stock_code, p.description, p.category
ORDER BY total_revenue_gbp DESC
LIMIT 10;

-- -----------------------------------------------------------------------------
-- 3. Customer RFM Segmentation Distribution and Value Contribution
-- -----------------------------------------------------------------------------
SELECT 
    customer_segment,
    COUNT(customer_key) AS customer_count,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(frequency), 1) AS avg_frequency_orders,
    ROUND(AVG(monetary_total), 2) AS avg_monetary_spend_gbp,
    ROUND(SUM(monetary_total), 2) AS segment_total_spend_gbp,
    ROUND(100.0 * SUM(monetary_total) / (SELECT SUM(monetary_total) FROM mart_customer_rfm), 2) AS revenue_share_pct
FROM mart_customer_rfm
GROUP BY customer_segment
ORDER BY segment_total_spend_gbp DESC;

-- -----------------------------------------------------------------------------
-- 4. Geographic Market Performance (International vs Domestic UK)
-- -----------------------------------------------------------------------------
SELECT 
    g.region,
    g.market_tier,
    g.country_name,
    COUNT(DISTINCT f.invoice_no) AS total_orders,
    ROUND(SUM(f.total_amount), 2) AS market_revenue_gbp,
    ROUND(100.0 * SUM(f.total_amount) / (SELECT SUM(total_amount) FROM fact_sales WHERE is_cancelled = FALSE), 2) AS revenue_contribution_pct
FROM fact_sales f
JOIN dim_geography g ON f.geography_key = g.geography_key
WHERE f.is_cancelled = FALSE
GROUP BY g.geography_key, g.region, g.market_tier, g.country_name
ORDER BY market_revenue_gbp DESC
LIMIT 15;

-- -----------------------------------------------------------------------------
-- 5. Customer Cohort Retention & Repeat Purchase Analysis
-- -----------------------------------------------------------------------------
SELECT 
    cohort_month,
    COUNT(DISTINCT customer_key) AS total_cohort_customers,
    SUM(CASE WHEN is_repeat_customer = TRUE THEN 1 ELSE 0 END) AS repeat_orders_placed,
    ROUND(AVG(days_since_prior_order), 1) AS avg_days_between_orders,
    ROUND(SUM(order_value), 2) AS cohort_lifetime_value_gbp
FROM fact_customer_retention
GROUP BY cohort_month
ORDER BY cohort_month;

-- -----------------------------------------------------------------------------
-- 6. Ingestion Audit & Data Quality Rejection Summary
-- -----------------------------------------------------------------------------
SELECT 
    batch_id,
    rejection_reason,
    COUNT(*) AS rejected_record_count
FROM etl_rejection_log
GROUP BY batch_id, rejection_reason
ORDER BY rejected_record_count DESC;
