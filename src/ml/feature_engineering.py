"""Temporal Feature Engineering Engine & Dataset Splitter for Customer Churn Prediction."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Tuple, List
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer

from src.database.connection import execute_query
from src.config import GUEST_CUSTOMER_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def extract_customer_features(
    inactivity_days: int = 90,
    observation_days: int = 180,
) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """Extracts customer behavioral features and churn targets using a temporal observation window.
    
    Prevents temporal data leakage by constructing feature vectors from observation history
    and evaluating churn labels over the subsequent inactivity window.
    """
    logger.info("Extracting transactional history from data warehouse...")
    sales_sql = """
    SELECT 
        f.invoice_no, f.customer_key, c.customer_id, c.gender, c.age_group,
        c.loyalty_tier, c.preferred_device, c.country, f.invoice_timestamp,
        f.quantity, f.unit_price, f.total_amount, f.is_cancelled, f.product_key
    FROM fact_sales f
    JOIN dim_customer c ON f.customer_key = c.customer_key
    WHERE c.customer_id != 0
    """
    df = execute_query(sales_sql)
    df["invoice_timestamp"] = pd.to_datetime(df["invoice_timestamp"])

    max_date = df["invoice_timestamp"].max()
    cutoff_date = max_date - pd.Timedelta(days=inactivity_days)
    observation_start = cutoff_date - pd.Timedelta(days=observation_days)

    logger.info("Temporal Split Boundaries:")
    logger.info("  - Observation Window: %s to %s (%d days)", observation_start.date(), cutoff_date.date(), observation_days)
    logger.info("  - Target Label Window: %s to %s (%d days)", cutoff_date.date(), max_date.date(), inactivity_days)

    # Filter observation transactions
    obs_df = df[(df["invoice_timestamp"] >= observation_start) & (df["invoice_timestamp"] < cutoff_date)].copy()
    target_df = df[(df["invoice_timestamp"] >= cutoff_date) & (df["invoice_timestamp"] <= max_date)].copy()

    is_cancelled_target = target_df["is_cancelled"].astype(bool)
    active_target_customers = set(target_df[~is_cancelled_target]["customer_id"].unique())

    # Aggregate customer features in observation window
    features_list = []
    grouped = obs_df.groupby("customer_id")

    for cust_id, group in grouped:
        is_cancelled_obs = group["is_cancelled"].astype(bool)
        valid_orders = group[~is_cancelled_obs]
        if valid_orders.empty:
            continue

        last_order = valid_orders["invoice_timestamp"].max()
        recency = (cutoff_date - last_order).days
        frequency = valid_orders["invoice_no"].nunique()
        monetary = valid_orders["total_amount"].sum()
        avg_basket = monetary / frequency if frequency > 0 else 0.0
        total_qty = valid_orders["quantity"].sum()
        cancellation_rate = len(group[is_cancelled_obs]) / len(group)
        product_variety = valid_orders["product_key"].nunique()

        # Inter-purchase latency
        order_dates = valid_orders[["invoice_no", "invoice_timestamp"]].drop_duplicates().sort_values("invoice_timestamp")["invoice_timestamp"]
        if len(order_dates) > 1:
            latencies = order_dates.diff().dt.days.dropna()
            mean_latency = latencies.mean()
            std_latency = latencies.std() if len(latencies) > 1 else 0.0
        else:
            mean_latency = observation_days
            std_latency = 0.0

        # Demographics
        first_row = group.iloc[0]
        gender = first_row.get("gender", "Unknown")
        age_group = first_row.get("age_group", "Unknown")
        loyalty_tier = first_row.get("loyalty_tier", "Bronze")
        preferred_device = first_row.get("preferred_device", "Desktop Web")
        country = first_row.get("country", "United Kingdom")

        # Label: Churned = 1 if NO active order in target window
        is_churned = 0 if cust_id in active_target_customers else 1

        features_list.append({
            "customer_id": cust_id,
            "recency_days": recency,
            "frequency_orders": frequency,
            "monetary_spend": round(monetary, 2),
            "avg_order_value": round(avg_basket, 2),
            "total_units": total_qty,
            "cancellation_rate": round(cancellation_rate, 4),
            "inter_purchase_mean": round(mean_latency, 2),
            "inter_purchase_std": round(std_latency, 2),
            "product_variety": product_variety,
            "gender": gender,
            "age_group": age_group,
            "loyalty_tier": loyalty_tier,
            "preferred_device": preferred_device,
            "country": country,
            "is_churned": is_churned,
        })

    feat_df = pd.DataFrame(features_list)
    logger.info("Extracted feature set for %d customers. Target churn distribution: %s", len(feat_df), feat_df["is_churned"].value_counts().to_dict())

    X = feat_df.drop(columns=["customer_id", "is_churned"])
    y = feat_df["is_churned"]
    feature_names = X.columns.tolist()

    return X, y, feature_names


def prepare_churn_features(
    test_size: float = 0.2,
    val_size: float = 0.15,
    random_state: int = 42
) -> Dict:
    """Prepares train, validation, and test splits with fitted preprocessors."""
    X, y, feature_names = extract_customer_features()

    # Train / Test split
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    # Train / Val split
    val_ratio_adjusted = val_size / (1.0 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=val_ratio_adjusted, random_state=random_state, stratify=y_train_val
    )

    num_cols = ["recency_days", "frequency_orders", "monetary_spend", "avg_order_value", "total_units", "cancellation_rate", "inter_purchase_mean", "inter_purchase_std", "product_variety"]
    cat_cols = ["gender", "age_group", "loyalty_tier", "preferred_device", "country"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
        ]
    )

    X_train_proc = preprocessor.fit_transform(X_train)
    X_val_proc = preprocessor.transform(X_val)
    X_test_proc = preprocessor.transform(X_test)

    # Get transformed column names
    cat_feature_names = preprocessor.named_transformers_["cat"].get_feature_names_out(cat_cols).tolist()
    all_transformed_names = num_cols + cat_feature_names

    logger.info("Dataset splitting completed:")
    logger.info("  - Train Set: %d samples", len(X_train))
    logger.info("  - Validation Set: %d samples", len(X_val))
    logger.info("  - Test Set: %d samples", len(X_test))
    logger.info("  - Total Features Dimension: %d columns", X_train_proc.shape[1])

    return {
        "X_train": X_train_proc,
        "X_val": X_val_proc,
        "X_test": X_test_proc,
        "y_train": y_train,
        "y_val": y_val,
        "y_test": y_test,
        "X_train_raw": X_train,
        "X_val_raw": X_val,
        "X_test_raw": X_test,
        "preprocessor": preprocessor,
        "feature_names": all_transformed_names,
        "num_cols": num_cols,
        "cat_cols": cat_cols,
    }
