# Data Dictionary and Validation Rules

This document provides a comprehensive data dictionary for the E-Commerce Retail Data Warehouse, Star Schema, Analytical Marts, and Validation Rules engine.

---

## 1. Dimensional Tables

### 1.1 `dim_customer` (Customer Dimension)
Slowly Changing Dimension (SCD Type 1) capturing registered customer master attributes and synthetic demographic enrichment.

| Column Name | Data Type | Constraints | Nullable | Description | Sample Values |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `customer_key` | `INTEGER` | `PRIMARY KEY` | No | Surrogate key generated for warehouse dimensional modeling. | `1`, `42`, `108` |
| `customer_id` | `BIGINT` | `UNIQUE` | Yes | Business identifier from source system. ID `0` designates anonymous/guest transactions. | `17850`, `13047`, `0` |
| `customer_code` | `VARCHAR(64)` | None | No | Prefixed business code. `GUEST_UNREGISTERED` for guests. | `CUST_17850`, `GUEST_UNREGISTERED` |
| `gender` | `VARCHAR(16)` | None | Yes | Synthetic customer gender demographic (`Female`, `Male`, `Non-Binary`, `Unknown`). | `Female`, `Male` |
| `age_group` | `VARCHAR(32)` | None | Yes | Synthetic customer age demographic (`18-25`, `26-35`, `36-50`, `51-65`, `65+`, `Unknown`). | `26-35`, `36-50` |
| `loyalty_tier` | `VARCHAR(32)` | None | Yes | Customer loyalty classification (`Bronze`, `Silver`, `Gold`, `Platinum`, `None`). | `Gold`, `Silver` |
| `signup_date` | `DATE` | None | Yes | Registration date prior to first recorded invoice. | `2010-03-15` |
| `preferred_device`| `VARCHAR(32)` | None | Yes | Customer browsing device preference (`Mobile App`, `Desktop Web`, `Mobile Web`, `Tablet`).| `Mobile App`, `Desktop Web`|
| `country` | `VARCHAR(64)` | None | Yes | Primary country of customer residence. | `United Kingdom`, `Germany` |

---

### 1.2 `dim_product` (Product Dimension)
Product catalog containing item descriptions, inferred merchandise categories, and nominal unit prices.

| Column Name | Data Type | Constraints | Nullable | Description | Sample Values |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `product_key` | `INTEGER` | `PRIMARY KEY` | No | Surrogate key uniquely identifying each product SKU. | `1`, `105`, `2560` |
| `stock_code` | `VARCHAR(64)` | `UNIQUE` | No | SKU stock code assigned by the retailer. | `85123A`, `71053`, `22423` |
| `description` | `TEXT` | None | Yes | Standardized uppercase product description. | `WHITE HANGING HEART T-LIGHT HOLDER` |
| `category` | `VARCHAR(64)` | None | No | Rule-inferred merchandise department. | `Seasonal & Festive`, `Kitchen & Dining` |
| `unit_price_nominal`| `NUMERIC(10,2)`| None | No | Median benchmark unit price in GBP (£). | `2.55`, `3.75`, `12.50` |

---

### 1.3 `dim_geography` (Geography Dimension)
Geographic dimension mapping transaction destination countries to global sales territories.

| Column Name | Data Type | Constraints | Nullable | Description | Sample Values |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `geography_key` | `INTEGER` | `PRIMARY KEY` | No | Surrogate key for geographical locations. | `1`, `2`, `15` |
| `country_name` | `VARCHAR(64)` | `UNIQUE` | No | Proper-cased country name. | `United Kingdom`, `Germany`, `France` |
| `region` | `VARCHAR(64)` | None | No | Broader geographic macro-region. | `Domestic UK`, `Western Europe`, `Nordics` |
| `market_tier` | `VARCHAR(32)` | None | No | Market priority classification tier. | `Tier 1 - Domestic`, `Tier 2 - Core Europe` |

---

### 1.4 `dim_date` (Date Dimension)
Conformed calendar dimension representing full date hierarchies for time-series analysis.

