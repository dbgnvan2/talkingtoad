# Image Intelligence & Optimization Plan - v1.9image

## Release Overview
- **Version**: 1.9image
- **Goal**: Dual-purpose engine for image **auditing** AND **automated optimization**
- **Key Features**:
  - Comprehensive image analysis with scoring
  - Automated compression, resizing, WebP conversion
  - Dedicated Image Analysis UI with thumbnails
- **Future (v2)**: Browser rendering (Playwright), LCP detection, local AI models

---

## PHASE 1: Data Model & Infrastructure

### Task 1.1: Create ImageInfo Model
**File**: `api/models/image.py` (NEW)

```python
@dataclass
class ImageInfo:
    url: str
    page_url: str
    alt: str | None
    title: str | None
    filename: str
    format: str  # jpeg, png, webp, avif, svg, gif, unknown
    width: int | None  # intrinsic
    height: int | None  # intrinsic
    rendered_width: int | None  # from HTML attributes
    rendered_height: int | None  # from HTML attributes
    file_size_bytes: int | None
    load_time_ms: int | None
    http_status: int
    is_lazy_loaded: bool
    has_srcset: bool
    srcset_candidates: list[str]
    is_decorative: bool
    surrounding_text: str  # ±200 chars around img tag
    content_hash: str | None  # for duplicate detection

    # Scores (computed)
    performance_score: float = 0.0
    accessibility_score: float = 0.0
    semantic_score: float = 0.0
    technical_score: float = 0.0
    overall_score: float = 0.0
```

### Task 1.2: Create Image Store Methods
**File**: `api/services/job_store.py`

Add methods:
- `save_images(job_id: str, images: list[ImageInfo])`
- `get_images(job_id: str) -> list[ImageInfo]`
- `get_image_summary(job_id: str) -> dict`

Add SQLite table:
```sql
CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    job_id TEXT NOT NULL,
    url TEXT NOT NULL,
    page_url TEXT NOT NULL,
    alt TEXT,
    title TEXT,
    filename TEXT,
    format TEXT,
    width INTEGER,
    height INTEGER,
    rendered_width INTEGER,
    rendered_height INTEGER,
    file_size_bytes INTEGER,
    load_time_ms INTEGER,
    http_status INTEGER,
    is_lazy_loaded BOOLEAN,
    has_srcset BOOLEAN,
    srcset_candidates TEXT,  -- JSON array
    is_decorative BOOLEAN,
    surrounding_text TEXT,
    content_hash TEXT,
    performance_score REAL,
    accessibility_score REAL,
    semantic_score REAL,
    technical_score REAL,
    overall_score REAL,
    UNIQUE(job_id, url)
);
```

---

## PHASE 2: Parser Enhancements

### Task 2.1: Enhanced Image Extraction
**File**: `api/crawler/parser.py`

Update `_extract_image_urls` to return full image data:

```python
def _extract_image_data(soup: BeautifulSoup, page_url: str) -> list[dict]:
    """Extract comprehensive image data from page."""
    images = []
    for tag in soup.find_all("img", src=True):
        src = tag["src"].strip()
        if not src or src.startswith("data:"):
            continue

        img_data = {
            "url": urljoin(page_url, src),
            "alt": tag.get("alt"),
            "title": tag.get("title"),
            "rendered_width": _parse_dimension(tag.get("width")),
            "rendered_height": _parse_dimension(tag.get("height")),
            "is_lazy_loaded": tag.get("loading") == "lazy",
            "has_srcset": bool(tag.get("srcset")),
            "srcset_candidates": _parse_srcset(tag.get("srcset", "")),
            "is_decorative": _detect_decorative(tag),
            "surrounding_text": _extract_surrounding_text(tag, limit=200),
        }
        images.append(img_data)
    return images
```

### Task 2.2: Decorative Detection
**File**: `api/crawler/parser.py`

```python
def _detect_decorative(tag) -> bool:
    """Detect if image is decorative."""
    # Explicit decorative markers
    if tag.get("role") == "presentation":
        return True
    if tag.get("aria-hidden") == "true":
        return True

    # Empty alt is intentionally decorative
    alt = tag.get("alt")
    if alt is not None and alt.strip() == "":
        return True

    # Tiny images (icons/spacers)
    try:
        w = int(tag.get("width", 999))
        h = int(tag.get("height", 999))
        if w < 32 and h < 32:
            return True
    except (ValueError, TypeError):
        pass

    return False
```

### Task 2.3: Srcset Parsing
**File**: `api/crawler/parser.py`

```python
def _parse_srcset(srcset: str) -> list[str]:
    """Parse srcset attribute into list of URLs."""
    if not srcset:
        return []
    candidates = []
    for part in srcset.split(","):
        part = part.strip()
        if part:
            url = part.split()[0]  # First part is URL
            candidates.append(url)
    return candidates
```

### Task 2.4: Surrounding Text Extraction
**File**: `api/crawler/parser.py`

```python
def _extract_surrounding_text(tag, limit: int = 200) -> str:
    """Extract text surrounding an image tag."""
    texts = []

    # Previous siblings
    for sib in tag.previous_siblings:
        if hasattr(sib, 'get_text'):
            texts.insert(0, sib.get_text(strip=True))
        elif isinstance(sib, str):
            texts.insert(0, sib.strip())
        if sum(len(t) for t in texts) > limit:
            break

    # Next siblings
    for sib in tag.next_siblings:
        if hasattr(sib, 'get_text'):
            texts.append(sib.get_text(strip=True))
        elif isinstance(sib, str):
            texts.append(sib.strip())
        if sum(len(t) for t in texts) > limit * 2:
            break

    return " ".join(texts)[:limit * 2]
```

