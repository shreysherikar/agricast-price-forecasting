"""
Automated tests for pipeline reproducibility, numerical parity, and concurrency locking.
"""
import pytest
import pandas as pd
import numpy as np

from src.pipeline.forecaster import ForecastingPipeline
from src.pipeline.model import SARIMAForecaster, NaiveForecaster
from src.pipeline.data_loader import load_raw_data, prepare_variant_b


@pytest.fixture
def variant_b(prices_csv_path):
    raw = load_raw_data(str(prices_csv_path))
    return prepare_variant_b(raw)


def test_pipeline_exact_stage3_parity(prices_csv_path, outputs_dir):
    """Pipeline execution must match approved Stage 3 outputs with max difference < 0.5."""
    pipeline = ForecastingPipeline(
        data_path=str(prices_csv_path),
        artifacts_dir=str(outputs_dir)
    )
    res = pipeline.run_pipeline(version_tag="automated_test")
    assert res["status"] == "SUCCESS"
    assert res["parity_verified"] is True
    assert res["parity_details"]["max_absolute_point_forecast_difference"] < 0.5
    assert res["mean_point_forecast"] == pytest.approx(15429.8, abs=0.5)
    assert res["holdout_mae"] == pytest.approx(1139.5, abs=0.5)


def test_sarima_model_specification(variant_b):
    """SARIMA model must use (1,1,1)x(1,0,0)[12] and rolling 120-month window."""
    model = SARIMAForecaster(window_size=120)
    assert model.order == (1, 1, 1)
    assert model.seasonal_order == (1, 0, 0, 12)
    assert model.window_size == 120

    model.fit(variant_b, cutoff_date="2025-09-01")
    p, l80, u80, l95, u95 = model.predict(steps=12)
    assert len(p) == 12
    assert p[0] > 10000.0


def test_naive_benchmark_flat_projection(variant_b):
    """Naive benchmark must project September 2024 price (14,363.0) flat across holdout."""
    naive = NaiveForecaster().fit(variant_b, cutoff_date="2024-09-01")
    assert naive.last_price == 14363.0
    preds = naive.predict(steps=12)
    assert len(preds) == 12
    assert (preds == 14363.0).all()


def test_sarima_rejects_unmasked_variant_a(prices_csv_path):
    """SARIMA fit must raise ValueError if passed unmasked data (Variant A) without 30 NaNs."""
    raw = load_raw_data(str(prices_csv_path))
    model = SARIMAForecaster(window_size=120)
    with pytest.raises(ValueError) as exc_info:
        model.fit(raw, cutoff_date="2025-09-01")
    assert "training requires approved Variant B" in str(exc_info.value)
    assert "strictly prohibited" in str(exc_info.value)


def test_pipeline_parity_contract_decoupling(prices_csv_path, tmp_path):
    """Pipeline must report PARITY_MISMATCH and parity_verified=False when output diverges from reference."""
    # Create a dummy reference forecast with artificially different values
    fake_ref = pd.DataFrame({
        "month": [f"2025-{m:02d}-01" for m in range(10, 13)] + [f"2026-{m:02d}-01" for m in range(1, 10)],
        "point_forecast": [9999.0] * 12,
        "lower_80": [8000.0] * 12,
        "upper_80": [12000.0] * 12,
        "lower_95": [7000.0] * 12,
        "upper_95": [13000.0] * 12,
    })
    fake_ref.to_csv(tmp_path / "final_forecast.csv", index=False)

    pipeline = ForecastingPipeline(
        data_path=str(prices_csv_path),
        artifacts_dir=str(tmp_path)
    )
    res = pipeline.run_pipeline(version_tag="divergence_test")

    # Execution succeeded and artifact is valid, but parity correctly reports mismatch
    assert res["execution_status"] == "COMPLETED"
    assert res["validation_status"] == "VALID"
    assert res["status"] == "PARITY_MISMATCH"
    assert res["parity_verified"] is False
    assert "PARITY MISMATCH" in res["message"]
    assert res["parity_details"]["max_absolute_point_forecast_difference"] > 100.0
