"""Job store implementation and factory.

This module provides:
- SQLiteJobStore: the job store
- get_job_store(): factory function
- Schema and helper functions for health scoring

Backward compatibility: public API is re-exported for existing code.

History: a second, Upstash-Redis implementation lived here until 2026-08-31. It
was never executed -- the factory selected it only when both UPSTASH_REDIS_REST_*
vars were set, and they never were -- and it had drifted from SQLite in ten known
ways while its AsyncMock-backed tests stayed green. Deleted rather than repaired;
see docs/functional-specification.md and LEARNINGS.md. If multi-instance
deployment is ever needed, write a fresh implementation against real round-trip
parity tests. Do not resurrect that one.
"""

from __future__ import annotations

import os
import logging

from api.services.job_store_base import (
    SCHEMA,
    _DEFAULT_TTL_DAYS,
    _DEFAULT_SQLITE_PATH,
    _density_health_score,
    _compute_v15_health_score,
    SEVERITY_ORDER,
    PRIORITY_ORDER,
)
from api.services.sqlite_store import SQLiteJobStore

logger = logging.getLogger(__name__)

__all__ = [
    "SQLiteJobStore",
    "get_job_store",
    "SCHEMA",
    "SEVERITY_ORDER",
    "PRIORITY_ORDER",
]

_REMOVED_REDIS_VARS = ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN")


def get_job_store() -> SQLiteJobStore:
    """Return the job store for the current environment.

    Selection order:
      1. DATABASE_URL set (sqlite:///... or path) → SQLiteJobStore at that path
      2. Unset → SQLiteJobStore at SQLITE_PATH (default: talkingtoad.db)

    Raises if the environment still configures the removed Redis backend. Falling
    back to SQLite silently would start cleanly and serve 200s while writing the
    deployment's data somewhere other than where it was configured to go — the
    failure has to be loud. A half-configured deployment (one var set) raises too:
    the old factory required both and silently ignored that case, which is the
    likelier operator mistake.
    """
    configured = [v for v in _REMOVED_REDIS_VARS if os.getenv(v, "")]
    if configured:
        raise RuntimeError(
            f"{', '.join(configured)} is set, but the Redis job store was removed "
            "(2026-08-31). Unset it, or restore api/services/redis_store.py from git "
            "history. Refusing to fall back to SQLite silently: that would write your "
            "data somewhere other than where this deployment was configured to put it."
        )

    url = os.getenv("DATABASE_URL", "")
    if url.startswith("sqlite:///"):
        db_path = url[len("sqlite:///"):] or _DEFAULT_SQLITE_PATH
    elif url:
        db_path = url
    else:
        db_path = _DEFAULT_SQLITE_PATH

    return SQLiteJobStore(db_path=db_path)