---

## PHASE 3: Image Fetcher

### Task 3.1: Full Image Fetch Function
**File**: `api/crawler/engine.py`

```python
async def _fetch_image_full(
    url: str,
    client: httpx.AsyncClient,
    timeout: float = 5.0,
    max_size: int = 5 * 1024 * 1024  # 5MB
) -> dict:
    """Fetch full image data including bytes."""
    start_time = time.time()
    result = {
        "url": url,
        "http_status": 0,
        "file_size_bytes": None,
        "load_time_ms": None,
        "width": None,
        "height": None,
        "format": "unknown",
        "content_hash": None,
        "error": None,
    }

    try:
        response = await client.get(url, timeout=timeout)
        result["http_status"] = response.status_code
        result["load_time_ms"] = int((time.time() - start_time) * 1000)

        if response.status_code < 400:
            content = response.content
            result["file_size_bytes"] = len(content)
            result["content_hash"] = hashlib.md5(content).hexdigest()

            # Get dimensions using Pillow
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(content))
                result["width"], result["height"] = img.size
                result["format"] = img.format.lower() if img.format else "unknown"
            except Exception:
                pass

    except Exception as e:
        result["error"] = str(e)
        result["load_time_ms"] = int((time.time() - start_time) * 1000)

    return result
```

### Task 3.2: Update Engine Image Queue Processing
**File**: `api/crawler/engine.py`

Replace HEAD-only checking with full GET:

```python
# ── 5.5 Image Analysis ─────────────────────────────────────
all_images: list[ImageInfo] = []
image_hashes: dict[str, str] = {}  # hash -> first URL (for duplicates)

for img_data in image_url_queue:
    if cancel_event and cancel_event.is_set():
        break

    # Merge parsed data with fetched data
    fetch_result = await _fetch_image_full(img_data["image_url"], client)

    image_info = ImageInfo(
        url=img_data["image_url"],
        page_url=img_data["page_url"],
        alt=img_data.get("alt"),
        title=img_data.get("title"),
        filename=_extract_filename(img_data["image_url"]),
        format=fetch_result["format"],
        width=fetch_result["width"],
        height=fetch_result["height"],
        rendered_width=img_data.get("rendered_width"),
        rendered_height=img_data.get("rendered_height"),
        file_size_bytes=fetch_result["file_size_bytes"],
        load_time_ms=fetch_result["load_time_ms"],
        http_status=fetch_result["http_status"],
        is_lazy_loaded=img_data.get("is_lazy_loaded", False),
        has_srcset=img_data.get("has_srcset", False),
        srcset_candidates=img_data.get("srcset_candidates", []),
        is_decorative=img_data.get("is_decorative", False),
        surrounding_text=img_data.get("surrounding_text", ""),
        content_hash=fetch_result["content_hash"],
    )

    # Track duplicates
    if image_info.content_hash:
        if image_info.content_hash in image_hashes:
            image_info.duplicate_of = image_hashes[image_info.content_hash]
        else:
            image_hashes[image_info.content_hash] = image_info.url

    all_images.append(image_info)
```

---

## PHASE 4: Image Issue Checker

### Task 4.1: Create Image Analysis Module
**File**: `api/crawler/image_analyzer.py` (NEW)

