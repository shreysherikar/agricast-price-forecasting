"""
Django models for price forecasting runs and interval points.
"""
from django.db import models
from django.db.models import Q, F
from django.core.exceptions import ValidationError


class ForecastRun(models.Model):
    """
    Represents an executed or ingested forecasting run.
    Contains run metadata, model provenance, and origin timestamp.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    model_version = models.CharField(
        max_length=64,
        default="SARIMA(1,1,1)(1,0,0)[12]",
        help_text="Model architecture and order specification",
    )
    origin = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Forecast origin period, e.g., 2025-09",
    )

    class Meta:
        db_table = "django_forecast_runs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["origin", "-created_at"], name="idx_forecast_origin_created"),
        ]

    def __str__(self) -> str:
        return f"ForecastRun(id={self.id}, origin={self.origin}, model={self.model_version}, created={self.created_at})"


class ForecastPoint(models.Model):
    """
    Represents a single monthly forecast point and associated prediction intervals.
    Enforces interval ordering constraints: lower_95 <= lower_80 <= point <= upper_80 <= upper_95.
    """
    run = models.ForeignKey(
        ForecastRun,
        on_delete=models.CASCADE,
        related_name="points",
        db_index=True,
    )
    month = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Target month formatted as YYYY-MM-DD",
    )
    point = models.FloatField(help_text="Central point forecast value")
    lower_80 = models.FloatField(help_text="Lower bound of 80% prediction interval")
    upper_80 = models.FloatField(help_text="Upper bound of 80% prediction interval")
    lower_95 = models.FloatField(help_text="Lower bound of 95% prediction interval")
    upper_95 = models.FloatField(help_text="Upper bound of 95% prediction interval")

    class Meta:
        db_table = "django_forecast_points"
        ordering = ["month"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "month"],
                name="unique_run_month",
            ),
            models.CheckConstraint(
                condition=(
                    Q(lower_95__lte=F("lower_80"))
                    & Q(lower_80__lte=F("point"))
                    & Q(point__lte=F("upper_80"))
                    & Q(upper_80__lte=F("upper_95"))
                ),
                name="valid_interval_ordering",
            ),
            models.CheckConstraint(
                condition=Q(point__gt=0),
                name="positive_point_forecast",
            ),
        ]
        indexes = [
            models.Index(fields=["run", "month"], name="idx_run_month"),
        ]

    def clean(self):
        super().clean()
        if self.point is not None and self.point <= 0:
            raise ValidationError("point must be strictly positive.")
        if not (self.lower_95 <= self.lower_80 <= self.point <= self.upper_80 <= self.upper_95):
            raise ValidationError(
                f"Invalid interval ordering: expected lower_95 ({self.lower_95}) <= "
                f"lower_80 ({self.lower_80}) <= point ({self.point}) <= "
                f"upper_80 ({self.upper_80}) <= upper_95 ({self.upper_95})"
            )

    def __str__(self) -> str:
        return f"ForecastPoint(run_id={self.run_id}, month={self.month}, point={self.point})"
