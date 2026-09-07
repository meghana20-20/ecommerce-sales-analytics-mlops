"""Generates simulated monthly order batch files to demonstrate incremental ingestion."""

import json
import logging
from pathlib import Path
from typing import List, Dict
import pandas as pd

from src.config import RAW_DATA_DIR, RAW_EXCEL_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BATCHES_DIR = RAW_DATA_DIR / "batches"
BATCH_MANIFEST_PATH = BATCHES_DIR / "batch_manifest.json"


def generate_monthly_batches(source_df: pd.DataFrame = None) -> List[Dict]:
    """Partitions the raw online retail transactions into monthly CSV files.
    
    This simulates an ongoing enterprise data flow where monthly transaction extracts
    arrive sequentially into the landing area.
    """
    BATCHES_DIR.mkdir(parents=True, exist_ok=True)

    if source_df is None:
        raw_parquet_path = RAW_DATA_DIR / "online_retail_raw.parquet"
        if raw_parquet_path.exists():
            logger.info("Loading raw dataset from %s", raw_parquet_path)
            source_df = pd.read_parquet(raw_parquet_path)
        elif RAW_EXCEL_PATH.exists():
            logger.info("Loading raw dataset from Excel %s", RAW_EXCEL_PATH)
            source_df = pd.read_excel(RAW_EXCEL_PATH)
        else:
            raise FileNotFoundError("Raw dataset not found. Please run fetch_uci_dataset first.")

    df = source_df.copy()
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    df["YearMonth"] = df["InvoiceDate"].dt.strftime("%Y_%m")

    unique_months = sorted(df["YearMonth"].dropna().unique())
    logger.info("Identified %d monthly batch partitions: %s", len(unique_months), unique_months)

    manifest = []
    for ym in unique_months:
        batch_df = df[df["YearMonth"] == ym].drop(columns=["YearMonth"])
        batch_filename = f"orders_{ym}.csv"
        batch_file_path = BATCHES_DIR / batch_filename
        
        batch_df.to_csv(batch_file_path, index=False)
        
        batch_info = {
            "batch_id": f"batch_{ym}",
            "period": ym.replace("_", "-"),
            "filename": batch_filename,
            "filepath": str(batch_file_path),
            "row_count": len(batch_df),
            "min_invoice_date": str(batch_df["InvoiceDate"].min()),
            "max_invoice_date": str(batch_df["InvoiceDate"].max()),
            "status": "READY_FOR_INGESTION",
        }
        manifest.append(batch_info)
        logger.info("Created batch %s: %d records -> %s", batch_info["batch_id"], len(batch_df), batch_filename)

    with open(BATCH_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Batch manifest written to %s with %d batches.", BATCH_MANIFEST_PATH, len(manifest))
    return manifest


if __name__ == "__main__":
    generate_monthly_batches()
