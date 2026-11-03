"""
Automated unit tests for FastAPI security:
- API-key authentication (missing key raises 401, invalid key raises 403, valid key passes)
- Bearer token fallback support
- Sliding-window rate limiting (429 Too Many Requests when threshold exceeded)
- Client IP isolation in rate limiting
"""
import os
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from src.api.security import (
    verify_api_key,
    get_expected_api_key,
    SlidingWindowRateLimiter,
    pipeline_rate_limiter,
    rate_limit_pipeline,
)


@pytest.fixture(autouse=True)
def clean_env_and_limiter(monkeypatch):
    monkeypatch.setenv("FORECAST_API_KEY", "test-secret-forecast-key-999")
    pipeline_rate_limiter.reset()
    yield
    pipeline_rate_limiter.reset()


def test_verify_api_key_missing_raises_401():
    """Missing API key must raise 401 UNAUTHORIZED."""
    mock_request = MagicMock()
    mock_request.headers.get.return_value = ""

    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(request=mock_request, api_key=None)

    assert exc_info.value.status_code == 401
    assert "Authentication required" in exc_info.value.detail
    assert exc_info.value.headers.get("WWW-Authenticate") == "ApiKey"


def test_verify_api_key_invalid_raises_403():
    """Invalid API key must raise 403 FORBIDDEN."""
    mock_request = MagicMock()
    mock_request.headers.get.return_value = ""

    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(request=mock_request, api_key="wrong-invalid-key")

    assert exc_info.value.status_code == 403
    assert "Forbidden" in exc_info.value.detail


def test_verify_api_key_valid_header_passes():
    """Valid API key must be returned successfully."""
    mock_request = MagicMock()
    expected = get_expected_api_key()
    assert expected == "test-secret-forecast-key-999"

    verified = verify_api_key(request=mock_request, api_key="test-secret-forecast-key-999")
    assert verified == "test-secret-forecast-key-999"


def test_verify_api_key_bearer_auth_fallback():
    """Authorization: Bearer <key> must be supported as fallback."""
    mock_request = MagicMock()
    mock_request.headers.get.side_effect = lambda h, default="": (
        "Bearer test-secret-forecast-key-999" if h == "Authorization" else default
    )

    verified = verify_api_key(request=mock_request, api_key=None)
    assert verified == "test-secret-forecast-key-999"


def test_rate_limiter_allows_under_threshold():
    """Sliding-window limiter allows requests under max_requests threshold."""
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60.0)
    for _ in range(3):
        limiter.check("client_test_1")  # Should not raise


def test_rate_limiter_blocks_over_threshold():
    """Sliding-window limiter raises 429 when threshold exceeded."""
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
    limiter.check("client_test_2")
    limiter.check("client_test_2")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check("client_test_2")

    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers


def test_rate_limiter_client_isolation():
    """Rate limits must be tracked independently per client identifier."""
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
    limiter.check("client_A")
    limiter.check("client_A")

    # client_A is blocked
    with pytest.raises(HTTPException):
        limiter.check("client_A")

    # client_B is unaffected
    limiter.check("client_B")  # Should not raise


def test_rate_limit_pipeline_dependency():
    """rate_limit_pipeline dependency resolves client IP and enforces limit."""
    mock_request = MagicMock()
    mock_request.client.host = "192.168.1.100"
    mock_request.headers.get.return_value = None

    pipeline_rate_limiter.max_requests = 1
    pipeline_rate_limiter.window_seconds = 60.0

    # 1st call: OK
    rate_limit_pipeline(mock_request)

    # 2nd call: Rate limited
    with pytest.raises(HTTPException) as exc_info:
        rate_limit_pipeline(mock_request)
    assert exc_info.value.status_code == 429
