"""In-memory rate limiter middleware for Ketrika API (SPECS §23, T6.2)."""

from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class InMemoryRateLimiter:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self, default_limit: int = 60, window_seconds: float = 60.0) -> None:
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._records: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, limit: int | None = None) -> tuple[bool, int, int]:
        """Check if request for key is allowed under rate limit.

        Returns:
            (is_allowed, remaining, retry_after)
        """
        max_requests = limit or self.default_limit
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            # Filter out timestamps older than sliding window
            timestamps = [ts for ts in self._records[key] if ts > cutoff]

            if len(timestamps) >= max_requests:
                # Rate limit exceeded
                oldest_ts = timestamps[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest_ts)))
                self._records[key] = timestamps
                return False, 0, retry_after

            # Allow request
            timestamps.append(now)
            self._records[key] = timestamps
            remaining = max_requests - len(timestamps)
            return True, remaining, 0

    def reset(self, key: str | None = None) -> None:
        """Reset records for testing."""
        with self._lock:
            if key:
                self._records.pop(key, None)
            else:
                self._records.clear()


# Global in-memory rate limiter instance
rate_limiter = InMemoryRateLimiter(default_limit=60, window_seconds=60.0)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware enforcing 60 req/min per client key."""

    def __init__(
        self,
        app: Callable[..., Any],
        limiter: InMemoryRateLimiter = rate_limiter,
        exempt_paths: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.limiter = limiter
        self.exempt_paths = exempt_paths or {
            "/v1/health",
            "/v1/docs",
            "/v1/redoc",
            "/v1/openapi.json",
            "/openapi.json",
        }

    def _extract_client_key(self, request: Request) -> str:
        """Extract rate limiting key from X-API-Key, Bearer token, or IP."""
        client_host = request.client.host if request.client else "unknown"
        if request.url.path == "/v1/auth/login":
            return f"ip:{client_host}"
        # 1. X-API-Key header
        api_key = request.headers.get("x-api-key")
        if api_key:
            return f"key:{hashlib.sha256(api_key.strip().encode()).hexdigest()}"

        # 2. Authorization header
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            return f"bearer:{hashlib.sha256(token.encode()).hexdigest()}"

        # 3. Client cookie
        cookie_token = request.cookies.get("session_token")
        if cookie_token:
            return f"cookie:{hashlib.sha256(cookie_token.encode()).hexdigest()}"

        # 4. Fallback to client IP
        return f"ip:{client_host}"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Check exemption
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_key = self._extract_client_key(request)
        allowed, remaining, retry_after = self.limiter.check(client_key)

        if not allowed:
            # Return RFC 7807 429 Too Many Requests
            return JSONResponse(
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.limiter.default_limit),
                    "X-RateLimit-Remaining": "0",
                    "Content-Type": "application/problem+json",
                },
                content={
                    "type": "https://datatracker.ietf.org/doc/html/rfc6585#section-4",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": (
                        f"Rate limit of {self.limiter.default_limit} requests "
                        f"per minute exceeded. Try again in {retry_after} seconds."
                    ),
                    "instance": request.url.path,
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.default_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
