from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .config import get_settings
from .errors import AppError, app_error_handler
from .observability import RequestContextMiddleware, SecurityAndRateLimitMiddleware, configure_logging
from .routes import router

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title="African Founder Studies API",
    version="0.1.0",
    description="Independent, citation-based public-ideas research API.",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_middleware(RequestContextMiddleware)
app.add_middleware(SecurityAndRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "X-Correlation-ID"],
)
app.include_router(router)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "African Founder Studies API", "documentation": "/api/docs"}
