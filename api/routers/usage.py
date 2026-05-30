"""Usage aggregation router (v2.6 M2.6 / Cycle EE).

Exposes ``GET /api/ai/usage/stats`` — returns a UsageReport DTO with
aggregated billing data for the authenticated customer over a date
range.

Per the Cycle EE auth-derived customer-id critique:
    - ``customer_id`` is NOT accepted as a query parameter.
    - The router derives it from the auth context.
    - Today, every authenticated request resolves to
      :data:`api.services.ai_router.SYSTEM_CONTEXT_ID` (no per-customer
      identity model yet).
    - TODO(M2.3): wire to the real per-bearer-token customer mapping
      when the identity model lands.

Per the Cycle EE date-range cap:
    - Requests with ``end_date - start_date > 90 days`` → HTTP 400
      with error code ``PERIOD_TOO_LARGE``.
    - Missing ``start_date`` or ``end_date`` → HTTP 422 (FastAPI's
      auto-validation).

Per the Cycle X auth pattern: router-level
``dependencies=[Depends(require_auth)]``. No per-endpoint auth dance.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.services.ai_router import SYSTEM_CONTEXT_ID
from api.services.auth import require_auth
from api.services.usage_logger import PeriodTooLargeError, usage_reader
from api.schemas.usage import UsageReport

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/ai/usage",
    tags=["usage"],
    dependencies=[Depends(require_auth)],
)


def _resolve_customer_id_from_auth() -> str:
    """Derive the customer_id for the current request.

    TODO(M2.3): wire to the real per-bearer-token customer mapping when
    the identity model lands. Today every authenticated caller maps to
    SYSTEM_CONTEXT_ID — there's no per-customer identity yet, and the
    write path also tags every row with SYSTEM_CONTEXT_ID, so queries
    return the appropriate data.

    This function is the SINGLE seam to update at M2.3 — replacing the
    constant with a session/token lookup. By centralising the derivation
    here, the router endpoint body never sees the constant directly.
    """
    return SYSTEM_CONTEXT_ID


@router.get("/stats", response_model=UsageReport)
async def get_usage_stats(
    start_date: str = Query(
        ...,
        description="ISO 8601 UTC inclusive lower bound. Example: 2026-05-01T00:00:00Z",
    ),
    end_date: str = Query(
        ...,
        description="ISO 8601 UTC inclusive upper bound. Example: 2026-05-31T23:59:59Z",
    ),
    provider: str | None = Query(
        None,
        description="Optional provider filter (openai / gemini / anthropic / deepseek).",
    ),
) -> UsageReport:
    """Aggregated billing report for the authenticated customer.

    The customer is derived from the auth context — it is NOT a query
    parameter. See module docstring for the identity-model TODO.

    Errors:
        - 400 PERIOD_TOO_LARGE: date range > 90 days.
        - 400 INVALID_DATE: start_date / end_date not parseable as ISO 8601.
        - 401 UNAUTHORIZED: missing or invalid bearer token (router-level).
        - 422: start_date or end_date missing (FastAPI auto-validation).
    """
    customer_id = _resolve_customer_id_from_auth()

    try:
        report = await usage_reader.get_usage_report(
            start_date=start_date,
            end_date=end_date,
            customer_id=customer_id,
            provider=provider,
        )
    except PeriodTooLargeError as exc:
        # 400 with a clear error code so frontend can render a specific
        # message ("range too large" vs "invalid dates").
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "PERIOD_TOO_LARGE",
                    "message": str(exc),
                }
            },
        ) from exc
    except ValueError as exc:
        # Either an invalid date format or an empty customer_id (the
        # latter would be a server-side bug — _resolve_customer_id never
        # returns empty — but the guard is defensive).
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_DATE",
                    "message": str(exc),
                }
            },
        ) from exc

    return report
