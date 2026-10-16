"""MLflow Experiment Tracking and Model Registry Wrapper."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, log_loss, confusion_matrix, roc_curve, precision_recall_curve
)

from src.config import BASE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = BASE_DIR / "models"
EXPERIMENT_NAME = "ecommerce_customer_churn"


class MLflowTrackerManager:
    """Manages MLflow experiment tracking, metric logging, artifact generation, and model registration."""

    def __init__(self, experiment_name: str = EXPERIMENT_NAME):
        self.experiment_name = experiment_name
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.mlflow_active = False

        try:
            import mlflow
            self.mlflow = mlflow
            db_uri = f"sqlite:///{BASE_DIR}/mlruns.db"
            mlflow.set_tracking_uri(db_uri)
            mlflow.set_experiment(experiment_name)
            self.mlflow_active = True
            logger.info("MLflow tracking initialized successfully (URI: %s).", db_uri)
        except Exception as e:
            logger.warning("MLflow tracking initialization fallback (%s). Logging locally to models/.", e)

    def evaluate_and_log_run(
        self,
        model_name: str,
        model: Any,
        preprocessor: Any,
        X_val: np.ndarray,
        y_val: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        params: Dict[str, Any],
        feature_names: list
    ) -> Dict[str, float]:
        """Evaluates classifier predictions, generates visual artifacts, and logs to MLflow/Local Storage."""
        # Predictions
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else y_pred

        # Metrics
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        roc_auc = roc_auc_score(y_test, y_prob)
        loss = log_loss(y_test, y_prob)

        metrics = {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "log_loss": round(loss, 4),
        }

        logger.info("Model [%s] Evaluation Metrics:", model_name)
        for k, v in metrics.items():
            logger.info("  - %-12s: %.4f", k, v)

        # Artifact Generation: Confusion Matrix
        cm = confusion_matrix(y_test, y_pred)
        fig_cm, ax_cm = plt.subplots(figsize=(6, 5))
        ax_cm.matshow(cm, cmap=plt.cm.Blues, alpha=0.7)
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax_cm.text(x=j, y=i, s=f"{cm[i, j]}", va='center', ha='center', size='xx-large')
        plt.xlabel('Predicted Label', fontsize=12)
        plt.ylabel('True Label', fontsize=12)
        plt.title(f'Confusion Matrix - {model_name}', fontsize=14)
        cm_path = MODELS_DIR / f"{model_name.lower().replace(' ', '_')}_cm.png"
        plt.tight_layout()
        plt.savefig(cm_path)
        plt.close(fig_cm)

        # Artifact Generation: ROC Curve
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        fig_roc, ax_roc = plt.subplots(figsize=(6, 5))
        ax_roc.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.3f})')
        ax_roc.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
        plt.xlabel('False Positive Rate', fontsize=12)
        plt.ylabel('True Positive Rate', fontsize=12)
        plt.title(f'ROC Curve - {model_name}', fontsize=14)
        plt.legend(loc="lower right")
        roc_path = MODELS_DIR / f"{model_name.lower().replace(' ', '_')}_roc.png"
        plt.tight_layout()
        plt.savefig(roc_path)
        plt.close(fig_roc)

        # Log to MLflow if active
        if self.mlflow_active:
            try:
                with self.mlflow.start_run(run_name=model_name):
                    self.mlflow.log_params(params)
                    self.mlflow.log_metrics(metrics)
                    self.mlflow.log_artifact(str(cm_path))
                    self.mlflow.log_artifact(str(roc_path))
            except Exception as err:
                logger.warning("Failed to log to MLflow server (%s).", err)

        # Local Metadata Backup
        meta = {
            "model_name": model_name,
            "params": params,
            "metrics": metrics,
            "cm_path": str(cm_path),
            "roc_path": str(roc_path)
        }
        meta_path = MODELS_DIR / f"{model_name.lower().replace(' ', '_')}_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return metrics

    def save_production_model(
        self,
        best_model_name: str,
        best_model: Any,
        preprocessor: Any,
        feature_names: list,
        metrics: Dict[str, float]
    ) -> Path:
        """Serializes winning model pipeline into models/production_churn_model.pkl."""
        model_payload = {
            "model_name": best_model_name,
            "model": best_model,
            "preprocessor": preprocessor,
            "feature_names": feature_names,
            "metrics": metrics,
        }
        prod_path = MODELS_DIR / "production_churn_model.pkl"
        joblib.dump(model_payload, prod_path)

        # Save metadata summary
        prod_meta_path = MODELS_DIR / "production_model_meta.json"
        with open(prod_meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "registered_name": "EcommerceChurnPredictor",
                "version": "1.0",
                "winning_model": best_model_name,
                "metrics": metrics,
                "feature_count": len(feature_names),
                "saved_at": pd.Timestamp.utcnow().isoformat()
            }, f, indent=2)

        logger.info("Production Churn Model registered and saved to %s.", prod_path)
        return prod_path
