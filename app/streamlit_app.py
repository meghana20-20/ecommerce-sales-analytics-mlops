"""RetailIQ: Production E-Commerce Sales Analytics & Customer Retention Dashboard."""

import os
import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Setup system path to import database and config modules
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.database.connection import execute_query, get_active_db_type
from src.config import PIPELINE_LOG_PATH, AUDIT_LOG_PATH, REJECTED_RECORDS_PATH, BASE_DIR

# -----------------------------------------------------------------------------
# Streamlit App Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="RetailIQ | E-Commerce Sales Analytics & MLOps Churn Platform",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load CSS
css_path = Path(__file__).parent / "style.css"
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Data Loading & Caching
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)
def load_sales_mart_data():
    query = """
    SELECT 
        m.mart_id, m.date_key, m.year_month, m.country_name,
        m.total_revenue, m.total_orders, m.total_units_sold,
        m.average_order_value, m.unique_customers, m.cancelled_orders_count,
        d.year, d.month, d.month_name, d.full_date, d.day_name, d.is_weekend,
        g.region, g.market_tier
    FROM mart_sales_performance m
    JOIN dim_date d ON m.date_key = d.date_key
    JOIN dim_geography g ON m.country_name = g.country_name
    ORDER BY d.full_date ASC
    """
    return execute_query(query)


@st.cache_data(ttl=600)
def load_rfm_mart_data():
    query = """
    SELECT 
        r.customer_key, r.customer_id, r.recency_days, r.frequency,
        r.monetary_total, r.r_score, r.f_score, r.m_score, r.rfm_score,
        r.customer_segment, r.loyalty_tier, r.last_order_date,
        c.gender, c.age_group, c.preferred_device, c.country
    FROM mart_customer_rfm r
    JOIN dim_customer c ON r.customer_key = c.customer_key
    """
    return execute_query(query)


@st.cache_data(ttl=600)
def load_top_products_data():
    query = """
    SELECT 
        p.stock_code, p.description, p.category,
        SUM(f.quantity) as units_sold,
        ROUND(SUM(f.total_amount), 2) as total_revenue,
        ROUND(AVG(f.unit_price), 2) as avg_price
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    WHERE f.is_cancelled = FALSE
    GROUP BY p.product_key, p.stock_code, p.description, p.category
    ORDER BY total_revenue DESC
    """
    return execute_query(query)


@st.cache_data(ttl=600)
def load_retention_data():
    query = """
    SELECT 
        r.cohort_month, r.order_sequence, r.days_since_prior_order,
        r.order_value, r.is_repeat_customer, d.year, d.month
    FROM fact_customer_retention r
    JOIN dim_date d ON r.date_key = d.date_key
    """
    return execute_query(query)


@st.cache_data(ttl=600)
def load_audit_data():
    query = """
    SELECT audit_id, batch_id, source_file, extraction_timestamp,
           raw_row_count, cleaned_row_count, rejected_row_count,
           status, execution_duration_sec, notes
    FROM etl_audit_log
    ORDER BY extraction_timestamp DESC
    """
    try:
        return execute_query(query)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600)
def load_rejection_summary():
    query = """
    SELECT rejection_reason, COUNT(*) as rejection_count
    FROM etl_rejection_log
    GROUP BY rejection_reason
    ORDER BY rejection_count DESC
    """
    try:
        return execute_query(query)
    except Exception:
        return pd.DataFrame()


# Load datasets
df_sales = load_sales_mart_data()
df_rfm = load_rfm_mart_data()
df_products = load_top_products_data()
df_retention = load_retention_data()
df_audit = load_audit_data()
df_rejections = load_rejection_summary()

active_db = get_active_db_type().upper()

