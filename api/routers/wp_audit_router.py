"""D3 — WordPress configuration audit endpoint.

POST /api/wp-audit/{job_id}   read-only, opt-in, post-scan

Spec:  docs/pending/2026-08-29_D3-wordpress-configuration-audit.md
Tests: tests/test_wp_audit.py

Deliberately its own router rather than an addition to the crawl router: this is
not part of a scan, it needs WordPress credentials, and it only works on
WordPress. Keeping it separate is what lets the crawl stay fast and universal.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.routers.fixes_shared import (
    _CREDS_PATH,
    _err,
    _validate_wp_domain_for_job,
    get_store,
)
from api.services.wp_client import WPAuthError, WPClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wp-audit", tags=["wp-audit"])


@router.post("/{job_id}", response_model=None)
async def wp_audit_endpoint(
    job_id: str,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Read the site's plugin, theme and Site Health configuration.

    Read-only by construction — see `api/services/wp_audit.py` and the guard in
    `tests/test_architecture_constraints.py`.
    """
    from api.services.wp_audit import (
        WPAuditError,
        collect_wp_audit,
        report_to_dict,
    )

    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    # Domain validation BEFORE any WordPress call — never authenticate against a
    # site this job is not for (CLAUDE.md WordPress-safety constraint).
    domain_err = await _validate_wp_domain_for_job(store, job_id)
    if domain_err is not None:
        return domain_err

    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS",
                    "wp-credentials.json not found — the WordPress configuration "
                    "audit needs stored admin credentials for this site.", 400)

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            report = await collect_wp_audit(wp)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except WPAuditError as exc:
        # A capability failure is the user's to fix, not a server fault — and it
        # must never be reported as "no problems found" (P2).
        status = 403 if exc.code == "WP_INSUFFICIENT_CAPABILITY" else 502
        return _err(exc.code, str(exc), status)
    except Exception as exc:  # noqa: BLE001
        logger.exception("wp_audit_failed", extra={"job_id": job_id})
        return _err("WP_AUDIT_FAILED", f"Could not read WordPress configuration: {exc}", 502)

    payload = report_to_dict(report)
    payload["job_id"] = job_id
    try:
        await store.update_job(job_id, wp_audit=payload)
    except Exception:  # noqa: BLE001
        logger.warning("wp_audit_persist_failed", extra={"job_id": job_id})
    return payload
