import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

REQUESTS = Counter("afs_http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("afs_http_request_duration_seconds", "HTTP latency", ["method", "path"])
ANSWERS = Counter("afs_answers_total", "Generated answers", ["confidence", "refused"])
PROVIDER_LATENCY = Histogram(
    "afs_provider_duration_seconds", "Provider latency", ["provider", "operation"]
)
PROVIDER_COST = Counter(
    "afs_provider_estimated_cost_usd_total", "Estimated provider cost", ["provider", "operation"]
)
JOBS = Counter("afs_jobs_total", "Background job outcomes", ["job_type", "status"])
CRAWL_FAILURES = Counter("afs_crawl_failures_total", "Crawl failure categories", ["category"])
EMBEDDINGS = Counter("afs_embeddings_total", "Generated embedding vectors", ["provider", "model"])
CITATIONS = Histogram("afs_answer_citations", "Citations per answer")


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))[:100]
        correlation_id = request.headers.get("x-correlation-id", request_id)[:100]
        traceparent = request.headers.get("traceparent", "")[:128]
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id, correlation_id=correlation_id, traceparent=traceparent or None
        )
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        REQUESTS.labels(request.method, path, response.status_code).inc()
        LATENCY.labels(request.method, path).observe(elapsed)
        response.headers["x-request-id"] = request_id
        response.headers["x-correlation-id"] = correlation_id
        structlog.get_logger().info(
            "request_completed",
            method=request.method,
            path=path,
            status=response.status_code,
            duration_ms=round(elapsed * 1000, 2),
        )
        return response


class SecurityAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Small local limiter; production deployments should share state through Redis."""

    def __init__(self, app: object, limit: int = 30, window_seconds: int = 60) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.limit = limit
        self.window_seconds = window_seconds
        self.events: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        limited_path = request.url.path in {
            "/api/v1/auth/login",
            "/api/v1/ask",
            "/api/v1/corrections",
        }
        if limited_path:
            client = request.client.host if request.client else "unknown"
            key = f"{client}:{request.url.path}"
            now = time.monotonic()
            events = self.events[key]
            while events and events[0] <= now - self.window_seconds:
                events.popleft()
            if len(events) >= self.limit:
                return Response(
                    content='{"error":{"code":"rate_limit_exceeded","message":"Too many requests"}}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(self.window_seconds)},
                )
            events.append(now)
        response = await call_next(request)
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
        response.headers["permissions-policy"] = "camera=(), microphone=(), geolocation=()"
        return response
