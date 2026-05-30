"""AI usage persistence service (v2.6 M2.5 / Cycle DD).

Per docs/pending/2026-05-29_m2_usage_persistence.md (approved 2026-05-29
with all five recommendations: asyncio.create_task pattern, SQLite-only
this cycle, structural+behavioural latency test, all three Cycle CC
TODOs closed, lifespan integration).

Public API
==========
This module is the only writer of ``ai_usage`` rows. Callers do not
touch the SQLite store directly. AIRouter._log_usage schedules
``usage_logger.record(...)`` via ``asyncio.create_task`` so the write
does not block the AIRouter call's return.

::

    from api.services.usage_logger import usage_logger
    await usage_logger.record({
        "customer_id": "system_account",
        "provider": "openai", "model": "gpt-4o",
        "input_token_count": 100, "output_token_count": 50,
        "cost_estimate_usd": 0.0025,
        "success": True,
    })

Privacy contract
================
``record()`` enforces the ``_SAFE_METADATA_KEYS`` whitelist a second
time (defence in depth — AIRouter._log_usage already filters once).
Anything outside the whitelist is silently dropped. No raw prompt or
response text ever reaches this layer; if it did, it would be dropped
here too.

Async + lifecycle
=================
Writes are fire-and-forget via ``asyncio.create_task``. The task is
tracked in ``_pending`` so the FastAPI lifespan shutdown can call
``await_pending()`` to drain in-flight writes before the process exits.

DB write failures are caught inside ``_persist`` and logged via the
standard application logger — they never raise into the caller's
event loop, and they never silently lose visibility (the standard
logger always sees the failure even if the persistence layer can't).

Storage backend
===============
SQLite-only this cycle (per approved spec). Redis parity is a follow-up
cycle before production billing. The ``_persist`` method uses the
``get_store()`` singleton from ``api.routers.crawl``, which is the
same single source of truth the rest of the application reads.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from api.services.ai_router import _SAFE_METADATA_KEYS

if TYPE_CHECKING:
    # get_store import is function-scoped at call time to avoid a
    # circular dependency at module load (crawl router imports many
    # services, some of which may eventually import this module).
    pass

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string — matches the
    convention used by every other timestamp column in the schema."""
    return datetime.now(timezone.utc).isoformat()


class UsageLogger:
    """Singleton — use the module-level :data:`usage_logger` instance.

    All persistence happens via ``record()``. ``record_parse_failure()``
    is a convenience for downstream parse failures (Cycle CC pattern)
    that AIRouter cannot detect from its HTTP-layer perspective.

    Thread / async safety: ``_pending`` is mutated only via
    ``asyncio.create_task`` / ``add_done_callback``, which are both
    safe from a single event loop. FastAPI workers run async-single-
    threaded, matching the existing pattern.
    """

    def __init__(self) -> None:
        self._pending: set[asyncio.Task] = set()

    async def record(self, metadata: dict) -> None:
        """Schedule an ai_usage write and return immediately.

        The actual DB write completes asynchronously. Persistence
        failures are caught inside the task — they do NOT raise into
        the caller's event loop.

        Args:
            metadata: dict shaped per ``_SAFE_METADATA_KEYS`` plus
                ``timestamp`` (auto-added if missing). Any key outside
                the whitelist is silently dropped — this is the privacy
                firewall. Required keys: customer_id, provider, model.
        """
        # Defence-in-depth whitelist enforcement — AIRouter._log_usage
        # already does this filter, but record() is callable directly
        # from advisor.py's parse-failure path which doesn't go through
        # AIRouter. Filtering here too ensures the whitelist is the
        # absolute persistence boundary.
        safe = {k: v for k, v in metadata.items() if k in _SAFE_METADATA_KEYS}
        # Auto-supply timestamp if caller didn't.
        safe.setdefault("timestamp", _now_iso())

        try:
            task = asyncio.create_task(self._persist(safe))
        except RuntimeError:
            # No running event loop. Happens in synchronous test
            # paths that call _log_usage outside of pytest-asyncio.
            # Fall back to inline persistence so the test can still
            # round-trip; the inline path is rare and only hit by
            # tests, so the latency penalty is acceptable.
            logger.debug("usage_logger_no_event_loop_inline_fallback")
            await self._persist(safe)
            return

        self._pending.add(task)
        # Ensure the task is removed from _pending after completion so
        # the set doesn't grow without bound.
        task.add_done_callback(self._pending.discard)

    async def record_parse_failure(
        self,
        *,
        customer_id: str,
        provider: str,
        model: str,
        error_message: str,
    ) -> None:
        """Convenience for downstream parse failures (Cycle CC pattern).

        Records a ``success=False`` event for application-level parse
        failures — distinct from provider HTTP failures, which AIRouter
        records via its own error-path in ``_call()``. This closes the
        TODO(M2.5) markers in advisor.py (`:252` and `:596`).

        The cost/token counts are 0 because no usable response was
        produced. ``error_message`` is truncated to 500 chars to match
        AIRouter's error-path truncation.
        """
        await self.record({
            "customer_id": customer_id,
            "provider": provider,
            "model": model,
            "input_token_count": 0,
            "output_token_count": 0,
            "cost_estimate_usd": 0.0,
            "success": False,
            "error_message": (error_message or "")[:500],
        })

    async def await_pending(self) -> None:
        """Wait for all in-flight writes to complete.

        Called from FastAPI lifespan shutdown so fire-and-forget tasks
        don't lose their writes when the process exits. Safe to call
        multiple times — re-entrant.

        Uses ``return_exceptions=True`` so one failing task doesn't
        prevent the others from completing. Failures are already logged
        inside ``_persist``.
        """
        if not self._pending:
            return
        # Snapshot — _pending mutates as tasks complete via the
        # done callback.
        pending = list(self._pending)
        await asyncio.gather(*pending, return_exceptions=True)

    async def _persist(self, safe: dict) -> None:
        """Internal: perform the actual DB write.

        Catches all exceptions and logs them via the standard logger.
        Never re-raises — a failed persistence must not propagate into
        a fire-and-forget task and leave noise in stderr / sentry.
        The standard logger captures the failure so it's never silently
        lost.
        """
        try:
            # Function-scoped import to avoid a circular dependency.
            from api.routers.crawl import get_store
            store = await get_store()
            await store.record_ai_usage(safe)
        except Exception as exc:
            logger.warning(
                "ai_usage_persist_failed",
                extra={
                    "error": str(exc)[:200],
                    "customer_id": safe.get("customer_id"),
                    "provider": safe.get("provider"),
                    "model": safe.get("model"),
                },
            )


