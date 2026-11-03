"""
Unit tests for FastAPIForecastService (caching, timeout, fallback, stale indicator).
"""
from unittest.mock import patch, MagicMock
import requests
from django.test import TestCase
from django.core.cache import cache
from forecasting.models import ForecastRun, ForecastPoint
from forecasting.services import (
    FastAPIForecastService,
    UpstreamServiceUnavailable,
    CACHE_KEY_LATEST_FORECAST,
)


class FastAPIForecastServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.run = ForecastRun.objects.create(
            origin="2025-09",
            model_version="SARIMA(1,1,1)(1,0,0)[12]",
        )
        self.point = ForecastPoint.objects.create(
            run=self.run,
            month="2025-10-01",
            point=15531.7,
            lower_80=14423.5,
            upper_80=16725.0,
            lower_95=13869.2,
            upper_95=17393.4,
        )

    def tearDown(self):
        cache.clear()

    @patch("forecasting.services.requests.get")
    def test_real_fastapi_response_shape_returns_all_points(self, mock_get):
        """Regression test: the FastAPI /api/v1/forecast endpoint returns its list under the key 'forecast'."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "forecast_origin": "2025-09-01",
            "origin_price": 15750.0,
            "model_name": "SARIMA(1,1,1)(1,0,0)[12]",
            "model_version": "SARIMA(1,1,1)(1,0,0)[12]",
            "mean_point_forecast": 15429.8,
            "forecast": [
                {"month": "2025-%02d-01" % m, "point_forecast": 15500.0 + m, "lower_80": 14000.0,
                 "upper_80": 17000.0, "lower_95": 13000.0, "upper_95": 18000.0}
                for m in range(10, 13)
            ],
        }
        mock_get.return_value = mock_resp

        res = FastAPIForecastService.get_latest_forecast(force_refresh=True)

        self.assertEqual(res["source"], "fastapi_live")
        self.assertEqual(len(res["points"]), 3)
        self.assertEqual(res["points"][0]["point"], 15510.0)

    @patch("forecasting.services.requests.get")
    def test_fastapi_successful_fresh_response_not_stale(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "model_version": "SARIMA(1,1,1)(1,0,0)[12]",
            "forecast_origin": "2025-09",
            "points": [
                {
                    "month": "2025-10-01",
                    "point_forecast": 15531.7,
                    "lower_80": 14423.5,
                    "upper_80": 16725.0,
                    "lower_95": 13869.2,
                    "upper_95": 17393.4,
                }
            ],
        }
        mock_get.return_value = mock_resp

        res = FastAPIForecastService.get_latest_forecast(force_refresh=True)

        self.assertFalse(res["stale"])
        self.assertEqual(res["source"], "fastapi_live")
        self.assertEqual(len(res["points"]), 1)
        self.assertEqual(res["points"][0]["point"], 15531.7)
        mock_get.assert_called_once()

        # Verify cached
        cached = cache.get(CACHE_KEY_LATEST_FORECAST)
        self.assertIsNotNone(cached)
        self.assertFalse(cached["stale"])

    @patch("forecasting.services.requests.get")
    def test_uses_cached_forecast_without_calling_upstream(self, mock_get):
        cache.set(
            CACHE_KEY_LATEST_FORECAST,
            {
                "model_version": "SARIMA",
                "origin": "2025-09",
                "stale": False,
                "source": "fastapi_live",
                "points": [{"month": "2025-10-01", "point": 15531.7}],
            },
            timeout=86400,
        )

        res = FastAPIForecastService.get_latest_forecast(force_refresh=False)
        self.assertFalse(res["stale"])
        self.assertEqual(res["points"][0]["point"], 15531.7)
        mock_get.assert_not_called()

    @patch("forecasting.services.requests.get")
    def test_fastapi_timeout_triggers_stale_fallback(self, mock_get):
        mock_get.side_effect = requests.Timeout("Connection timed out after 3.0s")

        res = FastAPIForecastService.get_latest_forecast(force_refresh=True)

        self.assertTrue(res["stale"])
        self.assertEqual(res["source"], "database_fallback")
        self.assertEqual(res["run_id"], self.run.id)
        self.assertEqual(len(res["points"]), 1)
        self.assertEqual(res["points"][0]["point"], 15531.7)

    @patch("forecasting.services.requests.get")
    def test_fastapi_500_error_triggers_stale_fallback(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_get.return_value = mock_resp

        res = FastAPIForecastService.get_latest_forecast(force_refresh=True)

        self.assertTrue(res["stale"])
        self.assertEqual(res["source"], "database_fallback")
        self.assertEqual(res["run_id"], self.run.id)

    @patch("forecasting.services.requests.get")
    def test_fastapi_failure_with_empty_database_raises_unavailable(self, mock_get):
        ForecastPoint.objects.all().delete()
        ForecastRun.objects.all().delete()

        mock_get.side_effect = requests.ConnectionError("Could not reach upstream")

        with self.assertRaises(UpstreamServiceUnavailable) as ctx:
            FastAPIForecastService.get_latest_forecast(force_refresh=True)

        self.assertIn("Upstream FastAPI failed", str(ctx.exception))
        self.assertIn("no stored ForecastRun exists", str(ctx.exception))
