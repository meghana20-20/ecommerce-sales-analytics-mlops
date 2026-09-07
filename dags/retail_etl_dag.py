"""Apache Airflow Orchestration DAG for E-Commerce Retail Data Warehouse & Marts."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to python path for task operators
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Airflow imports with resilient standalone execution wrapper
try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    from airflow.operators.empty import EmptyOperator
except (ImportError, Exception):
    class DAG:
        def __init__(self, dag_id, *args, **kwargs):
            self.dag_id = dag_id
            self.tasks = []

    class BaseOperatorMock:
        def __init__(self, task_id, *args, **kwargs):
            self.task_id = task_id
            if "dag" in kwargs and kwargs["dag"] is not None:
                kwargs["dag"].tasks.append(self)
        def __rshift__(self, other):
            return other
        def __lshift__(self, other):
            return other

    PythonOperator = BaseOperatorMock
    EmptyOperator = BaseOperatorMock

from src.ingestion.fetch_dataset import fetch_uci_dataset
from src.ingestion.generate_batches import generate_monthly_batches
from src.ingestion.enrich_customers import generate_synthetic_customer_master
from src.etl.extract import extract_full_dataset
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
from src.database.connection import get_engine, init_database


# Task Execution Callables
def etl_task_ingest_raw(**context):
    print("Airflow Task: Ingesting UCI Online Retail Dataset...")
    path = fetch_uci_dataset()
    return str(path)


def etl_task_generate_demographics(**context):
    print("Airflow Task: Generating Synthetic Customer Demographics...")
    df = generate_synthetic_customer_master()
    return len(df)


def etl_task_partition_batches(**context):
    print("Airflow Task: Partitioning Monthly Incremental Batches...")
    batches = generate_monthly_batches()
    return len(batches)


def etl_task_extract_and_validate(**context):
    print("Airflow Task: Extracting and Validating Raw Transactions...")
    raw_df, meta = extract_full_dataset()
    clean_df, rejected_df, summary = validate_batch(raw_df, batch_id=meta["batch_id"])
    print(f"Extraction complete: {len(clean_df)} clean, {len(rejected_df)} rejected.")
    return {"clean_count": len(clean_df), "rejected_count": len(rejected_df)}


def etl_task_transform_and_load(**context):
    print("Airflow Task: Transforming Data, Building Star Schema and Marts...")
    raw_df, meta = extract_full_dataset()
    cust_master = generate_synthetic_customer_master()
    clean_df, rejected_df, _ = validate_batch(raw_df, batch_id=meta["batch_id"])
    transformed_df = clean_and_transform_batch(clean_df, batch_id=meta["batch_id"])

    # Build dimensions
    min_date = str(transformed_df["InvoiceDate"].min().date())
    max_date = str(transformed_df["InvoiceDate"].max().date())
    dim_date = build_dim_date(min_date, max_date)
    dim_cust = build_dim_customer(transformed_df, cust_master)
    dim_prod = build_dim_product(transformed_df)
    dim_geo = build_dim_geography(transformed_df)

    # Build facts & marts
    fact_sales = build_fact_sales(transformed_df, dim_cust, dim_prod, dim_geo)
    fact_ret = build_fact_customer_retention(transformed_df, dim_cust)
    mart_sales = build_mart_sales_performance(fact_sales, dim_date, dim_geo)
    mart_rfm = build_mart_customer_rfm(fact_sales, dim_cust)

    counts = load_batch_into_warehouse(
        df_dim_date=dim_date,
        df_dim_cust=dim_cust,
        df_dim_prod=dim_prod,
        df_dim_geo=dim_geo,
        df_fact_sales=fact_sales,
        df_fact_ret=fact_ret,
        df_mart_sales=mart_sales,
        df_mart_rfm=mart_rfm,
        audit_metadata=meta,
        rejected_records=rejected_df,
    )
    return counts


def etl_task_quality_audit(**context):
    print("Airflow Task: Running Post-Load Data Quality Audit...")
    summary = run_data_quality_audit()
    print("Quality Audit Summary:\n", summary)
    return summary.to_dict()


# DAG Specification
default_args = {
    "owner": "data_engineering_team",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    dag_id="ecommerce_retail_sales_etl_pipeline",
    default_args=default_args,
    description="Orchestrates E-Commerce ingestion, Star Schema modeling, and Mart generation",
    schedule_interval="@monthly",
    catchup=False,
    tags=["ecommerce", "retail", "etl", "star_schema", "rfm"],
)

# Airflow Task Definitions
start_task = EmptyOperator(task_id="start_pipeline", dag=dag)

t1_ingest_raw = PythonOperator(
    task_id="ingest_raw_dataset",
    python_callable=etl_task_ingest_raw,
    dag=dag,
)

t2_enrich_demographics = PythonOperator(
    task_id="enrich_customer_demographics",
    python_callable=etl_task_generate_demographics,
    dag=dag,
)

t3_partition_batches = PythonOperator(
    task_id="partition_monthly_batches",
    python_callable=etl_task_partition_batches,
    dag=dag,
)

t4_extract_and_validate = PythonOperator(
    task_id="extract_and_validate_data",
    python_callable=etl_task_extract_and_validate,
    dag=dag,
)

t5_transform_and_load = PythonOperator(
    task_id="transform_build_star_schema_and_load",
    python_callable=etl_task_transform_and_load,
    dag=dag,
)

t6_quality_audit = PythonOperator(
    task_id="run_quality_audit",
    python_callable=etl_task_quality_audit,
    dag=dag,
)

end_task = EmptyOperator(task_id="end_pipeline", dag=dag)

# Define Dependency Lineage
start_task >> t1_ingest_raw
t1_ingest_raw >> t2_enrich_demographics >> t4_extract_and_validate
t1_ingest_raw >> t3_partition_batches >> t4_extract_and_validate
t4_extract_and_validate >> t5_transform_and_load >> t6_quality_audit >> end_task
