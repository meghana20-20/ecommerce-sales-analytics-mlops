"""Model Training Pipeline for Customer Churn Classifiers."""

import json
import logging
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier, GradientBoostingClassifier

try:
    from xgboost import XGBClassifier
    _HAS_XGBOOST = True
except Exception:
    _HAS_XGBOOST = False

from src.ml.feature_engineering import prepare_churn_features
from src.ml.mlflow_tracker import MLflowTrackerManager
from src.config import BASE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = BASE_DIR / "models"


def train_and_evaluate_models() -> Dict:
    """Trains Logistic Regression, Random Forest, and Gradient Boosted Tree classifiers, logs experiments, and registers winning model."""
    logger.info("=" * 80)
    logger.info("STARTING PHASE 2 MACHINE LEARNING MODEL TRAINING PIPELINE")
    logger.info("=" * 80)

    # 1. Feature Engineering & Temporal Data Split
    data = prepare_churn_features()
    X_train, y_train = data["X_train"], data["y_train"]
    X_val, y_val = data["X_val"], data["y_val"]
    X_test, y_test = data["X_test"], data["y_test"]
    preprocessor = data["preprocessor"]
    feature_names = data["feature_names"]

    tracker = MLflowTrackerManager()

    # Model Definitions & Hyperparameters
    classifiers = {
        "Logistic_Regression": {
            "model": LogisticRegression(max_iter=1000, C=1.0, penalty="l2", random_state=42),
            "params": {"C": 1.0, "penalty": "l2", "solver": "lbfgs", "max_iter": 1000}
        },
        "Random_Forest": {
            "model": RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1),
            "params": {"n_estimators": 100, "max_depth": 10, "criterion": "gini", "random_state": 42}
        },
    }

    if _HAS_XGBOOST:
        try:
            xgb = XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.05, random_state=42, eval_metric="logloss")
            # Dry run test if dylib loads
            xgb.fit(X_train[:10], y_train[:10])
            classifiers["XGBoost"] = {
                "model": XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.05, random_state=42, eval_metric="logloss"),
                "params": {"n_estimators": 100, "max_depth": 5, "learning_rate": 0.05, "eval_metric": "logloss", "random_state": 42}
            }
        except Exception as e:
            logger.warning("XGBoost library load failed (%s). Using HistGradientBoostingClassifier fallback.", e)
            classifiers["Gradient_Boosting"] = {
                "model": HistGradientBoostingClassifier(max_iter=100, max_depth=5, learning_rate=0.05, random_state=42),
                "params": {"max_iter": 100, "max_depth": 5, "learning_rate": 0.05, "random_state": 42}
            }
    else:
        classifiers["Gradient_Boosting"] = {
            "model": HistGradientBoostingClassifier(max_iter=100, max_depth=5, learning_rate=0.05, random_state=42),
            "params": {"max_iter": 100, "max_depth": 5, "learning_rate": 0.05, "random_state": 42}
        }

    results = {}
    best_score = -1.0
    best_model_name = None
    best_model_obj = None

    for name, spec in classifiers.items():
        logger.info("-" * 60)
        logger.info("Training Model: [%s]...", name)
        model = spec["model"]
        params = spec["params"]

        # Fit model on training set
        model.fit(X_train, y_train)

        # Evaluate and log run via MLflow manager
        metrics = tracker.evaluate_and_log_run(
            model_name=name,
            model=model,
            preprocessor=preprocessor,
            X_val=X_val,
            y_val=y_val,
            X_test=X_test,
            y_test=y_test,
            params=params,
            feature_names=feature_names
        )

        results[name] = {
            "params": params,
            "metrics": metrics
        }

        # Model selection metric: ROC-AUC + F1 Score combination
        combined_score = metrics["roc_auc"] * 0.6 + metrics["f1_score"] * 0.4
        if combined_score > best_score:
            best_score = combined_score
            best_model_name = name
            best_model_obj = model

    logger.info("=" * 80)
    logger.info("WINNING MODEL SELECTED: [%s] (Combined Score: %.4f, ROC-AUC: %.4f)",
                best_model_name, best_score, results[best_model_name]["metrics"]["roc_auc"])
    logger.info("=" * 80)

    # Save and Register Production Model
    prod_path = tracker.save_production_model(
        best_model_name=best_model_name,
        best_model=best_model_obj,
        preprocessor=preprocessor,
        feature_names=feature_names,
        metrics=results[best_model_name]["metrics"]
    )

    # Save summary report JSON
    comparison_path = MODELS_DIR / "model_comparison.json"
    with open(comparison_path, "w", encoding="utf-8") as f:
        json.dump({
            "winning_model": best_model_name,
            "best_score": best_score,
            "comparison": results,
            "dataset_sizes": {
                "train_samples": len(X_train),
                "val_samples": len(X_val),
                "test_samples": len(X_test),
                "feature_count": len(feature_names)
            }
        }, f, indent=2)

    return {
        "winning_model": best_model_name,
        "best_score": best_score,
        "results": results,
        "production_model_path": str(prod_path)
    }


if __name__ == "__main__":
    train_and_evaluate_models()
