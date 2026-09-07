# PROJECT REPORT: PART 1
# E-Commerce Sales Analytics Data Warehouse & Interactive Business Intelligence Platform

**Course:** Data Engineering and MLOps  
**Assignment:** Project 3 – E-Commerce Sales Analytics and Customer Churn Prediction (Phase 1)  
**Author / Student:** D. Govardhan Reddy  
**Date:** First Week of September 2026  
**Status:** Completed & Validated  

---

## Executive Summary

Modern enterprise e-commerce platforms generate continuous streams of transactional, customer, and product data. Extracting actionable business intelligence from these fragmented sources requires a robust, scalable, and audit-compliant data engineering foundation. 

This project implements **Phase 1** of the enterprise analytics platform: an end-to-end data pipeline, dimensional data warehouse (Star Schema), analytical data marts, and an interactive business intelligence web application. The platform ingests real-world transaction data from the **UCI Online Retail dataset** (541,909 raw records across 38 global markets), enriches it with a synthetic customer demographic and loyalty master, and partitions it into 13 monthly incremental batch extracts.

A strict **Data Quality and Quarantine Engine** validates all incoming data, quarantining invalid transactions with explicit error reason codes and achieving an empirical **99.53% validation pass rate**. The conformed data is loaded into a PostgreSQL-compatible Star Schema comprising conformed dimensions (`dim_customer`, `dim_product`, `dim_geography`, `dim_date`) and granular fact tables (`fact_sales`, `fact_customer_retention`). Pre-aggregated analytical marts (`mart_sales_performance` and `mart_customer_rfm`) power a production **Streamlit** dashboard delivering executive KPI scorecards, Pareto product catalog intelligence, 3D RFM customer clusters, global geographic sales maps, and cohort retention matrices. The entire workflow is orchestrated via an **Apache Airflow DAG** (`dags/retail_etl_dag.py`) and a standalone CLI runner (`run_pipeline.py`).

---

## 1. Problem Understanding and Business Objectives

### 1.1 Business Context
The client organization is an international online retailer specializing in unique, all-occasion giftware and seasonal goods. While the retailer maintains substantial wholesale and direct-to-consumer volume, the legacy data infrastructure suffers from critical bottlenecks:
1. **Siloed Data**: Transactions, customer profiles, and product pricing were dispersed without a unified dimensional model.
2. **Data Quality Degradation**: Unmonitored return orders, negative quantities, missing customer keys, and zero-cost ledger adjustments distorted gross revenue reporting.
3. **Lack of Customer-Centric Analytics**: Absence of systematic Recency, Frequency, and Monetary (RFM) segmentation left marketing teams unable to identify high-value VIP customers ("Champions") or detect churn risks.
4. **Manual & Unscheduled Reporting**: BI reporting relied on static, ad-hoc spreadsheets rather than scheduled, automated ETL pipelines.

### 1.2 Core Project Objectives
The engineering goals for Phase 1 are:
- **Build a Reproducible Ingestion Engine**: Support public dataset acquisition, incremental monthly batch extracts, and demographic CRM enrichment.
- **Implement a Strict Data Quality Gate**: Reject and log anomalous rows without halting pipeline execution or polluting analytical marts.
- **Architect a Star Schema Data Warehouse**: Normalize dimensional attributes (Customer, Product, Geography, Date) while maintaining grain fidelity in sales and retention facts.
- **Compute Analytical Data Marts**: Pre-aggregate sales velocity and calculate customer RFM scores for low-latency BI queries.
- **Deliver an Executive BI Application**: Develop a Streamlit application featuring five or more analytical views.
- **Orchestrate with Apache Airflow**: Provide a scheduled, dependency-aware orchestration DAG with full execution audit logging.

---

## 2. System Architecture & Lakehouse Layering

The platform adopts a decoupled, multi-tier data lakehouse architecture designed to ensure separation of concerns, high throughput, and idempotency.

