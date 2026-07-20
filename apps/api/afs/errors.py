from typing import Any

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Any = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
            }
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Guarantee a JSON, CORS-covered error body for exceptions with no specific handler.

    Starlette's default 500 fallback runs above CORSMiddleware and returns plain text,
    so browsers report a generic cross-origin fetch failure instead of the real error.
    """
    request_id = getattr(request.state, "request_id", None)
    structlog.get_logger().error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        request_id=request_id,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred. Please try again shortly.",
                "details": None,
                "request_id": request_id,
            }
        },
    )
