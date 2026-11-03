"""
FastAPI route handlers for forecasting, metrics, model metadata, data quality, and run triggers.
"""
import os
import json
import threading
import datetime
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.schemas import (
    ForecastResponse,
    ForecastPointSchema,
    MetricsResponse,
    MetricItem,
    ModelMetadataResponse,
    DataQualityResponse,
    ForecastRunRequest,
    ForecastRunResponse,
    HistoryResponse,
    HistoricalPointSchema,
)
from src.database.session import get_db
from src.database.models import ForecastRun, ForecastPoint, EvaluationMetric, ModelVersion, DataQualityEvent
from src.database.service import save_pipeline_run
from src.pipeline.forecaster import ForecastingPipeline
from src.pipeline.validator import ForecastArtifactValidator, DatasetValidator, ValidationError
from src.pipeline.data_loader import load_raw_data, prepare_variant_b
from src.monitoring.drift import DriftMonitor, RetrainingTriggerChecker
from src.api.security import verify_api_key, rate_limit_pipeline

router = APIRouter(prefix="/api/v1")

# Execution lock to prevent concurrent overlapping pipeline executions
pipeline_lock = threading.Lock()


def get_artifacts_dir() -> Path:
    """Resolve artifacts directory from env or default."""
    env_dir = os.getenv("ARTIFACTS_DIR", "")
    if env_dir:
        return Path(env_dir)
    for candidate in [
        Path("outputs"),
        Path("forecasting-project/outputs"),
        Path(__file__).resolve().parent.parent.parent / "outputs",
    ]:
        if candidate.exists():
            return candidate
    return Path("outputs")


def get_data_path() -> Path:
    """Resolve raw data path from env or default."""
    env_data = os.getenv("DATA_PATH", "")
    if env_data:
        return Path(env_data)
    for candidate in [
        Path("data/prices.csv"),
        Path("forecasting-project/data/prices.csv"),
        Path(__file__).resolve().parent.parent.parent / "data" / "prices.csv",
    ]:
        if candidate.exists():
            return candidate
    return Path("data/prices.csv")