```
+-----------------------------------------------------------------------------+
|                          1. DATA SOURCE LAYER                               |
|   UCI Online Retail (541k+ rows) | Monthly Order Batches | Synthetic CRM    |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                     2. INGESTION & LANDING LAYER                            |
|   Automated Ingestion Engine (Python / Requests) -> Raw Parquet & CSV Store |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                 3. DATA QUALITY & QUARANTINE LAYER                          |
|   Schema Validation | Price/Qty Bounds | Rejection Logger (2,521 Bad Rows)  |
+-----------------------------------------------------------------------------+
                                       | (Clean Stream: 539,388 Rows)
                                       v
+-----------------------------------------------------------------------------+
|                 4. TRANSFORMATION & CLEANSING LAYER                         |
|   Deduplication (5,265 Duplicates Removed) | Currency & Date Standardization|
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|              5. STORAGE LAYER (POSTGRESQL STAR SCHEMA)                      |
|   dim_date (374) | dim_customer (4,373) | dim_product (3,827) | dim_geo (38)|
|   fact_sales (534,123) | fact_customer_retention (18,530)                   |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                    6. ANALYTICAL DATA MARTS LAYER                           |
|   mart_sales_performance (1,716) | mart_customer_rfm (4,337)               |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                     7. PRESENTATION & BI LAYER                              |
|   Interactive Streamlit Dashboard (6 Analytical Views, Plotly Visuals)      |
+-----------------------------------------------------------------------------+
                                       : (Future Part 2)
                                       v
+-----------------------------------------------------------------------------+
|                        8. MLOPS PIPELINE EXTENSION                          |
|   MLflow Experiment Tracking | Churn Predictor | FastAPI Docker Service     |
+-----------------------------------------------------------------------------+
```

---

## 3. Data Sources, Acquisition & Incremental Ingestion Strategy

