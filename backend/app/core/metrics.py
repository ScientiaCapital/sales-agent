"""
Prometheus metrics integration for FastAPI.

Provides middleware for request metrics and an endpoint to expose metrics.
"""

import time
from typing import Callable
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 2, 5)
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.time() - start_time
            path = request.url.path
            REQUEST_COUNT.labels(request.method, path, str(status_code)).inc()
            REQUEST_LATENCY.observe(duration)


def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
