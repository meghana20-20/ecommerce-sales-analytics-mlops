"""Database Loader: persists dimension tables, fact tables, marts, and audit trails."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict
import pandas as pd
from sqlalchemy import text

from src.database.connection import get_engine, init_database
from src.config import EXPORTS_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def export_sample_tables(tables: Dict[str, pd.DataFrame]) -> None:
    """Exports sample records (first 100 rows) of each populated warehouse table for verification."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Exporting table snapshots to %s...", EXPORTS_DIR)
    for table_name, df in tables.items():
        if df is not None and not df.empty:
            export_path = EXPORTS_DIR / f"{table_name}_sample.csv"
            df.head(100).to_csv(export_path, index=False)
            logger.info("Saved sample of [%s] (%d rows) to %s", table_name, min(100, len(df)), export_path.name)


def load_batch_into_warehouse(
    df_dim_date: pd.DataFrame,
    df_dim_cust: pd.DataFrame,
    df_dim_prod: pd.DataFrame,
    df_dim_geo: pd.DataFrame,
    df_fact_sales: pd.DataFrame,
    df_fact_ret: pd.DataFrame,
    df_mart_sales: pd.DataFrame,
    df_mart_rfm: pd.DataFrame,
    audit_metadata: Dict,
    rejected_records: pd.DataFrame,
) -> Dict[str, int]:
    """Persists all transformed entities and analytical marts into the warehouse tables."""
    engine = get_engine()
    init_database(engine)

    logger.info("Loading warehouse tables...")
    counts = {}

    # Replace / Upsert tables
    tables_to_load = [
        ("dim_date", df_dim_date, "replace"),
        ("dim_customer", df_dim_cust, "replace"),
        ("dim_product", df_dim_prod, "replace"),
        ("dim_geography", df_dim_geo, "replace"),
        ("fact_sales", df_fact_sales, "replace"),
        ("fact_customer_retention", df_fact_ret, "replace"),
        ("mart_sales_performance", df_mart_sales, "replace"),
        ("mart_customer_rfm", df_mart_rfm, "replace"),
    ]

    with engine.begin() as conn:
        for table_name, df_table, if_exists_mode in tables_to_load:
            if df_table is not None and not df_table.empty:
                logger.info("Loading table [%s] (%d rows)...", table_name, len(df_table))
                df_table.to_sql(table_name, conn, if_exists=if_exists_mode, index=False)
                counts[table_name] = len(df_table)
            else:
                counts[table_name] = 0

    # Persist audit record
    audit_row = pd.DataFrame([{
        "audit_id": int(datetime.utcnow().timestamp()),
        "batch_id": audit_metadata.get("batch_id", "default"),
        "source_file": audit_metadata.get("source_file", "unknown"),
        "extraction_timestamp": pd.to_datetime(audit_metadata.get("extraction_timestamp", datetime.utcnow().isoformat())),
        "raw_row_count": audit_metadata.get("raw_row_count", 0),
        "cleaned_row_count": len(df_fact_sales) if df_fact_sales is not None else 0,
        "rejected_row_count": len(rejected_records) if rejected_records is not None else 0,
        "status": "COMPLETED",
        "execution_duration_sec": audit_metadata.get("duration_sec", 0.0),
        "notes": f"Successfully loaded {counts.get('fact_sales', 0)} sales and {counts.get('mart_customer_rfm', 0)} customer RFM profiles.",
    }])
    with engine.begin() as conn:
        audit_row.to_sql("etl_audit_log", conn, if_exists="append", index=False)

    # Persist sample rejected records into rejection log table
    if rejected_records is not None and not rejected_records.empty:
        rejection_rows = rejected_records.head(500).copy()
        rejection_rows.rename(columns={
            "InvoiceNo": "invoice_no",
            "StockCode": "stock_code",
            "Quantity": "quantity",
            "UnitPrice": "unit_price",
            "CustomerID": "customer_id",
        }, inplace=True)
        target_cols = [
            "batch_id", "invoice_no", "stock_code", "quantity",
            "unit_price", "customer_id", "rejection_reason", "logged_at"
        ]
        rejection_rows = rejection_rows[[c for c in target_cols if c in rejection_rows.columns]]
        rejection_rows["logged_at"] = pd.to_datetime(rejection_rows["logged_at"])
        with engine.begin() as conn:
            rejection_rows.to_sql("etl_rejection_log", conn, if_exists="append", index=False)

    # Export sample snapshot CSVs for project submission verification
    export_sample_tables({
        "dim_customer": df_dim_cust,
        "dim_product": df_dim_prod,
        "dim_geography": df_dim_geo,
        "dim_date": df_dim_date,
        "fact_sales": df_fact_sales,
        "fact_customer_retention": df_fact_ret,
        "mart_sales_performance": df_mart_sales,
        "mart_customer_rfm": df_mart_rfm,
    })

    logger.info("Warehouse loading complete. Row count summary: %s", counts)
    return counts