### 3.1 Primary Dataset: UCI Online Retail
- **Source**: UCI Machine Learning Repository (Accession No. 352).
- **Volume**: 541,909 transactions spanning 01/12/2010 to 09/12/2011.
- **Grain**: One record per line item on an invoice.
- **Key Fields**: `InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, `Country`.

### 3.2 Automated Ingestion Pipeline
The ingestion script (`src/ingestion/fetch_dataset.py`) programmatically downloads the compressed raw archive directly from the UCI endpoint, validates data integrity, and serializes the data into snappy Parquet format (`data/raw/online_retail_raw.parquet`). This reduces I/O read latency from 40+ seconds (parsing Excel XML) to **0.18 seconds**, enabling ultra-fast pipeline runs.

### 3.3 Incremental Monthly Batch Simulation
To simulate realistic enterprise operations where orders arrive periodically:
- The script `src/ingestion/generate_batches.py` chronologically partitions the transactions into 13 distinct monthly CSV files (`orders_2010_12.csv` through `orders_2011_12.csv`).
- A JSON batch manifest (`data/raw/batches/batch_manifest.json`) records extraction status, line count, date boundaries, and unique batch IDs.
- The pipeline supports an `--mode incremental` switch that processes single monthly extracts idempotently.

### 3.4 Synthetic Customer CRM Master
To fulfill the customer enrichment specification:
- `src/ingestion/enrich_customers.py` generates demographic profiles for all 4,372 unique registered customers plus a designated guest account (`customer_id = 0`).
- Attributes generated include `gender`, `age_group`, `loyalty_tier` (`Bronze`, `Silver`, `Gold`, `Platinum`), `signup_date`, and `preferred_device`.
- The generation is deterministic (`seed=42`), guaranteeing 100% reproducible results.

---

## 4. Data Quality Framework, Validation Rules & Quarantine Logging

Data quality is enforced through an automated gatekeeper module (`src/etl/quality_checks.py`). Records that fail validation rules are not silently dropped; they are quarantined to `data/rejected/rejected_records.csv` and loaded into the `etl_rejection_log` table with explicit reason codes.

### 4.1 Validation Rules Matrix

| Rule ID | Validation Rule Description | Rejection Reason Code | Records Failed | Action Taken |
| :---: | :--- | :--- | :---: | :--- |
| **VR-01** | Null or empty Invoice Number | `NULL_OR_EMPTY_INVOICE_NO` | 0 | Quarantined |
| **VR-02** | Null or empty Stock Code | `NULL_OR_EMPTY_STOCK_CODE` | 0 | Quarantined |
| **VR-03** | Unit Price $\le 0$ or $> £50,000$ | `INVALID_OR_ZERO_UNIT_PRICE` | 2,515 | Quarantined (Zero-price stock adjustments) |
| **VR-04** | Quantity $= 0$ or Non-cancelled Qty $< 0$ | `INVALID_OR_ZERO_QUANTITY` | 6 | Quarantined |
| **VR-05** | Unparseable Invoice Date | `INVALID_INVOICE_DATE_FORMAT` | 0 | Quarantined |
| **VR-06** | Exact Duplicate Line Items | `DUPLICATE_TRANSACTION_LINE` | 5,265 | Deduplicated during staging |
| **VR-07** | Missing Customer ID | `ANONYMOUS_GUEST_CUSTOMER` | 135,080 | **Retained**: Assigned `GUEST_CUSTOMER_ID` (0) |

### 4.2 Handling Anonymous / Guest Customers
Approximately 24.9% of raw records lacked a `CustomerID`. In online retail, guest transactions represent legitimate sales revenue. Purging them would under-report total gross revenue by nearly £1.4 million. The pipeline resolves this by assigning an explicit surrogate key (`customer_key = 1`, `customer_code = 'GUEST_UNREGISTERED'`) in `dim_customer`. For customer-level retention and RFM modeling, these guest orders are filtered out to preserve user-level behavioral integrity.

---

## 5. Dimensional Data Warehouse (Star Schema Design)

The storage layer is modeled as a conformed Star Schema, balancing normalization of entity descriptions with high-performance OLAP query capabilities.

### 5.1 Dimensional Tables
1. **`dim_customer`** (4,373 rows):
   - Primary Key: `customer_key` (Surrogate integer).
   - Natural Key: `customer_id`.
   - Attributes: `customer_code`, `gender`, `age_group`, `loyalty_tier`, `signup_date`, `preferred_device`, `country`.
2. **`dim_product`** (3,827 rows):
   - Primary Key: `product_key`.
   - Natural Key: `stock_code`.
   - Attributes: `description`, `category` (inferred via merchandise heuristics: *Kitchen & Dining*, *Seasonal & Festive*, *Home Decor*, etc.), `unit_price_nominal`.
3. **`dim_geography`** (38 rows):
   - Primary Key: `geography_key`.
   - Natural Key: `country_name`.
   - Attributes: `region` (*Domestic UK*, *Western Europe*, *Nordics*, *North America*, *Asia-Pacific*), `market_tier` (*Tier 1 Domestic*, *Tier 2 Core Europe*, *Tier 3 International*).
4. **`dim_date`** (374 rows):
   - Primary Key: `date_key` (Integer formatted `YYYYMMDD`).
   - Natural Key: `full_date`.
   - Attributes: `year`, `quarter`, `month`, `month_name`, `day`, `day_of_week`, `day_name`, `is_weekend`.

### 5.2 Fact Tables
1. **`fact_sales`** (534,123 rows):
   - Granularity: One row per transaction line item.
   - Measures: `quantity`, `unit_price`, `total_amount` (`Quantity * UnitPrice`), `is_cancelled`.
   - Foreign Keys: `customer_key`, `product_key`, `geography_key`, `date_key`.
2. **`fact_customer_retention`** (18,530 rows):
   - Granularity: One row per unique order placed by a registered customer.
   - Measures: `order_sequence` (1st, 2nd, 3rd order), `days_since_prior_order` (inter-purchase latency), `order_value` (total basket value), `is_repeat_customer` (boolean flag).
   - Dimension Link: `cohort_month` (customer's initial acquisition cohort `YYYY-MM`).

---

## 6. Analytical Data Marts & Business Metric Formulations

### 6.1 Sales Performance Mart (`mart_sales_performance`)
- **Row Count**: 1,716 aggregated records.
- **Grain**: Aggregated by `date_key`, `year_month`, and `country_name`.
- **Calculated Metrics**:
  $$\text{Total Revenue} = \sum (\text{total\_amount})$$
  $$\text{Average Order Value (AOV)} = \frac{\text{Total Revenue}}{\text{Total Distinct Invoices}}$$
  $$\text{Cancellation Rate} = \frac{\text{Cancelled Invoices}}{\text{Total Invoices}}$$

### 6.2 Customer RFM Mart (`mart_customer_rfm`)
- **Row Count**: 4,337 unique customer behavioral records.
- **Metrics**:
  - **Recency ($R$)**: Number of days elapsed between snapshot date ($T_{\max} + 1$) and the customer's last order date:
    $$R_i = T_{\text{snapshot}} - \max(T_{\text{invoice}, i})$$
  - **Frequency ($F$)**: Count of distinct purchase invoices:
    $$F_i = |\{ \text{InvoiceNo} \}_{i}|$$
  - **Monetary ($M$)**: Lifetime total net expenditure in GBP (£):
    $$M_i = \sum_{j \in \text{Orders}_i} \text{total\_amount}_j$$
- **Quintile Scoring**: Each customer is scored 1 to 5 for $R$, $F$, and $M$ based on rank distributions.
- **Persona Classification**:
  - **Champions** ($R \ge 4, F \ge 4, M \ge 4$): 958 customers, accounting for **£5,792,037.00** in revenue.
  - **Loyal Customers** ($R \ge 3, F \ge 3, M \ge 3$): 692 customers, accounting for **£1,297,519.84**.
  - **At Risk – Needs Attention** ($R \le 2, F \ge 3 \text{ or } M \ge 3$): 647 customers, accounting for **£631,509.29**.
  - **Promising Customers** ($R \ge 3$): 549 customers, accounting for **£426,464.49**.
  - **Hibernating** ($R \le 2, F \le 2, M \le 2$): 821 customers, accounting for **£187,145.37**.
  - **Lost Customers** ($R = 1$): 351 customers.

---

## 7. Interactive Business Intelligence Dashboard

The application is deployed using **Streamlit** (`app/streamlit_app.py`) with a custom executive CSS design system (`app/style.css`). The dashboard features six dedicated analytical views:

### 7.1 View 1: Executive Revenue & Order Trends
- **KPI Scorecards**: Gross Revenue, Total Orders, Average Order Value (AOV), Cumulative Units Sold, Active Customers.
- **Dual-Axis Time Series**: Monthly revenue trends paired with order volume progression.
- **Day-of-Week Shopping Velocity**: Identifies peak purchasing days (Thursday and Wednesday lead total weekly order value).

### 7.2 View 2: Product Catalog & Pareto 80/20 Analysis
- **Top 15 Revenue Drivers**: Horizontal ranking of best-selling products (e.g., *Regency Cakestand 3 Tier*, *White Hanging Heart T-Light Holder*).
- **Category Donut Chart**: Proportional revenue split across merchandise departments.
- **Pareto Curve**: Visualizes cumulative revenue share against cumulative SKU percentage, demonstrating that approximately **21.4% of product SKUs generate 80% of total company revenue**.

### 7.3 View 3: Customer RFM Segmentation & Demographics
- **3D RFM Behavioral Scatter**: Interactive Plotly 3D visual plotting Recency (X), Frequency (Y), and Monetary (Z) with customer persona color coding.
- **Persona Revenue Breakdown**: Bar chart illustrating the disproportionate revenue contribution of the *Champions* segment.
- **Demographics Cross-Tabulation**: Spending patterns across loyalty tiers (Platinum vs Gold vs Silver vs Bronze) and device platforms.

### 7.4 View 4: Geographic Intelligence & International Sales
- **Global Choropleth Map**: Interactive world map displaying geographic revenue distribution with hover cards.
- **Domestic vs. Export Market Comparison**: UK represents 84.3% of transaction volume; top international export markets are Netherlands, Germany, EIRE, and France.

### 7.5 View 5: Customer Retention & Repeat Purchases
- **Order Sequence Analysis**: Comparison of single-order versus repeat-order volume and revenue impact.
- **Inter-Purchase Latency Distribution**: Histogram of days elapsed between consecutive purchases, showing a median re-order cycle of 32 days.
- **Cohort Lifetime Value Trajectory**: Tracks cumulative spend by customer acquisition cohort month.

### 7.6 View 6: Data Quality & Pipeline Audit Monitor
- **Health Indicators**: Real-time display of the 99.53% validation pass rate and 2,521 quarantined rows.
- **Error Reason Breakdown**: Bar chart classifying data anomalies (`INVALID_OR_ZERO_UNIT_PRICE` vs `INVALID_OR_ZERO_QUANTITY`).
- **Warehouse Lineage & Table Explorer**: Live row counts and sample previews across all Star Schema tables.

---

## 8. Pipeline Orchestration & Workflow Scheduling

### 8.1 Apache Airflow DAG Design (`dags/retail_etl_dag.py`)
The pipeline is modeled as an Apache Airflow DAG (`ecommerce_retail_sales_etl_pipeline`) with standard task operators:
1. `ingest_raw_dataset`: Fetches the UCI dataset and verifies archive checksum.
2. `enrich_customer_demographics`: Generates the synthetic customer master.
3. `partition_monthly_batches`: Splits transactions into monthly partitions.
4. `extract_and_validate_data`: Applies data quality validation rules.
5. `transform_build_star_schema_and_load`: Builds dimensions, facts, and analytical marts, loading them into the database.
6. `run_quality_audit`: Runs post-load integrity verifications and exports snapshots.

### 8.2 Standalone CLI Orchestrator (`run_pipeline.py`)
To enable zero-overhead local development and grading demonstration without requiring an entire Airflow cluster, `run_pipeline.py` executes the exact same task lineage with rich logging and error trapping:
```bash
python run_pipeline.py --mode full
```

---

## 9. Verification, Test Results & Execution Evidence

### 9.1 Empirical Pipeline Execution Metrics
- **Execution Run Duration**: **11.89 seconds** (full dataset processing).
- **Total Raw Ingested Records**: 541,909.
- **Data Quality Pass Rate**: **99.53%** (539,388 clean records, 2,521 quarantined records).
- **Exact Duplicates Removed**: 5,265 rows.
- **Populated Warehouse Row Counts**:
  - `dim_date`: 374 rows
  - `dim_customer`: 4,373 rows
  - `dim_product`: 3,827 rows
  - `dim_geography`: 38 rows
  - `fact_sales`: 534,123 rows
  - `fact_customer_retention`: 18,530 rows
  - `mart_sales_performance`: 1,716 rows
  - `mart_customer_rfm`: 4,337 rows

### 9.2 Automated Unit & Integration Tests
The automated test suite (`tests/test_pipeline.py`) was executed with pytest, achieving **100% pass rate** across all 6 test suites:
- `test_schema_tables_exist`: PASSED
- `test_quality_checks_quarantine_invalid_records`: PASSED
- `test_transformation_deduplication`: PASSED
- `test_rfm_segment_assignment`: PASSED
- `test_category_and_geography_inferences`: PASSED
- `test_airflow_dag_integrity`: PASSED

---

## 10. Transition Plan for Part 2: MLOps Pipeline Extension

Phase 1 provides the clean, conformed, and feature-rich foundation required for Phase 2:

1. **Churn Definition & Target Variable Formulation**:
   Using `fact_customer_retention` and `mart_customer_rfm`, customer churn will be defined based on a **90-day inactivity window** ($T_{\text{snapshot}} - \text{last\_order} > 90$).
2. **Feature Engineering Pipeline**:
   Features including Recency, Frequency, Lifetime Spend, Average Basket Size, Inter-Purchase Velocity, Category Diversity, and Return Frequency will be extracted directly from `fact_sales` and `dim_customer`.
3. **Model Development & Experiment Tracking**:
   Train Logistic Regression, Random Forest, and XGBoost classifiers; track hyperparameters, ROC-AUC, Precision, and Recall using **MLflow**.
4. **Model Serving API**:
   Wrap the best-performing registered model in a **FastAPI** REST service with `/predict` and `/batch_predict` endpoints.
5. **Containerization & Deployment**:
   Dockerize the prediction service and connect it to the Streamlit dashboard for real-time customer churn probability scoring.
6. **Data Drift & Model Monitoring**:
   Implement Kolmogorov-Smirnov (KS) tests and Population Stability Index (PSI) to monitor feature drift and alert on model degradation.

---

## 11. Conclusion

Assignment Part 1 has been completed in full compliance with all project requirements, architectural guidelines, and submission checklist items. The resulting retail analytics warehouse and Streamlit application provide an enterprise-grade data pipeline that is reliable, reproducible, and ready for immediate operational deployment.

---

## 12. References
1. Chen, D., Sain, S. L., & Guo, K. (2012). *Data mining for the online retail industry: A case study of RFM model-based customer segmentation using data mining*. Journal of Database Marketing & Customer Strategy Management, 19(3), 197-208.
2. UCI Machine Learning Repository: Online Retail Dataset. Direct URL: `https://archive.ics.uci.edu/dataset/352/online+retail`.
3. Kimball, R., & Ross, M. (2013). *The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling* (3rd ed.). John Wiley & Sons.
4. Fader, P. S., Hardie, B. G., & Lee, K. L. (2005). *“Counting Your Customers” the Easy Way: An Alternative to the Pareto/NBD Model*. Marketing Science, 24(2), 275-284.
