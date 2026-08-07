"""Performance-bundle freshness (PB8).

How old bundle-derived data may be before a surface should warn the viewer that
the numbers are stale. Kept as config, not a magic literal in logic (P4).

Spec: docs/functional-specification.md §4.8 (Performance Bundle ingestion, PB8)
"""

from __future__ import annotations

from datetime import date, datetime


# Default staleness window. GSC lags ~2–3 days and bundles are typically
# produced monthly, so ~5 weeks is "older than one refresh cycle".
STALENESS_DAYS_DEFAULT = 35


def parse_generated_at(value: str | None) -> datetime | None:
    """Parse an ISO-8601 bundle `generated_at` (tolerating a trailing 'Z')."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def days_since(generated_at: str | None, today: date | None = None) -> int | None:
    """Whole days between `generated_at` and `today` (None if unparseable)."""
    dt = parse_generated_at(generated_at)
    if dt is None:
        return None
    today = today or date.today()
    return (today - dt.date()).days


def is_stale(
    generated_at: str | None,
    today: date | None = None,
    days: int = STALENESS_DAYS_DEFAULT,
) -> bool | None:
    """True when the data is older than `days`, False when fresh, None when the
    timestamp is missing/unparseable (caller decides how to present 'unknown')."""
    n = days_since(generated_at, today)
    return None if n is None else n > days


def earlier(a: str | None, b: str | None) -> str | None:
    """Return the earlier of two ISO timestamps, so a ledger row that carries data
    forward from an older bundle reports the vintage of its OLDEST contributing
    source, never optimistically the newest (PB8 honesty). On a one-sided parse
    failure returns the parseable side (a real date beats an unorderable one); if
    neither parses, returns `a`. Note: our own writer only ever stores valid ISO
    or None, so the unparseable branch is external-corruption defence only."""
    da, db = parse_generated_at(a), parse_generated_at(b)
    if da is None and db is None:
        return a
    if da is None:
        return b
    if db is None:
        return a
    return a if da <= db else b
