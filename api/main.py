"""FastAPI Production Inference Microservice for Customer Churn Prediction."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    CustomerFeaturesInput,
    SinglePredictionResponse,
    BatchPredictionRequest,
    BatchPredictionResponse,
    HealthResponse,
)
from src.config import BASE_DIR
from src.database.connection import get_active_db_type

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ChurnAPI")

MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "production_churn_model.pkl"

app = FastAPI(
    title="RetailIQ Customer Churn Prediction API",
    description="Production MLOps inference microservice for real-time and batch customer churn probability scoring.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model container
MODEL_CONTAINER: Dict = {}


def load_model_pipeline():
    """Loads production churn model binary."""
    global MODEL_CONTAINER
    if not MODEL_PATH.exists():
        logger.info("Production model not found at %s. Running model training pipeline...", MODEL_PATH)
        from src.ml.train import train_and_evaluate_models
        train_and_evaluate_models()

    try:
        logger.info("Loading production model artifact from %s...", MODEL_PATH)
        payload = joblib.load(MODEL_PATH)
        MODEL_CONTAINER["model_name"] = payload.get("model_name", "ProductionClassifier")
        MODEL_CONTAINER["model"] = payload["model"]
        MODEL_CONTAINER["preprocessor"] = payload["preprocessor"]
        MODEL_CONTAINER["feature_names"] = payload["feature_names"]
        MODEL_CONTAINER["metrics"] = payload.get("metrics", {})
        logger.info("Model [%s] loaded successfully.", MODEL_CONTAINER["model_name"])
    except Exception as err:
        logger.exception("Failed to load production model artifact: %s", err)
        raise RuntimeError(f"Model initialization error: {err}")


@app.on_event("startup")
def startup_event():
    load_model_pipeline()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Healthcheck endpoint reporting system status and active model metrics."""
    if not MODEL_CONTAINER:
        load_model_pipeline()
    return HealthResponse(
        status="HEALTHY",
        active_model=MODEL_CONTAINER.get("model_name", "Unknown"),
        metrics=MODEL_CONTAINER.get("metrics", {}),
        database=get_active_db_type().upper(),
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/model_info")
def get_model_info():
    """Exposes production model metadata, feature list, and evaluation metrics."""
    if not MODEL_CONTAINER:
        load_model_pipeline()
    return {
        "model_name": MODEL_CONTAINER.get("model_name"),
        "metrics": MODEL_CONTAINER.get("metrics"),
        "feature_count": len(MODEL_CONTAINER.get("feature_names", [])),
        "feature_names": MODEL_CONTAINER.get("feature_names", []),
    }


def predict_single_customer(item: CustomerFeaturesInput) -> SinglePredictionResponse:
    """Core prediction logic for a single customer feature vector."""
    if not MODEL_CONTAINER:
        load_model_pipeline()

    # Build single row DataFrame matching training features
    raw_dict = {
        "recency_days": item.recency_days,
        "frequency_orders": item.frequency_orders,
        "monetary_spend": item.monetary_spend,
        "avg_order_value": item.avg_order_value,
        "total_units": item.total_units,
        "cancellation_rate": item.cancellation_rate,
        "inter_purchase_mean": item.inter_purchase_mean,
        "inter_purchase_std": item.inter_purchase_std,
        "product_variety": item.product_variety,
        "gender": item.gender,
        "age_group": item.age_group,
        "loyalty_tier": item.loyalty_tier,
        "preferred_device": item.preferred_device,
        "country": item.country,
    }
    df_raw = pd.DataFrame([raw_dict])

    # Transform with fitted pipeline preprocessor
    X_proc = MODEL_CONTAINER["preprocessor"].transform(df_raw)

    model = MODEL_CONTAINER["model"]
    pred = int(model.predict(X_proc)[0])
    prob = float(model.predict_proba(X_proc)[0, 1]) if hasattr(model, "predict_proba") else float(pred)

    # Risk categorization
    if prob >= 0.70:
        risk_level = "High Risk"
        rec = "Trigger VIP win-back campaign with 20% discount coupon immediately."
    elif prob >= 0.40:
        risk_level = "Medium Risk"
        rec = "Send personalized product recommendations and re-engagement email."
    else:
        risk_level = "Low Risk"
        rec = "Standard loyalty engagement. Customer is active and healthy."

    return SinglePredictionResponse(
        customer_id=item.customer_id,
        churn_prediction=pred,
        churn_probability=round(prob, 4),
        risk_level=risk_level,
        recommendation=rec,
        model_version="v1.0"
    )


@app.post("/predict", response_model=SinglePredictionResponse)
def predict_churn(customer_input: CustomerFeaturesInput):
    """Predicts customer churn probability and risk tier for a single customer profile."""
    try:
        return predict_single_customer(customer_input)
    except Exception as e:
        logger.exception("Prediction failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/batch_predict", response_model=BatchPredictionResponse)
def batch_predict_churn(request: BatchPredictionRequest):
    """Predicts churn probabilities for a batch list of customer feature records."""
    try:
        predictions = [predict_single_customer(cust) for cust in request.customers]
        high_risk = sum(1 for p in predictions if p.risk_level == "High Risk")
        return BatchPredictionResponse(
            predictions=predictions,
            total_processed=len(predictions),
            high_risk_count=high_risk
        )
    except Exception as e:
        logger.exception("Batch prediction failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
