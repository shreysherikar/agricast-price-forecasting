"""
Django management command to ingest approved forecast CSV into ForecastRun and ForecastPoint records.
Validates required columns, date formats, numeric validity, and interval ordering.
Prevents accidental duplicate ingestion.
"""
import os
import csv
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from forecasting.models import ForecastRun, ForecastPoint

REQUIRED_COLUMNS = [
    "month",
    "point_forecast",
    "lower_80",
    "upper_80",
    "lower_95",
    "upper_95",
]


class Command(BaseCommand):
    help = "Ingest verified outputs/final_forecast.csv into ForecastRun and ForecastPoint models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="Path to final_forecast.csv (defaults to auto-resolving outputs/final_forecast.csv)",
        )
        parser.add_argument(
            "--origin",
            type=str,
            default="2025-09",
            help="Forecast origin period (default: 2025-09)",
        )
        parser.add_argument(
            "--model-version",
            type=str,
            default="SARIMA(1,1,1)(1,0,0)[12]",
            help="Model architecture and order specification",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force ingestion even if an existing run with the same origin exists",
        )

    def resolve_csv_path(self, user_path: Optional[str]) -> Path:
        if user_path:
            p = Path(user_path)
            if not p.is_file():
                raise CommandError(f"Specified CSV file not found: {p}")
            return p

        # Check candidate locations
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        candidates = [
            base_dir / "outputs" / "final_forecast.csv",
            base_dir.parent / "outputs" / "final_forecast.csv",
            Path("outputs/final_forecast.csv"),
        ]
        for cand in candidates:
            if cand.is_file():
                return cand.resolve()

        raise CommandError(
            f"Could not locate outputs/final_forecast.csv. Checked: {[str(c) for c in candidates]}"
        )

    def handle(self, *args, **options):
        csv_path = self.resolve_csv_path(options.get("file"))
        origin = options.get("origin", "2025-09").strip()
        model_version = options.get("model_version", "SARIMA(1,1,1)(1,0,0)[12]").strip()
        force = options.get("force", False)

        self.stdout.write(f"Reading forecast CSV from: {csv_path}")

        # Check for duplicate ingestion
        existing = ForecastRun.objects.filter(origin=origin, model_version=model_version)
        if existing.exists() and not force:
            latest = existing.first()
            raise CommandError(
                f"Duplicate ingestion prevented: ForecastRun for origin '{origin}' and model '{model_version}' "
                f"already exists (id={latest.id}, created={latest.created_at}). "
                f"Pass --force to ingest an additional run."
            )

        # Parse and validate CSV
        points_data = []
        try:
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames or []

                missing_cols = [c for c in REQUIRED_COLUMNS if c not in header]
                if missing_cols:
                    raise CommandError(
                        f"Malformed CSV: missing required columns {missing_cols}. Header was: {header}"
                    )

                for row_idx, row in enumerate(reader, start=2):
                    # Validate month format
                    month_raw = (row.get("month") or "").strip()
                    try:
                        dt = datetime.datetime.strptime(month_raw, "%Y-%m-%d")
                    except ValueError:
                        raise CommandError(
                            f"Malformed date in row {row_idx}: '{month_raw}'. Must be YYYY-MM-DD."
                        )

                    # Validate numeric fields
                    try:
                        pt = float(row["point_forecast"])
                        l80 = float(row["lower_80"])
                        u80 = float(row["upper_80"])
                        l95 = float(row["lower_95"])
                        u95 = float(row["upper_95"])
                    except (ValueError, TypeError, KeyError) as e:
                        raise CommandError(
                            f"Malformed numeric value in row {row_idx} ({month_raw}): {e}"
                        )

                    if pt <= 0:
                        raise CommandError(
                            f"Invalid non-positive forecast in row {row_idx} ({month_raw}): {pt}"
                        )

                    # Interval ordering validation
                    if not (l95 <= l80 <= pt <= u80 <= u95):
                        raise CommandError(
                            f"Invalid interval ordering in row {row_idx} ({month_raw}): "
                            f"expected lower_95 ({l95}) <= lower_80 ({l80}) <= point ({pt}) <= "
                            f"upper_80 ({u80}) <= upper_95 ({u95})"
                        )

                    points_data.append({
                        "month": month_raw,
                        "point": pt,
                        "lower_80": l80,
                        "upper_80": u80,
                        "lower_95": l95,
                        "upper_95": u95,
                    })

        except OSError as e:
            raise CommandError(f"Failed to read CSV file {csv_path}: {e}")

        if not points_data:
            raise CommandError(f"Forecast CSV is empty: {csv_path}")

        # Atomic persistence
        with transaction.atomic():
            run = ForecastRun.objects.create(
                origin=origin,
                model_version=model_version,
            )
            created_points = [
                ForecastPoint(
                    run=run,
                    month=item["month"],
                    point=item["point"],
                    lower_80=item["lower_80"],
                    upper_80=item["upper_80"],
                    lower_95=item["lower_95"],
                    upper_95=item["upper_95"],
                )
                for item in points_data
            ]
            ForecastPoint.objects.bulk_create(created_points)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully ingested {len(created_points)} forecast points into "
                f"ForecastRun id={run.id} (origin={run.origin}, model={run.model_version})."
            )
        )
