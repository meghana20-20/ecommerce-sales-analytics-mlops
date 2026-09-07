"""Analytical Data Marts: Sales Performance and Customer RFM Segmentation."""

import logging
from typing import Tuple
import numpy as np
import pandas as pd

from src.config import GUEST_CUSTOMER_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def build_mart_sales_performance(
    df_fact_sales: pd.DataFrame,
    df_dim_date: pd.DataFrame,
    df_dim_geo: pd.DataFrame
) -> pd.DataFrame:
    """Aggregates multi-dimensional sales performance metrics into an analytical mart."""
    logger.info("Computing mart_sales_performance...")
    df = df_fact_sales.copy()

    # Join date and geo attributes
    date_map = dict(zip(df_dim_date["date_key"], df_dim_date["year"].astype(str) + "-" + df_dim_date["month"].astype(str).str.zfill(2)))
    geo_map = dict(zip(df_dim_geo["geography_key"], df_dim_geo["country_name"]))

    df["year_month"] = df["date_key"].map(date_map)
    df["country_name"] = df["geography_key"].map(geo_map)

    # Aggregations by date_key, year_month, country_name
    grouped = df.groupby(["date_key", "year_month", "country_name"]).agg(
        total_revenue=("total_amount", "sum"),
        total_orders=("invoice_no", "nunique"),
        total_units_sold=("quantity", "sum"),
        unique_customers=("customer_key", "nunique"),
        cancelled_orders_count=("is_cancelled", lambda x: int(x.sum()))
    ).reset_index()

    grouped["average_order_value"] = np.where(
        grouped["total_orders"] > 0,
        (grouped["total_revenue"] / grouped["total_orders"]).round(2),
        0.0
    )
    grouped["total_revenue"] = grouped["total_revenue"].round(2)

    grouped.reset_index(drop=True, inplace=True)
    grouped["mart_id"] = grouped.index + 1

    cols = [
        "mart_id", "date_key", "year_month", "country_name",
        "total_revenue", "total_orders", "total_units_sold",
        "average_order_value", "unique_customers", "cancelled_orders_count"
    ]
    logger.info("mart_sales_performance computed successfully with %d rows.", len(grouped))
    return grouped[cols]


def assign_rfm_segment(r: int, f: int, m: int) -> str:
    """Classifies customers into standard behavioral segments based on RFM quartile scores."""
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    elif r <= 2 and (f >= 3 or m >= 3):
        return "At Risk - Needs Attention"
    elif r >= 3 and f >= 3 and m >= 3:
        return "Loyal Customers"
    elif r >= 4 and f <= 2:
        return "New / Potential Loyalists"
    elif r >= 3:
        return "Promising Customers"
    elif r == 1:
        return "Lost Customers"
    elif r <= 2 and f <= 2 and m <= 2:
        return "Hibernating"
    return "Standard Regulars"


def build_mart_customer_rfm(
    df_fact_sales: pd.DataFrame,
    df_dim_cust: pd.DataFrame
) -> pd.DataFrame:
    """Computes Recency, Frequency, and Monetary (RFM) segmentation for all registered customers."""
    logger.info("Computing mart_customer_rfm...")
    cust_key_to_id = dict(zip(df_dim_cust["customer_key"], df_dim_cust["customer_id"]))
    cust_tier_map = dict(zip(df_dim_cust["customer_key"], df_dim_cust.get("loyalty_tier", "Bronze")))

    # Filter out guest customers and invalid records for RFM
    sales = df_fact_sales.copy()
    sales["customer_id"] = sales["customer_key"].map(cust_key_to_id)
    reg_sales = sales[
        (sales["customer_id"] != GUEST_CUSTOMER_ID) &
        (~sales["is_cancelled"]) &
        (sales["total_amount"] > 0)
    ].copy()

    if reg_sales.empty:
        logger.warning("No registered sales available for RFM calculation.")
        return pd.DataFrame()

    reg_sales["invoice_timestamp"] = pd.to_datetime(reg_sales["invoice_timestamp"])
    snapshot_date = reg_sales["invoice_timestamp"].max() + pd.Timedelta(days=1)

    # Group by customer
    rfm = reg_sales.groupby(["customer_key", "customer_id"]).agg(
        last_order_timestamp=("invoice_timestamp", "max"),
        frequency=("invoice_no", "nunique"),
        monetary_total=("total_amount", "sum")
    ).reset_index()

    rfm["recency_days"] = (snapshot_date - rfm["last_order_timestamp"]).dt.days.astype(int)
    rfm["last_order_date"] = rfm["last_order_timestamp"].dt.date
    rfm["monetary_total"] = rfm["monetary_total"].round(2)

    # RFM Scoring using quintiles (1-5) or quantiles
    # Recency: lower days = higher score (5)
    rfm["r_score"] = pd.qcut(rfm["recency_days"], q=5, labels=[5, 4, 3, 2, 1], duplicates="drop").astype(int)
    # Frequency: higher freq = higher score (5)
    rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    # Monetary: higher monetary = higher score (5)
    rfm["m_score"] = pd.qcut(rfm["monetary_total"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5]).astype(int)

    rfm["rfm_score"] = rfm["r_score"].astype(str) + rfm["f_score"].astype(str) + rfm["m_score"].astype(str)
    rfm["customer_segment"] = rfm.apply(lambda row: assign_rfm_segment(row["r_score"], row["f_score"], row["m_score"]), axis=1)
    rfm["loyalty_tier"] = rfm["customer_key"].map(cust_tier_map).fillna("Bronze")

    cols = [
        "customer_key", "customer_id", "recency_days", "frequency", "monetary_total",
        "r_score", "f_score", "m_score", "rfm_score", "customer_segment",
        "loyalty_tier", "last_order_date"
    ]
    logger.info("mart_customer_rfm computed successfully for %d customers.", len(rfm))
    return rfm[cols]
