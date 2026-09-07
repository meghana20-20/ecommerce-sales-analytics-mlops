"""Generates a synthetic customer demographic and loyalty master dataset for enrichment."""

import logging
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd

from src.config import CUSTOMER_MASTER_PATH, RAW_DATA_DIR, GUEST_CUSTOMER_ID, GUEST_CUSTOMER_CODE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def generate_synthetic_customer_master(
    customer_ids: Optional[list] = None,
    output_path: Path = CUSTOMER_MASTER_PATH,
    seed: int = 42
) -> pd.DataFrame:
    """Generates synthetic customer demographic and loyalty profile attributes.
    
    This fulfills the optional customer enrichment requirement specified in the project guidelines,
    providing critical dimensions for demographic segmentation, retention modeling, and churn prediction.
    """
    np.random.seed(seed)

    if customer_ids is None:
        raw_parquet_path = RAW_DATA_DIR / "online_retail_raw.parquet"
        if raw_parquet_path.exists():
            df_raw = pd.read_parquet(raw_parquet_path, columns=["CustomerID", "Country"])
            cust_series = df_raw.dropna(subset=["CustomerID"])
            cust_country_map = cust_series.groupby("CustomerID")["Country"].agg(lambda x: x.mode()[0] if not x.empty else "United Kingdom").to_dict()
            unique_ids = sorted(df_raw["CustomerID"].dropna().astype(int).unique())
        else:
            unique_ids = list(range(12000, 18500))
            cust_country_map = {cid: "United Kingdom" for cid in unique_ids}
    else:
        unique_ids = sorted(list(set(customer_ids)))
        cust_country_map = {cid: "United Kingdom" for cid in unique_ids}

    # Ensure guest customer is included
    all_ids = [GUEST_CUSTOMER_ID] + [cid for cid in unique_ids if cid != GUEST_CUSTOMER_ID]
    n_customers = len(all_ids)
    logger.info("Generating synthetic profile data for %d customers...", n_customers)

    genders = np.random.choice(["Female", "Male", "Non-Binary"], size=n_customers, p=[0.52, 0.45, 0.03])
    age_groups = np.random.choice(
        ["18-25", "26-35", "36-50", "51-65", "65+"],
        size=n_customers,
        p=[0.15, 0.35, 0.30, 0.15, 0.05]
    )
    loyalty_tiers = np.random.choice(
        ["Bronze", "Silver", "Gold", "Platinum"],
        size=n_customers,
        p=[0.45, 0.30, 0.18, 0.07]
    )
    preferred_devices = np.random.choice(
        ["Mobile App", "Desktop Web", "Mobile Web", "Tablet"],
        size=n_customers,
        p=[0.45, 0.35, 0.15, 0.05]
    )

    # Generate random signup dates between 2009-01-01 and 2011-10-31
    base_timestamp = pd.Timestamp("2009-01-01").value // 10**9
    end_timestamp = pd.Timestamp("2011-10-31").value // 10**9
    random_seconds = np.random.randint(base_timestamp, end_timestamp, size=n_customers)
    signup_dates = pd.to_datetime(random_seconds, unit="s").date

    countries = [
        "United Kingdom" if cid == GUEST_CUSTOMER_ID else cust_country_map.get(cid, "United Kingdom")
        for cid in all_ids
    ]
    customer_codes = [
        GUEST_CUSTOMER_CODE if cid == GUEST_CUSTOMER_ID else f"CUST_{cid}"
        for cid in all_ids
    ]

    master_df = pd.DataFrame({
        "customer_id": all_ids,
        "customer_code": customer_codes,
        "gender": genders,
        "age_group": age_groups,
        "loyalty_tier": loyalty_tiers,
        "signup_date": signup_dates,
        "preferred_device": preferred_devices,
        "country": countries
    })

    # Set guest row specific attributes
    guest_idx = master_df["customer_id"] == GUEST_CUSTOMER_ID
    master_df.loc[guest_idx, "gender"] = "Unknown"
    master_df.loc[guest_idx, "age_group"] = "Unknown"
    master_df.loc[guest_idx, "loyalty_tier"] = "None"
    master_df.loc[guest_idx, "preferred_device"] = "Guest Checkout"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    master_df.to_csv(output_path, index=False)
    logger.info("Synthetic customer master saved to %s (%d records).", output_path, len(master_df))
    return master_df


if __name__ == "__main__":
    generate_synthetic_customer_master()
