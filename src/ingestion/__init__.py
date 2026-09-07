"""Ingestion module for raw dataset acquisition, batch generation, and customer enrichment."""
from .fetch_dataset import fetch_uci_dataset
from .generate_batches import generate_monthly_batches
from .enrich_customers import generate_synthetic_customer_master

__all__ = [
    "fetch_uci_dataset",
    "generate_monthly_batches",
    "generate_synthetic_customer_master",
]