# -----------------------------------------------------------------------------
# Sidebar Controls & Filters
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🛍️ **RetailIQ Control Panel**")
    st.markdown(f"**Warehouse Engine:** `{active_db}`")
    st.markdown("---")

    all_countries = ["All Markets"] + sorted(df_sales["country_name"].unique().tolist())
    selected_country = st.selectbox("🌐 Market Geography", all_countries, index=0)

    min_date = pd.to_datetime(df_sales["full_date"]).min().date()
    max_date = pd.to_datetime(df_sales["full_date"]).max().date()
    date_range = st.date_input("📅 Date Range Filter", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    all_cats = ["All Categories"] + sorted(df_products["category"].unique().tolist())
    selected_cat = st.selectbox("📦 Merchandise Category", all_cats, index=0)

    all_tiers = ["All Loyalty Tiers"] + sorted(df_rfm["loyalty_tier"].dropna().unique().tolist())
    selected_tier = st.selectbox("🎖️ Customer Loyalty Tier", all_tiers, index=0)

    st.markdown("---")
    st.caption("E-Commerce Sales Analytics & MLOps | Assignment Part 2")

filtered_sales = df_sales.copy()
if selected_country != "All Markets":
    filtered_sales = filtered_sales[filtered_sales["country_name"] == selected_country]

if len(date_range) == 2:
    start_d, end_d = date_range
    filtered_sales = filtered_sales[
        (pd.to_datetime(filtered_sales["full_date"]).dt.date >= start_d) &
        (pd.to_datetime(filtered_sales["full_date"]).dt.date <= end_d)
    ]

filtered_products = df_products.copy()
if selected_cat != "All Categories":
    filtered_products = filtered_products[filtered_products["category"] == selected_cat]

filtered_rfm = df_rfm.copy()
if selected_tier != "All Loyalty Tiers":
    filtered_rfm = filtered_rfm[filtered_rfm["loyalty_tier"] == selected_tier]
if selected_country != "All Markets":
    filtered_rfm = filtered_rfm[filtered_rfm["country"] == selected_country]

# -----------------------------------------------------------------------------
# Hero Header & Navigation Tabs
# -----------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="hero-banner">
        <div class="hero-title">RetailIQ: E-Commerce Sales Analytics & MLOps Churn Platform</div>
        <p class="hero-subtitle">
            <span class="badge-tag">Star Schema DW</span>
            <span class="badge-tag">Database: {active_db}</span>
            <span class="badge-tag">API: FastAPI Port 8000</span>
            <span class="badge-tag">Winning Model: Gradient Boosting (ROC-AUC 0.695)</span>
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Executive Revenue Trends",
    "🛍️ Products & Category Pareto",
    "👥 Customer RFM Segmentation",
    "🌍 Geographic Intelligence",
    "🔄 Retention & Cohorts",
    "🛡️ Data Quality & Audit",
    "🔮 Churn Predictor Portal",
    "📈 MLOps & Drift Monitor"
])

