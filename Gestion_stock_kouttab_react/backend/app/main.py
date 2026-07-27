"""FastAPI application entry-point."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import ERROR_MESSAGES, ErrorCode
from app.core.exceptions import register_exception_handlers
from app.core.logger import get_logger


logger = get_logger("main")


limiter = Limiter(key_func=get_remote_address, enabled=settings.rate_limit_enabled)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    logger.info("Kouttab Stock API demarre (env=%s)", settings.app_env)
    yield
    logger.info("Kouttab Stock API arrete.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.app_debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (slowapi). We override the default 429 response so it follows the
# standard ``{code, message, extras}`` envelope and exposes the ``RATE_7001`` code.
app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:  # noqa: ARG001
    code = ErrorCode.RATE_LIMIT_EXCEEDED
    if request.url.path.endswith("/auth/login"):
        code = ErrorCode.LOGIN_RATE_LIMITED
    _, message = ERROR_MESSAGES[code]
    return JSONResponse(
        status_code=429,
        content={
            "code": code.value,
            "message": message,
            "extras": {"limit": str(exc.detail) if exc.detail else None},
            "error": code.value,
            "details": {"limit": str(exc.detail) if exc.detail else None},
        },
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
# Keep the slowapi default handler ref to avoid an unused-import lint warning.
_ = _rate_limit_exceeded_handler
app.add_middleware(SlowAPIMiddleware)


# Request timing log
@app.middleware("http")
async def _log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Process-Time-ms"] = f"{duration_ms:.1f}"
    return response


# Custom exception handlers
register_exception_handlers(app)


# v1 router (prefix /api/v1)
app.include_router(api_router, prefix="/api/v1")


# Health endpoint (used by O2Switch / UptimeRobot)
@app.get("/health", tags=["meta"])
@app.get("/api/v1/health", tags=["meta"])
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": settings.app_version})


# Root
@app.get("/", tags=["meta"])
def root() -> JSONResponse:
    return JSONResponse(
        {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }
    )
