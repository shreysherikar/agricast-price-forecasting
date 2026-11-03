"""
Pydantic data schemas for API requests and responses.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., example="HEALTHY")
    version: str = Field(..., example="1.0.0")
    database_connected: bool = Field(..., example=True)
    artifacts_available: bool = Field(..., example=True)
    model_loaded: bool = Field(..., example=True)
    timestamp: str


class ForecastPointSchema(BaseModel):
    month: str = Field(..., example="2025-10-01")
    point_forecast: float = Field(..., example=15531.7)
    lower_80: float = Field(..., example=14423.5)
    upper_80: float = Field(..., example=16725.0)
    lower_95: float = Field(..., example=13869.2)
    upper_95: float = Field(..., example=17393.4)


class ForecastResponse(BaseModel):
    forecast_origin: str = Field(..., example="2025-09-01")
    origin_price: float = Field(..., example=15750.0)
    forecast_horizon: str = Field(..., example="2025-10-01 to 2026-09-01")
    model_name: str = Field(..., example="SARIMA(1,1,1)(1,0,0)[12]")
    model_version: str = Field(..., example="approved_stage3")
    artifact_timestamp: str
    run_id: str
    mean_point_forecast: float = Field(..., example=15429.8)
    forecast: List[ForecastPointSchema]


class MetricItem(BaseModel):
    model: str
    mae: float
    rmse: float
    smape: float
    mase: float
    bias: Optional[float] = None


class MetricsResponse(BaseModel):
    evaluation_set: str = Field(..., example="Final Holdout (Oct 2024 – Sep 2025)")
    holdout_months: int = 12
    primary_model_metrics: MetricItem
    benchmark_metrics: MetricItem
    comparison_metrics: Optional[MetricItem] = None
    relative_mae_improvement_pct: float = Field(..., example=1.80)
    interpretation: str


class ModelMetadataResponse(BaseModel):
    selected_model: str
    model_specification: Dict[str, Any]
    transformation: str
    training_window: str
    validation_performance: Dict[str, Any]
    holdout_performance: Dict[str, Any]
    known_limitations: List[str]


class DataQualityResponse(BaseModel):
    dataset_name: str
    observation_range: Dict[str, str]
    total_months: int
    valid_observations: int
    missing_data_block: Dict[str, Any]
    known_anomalies: List[Dict[str, Any]]
    data_quality_warnings: List[str]


class ForecastRunRequest(BaseModel):
    trigger_note: Optional[str] = "Manual dashboard trigger"
    version_tag: Optional[str] = "user_run"


class ForecastRunResponse(BaseModel):
    run_id: str
    status: str
    duration_ms: int
    timestamp: str
    forecast_origin: str
    forecast_horizon: str
    mean_point_forecast: float
    parity_verified: bool
    message: str


class HistoricalPointSchema(BaseModel):
    date: str
    price: Optional[float]
    segment: str
    is_missing: bool


class HistoryResponse(BaseModel):
    total_observations: int
    history: List[HistoricalPointSchema]