| Column Name | Data Type | Constraints | Nullable | Description | Sample Values |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `date_key` | `INTEGER` | `PRIMARY KEY` | No | Smart integer key formatted as `YYYYMMDD`. | `20101201`, `20110315` |
| `full_date` | `DATE` | `UNIQUE` | No | Calendar date. | `2010-12-01` |
| `year` | `INTEGER` | None | No | Calendar year. | `2010`, `2011` |
| `quarter` | `INTEGER` | None | No | Calendar quarter (1 to 4). | `1`, `2`, `3`, `4` |
| `month` | `INTEGER` | None | No | Calendar month (1 to 12). | `1` to `12` |
| `month_name` | `VARCHAR(20)` | None | No | Full English month name. | `December`, `January` |
| `day` | `INTEGER` | None | No | Day of the month (1 to 31). | `1`, `15`, `31` |
| `day_of_week` | `INTEGER` | None | No | ISO day of the week (1 = Monday, 7 = Sunday). | `1` to `7` |
| `day_name` | `VARCHAR(20)` | None | No | Full day name. | `Wednesday`, `Saturday` |
| `is_weekend` | `BOOLEAN` | None | No | Boolean flag indicating weekend days (Saturday/Sunday). | `TRUE`, `FALSE` |

---

## 2. Fact Tables

### 2.1 `fact_sales` (Sales Fact Table)
Granular transaction line-item fact table recording individual product sales.

| Column Name | Data Type | Constraints | Nullable | Description | Sample Values |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `sales_key` | `INTEGER` | `PRIMARY KEY` | No | Surrogate key for each transaction line item. | `1`, `54000` |
| `invoice_no` | `VARCHAR(32)` | None | No | Source invoice number. | `536365`, `C536379` |
| `customer_key` | `INTEGER` | `FOREIGN KEY` | No | References `dim_customer.customer_key`. | `1`, `42` |
| `product_key` | `INTEGER` | `FOREIGN KEY` | No | References `dim_product.product_key`. | `1`, `105` |
| `geography_key` | `INTEGER` | `FOREIGN KEY` | No | References `dim_geography.geography_key`. | `1`, `2` |
| `date_key` | `INTEGER` | `FOREIGN KEY` | No | References `dim_date.date_key`. | `20101201` |
| `invoice_timestamp`| `TIMESTAMP` | None | No | Exact transaction timestamp. | `2010-12-01 08:26:00` |
| `quantity` | `INTEGER` | None | No | Item quantity sold (negative for return transactions). | `6`, `24`, `-1` |
| `unit_price` | `NUMERIC(10,2)`| None | No | Unit sale price in GBP (£). | `2.55`, `4.99` |
| `total_amount` | `NUMERIC(12,2)`| None | No | Total revenue for line item (`Quantity * UnitPrice`). | `15.30`, `-2.55` |
| `is_cancelled` | `BOOLEAN` | None | No | Flag indicating if transaction represents a return/cancellation.| `FALSE`, `TRUE` |
| `batch_id` | `VARCHAR(64)` | None | Yes | Ingestion batch identifier. | `batch_2010_12` |

---

### 2.2 `fact_customer_retention` (Customer Retention Fact Table)
Order-level fact table capturing cohort lifecycle progression, order frequency, and inter-purchase latency.

| Column Name | Data Type | Constraints | Nullable | Description | Sample Values |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `retention_key` | `INTEGER` | `PRIMARY KEY` | No | Surrogate key for each customer order event. | `1`, `1240` |
| `customer_key` | `INTEGER` | `FOREIGN KEY` | No | References `dim_customer.customer_key`. | `42`, `108` |
| `date_key` | `INTEGER` | `FOREIGN KEY` | No | References `dim_date.date_key`. | `20110315` |
| `cohort_month` | `VARCHAR(7)` | None | No | Year-month of customer's very first recorded purchase (`YYYY-MM`). | `2010-12`, `2011-01` |
| `order_sequence` | `INTEGER` | None | No | Lifetime order number for the customer (1st order, 2nd order, etc.). | `1`, `2`, `7` |
| `days_since_prior_order` | `INTEGER` | None | Yes | Number of elapsed calendar days since customer's previous order. | `0`, `24`, `68` |
| `order_value` | `NUMERIC(12,2)`| None | No | Total net basket value for the order. | `350.25`, `89.90` |
| `is_repeat_customer` | `BOOLEAN` | None | No | Boolean flag indicating whether `order_sequence > 1`. | `FALSE`, `TRUE` |

---

## 3. Analytical Data Marts

