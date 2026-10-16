# 🛍️ RetailIQ: E-Commerce Sales Analytics & Customer Churn MLOps Platform
**Course:** Data Engineering and MLOps | **Full End-to-End Platform (Phase 1 & Phase 2)**

---

## 📌 Executive Overview

RetailIQ is an enterprise-grade data engineering, predictive machine learning, and MLOps analytics platform built on real-world transactional records from the **UCI Online Retail dataset** (541,909 raw records across 38 global markets).

### Phase 1: Data Engineering & Data Warehouse Infrastructure
1. **Automated Ingestion & Batch Partitioning**: Ingests multi-sheet extracts, partitions historical data into 13 monthly incremental batches, and enriches data with synthetic customer demographic master records.
2. **Data Quality & Quarantine Framework**: Enforces business validation rules (price sanity, quantity bounds, cancellation detection, duplicate prevention) and logs rejected records with explicit error reason codes (**99.53% validation pass rate**).
3. **Star Schema Data Warehouse**: Implements a dimensional schema (`dim_customer`, `dim_product`, `dim_geography`, `dim_date`, `fact_sales`, `fact_customer_retention`) supporting both PostgreSQL and SQLite.
4. **Analytical Data Marts**: Computes pre-aggregated data marts for Sales Performance and Customer RFM (Recency, Frequency, Monetary) Segmentation.
5. **Orchestration**: Production **Apache Airflow DAG** (`dags/retail_etl_dag.py`) and standalone CLI runner (`run_pipeline.py`).

### Phase 2: MLOps Extension & Customer Churn Prediction Engine
1. **Temporal Feature Engineering (Zero Data Leakage)**: Computes 14 behavioral and demographic customer features over a **180-day observation window** and evaluates binary churn labels over a subsequent **90-day inactivity target window**.
2. **Model Training & Experiment Tracking**: Benchmarks **Logistic Regression**, **Random Forest**, and **Gradient Boosting** classifiers tracked via **MLflow** (`sqlite:///mlruns.db`). Winning model (**Gradient Boosting**: ROC-AUC 0.6950, F1 0.5628) serialized and registered as `EcommerceChurnPredictor`.
3. **Production FastAPI Microservice**: Exposes high-throughput REST endpoints (`/health`, `/model_info`, `/predict`, `/batch_predict`) for real-time customer churn scoring and automated retention playbooks.
4. **Feature & Data Drift Monitoring**: Implements **Population Stability Index (PSI)** and **Two-Sample Kolmogorov-Smirnov (KS)** statistical tests to audit feature drift and alert on model degradation.
5. **Interactive Streamlit UI (8 Analytical Tabs)**: Includes real-time Churn Predictor Portal (Tab 7) and MLOps Registry & Feature Drift Monitor (Tab 8).
6. **Docker Multi-Container Deployment**: Fully containerized using **Docker Compose** (`postgres`, `fastapi_service`, `streamlit_dashboard`).

---

## 📦 Project Deliverables Package

