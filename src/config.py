"""Centralized configuration and environment settings for E-Commerce Retail Pipeline."""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
STAGING_DATA_DIR = DATA_DIR / "staging"
REJECTED_DATA_DIR = DATA_DIR / "rejected"
WAREHOUSE_DIR = DATA_DIR / "warehouse"
EXPORTS_DIR = DATA_DIR / "exports"
LOGS_DIR = DATA_DIR / "logs"
DOCS_DIR = BASE_DIR / "docs"
SCREENSHOTS_DIR = DOCS_DIR / "screenshots"

# Ensure runtime directories exist
for directory in [
    DATA_DIR,
    RAW_DATA_DIR,
    STAGING_DATA_DIR,
    REJECTED_DATA_DIR,
    WAREHOUSE_DIR,
    EXPORTS_DIR,
    LOGS_DIR,
    DOCS_DIR,
    SCREENSHOTS_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

# Dataset URLs & Sources
UCI_DATASET_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
UCI_BACKUP_EXCEL_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/00352/Online%20Retail.xlsx"
RAW_EXCEL_FILENAME = "Online Retail.xlsx"
RAW_EXCEL_PATH = RAW_DATA_DIR / RAW_EXCEL_FILENAME
CUSTOMER_MASTER_PATH = RAW_DATA_DIR / "synthetic_customer_master.csv"

# Database Configuration
# Supports PostgreSQL with zero-config SQLite fallback for flexible deployment
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ecommerce_dw")

DEFAULT_SQLITE_URL = f"sqlite:///{WAREHOUSE_DIR}/ecommerce_dw.db"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# ETL Validation Rules & Boundaries
EXPECTED_COLUMNS = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]

MAX_QUANTITY_THRESHOLD = 50000
MIN_QUANTITY_VALID = 1
MIN_PRICE_VALID = 0.001
MAX_PRICE_THRESHOLD = 50000.0

# Guest / Anonymous Customer Key
GUEST_CUSTOMER_ID = 0
GUEST_CUSTOMER_CODE = "GUEST_UNREGISTERED"

# Ingestion Logging
AUDIT_LOG_PATH = LOGS_DIR / "ingestion_audit_log.json"
REJECTED_RECORDS_PATH = REJECTED_DATA_DIR / "rejected_records.csv"
PIPELINE_LOG_PATH = LOGS_DIR / "pipeline_execution.log"
