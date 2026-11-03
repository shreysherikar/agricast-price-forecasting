"""
Unit tests for load_forecast Django management command.
"""
import tempfile
import os
from io import StringIO
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from forecasting.models import ForecastRun, ForecastPoint


class LoadForecastCommandTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_csv(self, filename: str, content: str) -> str:
        filepath = os.path.join(self.temp_dir.name, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def test_load_valid_csv_successfully(self):
        valid_content = (
            "month,point_forecast,lower_80,upper_80,lower_95,upper_95\n"
            "2025-10-01,15531.7,14423.5,16725.0,13869.2,17393.4\n"
            "2025-11-01,15411.2,13901.0,17085.5,13162.5,18044.2\n"
        )
        csv_path = self.create_csv("valid.csv", valid_content)
        out = StringIO()
        call_command("load_forecast", file=csv_path, origin="2025-09", stdout=out)

        self.assertIn("Successfully ingested 2 forecast points", out.getvalue())
        self.assertEqual(ForecastRun.objects.count(), 1)
        run = ForecastRun.objects.first()
        self.assertEqual(run.origin, "2025-09")
        self.assertEqual(run.points.count(), 2)

    def test_duplicate_ingestion_prevented(self):
        valid_content = (
            "month,point_forecast,lower_80,upper_80,lower_95,upper_95\n"
            "2025-10-01,15531.7,14423.5,16725.0,13869.2,17393.4\n"
        )
        csv_path = self.create_csv("valid.csv", valid_content)
        call_command("load_forecast", file=csv_path, origin="2025-09")

        # Second run without --force should fail
        with self.assertRaises(CommandError) as ctx:
            call_command("load_forecast", file=csv_path, origin="2025-09")
        self.assertIn("Duplicate ingestion prevented", str(ctx.exception))

        # With --force it should succeed
        out = StringIO()
        call_command("load_forecast", file=csv_path, origin="2025-09", force=True, stdout=out)
        self.assertIn("Successfully ingested", out.getvalue())
        self.assertEqual(ForecastRun.objects.count(), 2)

    def test_missing_required_columns_rejected(self):
        bad_content = (
            "month,point_forecast,lower_80\n"
            "2025-10-01,15531.7,14423.5\n"
        )
        csv_path = self.create_csv("missing_cols.csv", bad_content)
        with self.assertRaises(CommandError) as ctx:
            call_command("load_forecast", file=csv_path)
        self.assertIn("missing required columns", str(ctx.exception))

    def test_malformed_date_rejected(self):
        bad_content = (
            "month,point_forecast,lower_80,upper_80,lower_95,upper_95\n"
            "10/01/2025,15531.7,14423.5,16725.0,13869.2,17393.4\n"
        )
        csv_path = self.create_csv("bad_date.csv", bad_content)
        with self.assertRaises(CommandError) as ctx:
            call_command("load_forecast", file=csv_path)
        self.assertIn("Malformed date", str(ctx.exception))

    def test_malformed_numeric_rejected(self):
        bad_content = (
            "month,point_forecast,lower_80,upper_80,lower_95,upper_95\n"
            "2025-10-01,not_a_number,14423.5,16725.0,13869.2,17393.4\n"
        )
        csv_path = self.create_csv("bad_num.csv", bad_content)
        with self.assertRaises(CommandError) as ctx:
            call_command("load_forecast", file=csv_path)
        self.assertIn("Malformed numeric", str(ctx.exception))

    def test_invalid_interval_ordering_rejected(self):
        bad_content = (
            "month,point_forecast,lower_80,upper_80,lower_95,upper_95\n"
            "2025-10-01,15531.7,17000.0,16725.0,13869.2,17393.4\n"
        )
        csv_path = self.create_csv("bad_order.csv", bad_content)
        with self.assertRaises(CommandError) as ctx:
            call_command("load_forecast", file=csv_path)
        self.assertIn("Invalid interval ordering", str(ctx.exception))

    def test_empty_csv_rejected(self):
        bad_content = "month,point_forecast,lower_80,upper_80,lower_95,upper_95\n"
        csv_path = self.create_csv("empty.csv", bad_content)
        with self.assertRaises(CommandError) as ctx:
            call_command("load_forecast", file=csv_path)
        self.assertIn("empty", str(ctx.exception).lower())
