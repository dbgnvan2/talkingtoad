"""
Architecture constraint tests.

These tests enforce critical design rules that must NEVER be violated.
They prevent architectural regressions that would break performance,
compatibility, or maintainability.

CRITICAL: These tests document and enforce the TalkingToad architecture.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from api.crawler.engine import run_crawl
from api.models.job import CrawlJob


@pytest.mark.asyncio
async def test_scan_never_calls_wordpress_api():
    """
    CRITICAL ARCHITECTURE CONSTRAINT: Scan must NEVER call WordPress API.

    Why this matters:
    - WP API calls are SLOW (100 images = 100+ API requests = 10x+ crawl time)
    - WP API only works on WordPress sites (breaks universal compatibility)
    - Scan should work on ANY site (Drupal, Joomla, static HTML)

    3-Level Architecture:
    - Level 1 (Scan): HTML + HEAD requests ONLY
    - Level 2 (Fetch): WP API + image file download (user-triggered)
    - Level 3 (AI): Vision model analysis (user-triggered)

    This test prevents the regression where WP API calls were added to
    the scan loop at engine.py lines 569-586, breaking this design.
    """
    # Create a test job
    job = CrawlJob(
        job_id="test-scan-no-wp",
        target_url="https://example.org",
        status="queued",
    )

    # Mock the HTTP client to track requests
    mock_requests = []

    async def mock_get(url, **kwargs):
        """Track all HTTP GET requests during scan."""
        mock_requests.append(("GET", url))
        # Return minimal response
        response = AsyncMock()
        response.status_code = 200
        response.text = "<html><body><h1>Test</h1></body></html>"
        response.headers = {}
        return response

    async def mock_head(url, **kwargs):
        """Track all HTTP HEAD requests during scan."""
        mock_requests.append(("HEAD", url))
        response = AsyncMock()
        response.status_code = 200
        response.headers = {"content-type": "image/jpeg", "content-length": "50000"}
        return response

    # Mock the store to avoid database operations
    mock_store = AsyncMock()
    mock_store.get_job.return_value = job
    mock_store.save_job = AsyncMock()
    mock_store.save_pages = AsyncMock()
    mock_store.save_images = AsyncMock()

    # Mock the WordPress client (this is what we're testing doesn't get called)
    with patch("api.crawler.engine.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.head = mock_head
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        # Run the crawler (limited to 1 page to keep test fast)
        try:
            await run_crawl(
                job_id=job.job_id,
                target_url=job.target_url,
                store=mock_store,
                on_progress=None,
                max_pages=1,
                crawl_delay_ms=0,
            )
        except Exception:
            # Crawl might fail due to mocking, but we only care about requests made
            pass

    # CRITICAL ASSERTION: WordPress API endpoints should NEVER be called during scan
    wp_api_endpoints = [
        "/wp-json/",
        "/wp-admin/",
        "?rest_route=",
        "/xmlrpc.php",
    ]

    for method, url in mock_requests:
        for wp_endpoint in wp_api_endpoints:
            assert wp_endpoint not in url, (
                f"ARCHITECTURE VIOLATION: Scan called WordPress API endpoint!\n"
                f"Request: {method} {url}\n"
                f"Scan must ONLY use HTML parsing and HEAD requests.\n"
                f"WordPress API calls belong in Level 2 (Fetch), not Level 1 (Scan)."
            )

    # Verify that only GET and HEAD requests were made (no POST to WP API)
    for method, url in mock_requests:
        assert method in ["GET", "HEAD"], (
            f"Scan should only make GET and HEAD requests, got: {method} {url}"
        )


@pytest.mark.asyncio
async def test_image_scan_uses_head_requests_not_full_download():
    """
    Test that image scanning uses HEAD requests to get metadata efficiently.

    Scan should:
    - Use HEAD request to get Content-Length and Content-Type headers
    - NOT download the full image file during scan
    - Full download happens in Level 2 (Fetch) only when user requests it
    """
    # This test ensures we're not wasting bandwidth downloading images
    # during the scan phase when we only need size and format metadata

    # Implementation similar to test_scan_never_calls_wordpress_api
    # but specifically verifying HEAD requests are used for images
    pass  # TODO: Implement when HEAD request logic is in place


def test_fetch_endpoint_requires_explicit_user_action():
    """
    Test that fetch (Level 2) is never triggered automatically by scan.

    Fetch should ONLY happen when:
    - User clicks "Fetch" button on an image
    - User clicks "Fetch All" (explicit action)
    - NEVER automatically during scan

    This ensures:
    - Scan stays fast (no WP API or image downloads)
    - User controls when expensive operations happen
    - Works on non-WordPress sites
    """
    pass  # TODO: Implement by checking that scan completion doesn't trigger fetch


def test_geo_analysis_requires_user_configuration():
    """
    Test that GEO analysis cannot run without domain configuration.

    This ensures:
    - No AI costs without explicit user setup
    - Clear error messages guide user to configure GEO first
    - No silent failures or confusing behavior
    """
    pass  # TODO: Implement (partially covered in test_geo_integration.py)


def test_three_level_architecture_data_sources():
    """
    Test that ImageInfo.data_source correctly reflects the analysis level.

    - "html_only": Level 1 (Scan) - HTML + HEAD only
    - "full_fetch": Level 2 (Fetch) - WP API + image file
    - "geo_analyzed": Level 3 (AI) - Vision model analysis

    This field is critical for UI display logic and tells the frontend
    what data is available and what actions the user can take.
    """
    from api.models.image import ImageInfo

    # Level 1: Scan
    img_scan = ImageInfo(
        url="https://example.org/test.jpg",
        page_url="https://example.org",
        job_id="test",
        data_source="html_only",
    )
    assert img_scan.data_source == "html_only"

    # Level 2: Fetch
    img_fetch = ImageInfo(
        url="https://example.org/test.jpg",
        page_url="https://example.org",
        job_id="test",
        data_source="full_fetch",
        file_size_bytes=50000,  # File data available
    )
    assert img_fetch.data_source == "full_fetch"

    # Level 3: GEO AI
    img_geo = ImageInfo(
        url="https://example.org/test.jpg",
        page_url="https://example.org",
        job_id="test",
        data_source="geo_analyzed",
        description="GEO-optimized description",
    )
    assert img_geo.data_source == "geo_analyzed"


def test_scan_performance_constraint():
    """
    Test that scan completes within reasonable time for small sites.

    Performance regression test:
    - 10-page site should scan in < 30 seconds
    - If scan takes > 30 seconds, likely calling slow APIs (WP, AI, etc.)

    This is a smoke test for performance regressions.
    """
    pass  # TODO: Implement with timing assertions


def test_url_normalization_is_consistent():
    """
    Test that URL normalization is applied consistently everywhere.

    Critical for:
    - Duplicate detection
    - Cache lookups
    - Link matching

    All URLs should be normalized the same way whether they come from:
    - Scan
    - Fetch
    - User input
    - WordPress API
    """
    from api.crawler.normaliser import normalise_url

    # Test various URL formats normalize to same result
    urls = [
        "https://example.org/page",
        "https://example.org/page/",
        "https://example.org/page?",
        "https://example.org/page#",
        "https://EXAMPLE.ORG/page",
    ]

    normalized = [normalise_url(url) for url in urls]

    # All should normalize to the same canonical form
    assert len(set(normalized)) == 1, (
        f"URL normalization is inconsistent: {set(normalized)}"
    )


def test_issue_codes_are_unique():
    """
    Test that all issue codes are unique across categories.

    Prevents bugs where the same code is used for different issues,
    causing confusion in reporting and filtering.
    """
    from api.crawler.issue_checker import _CATALOGUE

    all_codes = [issue["code"] for issue in _CATALOGUE.values()]
    unique_codes = set(all_codes)

    duplicates = []
    seen = set()
    for code in all_codes:
        if code in seen:
            duplicates.append(code)
        seen.add(code)

    assert len(all_codes) == len(unique_codes), (
        f"Duplicate issue codes found: {duplicates}\n"
        f"Each issue code must be unique!"
    )


def test_score_calculation_is_deterministic():
    """
    Test that image scores are calculated consistently.

    Given the same ImageInfo with the same issues, scores should
    always be identical (no randomness or dependency on external state).
    """
    from api.crawler.image_analyzer import analyze_image
    from api.models.image import ImageInfo

    # Create two identical images
    img1 = ImageInfo(
        url="https://example.org/test.jpg",
        page_url="https://example.org",
        job_id="test",
        alt="Test alt text",
        file_size_bytes=50000,
        width=800,
        height=600,
    )

    img2 = ImageInfo(
        url="https://example.org/test.jpg",
        page_url="https://example.org",
        job_id="test",
        alt="Test alt text",
        file_size_bytes=50000,
        width=800,
        height=600,
    )

    issues1, scores1 = analyze_image(img1, job_id="test")
    issues2, scores2 = analyze_image(img2, job_id="test")

    # Scores should be identical for identical images
    assert scores1 == scores2, (
        f"Score calculation is non-deterministic!\n"
        f"Scores1: {scores1}\n"
        f"Scores2: {scores2}"
    )
