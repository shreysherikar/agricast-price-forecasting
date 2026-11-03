"""
Data and artifact validation module.
Enforces strict schema, date continuity, numeric bounds, and prediction interval ordering.
Does NOT silently repair invalid data or artifacts; raises clear validation errors.
"""
from typing import Dict, Any, List
import pandas as pd
import numpy as np


class ValidationError(Exception):
    """Custom exception raised when data or artifact validation fails."""
    pass


class DatasetValidator:
    """Validates raw and Variant B price datasets."""

    @staticmethod
    def validate_raw(df: pd.DataFrame) -> Dict[str, Any]:
        """Validate raw prices dataset (Variant A)."""
        if not isinstance(df, pd.DataFrame):
            raise ValidationError("Input must be a pandas DataFrame.")

        required_cols = ["date", "avg_monthly_price"]
        for col in required_cols:
            if col not in df.columns:
                raise ValidationError(f"Missing required column in raw data: '{col}'")

        if len(df) != 249:
            raise ValidationError(f"Expected 249 monthly observations, found {len(df)}")

        # Check date sorting and duplicates
        if df["date"].duplicated().any():
            dup_dates = df.loc[df["date"].duplicated(), "date"].tolist()
            raise ValidationError(f"Duplicate dates found in raw dataset: {dup_dates}")

        # Check date range
        min_date = pd.to_datetime(df["date"].min())
        max_date = pd.to_datetime(df["date"].max())
        if min_date != pd.Timestamp("2005-01-01"):
            raise ValidationError(f"Expected start date 2005-01-01, found {min_date}")
        if max_date != pd.Timestamp("2025-09-01"):
            raise ValidationError(f"Expected end date 2025-09-01, found {max_date}")

        # Verify continuous monthly index
        expected_range = pd.date_range("2005-01-01", "2025-09-01", freq="MS")
        if not df["date"].equals(pd.Series(expected_range)):
            raise ValidationError("Dates do not match expected continuous month-start sequence.")

        # Check for positive finite values in raw data
        if df["avg_monthly_price"].isna().any():
            raise ValidationError("Raw dataset contains unexpected NaN values.")
        if (df["avg_monthly_price"] <= 0).any():
            raise ValidationError("Raw dataset contains non-positive price observations.")

        return {
            "status": "VALID",
            "observation_count": len(df),
            "start_date": min_date.strftime("%Y-%m-%d"),
            "end_date": max_date.strftime("%Y-%m-%d"),
        }

    @staticmethod
    def validate_variant_b(df: pd.DataFrame) -> Dict[str, Any]:
        """Validate Variant B (primary analytical series with 30-month unobserved gap)."""
        if not isinstance(df, pd.DataFrame):
            raise ValidationError("Input must be a pandas DataFrame.")

        required_cols = ["date", "avg_monthly_price"]
        for col in required_cols:
            if col not in df.columns:
                raise ValidationError(f"Missing required column in Variant B: '{col}'")

        if len(df) != 249:
            raise ValidationError(f"Expected 249 monthly observations in Variant B, found {len(df)}")

        # Check date sorting and duplicates
        if df["date"].duplicated().any():
            dup_dates = df.loc[df["date"].duplicated(), "date"].tolist()
            raise ValidationError(f"Duplicate dates found in Variant B: {dup_dates}")

        # Check date range
        min_date = pd.to_datetime(df["date"].min())
        max_date = pd.to_datetime(df["date"].max())
        if min_date != pd.Timestamp("2005-01-01"):
            raise ValidationError(f"Expected start date 2005-01-01, found {min_date}")
        if max_date != pd.Timestamp("2025-09-01"):
            raise ValidationError(f"Expected end date 2025-09-01, found {max_date}")

        # Verify continuous monthly index
        expected_range = pd.date_range("2005-01-01", "2025-09-01", freq="MS")
        if not df["date"].equals(pd.Series(expected_range)):
            raise ValidationError("Dates do not match expected continuous month-start sequence.")

        nan_mask = df["avg_monthly_price"].isna()
        nan_count = int(nan_mask.sum())
        if nan_count != 30:
            raise ValidationError(f"Variant B must have exactly 30 NaN months, found {nan_count}")

        nan_dates = df.loc[nan_mask, "date"]
        expected_nan_start = pd.Timestamp("2021-06-01")
        expected_nan_end = pd.Timestamp("2023-11-01")

        if nan_dates.min() != expected_nan_start or nan_dates.max() != expected_nan_end:
            raise ValidationError(
                f"Variant B NaN block must span {expected_nan_start} to {expected_nan_end}, "
                f"found {nan_dates.min()} to {nan_dates.max()}"
            )

        # Check that non-NaN observations are positive
        valid_prices = df.loc[~nan_mask, "avg_monthly_price"]
        if (valid_prices <= 0).any():
            raise ValidationError("Variant B contains non-positive price observations.")

        # Check December 2023 retention
        dec_2023 = df.loc[df["date"] == "2023-12-01", "avg_monthly_price"]
        if dec_2023.empty or pd.isna(dec_2023.iloc[0]):
            raise ValidationError("December 2023 must be present and observed in Variant B.")
        if dec_2023.iloc[0] != 16163.0:
            raise ValidationError(f"December 2023 price must be 16163.0, found {dec_2023.iloc[0]}")

        return {
            "status": "VALID",
            "total_months": len(df),
            "valid_observations": len(df) - nan_count,
            "missing_block_months": nan_count,
            "missing_block_start": expected_nan_start.strftime("%Y-%m-%d"),
            "missing_block_end": expected_nan_end.strftime("%Y-%m-%d"),
            "december_2023_price": float(dec_2023.iloc[0]),
        }


