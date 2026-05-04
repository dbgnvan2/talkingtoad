# Fix Manager Router Implementation Guide

This document provides a template and pattern for implementing the 6 pending routers in the Fix Manager module. All routers follow the same architectural pattern established by `fix_manager_router.py`.

**Pending routers:**
1. `link_router.py` — Link replacement and broken link verification
2. `title_router.py` — Title optimization and bulk operations
3. `heading_router.py` — Heading level/text management
4. `image_router.py` — Image metadata and optimization
5. `orphaned_media_router.py` — Orphaned media detection and cleanup
6. `batch_optimizer_router.py` — Batch image optimization with pause/resume

---

## Pattern Overview

Each router follows this structure:

```python
"""Domain-specific router for {domain} fixes."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.models.{model} import {ResponseModel}
from api.routers.fixes_shared import (
    _validate_wp_domain_for_job,
    _validate_wp_domain_for_url,
    get_store,
    _CREDS_PATH,
)
from api.services.wp_fixer import {required_functions}
from api.services.error_responses import _err
from api.services.wp_client import WPClient, WPAuthError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fixes", dependencies=[Depends(require_auth)])

@router.post("/{endpoint_name}", response_model=ResponseModel)
async def endpoint_handler(
    job_id: str,
    # other params
    store=Depends(get_store),
) -> ResponseModel | JSONResponse:
    """Docstring with purpose and spec reference."""
    # 1. Validate job exists
    # 2. Validate WordPress domain
    # 3. Check credentials exist
    # 4. Connect to WordPress
    # 5. Perform operation
    # 6. Return response
```

**Key patterns:**
- All routers prefix `/api/fixes`
- All endpoints require authentication via `Depends(require_auth)`
- All endpoints validating WordPress check domain + credentials
- All endpoints use dependency injection for `store` and `wp` client
- All responses use Pydantic models defined in `api/models/` or `fixes_shared.py`
- All errors return JSONResponse from `_err()` helper

---

## 1. link_router.py

**Purpose:** Replace links, mark anchors as fixed, verify broken links

**Endpoints to implement:**

### POST /replace-link/{job_id}
Replace all instances of one URL with another across all posts.

```python
class ReplaceLinkRequest(BaseModel):
    old_url: str
    new_url: str

class ReplaceLinkResponse(BaseModel):
    posts_updated: int
    replacements_made: int
    errors: list[dict]  # [{"post_id": ..., "error": ...}]

@router.post("/replace-link/{job_id}", response_model=ReplaceLinkResponse)
async def replace_link_endpoint(
    job_id: str,
    body: ReplaceLinkRequest,
    store=Depends(get_store),
) -> ReplaceLinkResponse | JSONResponse:
    """Replace all instances of old_url with new_url in post content."""
    # 1. Validate job
    # 2. Validate WP domain
    # 3. Connect to WordPress
    # 4. For each post:
    #    a. Call wp_fixer.replace_link_in_post(wp, post_id, old_url, new_url)
    #    b. Collect results
    # 5. Return summary
```

### POST /mark-anchor-fixed/{job_id}
Mark a specific empty anchor as fixed (removes it from LINK_EMPTY_ANCHOR issues).

```python
class MarkAnchorFixedRequest(BaseModel):  # already in fixes_shared.py
    job_id: str
    page_url: str
    link_href: str

class MarkAnchorFixedResponse(BaseModel):  # already in fixes_shared.py
    success: bool
    remaining: int
    error: str | None = None

@router.post("/mark-anchor-fixed/{job_id}", response_model=MarkAnchorFixedResponse)
async def mark_anchor_fixed_endpoint(
    job_id: str,
    body: MarkAnchorFixedRequest,
    store=Depends(get_store),
) -> MarkAnchorFixedResponse | JSONResponse:
    """Mark a single empty anchor as fixed."""
    # 1. Get all issues for this job of type LINK_EMPTY_ANCHOR
    # 2. Find matching issue by page_url + link_href
    # 3. Update issue status to "fixed"
    # 4. Return remaining count of same issue type
```