```python
"""Image analysis and issue detection."""

from api.models.image import ImageInfo
from api.models.issue import Issue
from api.crawler.issue_checker import make_issue

# Configuration defaults
DEFAULT_CONFIG = {
    "max_image_size_kb": 200,
    "slow_load_threshold_ms": 1000,
    "bpp_threshold": 0.5,
    "alt_min_length": 5,
    "alt_max_length": 125,
    "overscale_ratio": 2.0,
    "legacy_format_threshold_kb": 50,
}

GENERIC_ALT_TERMS = {"image", "photo", "picture", "pic", "img", "graphic", "icon"}


def analyze_image(img: ImageInfo, config: dict = None) -> tuple[list[Issue], dict]:
    """
    Analyze a single image and return issues + scores.

    Returns:
        (issues, scores_dict)
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    issues = []

    # ALT TEXT ANALYSIS
    issues.extend(_check_alt_text(img, cfg))

    # SIZE & PERFORMANCE
    issues.extend(_check_performance(img, cfg))

    # FORMAT ANALYSIS
    issues.extend(_check_format(img, cfg))

    # RESPONSIVE
    issues.extend(_check_responsive(img, cfg))

    # BROKEN
    issues.extend(_check_broken(img))

    # DUPLICATES (handled at batch level)

    # Calculate scores
    scores = _calculate_scores(img, issues, cfg)

    return issues, scores


def _check_alt_text(img: ImageInfo, cfg: dict) -> list[Issue]:
    """Check alt text issues."""
    issues = []
    alt = img.alt

    # IMG_ALT_MISSING - only for non-decorative
    if not img.is_decorative:
        if alt is None or (isinstance(alt, str) and not alt.strip()):
            issues.append(make_issue(
                "IMG_ALT_MISSING", img.page_url,
                extra={"image_url": img.url}
            ))
            return issues  # No point checking quality if missing

    # IMG_ALT_MISUSED
    if img.is_decorative and alt and alt.strip():
        issues.append(make_issue(
            "IMG_ALT_MISUSED", img.page_url,
            extra={"image_url": img.url, "reason": "decorative_with_alt"}
        ))

    if alt:
        alt_clean = alt.strip()

        # IMG_ALT_TOO_SHORT
        if len(alt_clean) < cfg["alt_min_length"]:
            issues.append(make_issue(
                "IMG_ALT_TOO_SHORT", img.page_url,
                extra={"image_url": img.url, "length": len(alt_clean)}
            ))

        # IMG_ALT_TOO_LONG
        if len(alt_clean) > cfg["alt_max_length"]:
            issues.append(make_issue(
                "IMG_ALT_TOO_LONG", img.page_url,
                extra={"image_url": img.url, "length": len(alt_clean)}
            ))

        # IMG_ALT_GENERIC
        if alt_clean.lower() in GENERIC_ALT_TERMS:
            issues.append(make_issue(
                "IMG_ALT_GENERIC", img.page_url,
                extra={"image_url": img.url, "alt": alt_clean}
            ))

        # IMG_ALT_DUP_FILENAME
        filename_base = img.filename.rsplit(".", 1)[0] if img.filename else ""
        if filename_base and _normalize(alt_clean) == _normalize(filename_base):
            issues.append(make_issue(
                "IMG_ALT_DUP_FILENAME", img.page_url,
                extra={"image_url": img.url, "alt": alt_clean, "filename": img.filename}
            ))

    return issues


def _check_performance(img: ImageInfo, cfg: dict) -> list[Issue]:
    """Check performance issues."""
    issues = []

    # IMG_OVERSIZED
    if img.file_size_bytes:
        limit_bytes = cfg["max_image_size_kb"] * 1024
        if img.file_size_bytes > limit_bytes:
            issues.append(make_issue(
                "IMG_OVERSIZED", img.page_url,
                extra={
                    "image_url": img.url,
                    "size_kb": round(img.file_size_bytes / 1024, 1),
                    "limit_kb": cfg["max_image_size_kb"]
                }
            ))

    # IMG_SLOW_LOAD
    if img.load_time_ms and img.load_time_ms > cfg["slow_load_threshold_ms"]:
        issues.append(make_issue(
            "IMG_SLOW_LOAD", img.page_url,
            extra={
                "image_url": img.url,
                "load_time_ms": img.load_time_ms,
                "threshold_ms": cfg["slow_load_threshold_ms"]
            }
        ))

    # IMG_OVERSCALED
    if img.width and img.rendered_width:
        ratio = img.width / img.rendered_width
        if ratio > cfg["overscale_ratio"]:
            issues.append(make_issue(
                "IMG_OVERSCALED", img.page_url,
                extra={
                    "image_url": img.url,
                    "intrinsic_width": img.width,
                    "rendered_width": img.rendered_width,
                    "ratio": round(ratio, 1)
                }
            ))

    # IMG_POOR_COMPRESSION
    if img.file_size_bytes and img.width and img.height:
        pixels = img.width * img.height
        if pixels > 0:
            bpp = img.file_size_bytes / pixels
            if bpp > cfg["bpp_threshold"]:
                issues.append(make_issue(
                    "IMG_POOR_COMPRESSION", img.page_url,
                    extra={
                        "image_url": img.url,
                        "bpp": round(bpp, 2),
                        "threshold": cfg["bpp_threshold"]
                    }
                ))

    return issues


def _check_format(img: ImageInfo, cfg: dict) -> list[Issue]:
    """Check format issues."""
    issues = []

    legacy_formats = {"jpeg", "jpg", "png", "gif"}
    if img.format and img.format.lower() in legacy_formats:
        threshold_bytes = cfg["legacy_format_threshold_kb"] * 1024
        if img.file_size_bytes and img.file_size_bytes > threshold_bytes:
            issues.append(make_issue(
                "IMG_FORMAT_LEGACY", img.page_url,
                extra={
                    "image_url": img.url,
                    "format": img.format,
                    "size_kb": round(img.file_size_bytes / 1024, 1)
                }
            ))

    return issues


def _check_responsive(img: ImageInfo, cfg: dict) -> list[Issue]:
    """Check responsive image issues."""
    issues = []

    # IMG_NO_SRCSET
    if not img.has_srcset:
        # Only flag if image is being scaled down
        if img.width and img.rendered_width and img.width > img.rendered_width:
            issues.append(make_issue(
                "IMG_NO_SRCSET", img.page_url,
                extra={
                    "image_url": img.url,
                    "intrinsic_width": img.width,
                    "rendered_width": img.rendered_width
                }
            ))

    return issues


def _check_broken(img: ImageInfo) -> list[Issue]:
    """Check for broken images."""
    issues = []

    if img.http_status >= 400:
        issues.append(make_issue(
            "IMG_BROKEN", img.page_url,
            extra={
                "image_url": img.url,
                "status_code": img.http_status
            }
        ))

    return issues


def check_duplicates(images: list[ImageInfo]) -> list[Issue]:
    """Check for duplicate images across the site."""
    issues = []
    hash_to_images: dict[str, list[ImageInfo]] = {}

    for img in images:
        if img.content_hash:
            if img.content_hash not in hash_to_images:
                hash_to_images[img.content_hash] = []
            hash_to_images[img.content_hash].append(img)

    for hash_val, imgs in hash_to_images.items():
        if len(imgs) > 1:
            # Check if alt text differs
            alts = set(img.alt for img in imgs if img.alt)
            if len(alts) > 1:
                for img in imgs[1:]:  # Skip first occurrence
                    issues.append(make_issue(
                        "IMG_DUPLICATE_CONTENT", img.page_url,
                        extra={
                            "image_url": img.url,
                            "duplicate_of": imgs[0].url,
                            "different_alts": list(alts)
                        }
                    ))

    return issues


def _calculate_scores(img: ImageInfo, issues: list[Issue], cfg: dict) -> dict:
    """Calculate image scores."""
    issue_codes = {i.issue_code for i in issues}

    # Performance score (0-100)
    perf = 100
    if "IMG_OVERSIZED" in issue_codes:
        perf -= 30
    if "IMG_SLOW_LOAD" in issue_codes:
        perf -= 25
    if "IMG_POOR_COMPRESSION" in issue_codes:
        perf -= 20
    if "IMG_OVERSCALED" in issue_codes:
        perf -= 15
    if "IMG_FORMAT_LEGACY" in issue_codes:
        perf -= 10

    # Accessibility score (0-100)
    access = 100
    if "IMG_ALT_MISSING" in issue_codes:
        access -= 50
    if "IMG_ALT_MISUSED" in issue_codes:
        access -= 30
    if "IMG_ALT_TOO_SHORT" in issue_codes:
        access -= 15
    if "IMG_ALT_TOO_LONG" in issue_codes:
        access -= 10
    if "IMG_ALT_GENERIC" in issue_codes:
        access -= 20
    if "IMG_ALT_DUP_FILENAME" in issue_codes:
        access -= 15

    # Technical score (0-100)
    tech = 100
    if "IMG_BROKEN" in issue_codes:
        tech -= 50
    if "IMG_NO_SRCSET" in issue_codes:
        tech -= 20
    if "IMG_DUPLICATE_CONTENT" in issue_codes:
        tech -= 15

    # Semantic score (placeholder for Phase 4)
    semantic = 100

    # Overall weighted score
    overall = (
        0.30 * max(0, perf) +
        0.30 * max(0, access) +
        0.20 * max(0, semantic) +
        0.20 * max(0, tech)
    )

    return {
        "performance_score": max(0, perf),
        "accessibility_score": max(0, access),
        "semantic_score": max(0, semantic),
        "technical_score": max(0, tech),
        "overall_score": round(overall, 1),
    }


def _normalize(s: str) -> str:
    """Normalize string for comparison."""
    import re
    return re.sub(r'[^a-z0-9]', '', s.lower())
```

