"""
Django REST Framework views for the forecasting gateway.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .services import FastAPIForecastService, UpstreamServiceUnavailable
from .serializers import LatestForecastResponseSerializer


class LatestForecastView(APIView):
    """
    GET /api/forecast/latest/
    Returns the latest 12-month operational forecast, intervals, model version,
    forecast origin, and stale indicator.
    """
    def get(self, request, *args, **kwargs):
        force_refresh = request.query_params.get("force_refresh", "false").lower() in ("true", "1")
        try:
            forecast_data = FastAPIForecastService.get_latest_forecast(force_refresh=force_refresh)
            serializer = LatestForecastResponseSerializer(data=forecast_data)
            if serializer.is_valid():
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(forecast_data, status=status.HTTP_200_OK)
        except UpstreamServiceUnavailable as e:
            return Response(
                {
                    "error": "Service Unavailable",
                    "detail": str(e),
                    "stale": True,
                    "points": [],
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            return Response(
                {
                    "error": "Internal Server Error",
                    "detail": str(e),
                    "stale": True,
                    "points": [],
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class HealthCheckView(APIView):
    """
    GET /api/health/
    Health status of the Django gateway and database connectivity.
    """
    def get(self, request, *args, **kwargs):
        from django.db import connection
        db_ok = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            db_ok = False

        return Response(
            {
                "status": "HEALTHY" if db_ok else "DEGRADED",
                "service": "django_gateway",
                "database_connected": db_ok,
            },
            status=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