### 3.1 `mart_sales_performance` (Sales Performance Mart)
Aggregated analytical table designed for executive dashboards, monthly/daily revenue tracking, and order trends.

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `mart_id` | `INTEGER (PK)` | Surrogate key for aggregated rows. |
| `date_key` | `INTEGER (FK)` | Links to `dim_date.date_key`. |
| `year_month` | `VARCHAR(7)` | Standardized `YYYY-MM` month string for time-series grouping. |
| `country_name` | `VARCHAR(64)` | Market country name. |
| `total_revenue` | `NUMERIC(14,2)` | Net total sales revenue (£). |
| `total_orders` | `INTEGER` | Count of distinct invoices. |
| `total_units_sold`| `INTEGER` | Cumulative units sold. |
| `average_order_value` | `NUMERIC(10,2)`| Average revenue per order (AOV). |
| `unique_customers` | `INTEGER` | Count of unique active buyers. |
| `cancelled_orders_count` | `INTEGER` | Number of cancelled/returned orders. |

---

### 3.2 `mart_customer_rfm` (Customer RFM Mart)
Customer-level analytical mart computing Recency, Frequency, and Monetary scores and behavioral segments.

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `customer_key` | `INTEGER (PK, FK)`| References `dim_customer.customer_key`. |
| `customer_id` | `BIGINT` | Unique source customer ID. |
| `recency_days` | `INTEGER` | Elapsed days between reference snapshot date and customer's latest purchase. |
| `frequency` | `INTEGER` | Lifetime count of distinct purchase orders. |
| `monetary_total` | `NUMERIC(14,2)` | Lifetime total net spend (£). |
| `r_score` | `INTEGER` | Recency quintile score (1 = Inactive/Dormant, 5 = Highly Recent). |
| `f_score` | `INTEGER` | Frequency quintile score (1 = Single Buyer, 5 = Frequent Buyer). |
| `m_score` | `INTEGER` | Monetary quintile score (1 = Low Spender, 5 = High Spender / VIP). |
| `rfm_score` | `VARCHAR(8)` | Concatenated 3-digit score (e.g., `555`, `454`, `111`). |
| `customer_segment` | `VARCHAR(64)` | Business segment (`Champions`, `Loyal Customers`, `At Risk`, `Hibernating`, `Lost`). |
| `loyalty_tier` | `VARCHAR(32)` | Demographics loyalty tier from CRM master (`Bronze`, `Silver`, `Gold`, `Platinum`). |
| `last_order_date` | `DATE` | Calendar date of most recent transaction. |

---

## 4. Validation Rules & Rejection Log Catalog

The data quality engine intercepts raw records before ingestion into staging and routes invalid rows to `etl_rejection_log` and `data/rejected/rejected_records.csv`.

| Validation Rule ID | Rejection Reason Code | Condition Triggered | Remediation Policy |
| :--- | :--- | :--- | :--- |
| **VR-01** | `NULL_OR_EMPTY_INVOICE_NO` | `InvoiceNo IS NULL OR TRIM(InvoiceNo) = ''` | Quarantine to rejection log. Record rejected. |
| **VR-02** | `NULL_OR_EMPTY_STOCK_CODE` | `StockCode IS NULL OR TRIM(StockCode) = ''` | Quarantine to rejection log. Record rejected. |
| **VR-03** | `INVALID_OR_ZERO_UNIT_PRICE` | `UnitPrice IS NULL OR UnitPrice <= 0 OR UnitPrice > 50000` | Quarantine to rejection log. Zero-cost items & administrative ledger adjustments rejected. |
| **VR-04** | `INVALID_OR_ZERO_QUANTITY` | `Quantity == 0` OR `(Quantity < 0 AND NOT InvoiceNo LIKE 'C%')` OR `Quantity > 50000` | Zero-quantity items and non-cancelled negative quantity items quarantined. |
| **VR-05** | `INVALID_INVOICE_DATE_FORMAT`| `InvoiceDate` unparseable as valid timestamp. | Quarantine to rejection log. |
| **VR-06** | `DUPLICATE_TRANSACTION_LINE` | Exact duplicate on `(InvoiceNo, StockCode, Quantity, UnitPrice, InvoiceDate)` | Deduplicated in staging. Only first occurrence preserved. |
| **VR-07** | `ANONYMOUS_GUEST_CUSTOMER` | `CustomerID IS NULL` | **Allowed with Default**: Assigned `GUEST_CUSTOMER_ID` (`0`) to preserve macro sales revenue while keeping customer metrics clean. |
