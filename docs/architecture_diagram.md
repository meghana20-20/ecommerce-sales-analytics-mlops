# System Architecture and Data Pipeline Flow

## 1. End-to-End System Architecture

The analytics platform follows a decoupled, multi-tier Lakehouse/Warehouse architecture designed for enterprise reliability, auditability, and analytical performance.

```mermaid
flowchart TD
    classDef sourceStyle fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef ingestStyle fill:#0f172a,stroke:#10b981,stroke-width:2px,color:#fff;
    classDef lakeStyle fill:#1e1e2e,stroke:#f59e0b,stroke-width:2px,color:#fff;
    classDef whStyle fill:#172554,stroke:#6366f1,stroke-width:2px,color:#fff;
    classDef martStyle fill:#312e81,stroke:#8b5cf6,stroke-width:2px,color:#fff;
    classDef dashStyle fill:#111827,stroke:#ec4899,stroke-width:2px,color:#fff;
    classDef mlStyle fill:#064e3b,stroke:#14b8a6,stroke-width:2px,stroke-dasharray: 5 5,color:#fff;

    subgraph Tier1 ["1. Data Source Layer"]
        UCI["UCI Online Retail Repository<br/>(541,909 Transactions)"]:::sourceStyle
        BatchSource["Simulated Monthly Invoices<br/>(orders_YYYY_MM.csv)"]:::sourceStyle
        CustProfile["Synthetic Customer Demographics<br/>(CRM Attributes)"]:::sourceStyle
    end

    subgraph Tier2 ["2. Ingestion & Landing Layer"]
        FetchEngine["Automated Ingestion Engine<br/>(Python / Requests / OpenPyXL)"]:::ingestStyle
        LandingRaw[("Raw Data Lakehouse<br/>/data/raw/")]:::ingestStyle
        BatchPartitioner["Batch Partitioner & Manifest Generator"]:::ingestStyle
    end

    subgraph Tier3 ["3. Raw/Staging & Quality Layer"]
        StagingArea[("Staging Parquet Store<br/>/data/staging/")]:::lakeStyle
        ValEngine["Data Quality Validation Engine<br/>(Rule Enforcement & Rejection)"]:::lakeStyle
        Rejections[("Quarantine / Error Log<br/>rejected_records.csv")]:::lakeStyle
        AuditLog[("Ingestion Audit Trail<br/>etl_audit_log")]:::lakeStyle
    end

    subgraph Tier4 ["4. Transformation & Cleaning Layer"]
        TransformEngine["Deduplication & Standardization<br/>Currency Normalization (GBP)<br/>Cancellation Logic & Key Resolution"]:::ingestStyle
    end

    subgraph Tier5 ["5. Storage Layer (PostgreSQL Star Schema)"]
        DimDate[("dim_date<br/>(Calendar Hierarchy)")]:::whStyle
        DimCust[("dim_customer<br/>(Demographics & Loyalty)")]:::whStyle
        DimProd[("dim_product<br/>(Catalog & Categorization)")]:::whStyle
        DimGeo[("dim_geography<br/>(Regions & Tiers)")]:::whStyle
        FactSales[("fact_sales<br/>(Granular Line Items)")]:::whStyle
        FactRetention[("fact_customer_retention<br/>(Cohort & Repeat Sequence)")]:::whStyle
    end

    subgraph Tier6 ["6. Analytics & Data Marts Layer"]
        MartSales[("mart_sales_performance<br/>(Revenue, AOV, Volume)")]:::martStyle
        MartRFM[("mart_customer_rfm<br/>(Recency, Frequency, Monetary)")]:::martStyle
    end

    subgraph Tier7 ["7. Presentation & BI Layer"]
        Dashboard["Streamlit Interactive Analytics Web App<br/>(Plotly Visuals & KPI Scorecards)"]:::dashStyle
    end

    subgraph Tier8 ["8. Future MLOps Layer (Part 2)"]
        MLOps["MLflow Experiment Tracking<br/>Churn / Repeat-Purchase Model<br/>FastAPI Model Serving & Docker"]:::mlStyle
    end

    %% Data Flow Connections
    Tier1 --> FetchEngine & BatchPartitioner
    FetchEngine --> LandingRaw
    LandingRaw --> StagingArea
    StagingArea --> ValEngine
    ValEngine -- Invalid Records --> Rejections
    ValEngine -- Audit Metrics --> AuditLog
    ValEngine -- Validated Stream --> TransformEngine

    TransformEngine --> DimDate & DimCust & DimProd & DimGeo
    TransformEngine --> FactSales & FactRetention

    FactSales & DimDate & DimGeo --> MartSales
    FactSales & DimCust --> MartRFM

    MartSales & MartRFM & Rejections & AuditLog --> Dashboard
    MartRFM & FactRetention -.-> MLOps
```

