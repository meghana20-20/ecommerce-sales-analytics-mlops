"""Star Schema builders: Dimensions (Customer, Product, Geography, Date) and Fact tables (Sales, Retention)."""

import logging
from typing import Dict, Tuple
import numpy as np
import pandas as pd

from src.config import GUEST_CUSTOMER_ID, GUEST_CUSTOMER_CODE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def infer_product_category(desc: str) -> str:
    """Categorizes retail products using description heuristics."""
    d = str(desc).upper()
    if any(w in d for w in ["HEART", "CHRISTMAS", "XMAS", "STAR", "LIGHT", "CANDLE", "TREE", "FESTIVE", "DECORATION"]):
        return "Seasonal & Festive"
    if any(w in d for w in ["MUG", "CUP", "PLATE", "BOWL", "TEA", "COFFEE", "BAKING", "CUTLERY", "KITCHEN", "JAR", "BOTTLE"]):
        return "Kitchen & Dining"
    if any(w in d for w in ["BAG", "TOTE", "PURSE", "WALLET", "LUGGAGE", "TRAVEL"]):
        return "Bags & Travel"
    if any(w in d for w in ["PEN", "NOTEBOOK", "PENCIL", "CARD", "STICKER", "PAPER", "STATIONERY"]):
        return "Stationery & Office"
    if any(w in d for w in ["BOX", "CLOCK", "FRAME", "MIRROR", "CUSHION", "SIGN", "LANTERN", "DOORSTOP"]):
        return "Home Decor & Furnishing"
    if any(w in d for w in ["TOY", "GAME", "DOLL", "PUZZLE", "CHILD"]):
        return "Toys & Children"
    return "Gifts & Accessories"


def infer_geography_region(country: str) -> Tuple[str, str]:
    """Maps country to global sales region and market tier."""
    c = str(country).strip().title()
    if c in ["United Kingdom", "Uk"]:
        return "Domestic UK", "Tier 1 - Domestic"
    if c in ["Germany", "France", "Eire", "Ireland", "Netherlands", "Belgium", "Switzerland", "Austria"]:
        return "Western Europe", "Tier 2 - Core Europe"
    if c in ["Spain", "Portugal", "Italy", "Greece", "Cyprus", "Malta"]:
        return "Southern Europe", "Tier 2 - Core Europe"
    if c in ["Norway", "Sweden", "Finland", "Denmark", "Iceland"]:
        return "Nordics", "Tier 2 - Core Europe"
    if c in ["Poland", "Czech Republic", "Lithuania", "European Community"]:
        return "Eastern Europe", "Tier 3 - Extended EU"
    if c in ["Usa", "United States", "Canada"]:
        return "North America", "Tier 3 - International"
    if c in ["Australia", "Japan", "Singapore", "Hong Kong"]:
        return "Asia-Pacific", "Tier 3 - International"
    if c in ["United Arab Emirates", "Saudi Arabia", "Bahrain", "Israel", "Lebanon"]:
        return "Middle East", "Tier 3 - International"
    if c in ["Rsa", "South Africa", "Nigeria"]:
        return "Africa", "Tier 3 - International"
    if c in ["Brazil", "Argentina"]:
        return "Latin America", "Tier 3 - International"
    return "Other / Overseas", "Tier 3 - International"


def build_dim_date(min_date_str: str = "2009-12-01", max_date_str: str = "2012-01-31") -> pd.DataFrame:
    """Generates continuous calendar dimension table."""
    logger.info("Generating dim_date dimension from %s to %s...", min_date_str, max_date_str)
    date_range = pd.date_range(start=min_date_str, end=max_date_str, freq="D")
    
    df_date = pd.DataFrame({"full_date": date_range.date})
    df_date["date_key"] = date_range.strftime("%Y%m%d").astype(int)
    df_date["year"] = date_range.year
    df_date["quarter"] = date_range.quarter
    df_date["month"] = date_range.month
    df_date["month_name"] = date_range.strftime("%B")
    df_date["day"] = date_range.day
    df_date["day_of_week"] = date_range.dayofweek + 1 # 1 = Monday, 7 = Sunday
    df_date["day_name"] = date_range.strftime("%A")
    df_date["is_weekend"] = date_range.dayofweek >= 5

    cols = ["date_key", "full_date", "year", "quarter", "month", "month_name", "day", "day_of_week", "day_name", "is_weekend"]
    return df_date[cols]


