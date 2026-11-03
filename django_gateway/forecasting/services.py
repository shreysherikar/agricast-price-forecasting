"""
FastAPI Forecast Integration Service.
Calls the upstream FastAPI forecasting service with strict 3-second timeout,
1-day caching, and automatic graceful fallback to the latest stored ForecastRun
with a clear stale=True indicator.
"""
import logging
from typing import Dict, Any, Optional
import requests
from django.conf import settings
from django.core.cache import cache
from .models import ForecastRun

logger = logging.getLogger(__name__)

CACHE_KEY_LATEST_FORECAST = "fastapi_latest_forecast_cache"


class ForecastServiceError(Exception):
    """Base error for forecast service failures."""
    pass


class UpstreamServiceUnavailable(ForecastServiceError):
    """Raised when upstream FastAPI is unavailable and no database fallback exists."""
    pass


class FastAPIForecastService:
    @classmethod
    def get_latest_forecast(cls, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Retrieve the latest 12-month forecast.
        1. Checks 1-day cache unless force_refresh is True.
        2. Queries FastAPI upstream with a 3.0s timeout.
        3. If upstream succeeds, caches response and returns with stale=False.
        4. If upstream fails or times out, falls back to latest ForecastRun in database with stale=True.
        5. If database is also empty, raises UpstreamServiceUnavailable (never fabricates data).
        """
        if not force_refresh:
            cached = cache.get(CACHE_KEY_LATEST_FORECAST)
            if cached and isinstance(cached, dict):
                # Ensure cached fresh response preserves its accurate stale state
                return cached

        # Attempt to call upstream FastAPI service
        base_url = getattr(settings, "FASTAPI_BASE_URL", "http://localhost:8000").rstrip("/")
        timeout_seconds = getattr(settings, "FASTAPI_TIMEOUT_SECONDS", 3.0)
        cache_ttl = getattr(settings, "FASTAPI_CACHE_TTL_SECONDS", 86400)
        url = f"{base_url}/api/v1/forecast"

        upstream_error: Optional[str] = None
        try:
            resp = requests.get(url, timeout=timeout_seconds)
            if resp.status_code == 200:
                data = resp.json()
                raw_points = data.get("forecast", data.get("points", []))  # FastAPI returns the list under "forecast"
                formatted_points = [
                    {
                        "month": p.get("month"),
                        "point": p.get("point_forecast") if "point_forecast" in p else p.get("point"),
                        "lower_80": p.get("lower_80"),
                        "upper_80": p.get("upper_80"),
                        "lower_95": p.get("lower_95"),
                        "upper_95": p.get("upper_95"),
                    }
                    for p in raw_points
                ]

                fresh_result = {
                    "run_id": None,
                    "created_at": None,
                    "model_version": data.get("model_version", "SARIMA(1,1,1)(1,0,0)[12]"),
                    "origin": data.get("forecast_origin", "2025-09"),
                    "stale": False,
                    "source": "fastapi_live",
                    "points": formatted_points,
                }
                # Cache successful fresh response for 1 day
                cache.set(CACHE_KEY_LATEST_FORECAST, fresh_result, timeout=cache_ttl)
                return fresh_result
            else:
                upstream_error = f"FastAPI returned HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning(upstream_error)
        except requests.Timeout as e:
            upstream_error = f"FastAPI request timed out after {timeout_seconds}s: {e}"
            logger.warning(upstream_error)
        except requests.RequestException as e:
            upstream_error = f"FastAPI connection failed: {e}"
            logger.warning(upstream_error)
        except Exception as e:
            upstream_error = f"Unexpected error communicating with FastAPI: {e}"
            logger.exception(upstream_error)

        # Fallback to latest stored ForecastRun in local database
        db_run = ForecastRun.objects.prefetch_related("points").order_by("-created_at").first()
        if db_run is not None:
            points = [
                {
                    "month": p.month,
                    "point": p.point,
                    "lower_80": p.lower_80,
                    "upper_80": p.upper_80,
                    "lower_95": p.lower_95,
                    "upper_95": p.upper_95,
                }
                for p in db_run.points.all()
            ]
            fallback_result = {
                "run_id": db_run.id,
                "created_at": db_run.created_at.isoformat(),
                "model_version": db_run.model_version,
                "origin": db_run.origin,
                "stale": True,
                "source": "database_fallback",
                "fallback_reason": upstream_error,
                "points": points,
            }
            return fallback_result

        # Both upstream and database are unavailable: do not fabricate forecast values
        raise UpstreamServiceUnavailable(
            f"Forecasting service unavailable: Upstream FastAPI failed ({upstream_error}) "
            f"and no stored ForecastRun exists in the database."
        )
