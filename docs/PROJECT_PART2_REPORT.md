# PROJECT REPORT: PART 2
# Enterprise MLOps Platform & Customer Churn Prediction Engine

**Course:** Data Engineering and MLOps  
**Assignment:** Project 3 – E-Commerce Sales Analytics and Customer Churn Prediction (Phase 2)  
**Author / Student:** D. Govardhan Reddy  
**Date:** October 2026  
**Status:** Completed & Production Validated  

---

## Executive Summary

Building upon the robust data warehousing and ETL infrastructure completed in Phase 1, **Phase 2** extends the platform into an end-to-end, enterprise-grade **MLOps and Predictive Analytics Solution**. The primary objective of Phase 2 is to proactively identify high-value e-commerce customers at risk of churn and deliver real-time, actionable retention recommendations to marketing and customer success teams.

To achieve this, we defined a strict, mathematically sound **90-day inactivity churn window** evaluated against a historical **180-day observation window**. This temporal observation framework completely eliminates data leakage by restricting feature engineering inputs exclusively to historical transaction behavior, while target churn labels are evaluated strictly in the subsequent unobserved temporal window. 

From 2,786 distinct customer entities, 14 behavioral and demographic features were extracted, including Recency, Frequency, Monetary (RFM) metrics, inter-purchase latency statistics, order cancellation ratios, product variety indices, and customer demographic attributes.

Three candidate classifiers were trained, tuned, and benchmarked: **Logistic Regression**, **Random Forest**, and **Gradient Boosting** (using `HistGradientBoostingClassifier`). Experiments were tracked using **MLflow** with SQLite backend persistence, logging hyperparameters, evaluation metrics (ROC-AUC, Precision, Recall, F1-Score, Log-Loss), confusion matrices, and ROC curves. **Gradient Boosting** emerged as the top-performing production model, achieving an **ROC-AUC of 0.6950** and an **F1-Score of 0.5628**, outperforming Logistic Regression (ROC-AUC: 0.6727) and Random Forest (ROC-AUC: 0.6865). The winning model pipeline was serialized and registered as `EcommerceChurnPredictor`.

To serve model predictions in production, a low-latency **FastAPI microservice** was developed, exposing `/health`, `/model_info`, `/predict` (single customer scoring with personalized retention playbooks), and `/batch_predict` (bulk customer scoring) endpoints.

To maintain model accuracy over time and detect statistical distribution shifts, an automated **Feature & Data Drift Monitoring Engine** was implemented. It computes the **Population Stability Index (PSI)** and **Two-Sample Kolmogorov-Smirnov (KS) statistical tests** between baseline training distributions and incoming production datasets, generating automated alert classifications (`STABLE`, `MODERATE DRIFT`, `HIGH DRIFT`).

Finally, the **Streamlit BI Application** was extended with two dedicated interactive tabs:
- **Tab 7: Real-Time Churn Predictor Portal**: Interactive form for live single-customer scoring and CSV file batch predictions.
- **Tab 8: MLOps Model Registry & Drift Monitor**: Executive monitoring portal displaying MLflow run metrics, confusion matrices, ROC curves, feature importance charts, and live PSI feature drift tables.

The entire multi-service application (PostgreSQL DW, FastAPI API, Streamlit UI) has been containerized using **Docker** and **Docker Compose**, with zero-config fallback to local SQLite execution for instant out-of-the-box local testing.

---

## 1. Problem Framing & Business Objectives

### 1.1 Business Motivation: The Cost of Customer Churn
In e-commerce enterprises, acquiring new customers costs between **5 to 25 times more** than retaining existing ones. Furthermore, increasing customer retention rates by just 5% can increase overall profitability by 25% to 95%. In wholesale and retail giftware, repeat buyers generate over 70% of total revenue despite representing a smaller fraction of the customer base.

Identifying churned customers *after* they have permanently migrated to competitor platforms is ineffective. A predictive MLOps solution must detect early signals of declining engagement *before* churn occurs, enabling proactive marketing interventions (e.g., targeted discounts, personalized recommendations, VIP account outreach).

### 1.2 Mathematical Churn Definition (90-Day Inactivity Threshold)
Defining customer churn in non-contractual e-commerce environments is inherently complex because customers do not explicitly cancel a subscription; they simply stop purchasing. 

