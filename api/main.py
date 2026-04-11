"""
TalkingToad FastAPI application entry point (spec §2.3, §2.6, §8).

Wires together:
  - CORS middleware (ALLOWED_ORIGINS env var)
  - slowapi rate limiting middleware
  - Auth dependency (applied per-router)
  - Job store lifecycle (init on startup, close on shutdown)
  - Structured JSON logging
  - All routers
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pythonjsonlogger import jsonlogger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.routers import crawl as crawl_router
from api.routers import fixes as fixes_router
from api.routers import utility as utility_router
from api.services.job_store import SQLiteJobStore, RedisJobStore, get_job_store
from api.services.rate_limiter import limiter

# ── Logging setup ──────────────────────────────────────────────────────────

def _configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)


_configure_logging()
logger = logging.getLogger(__name__)

# ── Job store singleton ────────────────────────────────────────────────────

_store: SQLiteJobStore | RedisJobStore | None = None


# ── App lifecycle ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store
    _store = get_job_store()
    await _store.init()
    logger.info("app_startup", extra={"db_path": _store._db_path})
    yield
    if _store:
        await _store.close()
    logger.info("app_shutdown")


# ── App factory ────────────────────────────────────────────────────────────

app = FastAPI(
    title="TalkingToad",
    description="Nonprofit SEO Crawler API",
    version="1.4",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────────

_allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
_allowed_origins = [o.strip() for o in _allowed_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
)

# ── Rate limiting ──────────────────────────────────────────────────────────

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Custom exception handlers ──────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return all HTTPExceptions in the spec error shape {error: {code, message, http_status}}."""
    detail = exc.detail
    # If the raising code already used our error shape, pass it through
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(detail), "http_status": exc.status_code}},
    )


# ── Routers ────────────────────────────────────────────────────────────────

app.include_router(crawl_router.router)
app.include_router(fixes_router.router)
app.include_router(utility_router.router)
