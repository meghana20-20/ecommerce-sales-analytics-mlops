"""Extract component for loading raw order transaction data into staging."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple
import pandas as pd

from src.config import RAW_DATA_DIR, STAGING_DATA_DIR, EXPECTED_COLUMNS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def extract_raw_batch(file_path: Path, batch_id: str) -> Tuple[pd.DataFrame, Dict]:
    """Reads a specific raw transaction batch file into staging."""
    if not file_path.exists():
        raise FileNotFoundError(f"Source batch file not found: {file_path}")

    start_time = datetime.utcnow()
    logger.info("Extracting raw batch [%s] from %s...", batch_id, file_path)

    if file_path.suffix == ".parquet":
        df = pd.read_parquet(file_path)
    elif file_path.suffix in [".csv", ".txt"]:
        df = pd.read_csv(file_path, dtype={"InvoiceNo": str, "StockCode": str})
    elif file_path.suffix in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path, engine="openpyxl", dtype={"InvoiceNo": str, "StockCode": str})
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")

    # Column presence check
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            raise KeyError(f"Expected column '{col}' missing from extract: {file_path}")

    staging_path = STAGING_DATA_DIR / f"staging_{batch_id}.parquet"
    df.to_parquet(staging_path, index=False)

    metadata = {
        "batch_id": batch_id,
        "source_file": str(file_path.name),
        "source_path": str(file_path),
        "staging_path": str(staging_path),
        "extraction_timestamp": start_time.isoformat(),
        "raw_row_count": len(df),
        "raw_columns": df.columns.tolist(),
        "status": "EXTRACTED",
    }
    logger.info("Extracted %d records for batch [%s]. Staged to %s", len(df), batch_id, staging_path)
    return df, metadata


def extract_full_dataset() -> Tuple[pd.DataFrame, Dict]:
    """Extracts the complete raw dataset as a single baseline batch."""
    parquet_path = RAW_DATA_DIR / "online_retail_raw.parquet"
    csv_path = RAW_DATA_DIR / "online_retail_raw.csv"

    if parquet_path.exists():
        target = parquet_path
    elif csv_path.exists():
        target = csv_path
    else:
        from src.ingestion.fetch_dataset import fetch_uci_dataset
        target = fetch_uci_dataset()

    return extract_raw_batch(target, batch_id="full_historical_baseline")
