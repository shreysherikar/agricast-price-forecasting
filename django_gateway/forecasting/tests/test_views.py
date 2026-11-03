"""
Integration tests for Django REST API endpoints (GET /api/forecast/latest/ and /api/health/).
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache

from forecasting.models import ForecastRun, ForecastPoint


class ForecastAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
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
    def test_get_latest_forecast_live_success(self, mock_get):
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

        url = reverse("forecast-latest")
        response = self.client.get(url, {"force_refresh": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data["stale"])
        self.assertEqual(data["source"], "fastapi_live")
        self.assertEqual(data["origin"], "2025-09")
        self.assertEqual(len(data["points"]), 1)
        self.assertEqual(data["points"][0]["point"], 15531.7)

    @patch("forecasting.services.requests.get")
    def test_get_latest_forecast_fallback_stale(self, mock_get):
        mock_get.side_effect = Exception("FastAPI service unreachable")

        url = reverse("forecast-latest")
        response = self.client.get(url, {"force_refresh": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["stale"])
        self.assertEqual(data["source"], "database_fallback")
        self.assertEqual(data["run_id"], self.run.id)
        self.assertEqual(len(data["points"]), 1)
        self.assertEqual(data["points"][0]["point"], 15531.7)

    @patch("forecasting.services.requests.get")
    def test_get_latest_forecast_empty_db_and_upstream_failure(self, mock_get):
        ForecastPoint.objects.all().delete()
        ForecastRun.objects.all().delete()
        mock_get.side_effect = Exception("FastAPI offline")

        url = reverse("forecast-latest")
        response = self.client.get(url, {"force_refresh": "true"})

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        data = response.json()
        self.assertTrue(data["stale"])
        self.assertIn("detail", data)

    def test_health_endpoint(self):
        url = reverse("gateway-health")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertTrue(data["database_connected"])