def build_dim_customer(df_trans: pd.DataFrame, df_cust_master: pd.DataFrame) -> pd.DataFrame:
    """Builds dim_customer combining transaction references with customer master profiles."""
    logger.info("Building dim_customer dimension...")
    trans_cust_ids = set(df_trans["customer_id"].dropna().unique())
    master_cust_ids = set(df_cust_master["customer_id"].unique()) if not df_cust_master.empty else set()
    all_cust_ids = sorted(list(trans_cust_ids.union(master_cust_ids)))

    df_base = pd.DataFrame({"customer_id": all_cust_ids})

    if not df_cust_master.empty:
        merged = pd.merge(df_base, df_cust_master, on="customer_id", how="left")
    else:
        merged = df_base.copy()
        merged["gender"] = "Unknown"
        merged["age_group"] = "Unknown"
        merged["loyalty_tier"] = "Bronze"
        merged["signup_date"] = pd.to_datetime("2010-01-01").date()
        merged["preferred_device"] = "Desktop Web"
        merged["country"] = "United Kingdom"
        merged["customer_code"] = merged["customer_id"].apply(lambda x: GUEST_CUSTOMER_CODE if x == GUEST_CUSTOMER_ID else f"CUST_{x}")

    # Set guest customer default attributes
    guest_mask = merged["customer_id"] == GUEST_CUSTOMER_ID
    merged.loc[guest_mask, "customer_code"] = GUEST_CUSTOMER_CODE
    merged.loc[guest_mask, "gender"] = "Unknown"
    merged.loc[guest_mask, "age_group"] = "Unknown"
    merged.loc[guest_mask, "loyalty_tier"] = "None"
    merged.loc[guest_mask, "preferred_device"] = "Guest Checkout"

    # Fill missing values
    merged["gender"] = merged["gender"].fillna("Unknown")
    merged["age_group"] = merged["age_group"].fillna("Unknown")
    merged["loyalty_tier"] = merged["loyalty_tier"].fillna("Bronze")
    merged["preferred_device"] = merged["preferred_device"].fillna("Desktop Web")
    merged["customer_code"] = merged["customer_code"].fillna(merged["customer_id"].apply(lambda x: f"CUST_{x}"))

    # Surrogate key
    merged.reset_index(drop=True, inplace=True)
    merged["customer_key"] = merged.index + 1

    cols = ["customer_key", "customer_id", "customer_code", "gender", "age_group", "loyalty_tier", "signup_date", "preferred_device", "country"]
    logger.info("dim_customer built successfully with %d entries.", len(merged))
    return merged[cols]


def build_dim_product(df_trans: pd.DataFrame) -> pd.DataFrame:
    """Builds dim_product dimension from transaction records."""
    logger.info("Building dim_product dimension...")
    grouped = df_trans.groupby("StockCode").agg(
        description=("Description", "first"),
        unit_price_nominal=("UnitPrice", "median")
    ).reset_index()

    grouped.rename(columns={"StockCode": "stock_code"}, inplace=True)
    grouped["category"] = grouped["description"].apply(infer_product_category)
    grouped["unit_price_nominal"] = grouped["unit_price_nominal"].round(2)

    grouped.reset_index(drop=True, inplace=True)
    grouped["product_key"] = grouped.index + 1

    cols = ["product_key", "stock_code", "description", "category", "unit_price_nominal"]
    logger.info("dim_product built successfully with %d unique products.", len(grouped))
    return grouped[cols]


def build_dim_geography(df_trans: pd.DataFrame) -> pd.DataFrame:
    """Builds dim_geography dimension from transaction records."""
    logger.info("Building dim_geography dimension...")
    countries = sorted(df_trans["Country"].dropna().unique())
    geo_list = []
    for idx, c in enumerate(countries, start=1):
        region, tier = infer_geography_region(c)
        geo_list.append({
            "geography_key": idx,
            "country_name": c,
            "region": region,
            "market_tier": tier
        })
    df_geo = pd.DataFrame(geo_list)
    logger.info("dim_geography built successfully with %d countries.", len(df_geo))
    return df_geo