### Task 4.2: Add New Issue Codes to Catalogue
**File**: `api/crawler/issue_checker.py`

Add to `_CATALOGUE`:

```python
# ── IMAGE ISSUES (v1.9) ────────────────────────────────────────────────────

# ACCESSIBILITY & ALT QUALITY
"IMG_ALT_MISSING": _IssueSpec(
    category="image", severity="critical",
    description="Image is missing alt text (non-decorative image)",
    recommendation="Add descriptive alt text that describes what the image shows.",
    human_description="Missing Alt Text",
),

"IMG_ALT_QUALITY": _IssueSpec(
    category="image", severity="warning",
    description="Image alt text has quality issues (too short, too long, or generic)",
    recommendation="Alt text should be 5-125 characters and describe the specific image content. Avoid generic terms like 'image' or 'photo'.",
    human_description="Poor Alt Text Quality",
),

"IMG_ALT_DUP_FILENAME": _IssueSpec(
    category="image", severity="warning",
    description="Image alt text is the same as the filename",
    recommendation="Write descriptive alt text instead of using the filename. Describe what the image shows.",
    human_description="Alt Text Matches Filename",
),

"IMG_ALT_MISUSED": _IssueSpec(
    category="image", severity="warning",
    description="Alt text usage is incorrect for image type (decorative with alt, or meaningful without)",
    recommendation="Decorative images should have empty alt=''. Meaningful images need descriptive alt text.",
    human_description="Alt Text Misused",
),

# PERFORMANCE
"IMG_OVERSIZED": _IssueSpec(
    category="image", severity="warning",
    description="Image file size exceeds recommended limit",
    recommendation="Compress or resize the image. Use the 'Optimize' button to automatically fix.",
    human_description="Oversized Image",
),

"IMG_SLOW_LOAD": _IssueSpec(
    category="image", severity="warning",
    description="Image takes too long to load (>1 second)",
    recommendation="Optimize the image size, use a CDN, or enable lazy loading.",
    human_description="Slow Loading Image",
),

"IMG_OVERSCALED": _IssueSpec(
    category="image", severity="warning",
    description="Image intrinsic size is >2x its display size (wasted bandwidth)",
    recommendation="Resize the image to match display dimensions or use srcset for responsive delivery.",
    human_description="Overscaled Image",
),

"IMG_POOR_COMPRESSION": _IssueSpec(
    category="image", severity="warning",
    description="Image has poor compression efficiency (BPP > 0.5)",
    recommendation="Re-compress using WebP format for better efficiency.",
    human_description="Poor Compression",
),

"IMG_FORMAT_LEGACY": _IssueSpec(
    category="image", severity="info",
    description="Image uses legacy format (JPEG/PNG/GIF) where WebP would save >30%",
    recommendation="Convert to WebP format for significant file size reduction.",
    human_description="Legacy Image Format",
),

# TECHNICAL
"IMG_NO_SRCSET": _IssueSpec(
    category="image", severity="info",
    description="Large image lacks srcset for responsive delivery",
    recommendation="Add srcset attribute to serve appropriately sized images to different devices.",
    human_description="Missing Responsive Images",
),

"IMG_BROKEN": _IssueSpec(
    category="image", severity="critical",
    description="Image returns HTTP error (4xx/5xx)",
    recommendation="Fix or remove the broken image reference.",
    human_description="Broken Image",
),

"IMG_DUPLICATE_CONTENT": _IssueSpec(
    category="image", severity="info",
    description="Same image used multiple times with different alt text",
    recommendation="Use consistent alt text for the same image across pages.",
    human_description="Duplicate Image",
),

# SEMANTIC / GEO (Phase 4)
"IMG_SEMANTIC_DRIFT": _IssueSpec(
    category="image", severity="info",
    description="Image alt text doesn't align with page topic",
    recommendation="Update alt text to better reflect the page content and topic.",
    human_description="Alt Text Off-Topic",
),

"IMG_ALT_NO_ENTITIES": _IssueSpec(
    category="image", severity="info",
    description="Alt text lacks named entities (places, people, specific concepts)",
    recommendation="Include specific names, places, or concepts in alt text for better SEO.",
    human_description="Alt Text Missing Entities",
),
```

