"""
Automated unit tests for drift monitoring and retraining trigger evaluations.
"""
import pytest
import pandas as pd
from src.monitoring.drift import DriftMonitor, RetrainingTriggerChecker


@pytest.fixture
def baseline_forecast(outputs_dir):
    return pd.read_csv(outputs_dir / "final_forecast.csv")


def test_forecast_distribution_drift_no_drift(baseline_forecast):
    """Identical forecasts must show zero drift and STABLE status."""
    res = DriftMonitor.check_forecast_distribution_drift(baseline_forecast, baseline_forecast)
    assert res["drift_detected"] is False
    assert res["status"] == "STABLE"
    assert res["mean_point_difference"] == 0.0


def test_forecast_distribution_drift_detected(baseline_forecast):
    """Shifted forecast (>15% divergence) must trigger DRIFT_ALERT."""
    shifted = baseline_forecast.copy()
    shifted["point_forecast"] = shifted["point_forecast"] * 1.25  # +25% jump
    res = DriftMonitor.check_forecast_distribution_drift(shifted, baseline_forecast)
    assert res["drift_detected"] is True
    assert res["status"] == "DRIFT_ALERT"


def test_future_actuals_monitoring_awaiting():
    """When no actuals are passed, monitoring status is AWAITING_FUTURE_OBSERVATIONS."""
    res = DriftMonitor.evaluate_future_actuals_schema(pd.DataFrame(), {})
    assert res["monitoring_status"] == "AWAITING_FUTURE_OBSERVATIONS"
    assert res["observed_months_count"] == 0


def test_future_actuals_monitoring_active(baseline_forecast):
    """When hypothetical verified prices are passed, calculates MAE and interval coverage."""
    synthetic_actuals = {
        "2025-10-01": 15500.0,
        "2025-11-01": 15400.0,
    }
    res = DriftMonitor.evaluate_future_actuals_schema(baseline_forecast, synthetic_actuals)
    assert res["monitoring_status"] == "ACTIVE_EVALUATION"
    assert res["observed_months_count"] == 2
    assert "prospective_mae" in res
    assert res["empirical_coverage_80_pct"] == 100.0


def test_retraining_trigger_no_retrain():
    """Insufficient new observations (<12) must NOT recommend retraining."""
    res = RetrainingTriggerChecker.evaluate_triggers(new_actuals_count=5)
    assert res["recommend_retraining"] is False
    assert res["sufficient_new_observations"] is False


def test_retraining_trigger_recommend_retrain():
    """Sufficient data (>=12) and sustained degradation (>=3 months) triggers retraining recommendation."""
    res = RetrainingTriggerChecker.evaluate_triggers(
        new_actuals_count=12,
        consecutive_degradation_months=3
    )
    assert res["recommend_retraining"] is True
    assert "CRITERION_1_DEGRADATION" in res["active_triggers"]
