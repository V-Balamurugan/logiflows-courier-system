import time
from collections import defaultdict
from typing import Dict, List, Tuple
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window IP rate limiter for sensitive authentication endpoints."""

    def __init__(self, app, max_requests: int = 20, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # In-memory store: { ip: [timestamp1, timestamp2, ...] }
        self._requests: Dict[str, List[float]] = defaultdict(list)
        # Targeted sensitive endpoints
        self.rate_limited_paths = [
            f"{settings.API_V1_STR}/auth/login",
            f"{settings.API_V1_STR}/auth/register",
        ]

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate-limiting entirely during automated unit tests
        if settings.ENVIRONMENT == "test":
            return await call_next(request)

        # Check if the request is targeting a sensitive auth endpoint with POST
        if request.method == "POST" and request.url.path in self.rate_limited_paths:
            client_ip = request.client.host if request.client else "127.0.0.1"
            # Forwarded headers support if behind proxy
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()

            now = time.time()
            timestamps = self._requests[client_ip]

            # Prune timestamps older than sliding window
            cutoff = now - self.window_seconds
            self._requests[client_ip] = [ts for ts in timestamps if ts > cutoff]

            # Check if threshold exceeded
            if len(self._requests[client_ip]) >= self.max_requests:
                retry_after = int(self.window_seconds - (now - self._requests[client_ip][0]))
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests. Please try again after cooldown."},
                    headers={"Retry-After": str(max(1, retry_after))}
                )

            # Record this valid attempt
            self._requests[client_ip].append(now)

        return await call_next(request)