### POST /verify-broken-links/{job_id}
Re-check status of previously broken links.

```python
class VerifyBrokenLinksResponse(BaseModel):  # already in fixes_shared.py
    total: int
    checked: int
    fixed: int
    still_broken: int
    errors: int
    results: list[VerifyResult]

@router.post("/verify-broken-links/{job_id}", response_model=VerifyBrokenLinksResponse)
async def verify_broken_links_endpoint(
    job_id: str,
    store=Depends(get_store),
) -> VerifyBrokenLinksResponse | JSONResponse:
    """Re-check status of all broken links in the crawl."""
    # 1. Get all broken link issues from store
    # 2. For each link:
    #    a. HEAD request to check current status
    #    b. Store result
    # 3. Return summary with count of newly fixed links
```

---

## 2. title_router.py

**Purpose:** Bulk title operations and predefined fix values

**Endpoints to implement:**

### POST /bulk-trim-titles/{job_id}
Apply the same title fix rule to multiple pages.

```python
class BulkTrimTitlesRequest(BaseModel):
    field: str  # "seo_title" or "wp_page_title"
    max_length: int = 60

class BulkTrimTitlesResponse(BaseModel):
    pages_updated: int
    titles_changed: int
    errors: list[dict]

@router.post("/bulk-trim-titles/{job_id}", response_model=BulkTrimTitlesResponse)
async def bulk_trim_titles_endpoint(
    job_id: str,
    body: BulkTrimTitlesRequest,
    store=Depends(get_store),
) -> BulkTrimTitlesResponse | JSONResponse:
    """Apply title trimming to multiple pages at once."""
    # 1. Validate job and WP domain
    # 2. Connect to WordPress
    # 3. Get all pages with TITLE_TOO_LONG or TITLE_MISSING
    # 4. For each page:
    #    a. Call wp_title_fixer.bulk_trim_titles(wp, field)
    #    b. Collect results
    # 5. Return summary
```

### POST /trim-one/{job_id}
Trim a single page's title.

```python
class TrimOneRequest(BaseModel):
    page_url: str
    field: str
    max_length: int = 60

@router.post("/trim-one/{job_id}", response_model=...)
async def trim_one_endpoint(...) -> ...:
    """Trim a single page's title to max_length."""
    # 1. Validate domain for URL
    # 2. Find WordPress post by URL
    # 3. Get current title value
    # 4. Call wp_title_fixer.trim_title(current, max_length)
    # 5. Update post with trimmed title
    # 6. Return updated value
```

### GET /predefined-codes
Get predefined fix values for common title problems.

```python
@router.get("/predefined-codes", response_model=dict)
async def get_predefined_codes() -> dict:
    """Return predefined title fix values."""
    # Return wp_shared.PREDEFINED_FIX_VALUES
    # Example: {"TITLE_TOO_LONG": {"max_length": 60}, "TITLE_MISSING": {"default": "..."}}
```

---

## 3. heading_router.py

**Purpose:** Heading level and text management

**Endpoints to implement:**

### POST /change-level/{job_id}
Promote or demote a heading (H1 → H2, H3 → H2, etc.).

```python
class ChangeHeadingLevelRequest(BaseModel):
    page_url: str
    current_level: int  # 1-6
    new_level: int      # 1-6

@router.post("/change-level/{job_id}", response_model=dict)
async def change_heading_level_endpoint(...) -> dict:
    """Change heading level."""
    # 1. Validate domain
    # 2. Find WordPress post by URL
    # 3. Call wp_heading_fixer.change_heading_level(wp, post_id, old_level, new_level)
    # 4. Return updated heading structure
```

### POST /change-text/{job_id}
Update the text content of a heading.