| Deliverable | Description | Repository File Location |
| :---: | :--- | :--- |
| **ETL & Data Pipeline** | Ingestion, Quality Checks, Star Schema ETL | [`src/etl/`](file://src/etl/) & [`run_pipeline.py`](file://run_pipeline.py) |
| **Airflow Workflow** | Scheduled Airflow DAG Pipeline | [`dags/retail_etl_dag.py`](file://dags/retail_etl_dag.py) |
| **Data Warehouse** | PostgreSQL/SQLite Star Schema SQL | [`src/database/schema.sql`](file://src/database/schema.sql) |
| **ML Feature Pipeline** | Temporal Observation Feature Store | [`src/ml/feature_engineering.py`](file://src/ml/feature_engineering.py) |
| **ML Training & MLflow** | Model Benchmarking & MLflow Logger | [`src/ml/train.py`](file://src/ml/train.py) & [`src/ml/mlflow_tracker.py`](file://src/ml/mlflow_tracker.py) |
| **Drift Monitoring Engine** | PSI & KS-Test Drift Evaluator | [`src/ml/drift_monitor.py`](file://src/ml/drift_monitor.py) |
| **FastAPI Microservice** | Production REST Inference Endpoints | [`api/main.py`](file://api/main.py) & [`api/schemas.py`](file://api/schemas.py) |
| **Streamlit Dashboard** | 8 Interactive Analytics & MLOps Tabs | [`app/streamlit_app.py`](file://app/streamlit_app.py) |
| **Test Suite** | Unit & Integration Automated Tests (13/13 Pass) | [`tests/test_pipeline.py`](file://tests/test_pipeline.py) & [`tests/test_ml_pipeline.py`](file://tests/test_ml_pipeline.py) |
| **Phase 1 Report** | Part 1 Comprehensive Report | [`docs/PROJECT_PART1_REPORT.md`](file://docs/PROJECT_PART1_REPORT.md) |
| **Phase 2 Report** | Part 2 Comprehensive MLOps Report | [`docs/PROJECT_PART2_REPORT.md`](file://docs/PROJECT_PART2_REPORT.md) |

---

## 🚀 Quickstart Guide

### 1. Prerequisites & Environment Setup
```bash
# Clone repository & create virtual environment
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Execute Data Pipeline & Train ML Models
```bash
# Full pipeline execution: ETL -> Star Schema -> Marts -> ML Model Training & Artifact Logging
python run_pipeline.py --mode full
```

### 3. Launch FastAPI Microservice
```bash
# Starts FastAPI server on http://localhost:8000 (Swagger docs at http://localhost:8000/docs)
python -m uvicorn api.main:app --port 8000 --host 0.0.0.0
```

### 4. Launch Streamlit BI & MLOps Dashboard
```bash
# Starts Streamlit app on http://localhost:8501
streamlit run app/streamlit_app.py
```

### 5. Run Complete Automated Test Suite
```bash
# Executes 13 unit & integration tests across DE & MLOps pipelines
pytest tests/ -v
```

---

## 🤖 MLOps Model Benchmark & Performance Summary

Three algorithms were benchmarked on a stratified test set ($N=2,786$ customers):

| Algorithm | Accuracy | Precision | Recall | F1-Score | ROC-AUC | Log-Loss | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Logistic Regression** | 0.6388 | 0.6486 | 0.4571 | 0.5363 | 0.6727 | 0.6387 | Baseline |
| **Random Forest** | 0.6411 | 0.6515 | 0.4649 | 0.5425 | 0.6865 | 0.6321 | Benchmark |
| **Gradient Boosting** | **0.6531** | **0.6682** | **0.4862** | **0.5628** | **0.6950** | **0.6245** | **WINNER (Registered)** |

---

## 🔌 FastAPI Microservice Endpoints

| Endpoint | Method | Description | Example Request |
| :--- | :---: | :--- | :--- |
| `GET /health` | `GET` | Health check & model status | `curl http://localhost:8000/health` |
| `GET /model_info` | `GET` | Production model metadata | `curl http://localhost:8000/model_info` |
| `POST /predict` | `POST` | Single customer churn prediction | `{"recency_days": 120.0, "frequency_orders": 2, ...}` |
| `POST /batch_predict` | `POST` | Bulk customer predictions | `{"customers": [{...}, {...}]}` |

---

## 📊 Streamlit Interactive Dashboard Tabs

- **Tab 1: Executive KPI Overview**: Revenue, Order Velocity, Customer Growth, and Monthly Sales Trends.
- **Tab 2: Product & Category Intelligence**: Pareto Analysis (80/20 Rule) and Top Selling SKUs.
- **Tab 3: Customer RFM Segmentation**: 3D Scatter plots and RFM Persona distribution.
- **Tab 4: Geographic Sales Map**: Global revenue maps and market tier breakdown.
- **Tab 5: Cohort Retention Analysis**: Monthly retention matrices and customer heatmaps.
- **Tab 6: Data Quality & Audit Logs**: Real-time ETL audit logs and quarantine reason breakdown.
- **Tab 7: Real-Time Churn Predictor Portal**: Interactive single-customer form and batch CSV scoring.
- **Tab 8: MLOps Registry & Feature Drift Monitor**: MLflow run logs, ROC curves, and live PSI feature drift auditor.

---

## 🐳 Docker Multi-Container Orchestration

To run the entire system in isolated Docker containers:
```bash
docker-compose up -d --build
```
This launches:
- `ecommerce_postgres`: PostgreSQL DW on port `5432`
- `ecommerce_fastapi_api`: FastAPI microservice on port `8000`
- `ecommerce_streamlit_app`: Streamlit UI on port `8501`
