"""
Automated unit and integration tests for data loading and Variant B preparation.
Verifies date continuity, 30-month unobserved block preservation, and zero interpolation.
"""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from src.pipeline.data_loader import load_raw_data, prepare_variant_b, get_series_segments
from src.pipeline.validator import DatasetValidator, ValidationError


@pytest.fixture
def raw_data(prices_csv_path):
    return load_raw_data(str(prices_csv_path))


@pytest.fixture
def variant_b(raw_data):
    return prepare_variant_b(raw_data)


def test_raw_data_schema(raw_data):
    """Raw data must contain exactly 'date' and 'avg_monthly_price'."""
    assert "date" in raw_data.columns
    assert "avg_monthly_price" in raw_data.columns
    assert len(raw_data) == 249


def test_raw_data_continuity(raw_data):
    """Raw series must span 2005-01-01 to 2025-09-01 without skipped months."""
    val = DatasetValidator.validate_raw(raw_data)
    assert val["status"] == "VALID"
    assert val["start_date"] == "2005-01-01"
    assert val["end_date"] == "2025-09-01"
    assert raw_data["date"].duplicated().sum() == 0


def test_raw_data_prices_positive(raw_data):
    """Raw price observations must be strictly positive and finite."""
    assert (raw_data["avg_monthly_price"] > 0).all()
    assert np.isfinite(raw_data["avg_monthly_price"]).all()


def test_variant_b_30_month_gap_preservation(variant_b):
    """Variant B must set exactly June 2021 to November 2023 (30 months) to NaN."""
    val = DatasetValidator.validate_variant_b(variant_b)
    assert val["status"] == "VALID"
    assert val["missing_block_months"] == 30
    assert val["missing_block_start"] == "2021-06-01"
    assert val["missing_block_end"] == "2023-11-01"
    assert val["valid_observations"] == 219


def test_variant_b_no_interpolation(variant_b):
    """Variant B must strictly NOT interpolate or bridge across the 30-month gap."""
    gap_prices = variant_b.loc[
        (variant_b["date"] >= "2021-06-01") & (variant_b["date"] <= "2023-11-01"),
        "avg_monthly_price"
    ]
    assert gap_prices.isna().all(), "All 30 months in gap must remain NaN"
    assert len(gap_prices) == 30


def test_variant_b_december_2023_retention(variant_b):
    """December 2023 price must be retained at 16,163.0."""
    dec_2023 = variant_b.loc[variant_b["date"] == "2023-12-01", "avg_monthly_price"]
    assert not dec_2023.empty
    assert dec_2023.iloc[0] == 16163.0


def test_series_segments(variant_b):
    """Verify segment split: Segment 1 (197m), Gap (30m), Segment 2 (22m)."""
    seg1, gap, seg2 = get_series_segments(variant_b)
    assert len(seg1) == 197
    assert len(gap) == 30
    assert len(seg2) == 22
    assert len(seg1) + len(gap) + len(seg2) == 249


def test_validator_rejects_altered_data():
    """Validator must reject datasets with missing dates or wrong NaN block."""
    bad_df = pd.DataFrame({
        "date": pd.date_range("2005-01-01", periods=10, freq="MS"),
        "avg_monthly_price": [100.0] * 10
    })
    with pytest.raises(ValidationError):
        DatasetValidator.validate_raw(bad_df)