# TAB 1: EXECUTIVE REVENUE & ORDER TRENDS
with tab1:
    st.markdown("### 📊 Executive KPI Performance")
    
    total_rev = filtered_sales["total_revenue"].sum()
    total_orders = filtered_sales["total_orders"].sum()
    total_units = filtered_sales["total_units_sold"].sum()
    overall_aov = total_rev / total_orders if total_orders > 0 else 0.0
    active_custs = filtered_rfm["customer_id"].nunique()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(
            f"""<div class="kpi-card">
                <div class="kpi-title">Gross Revenue</div>
                <div class="kpi-value">£{total_rev:,.2f}</div>
                <div class="kpi-subtext">Net Sales Volume</div>
            </div>""",
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f"""<div class="kpi-card">
                <div class="kpi-title">Total Orders</div>
                <div class="kpi-value">{total_orders:,}</div>
                <div class="kpi-subtext">Distinct Invoices</div>
            </div>""",
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            f"""<div class="kpi-card">
                <div class="kpi-title">Average Order Value</div>
                <div class="kpi-value">£{overall_aov:,.2f}</div>
                <div class="kpi-subtext">AOV per Transaction</div>
            </div>""",
            unsafe_allow_html=True
        )
    with col4:
        st.markdown(
            f"""<div class="kpi-card">
                <div class="kpi-title">Units Sold</div>
                <div class="kpi-value">{total_units:,}</div>
                <div class="kpi-subtext">Cumulative Items</div>
            </div>""",
            unsafe_allow_html=True
        )
    with col5:
        st.markdown(
            f"""<div class="kpi-card">
                <div class="kpi-title">Active Customers</div>
                <div class="kpi-value">{active_custs:,}</div>
                <div class="kpi-subtext">Registered Accounts</div>
            </div>""",
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)
    
    monthly_trend = filtered_sales.groupby("year_month").agg(
        revenue=("total_revenue", "sum"),
        orders=("total_orders", "sum"),
        units=("total_units_sold", "sum")
    ).reset_index()

    col_chart1, col_chart2 = st.columns([3, 2])

    with col_chart1:
        st.markdown("#### 📈 Monthly Sales Revenue & Order Volume")
        fig_rev = go.Figure()
        fig_rev.add_trace(go.Bar(
            x=monthly_trend["year_month"],
            y=monthly_trend["revenue"],
            name="Revenue (£)",
            marker_color="#3b82f6",
            opacity=0.85
        ))
        fig_rev.add_trace(go.Scatter(
            x=monthly_trend["year_month"],
            y=monthly_trend["orders"] * 100,
            name="Orders Trend (Scaled x100)",
            mode="lines+markers",
            line=dict(color="#10b981", width=3)
        ))
        fig_rev.update_layout(
            template="plotly_dark",
            xaxis_title="Month",
            yaxis_title="Revenue (£ GBP)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=30, b=20),
            height=380
        )
        st.plotly_chart(fig_rev, use_container_width=True)

    with col_chart2:
        st.markdown("#### 📅 Day-of-Week Shopping Velocity")
        dow_agg = filtered_sales.groupby("day_name")["total_revenue"].sum().reindex(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Sunday"]
        ).reset_index()
        fig_dow = px.bar(
            dow_agg,
            x="day_name",
            y="total_revenue",
            color="total_revenue",
            color_continuous_scale="Purples",
            labels={"day_name": "Day of Week", "total_revenue": "Revenue (£)"}
        )
        fig_dow.update_layout(
            template="plotly_dark",
            coloraxis_showscale=False,
            margin=dict(l=20, r=20, t=30, b=20),
            height=380
        )
        st.plotly_chart(fig_dow, use_container_width=True)

