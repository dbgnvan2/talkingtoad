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
from api.routers.batch_optimizer_router import router as batch_optimizer_router
from api.routers.image_router import router as image_router
from api.routers.link_router import router as link_router
from api.routers.orphaned_media_router import router as orphaned_media_router
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
router.include_router(image_router, tags=["fixes"])
router.include_router(orphaned_media_router, tags=["fixes"])
router.include_router(batch_optimizer_router, tags=["fixes"])
router.include_router(link_router, tags=["fixes"])
router.include_router(fix_manager_router, tags=["fixes"])

# v2.3 M0.12.7: all six domain routers from the v2.0 split are now registered.
# Frontend api.js no longer 404s or 405s against any documented /api/fixes/*
# endpoint. The catch-all GET /{job_id} in fix_manager_router is constrained
# to a UUID pattern so it doesn't shadow new sibling routes.

__all__ = ["router"]
