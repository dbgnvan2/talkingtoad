"""
Verified links router — /api/verified-links

Lets users mark external URLs as "verified good" so the crawler stops
flagging them as EXTERNAL_LINK_SKIPPED in future crawls.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.services.auth import require_auth
from api.services.job_store import SQLiteJobStore, RedisJobStore

router = APIRouter(
    prefix="/api/verified-links",
    dependencies=[Depends(require_auth)],
)


def get_store() -> SQLiteJobStore | RedisJobStore:
    from api.main import _store
    return _store  # type: ignore[return-value]


class AddVerifiedLinkRequest(BaseModel):
    url: str
    job_id: str | None = None  # if provided, suppress matching issues from this job immediately


@router.get("")
async def list_verified_links(
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> list[dict]:
    """Return all verified links with their date verified."""
    return await store.get_verified_links()


@router.post("")
async def add_verified_link(
    body: AddVerifiedLinkRequest,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict:
    """Mark a URL as verified. Idempotent — re-verifying resets the date.

    If job_id is supplied, also removes the EXTERNAL_LINK_SKIPPED issue for
    this URL from that job so the dashboard count updates immediately.
    """
    url = body.url.strip()
    if not url:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_URL", "message": "url is required", "http_status": 400}},
        )
    verified_at = await store.add_verified_link(url)
    suppressed = 0
    if body.job_id:
        suppressed = await store.delete_issues_by_code_and_url(
            body.job_id, "EXTERNAL_LINK_SKIPPED", url
        )
    return {"url": url, "verified_at": verified_at, "suppressed": suppressed}


@router.delete("")
async def remove_verified_link(
    url: str = Query(..., description="The URL to unverify"),
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict:
    """Remove a URL from the verified list."""
    existed = await store.remove_verified_link(url)
    return {"url": url, "removed": existed}