# Module-level singleton. Other modules use ``usage_logger.record(...)``.
# Do NOT instantiate UsageLogger() elsewhere — multiple instances would
# mean multiple _pending sets and await_pending() would only drain its
# own.
usage_logger = UsageLogger()


# ===========================================================================
# Read path (v2.6 M2.6 / Cycle EE)
# ===========================================================================
#
# UsageReader is an INDEPENDENT class — no shared base or state with
# UsageLogger above. Co-located in this file for discoverability only.
# Per the Cycle EE locked decision (#2) and the user's critique on
# avoiding the "God Service" pattern.
#
# Two enforcement points live here:
#   1. 90-day date-range cap → raises ValueError on violation; the
#      router catches and returns HTTP 400 PERIOD_TOO_LARGE.
#   2. customer_id is REQUIRED — passing None / "" raises ValueError.
#      This is the privacy boundary at the service layer; the store
#      layer also enforces it, defence-in-depth.


from datetime import timedelta

from api.schemas.usage import (
    ModelBreakdown,
    ProviderBreakdown,
    UsageReport,
)


_MAX_PERIOD_DAYS = 90
"""Hard cap on usage-report date ranges. Beyond 90 days, requests are
rejected with HTTP 400. Rationale: prevents accidental full-table
scans on a growing ai_usage table; the typical billing query is
month-scoped anyway."""


class PeriodTooLargeError(ValueError):
    """Raised when a usage-report query exceeds the 90-day window.
    The usage router catches this and maps to HTTP 400 with error code
    ``PERIOD_TOO_LARGE``."""


class UsageReader:
    """Read-path service for ai_usage aggregation.

    Singleton — use the module-level :data:`usage_reader` instance.
    Stateless; methods can be called concurrently.

    Strict customer_id requirement: there is no method on this class
    that returns aggregated data without specifying customer_id. The
    "system admin sees all" pattern is deliberately absent — every
    query is scoped to one customer. Today every authenticated request
    derives customer_id = SYSTEM_CONTEXT_ID at the router layer
    (TODO M2.3 wires real per-customer identity).
    """

    async def get_usage_report(
        self,
        *,
        start_date: str,
        end_date: str,
        customer_id: str,
        provider: str | None = None,
    ) -> UsageReport:
        """Build a UsageReport DTO from aggregated ai_usage rows.

        Args:
            start_date: ISO 8601 UTC inclusive lower bound.
            end_date:   ISO 8601 UTC inclusive upper bound.
            customer_id: REQUIRED. Empty / None raises ValueError.
            provider: optional filter to one provider.

        Raises:
            ValueError: customer_id is empty / None.
            PeriodTooLargeError: ``end_date - start_date > 90 days``.
            ValueError: date strings don't parse as ISO 8601.

        Returns:
            UsageReport DTO ready for JSON serialisation.
        """
        if not customer_id:
            raise ValueError(
                "customer_id is required — UsageReader does not support "
                "global aggregation queries."
            )

        # Validate dates parse + range is within the cap. Use fromisoformat
        # which accepts both naive and offset-aware ISO 8601. We don't
        # care about TZ for the duration calculation as long as both
        # endpoints are in the same TZ (caller's responsibility — the
        # router enforces UTC).
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"start_date / end_date must be ISO 8601 strings: {exc!s}"
            ) from exc

        if end_dt < start_dt:
            raise ValueError("end_date must be >= start_date")

        if (end_dt - start_dt) > timedelta(days=_MAX_PERIOD_DAYS):
            raise PeriodTooLargeError(
                f"Date range exceeds {_MAX_PERIOD_DAYS}-day cap "
                f"({(end_dt - start_dt).days} days requested)"
            )

        from api.routers.crawl import get_store
        store = await get_store()
        raw = await store.aggregate_ai_usage(
            start_ts=start_date,
            end_ts=end_date,
            customer_id=customer_id,
            provider=provider,
        )

        return UsageReport(
            period_start=start_date,
            period_end=end_date,
            customer_id=customer_id,
            total_calls=raw["total_calls"],
            successful_calls=raw["successful_calls"],
            failed_calls=raw["failed_calls"],
            total_input_tokens=raw["total_input_tokens"],
            total_output_tokens=raw["total_output_tokens"],
            total_cost_usd=raw["total_cost_usd"],
            by_provider=[
                ProviderBreakdown(**row) for row in raw["by_provider"]
            ],
            by_model=[ModelBreakdown(**row) for row in raw["by_model"]],
        )


usage_reader = UsageReader()
"""Module-level singleton. Import as
``from api.services.usage_logger import usage_reader``. Do NOT
instantiate UsageReader() elsewhere — keeping a single instance makes
the seam easy to mock in tests and ensures architectural consistency."""
