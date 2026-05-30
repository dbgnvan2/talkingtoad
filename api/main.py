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

from dotenv import load_dotenv
from fastapi import FastAPI, Request

# Load .env file at the earliest possible entry point
load_dotenv()
load_dotenv(".env-ttoad")
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
from api.routers import verified as verified_router
from api.routers import ai as ai_router
from api.routers import geo as geo_router
from api.routers import advisor as advisor_router
from api.services.job_store import SQLiteJobStore, RedisJobStore, get_job_store
from api.services.rate_limiter import limiter

# ── Logging setup ──────────────────────────────────────────────────────────

def _configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    # Simple plain-text logging for easier local debugging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True
    )
    # v2.3 (M0.8 P8) — was: print(f"... API_KEY_READ={os.getenv('API_KEY_READ')}")
    # which leaked the actual key value to stdout/logs. Log only whether it's
    # set, never the value.
    _api_key_set = bool(os.getenv("API_KEY_READ"))
    logging.getLogger(__name__).debug(
        "env_loaded", extra={"api_key_read_set": _api_key_set}
    )


_configure_logging()
logger = logging.getLogger(__name__)


# ── Production safety checks (M0.8) ────────────────────────────────────────

def _is_production() -> bool:
    """Detect production environment via common host-provider markers.

    Recognises:
    - VERCEL=1                (Vercel)
    - RAILWAY_ENVIRONMENT=*   (Railway, set by their build system)
    - RENDER=true             (Render)
    - ENV=production          (generic)
    """
    return any([
        os.getenv("VERCEL") == "1",
        os.getenv("RAILWAY_ENVIRONMENT"),
        os.getenv("RENDER") == "true",
        os.getenv("ENV", "").lower() == "production",
    ])


def _assert_production_safe() -> None:
    """Fail-closed safety checks. Refuses to start the app if a footgun would
    leave the production deployment open or unsafe.

    v2.3 M0.8:
    - P2: AUTH_TOKEN empty in production = open API. Refuse to start.
    - P3: ALLOWED_ORIGINS=* with allow_credentials=True is a CSRF surface.
      Refuse to start in production (allowed in dev for convenience).
    """
    if not _is_production():
        if not os.getenv("AUTH_TOKEN"):
            # NOTE: don't use extra={"message": ...} — that key conflicts
            # with logging's own LogRecord.message attribute.
            logger.warning(
                "AUTH_TOKEN is unset — running in dev mode (all requests "
                "allowed). Set AUTH_TOKEN before deploying to production."
            )
        return

    # ── PRODUCTION CHECKS ──
    if not os.getenv("AUTH_TOKEN"):
        raise RuntimeError(
            "P2 fail-closed: AUTH_TOKEN is empty in a production environment "
            "(VERCEL/RAILWAY/RENDER/ENV=production detected). Set AUTH_TOKEN "
            "before starting. Refusing to boot with an open API."
        )

    raw_origins = os.getenv("ALLOWED_ORIGINS", "")
    origin_list = [o.strip() for o in raw_origins.split(",") if o.strip()]
    if "*" in origin_list:
        raise RuntimeError(
            "P3 fail-closed: ALLOWED_ORIGINS=* combined with allow_credentials=True "
            "is a CSRF surface. Set ALLOWED_ORIGINS to your specific frontend "
            "origin(s) in production."
        )


_assert_production_safe()

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
    # v2.6 M2.5 / Cycle DD: drain in-flight ai_usage writes before close.
    # Without this, fire-and-forget tasks scheduled by AIRouter._log_usage
    # would be cancelled mid-write on shutdown and their billing data
    # would be lost. Done BEFORE store.close() so the underlying SQLite
    # connection is still open when the writes complete.
    from api.services.usage_logger import usage_logger
    await usage_logger.await_pending()
    if _store:
        await _store.close()
    logger.info("app_shutdown")


# ── App factory ────────────────────────────────────────────────────────────

app = FastAPI(
    title="TalkingToad",
    description="Nonprofit SEO Crawler API",
    version="2.6.0",
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
app.include_router(verified_router.router)
app.include_router(utility_router.router)
app.include_router(utility_router.public_router)
app.include_router(ai_router.router)
app.include_router(geo_router.router)
app.include_router(advisor_router.router)
