# RetailIQ: Comprehensive MLOps & Data Engineering Platform
## Final Project Presentation (Phase 1 & Phase 2 Combined)

---

### Slide 1: Title Slide
**Title:** RetailIQ: End-to-End E-Commerce Analytics & Customer Churn MLOps
**Subtitle:** From Raw Data Ingestion to Real-Time Predictive AI
**Presenter:** [Your Name]
**Date:** [Date]

---

### Slide 2: Project Vision & Objectives
**Title:** The Goal: Building a Production-Grade Data Product
* **Problem:** E-commerce platforms struggle to identify at-risk customers proactively and suffer from siloed, unvalidated data.
* **Objective:** Build an automated, scalable pipeline that transforms raw transactional data into actionable business intelligence and real-time AI predictions.
* **Phase 1 (Data Engineering):** Robust ETL, Data Warehouse, and Airflow orchestration.
* **Phase 2 (Machine Learning):** Feature Engineering, MLflow tracking, FastAPI deployment, and an interactive Streamlit UI.

---

### Slide 3: Architecture Overview
**Title:** System Architecture & Tech Stack
* **Orchestration:** Apache Airflow
* **Storage / Warehouse:** PostgreSQL (Star Schema)
* **Processing:** Python (Pandas/NumPy)
* **ML Experimentation:** MLflow & Scikit-Learn
* **Model Deployment:** FastAPI
* **Front-End Dashboard:** Streamlit
* **Infrastructure:** Docker & Docker Compose (Multi-container deployment)

---

### Slide 4: Phase 1 - Automated Ingestion & Quality Control
**Title:** Data Engineering: Building the Foundation
* **Data Source:** +500k e-commerce transactions across 13 monthly batches.
* **Quarantine Framework:** Enforced strict business rules (valid prices, positive quantities, duplicate detection).
* **Results:** Achieved a **99.53% Validation Pass Rate**.
* **Auditability:** 2,500+ records automatically quarantined with explicit error reason codes, ensuring zero pollution of the downstream data warehouse.

---

### Slide 5: Phase 1 - The Data Warehouse
**Title:** Star Schema & Analytical Data Marts
* **Dimensional Modeling:** Built a highly optimized Star Schema with core dimensions (`dim_customer`, `dim_product`, `dim_date`, `dim_geography`) and a central `fact_sales` table.
* **Data Marts for Business:**
  * **Sales Performance Mart:** Pre-aggregated revenue, AOV, and volume metrics by time and geography.
  * **RFM Segmentation Mart:** Recency, Frequency, and Monetary scores segmenting customers into Loyalty Tiers (Bronze, Silver, Gold, Platinum).

---

### Slide 6: Phase 2 - Machine Learning Feature Engineering
**Title:** Designing for Prediction: Zero Data Leakage
* **Objective:** Predict if an active customer will churn (stop buying).
* **Temporal Splitting:** 
  * **Observation Window (180 days):** Calculated 14 behavioral features (e.g., Recency, Cancellation Rate, Inter-purchase Latency).
  * **Target Window (90 days):** Assigned binary churn labels based on inactivity.
* **Result:** Extracted a highly predictive feature set for 2,786 unique customers.

---

### Slide 7: Phase 2 - Model Training & MLOps
**Title:** ML Experimentation with MLflow
* **Algorithm Benchmarking:** Trained Logistic Regression, Random Forest, and Gradient Boosting models.
* **MLflow Registry:** Automatically tracked hyper-parameters, metrics (Accuracy, F1, Log-Loss), and artifacts (Confusion Matrices).
* **The Winner:** **Gradient Boosting Classifier**
  * **Combined Score:** 0.6421
  * **ROC-AUC:** 0.6950
* **Deployment Ready:** Serialized as `production_churn_model.pkl` for immediate downstream consumption.

---

### Slide 8: Phase 2 - Production Deployment
**Title:** FastAPI & Docker Containerization
* **Microservices Architecture:** 
  * Deployed the winning Gradient Boosting model inside a high-throughput **FastAPI** REST microservice (`/predict`).
* **Docker Compose Network:**
  * Container 1: `ecommerce_postgres` (Data Warehouse)
  * Container 2: `ecommerce_fastapi_api` (AI Backend)
  * Container 3: `ecommerce_streamlit_app` (Front-End)
* **Result:** A fully isolated, reproducible production environment.

---

### Slide 9: The Final Product
**Title:** Interactive Streamlit Dashboard
* **8 Analytical Tabs:** Providing 360-degree business intelligence.
* **Highlights:**
  * Executive Revenue Trends & Global Heatmaps.
  * 3D RFM Behavioral Scatter Plots.
  * **Real-Time Churn Portal (Tab 7):** Submit customer features and instantly receive a Churn Probability % and an automated Retention Recommendation via the FastAPI backend.

---

### Slide 10: Conclusion & Next Steps
**Title:** Business Impact & Future Work
* **Business Impact:** Shifted from retrospective reporting to proactive AI-driven retention strategies.
* **Next Steps:**
  * Implement automated model retraining DAGs in Airflow.
  * Integrate A/B testing for retention playbooks.
  * Expand the dataset to include web-analytics (clickstream) data.

---

**Questions?**