---

## PHASE 5: Image Optimizer (Execution Module)

### Task 5.1: Create ImageOptimizer Class
**File**: `api/services/image_optimizer.py` (NEW)

```python
"""Image optimization engine - compression, resizing, conversion."""

import os
import hashlib
import shutil
from pathlib import Path
from PIL import Image
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    original_url: str
    optimized_url: Optional[str]
    original_size_kb: float
    optimized_size_kb: Optional[float]
    savings_percent: Optional[float]
    original_dimensions: str
    new_dimensions: Optional[str]
    format_change: Optional[str]
    backup_path: str
    status: str  # success, skipped, failed
    skip_reason: Optional[str] = None
    error: Optional[str] = None


class ImageOptimizer:
    """Automated image optimization with safety rules."""

    # Configuration
    DEFAULT_MAX_WIDTH = 1200
    WEBP_QUALITY = 80
    WEBP_METHOD = 6  # Best compression
    MIN_SAVINGS_PERCENT = 5  # Don't bother if < 5% savings

    def __init__(
        self,
        backup_dir: str,
        production_dir: str,
        archive_dir: str,
        max_width: int = DEFAULT_MAX_WIDTH,
    ):
        self.backup_dir = Path(backup_dir)
        self.production_dir = Path(production_dir)
        self.archive_dir = Path(archive_dir)
        self.max_width = max_width

        # Ensure directories exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    async def optimize(
        self,
        image_path: str,
        rendered_width: Optional[int] = None,
        job_id: str = "unknown",
    ) -> OptimizationResult:
        """
        Optimize a single image with full safety checks.

        Pipeline:
        1. Backup original
        2. Smart resize (no upscaling)
        3. Convert to WebP
        4. Negative compression check
        5. Verify and replace
        6. Dual save
        """
        original_path = Path(image_path)

        if not original_path.exists():
            return OptimizationResult(
                original_url=image_path,
                optimized_url=None,
                original_size_kb=0,
                optimized_size_kb=None,
                savings_percent=None,
                original_dimensions="unknown",
                new_dimensions=None,
                format_change=None,
                backup_path="",
                status="failed",
                error="File not found",
            )

        # Get original stats
        original_size = original_path.stat().st_size
        original_size_kb = original_size / 1024

        try:
            with Image.open(original_path) as img:
                original_width, original_height = img.size
                original_format = img.format or "unknown"
        except Exception as e:
            return OptimizationResult(
                original_url=image_path,
                optimized_url=None,
                original_size_kb=original_size_kb,
                optimized_size_kb=None,
                savings_percent=None,
                original_dimensions="unknown",
                new_dimensions=None,
                format_change=None,
                backup_path="",
                status="failed",
                error=f"Cannot open image: {e}",
            )

        # 1. BACKUP
        backup_path = self._backup_original(original_path, job_id)

        # 2. CALCULATE TARGET SIZE
        target_width = self._calculate_target_width(
            original_width, rendered_width
        )

        # NO-UPSCALE RULE
        if target_width >= original_width:
            # Check if format conversion alone would help
            if original_format.lower() in ("webp", "avif"):
                return OptimizationResult(
                    original_url=image_path,
                    optimized_url=None,
                    original_size_kb=original_size_kb,
                    optimized_size_kb=None,
                    savings_percent=None,
                    original_dimensions=f"{original_width}x{original_height}",
                    new_dimensions=None,
                    format_change=None,
                    backup_path=str(backup_path),
                    status="skipped",
                    skip_reason="already_optimal",
                )
            # Continue with format conversion only
            target_width = original_width

        # 3. OPTIMIZE
        new_filename = f"{original_path.stem}-small.webp"
        temp_path = self.backup_dir / job_id / new_filename

        try:
            with Image.open(original_path) as img:
                # Resize if needed
                if target_width < original_width:
                    ratio = target_width / original_width
                    new_height = int(original_height * ratio)
                    img = img.resize(
                        (target_width, new_height),
                        Image.Resampling.LANCZOS
                    )
                    new_dimensions = f"{target_width}x{new_height}"
                else:
                    new_dimensions = f"{original_width}x{original_height}"

                # Convert to RGB if necessary (WebP doesn't support all modes)
                if img.mode in ("RGBA", "P"):
                    # Keep alpha for RGBA
                    pass
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                # Save as WebP
                img.save(
                    temp_path,
                    "WEBP",
                    quality=self.WEBP_QUALITY,
                    method=self.WEBP_METHOD,
                )

        except Exception as e:
            return OptimizationResult(
                original_url=image_path,
                optimized_url=None,
                original_size_kb=original_size_kb,
                optimized_size_kb=None,
                savings_percent=None,
                original_dimensions=f"{original_width}x{original_height}",
                new_dimensions=None,
                format_change=None,
                backup_path=str(backup_path),
                status="failed",
                error=f"Optimization failed: {e}",
            )

        # 4. NEGATIVE COMPRESSION CHECK
        optimized_size = temp_path.stat().st_size
        optimized_size_kb = optimized_size / 1024
        savings_percent = ((original_size - optimized_size) / original_size) * 100

        if optimized_size >= original_size:
            temp_path.unlink()  # Delete the larger file
            return OptimizationResult(
                original_url=image_path,
                optimized_url=None,
                original_size_kb=original_size_kb,
                optimized_size_kb=optimized_size_kb,
                savings_percent=savings_percent,
                original_dimensions=f"{original_width}x{original_height}",
                new_dimensions=new_dimensions,
                format_change=f"{original_format} → webp",
                backup_path=str(backup_path),
                status="skipped",
                skip_reason="negative_compression",
            )

        if savings_percent < self.MIN_SAVINGS_PERCENT:
            temp_path.unlink()
            return OptimizationResult(
                original_url=image_path,
                optimized_url=None,
                original_size_kb=original_size_kb,
                optimized_size_kb=optimized_size_kb,
                savings_percent=savings_percent,
                original_dimensions=f"{original_width}x{original_height}",
                new_dimensions=new_dimensions,
                format_change=f"{original_format} → webp",
                backup_path=str(backup_path),
                status="skipped",
                skip_reason="minimal_savings",
            )

        # 5. VERIFICATION - Check BPP
        with Image.open(temp_path) as img:
            w, h = img.size
        pixels = w * h
        bpp = optimized_size / pixels if pixels > 0 else 0

        if bpp > 0.5:
            logger.warning(f"Post-optimization BPP still high: {bpp:.2f}")

        # 6. DUAL SAVE
        production_path = self.production_dir / new_filename
        archive_path = self.archive_dir / job_id / new_filename

        archive_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temp_path, archive_path)

        # Move to production (or copy if different filesystem)
        if production_path.parent.exists():
            shutil.move(str(temp_path), str(production_path))
            optimized_url = str(production_path)
        else:
            optimized_url = str(temp_path)

        return OptimizationResult(
            original_url=image_path,
            optimized_url=optimized_url,
            original_size_kb=round(original_size_kb, 1),
            optimized_size_kb=round(optimized_size_kb, 1),
            savings_percent=round(savings_percent, 1),
            original_dimensions=f"{original_width}x{original_height}",
            new_dimensions=new_dimensions,
            format_change=f"{original_format} → webp",
            backup_path=str(backup_path),
            status="success",
        )

    def _backup_original(self, path: Path, job_id: str) -> Path:
        """Backup original file before modification."""
        backup_dir = self.backup_dir / job_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / path.name
        shutil.copy2(path, backup_path)
        return backup_path

    def _calculate_target_width(
        self,
        intrinsic_width: int,
        rendered_width: Optional[int],
    ) -> int:
        """Calculate optimal target width."""
        if rendered_width and rendered_width < intrinsic_width:
            return min(rendered_width, self.max_width)
        return min(intrinsic_width, self.max_width)


async def batch_optimize(
    optimizer: ImageOptimizer,
    images: list[dict],
    job_id: str,
) -> list[OptimizationResult]:
    """Optimize multiple images."""
    results = []
    for img in images:
        # Only optimize if flagged for performance issues
        if any(code in img.get("issues", []) for code in [
            "IMG_OVERSIZED", "IMG_OVERSCALED",
            "IMG_POOR_COMPRESSION", "IMG_FORMAT_LEGACY"
        ]):
            result = await optimizer.optimize(
                img["local_path"],
                rendered_width=img.get("rendered_width"),
                job_id=job_id,
            )
            results.append(result)
    return results
```

