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

# Main router
router = APIRouter()

# Register fix manager core endpoints
router.include_router(fix_manager_router, tags=["fixes"])

# TODO: Import and register additional routers as they are created
# from api.routers.link_router import router as link_router
# from api.routers.title_router import router as title_router
# from api.routers.heading_router import router as heading_router
# from api.routers.image_router import router as image_router
# from api.routers.orphaned_media_router import router as orphaned_media_router
# from api.routers.batch_optimizer_router import router as batch_optimizer_router
#
# router.include_router(link_router, tags=["fixes"])
# router.include_router(title_router, tags=["fixes"])
# router.include_router(heading_router, tags=["fixes"])
# router.include_router(image_router, tags=["fixes"])
# router.include_router(orphaned_media_router, tags=["fixes"])
# router.include_router(batch_optimizer_router, tags=["fixes"])

__all__ = ["router"]
