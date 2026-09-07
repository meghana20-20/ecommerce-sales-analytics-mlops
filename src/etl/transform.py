"""Transform component: standardization, deduplication, and feature derivation."""

import logging
from typing import Tuple
import pandas as pd
import numpy as np

from src.config import GUEST_CUSTOMER_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def clean_and_transform_batch(valid_df: pd.DataFrame, batch_id: str) -> pd.DataFrame:
    """Standardizes, deduplicates, and enriches clean transaction records."""
    if valid_df.empty:
        logger.warning("Empty batch passed to clean_and_transform_batch [%s].", batch_id)
        return valid_df

    logger.info("Transforming batch [%s] with %d records...", batch_id, len(valid_df))
    df = valid_df.copy()

    # 1. Standardize text attributes
    df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
    df["StockCode"] = df["StockCode"].astype(str).str.strip().str.upper()
    df["Description"] = df["Description"].fillna("UNKNOWN_PRODUCT").astype(str).str.strip().str.upper()
    df["Country"] = df["Country"].fillna("United Kingdom").astype(str).str.strip().str.title()

    # 2. Parse and standardize dates
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["date_key"] = df["InvoiceDate"].dt.strftime("%Y%m%d").astype(int)

    # 3. Numeric conversions & revenue derivation
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").astype(int)
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce").round(2)
    df["total_amount"] = (df["Quantity"] * df["UnitPrice"]).round(2)

    # 4. Cancellation flag
    df["is_cancelled"] = df["InvoiceNo"].str.upper().str.startswith("C") | (df["Quantity"] < 0)

    # 5. Customer ID handling (assign guest customer 0 if unassigned)
    df["customer_id"] = (
        pd.to_numeric(df["CustomerID"], errors="coerce")
        .fillna(GUEST_CUSTOMER_ID)
        .astype(int)
    )

    # 6. Deduplication & Idempotency
    initial_rows = len(df)
    df.drop_duplicates(
        subset=["InvoiceNo", "StockCode", "Quantity", "UnitPrice", "InvoiceDate"],
        keep="first",
        inplace=True
    )
    duplicates_removed = initial_rows - len(df)
    if duplicates_removed > 0:
        logger.info("Batch [%s]: Removed %d exact duplicate transaction rows.", batch_id, duplicates_removed)

    df["batch_id"] = batch_id
    logger.info("Batch [%s] transformation complete. %d clean rows prepared.", batch_id, len(df))
    return df