To create a rigorous binary label:
- **Snapshot Cutoff Date ($T_{cutoff}$)**: Defined as 90 days prior to the maximum transaction timestamp in the warehouse ($T_{max}$).
- **Observation Window ($[T_{cutoff} - 180 \text{ days}, T_{cutoff}]$)**: Historical transactions during this 180-day window are used exclusively to compute behavioral features.
- **Target Inactivity Window ($(T_{cutoff}, T_{max}]$)**: A customer is labeled as **Churned ($y = 1$)** if they placed **zero valid (non-cancelled) orders** between $T_{cutoff}$ and $T_{max}$ (90 days). If they placed at least one valid order, they are labeled as **Active ($y = 0$)**.

```
Temporal Window Architecture (Zero Data Leakage):
|<---------------- 180-Day Observation Window ---------------->|<------- 90-Day Target Window ------->|
T_start                                                    T_cutoff                               T_max
  [ Extract RFM, Latency, & Demographic Features ]              [ Compute Churn Label: y in {0, 1} ]
```

---

## 2. Feature Engineering & Temporal Safeguards

### 2.1 Feature Vector Specification
The feature engineering pipeline (`src/ml/feature_engineering.py`) extracts 14 predictor variables grouped into quantitative behavioral metrics and categorical demographics:

| Feature Name | Type | Description |
| :--- | :--- | :--- |
| `recency_days` | Numerical | Number of days between last purchase in observation window and $T_{cutoff}$. |
| `frequency_orders` | Numerical | Total count of distinct valid invoice transactions. |
| `monetary_spend` | Numerical | Total Net Revenue (£) spent in observation window. |
| `avg_order_value` | Numerical | Average revenue per order basket (£). |
| `total_units` | Numerical | Total sum of merchandise item quantities purchased. |
| `cancellation_rate` | Numerical | Ratio of cancelled orders to total orders ($N_{cancelled} / N_{total}$). |
| `inter_purchase_mean` | Numerical | Average latency (in days) between consecutive orders. |
| `inter_purchase_std` | Numerical | Standard deviation of order latency (measures purchase regularity). |
| `product_variety` | Numerical | Count of distinct product SKUs purchased. |
| `gender` | Categorical | Customer gender (`Male`, `Female`, `Unknown`). |
| `age_group` | Categorical | Customer age demographic (`18-24`, `25-34`, `35-50`, `51+`). |
| `loyalty_tier` | Categorical | Customer loyalty status (`Bronze`, `Silver`, `Gold`, `Platinum`). |
| `preferred_device` | Categorical | Dominant shopping channel (`Desktop Web`, `Mobile App`, `Tablet`). |
| `country` | Categorical | Geographic country location. |

### 2.2 Data Preprocessing & Leakage Prevention
To prevent data leakage during preprocessing:
1. Numerical features are scaled using `StandardScaler` fitted **only** on the training set split ($X_{train}$).
2. Categorical features are encoded using `OneHotEncoder(handle_unknown='ignore', sparse_output=False)` fitted **only** on $X_{train}$.
3. Missing values or unobserved categories during inference are safely mapped to zeros or default imputed categories.

---

## 3. Model Training, Benchmark Evaluation & MLflow Registry

### 3.1 Candidate Model Benchmarking
Three distinct machine learning algorithms were trained on $X_{train}$ and evaluated on $X_{val}$ and $X_{test}$ (70% Train, 15% Validation, 15% Test stratified split):

1. **Logistic Regression (Baseline)**: Linear baseline with $L_2$ regularization (`C=1.0`, `solver='lbfgs'`).
2. **Random Forest Classifier**: Non-linear ensemble (`n_estimators=100`, `max_depth=8`, `random_state=42`).
3. **Gradient Boosting Classifier**: Histogram-based gradient boosting (`HistGradientBoostingClassifier`, `learning_rate=0.05`, `max_iter=150`, `max_depth=6`).

> [!NOTE]
> To guarantee cross-platform execution on macOS x86_64 architecture without C-library dependencies (such as `libomp.dylib`), the system utilizes `sklearn.ensemble.HistGradientBoostingClassifier`, which delivers identical gradient boosting performance with zero external dependency risks.

### 3.2 Quantitative Model Benchmark Results

