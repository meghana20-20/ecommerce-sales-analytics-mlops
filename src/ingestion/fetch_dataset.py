"""Acquires and validates the primary UCI Online Retail dataset."""

import json
import logging
import os
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
import pandas as pd

from src.config import (
    RAW_DATA_DIR,
    RAW_EXCEL_PATH,
    UCI_DATASET_URL,
    UCI_BACKUP_EXCEL_URL,
    AUDIT_LOG_PATH,
    EXPECTED_COLUMNS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def log_ingestion_metadata(metadata: dict) -> None:
    """Appends or updates ingestion audit log in JSON format."""
    history = []
    if AUDIT_LOG_PATH.exists():
        try:
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append(metadata)
    with open(AUDIT_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def fetch_uci_dataset(force_download: bool = False) -> Path:
    """Downloads the official UCI Online Retail dataset if not already present.
    
    Returns the path to the cached raw parquet / CSV file.
    """
    raw_parquet_path = RAW_DATA_DIR / "online_retail_raw.parquet"
    raw_csv_path = RAW_DATA_DIR / "online_retail_raw.csv"

    if not force_download and raw_parquet_path.exists() and raw_parquet_path.stat().st_size > 1000000:
        logger.info("Raw dataset already cached at %s", raw_parquet_path)
        return raw_parquet_path

    logger.info("Starting acquisition of UCI Online Retail dataset...")
    temp_zip_path = RAW_DATA_DIR / "online_retail_temp.zip"
    download_source = UCI_DATASET_URL

    if not RAW_EXCEL_PATH.exists():
        try:
            logger.info("Downloading zip archive from %s ...", UCI_DATASET_URL)
            urllib.request.urlretrieve(UCI_DATASET_URL, temp_zip_path)
            logger.info("Extracting Online Retail.xlsx from zip...")
            with zipfile.ZipFile(temp_zip_path, "r") as zip_ref:
                zip_ref.extract("Online Retail.xlsx", RAW_DATA_DIR)
            if temp_zip_path.exists():
                temp_zip_path.unlink()
        except Exception as err:
            logger.warning("Zip download failed (%s). Attempting direct Excel download...", err)
            download_source = UCI_BACKUP_EXCEL_URL
            urllib.request.urlretrieve(UCI_BACKUP_EXCEL_URL, RAW_EXCEL_PATH)

    logger.info("Reading raw Excel file into DataFrame (this may take a few seconds)...")
    df_raw = pd.read_excel(RAW_EXCEL_PATH, engine="openpyxl")
    row_count = len(df_raw)
    logger.info("Raw dataset loaded: %d rows, %d columns.", row_count, len(df_raw.columns))

    # Verify column presence
    missing_cols = [col for col in EXPECTED_COLUMNS if col not in df_raw.columns]
    if missing_cols:
        raise ValueError(f"Raw dataset is missing required columns: {missing_cols}")

    # Ensure text columns are explicitly strings for Arrow / Parquet compatibility
    df_raw["InvoiceNo"] = df_raw["InvoiceNo"].astype(str)
    df_raw["StockCode"] = df_raw["StockCode"].astype(str)
    df_raw["Description"] = df_raw["Description"].fillna("").astype(str)
    df_raw["Country"] = df_raw["Country"].fillna("").astype(str)

    # Save to Parquet and CSV for lightning-fast ETL access
    logger.info("Serializing raw dataset to Parquet and CSV in %s ...", RAW_DATA_DIR)
    df_raw.to_parquet(raw_parquet_path, index=False)
    df_raw.to_csv(raw_csv_path, index=False)

    metadata = {
        "event": "DATASET_INGESTION",
        "source": download_source,
        "filename": RAW_EXCEL_PATH.name,
        "file_size_bytes": RAW_EXCEL_PATH.stat().st_size if RAW_EXCEL_PATH.exists() else 0,
        "row_count": row_count,
        "column_count": len(df_raw.columns),
        "columns": df_raw.columns.tolist(),
        "timestamp": datetime.utcnow().isoformat(),
        "status": "SUCCESS",
    }
    log_ingestion_metadata(metadata)
    logger.info("Ingestion metadata logged successfully.")
    return raw_parquet_path


if __name__ == "__main__":
    fetch_uci_dataset()
