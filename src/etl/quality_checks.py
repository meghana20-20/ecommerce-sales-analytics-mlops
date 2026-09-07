"""Data Quality validation engine, rejection logging, and audit metrics."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple
import pandas as pd
import numpy as np

from src.config import (
    REJECTED_RECORDS_PATH,
    MIN_PRICE_VALID,
    MAX_PRICE_THRESHOLD,
    MAX_QUANTITY_THRESHOLD,
    GUEST_CUSTOMER_ID,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def validate_batch(df: pd.DataFrame, batch_id: str) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """Validates raw records against business rules and segregates clean vs rejected data.
    
    Returns:
        valid_df: Records passing quality criteria.
        rejected_df: Records failing quality criteria with explicit rejection reasons.
        quality_summary: Statistics on pass/rejection rates and anomaly types.
    """
    logger.info("Executing Data Quality checks for batch [%s] on %d records...", batch_id, len(df))
    working_df = df.copy()

    # Pre-process columns
    working_df["InvoiceNo_str"] = working_df["InvoiceNo"].astype(str).str.strip()
    working_df["StockCode_str"] = working_df["StockCode"].astype(str).str.strip()
    working_df["Quantity_num"] = pd.to_numeric(working_df["Quantity"], errors="coerce")
    working_df["UnitPrice_num"] = pd.to_numeric(working_df["UnitPrice"], errors="coerce")
    
    # Check if invoice is an official cancellation (starts with 'C')
    is_cancellation = working_df["InvoiceNo_str"].str.upper().str.startswith("C")

    # Define validation failure masks
    reasons = []

    # 1. Null / Empty Invoice or StockCode
    mask_null_invoice = working_df["InvoiceNo_str"].isna() | (working_df["InvoiceNo_str"] == "") | (working_df["InvoiceNo_str"].str.lower() == "nan")
    mask_null_stock = working_df["StockCode_str"].isna() | (working_df["StockCode_str"] == "") | (working_df["StockCode_str"].str.lower() == "nan")

    # 2. Price validation
    mask_invalid_price = (
        working_df["UnitPrice_num"].isna()
        | (working_df["UnitPrice_num"] < 0)
        | (working_df["UnitPrice_num"] == 0)
        | (working_df["UnitPrice_num"] > MAX_PRICE_THRESHOLD)
    )

    # 3. Quantity validation:
    # Cancellation records (starting with 'C') are allowed negative quantity.
    # Non-cancellation records MUST have positive quantity.
    mask_invalid_qty = (
        working_df["Quantity_num"].isna()
        | (working_df["Quantity_num"] == 0)
        | ((~is_cancellation) & (working_df["Quantity_num"] < 0))
        | (working_df["Quantity_num"].abs() > MAX_QUANTITY_THRESHOLD)
    )

    # 4. Date parsing check
    parsed_dates = pd.to_datetime(working_df["InvoiceDate"], errors="coerce")
    mask_invalid_date = parsed_dates.isna()

    # Combine into a prioritized rejection reason
    rejection_mask = mask_null_invoice | mask_null_stock | mask_invalid_price | mask_invalid_qty | mask_invalid_date

    rejected_records = []
    if rejection_mask.any():
        bad_df = working_df[rejection_mask].copy()
        
        # Assign explicit reasons
        conditions = [
            mask_null_invoice[rejection_mask],
            mask_null_stock[rejection_mask],
            mask_invalid_price[rejection_mask],
            mask_invalid_qty[rejection_mask],
            mask_invalid_date[rejection_mask],
        ]
        choices = [
            "NULL_OR_EMPTY_INVOICE_NO",
            "NULL_OR_EMPTY_STOCK_CODE",
            "INVALID_OR_ZERO_UNIT_PRICE",
            "INVALID_OR_ZERO_QUANTITY",
            "INVALID_INVOICE_DATE_FORMAT",
        ]
        bad_df["rejection_reason"] = np.select(conditions, choices, default="UNKNOWN_VALIDATION_ERROR")
        bad_df["batch_id"] = batch_id
        bad_df["logged_at"] = datetime.utcnow().isoformat()
        
        # Persist to rejected records file
        cols_to_export = [
            "batch_id", "InvoiceNo", "StockCode", "Description",
            "Quantity", "UnitPrice", "CustomerID", "Country",
            "rejection_reason", "logged_at"
        ]
        existing_cols = [c for c in cols_to_export if c in bad_df.columns]
        rejected_export = bad_df[existing_cols]

        REJECTED_RECORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        if REJECTED_RECORDS_PATH.exists():
            rejected_export.to_csv(REJECTED_RECORDS_PATH, mode="a", header=False, index=False)
        else:
            rejected_export.to_csv(REJECTED_RECORDS_PATH, mode="w", header=True, index=False)

        rejected_records = rejected_export
        logger.warning("Batch [%s]: %d records failed quality checks and were quarantined.", batch_id, len(bad_df))
    else:
        rejected_records = pd.DataFrame(columns=[
            "batch_id", "InvoiceNo", "StockCode", "Description",
            "Quantity", "UnitPrice", "CustomerID", "Country",
            "rejection_reason", "logged_at"
        ])

    # Filter clean dataset
    clean_df = working_df[~rejection_mask].copy()
    clean_df.drop(columns=["InvoiceNo_str", "StockCode_str", "Quantity_num", "UnitPrice_num"], inplace=True)

    # Summary statistics
    total_count = len(df)
    clean_count = len(clean_df)
    rejected_count = len(rejected_records)
    pass_rate = round((clean_count / total_count * 100), 2) if total_count > 0 else 0.0

    quality_summary = {
        "batch_id": batch_id,
        "total_records": total_count,
        "valid_records": clean_count,
        "rejected_records": rejected_count,
        "pass_rate_pct": pass_rate,
        "rejection_breakdown": rejected_records["rejection_reason"].value_counts().to_dict() if rejected_count > 0 else {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    logger.info("Batch [%s] Quality Pass Rate: %s%% (%d clean, %d rejected)", batch_id, pass_rate, clean_count, rejected_count)
    return clean_df, rejected_records, quality_summary


def run_data_quality_audit() -> pd.DataFrame:
    """Reads the cumulative rejected records log and returns summary metrics."""
    if not REJECTED_RECORDS_PATH.exists():
        return pd.DataFrame(columns=["rejection_reason", "count", "pct"])
    df = pd.read_csv(REJECTED_RECORDS_PATH)
    if df.empty:
        return pd.DataFrame(columns=["rejection_reason", "count", "pct"])
    summary = df["rejection_reason"].value_counts().reset_index()
    summary.columns = ["rejection_reason", "count"]
    summary["pct"] = round(summary["count"] / summary["count"].sum() * 100, 2)
    return summary