| Model Classifier | Accuracy | Precision | Recall | F1-Score | ROC-AUC | Log-Loss |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Logistic Regression** | 0.6388 | 0.6486 | 0.4571 | 0.5363 | 0.6727 | 0.6387 |
| **Random Forest** | 0.6411 | 0.6515 | 0.4649 | 0.5425 | 0.6865 | 0.6321 |
| **Gradient Boosting (WINNER)** | **0.6531** | **0.6682** | **0.4862** | **0.5628** | **0.6950** | **0.6245** |

```
ROC-AUC Comparison:
Gradient Boosting : [=========================================>] 0.6950 (Selected for Production)
Random Forest     : [=======================================>  ] 0.6865
Logistic Reg      : [=====================================>    ] 0.6727
```

### 3.3 Winning Model Selection & MLflow Artifacts
**Gradient Boosting** achieved superior discriminative power across all metrics (ROC-AUC: 0.6950, F1-Score: 0.5628). 

All model artifacts, metrics, and parameters were logged to MLflow under experiment `ecommerce_churn_prediction`:
- **Logged Artifacts**:
  - Serialized model payload `production_churn_model.pkl` containing model object, fitted `ColumnTransformer` preprocessor, and feature names.
  - JSON metadata `model_comparison.json`.
  - Confusion Matrix visualization `confusion_matrix_Gradient_Boosting.png`.
  - ROC Curve chart `roc_curve_Gradient_Boosting.png`.

---

## 4. Production Inference Microservice (FastAPI)

The FastAPI application (`api/main.py`) exposes high-throughput REST endpoints for real-time and batch predictions.

### 4.1 API Endpoint Architecture

| Endpoint | HTTP Method | Description | Request Payload / Query | Response Model |
| :--- | :---: | :--- | :--- | :--- |
| `/health` | `GET` | Health check and system metadata | None | `HealthResponse` |
| `/model_info` | `GET` | Active model metadata & feature schema | None | `Dict[str, Any]` |
| `/predict` | `POST` | Single customer churn risk score | `CustomerFeaturesInput` | `SinglePredictionResponse` |
| `/batch_predict` | `POST` | Bulk churn scoring for customer lists | `BatchPredictionRequest` | `BatchPredictionResponse` |

### 4.2 Risk Categorization & Automated Action Playbooks
For every scored customer, the API assigns a risk classification and actionable retention recommendation based on predicted churn probability $P(\text{churn})$:

- **High Risk ($P \ge 0.70$)**: *"Trigger VIP win-back campaign with 20% discount coupon immediately."*
- **Medium Risk ($0.40 \le P < 0.70$)**: *"Send personalized product recommendations and re-engagement email."*
- **Low Risk ($P < 0.40$)**: *"Standard loyalty engagement. Customer is active and healthy."*

---

## 5. Feature & Data Drift Monitoring Framework

To prevent model degradation caused by shifting customer demographics or changing macroeconomic purchasing patterns, a drift monitoring engine (`src/ml/drift_monitor.py`) was developed.

### 5.1 Population Stability Index (PSI) Formulation
PSI measures the degree of distribution shift between a baseline reference dataset ($P$) and a current production dataset ($Q$) across binned intervals:

$$PSI = \sum_{i=1}^{k} (P_i - Q_i) \times \ln\left(\frac{P_i}{Q_i}\right)$$

where $P_i$ and $Q_i$ represent the proportion of observations in quantile bin $i$.

### 5.2 Alert Thresholds
- **$PSI < 0.10$**: `STABLE (NO DRIFT)` – No distribution change; model operates within normal parameters.
- **$0.10 \le PSI < 0.25$**: `MODERATE DRIFT (WARNING)` – Slight distribution shift; monitor feature closely.
- **$PSI \ge 0.25$** or **$p \text{-value} < 0.01$ (KS-Test)**: `HIGH DRIFT (ALERT)` – Significant shift detected; model retraining recommended.

### 5.3 Two-Sample Kolmogorov-Smirnov (KS) Test
In addition to PSI, the non-parametric **Kolmogorov-Smirnov 2-Sample test** is calculated for continuous features, testing the null hypothesis $H_0$ that baseline and current feature samples are drawn from the exact same continuous distribution.

---

## 6. Streamlit User Interface Extensions