---

## 2. Dimensional Data Warehouse (Star Schema ER Diagram)

The dimensional data warehouse employs a classic **Star Schema** pattern optimized for analytical queries (OLAP), slice-and-dice drill-downs, and business intelligence dashboards.

```mermaid
erDiagram
    DIM_CUSTOMER ||--o{ FACT_SALES : "places"
    DIM_PRODUCT ||--o{ FACT_SALES : "purchased in"
    DIM_GEOGRAPHY ||--o{ FACT_SALES : "originates from"
    DIM_DATE ||--o{ FACT_SALES : "occurs on"

    DIM_CUSTOMER ||--o{ FACT_CUSTOMER_RETENTION : "exhibits"
    DIM_DATE ||--o{ FACT_CUSTOMER_RETENTION : "measured on"

    DIM_CUSTOMER ||--|| MART_CUSTOMER_RFM : "evaluated by"
    DIM_DATE ||--o{ MART_SALES_PERFORMANCE : "summarized by"

    DIM_CUSTOMER {
        int customer_key PK
        bigint customer_id UK
        string customer_code
        string gender
        string age_group
        string loyalty_tier
        date signup_date
        string preferred_device
        string country
    }

    DIM_PRODUCT {
        int product_key PK
        string stock_code UK
        string description
        string category
        decimal unit_price_nominal
    }

    DIM_GEOGRAPHY {
        int geography_key PK
        string country_name UK
        string region
        string market_tier
    }

    DIM_DATE {
        int date_key PK
        date full_date UK
        int year
        int quarter
        int month
        string month_name
        int day
        int day_of_week
        string day_name
        boolean is_weekend
    }

    FACT_SALES {
        int sales_key PK
        string invoice_no
        int customer_key FK
        int product_key FK
        int geography_key FK
        int date_key FK
        timestamp invoice_timestamp
        int quantity
        decimal unit_price
        decimal total_amount
        boolean is_cancelled
        string batch_id
    }

    FACT_CUSTOMER_RETENTION {
        int retention_key PK
        int customer_key FK
        int date_key FK
        string cohort_month
        int order_sequence
        int days_since_prior_order
        decimal order_value
        boolean is_repeat_customer
    }

    MART_SALES_PERFORMANCE {
        int mart_id PK
        int date_key FK
        string year_month
        string country_name
        decimal total_revenue
        int total_orders
        int total_units_sold
        decimal average_order_value
        int unique_customers
        int cancelled_orders_count
    }

    MART_CUSTOMER_RFM {
        int customer_key PK, FK
        bigint customer_id UK
        int recency_days
        int frequency
        decimal monetary_total
        int r_score
        int f_score
        int m_score
        string rfm_score
        string customer_segment
        string loyalty_tier
        date last_order_date
    }
```

---

## 3. Orchestrated Pipeline Execution Flow (Airflow DAG)

```mermaid
sequenceDiagram
    autonumber
    actor Scheduler as Airflow / CLI Runner
    participant Raw as Ingestion Engine
    participant QA as Quality Assurance Engine
    participant Trans as Transformation Engine
    participant DW as PostgreSQL / Star Schema
    participant Marts as Analytical Marts
    participant BI as Streamlit Platform

    Scheduler->>Raw: Trigger Ingestion & Batch Partitioning
    Raw->>Raw: Fetch UCI Online Retail & synthesize customer master
    Raw->>QA: Push Staging Parquet files
    QA->>QA: Execute validation rules (schema, nulls, positive prices)
    alt Records Fail Quality Checks
        QA->>QA: Quarantine bad rows to rejected_records.csv
        QA->>DW: Log failure reason codes in etl_rejection_log
    end
    QA->>Trans: Send validated clean records
    Trans->>Trans: Deduplicate, format dates, standardize currency (GBP)
    Trans->>DW: Build & Load Dimensions (Customer, Product, Geo, Date)
    Trans->>DW: Build & Load Fact Tables (fact_sales, fact_retention)
    DW->>Marts: Compute Marts (mart_sales_performance, mart_customer_rfm)
    Marts->>DW: Persist Mart tables & write etl_audit_log entry
    DW->>BI: Serve low-latency analytical data queries to Streamlit
    BI->>Scheduler: Pipeline run successful (Audit status: COMPLETED)
```