# ─────────────────────────────────────────────────────────────────────────────
# 1. GET /api/v1/forecast
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/forecast", response_model=ForecastResponse, summary="Retrieve 12-Month Price Forecast")
def get_forecast(db: Session = Depends(get_db)):
    """
    Retrieve the approved 12-month operational price forecast (October 2025 to September 2026),
    including point forecasts and 80% & 95% model-based prediction intervals.
    """
    artifacts_dir = get_artifacts_dir()
    csv_path = artifacts_dir / "final_forecast.csv"

    if not csv_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved forecast artifact not found at {csv_path}",
        )

    try:
        df = pd.read_csv(csv_path)
        ForecastArtifactValidator.validate_forecast_dataframe(df)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forecast artifact validation failed: {str(e)}",
        )

    # File modification timestamp
    mtime = datetime.datetime.fromtimestamp(csv_path.stat().st_mtime, tz=datetime.timezone.utc).isoformat()

    points = [
        ForecastPointSchema(
            month=str(row["month"]),
            point_forecast=float(row["point_forecast"]),
            lower_80=float(row["lower_80"]),
            upper_80=float(row["upper_80"]),
            lower_95=float(row["lower_95"]),
            upper_95=float(row["upper_95"]),
        )
        for _, row in df.iterrows()
    ]

    return ForecastResponse(
        forecast_origin="2025-09-01",
        origin_price=15750.0,
        forecast_horizon="2025-10-01 to 2026-09-01",
        model_name="SARIMA(1,1,1)(1,0,0)[12]",
        model_version="approved_stage3",
        artifact_timestamp=mtime,
        run_id="stage3_approved_baseline",
        mean_point_forecast=round(float(df["point_forecast"].mean()), 1),
        forecast=points,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /api/v1/metrics
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/metrics", response_model=MetricsResponse, summary="Retrieve Holdout Performance Metrics")
def get_metrics():
    """
    Retrieve out-of-sample holdout evaluation metrics (October 2024 to September 2025)
    for the primary SARIMA model and the Naive benchmark.
    """
    artifacts_dir = get_artifacts_dir()
    csv_path = artifacts_dir / "forecast_metrics.csv"

    if not csv_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holdout metrics artifact not found.",
        )

    df = pd.read_csv(csv_path)

    # Primary SARIMA metrics
    sarima_row = df[df["Model"].str.contains("SARIMA")].iloc[0]
    naive_row = df[df["Model"].str.contains("Naive")].iloc[0]
    arima_rows = df[df["Model"].str.contains("ARIMA")]

    primary = MetricItem(
        model=str(sarima_row["Model"]),
        mae=float(sarima_row["MAE"]),
        rmse=float(sarima_row["RMSE"]),
        smape=float(sarima_row["sMAPE (%)"]),
        mase=float(sarima_row["MASE"]),
        bias=495.77,
    )

    benchmark = MetricItem(
        model=str(naive_row["Model"]),
        mae=float(naive_row["MAE"]),
        rmse=float(naive_row["RMSE"]),
        smape=float(naive_row["sMAPE (%)"]),
        mase=float(naive_row["MASE"]),
        bias=546.00,
    )

    comparison = None
    if not arima_rows.empty:
        ar_row = arima_rows.iloc[0]
        comparison = MetricItem(
            model=str(ar_row["Model"]),
            mae=float(ar_row["MAE"]),
            rmse=float(ar_row["RMSE"]),
            smape=float(ar_row["sMAPE (%)"]),
            mase=float(ar_row["MASE"]),
            bias=766.88,
        )

    rel_improvement = round(float((benchmark.mae - primary.mae) / benchmark.mae * 100.0), 2)

    interpretation = (
        f"SARIMA modestly outperforms the Naive benchmark on holdout MAE by {rel_improvement}% "
        f"({primary.mae} vs {benchmark.mae}). Error dynamics in the holdout were dominated by a sharp mid-winter "
        f"slump in Jan–Feb 2025 (11,313), which induced positive signed error across all models."
    )

    return MetricsResponse(
        evaluation_set="Final Holdout (Oct 2024 – Sep 2025)",
        holdout_months=12,
        primary_model_metrics=primary,
        benchmark_metrics=benchmark,
        comparison_metrics=comparison,
        relative_mae_improvement_pct=rel_improvement,
        interpretation=interpretation,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. GET /api/v1/model
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/model", response_model=ModelMetadataResponse, summary="Retrieve Model Metadata & Specification")
def get_model():
    """
    Retrieve model specification, training windows, transformation details,
    cross-validation performance, holdout results, and explicit operational limitations.
    """
    return ModelMetadataResponse(
        selected_model="SARIMA(1,1,1)(1,0,0)[12]",
        model_specification={
            "order": [1, 1, 1],
            "seasonal_order": [1, 0, 0, 12],
            "state_space_formulation": "SARIMAX with exact Kalman filtering",
            "enforce_stationarity": False,
            "enforce_invertibility": False,
        },
        transformation="Log transformation (geometric conditional median back-transformation via exponentiation)",
        training_window="Rolling 120 months (10 years) prior to forecast origin",
        validation_performance={
            "validation_design": "4-fold chronological expanding-origin cross-validation (pre-2021 history)",
            "mean_mae": 952.5,
            "mean_rmse": 1108.4,
            "mean_smape": 11.33,
            "mean_mase": 0.513,
            "worst_fold_mae": 1985.6,
            "convergence_rate": "100% (0 fit failures across all evaluated configurations)",
        },
        holdout_performance={
            "holdout_window": "2024-10-01 to 2025-09-01 (12 months)",
            "mae": 1139.48,
            "rmse": 1533.89,
            "smape": 8.38,
            "mase": 0.7334,
            "bias": 495.77,
        },
        known_limitations=[
            "State-space Kalman imputation over 30-month unobserved gap does not recover true lost market volatility.",
            "Segment 2 contains only 22 months post-2023, providing fewer than 2 annual cycles in the current price regime.",
            "Prediction intervals assume Gaussian innovations around a stable autoregressive regime; severe macroeconomic breaks may breach bounds.",
            "Modest edge over baseline: SARIMA achieves ~1.8% error reduction over Naive carry-forward, which remains an essential planning baseline.",
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. GET /api/v1/data-quality
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/data-quality", response_model=DataQualityResponse, summary="Retrieve Data Quality & Anomaly Summary")
def get_data_quality():
    """
    Retrieve audit summary of the analytical time-series series, including
    the 30-month unobserved copied block, December 2023 retention, and structural shifts.
    """
    data_path = get_data_path()
    df_raw = load_raw_data(str(data_path))
    df_b = prepare_variant_b(df_raw)
    val = DatasetValidator.validate_variant_b(df_b)

    anomalies = [
        {
            "anomaly_id": "ANOMALY_30M_COPIED_BLOCK",
            "period": "2021-06-01 to 2023-11-01 (30 months)",
            "type": "Repeated Sequence Duplication",
            "treatment": "Treated as unobserved NaNs in primary Variant B. Artificial interpolation strictly prohibited.",
            "status": "APPROVED_STAGE_1_DECISION",
        },
        {
            "anomaly_id": "REGIME_BOUNDARY_DEC2023",
            "period": "2023-12-01",
            "price": 16163.0,
            "type": "Post-Gap Level Resumption",
            "treatment": "Retained in primary series; sensitivity tests confirm it anchors the post-gap regime shift.",
            "status": "APPROVED_STAGE_1_DECISION",
        },
        {
            "anomaly_id": "STRUCTURAL_SHIFT_NOV2013",
            "period": "2013-11-01",
            "type": "Permanent Level Jump (+42.3%)",
            "treatment": "Captured via rolling-120 window and first-order integration I(1).",
            "status": "DOCUMENTED_DIAGNOSTIC",
        },
    ]

    warnings = [
        "Observations before (May 2021) and after (December 2023) the unobserved block must never be treated as contiguous.",
        "Dropping NaNs without preserving monthly index creates a false +48.8% single-month artificial spike.",
        "Annual seasonality models cannot be estimated reliably using only Segment 2 (22 months < 2 seasonal cycles).",
    ]

    return DataQualityResponse(
        dataset_name="Variant B (Primary Analytical Series)",
        observation_range={
            "start": "2005-01-01",
            "end": "2025-09-01",
        },
        total_months=val["total_months"],
        valid_observations=val["valid_observations"],
        missing_data_block={
            "start": val["missing_block_start"],
            "end": val["missing_block_end"],
            "months_count": val["missing_block_months"],
            "representation": "NaN (unobserved, calendar spacing strictly preserved)",
        },
        known_anomalies=anomalies,
        data_quality_warnings=warnings,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. GET /api/v1/history
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/history", response_model=HistoryResponse, summary="Retrieve Historical Price Observations")
def get_history():
    """
    Retrieve historical monthly prices (2005-01 to 2025-09) formatted for visualization,
    with explicit segment labels (Segment 1, Missing Block, Segment 2).
    """
    data_path = get_data_path()
    df_raw = load_raw_data(str(data_path))
    df_b = prepare_variant_b(df_raw)

    history = []
    for _, row in df_b.iterrows():
        dt_str = row["date"].strftime("%Y-%m-%d")
        price = None if pd.isna(row["avg_monthly_price"]) else float(row["avg_monthly_price"])
        if row["date"] <= pd.Timestamp("2021-05-01"):
            seg = "segment_1"
        elif row["date"] <= pd.Timestamp("2023-11-01"):
            seg = "missing_block"
        else:
            seg = "segment_2"

        history.append(HistoricalPointSchema(
            date=dt_str,
            price=price,
            segment=seg,
            is_missing=price is None,
        ))

    return HistoryResponse(
        total_observations=len(history),
        history=history,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. GET /api/v1/monitoring/drift
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/monitoring/drift", summary="Retrieve Drift Monitoring & Retraining Status")
def get_drift_status(db: Session = Depends(get_db)):
    """
    Retrieve drift monitoring metrics and retraining trigger evaluations.
    Compares the most recent distinct operational forecast run against the approved
    Stage 3 baseline. Returns BASELINE_ONLY / NOT_EVALUATED when no new run exists.
    """
    artifacts_dir = get_artifacts_dir()
    fc_path = artifacts_dir / "final_forecast.csv"
    if not fc_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved baseline forecast artifact not found at {fc_path}",
        )

    df_base = pd.read_csv(fc_path)

    # 1. Look for distinct post-baseline operational run in the database
    latest_run = (
        db.query(ForecastRun)
        .filter(ForecastRun.id != "stage3_approved_baseline")
        .order_by(ForecastRun.created_at.desc())
        .first()
    )

    triggers = RetrainingTriggerChecker.evaluate_triggers(new_actuals_count=0)

    # 2. If no distinct run exists, report BASELINE_ONLY without fake self-comparison
    if not latest_run or not latest_run.points:
        return {
            "status": "BASELINE_ONLY",
            "monitoring_scope": "Commodity Price Horizon (Oct 2025 – Sep 2026)",
            "baseline_run_id": "stage3_approved_baseline",
            "latest_run_id": None,
            "forecast_drift": {
                "status": "NOT_EVALUATED",
                "drift_detected": False,
                "message": "No distinct post-baseline operational forecast run found. Awaiting pipeline execution.",
                "baseline_points_count": len(df_base),
            },
            "retraining_triggers": triggers,
            "note": "Awaiting new forecast execution or post-September-2025 actual price observations to evaluate drift.",
        }

    # 3. If a distinct run exists, evaluate genuine drift against Stage 3 baseline
    pts = sorted(latest_run.points, key=lambda x: x.month)
    df_new = pd.DataFrame([
        {
            "month": p.month,
            "point_forecast": p.point_forecast,
            "lower_80": p.lower_80,
            "upper_80": p.upper_80,
            "lower_95": p.lower_95,
            "upper_95": p.upper_95,
        }
        for p in pts
    ])

    drift = DriftMonitor.check_forecast_distribution_drift(df_new, df_base)
    return {
        "status": "DRIFT_EVALUATED",
        "monitoring_scope": "Commodity Price Horizon (Oct 2025 – Sep 2026)",
        "baseline_run_id": "stage3_approved_baseline",
        "latest_run_id": latest_run.id,
        "forecast_drift": drift,
        "retraining_triggers": triggers,
        "note": f"Evaluated drift of latest run ({latest_run.id}) against approved Stage 3 baseline.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. POST /api/v1/forecast/run
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/forecast/run",
    response_model=ForecastRunResponse,
    summary="Execute Forecasting Pipeline",
    dependencies=[Depends(verify_api_key), Depends(rate_limit_pipeline)],
)
def trigger_forecast_run(
    req: ForecastRunRequest = ForecastRunRequest(),
    db: Session = Depends(get_db),
):
    """
    Deterministically execute the approved forecasting pipeline.
    Uses concurrency locking to prevent conflicting parallel executions.
    Writes atomic versioned artifacts and records execution in the database.
    """
    # Concurrency control
    acquired = pipeline_lock.acquire(blocking=False)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="A forecasting pipeline run is currently in progress. Please wait for completion.",
        )

    try:
        data_path = get_data_path()
        artifacts_dir = get_artifacts_dir()

        pipeline = ForecastingPipeline(data_path=str(data_path), artifacts_dir=str(artifacts_dir))
        summary = pipeline.run_pipeline(version_tag=req.version_tag)

        # Persist execution run in database
        save_pipeline_run(db, summary)

        return ForecastRunResponse(
            run_id=summary["run_id"],
            status=summary["status"],
            duration_ms=summary["duration_ms"],
            timestamp=summary["timestamp"],
            forecast_origin=summary["forecast_origin"],
            forecast_horizon=summary["forecast_horizon"],
            mean_point_forecast=summary["mean_point_forecast"],
            parity_verified=summary["parity_verified"],
            message=summary["message"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forecasting pipeline execution failed: {str(e)}",
        )
    finally:
        pipeline_lock.release()
