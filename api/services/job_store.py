"""Job store protocol, implementations, and factory.

This module provides:
- JobStore Protocol: interface that all implementations must follow
- SQLiteJobStore: local SQLite implementation
- RedisJobStore: Upstash Redis implementation for production
- get_job_store(): factory function that selects appropriate backend
- Schema and helper functions for health scoring

Backward compatibility: public API is re-exported for existing code.
"""

from __future__ import annotations

import os
import logging

from api.services.job_store_base import (
    JobStore,
    SCHEMA,
    _DEFAULT_TTL_DAYS,
    _DEFAULT_SQLITE_PATH,
    _density_health_score,
    _compute_v15_health_score,
    SEVERITY_ORDER,
    PRIORITY_ORDER,
)
from api.services.sqlite_store import SQLiteJobStore
from api.services.redis_store import RedisJobStore

logger = logging.getLogger(__name__)

__all__ = [
    "JobStore",
    "SQLiteJobStore",
    "RedisJobStore",
    "get_job_store",
    "SCHEMA",
    "SEVERITY_ORDER",
    "PRIORITY_ORDER",
]


def get_job_store() -> "SQLiteJobStore | RedisJobStore":
    """Return the appropriate job store for the current environment.

    Selection order:
      1. UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN set → RedisJobStore
      2. DATABASE_URL set (sqlite:///... or path) → SQLiteJobStore at that path
      3. Neither set → SQLiteJobStore at SQLITE_PATH (default: talkingtoad.db)
    """
    redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "")
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
    if redis_url and redis_token:
        logger.info("using_redis_store")
        return RedisJobStore(url=redis_url, token=redis_token)

    url = os.getenv("DATABASE_URL", "")
    if url.startswith("sqlite:///"):
        db_path = url[len("sqlite:///"):] or _DEFAULT_SQLITE_PATH
    elif url:
        db_path = url
    else:
        db_path = _DEFAULT_SQLITE_PATH

    return SQLiteJobStore(db_path=db_path)