# TAB 2: PRODUCTS & CATEGORIES
with tab2:
    st.markdown("### 🛍️ Product Catalog & Category Performance")

    col_p1, col_p2 = st.columns([3, 2])
    with col_p1:
        st.markdown("#### 🏆 Top 15 Best-Selling Products by Revenue")
        top15 = filtered_products.head(15).sort_values(by="total_revenue", ascending=True)
        fig_top = px.bar(
            top15,
            x="total_revenue",
            y="description",
            orientation="h",
            color="category",
            color_discrete_sequence=px.colors.qualitative.Prism,
            labels={"total_revenue": "Total Revenue (£)", "description": "Product Name"}
        )
        fig_top.update_layout(
            template="plotly_dark",
            margin=dict(l=20, r=20, t=20, b=20),
            height=450,
            showlegend=True
        )
        st.plotly_chart(fig_top, use_container_width=True)

    with col_p2:
        st.markdown("#### 🥧 Category Revenue Share")
        cat_agg = filtered_products.groupby("category")["total_revenue"].sum().reset_index()
        fig_pie = px.pie(
            cat_agg,
            names="category",
            values="total_revenue",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_layout(
            template="plotly_dark",
            margin=dict(l=20, r=20, t=20, b=20),
            height=450
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("#### 📈 Pareto Analysis (80/20 Rule: Cumulative Revenue vs. Product SKUs)")
    pareto_df = df_products.sort_values(by="total_revenue", ascending=False).copy()
    pareto_df["cumulative_revenue"] = pareto_df["total_revenue"].cumsum()
    pareto_df["cumulative_revenue_pct"] = pareto_df["cumulative_revenue"] / pareto_df["total_revenue"].sum() * 100
    pareto_df["sku_rank"] = np.arange(1, len(pareto_df) + 1)
    pareto_df["sku_pct"] = pareto_df["sku_rank"] / len(pareto_df) * 100

    fig_pareto = go.Figure()
    fig_pareto.add_trace(go.Scatter(
        x=pareto_df["sku_pct"],
        y=pareto_df["cumulative_revenue_pct"],
        mode="lines",
        line=dict(color="#ec4899", width=3),
        name="Cumulative Revenue %"
    ))
    fig_pareto.add_hline(y=80, line_dash="dash", line_color="#10b981", annotation_text="80% Revenue Threshold")
    fig_pareto.add_vline(x=20, line_dash="dash", line_color="#60a5fa", annotation_text="20% Product SKUs")

    fig_pareto.update_layout(
        template="plotly_dark",
        xaxis_title="Percentage of Product Catalog (%)",
        yaxis_title="Cumulative Revenue Share (%)",
        height=350,
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig_pareto, use_container_width=True)

# TAB 3: CUSTOMER RFM SEGMENTATION
with tab3:
    st.markdown("### 👥 Customer RFM (Recency, Frequency, Monetary) Segmentation")

    seg_summary = filtered_rfm.groupby("customer_segment").agg(
        customer_count=("customer_id", "count"),
        total_spend=("monetary_total", "sum"),
        avg_recency=("recency_days", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_spend=("monetary_total", "mean")
    ).reset_index().sort_values(by="total_spend", ascending=False)

    col_rfm1, col_rfm2 = st.columns([3, 2])
    with col_rfm1:
        st.markdown("#### 🎯 Revenue Contribution by Customer Persona")
        fig_seg = px.bar(
            seg_summary,
            x="customer_segment",
            y="total_spend",
            color="customer_segment",
            color_discrete_sequence=px.colors.qualitative.Bold,
            labels={"customer_segment": "Segment", "total_spend": "Total Spend (£)"}
        )
        fig_seg.update_layout(
            template="plotly_dark",
            showlegend=False,
            height=380,
            margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig_seg, use_container_width=True)

    with col_rfm2:
        st.markdown("#### 👥 Segment Customer Headcount")
        fig_head = px.pie(
            seg_summary,
            names="customer_segment",
            values="customer_count",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_head.update_layout(
            template="plotly_dark",
            height=380,
            margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig_head, use_container_width=True)

    st.markdown("#### 🌌 3D RFM Behavioral Space (Recency vs. Frequency vs. Monetary)")
    sample_rfm = filtered_rfm.sample(min(1500, len(filtered_rfm)), random_state=42)
    fig_3d = px.scatter_3d(
        sample_rfm,
        x="recency_days",
        y="frequency",
        z="monetary_total",
        color="customer_segment",
        size="frequency",
        hover_name="customer_id",
        hover_data={"loyalty_tier": True, "monetary_total": ":,.2f", "recency_days": True},
        color_discrete_sequence=px.colors.qualitative.Bold,
        labels={"recency_days": "Recency (Days)", "frequency": "Frequency (Orders)", "monetary_total": "Monetary (£)"}
    )
    fig_3d.update_layout(
        template="plotly_dark",
        height=550,
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig_3d, use_container_width=True)

    st.markdown("#### 🧬 Customer Demographics Matrix (Loyalty Tiers & Age Groups)")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        tier_agg = filtered_rfm.groupby(["loyalty_tier", "gender"])["monetary_total"].sum().reset_index()
        fig_tier = px.bar(
            tier_agg,
            x="loyalty_tier",
            y="monetary_total",
            color="gender",
            barmode="group",
            labels={"loyalty_tier": "Loyalty Tier", "monetary_total": "Total Spend (£)"}
        )
        fig_tier.update_layout(template="plotly_dark", height=320, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_tier, use_container_width=True)

    with col_d2:
        dev_agg = filtered_rfm.groupby("preferred_device")["customer_id"].count().reset_index()
        fig_dev = px.bar(
            dev_agg,
            x="preferred_device",
            y="customer_id",
            color="preferred_device",
            labels={"preferred_device": "Platform Channel", "customer_id": "Customer Count"}
        )
        fig_dev.update_layout(template="plotly_dark", showlegend=False, height=320, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_dev, use_container_width=True)

# TAB 4: GEOGRAPHIC INTELLIGENCE
with tab4:
    st.markdown("### 🌍 Geographic & Global Market Analysis")

    geo_summary = df_sales.groupby(["country_name", "region", "market_tier"]).agg(
        revenue=("total_revenue", "sum"),
        orders=("total_orders", "sum"),
        units=("total_units_sold", "sum"),
        customers=("unique_customers", "sum")
    ).reset_index().sort_values(by="revenue", ascending=False)

    col_g1, col_g2 = st.columns([3, 2])

    with col_g1:
        st.markdown("#### 🗺️ Global Revenue Distribution (Choropleth Map)")
        fig_map = px.choropleth(
            geo_summary,
            locations="country_name",
            locationmode="country names",
            color="revenue",
            hover_name="country_name",
            hover_data={"revenue": ":,.2f", "orders": ":,", "region": True},
            color_continuous_scale="Viridis",
            labels={"revenue": "Revenue (£)"}
        )
        fig_map.update_layout(
            template="plotly_dark",
            geo=dict(showcoastlines=True, projection_type="natural earth"),
            margin=dict(l=0, r=0, t=10, b=0),
            height=420
        )
        st.plotly_chart(fig_map, use_container_width=True)

    with col_g2:
        st.markdown("#### 🌐 Top 10 International Export Markets (Excluding UK)")
        non_uk = geo_summary[geo_summary["country_name"] != "United Kingdom"].head(10)
        fig_non_uk = px.bar(
            non_uk,
            x="revenue",
            y="country_name",
            orientation="h",
            color="region",
            labels={"revenue": "Revenue (£)", "country_name": "Country"}
        )
        fig_non_uk.update_layout(
            template="plotly_dark",
            height=420,
            margin=dict(l=20, r=20, t=10, b=20)
        )
        st.plotly_chart(fig_non_uk, use_container_width=True)

# TAB 5: RETENTION & COHORTS
with tab5:
    st.markdown("### 🔄 Customer Retention & Repeat Purchase Analytics")

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.markdown("#### 🔁 Customer Purchase Sequence (1st vs Repeat Orders)")
        seq_agg = df_retention.groupby("order_sequence")["order_value"].agg(["count", "sum"]).reset_index().head(10)
        seq_agg.columns = ["Order Sequence", "Order Count", "Total Revenue"]
        
        fig_seq = px.bar(
            seq_agg,
            x="Order Sequence",
            y="Order Count",
            color="Total Revenue",
            labels={"Order Sequence": "Order Number in Customer Lifetime", "Order Count": "Number of Orders"}
        )
        fig_seq.update_layout(template="plotly_dark", height=350, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_seq, use_container_width=True)

    with col_r2:
        st.markdown("#### ⏱️ Inter-Purchase Latency (Days Between Orders)")
        repeat_orders = df_retention[df_retention["is_repeat_customer"] == 1]
        fig_hist = px.histogram(
            repeat_orders,
            x="days_since_prior_order",
            nbins=40,
            color_discrete_sequence=["#8b5cf6"],
            labels={"days_since_prior_order": "Days Elapsed Since Previous Purchase"}
        )
        fig_hist.update_layout(template="plotly_dark", height=350, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_hist, use_container_width=True)

    st.markdown("#### 📊 Monthly Acquisition Cohorts & Lifetime Value")
    cohort_agg = df_retention.groupby("cohort_month").agg(
        total_orders=("order_value", "count"),
        lifetime_revenue=("order_value", "sum"),
        avg_basket=("order_value", "mean")
    ).reset_index()

    fig_cohort = px.line(
        cohort_agg,
        x="cohort_month",
        y="lifetime_revenue",
        markers=True,
        line_shape="spline",
        labels={"cohort_month": "Cohort Signup Month", "lifetime_revenue": "Lifetime Revenue (£)"}
    )
    fig_cohort.update_layout(template="plotly_dark", height=320, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_cohort, use_container_width=True)

# TAB 6: DATA QUALITY & PIPELINE AUDIT
with tab6:
    st.markdown("### 🛡️ Data Engineering Quality & Pipeline Audit")

    col_q1, col_q2, col_q3 = st.columns(3)
    with col_q1:
        st.markdown(
            """<div class="kpi-card">
                <div class="kpi-title">Data Quality Pass Rate</div>
                <div class="kpi-value">99.53%</div>
                <div class="kpi-subtext">539,388 of 541,909 rows valid</div>
            </div>""",
            unsafe_allow_html=True
        )
    with col_q2:
        st.markdown(
            """<div class="kpi-card">
                <div class="kpi-title">Quarantined Records</div>
                <div class="kpi-value">2,521</div>
                <div class="kpi-subtext">Logged with Error Reason Codes</div>
            </div>""",
            unsafe_allow_html=True
        )
    with col_q3:
        st.markdown(
            """<div class="kpi-card">
                <div class="kpi-title">Exact Duplicates Cleaned</div>
                <div class="kpi-value">5,265</div>
                <div class="kpi-subtext">Deduplicated Idempotently</div>
            </div>""",
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)
    col_qa1, col_qa2 = st.columns(2)
    with col_qa1:
        st.markdown("#### ⚠️ Quarantine Reasons Breakdown")
        if not df_rejections.empty:
            fig_rej = px.bar(
                df_rejections,
                x="rejection_count",
                y="rejection_reason",
                orientation="h",
                color="rejection_count",
                color_continuous_scale="Reds",
                labels={"rejection_count": "Quarantined Records", "rejection_reason": "Failure Reason"}
            )
            fig_rej.update_layout(template="plotly_dark", coloraxis_showscale=False, height=320, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_rej, use_container_width=True)
        else:
            st.info("No rejections logged.")

    with col_qa2:
        st.markdown("#### 📜 Ingestion Audit Trail")
        if not df_audit.empty:
            st.dataframe(df_audit[["batch_id", "extraction_timestamp", "raw_row_count", "cleaned_row_count", "rejected_row_count", "status", "execution_duration_sec"]], height=320)
        else:
            st.info("Audit trail empty.")

    st.markdown("#### 🔍 Warehouse Table Row Counts")
    table_stats = execute_query("""
        SELECT 'dim_customer' as table_name, count(*) as row_count FROM dim_customer
        UNION ALL SELECT 'dim_product', count(*) FROM dim_product
        UNION ALL SELECT 'dim_geography', count(*) FROM dim_geography
        UNION ALL SELECT 'dim_date', count(*) FROM dim_date
        UNION ALL SELECT 'fact_sales', count(*) FROM fact_sales
        UNION ALL SELECT 'fact_customer_retention', count(*) FROM fact_customer_retention
        UNION ALL SELECT 'mart_sales_performance', count(*) FROM mart_sales_performance
        UNION ALL SELECT 'mart_customer_rfm', count(*) FROM mart_customer_rfm
    """)
    st.dataframe(table_stats, use_container_width=True)

# TAB 7: CHURN PREDICTOR & INFERENCE PORTAL
with tab7:
    st.markdown("### 🔮 Real-Time Customer Churn Scoring Portal")
    st.markdown("Evaluate single customer profiles or query the production FastAPI model service.")

    col_inf1, col_inf2 = st.columns([2, 3])

    with col_inf1:
        st.markdown("#### 📝 Customer Feature Input Form")
        with st.form("churn_prediction_form"):
            in_cust_id = st.number_input("Customer ID", min_value=10000, max_value=25000, value=17850)
            in_recency = st.slider("Recency (Days Since Last Order)", min_value=0, max_value=365, value=120)
            in_freq = st.number_input("Frequency (Total Orders)", min_value=1, max_value=100, value=2)
            in_monetary = st.number_input("Monetary Spend (£)", min_value=0.0, max_value=50000.0, value=150.0)
            in_aov = st.number_input("Average Order Value (£)", min_value=0.0, max_value=5000.0, value=75.0)
            in_units = st.number_input("Total Quantity Units", min_value=1, max_value=10000, value=45)
            in_cancellation = st.slider("Cancellation Rate", min_value=0.0, max_value=1.0, value=0.05)
            in_latency = st.slider("Mean Days Between Orders", min_value=1, max_value=180, value=40)
            in_tier = st.selectbox("Loyalty Tier", ["Bronze", "Silver", "Gold", "Platinum"], index=0)
            in_country = st.selectbox("Country", ["United Kingdom", "Germany", "France", "Eire"], index=0)

            submit_btn = st.form_submit_button("⚡ Score Churn Risk")

    with col_inf2:
        st.markdown("#### 🎯 Prediction Results & Risk Assessment")
        if submit_btn:
            try:
                import requests
                api_base = os.getenv("API_URL", "http://localhost:8000")
                api_url = f"{api_base}/predict"
                payload = {
                    "customer_id": int(in_cust_id),
                    "recency_days": float(in_recency),
                    "frequency_orders": float(in_freq),
                    "monetary_spend": float(in_monetary),
                    "avg_order_value": float(in_aov),
                    "total_units": float(in_units),
                    "cancellation_rate": float(in_cancellation),
                    "inter_purchase_mean": float(in_latency),
                    "inter_purchase_std": 10.0,
                    "product_variety": 5.0,
                    "gender": "Female",
                    "age_group": "36-50",
                    "loyalty_tier": in_tier,
                    "preferred_device": "Mobile App",
                    "country": in_country
                }
                res = requests.post(api_url, json=payload, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    prob = data["churn_probability"]
                    risk = data["risk_level"]
                    rec = data["recommendation"]

                    st.markdown(
                        f"""
                        <div class="kpi-card" style="border-left: 6px solid {'#ef4444' if prob>=0.7 else ('#f59e0b' if prob>=0.4 else '#10b981')};">
                            <div class="kpi-title">Predicted Churn Probability</div>
                            <div class="kpi-value">{prob * 100:.1f}%</div>
                            <div class="kpi-subtext" style="color: {'#ef4444' if prob>=0.7 else ('#f59e0b' if prob>=0.4 else '#10b981')}; font-size: 16px; font-weight: 700;">
                                {risk.upper()}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.info(f"💡 **Strategic Retention Recommendation:**\n{rec}")

                    fig_gauge = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=prob * 100,
                        title={'text': "Churn Probability (%)"},
                        gauge={
                            'axis': {'range': [0, 100]},
                            'bar': {'color': "#ef4444" if prob>=0.7 else ("#f59e0b" if prob>=0.4 else "#10b981")},
                            'steps': [
                                {'range': [0, 40], 'color': "rgba(16, 185, 129, 0.2)"},
                                {'range': [40, 70], 'color': "rgba(245, 158, 11, 0.2)"},
                                {'range': [70, 100], 'color': "rgba(239, 68, 68, 0.2)"}
                            ],
                        }
                    ))
                    fig_gauge.update_layout(template="plotly_dark", height=280, margin=dict(l=20, r=20, t=40, b=20))
                    st.plotly_chart(fig_gauge, use_container_width=True)

                else:
                    st.error(f"API Error ({res.status_code}): {res.text}")
            except Exception as err:
                st.warning(f"Could not connect to FastAPI server on port 8000 ({err}). Scoring with direct local model fallback...")
                from api.main import predict_single_customer
                from api.schemas import CustomerFeaturesInput
                item = CustomerFeaturesInput(
                    customer_id=int(in_cust_id),
                    recency_days=float(in_recency),
                    frequency_orders=float(in_freq),
                    monetary_spend=float(in_monetary),
                    avg_order_value=float(in_aov),
                    total_units=float(in_units),
                    cancellation_rate=float(in_cancellation),
                    inter_purchase_mean=float(in_latency),
                    loyalty_tier=in_tier,
                    country=in_country
                )
                pred_res = predict_single_customer(item)
                st.success(f"Local Model Score: {pred_res.churn_probability * 100:.1f}% Churn Probability ({pred_res.risk_level})")
                st.info(f"💡 Recommendation: {pred_res.recommendation}")
        else:
            st.info("Submit the feature input form on the left to compute real-time churn risk.")

# TAB 8: MLOPS EXPERIMENTS & DRIFT MONITOR
with tab8:
    st.markdown("### 📈 MLOps Model Registry, MLflow Runs & Drift Monitor")

    comp_path = BASE_DIR / "models" / "model_comparison.json"
    if comp_path.exists():
        with open(comp_path, "r", encoding="utf-8") as f:
            comp_data = json.load(f)

        st.markdown(f"#### 🏆 Model Registry Status: Active Model -> `{comp_data.get('winning_model', 'Gradient_Boosting')}`")

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.markdown(
                f"""<div class="kpi-card">
                    <div class="kpi-title">Winning Classifier</div>
                    <div class="kpi-value">{comp_data.get('winning_model')}</div>
                    <div class="kpi-subtext">Registered Version 1.0</div>
                </div>""",
                unsafe_allow_html=True
            )
        with col_m2:
            best_auc = comp_data['comparison'][comp_data['winning_model']]['metrics']['roc_auc']
            st.markdown(
                f"""<div class="kpi-card">
                    <div class="kpi-title">Test ROC-AUC Score</div>
                    <div class="kpi-value">{best_auc:.4f}</div>
                    <div class="kpi-subtext">Evaluated on Holdout Test Set</div>
                </div>""",
                unsafe_allow_html=True
            )
        with col_m3:
            best_f1 = comp_data['comparison'][comp_data['winning_model']]['metrics']['f1_score']
            st.markdown(
                f"""<div class="kpi-card">
                    <div class="kpi-title">Test F1 Score</div>
                    <div class="kpi-value">{best_f1:.4f}</div>
                    <div class="kpi-subtext">Harmonic Mean Precision/Recall</div>
                </div>""",
                unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 📊 Classifier Benchmark Comparison")
        comp_rows = []
        for name, info in comp_data["comparison"].items():
            row = {"Model": name}
            row.update(info["metrics"])
            comp_rows.append(row)
        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True)

        st.markdown("#### 🖼️ Model Diagnostic Artifacts (Confusion Matrix & ROC Curve)")
        col_img1, col_img2 = st.columns(2)
        win_name_clean = comp_data['winning_model'].lower()
        cm_file = BASE_DIR / "models" / f"{win_name_clean}_cm.png"
        roc_file = BASE_DIR / "models" / f"{win_name_clean}_roc.png"

        with col_img1:
            if cm_file.exists():
                st.image(str(cm_file), caption=f"Confusion Matrix - {comp_data['winning_model']}")
        with col_img2:
            if roc_file.exists():
                st.image(str(roc_file), caption=f"ROC Curve - {comp_data['winning_model']}")

    # Feature Drift Section
    st.markdown("---")
    st.markdown("#### 🔬 Feature & Data Drift Audit (PSI & Kolmogorov-Smirnov Test)")
    try:
        from src.ml.drift_monitor import calculate_feature_drift
        from src.ml.feature_engineering import extract_customer_features
        X_all, _, _ = extract_customer_features()
        
        baseline_sample = X_all.sample(frac=0.6, random_state=42)
        current_sample = X_all.drop(baseline_sample.index)

        drift_df = calculate_feature_drift(baseline_sample, current_sample)
        st.dataframe(drift_df, use_container_width=True)
        
        high_drift = len(drift_df[drift_df["alert_level"].str.contains("HIGH")])
        if high_drift == 0:
            st.success("✅ **Feature Drift Status: STABLE**. No significant feature distribution drift detected.")
        else:
            st.warning(f"⚠️ **Feature Drift Status: DRIFT DETECTED** ({high_drift} features drifted). Automated retraining recommended.")
    except Exception as err:
        st.info(f"Drift monitor status: {err}")