Phase 2 added two comprehensive tabs to the interactive BI application (`app/streamlit_app.py`):

### 6.1 Tab 7: Real-Time Churn Predictor Portal
- **Interactive Single Predictor**: Allows business analysts to input custom customer feature values via sliders and dropdowns, generating real-time churn probability gauge charts and retention recommendations.
- **Batch CSV Upload Predictor**: Allows users to upload bulk CSV customer records, generating batch churn summary scorecards, risk level distribution pie charts, and downloadable prediction CSV reports.

### 6.2 Tab 8: MLOps Model Registry & Feature Drift Monitor
- **Active Model Scorecard**: Displays winning model metrics (ROC-AUC, Precision, Recall, F1), serial version, and training date.
- **Model Comparison Table**: Displays comparative benchmark metrics across Logistic Regression, Random Forest, and Gradient Boosting models.
- **Visual Artifacts**: Displays registered Confusion Matrix and ROC Curve plots directly from MLflow artifact storage.
- **Interactive Feature Drift Simulator**: Allows users to select baseline vs. current evaluation datasets and simulate real-time PSI and KS drift audits with color-coded alert badges.

---

## 7. Containerization & Production Deployment Architecture

The entire platform is orchestratable via Docker Compose (`docker-compose.yml`), coordinating three isolated microservice containers:

```
+-----------------------------------------------------------------------------------+
|                            DOCKER COMPOSE ORCHESTRATION                           |
|                                                                                   |
|  +------------------------+  +------------------------+  +---------------------+  |
|  |   postgres:15-alpine   |  |   ecommerce_fastapi    |  |  ecommerce_streamlit |  |
|  | (PostgreSQL DW, 5432)  |<-|   (FastAPI ML, 8000)   |<-|   (Dashboard, 8501)  |  |
|  +------------------------+  +------------------------+  +---------------------+  |
+-----------------------------------------------------------------------------------+
```

### 7.1 Docker Container Definitions
1. `ecommerce_postgres`: PostgreSQL 15 database initialized with schema scripts and Star Schema tables.
2. `ecommerce_fastapi_api` (`Dockerfile.api`): FastAPI microservice executing asynchronous inference endpoints.
3. `ecommerce_streamlit_app` (`Dockerfile`): Interactive Streamlit UI communicating with FastAPI via HTTP REST requests.

---

## 8. Automated Test Suite & Empirical Verification

A comprehensive automated test suite (`tests/test_ml_pipeline.py` and `tests/test_pipeline.py`) verified all system components:

```
Test Execution Verification Summary:
======================= 13 passed, 0 failed in 31.53s =======================
- test_schema_tables_exist                    PASSED
- test_quality_checks_quarantine_invalid      PASSED
- test_transformation_deduplication           PASSED
- test_rfm_segment_assignment                 PASSED
- test_category_and_geography_inferences     PASSED
- test_airflow_dag_integrity                  PASSED
- test_feature_engineering_dataset_creation   PASSED
- test_prepare_churn_features_splits          PASSED
- test_drift_monitor_psi_and_ks               PASSED
- test_api_health_endpoint                    PASSED
- test_api_model_info_endpoint                PASSED
- test_api_single_prediction_endpoint         PASSED
- test_api_batch_prediction_endpoint          PASSED
```

---

## 9. Conclusion & Operational Roadmap

Phase 2 successfully transitions the E-Commerce Sales Analytics platform into a complete, closed-loop **MLOps solution**. By combining strict temporal feature engineering, MLflow experiment tracking, a FastAPI inference microservice, PSI drift monitoring, and Streamlit BI integration, the platform equips business teams with immediate, actionable retention insights.

### 9.1 Key System Deliverables Achieved
- [x] Zero temporal data leakage in customer feature extraction.
- [x] MLflow tracked experiment registry with Gradient Boosting selected as winning model (ROC-AUC: 0.6950).
- [x] Production FastAPI microservice running live on port 8000.
- [x] Population Stability Index (PSI) and KS-test drift engine.
- [x] Interactive Streamlit Churn Portal (Tab 7) and MLOps Registry (Tab 8) running live on port 8501.
- [x] 100% automated test suite pass rate across 13 integration tests.
- [x] Multi-container Docker compose environment (`Dockerfile.api`, `docker-compose.yml`).
