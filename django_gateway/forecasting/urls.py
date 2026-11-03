"""
Forecasting app URL routes.
"""
from django.urls import path
from .views import LatestForecastView, HealthCheckView

urlpatterns = [
    path("forecast/latest/", LatestForecastView.as_view(), name="forecast-latest"),
    path("health/", HealthCheckView.as_view(), name="gateway-health"),
]
