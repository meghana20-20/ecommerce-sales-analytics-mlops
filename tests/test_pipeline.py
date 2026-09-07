"""Unit and integration tests for E-Commerce Retail Pipeline and Data Quality Framework."""

import pytest
import pandas as pd
import numpy as np

from src.database.connection import get_engine, init_database, execute_query
from src.etl.quality_checks import validate_batch
from src.etl.transform import clean_and_transform_batch
from src.models.marts import assign_rfm_segment
from src.models.star_schema import infer_product_category, infer_geography_region


def test_schema_tables_exist():
    """Verifies that all star schema tables, marts, and audit logs exist in the warehouse."""
    engine = get_engine(force_sqlite=True)
    init_database(engine)
    
    tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables_df = execute_query(tables_query)
    table_names = set(tables_df["name"].tolist())

    expected_tables = {
        "dim_customer",
        "dim_product",
        "dim_geography",
        "dim_date",
        "fact_sales",
        "fact_customer_retention",
        "mart_sales_performance",
        "mart_customer_rfm",
        "etl_audit_log",
        "etl_rejection_log",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"


def test_quality_checks_quarantine_invalid_records():
    """Verifies that negative non-cancelled quantities and zero prices are rejected."""
    raw_sample = pd.DataFrame({
        "InvoiceNo": ["536365", "C536366", "536367", "536368", ""],
        "StockCode": ["85123A", "71053", "22423", "84029E", "84029G"],
        "Description": ["Candle", "Cup", "Plate", "Napkin", "Bowl"],
        "Quantity": [10, -2, -5, 0, 4], # 536367 is negative non-cancellation (reject), 536368 is 0 (reject), '' is empty invoice
        "InvoiceDate": ["2010-12-01 08:26:00"] * 5,
        "UnitPrice": [2.55, 3.39, 1.25, 0.0, 4.50],
        "CustomerID": [17850, 17850, 13047, 13047, 12000],
        "Country": ["United Kingdom"] * 5,
    })

    clean_df, rejected_df, summary = validate_batch(raw_sample, batch_id="test_unit_batch")
    
    # 536365 (valid) and C536366 (valid cancellation) should pass
    assert len(clean_df) == 2
    assert len(rejected_df) == 3
    rejection_reasons = rejected_df["rejection_reason"].tolist()
    assert "INVALID_OR_ZERO_QUANTITY" in rejection_reasons
    assert "NULL_OR_EMPTY_INVOICE_NO" in rejection_reasons


def test_transformation_deduplication():
    """Verifies exact duplicate transaction removal and cancellation flag assignment."""
    clean_sample = pd.DataFrame({
        "InvoiceNo": ["536365", "536365", "C536366"],
        "StockCode": ["85123A", "85123A", "71053"],
        "Description": ["Candle", "Candle", "Cup"],
        "Quantity": [10, 10, -2],
        "InvoiceDate": ["2010-12-01 08:26:00", "2010-12-01 08:26:00", "2010-12-01 08:30:00"],
        "UnitPrice": [2.55, 2.55, 3.39],
        "CustomerID": [17850, 17850, 17850],
        "Country": ["United Kingdom", "United Kingdom", "United Kingdom"],
    })

    transformed = clean_and_transform_batch(clean_sample, batch_id="test_dedup")
    assert len(transformed) == 2 # 1 duplicate dropped
    cancellation_row = transformed[transformed["InvoiceNo"] == "C536366"].iloc[0]
    assert cancellation_row["is_cancelled"] == True
    assert cancellation_row["total_amount"] == -6.78


def test_rfm_segment_assignment():
    """Verifies business classification of RFM score combinations."""
    assert assign_rfm_segment(5, 5, 5) == "Champions"
    assert assign_rfm_segment(4, 4, 4) == "Champions"
    assert assign_rfm_segment(4, 4, 3) == "Loyal Customers"
    assert assign_rfm_segment(2, 4, 4) == "At Risk - Needs Attention"
    assert assign_rfm_segment(1, 1, 1) == "Lost Customers"
    assert assign_rfm_segment(4, 1, 2) == "New / Potential Loyalists"


def test_category_and_geography_inferences():
    """Verifies merchandise categorizer and geographic territory mapping."""
    cat1 = infer_product_category("VINTAGE CHRISTMAS TREE HANGER")
    assert cat1 == "Seasonal & Festive"
    
    cat2 = infer_product_category("CERAMIC COFFEE MUG WITH SPOON")
    assert cat2 == "Kitchen & Dining"

    region_uk, tier_uk = infer_geography_region("United Kingdom")
    assert region_uk == "Domestic UK"
    assert tier_uk == "Tier 1 - Domestic"

    region_de, tier_de = infer_geography_region("Germany")
    assert region_de == "Western Europe"
    assert tier_de == "Tier 2 - Core Europe"


def test_airflow_dag_integrity():
    """Verifies that the Airflow DAG loads with correct task counts and structure."""
    from dags.retail_etl_dag import dag
    assert dag is not None
    assert dag.dag_id == "ecommerce_retail_sales_etl_pipeline"
    assert len(dag.tasks) >= 7
