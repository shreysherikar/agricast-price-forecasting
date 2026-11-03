"""
Security utilities for FastAPI:
- API key authentication for sensitive administrative and pipeline execution endpoints.
- Thread-safe in-memory sliding-window rate limiting.
"""
import os
import time
from collections import defaultdict
from threading import Lock
from typing import Optional

from fastapi import Request, HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_expected_api_key() -> str:
    """Load API key from environment variable FORECAST_API_KEY with secure default for dev."""
    return os.getenv("FORECAST_API_KEY", "dev-forecast-key-change-in-prod")


def verify_api_key(
    request: Request = None,
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    """
    Validate incoming API key against configured environment variable.
    Returns 401 Unauthorized if missing.
    Returns 403 Forbidden if mismatched.
    """
    # Allow bypass during direct unit test calls if request is None and api_key is None
    if request is None and api_key is None:
        # Check if running in direct Python test mode
        if os.getenv("TESTING_DIRECT_CALL", "0") == "1":
            return "direct_test_key"

    if not api_key:
        # Also check Authorization header as fallback: Authorization: Bearer <key>
        if request is not None:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:].strip()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: X-API-Key header is missing.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    expected = get_expected_api_key()
    if api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid API key.",
        )

    return api_key


class SlidingWindowRateLimiter:
    """
    Thread-safe sliding-window rate limiter for sensitive API endpoints.
    """
    def __init__(self, max_requests: int = 5, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.client_records = defaultdict(list)
        self.lock = Lock()

    def check(self, client_identifier: str) -> None:
        now = time.time()
        with self.lock:
            cutoff = now - self.window_seconds
            # Purge timestamps outside window
            self.client_records[client_identifier] = [
                t for t in self.client_records[client_identifier] if t > cutoff
            ]
            if len(self.client_records[client_identifier]) >= self.max_requests:
                oldest = self.client_records[client_identifier][0]
                retry_after = max(1, int(self.window_seconds - (now - oldest)) + 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Rate limit exceeded: maximum {self.max_requests} requests "
                        f"per {int(self.window_seconds)} seconds. Please retry in {retry_after}s."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            self.client_records[client_identifier].append(now)

    def reset(self):
        """Reset all tracked client records (for test isolation)."""
        with self.lock:
            self.client_records.clear()


# Default rate limiter for pipeline execution (5 runs per minute per client)
pipeline_rate_limiter = SlidingWindowRateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_PIPELINE_RUN_MAX", "5")),
    window_seconds=float(os.getenv("RATE_LIMIT_PIPELINE_RUN_WINDOW", "60.0")),
)


def rate_limit_pipeline(request: Request):
    """Dependency to enforce rate limiting based on client IP."""
    if request is None:
        return
    client_ip = request.client.host if request.client else "unknown_client"
    # Honor X-Forwarded-For if running behind a trusted reverse proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    pipeline_rate_limiter.check(client_ip)
