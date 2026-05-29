"""Image / asset checks: per-asset file-size limits for PDFs and images.

The per-page image-alt issue and the per-image IMG_* alt-quality checks live
elsewhere — this module handles the standalone check_asset() called by the
engine for non-HTML fetches.

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function body is byte-identical to the original
check_asset().
"""

from api.crawler.fetcher import FetchResult

from api.crawler.checkers.registry import (
    Issue,
    _IMAGE_SIZE_LIMIT_KB,
    _PDF_SIZE_LIMIT,
    make_issue,
)


def check_asset(result: FetchResult, *, img_size_limit_kb: int = _IMAGE_SIZE_LIMIT_KB) -> list[Issue]:
    """Run checks appropriate for a non-HTML asset (PDF, image, etc.).

    HTML-specific checks (title, meta, headings) are intentionally skipped.
    Only checks the file size using the Content-Length response header.

    Args:
        result: The fetch result for the asset.
        img_size_limit_kb: Flag images larger than this many KB as IMG_OVERSIZED.
    """
    issues: list[Issue] = []
    # Defensive: FetchResult.content_type is typed `str` and defaults to
    # "", but the fetcher can still pass None when the server omits the
    # Content-Type header (common for poorly-configured static-asset
    # servers). `"pdf" in None` raises TypeError and crashes the checker.
    # Coalesce to "" so the downstream `in` and .startswith() calls see
    # a string in every case.
    ct = result.content_type or ""
    try:
        size = int(result.headers.get("content-length", 0) or 0)
    except (ValueError, TypeError):
        size = 0

    img_limit_bytes = img_size_limit_kb * 1024

    if "pdf" in ct and size > 0 and size > _PDF_SIZE_LIMIT:
        size_kb = round(size / 1024, 1)
        issue = make_issue("PDF_TOO_LARGE", result.url)
        issue.description = f"PDF file is {size_kb} KB (exceeds 10 MB limit)"
        issue.extra = {"size_kb": size_kb, "limit_kb": _PDF_SIZE_LIMIT // 1024}
        issues.append(issue)
    elif ct.startswith("image/") and size > 0 and size > img_limit_bytes:
        issue = make_issue("IMG_OVERSIZED", result.url)
        # Override description to show the actual threshold used
        size_kb = round(size / 1024, 1)
        issue.description = f"Image file is {size_kb} KB (exceeds {img_size_limit_kb} KB limit)"
        issue.extra = {"size_kb": size_kb, "limit_kb": img_size_limit_kb}
        issues.append(issue)

    return issues
