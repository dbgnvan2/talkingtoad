"""WordPress Fix Manager endpoints (v2.0).

This module routes fix-related endpoints across domain-specific router modules:
- fix_manager_router: Core fix CRUD (generate, list, update, apply, delete)
- link_router: Link-related fixes (replace, mark-anchor-fixed, verify-broken-links, etc.)
- title_router: Title-specific endpoints (bulk-trim, trim-one, predefined-codes)
- heading_router: Heading management (level, text, bulk-replace, to-bold, etc.)
- image_router: Image metadata and optimization (update-meta, refresh, optimize-*)
- orphaned_media_router: Orphaned media detection and deletion
- batch_optimizer_router: Batch image optimization (start, status, pause, resume)

Each router is independently deployable and testable, with shared utilities in fixes_shared.
"""

from __future__ import annotations

from fastapi import APIRouter
from api.routers.fix_manager_router import router as fix_manager_router
from api.routers.heading_router import router as heading_router
from api.routers.title_router import router as title_router

# Main router
router = APIRouter()

# Register fix-domain routers.
# Each router declares its own /api/fixes prefix and auth dependency.
#
# Order matters: literal-path routers MUST be registered before
# fix_manager_router, because fix_manager_router has catch-all routes like
# GET /{job_id} (constrained to UUID). FastAPI matches by registration order
# and returns 422 from a pattern-validation failure rather than continuing to
# the next router. Registering literal-path routers first means requests like
# GET /api/fixes/predefined-codes hit the literal route, not the catch-all.
router.include_router(title_router, tags=["fixes"])
router.include_router(heading_router, tags=["fixes"])
router.include_router(fix_manager_router, tags=["fixes"])

# TODO (v2.3 M0.12.3-6): the remaining domain routers will land in this order:
# - image_router (info, update-meta, refresh, optimize-*)
# - orphaned_media_router (orphaned-media/{job_id})
# - batch_optimizer_router (batch-optimize/start, status, pause, resume, cancel, list)
# - link_router (link-sources, replace-link, verify-broken-links, mark-*-fixed, apply-one, wp-value)

__all__ = ["router"]
