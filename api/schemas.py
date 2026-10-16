"""Pydantic Request and Response Schemas for FastAPI Inference Microservice."""

from typing import List, Optional, Dict, Union
from pydantic import BaseModel, Field


class CustomerFeaturesInput(BaseModel):
    customer_id: Optional[Union[int, str]] = Field(default=None, description="Optional customer ID for feature warehouse lookup")
    recency_days: float = Field(..., ge=0, description="Days since last purchase")
    frequency_orders: float = Field(..., ge=1, description="Total order count")
    monetary_spend: float = Field(..., ge=0, description="Total spend in GBP (£)")
    avg_order_value: float = Field(..., ge=0, description="Average order spend")
    total_units: float = Field(..., ge=0, description="Total units purchased")
    cancellation_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Order cancellation ratio")
    inter_purchase_mean: float = Field(default=30.0, ge=0.0, description="Mean days between orders")
    inter_purchase_std: float = Field(default=10.0, ge=0.0, description="Std dev of days between orders")
    product_variety: float = Field(default=5.0, ge=1, description="Distinct product SKUs purchased")
    gender: str = Field(default="Unknown", description="Customer gender demographic")
    age_group: str = Field(default="36-50", description="Customer age group")
    loyalty_tier: str = Field(default="Bronze", description="Customer loyalty tier")
    preferred_device: str = Field(default="Desktop Web", description="Primary shopping platform channel")
    country: str = Field(default="United Kingdom", description="Customer country")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": 17850,
                "recency_days": 45.0,
                "frequency_orders": 3.0,
                "monetary_spend": 450.0,
                "avg_order_value": 150.0,
                "total_units": 120.0,
                "cancellation_rate": 0.05,
                "inter_purchase_mean": 28.5,
                "inter_purchase_std": 8.0,
                "product_variety": 12.0,
                "gender": "Female",
                "age_group": "26-35",
                "loyalty_tier": "Gold",
                "preferred_device": "Mobile App",
                "country": "United Kingdom"
            }
        }


class SinglePredictionResponse(BaseModel):
    customer_id: Optional[Union[int, str]]
    churn_prediction: int = Field(..., description="Binary classification (1 = Churned/At Risk, 0 = Active)")
    churn_probability: float = Field(..., description="Predicted probability of churn (0.0 to 1.0)")
    risk_level: str = Field(..., description="Categorical risk tier: Low, Medium, High")
    recommendation: str = Field(..., description="Suggested retention action")
    model_version: str = Field(default="v1.0")


class BatchPredictionRequest(BaseModel):
    customers: List[CustomerFeaturesInput]


class BatchPredictionResponse(BaseModel):
    predictions: List[SinglePredictionResponse]
    total_processed: int
    high_risk_count: int


class HealthResponse(BaseModel):
    status: str
    active_model: str
    metrics: Dict[str, float]
    database: str
    timestamp: str
