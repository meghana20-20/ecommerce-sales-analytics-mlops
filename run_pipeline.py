#!/usr/bin/env python3
"""End-to-End Orchestrator CLI for the E-Commerce Retail Data Pipeline."""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
import pandas as pd

from src.config import (
    BASE_DIR,
    RAW_DATA_DIR,
    LOGS_DIR,
    PIPELINE_LOG_PATH,
    CUSTOMER_MASTER_PATH,
    RAW_EXCEL_PATH,
)
from src.database.connection import get_engine, init_database, get_active_db_type, execute_query
from src.ingestion.fetch_dataset import fetch_uci_dataset
from src.ingestion.generate_batches import generate_monthly_batches
from src.ingestion.enrich_customers import generate_synthetic_customer_master
from src.etl.extract import extract_raw_batch, extract_full_dataset
from src.etl.quality_checks import validate_batch, run_data_quality_audit
from src.etl.transform import clean_and_transform_batch
from src.etl.load import load_batch_into_warehouse
from src.models.star_schema import (
    build_dim_date,
    build_dim_customer,
    build_dim_product,
    build_dim_geography,
    build_fact_sales,
    build_fact_customer_retention,
)
from src.models.marts import build_mart_sales_performance, build_mart_customer_rfm

# Configure file and console logging
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PIPELINE_LOG_PATH, mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("RetailPipeline")


def run_pipeline(mode: str = "full", limit: int = None, force_sqlite: bool = False) -> dict:
    """Executes the complete retail data engineering pipeline end-to-end."""
    start_time = time.time()
    logger.info("=" * 80)
    logger.info("STARTING E-COMMERCE ETL PIPELINE EXECUTION")
    logger.info("Execution Mode: %s | Row Limit: %s | Timestamp: %s", mode, limit, datetime.utcnow().isoformat())
    logger.info("=" * 80)

    # Step 0: Database Initialization
    engine = get_engine(force_sqlite=force_sqlite)
    init_database(engine)
    db_type = get_active_db_type()
    logger.info("Connected to Target Data Warehouse: [%s]", db_type.upper())

    # Step 1: Data Acquisition
    logger.info("[STEP 1/7] Ingesting Primary Dataset (UCI Online Retail)...")
    raw_dataset_path = fetch_uci_dataset()
    logger.info("Primary dataset ready at %s", raw_dataset_path)

    # Step 2: Synthetic Customer Master Generation
    logger.info("[STEP 2/7] Generating Synthetic Customer Demographics & Loyalty Master...")
    df_cust_master = generate_synthetic_customer_master()

    # Step 3: Incremental Batch Partitioning
    logger.info("[STEP 3/7] Generating Monthly Incremental Batch Partitions...")
    batches = generate_monthly_batches()
    logger.info("Generated %d monthly batch files for incremental processing.", len(batches))

    # Step 4: Extraction & Raw Staging
    logger.info("[STEP 4/7] Extracting Raw Data...")
    if mode == "incremental" and batches:
        # Pick the latest monthly batch for demonstration
        target_batch = batches[-1]
        raw_df, extract_meta = extract_raw_batch(Path(target_batch["filepath"]), target_batch["batch_id"])
    else:
        raw_df, extract_meta = extract_full_dataset()

    if limit and limit > 0:
        logger.info("Applying test limit: keeping first %d rows...", limit)
        raw_df = raw_df.head(limit)
        extract_meta["raw_row_count"] = len(raw_df)

    # Step 5: Data Quality Validation & Error Logging
    logger.info("[STEP 5/7] Executing Data Quality Checks & Error Handling...")
    clean_df, rejected_records, quality_summary = validate_batch(raw_df, batch_id=extract_meta["batch_id"])

    # Step 6: Transformation, Cleansing & Dimensional Modeling
    logger.info("[STEP 6/7] Transforming Data & Building Star Schema...")
    transformed_df = clean_and_transform_batch(clean_df, batch_id=extract_meta["batch_id"])

    # Dimensions
    min_date = str(transformed_df["InvoiceDate"].min().date())
    max_date = str(transformed_df["InvoiceDate"].max().date())
    df_dim_date = build_dim_date(min_date_str=min_date, max_date_str=max_date)
    df_dim_cust = build_dim_customer(transformed_df, df_cust_master)
    df_dim_prod = build_dim_product(transformed_df)
    df_dim_geo = build_dim_geography(transformed_df)

    # Fact Tables
    df_fact_sales = build_fact_sales(transformed_df, df_dim_cust, df_dim_prod, df_dim_geo)
    df_fact_ret = build_fact_customer_retention(transformed_df, df_dim_cust)

    # Analytical Marts
    logger.info("Computing Analytical Data Marts (Sales Performance & Customer RFM)...")
    df_mart_sales = build_mart_sales_performance(df_fact_sales, df_dim_date, df_dim_geo)
    df_mart_rfm = build_mart_customer_rfm(df_fact_sales, df_dim_cust)

    # Step 7: Warehouse Loading & Verification
    logger.info("[STEP 7/7] Loading Star Schema and Analytical Marts into Data Warehouse...")
    duration = round(time.time() - start_time, 2)
    extract_meta["duration_sec"] = duration

    loaded_counts = load_batch_into_warehouse(
        df_dim_date=df_dim_date,
        df_dim_cust=df_dim_cust,
        df_dim_prod=df_dim_prod,
        df_dim_geo=df_dim_geo,
        df_fact_sales=df_fact_sales,
        df_fact_ret=df_fact_ret,
        df_mart_sales=df_mart_sales,
        df_mart_rfm=df_mart_rfm,
        audit_metadata=extract_meta,
        rejected_records=rejected_records,
    )

    # Print Summary Scorecard
    logger.info("=" * 80)
    logger.info("PIPELINE EXECUTION COMPLETED SUCCESSFULLY IN %.2f SECONDS", duration)
    logger.info("Warehouse Engine: %s", db_type.upper())
    logger.info("Total Raw Records Processed: %d", extract_meta["raw_row_count"])
    logger.info("Data Quality Pass Rate: %.2f%% (%d valid, %d rejected)", quality_summary["pass_rate_pct"], len(clean_df), len(rejected_records))
    logger.info("Warehouse Tables Populated:")
    for tbl, count in loaded_counts.items():
        logger.info("  - %-25s : %8d rows", tbl, count)
    logger.info("=" * 80)

    return {
        "status": "SUCCESS",
        "duration_sec": duration,
        "database": db_type,
        "raw_records": extract_meta["raw_row_count"],
        "clean_records": len(clean_df),
        "rejected_records": len(rejected_records),
        "pass_rate_pct": quality_summary["pass_rate_pct"],
        "table_counts": loaded_counts,
    }


def main():
    parser = argparse.ArgumentParser(description="E-Commerce Retail Pipeline Runner")
    parser.add_argument("--mode", choices=["full", "incremental", "sample"], default="full", help="Pipeline execution mode")
    parser.add_argument("--limit", type=int, default=None, help="Optional record limit for testing")
    parser.add_argument("--force-sqlite", action="store_true", help="Force SQLite storage engine")
    args = parser.parse_args()

    try:
        run_pipeline(mode=args.mode, limit=args.limit, force_sqlite=args.force_sqlite)
    except Exception as e:
        logger.exception("Pipeline execution failed with error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
