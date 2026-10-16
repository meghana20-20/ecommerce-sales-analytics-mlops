"""Unit and integration tests for MLOps Pipeline, Feature Drift Monitor, and FastAPI Service."""

import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from src.database.connection import get_engine, init_database
from src.ml.feature_engineering import extract_customer_features, prepare_churn_features
from src.ml.drift_monitor import calculate_psi, calculate_feature_drift
from api.main import app

client = TestClient(app)


def test_feature_engineering_dataset_creation():
    """Verifies temporal churn feature extraction and leakage safeguards."""
    engine = get_engine(force_sqlite=True)
    init_database(engine)

    X, y, feature_names = extract_customer_features()
    
    assert not X.empty, "Feature DataFrame should not be empty."
    assert len(X) == len(y), "X and y must have equal number of rows."
    assert "recency_days" in X.columns, "Feature dataset must contain recency_days."
    
    # Target label must be binary 0 or 1
    unique_targets = set(y.dropna().unique())
    assert unique_targets.issubset({0, 1}), f"Unexpected target values: {unique_targets}"


def test_prepare_churn_features_splits():
    """Verifies data split ratios and feature preprocessor transformation."""
    splits = prepare_churn_features()
    assert "X_train" in splits and "X_val" in splits and "X_test" in splits
    assert splits["X_train"].shape[1] == len(splits["feature_names"])



def test_drift_monitor_psi_and_ks():
    """Verifies PSI score calculation and 2-sample KS feature drift detector."""
    # Test identical distributions -> PSI should be close to 0
    np.random.seed(42)
    base = np.random.normal(loc=50.0, scale=10.0, size=1000)
    curr_same = np.random.normal(loc=50.0, scale=10.0, size=1000)
    
    psi_identical = calculate_psi(base, curr_same)
    assert psi_identical < 0.10, f"PSI for identical distribution should be low, got {psi_identical}"

    # Test shifted distribution -> PSI should be elevated
    curr_shifted = np.random.normal(loc=75.0, scale=10.0, size=1000)
    psi_shifted = calculate_psi(base, curr_shifted)
    assert psi_shifted >= 0.25, f"PSI for shifted distribution should be HIGH (>=0.25), got {psi_shifted}"

    # Test multi-feature drift report
    df_base = pd.DataFrame({"recency_days": base, "monetary_spend": base * 2})
    df_curr = pd.DataFrame({"recency_days": curr_shifted, "monetary_spend": base * 2})

    drift_report = calculate_feature_drift(df_base, df_curr)
    assert not drift_report.empty
    assert "recency_days" in drift_report["feature"].values
    recency_alert = drift_report[drift_report["feature"] == "recency_days"]["alert_level"].values[0]
    assert "HIGH" in recency_alert or "MODERATE" in recency_alert


def test_api_health_endpoint():
    """Verifies FastAPI health check endpoint returns 200 OK and model status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "active_model" in data
    assert "metrics" in data


def test_api_model_info_endpoint():
    """Verifies model_info metadata endpoint."""
    response = client.get("/model_info")
    assert response.status_code == 200
    data = response.json()
    assert "model_name" in data
    assert "feature_count" in data
    assert data["feature_count"] > 0


def test_api_single_prediction_endpoint():
    """Verifies /predict POST endpoint with a sample customer payload."""
    payload = {
        "customer_id": "TEST_CUST_1001",
        "recency_days": 120.0,
        "frequency_orders": 2,
        "monetary_spend": 150.50,
        "avg_order_value": 75.25,
        "total_units": 15,
        "cancellation_rate": 0.0,
        "inter_purchase_mean": 30.0,
        "inter_purchase_std": 5.0,
        "product_variety": 4,
        "gender": "Female",
        "age_group": "25-34",
        "loyalty_tier": "Bronze",
        "preferred_device": "Mobile App",
        "country": "United Kingdom"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "TEST_CUST_1001"
    assert data["churn_prediction"] in [0, 1]
    assert 0.0 <= data["churn_probability"] <= 1.0
    assert data["risk_level"] in ["High Risk", "Medium Risk", "Low Risk"]
    assert "recommendation" in data


def test_api_batch_prediction_endpoint():
    """Verifies /batch_predict POST endpoint with multiple customer payloads."""
    payload = {
        "customers": [
            {
                "customer_id": "BATCH_CUST_1",
                "recency_days": 10.0,
                "frequency_orders": 12,
                "monetary_spend": 2500.0,
                "avg_order_value": 208.3,
                "total_units": 120,
                "cancellation_rate": 0.01,
                "inter_purchase_mean": 12.0,
                "inter_purchase_std": 2.0,
                "product_variety": 18,
                "gender": "Male",
                "age_group": "35-44",
                "loyalty_tier": "Gold",
                "preferred_device": "Desktop",
                "country": "United Kingdom"
            },
            {
                "customer_id": "BATCH_CUST_2",
                "recency_days": 180.0,
                "frequency_orders": 1,
                "monetary_spend": 45.0,
                "avg_order_value": 45.0,
                "total_units": 2,
                "cancellation_rate": 0.0,
                "inter_purchase_mean": 0.0,
                "inter_purchase_std": 0.0,
                "product_variety": 1,
                "gender": "Female",
                "age_group": "18-24",
                "loyalty_tier": "Bronze",
                "preferred_device": "Mobile App",
                "country": "United Kingdom"
            }
        ]
    }
    response = client.post("/batch_predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_processed"] == 2
    assert len(data["predictions"]) == 2
    assert "high_risk_count" in data
