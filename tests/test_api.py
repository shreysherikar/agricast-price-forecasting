"""
Automated unit and integration tests for API endpoints and error responses.
"""
import pytest
from src.database.session import get_db
from fastapi import HTTPException
from src.database.models import ForecastRun, ForecastPoint
from src.api.routes import (
    get_forecast,
    get_metrics,
    get_model,
    get_data_quality,
    get_history,
    get_drift_status,
    trigger_forecast_run,
)
from src.api.schemas import ForecastRunRequest
from main import get_health


@pytest.fixture
def db_session(project_dir):
    from src.database.session import init_db, get_db
    from src.database.service import seed_approved_stage3_data

    init_db()
    db = next(get_db())
    try:
        seed_approved_stage3_data(db, artifacts_dir=str(project_dir / "outputs"))
    except Exception:
        pass
    yield db
    db.close()


def test_health_endpoint(db_session):
    """GET /health must return HEALTHY with database and artifacts available."""
    res = get_health(db_session)
    assert res.status == "HEALTHY"
    assert res.database_connected is True
    assert res.artifacts_available is True
    assert res.version == "1.0.0"


def test_forecast_endpoint(db_session):
    """GET /api/v1/forecast must return 12 points spanning 2025-10 to 2026-09."""
    res = get_forecast(db_session)
    assert res.forecast_origin == "2025-09-01"
    assert res.forecast_horizon == "2025-10-01 to 2026-09-01"
    assert res.mean_point_forecast == pytest.approx(15429.8, abs=0.5)
    assert len(res.forecast) == 12
    assert res.forecast[0].month == "2025-10-01"
    assert res.forecast[-1].month == "2026-09-01"


def test_metrics_endpoint():
    """GET /api/v1/metrics must report holdout MAE for SARIMA (1139.5) and Naive (1160.33)."""
    res = get_metrics()
    assert res.holdout_months == 12
    assert res.primary_model_metrics.mae == pytest.approx(1139.5, abs=0.5)
    assert res.benchmark_metrics.mae == pytest.approx(1160.33, abs=0.5)
    assert res.relative_mae_improvement_pct == pytest.approx(1.8, abs=0.1)


def test_model_endpoint():
    """GET /api/v1/model must report approved SARIMA specification and known limitations."""
    res = get_model()
    assert res.selected_model == "SARIMA(1,1,1)(1,0,0)[12]"
    assert res.model_specification["order"] == [1, 1, 1]
    assert res.model_specification["seasonal_order"] == [1, 0, 0, 12]
    assert len(res.known_limitations) >= 3


def test_data_quality_endpoint():
    """GET /api/v1/data-quality must report 249 total months, 219 valid, and 30 missing."""
    res = get_data_quality()
    assert res.total_months == 249
    assert res.valid_observations == 219
    assert res.missing_data_block["months_count"] == 30
    assert res.missing_data_block["start"] == "2021-06-01"
    assert res.missing_data_block["end"] == "2023-11-01"


def test_history_endpoint():
    """GET /api/v1/history must return all 249 historical monthly points."""
    res = get_history()
    assert res.total_observations == 249
    assert res.history[0].date == "2005-01-01"
    assert res.history[-1].date == "2025-09-01"


def test_drift_endpoint_baseline_only(db_session):
    """GET /api/v1/monitoring/drift must report BASELINE_ONLY when no post-baseline runs exist."""
    # Temporarily remove any non-baseline runs
    db_session.query(ForecastRun).filter(ForecastRun.id != "stage3_approved_baseline").delete()
    db_session.commit()

    res = get_drift_status(db=db_session)
    assert res["status"] == "BASELINE_ONLY"
    assert res["forecast_drift"]["status"] == "NOT_EVALUATED"
    assert res["forecast_drift"]["drift_detected"] is False
    assert "No distinct post-baseline operational forecast run found" in res["forecast_drift"]["message"]


def test_drift_endpoint_after_pipeline_run(db_session):
    """GET /api/v1/monitoring/drift after pipeline run must evaluate genuine drift against Stage 3 baseline."""
    # Execute a pipeline run
    req = ForecastRunRequest(version_tag="drift_eval_run")
    run_res = trigger_forecast_run(req=req, db=db_session)
    assert run_res.status == "SUCCESS"

    res = get_drift_status(db=db_session)
    assert res["status"] == "DRIFT_EVALUATED"
    assert res["latest_run_id"] == run_res.run_id
    assert res["forecast_drift"]["drift_detected"] is False
    assert res["forecast_drift"]["status"] == "STABLE"


def test_drift_endpoint_detects_drift_when_shifted(db_session):
    """GET /api/v1/monitoring/drift must trigger DRIFT_ALERT when forecast shifts >15%."""
    # Create a synthetic shifted run in the database
    shifted_run_id = "run_test_shifted_divergence"
    run = ForecastRun(
        id=shifted_run_id,
        trigger_type="test_shift",
        status="SUCCESS",
        execution_time_ms=100,
        training_cutoff="2025-09-01",
        forecast_origin="2025-09-01",
        forecast_horizon="2025-10-01 to 2026-09-01",
    )
    db_session.add(run)
    db_session.flush()

    # Add points shifted by +30%
    future_months = [f"2025-{m:02d}-01" for m in range(10, 13)] + [f"2026-{m:02d}-01" for m in range(1, 10)]
    for m in future_months:
        pt = ForecastPoint(
            run_id=shifted_run_id,
            month=m,
            point_forecast=20000.0,  # ~30% higher than ~15,400 baseline
            lower_80=18000.0,
            upper_80=22000.0,
            lower_95=16000.0,
            upper_95=24000.0,
        )
        db_session.add(pt)
    db_session.commit()

    res = get_drift_status(db=db_session)
    assert res["status"] == "DRIFT_EVALUATED"
    assert res["forecast_drift"]["drift_detected"] is True
    assert res["forecast_drift"]["status"] == "DRIFT_ALERT"
    assert res["forecast_drift"]["mean_percentage_difference"] > 15.0

    # Clean up test run
    db_session.query(ForecastPoint).filter_by(run_id=shifted_run_id).delete()
    db_session.query(ForecastRun).filter_by(id=shifted_run_id).delete()
    db_session.commit()


def test_drift_endpoint_missing_baseline_error(monkeypatch, db_session, tmp_path):
    """GET /api/v1/monitoring/drift must raise 404 if baseline final_forecast.csv is missing."""
    import src.api.routes as routes_mod
    monkeypatch.setattr(routes_mod, "get_artifacts_dir", lambda: tmp_path)
    with pytest.raises(HTTPException) as exc_info:
        get_drift_status(db=db_session)
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_pipeline_run_endpoint(db_session):
    """POST /api/v1/forecast/run must execute pipeline and return success with parity."""
    req = ForecastRunRequest(version_tag="api_test_run")
    res = trigger_forecast_run(req=req, db=db_session)
    assert res.status == "SUCCESS"
    assert res.parity_verified is True
    assert res.mean_point_forecast == pytest.approx(15429.8, abs=0.5)
    assert "Parity with approved Stage 3 baseline confirmed" in res.message