### Task 5.2: WordPress Integration for Optimization
**File**: `api/services/image_optimizer.py` (addition)

```python
async def optimize_wordpress_image(
    self,
    image_url: str,
    wp_client: WordPressClient,
    job_id: str,
) -> OptimizationResult:
    """
    Full WordPress optimization flow:
    1. Download image
    2. Optimize locally
    3. Upload optimized version
    4. Update WordPress attachment
    5. Update all post references
    """
    # Download
    local_path = await self._download_image(image_url, job_id)

    # Optimize
    result = await self.optimize(local_path, job_id=job_id)

    if result.status == "success":
        # Upload to WordPress
        new_attachment = await wp_client.upload_media(
            result.optimized_url,
            filename=Path(result.optimized_url).name,
        )

        # Update references in posts
        await wp_client.replace_image_references(
            old_url=image_url,
            new_url=new_attachment["source_url"],
        )

        result.optimized_url = new_attachment["source_url"]

    return result
```

---

## PHASE 6: API Endpoints

### Task 5.1: Image Analysis Endpoints
**File**: `api/routers/crawl.py`

```python
@router.get("/{job_id}/images")
async def get_images(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("score", regex="^(score|size|load_time)$"),
    store: JobStore = Depends(get_store),
) -> dict:
    """Get all images for a job with analysis data."""
    images = await store.get_images(job_id, page=page, limit=limit, sort_by=sort_by)
    summary = await store.get_image_summary(job_id)
    return {
        "job_id": job_id,
        "images": [img.to_dict() for img in images],
        "summary": summary,
        "pagination": {"page": page, "limit": limit}
    }


@router.get("/{job_id}/images/summary")
async def get_image_summary(
    job_id: str,
    store: JobStore = Depends(get_store),
) -> dict:
    """Get image health summary for a job."""
    return await store.get_image_summary(job_id)
```

