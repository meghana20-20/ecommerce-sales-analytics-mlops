# 🛍️ RetailIQ: E-Commerce Sales Analytics & Customer Churn Platform
**Course:** Data Engineering and MLOps | **Phase 1: Data Pipeline Implementation**

---

## 📌 Executive Overview

RetailIQ is an end-to-end enterprise data engineering and business intelligence platform built on transactional retail records from the **UCI Online Retail dataset** (541,909 transactions across 38 global markets).

Phase 1 establishes the foundational data infrastructure:
1. **Automated Data Ingestion & Batch Partitioning**: Ingests raw multi-sheet extracts, partitions historical data into 13 monthly incremental batches, and generates synthetic customer demographic master records.
2. **Data Quality & Quarantine Framework**: Enforces business validation rules (price sanity, quantity bounds, cancellation detection, duplicate prevention) and logs rejected records with explicit error reason codes.
3. **Star Schema Data Warehouse**: Implements a dimensional schema (`dim_customer`, `dim_product`, `dim_geography`, `dim_date`, `fact_sales`, `fact_customer_retention`) compatible with PostgreSQL and SQLite.
4. **Analytical Data Marts**: Calculates pre-aggregated marts for multi-dimensional Sales Performance and Customer RFM (Recency, Frequency, Monetary) Segmentation.
5. **Orchestration**: Features a production **Apache Airflow DAG** (`dags/retail_etl_dag.py`) and a standalone CLI orchestrator (`run_pipeline.py`).
6. **Interactive Business Intelligence Web App**: A **Streamlit** dashboard delivering 6 executive views (Sales Trends, Pareto Catalog Analysis, RFM 3D Clusters, Global Geography, Cohort Retention, and Data Quality Monitoring).

---

## 📦 Part 1 Submission Deliverables Package

| Item | Deliverable Description | Repository File Location |
| :---: | :--- | :--- |
| **1** | Source Code and ETL Scripts | [`src/`](file://src/) & [`run_pipeline.py`](file://run_pipeline.py) |
| **2** | Airflow DAG & Orchestration Workflow | [`dags/retail_etl_dag.py`](file://dags/retail_etl_dag.py) |
| **3** | Database Schema & Sample Populated Tables | [`src/database/schema.sql`](file://src/database/schema.sql), [`sql/sample_queries.sql`](file://sql/sample_queries.sql), and [`data/exports/`](file://data/exports/) |
| **4** | Dataset Source Information & Access Instructions | [`docs/dataset_source_info.md`](file://docs/dataset_source_info.md) |
| **5** | Architecture Diagram & Pipeline Flow | [`docs/architecture_diagram.md`](file://docs/architecture_diagram.md) |
| **6** | Data Dictionary & Validation Rules | [`docs/data_dictionary.md`](file://docs/data_dictionary.md) |
| **7** | Streamlit Interactive Application | [`app/streamlit_app.py`](file://app/streamlit_app.py) & [`app/style.css`](file://app/style.css) |
| **8** | Comprehensive Project Report (8–10 Pages) | [`docs/PROJECT_PART1_REPORT.md`](file://docs/PROJECT_PART1_REPORT.md) |
| **9** | Execution Evidence & Audit Logs | [`data/logs/pipeline_execution.log`](file://data/logs/pipeline_execution.log) & [`data/logs/ingestion_audit_log.json`](file://data/logs/ingestion_audit_log.json) |
| **10** | README with Setup & Run Instructions | [`README.md`](file://README.md) (this document) |

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10+ (or Python 3.11)
- Virtual environment with dependencies:
  ```bash
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

### 2. Execute the Complete Pipeline End-to-End
Run the standalone pipeline orchestrator to fetch the dataset, run quality checks, build the star schema, compute analytical marts, and export table snapshots:
```bash
python run_pipeline.py --mode full
```

To run in **incremental batch mode** (processing monthly order batches):
```bash
python run_pipeline.py --mode incremental
```

### 3. Launch the Interactive Streamlit Dashboard
Launch the dashboard on `http://localhost:8501`:
```bash
streamlit run app/streamlit_app.py
```

### 4. Run Automated Test Suite
Execute the pytest suite covering schema integrity, quality validation, deduplication, and RFM scoring:
```bash
pytest tests/test_pipeline.py -v
```

---

## 🏛️ Data Warehouse Architecture

### Star Schema Entity Relationship
```
               +--------------------+
               |      dim_date      |
               +--------------------+
                         | (date_key)
                         v
+--------------------+ +--------------------+ +--------------------+
|    dim_customer    | |     fact_sales     | |    dim_product     |
+--------------------+ +--------------------+ +--------------------+
| customer_key (PK)  | | sales_key (PK)     | | product_key (PK)   |
| customer_id (UK)   |-| customer_key (FK)  | | stock_code (UK)    |
| gender             | | product_key (FK)   |-| description        |
| age_group          | | geography_key (FK) | | category           |
| loyalty_tier       | | date_key (FK)      | | unit_price_nominal |
+--------------------+ | invoice_no         | +--------------------+
         |             | quantity           |
         |             | unit_price         |
         |             | total_amount       |
         |             | is_cancelled       |
         |             +--------------------+
         |                       ^
         |                       | (geography_key)
         |             +--------------------+
         |             |   dim_geography    |
         |             +--------------------+
         |             | geography_key (PK) |
         |             | country_name (UK)  |
         |             | region             |
         |             | market_tier        |
         |             +--------------------+
         v
+-----------------------------+
|   fact_customer_retention   |
+-----------------------------+
| retention_key (PK)          |
| customer_key (FK)           |
| cohort_month                |
| order_sequence              |
| days_since_prior_order      |
| order_value                 |
| is_repeat_customer          |
+-----------------------------+
```

### Analytical Data Marts
- **`mart_sales_performance`**: Pre-aggregated revenue, distinct order count, total units sold, AOV, and unique customer reach by month and country.
- **`mart_customer_rfm`**: Quintile scoring (1-5) for Recency, Frequency, and Monetary attributes with customer persona classification (`Champions`, `Loyal Customers`, `At Risk`, `Hibernating`, `Lost`).

---

## 🛡️ Data Quality Framework & Validation Summary

Execution metrics from the baseline pipeline run:
- **Total Raw Ingested Records**: 541,909
- **Cleaned Valid Records**: 539,388 (**99.53% Pass Rate**)
- **Quarantined Records**: 2,521 rows quarantined to `data/rejected/rejected_records.csv`
  - Zero / Invalid Unit Price (`INVALID_OR_ZERO_UNIT_PRICE`): 2,515 rows (administrative adjustments)
  - Zero Quantity (`INVALID_OR_ZERO_QUANTITY`): 6 rows
- **Exact Duplicates Cleaned**: 5,265 duplicate transaction rows eliminated.

---

## 🐳 Docker Deployment (Optional)

To spin up a dedicated PostgreSQL database container along with the Streamlit service:
```bash
docker-compose up -d
```
The database will automatically initialize using `src/database/schema.sql`.
