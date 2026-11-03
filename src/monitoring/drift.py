"""
Drift monitoring and model degradation alert module.
Provides architectural frameworks for data drift, forecast distribution drift,
and post-horizon error tracking when actual observations arrive in the future.

NOTE: Real observations beyond September 2025 are currently unobserved.
All monitoring capabilities herein are architectural implementations designed to ingest
future prices as they occur, without fabricating or simulating real drift results.
"""
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


class DriftMonitor:
    """
    Monitors input data distributions, forecast stability, and prospective error tracking.
    """

    @staticmethod
    def check_forecast_distribution_drift(
        new_forecast: pd.DataFrame,
        baseline_forecast: pd.DataFrame,
        max_allowed_divergence_pct: float = 15.0
    ) -> Dict[str, Any]:
        """
        Compare newly generated 12-month forecast against the approved Stage 3 baseline.
        Checks for unexpected shifts in point forecast trajectory or interval widths.
        """
        p_new = new_forecast["point_forecast"].values
        p_base = baseline_forecast["point_forecast"].values

        mean_diff = float(np.mean(p_new - p_base))
        pct_diff = float(100.0 * np.mean(np.abs(p_new - p_base) / p_base))
        max_pt_diff = float(np.max(np.abs(p_new - p_base)))

        # Interval width comparison
        w_new_80 = float(np.mean(new_forecast["upper_80"].values - new_forecast["lower_80"].values))
        w_base_80 = float(np.mean(baseline_forecast["upper_80"].values - baseline_forecast["lower_80"].values))
        w_ratio = round(w_new_80 / w_base_80, 3) if w_base_80 > 0 else 1.0

        drift_detected = pct_diff > max_allowed_divergence_pct

        return {
            "monitoring_capability": "Forecast Distribution Drift",
            "drift_detected": drift_detected,
            "mean_point_difference": round(mean_diff, 2),
            "mean_percentage_difference": round(pct_diff, 2),
            "max_point_difference": round(max_pt_diff, 2),
            "interval_width_ratio_80": w_ratio,
            "status": "DRIFT_ALERT" if drift_detected else "STABLE",
            "note": "Evaluated against approved Stage 3 forecast baseline.",
        }

    @staticmethod
    def evaluate_future_actuals_schema(
        forecast_df: pd.DataFrame,
        new_actuals: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Framework for prospective error monitoring when post-September-2025 prices become available.
        Input: new_actuals dictionary { "2025-10-01": price, ... }
        """
        if not new_actuals:
            return {
                "monitoring_status": "AWAITING_FUTURE_OBSERVATIONS",
                "observed_months_count": 0,
                "message": "No observed prices available beyond 2025-09-01. Monitoring framework ready to ingest actuals.",
            }

        comparisons = []
        for month, actual in new_actuals.items():
            match = forecast_df[forecast_df["month"] == month]
            if not match.empty:
                pred = float(match["point_forecast"].iloc[0])
                l80, u80 = float(match["lower_80"].iloc[0]), float(match["upper_80"].iloc[0])
                l95, u95 = float(match["lower_95"].iloc[0]), float(match["upper_95"].iloc[0])
                err = pred - actual
                in_80 = l80 <= actual <= u80
                in_95 = l95 <= actual <= u95
                comparisons.append({
                    "month": month,
                    "actual": actual,
                    "predicted": pred,
                    "error": round(err, 2),
                    "abs_error": round(abs(err), 2),
                    "in_80_ci": in_80,
                    "in_95_ci": in_95,
                })

        if not comparisons:
            return {
                "monitoring_status": "NO_MATCHING_MONTHS",
                "observed_months_count": 0,
            }

        df_comp = pd.DataFrame(comparisons)
        mae = float(df_comp["abs_error"].mean())
        bias = float(df_comp["error"].mean())
        coverage_80 = float(df_comp["in_80_ci"].mean() * 100.0)
        coverage_95 = float(df_comp["in_95_ci"].mean() * 100.0)

        return {
            "monitoring_status": "ACTIVE_EVALUATION",
            "observed_months_count": len(df_comp),
            "prospective_mae": round(mae, 2),
            "prospective_bias": round(bias, 2),
            "empirical_coverage_80_pct": round(coverage_80, 1),
            "empirical_coverage_95_pct": round(coverage_95, 1),
            "monthly_breakdown": comparisons,
        }


class RetrainingTriggerChecker:
    """
    Evaluates explicit criteria required to trigger formal model retraining.
    Retraining must never occur automatically on synthetic or unvalidated data.
    """

    CRITERIA = {
        "CRITERION_1_DEGRADATION": "Model MAE exceeds Naive baseline for 3 consecutive newly observed months.",
        "CRITERION_2_PERSISTENT_BIAS": "Mean signed error (bias) exceeds 1,500 units for 3 consecutive months.",
        "CRITERION_3_REGIME_BREAK": "Single-month price change exceeds 35% or 3-month rolling volatility triples.",
        "CRITERION_4_SAMPLE_SUFFICIENCY": "At least 12 new verified, contiguous monthly observations have accumulated.",
    }

    @classmethod
    def evaluate_triggers(
        cls,
        new_actuals_count: int = 0,
        consecutive_degradation_months: int = 0,
        consecutive_bias_months: int = 0,
        regime_break_detected: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluate retraining decision logic against operational rules.
        """
        triggers_active = []

        if consecutive_degradation_months >= 3:
            triggers_active.append("CRITERION_1_DEGRADATION")
        if consecutive_bias_months >= 3:
            triggers_active.append("CRITERION_2_PERSISTENT_BIAS")
        if regime_break_detected:
            triggers_active.append("CRITERION_3_REGIME_BREAK")

        sufficient_sample = new_actuals_count >= 12
        recommend_retrain = bool(triggers_active and sufficient_sample)

        return {
            "recommend_retraining": recommend_retrain,
            "sufficient_new_observations": sufficient_sample,
            "new_observations_count": new_actuals_count,
            "active_triggers": triggers_active,
            "operational_policy": (
                "Automatic retraining prohibited. Any retraining requires human review of new data, "
                "re-estimation of stationarity and seasonality diagnostics, and validation against benchmarks."
            ),
            "criteria_definitions": cls.CRITERIA,
        }