```python
class ChangeHeadingTextRequest(BaseModel):
    page_url: str
    level: int
    new_text: str

@router.post("/change-text/{job_id}", response_model=dict)
async def change_heading_text_endpoint(...) -> dict:
    """Change heading text content."""
    # 1. Validate domain
    # 2. Find WordPress post by URL
    # 3. Call wp_heading_fixer.change_heading_text(wp, post_id, level, new_text)
    # 4. Return updated heading
```

### POST /to-bold/{job_id}
Convert a heading to bold text (demote to paragraph with <strong>).

```python
class ToBoldRequest(BaseModel):
    page_url: str
    level: int

@router.post("/to-bold/{job_id}", response_model=dict)
async def convert_to_bold_endpoint(...) -> dict:
    """Convert heading to bold paragraph."""
    # 1. Get heading text
    # 2. Remove heading tag
    # 3. Add <strong> around text
    # 4. Update post content
```

### GET /analyze/{job_id}
Analyze heading structure of a page (H1/H2/H3 hierarchy).

```python
@router.get("/analyze/{job_id}", response_model=dict)
async def analyze_headings_endpoint(
    page_url: str,
    store=Depends(get_store),
) -> dict:
    """Analyze page heading structure."""
    # 1. Validate domain
    # 2. Find WordPress post by URL
    # 3. Call wp_heading_fixer.analyze_heading_sources(wp, post_id)
    # 4. Return structure with all H1-H6 headings and their positions
```

---

## 4. image_router.py

**Purpose:** Image metadata and optimization

**Endpoints to implement:**

### POST /update-meta/{job_id}
Update image metadata in WordPress (alt, title, caption, description).

```python
class UpdateImageMetaRequest(BaseModel):
    image_url: str
    alt_text: str | None = None
    title: str | None = None
    caption: str | None = None
    description: str | None = None

@router.post("/update-meta/{job_id}", response_model=dict)
async def update_image_meta_endpoint(...) -> dict:
    """Update image metadata in WordPress."""
    # 1. Validate domain for URL
    # 2. Connect to WordPress
    # 3. Find attachment by URL (slug-based query)
    # 4. Call wp_image_fixer.update_image_metadata(wp, attachment_id, ...)
    # 5. Return updated image metadata
```

### POST /refresh/{job_id}
Refresh image analysis from current WordPress state.

```python
@router.post("/refresh/{job_id}", response_model=dict)
async def refresh_image_analysis_endpoint(
    page_url: str,
    store=Depends(get_store),
) -> dict:
    """Refetch image metadata and analysis."""
    # 1. Validate domain
    # 2. Find all images on page_url from database
    # 3. For each image:
    #    a. Refetch from WordPress
    #    b. Update database
    # 4. Return updated images
```

### POST /optimize-existing/{job_id}
Optimize an image already in WordPress.

```python
class OptimizeExistingRequest(BaseModel):
    image_url: str
    target_size_kb: int = 200
    geo_settings: dict | None = None

@router.post("/optimize-existing/{job_id}", response_model=dict)
async def optimize_existing_image_endpoint(...) -> dict:
    """Download, optimize, and re-upload image."""
    # 1. Validate domain
    # 2. Connect to WordPress
    # 3. Call wp_image_fixer.optimize_existing_image(wp, image_url, target_size_kb, geo_settings)
    # 4. Return upload result with new image URL
```

### POST /optimize-local/{job_id}
Upload and optimize a local image file.

```python
class OptimizeLocalRequest(BaseModel):
    file_path: str  # local file to upload
    target_size_kb: int = 200
    geo_settings: dict | None = None

@router.post("/optimize-local/{job_id}", response_model=dict)
async def optimize_local_image_endpoint(...) -> dict:
    """Upload and optimize local image to WordPress."""
    # 1. Validate domain
    # 2. Connect to WordPress
    # 3. Call wp_image_fixer.optimize_local_image(wp, file_path, target_size_kb, geo_settings)
    # 4. Return upload result
```

### GET /analyze-geo/{job_id}
Generate GEO-optimized alt text and description.