class ForecastArtifactValidator:
    """Validates final 12-month operational forecast CSV and interval tables."""

    EXPECTED_COLUMNS = ["month", "point_forecast", "lower_80", "upper_80", "lower_95", "upper_95"]
    EXPECTED_HORIZON_MONTHS = [
        "2025-10-01", "2025-11-01", "2025-12-01", "2026-01-01",
        "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01",
        "2026-06-01", "2026-07-01", "2026-08-01", "2026-09-01",
    ]

    @classmethod
    def validate_forecast_dataframe(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate schema, dates, numeric positivity, and interval bounds.
        Rule: lower_95 <= lower_80 <= point_forecast <= upper_80 <= upper_95.
        """
        if not isinstance(df, pd.DataFrame):
            raise ValidationError("Forecast artifact must be a pandas DataFrame.")

        # 1. Column Schema
        for col in cls.EXPECTED_COLUMNS:
            if col not in df.columns:
                raise ValidationError(f"Forecast artifact missing required column: '{col}'")

        # 2. Length (Exactly 12 months)
        if len(df) != 12:
            raise ValidationError(f"Forecast must contain exactly 12 months, found {len(df)}")

        # 3. Date Sequence and Duplicates
        month_list = [str(m).strip() for m in df["month"].tolist()]
        if len(month_list) != len(set(month_list)):
            raise ValidationError("Forecast contains duplicate month entries.")

        if month_list != cls.EXPECTED_HORIZON_MONTHS:
            raise ValidationError(
                f"Forecast months must exactly match October 2025 to September 2026.\n"
                f"Expected: {cls.EXPECTED_HORIZON_MONTHS}\nGot: {month_list}"
            )

        # 4. Check for NaNs or Infinities
        numeric_cols = ["point_forecast", "lower_80", "upper_80", "lower_95", "upper_95"]
        for col in numeric_cols:
            if df[col].isna().any():
                raise ValidationError(f"Forecast column '{col}' contains NaN values.")
            if not np.isfinite(df[col]).all():
                raise ValidationError(f"Forecast column '{col}' contains non-finite values.")
            if (df[col] <= 0).any():
                raise ValidationError(f"Forecast column '{col}' contains non-positive values.")

        # 5. Interval Ordering Validation
        # Condition: lower_95 <= lower_80 <= point_forecast <= upper_80 <= upper_95
        violations = []
        for idx, row in df.iterrows():
            m = row["month"]
            p = row["point_forecast"]
            l80, u80 = row["lower_80"], row["upper_80"]
            l95, u95 = row["lower_95"], row["upper_95"]

            if not (l95 <= l80 <= p <= u80 <= u95):
                violations.append(
                    f"Row {idx} ({m}): Interval ordering violation: "
                    f"lower_95 ({l95}) <= lower_80 ({l80}) <= point ({p}) "
                    f"<= upper_80 ({u80}) <= upper_95 ({u95}) failed."
                )

        if violations:
            raise ValidationError("\n".join(violations))

        return {
            "status": "VALID",
            "horizon_months": len(df),
            "start_month": month_list[0],
            "end_month": month_list[-1],
            "mean_point_forecast": float(df["point_forecast"].mean()),
            "min_point_forecast": float(df["point_forecast"].min()),
            "max_point_forecast": float(df["point_forecast"].max()),
        }