### Task 5.2: Image Summary Schema
```python
{
    "total_images": 150,
    "images_analyzed": 145,
    "image_health_score": 72,
    "by_issue": {
        "IMG_ALT_MISSING": 12,
        "IMG_OVERSIZED": 8,
        "IMG_SLOW_LOAD": 3,
        ...
    },
    "by_format": {
        "jpeg": 80,
        "png": 45,
        "webp": 20,
        "gif": 5
    },
    "total_size_kb": 12500,
    "avg_load_time_ms": 450,
    "avg_score": 72
}
```

---

## PHASE 6: Frontend - Image Analysis Tab

### Task 6.1: Add Image Analysis Tab
**File**: `frontend/src/pages/Results.jsx`

Add new tab constant:
```javascript
const TAB_IMAGES = CATEGORIES.length + 4  // After Fix History
```

Update tabs array:
```javascript
const tabs = ['Summary', ...CATEGORIES.map(c => c.label), 'By Page', 'Fix Manager', 'Fix History', 'Image Analysis']
```

### Task 6.2: Create ImageAnalysisTab Component
**File**: `frontend/src/components/ImageAnalysisTab.jsx` (NEW)

```jsx
export default function ImageAnalysisTab({ jobId }) {
  const [images, setImages] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sortBy, setSortBy] = useState('score')
  const [selectedImage, setSelectedImage] = useState(null)

  // Fetch images and summary
  // Display health score gauge
  // Grid of image cards with thumbnails
  // Click to expand details
  // Filter by issue type
}
```

### Task 6.3: ImageCard Component
**File**: `frontend/src/components/ImageCard.jsx` (NEW)

```jsx
function ImageCard({ image, onClick }) {
  return (
    <div className="bg-white border rounded-xl p-4 hover:shadow-md cursor-pointer">
      {/* Thumbnail */}
      <img
        src={image.url}
        alt=""
        className="w-full h-32 object-cover rounded-lg mb-3"
        loading="lazy"
      />

      {/* Score badge */}
      <div className="flex justify-between items-center mb-2">
        <ScoreBadge score={image.overall_score} />
        <span className="text-xs text-gray-400">{image.format}</span>
      </div>

      {/* Filename */}
      <p className="text-sm font-mono text-gray-600 truncate">{image.filename}</p>

      {/* Quick stats */}
      <div className="flex gap-2 mt-2 text-xs text-gray-500">
        <span>{Math.round(image.file_size_bytes / 1024)}KB</span>
        <span>{image.width}×{image.height}</span>
      </div>

      {/* Issue indicators */}
      {image.issues?.length > 0 && (
        <div className="flex gap-1 mt-2 flex-wrap">
          {image.issues.slice(0, 3).map(issue => (
            <IssuePill key={issue} code={issue} />
          ))}
        </div>
      )}
    </div>
  )
}
```

### Task 6.4: Image Health Score Gauge
**File**: `frontend/src/components/ImageHealthGauge.jsx` (NEW)

Visual gauge showing overall image health score (0-100) with color coding.

### Task 6.5: Image Detail Modal
**File**: `frontend/src/components/ImageDetailModal.jsx` (NEW)

Full details when clicking an image:
- Large preview
- All metadata
- Score breakdown
- List of issues with recommendations
- Fix suggestions

---

## PHASE 7: Frontend Help Content

### Task 7.1: Add Help Content for New Issues
**File**: `frontend/src/data/issueHelp.js`

Add entries for all new issue codes:
- IMG_ALT_TOO_SHORT
- IMG_ALT_TOO_LONG
- IMG_ALT_GENERIC
- IMG_ALT_DUP_FILENAME
- IMG_ALT_MISUSED
- IMG_SLOW_LOAD
- IMG_OVERSCALED
- IMG_POOR_COMPRESSION
- IMG_FORMAT_LEGACY
- IMG_NO_SRCSET
- IMG_DUPLICATE_CONTENT

---

## PHASE 8: Integration & Testing

### Task 8.1: Update Engine Integration
**File**: `api/crawler/engine.py`

- Integrate image analyzer into crawl pipeline
- Store images with job
- Generate image summary

### Task 8.2: Tests
**File**: `tests/test_image_analyzer.py` (NEW)

- Test alt text detection
- Test size/performance checks
- Test format detection
- Test scoring calculations
- Test duplicate detection

### Task 8.3: API Tests
**File**: `tests/test_image_api.py` (NEW)

- Test /images endpoint
- Test /images/summary endpoint

---

## PHASE 9: PDF/Excel Report Integration

### Task 9.1: Add Image Section to PDF
**File**: `api/services/report_generator.py`

Add "Image Analysis" section:
- Image Health Score
- Top issues breakdown
- Worst performing images list

### Task 9.2: Add Image Sheet to Excel
**File**: `api/services/excel_generator.py`

Add "Images" tab with all image data.

---

## FILE CHANGES SUMMARY