```python
@router.get("/analyze-geo/{job_id}", response_model=dict)
async def analyze_geo_endpoint(
    image_url: str,
    page_url: str,
    store=Depends(get_store),
) -> dict:
    """Generate GEO-optimized image metadata."""
    # 1. Get image bytes from URL
    # 2. Get page context from database
    # 3. Get GEO settings from store
    # 4. Call AI analyzer with GEO prompt
    # 5. Return suggested alt text + description with entity annotations
```

### POST /apply-geo-metadata/{job_id}
Apply GEO-optimized metadata to WordPress image.

```python
class ApplyGeoMetadataRequest(BaseModel):
    image_url: str
    alt_text: str
    description: str

@router.post("/apply-geo-metadata/{job_id}", response_model=dict)
async def apply_geo_metadata_endpoint(...) -> dict:
    """Apply GEO-optimized metadata to WordPress."""
    # 1. Validate domain
    # 2. Find attachment by URL
    # 3. Update metadata
    # 4. Return updated image
```

---

## 5. orphaned_media_router.py

**Purpose:** Orphaned media detection and cleanup

**Endpoints to implement:**

### GET /orphaned/{job_id}
List orphaned images (in WordPress Media Library but not used on any page).

```python
@router.get("/orphaned/{job_id}", response_model=list[dict])
async def list_orphaned_endpoint(
    job_id: str,
    store=Depends(get_store),
) -> list[dict] | JSONResponse:
    """List orphaned images for the target domain."""
    # 1. Validate job and WP domain
    # 2. Connect to WordPress
    # 3. Call wp_fixer.find_orphaned_media(wp)
    # 4. Return list of orphaned attachment IDs + metadata
```

### POST /delete/{job_id}
Delete one or more orphaned images.

```python
class DeleteOrphanedRequest(BaseModel):
    attachment_ids: list[int]  # IDs to delete

class DeleteOrphanedResponse(BaseModel):
    deleted: int
    errors: list[dict]

@router.post("/delete/{job_id}", response_model=DeleteOrphanedResponse)
async def delete_orphaned_endpoint(...) -> DeleteOrphanedResponse | JSONResponse:
    """Delete selected orphaned images."""
    # 1. Validate domain
    # 2. Connect to WordPress
    # 3. For each attachment_id:
    #    a. DELETE /wp-json/wp/v2/media/{id}?force=true
    #    b. Collect result
    # 4. Return summary (deleted count, errors)
```

### GET /export-csv/{job_id}
Export orphaned media list as CSV.

```python
@router.get("/export-csv/{job_id}", response_class=...)
async def export_orphaned_csv_endpoint(
    job_id: str,
    store=Depends(get_store),
) -> ...:
    """Export orphaned media as CSV file."""
    # 1. Get orphaned media list
    # 2. Format as CSV (filename, size, upload_date, dimensions)
    # 3. Return with Content-Disposition header for download
```

---

## 6. batch_optimizer_router.py

**Purpose:** Batch image optimization with pause/resume

**Endpoints to implement:**

### POST /start/{job_id}
Start a batch optimization job.

```python
class StartBatchRequest(BaseModel):
    image_urls: list[str]
    target_size_kb: int = 200
    max_concurrent: int = 3
    geo_settings: dict | None = None

class StartBatchResponse(BaseModel):
    batch_id: str
    total_images: int
    status: str  # "running"

@router.post("/start/{job_id}", response_model=StartBatchResponse)
async def start_batch_endpoint(...) -> StartBatchResponse | JSONResponse:
    """Start batch optimization."""
    # 1. Validate domain
    # 2. Create batch job in store with "running" status
    # 3. Spawn async task for batch processing
    # 4. Return batch_id for polling
```

### GET /status/{job_id}
Check batch optimization status.