def build_fact_sales(
    df_trans: pd.DataFrame,
    df_dim_cust: pd.DataFrame,
    df_dim_prod: pd.DataFrame,
    df_dim_geo: pd.DataFrame,
) -> pd.DataFrame:
    """Constructs fact_sales table linking transactions to dimension surrogate keys."""
    logger.info("Assembling fact_sales table from %d transactions...", len(df_trans))
    df = df_trans.copy()

    # Map foreign keys
    cust_map = dict(zip(df_dim_cust["customer_id"], df_dim_cust["customer_key"]))
    prod_map = dict(zip(df_dim_prod["stock_code"], df_dim_prod["product_key"]))
    geo_map = dict(zip(df_dim_geo["country_name"], df_dim_geo["geography_key"]))

    default_cust_key = cust_map.get(GUEST_CUSTOMER_ID, 1)
    df["customer_key"] = df["customer_id"].map(cust_map).fillna(default_cust_key).astype(int)
    df["product_key"] = df["StockCode"].map(prod_map).fillna(1).astype(int)
    df["geography_key"] = df["Country"].map(geo_map).fillna(1).astype(int)

    # Date key is already YYYYMMDD
    df["invoice_timestamp"] = df["InvoiceDate"]

    df.reset_index(drop=True, inplace=True)
    df["sales_key"] = df.index + 1

    fact = pd.DataFrame({
        "sales_key": df["sales_key"],
        "invoice_no": df["InvoiceNo"],
        "customer_key": df["customer_key"],
        "product_key": df["product_key"],
        "geography_key": df["geography_key"],
        "date_key": df["date_key"],
        "invoice_timestamp": df["invoice_timestamp"],
        "quantity": df["Quantity"],
        "unit_price": df["UnitPrice"],
        "total_amount": df["total_amount"],
        "is_cancelled": df["is_cancelled"],
        "batch_id": df.get("batch_id", "historical")
    })
    logger.info("fact_sales assembled successfully with %d rows.", len(fact))
    return fact


def build_fact_customer_retention(
    df_trans: pd.DataFrame,
    df_dim_cust: pd.DataFrame
) -> pd.DataFrame:
    """Builds fact_customer_retention tracking cohort lifecycle and purchase sequence."""
    logger.info("Building fact_customer_retention for repeat-purchase analysis...")
    # Filter registered customers with valid purchases (exclude guest 0 and cancellations for retention)
    reg_orders = df_trans[
        (df_trans["customer_id"] != GUEST_CUSTOMER_ID) &
        (~df_trans["is_cancelled"]) &
        (df_trans["total_amount"] > 0)
    ].copy()

    if reg_orders.empty:
        logger.warning("No valid registered customer orders found for retention table.")
        return pd.DataFrame()

    # Aggregate by Invoice level
    order_agg = reg_orders.groupby(["customer_id", "InvoiceNo", "date_key"]).agg(
        order_date=("InvoiceDate", "min"),
        order_value=("total_amount", "sum")
    ).reset_index()

    order_agg.sort_values(by=["customer_id", "order_date"], inplace=True)

    # Determine first purchase (cohort)
    cust_first_order = order_agg.groupby("customer_id")["order_date"].min().reset_index()
    cust_first_order["cohort_month"] = cust_first_order["order_date"].dt.strftime("%Y-%m")
    cohort_map = dict(zip(cust_first_order["customer_id"], cust_first_order["cohort_month"]))
    order_agg["cohort_month"] = order_agg["customer_id"].map(cohort_map)

    # Order sequence number (1st, 2nd, 3rd order)
    order_agg["order_sequence"] = order_agg.groupby("customer_id").cumcount() + 1

    # Days since prior purchase
    order_agg["prev_order_date"] = order_agg.groupby("customer_id")["order_date"].shift(1)
    order_agg["days_since_prior_order"] = (order_agg["order_date"] - order_agg["prev_order_date"]).dt.days
    order_agg["days_since_prior_order"] = order_agg["days_since_prior_order"].fillna(0).astype(int)

    order_agg["is_repeat_customer"] = order_agg["order_sequence"] > 1

    # Map customer surrogate key
    cust_map = dict(zip(df_dim_cust["customer_id"], df_dim_cust["customer_key"]))
    order_agg["customer_key"] = order_agg["customer_id"].map(cust_map).fillna(1).astype(int)

    order_agg.reset_index(drop=True, inplace=True)
    order_agg["retention_key"] = order_agg.index + 1
    order_agg["order_value"] = order_agg["order_value"].round(2)

    cols = [
        "retention_key", "customer_key", "date_key", "cohort_month",
        "order_sequence", "days_since_prior_order", "order_value", "is_repeat_customer"
    ]
    logger.info("fact_customer_retention built successfully with %d order records.", len(order_agg))
    return order_agg[cols]