### New Files (9)
| File | Purpose |
|------|---------|
| `api/models/image.py` | ImageInfo data model |
| `api/crawler/image_analyzer.py` | Audit module - analysis & scoring |
| `api/services/image_optimizer.py` | Execution module - compression, resizing, WebP |
| `frontend/src/components/ImageAnalysisTab.jsx` | Main tab component |
| `frontend/src/components/ImageCard.jsx` | Image card with thumbnail |
| `frontend/src/components/ImageHealthGauge.jsx` | Score visualization |
| `frontend/src/components/ImageDetailModal.jsx` | Detailed image view + optimize button |
| `tests/test_image_analyzer.py` | Analyzer unit tests |
| `tests/test_image_optimizer.py` | Optimizer unit tests |

### Modified Files (9)
| File | Changes |
|------|---------|
| `api/crawler/parser.py` | Enhanced image extraction (srcset, decorative, surrounding text) |
| `api/crawler/engine.py` | Full GET image fetching + Pillow dimensions |
| `api/crawler/issue_checker.py` | 14 new image issue codes |
| `api/services/job_store.py` | Image storage methods + SQLite table |
| `api/routers/crawl.py` | Image API endpoints |
| `frontend/src/pages/Results.jsx` | Image Analysis tab |
| `frontend/src/data/issueHelp.js` | Help content for new issues |
| `api/services/report_generator.py` | PDF image section |
| `api/services/excel_generator.py` | Excel image sheet |

---

## V2 ROADMAP (Future)

### Browser Rendering (Playwright)
- Actual rendered dimensions
- LCP detection
- Lazy loading verification
- Viewport detection

### Local AI Models
- CLIP for image embeddings
- Sentence transformers for alt embeddings
- Entity extraction (spaCy)

### Additional Checks
- IMG_NOT_INDEXABLE (robots.txt)
- IMG_LCP_TOO_LARGE
- IMG_LCP_NOT_PRELOADED
- IMG_SEMANTIC_DRIFT
- IMG_ALT_CONTEXT_MISMATCH
- IMG_ALT_NO_ENTITIES

---

## IMPLEMENTATION ORDER

### Week 1: Foundation
- Phase 1: Data Model (ImageInfo class, SQLite table)
- Phase 2: Parser Enhancements (srcset, decorative detection, surrounding text)

### Week 2: Analysis Engine
- Phase 3: Image Fetcher (full GET, Pillow dimensions)
- Phase 4: Image Analyzer (all issue checks, scoring)

### Week 3: Optimization Engine
- Phase 5: Image Optimizer (backup, resize, WebP convert, safety checks)
- Phase 6: API Endpoints (images, summary, optimize action)

### Week 4: Frontend
- Phase 7: Image Analysis Tab (thumbnails, cards, health gauge)
- Phase 8: Help Content (all new issue codes)

### Week 5: Integration & Polish
- Phase 9: PDF/Excel Reports
- Phase 10: Testing (analyzer, optimizer, API)
- Integration testing with real WordPress sites

---

## ISSUE CODES SUMMARY (14 Total)

### Accessibility (4)
| Code | Severity | Trigger |
|------|----------|---------|
| `IMG_ALT_MISSING` | critical | null/empty alt on non-decorative |
| `IMG_ALT_QUALITY` | warning | <5 chars, >125 chars, or generic terms |
| `IMG_ALT_DUP_FILENAME` | warning | alt == filename |
| `IMG_ALT_MISUSED` | warning | decorative/meaningful mismatch |

### Performance (5)
| Code | Severity | Trigger |
|------|----------|---------|
| `IMG_OVERSIZED` | warning | >200KB (configurable) |
| `IMG_SLOW_LOAD` | warning | >1000ms load time |
| `IMG_OVERSCALED` | warning | intrinsic/rendered > 2x |
| `IMG_POOR_COMPRESSION` | warning | BPP > 0.5 |
| `IMG_FORMAT_LEGACY` | info | JPEG/PNG/GIF when WebP better |

### Technical (3)
| Code | Severity | Trigger |
|------|----------|---------|
| `IMG_BROKEN` | critical | HTTP 4xx/5xx |
| `IMG_NO_SRCSET` | info | missing responsive images |
| `IMG_DUPLICATE_CONTENT` | info | same image, different alt |

### Semantic/GEO (2) - Phase 4
| Code | Severity | Trigger |
|------|----------|---------|
| `IMG_SEMANTIC_DRIFT` | info | alt doesn't match page topic |
| `IMG_ALT_NO_ENTITIES` | info | no named entities in alt |

---

## OPTIMIZATION SAFETY RULES

| Rule | Description |
|------|-------------|
| **No-Upscale** | Never resize image larger than intrinsic size |
| **Negative Compression** | Discard if WebP larger than original |
| **Minimum Savings** | Skip if savings < 5% |
| **Post-Verification** | Re-check BPP after optimization |
| **Backup First** | Always backup before destructive ops |
| **Atomic Replace** | Verify new file before deleting old |
| **Dual Save** | Save to production AND archive |

---

## SCORING MODEL

```
Image SEO Score (0-100) =
  30% Accessibility (alt presence + quality)
+ 30% Performance (size, BPP, load time)
+ 20% Semantic (topic alignment, entities)
+ 20% Technical (format, srcset, status)
```

### Score Deductions
| Issue | Deduction |
|-------|-----------|
| IMG_ALT_MISSING | -50 accessibility |
| IMG_ALT_QUALITY | -25 accessibility |
| IMG_OVERSIZED | -30 performance |
| IMG_POOR_COMPRESSION | -20 performance |
| IMG_BROKEN | -50 technical |
| IMG_SEMANTIC_DRIFT | -30 semantic |
