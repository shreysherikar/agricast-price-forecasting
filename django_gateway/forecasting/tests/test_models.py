"""
Unit tests for ForecastRun and ForecastPoint Django models.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from forecasting.models import ForecastRun, ForecastPoint


class ForecastModelTests(TestCase):
    def setUp(self):
        self.run = ForecastRun.objects.create(
            origin="2025-09",
            model_version="SARIMA(1,1,1)(1,0,0)[12]",
        )

    def test_forecast_run_creation(self):
        self.assertIsNotNone(self.run.id)
        self.assertEqual(self.run.origin, "2025-09")
        self.assertEqual(self.run.model_version, "SARIMA(1,1,1)(1,0,0)[12]")
        self.assertIn("ForecastRun", str(self.run))

    def test_forecast_point_valid_creation(self):
        point = ForecastPoint.objects.create(
            run=self.run,
            month="2025-10-01",
            point=15531.7,
            lower_80=14423.5,
            upper_80=16725.0,
            lower_95=13869.2,
            upper_95=17393.4,
        )
        point.full_clean()  # should not raise
        self.assertEqual(self.run.points.count(), 1)
        self.assertEqual(point.month, "2025-10-01")

    def test_forecast_point_invalid_interval_ordering_raises(self):
        # lower_80 > upper_80 violation
        point = ForecastPoint(
            run=self.run,
            month="2025-10-01",
            point=15000.0,
            lower_80=16000.0,  # Invalid: higher than point & upper
            upper_80=14000.0,
            lower_95=13000.0,
            upper_95=17000.0,
        )
        with self.assertRaises(ValidationError):
            point.full_clean()

    def test_forecast_point_negative_price_raises(self):
        point = ForecastPoint(
            run=self.run,
            month="2025-10-01",
            point=-100.0,
            lower_80=-200.0,
            upper_80=-50.0,
            lower_95=-300.0,
            upper_95=0.0,
        )
        with self.assertRaises(ValidationError):
            point.full_clean()

    def test_unique_run_month_constraint(self):
        ForecastPoint.objects.create(
            run=self.run,
            month="2025-10-01",
            point=15000.0,
            lower_80=14000.0,
            upper_80=16000.0,
            lower_95=13000.0,
            upper_95=17000.0,
        )
        with self.assertRaises(IntegrityError):
            ForecastPoint.objects.create(
                run=self.run,
                month="2025-10-01",
                point=15200.0,
                lower_80=14100.0,
                upper_80=16100.0,
                lower_95=13100.0,
                upper_95=17100.0,
            )

    def test_cascade_delete(self):
        ForecastPoint.objects.create(
            run=self.run,
            month="2025-10-01",
            point=15000.0,
            lower_80=14000.0,
            upper_80=16000.0,
            lower_95=13000.0,
            upper_95=17000.0,
        )
        self.assertEqual(ForecastPoint.objects.count(), 1)
        self.run.delete()
        self.assertEqual(ForecastPoint.objects.count(), 0)
