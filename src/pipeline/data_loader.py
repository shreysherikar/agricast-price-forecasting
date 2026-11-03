"""
Data loading and Variant B preparation module.
Preserves original calendar spacing and represents the confirmed 30-month
copied block (June 2021 to November 2023) as unobserved NaNs without interpolation.
"""
import os
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import pandas as pd


def get_default_data_path() -> Path:
    """Resolve default path to data/prices.csv based on repository root."""
    for candidate in [
        Path("data/prices.csv"),
        Path("forecasting-project/data/prices.csv"),
        Path(__file__).resolve().parent.parent.parent / "data" / "prices.csv",
    ]:
        if candidate.exists():
            return candidate
    return Path("data/prices.csv")


def load_raw_data(csv_path: Optional[str] = None) -> pd.DataFrame:
    """
    Load raw historical prices.csv and validate basic structure.
    Expected: 249 monthly observations from 2005-01-01 to 2025-09-01.
    """
    path = Path(csv_path) if csv_path else get_default_data_path()
    if not path.exists():
        raise FileNotFoundError(f"Source price data not found at: {path}")

    df = pd.read_csv(path)
    if "date" not in df.columns or "avg_monthly_price" not in df.columns:
        raise ValueError(f"Unexpected columns in {path}: {list(df.columns)}")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["avg_monthly_price"] = df["avg_monthly_price"].astype(float)
    return df


def prepare_variant_b(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare approved primary Variant B:
    - Sets 2021-06-01 through 2023-11-01 (30 months) to NaN.
    - Preserves December 2023 (16,163.0) and all calendar spacing.
    - Strictly avoids artificial interpolation or bridging across the gap.
    """
    df = df_raw.copy()
    df["date"] = pd.to_datetime(df["date"])
    gap_start = pd.Timestamp("2021-06-01")
    gap_end = pd.Timestamp("2023-11-01")
    gap_mask = (df["date"] >= gap_start) & (df["date"] <= gap_end)
    df.loc[gap_mask, "avg_monthly_price"] = np.nan
    df["variant"] = "B"
    nan_count = int(df.loc[gap_mask, "avg_monthly_price"].isna().sum())
    if nan_count != 30:
        raise ValueError(f"CRITICAL: Variant B gap mask must contain exactly 30 NaN months, found {nan_count}")
    return df


def load_variant_b(csv_path: Optional[str] = None) -> pd.DataFrame:
    """
    Load Variant B series directly from outputs/variant_B_nan_block.csv if available,
    or prepare it deterministically from raw data/prices.csv.
    Guarantees exactly 30 unobserved NaN months in 2021-06-01 to 2023-11-01.
    """
    if csv_path:
        p = Path(csv_path)
        if p.exists():
            df = pd.read_csv(p)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            gap_mask = (df["date"] >= pd.Timestamp("2021-06-01")) & (df["date"] <= pd.Timestamp("2023-11-01"))
            if df.loc[gap_mask, "avg_monthly_price"].isna().sum() == 30:
                df["variant"] = "B"
                return df
            return prepare_variant_b(df)

    for candidate in [
        Path("outputs/variant_B_nan_block.csv"),
        Path("forecasting-project/outputs/variant_B_nan_block.csv"),
        Path(__file__).resolve().parent.parent.parent / "outputs" / "variant_B_nan_block.csv",
    ]:
        if candidate.exists():
            df = pd.read_csv(candidate)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            gap_mask = (df["date"] >= pd.Timestamp("2021-06-01")) & (df["date"] <= pd.Timestamp("2023-11-01"))
            if df.loc[gap_mask, "avg_monthly_price"].isna().sum() == 30:
                df["variant"] = "B"
                return df

    raw = load_raw_data()
    return prepare_variant_b(raw)


def get_series_segments(df_variant_b: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Extract Segment 1 (pre-gap), Missing Block, and Segment 2 (post-gap).
    """
    seg1 = df_variant_b[df_variant_b["date"] <= "2021-05-01"].copy()
    gap = df_variant_b[(df_variant_b["date"] >= "2021-06-01") & (df_variant_b["date"] <= "2023-11-01")].copy()
    seg2 = df_variant_b[df_variant_b["date"] >= "2023-12-01"].copy()
    return seg1, gap, seg2
