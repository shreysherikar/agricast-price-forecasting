"""
Automated unit tests for forecast artifact schemas, interval ordering, and serialization.
"""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from src.pipeline.validator import ForecastArtifactValidator, ValidationError


@pytest.fixture
def approved_forecast(outputs_dir):
    return pd.read_csv(outputs_dir / "final_forecast.csv")


def test_forecast_schema_and_columns(approved_forecast):
    """Artifact must contain exactly 12 months with required column names."""
    expected_cols = ["month", "point_forecast", "lower_80", "upper_80", "lower_95", "upper_95"]
    assert list(approved_forecast.columns) == expected_cols
    assert len(approved_forecast) == 12


def test_forecast_dates_horizon(approved_forecast):
    """Forecast dates must strictly be October 2025 to September 2026."""
    val = ForecastArtifactValidator.validate_forecast_dataframe(approved_forecast)
    assert val["status"] == "VALID"
    assert val["start_month"] == "2025-10-01"
    assert val["end_month"] == "2026-09-01"
    assert val["horizon_months"] == 12


def test_interval_ordering(approved_forecast):
    """Must strictly satisfy: lower_95 <= lower_80 <= point_forecast <= upper_80 <= upper_95."""
    for _, row in approved_forecast.iterrows():
        p = row["point_forecast"]
        l80, u80 = row["lower_80"], row["upper_80"]
        l95, u95 = row["lower_95"], row["upper_95"]
        assert l95 <= l80 <= p <= u80 <= u95, f"Ordering failed for month {row['month']}"


def test_no_missing_or_non_positive_forecast_values(approved_forecast):
    """No NaNs or non-positive price predictions allowed."""
    assert not approved_forecast.isna().any().any()
    numeric_cols = ["point_forecast", "lower_80", "upper_80", "lower_95", "upper_95"]
    assert (approved_forecast[numeric_cols] > 0).all().all()


def test_validator_rejects_interval_ordering_violation():
    """Validator must reject forecasts where lower bound exceeds point forecast."""
    bad_df = pd.DataFrame({
        "month": ForecastArtifactValidator.EXPECTED_HORIZON_MONTHS,
        "point_forecast": [15000.0] * 12,
        "lower_80": [16000.0] * 12,  # VIOLATION: lower > point
        "upper_80": [17000.0] * 12,
        "lower_95": [14000.0] * 12,
        "upper_95": [18000.0] * 12,
    })
    with pytest.raises(ValidationError, match="Interval ordering violation"):
        ForecastArtifactValidator.validate_forecast_dataframe(bad_df)


def test_validator_rejects_wrong_horizon_length():
    """Validator must reject forecasts with other than 12 months."""
    bad_df = pd.DataFrame({
        "month": ForecastArtifactValidator.EXPECTED_HORIZON_MONTHS[:6],
        "point_forecast": [15000.0] * 6,
        "lower_80": [14000.0] * 6,
        "upper_80": [16000.0] * 6,
        "lower_95": [13000.0] * 6,
        "upper_95": [17000.0] * 6,
    })
    with pytest.raises(ValidationError, match="exactly 12 months"):
        ForecastArtifactValidator.validate_forecast_dataframe(bad_df)