```python
class BatchStatus(BaseModel):
    batch_id: str
    status: str  # "running", "paused", "completed", "cancelled"
    total: int
    processed: int
    succeeded: int
    failed: int
    results: list[dict]  # per-image status

@router.get("/status/{job_id}", response_model=BatchStatus)
async def get_batch_status_endpoint(
    job_id: str,
    batch_id: str,
    store=Depends(get_store),
) -> BatchStatus | JSONResponse:
    """Get batch optimization status."""
    # 1. Fetch batch record from store
    # 2. Return current status and per-image results
```

### POST /pause/{job_id}
Pause an in-progress batch.

```python
@router.post("/pause/{job_id}", response_model=dict)
async def pause_batch_endpoint(
    job_id: str,
    batch_id: str,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Pause batch optimization."""
    # 1. Update batch status to "paused"
    # 2. Stop processing new images
    # 3. Allow resume from current position
```

### POST /resume/{job_id}
Resume a paused batch.

```python
@router.post("/resume/{job_id}", response_model=dict)
async def resume_batch_endpoint(
    job_id: str,
    batch_id: str,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Resume paused batch optimization."""
    # 1. Update batch status to "running"
    # 2. Continue processing from where it paused
```

### POST /cancel/{job_id}
Cancel a batch optimization job.

```python
@router.post("/cancel/{job_id}", response_model=dict)
async def cancel_batch_endpoint(
    job_id: str,
    batch_id: str,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Cancel batch optimization."""
    # 1. Update batch status to "cancelled"
    # 2. Stop all processing
    # 3. Clean up temporary files
```

---

## Integration Checklist

For each router implementation:

- [ ] **Module creation** — Create `{domain}_router.py` in `api/routers/`
- [ ] **Imports** — All required imports from wp_fixer, models, error_responses
- [ ] **Models** — Define request/response Pydantic models in module or fixes_shared.py
- [ ] **Endpoints** — Implement all required @router.post/@router.get endpoints
- [ ] **Validation** — Validate job, WP domain, credentials before operations
- [ ] **Error handling** — Return JSONResponse(_err(...)) for all error cases
- [ ] **Logging** — Log operations with context (job_id, affected resources)
- [ ] **Testing** — Add `test_{domain}_router.py` with endpoint tests
- [ ] **Registration** — Add `from api.routers.{domain}_router import router as {domain}_router` to fixes.py
- [ ] **include_router** — Add `router.include_router({domain}_router, tags=["fixes"])` to fixes.py
- [ ] **Documentation** — Update `docs/architecture.md` to document new endpoints
- [ ] **API docs** — Add OpenAPI docstrings to endpoint functions (auto-exposed in /docs)

---

## Testing Pattern

Each router should have corresponding test file:

```python
# tests/test_{domain}_router.py
import pytest
from httpx import AsyncClient
from api.main import app

@pytest.mark.asyncio
async def test_{endpoint}_success():
    """Test successful {endpoint} operation."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            f"/api/fixes/{endpoint}/{job_id}",
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
            json={...},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True

@pytest.mark.asyncio
async def test_{endpoint}_missing_job():
    """Test {endpoint} with nonexistent job."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            f"/api/fixes/{endpoint}/nonexistent-job-id",
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
            json={...},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["code"] == "JOB_NOT_FOUND"

@pytest.mark.asyncio
async def test_{endpoint}_domain_mismatch():
    """Test {endpoint} with domain mismatch."""
    # WordPress credentials for wrong domain
    # Should return 403 DOMAIN_MISMATCH
```

---

## Backward Compatibility

All routers must maintain backward compatibility:
- Endpoint URLs cannot change after initial implementation
- Request/response models cannot have breaking changes
- New fields should be optional with defaults
- Deprecated fields should be kept for one major version

---

## Questions & Support

For implementation questions, refer to:
1. `fix_manager_router.py` — established pattern
2. `api/services/wp_fixer.py` — available functions for each domain
3. `api/models/` — Pydantic models available for responses
4. `api/services/error_responses.py` — error response patterns

