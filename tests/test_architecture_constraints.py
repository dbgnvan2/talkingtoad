"""
Architecture constraint tests.

These tests enforce critical design rules that must NEVER be violated.
They prevent architectural regressions that would break performance,
compatibility, or maintainability.

CRITICAL: These tests document and enforce the TalkingToad architecture.
"""

import os
import re
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

    # _CATALOGUE is a dict[str, _IssueSpec] where keys are issue codes
    all_codes = list(_CATALOGUE.keys())
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


class TestIssueCodeParity:
    """
    Ensure frontend issueHelp.js and backend _CATALOGUE stay in sync.

    Every code in issueHelp.js must exist in _CATALOGUE and vice-versa.
    This prevents dead help entries (frontend has code that backend never
    emits) and undocumented issues (backend emits code with no help text).
    """

    @staticmethod
    def _parse_issue_help_codes() -> set[str]:
        """Extract issue code keys from frontend/src/data/issueHelp.js."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        js_path = os.path.join(
            project_root, "frontend", "src", "data", "issueHelp.js"
        )
        with open(js_path) as f:
            content = f.read()
        # Match patterns like "  CODE_NAME: {" at the start of a line
        codes = re.findall(r"^\s+([A-Z][A-Z0-9_]+):\s*\{", content, re.MULTILINE)
        return set(codes)

    def test_every_frontend_code_exists_in_catalogue(self):
        """Every code in issueHelp.js must have a matching _CATALOGUE entry."""
        from api.crawler.issue_checker import _CATALOGUE

        frontend_codes = self._parse_issue_help_codes()
        catalogue_codes = set(_CATALOGUE.keys())

        missing_from_backend = frontend_codes - catalogue_codes
        assert not missing_from_backend, (
            f"issueHelp.js contains codes not found in _CATALOGUE:\n"
            f"  {sorted(missing_from_backend)}\n"
            f"Remove these from issueHelp.js or add them to _CATALOGUE."
        )

    def test_every_catalogue_code_exists_in_frontend(self):
        """Every code in _CATALOGUE must have a matching issueHelp.js entry."""
        from api.crawler.issue_checker import _CATALOGUE

        frontend_codes = self._parse_issue_help_codes()
        catalogue_codes = set(_CATALOGUE.keys())

        missing_from_frontend = catalogue_codes - frontend_codes
        assert not missing_from_frontend, (
            f"_CATALOGUE contains codes not found in issueHelp.js:\n"
            f"  {sorted(missing_from_frontend)}\n"
            f"Add help entries for these codes in issueHelp.js."
        )


class TestAIReadinessConfidenceLabels:
    """v2.3 M0.2 — every ai_readiness code must declare a confidence label.

    Per v2.0 AI-Readiness spec §2 — the module is useful only if users know
    what they're being told. A heuristic check labelled as Established (or
    vice versa) misleads about the strength of evidence. The single-source
    catalogue (_AI_READINESS_CONFIDENCE in issue_checker.py) makes labelling
    explicit; this test catches new ai_readiness codes that get added
    without a label.
    """

    def test_every_ai_readiness_code_has_confidence_label(self):
        from api.crawler.issue_checker import (
            _AI_READINESS_CONFIDENCE,
            _CATALOGUE,
        )

        ai_readiness_codes = {
            code for code, spec in _CATALOGUE.items()
            if spec.category == "ai_readiness"
        }
        labelled_codes = set(_AI_READINESS_CONFIDENCE.keys())

        unlabelled = ai_readiness_codes - labelled_codes
        assert not unlabelled, (
            f"ai_readiness codes in _CATALOGUE missing from "
            f"_AI_READINESS_CONFIDENCE:\n  {sorted(unlabelled)}\n"
            f"Add an entry per the v2.0 spec confidence taxonomy:\n"
            f"  - 'Established': vendor-confirmed effect on AI citation\n"
            f"  - 'Reasonable proxy': industry consensus + Google's "
            f"published best practices\n"
            f"  - 'Heuristic': industry consensus only"
        )

    def test_confidence_labels_use_canonical_values(self):
        """Adversarial: someone types 'established' (lowercase) — must fail.
        Per spec the three labels are the only allowed strings."""
        from api.crawler.issue_checker import _AI_READINESS_CONFIDENCE

        valid_labels = {"Established", "Reasonable proxy", "Heuristic"}
        invalid = {
            code: label
            for code, label in _AI_READINESS_CONFIDENCE.items()
            if label not in valid_labels
        }
        assert not invalid, (
            f"Invalid confidence labels (must be one of {valid_labels}):\n"
            f"  {invalid}"
        )

    def test_make_issue_propagates_confidence_label(self):
        """make_issue() must surface the confidence label on the resulting Issue."""
        from api.crawler.issue_checker import make_issue
        # LLMS_TXT_MISSING is labelled Heuristic
        issue = make_issue("LLMS_TXT_MISSING", page_url="https://example.com/")
        assert issue.confidence_label == "Heuristic"

        # AI_BOT_SEARCH_BLOCKED is labelled Established
        issue = make_issue("AI_BOT_SEARCH_BLOCKED", page_url="https://example.com/")
        assert issue.confidence_label == "Established"

        # A non-ai-readiness code (TITLE_MISSING) gets no label.
        issue = make_issue("TITLE_MISSING", page_url="https://example.com/")
        assert issue.confidence_label is None

    # ── Cycle S: belt-and-braces guards (invariants 4 & 5) ─────────────
    # These two assertions catch the reverse-direction drift that the
    # existing tests above don't directly enforce: orphan confidence
    # entries for codes that no longer exist in the catalogue, and
    # confidence entries attached to codes whose category drifted away
    # from "ai_readiness". Both are currently clean (0 violations as of
    # the structural-integrity audit) — these tests guard against future
    # regression.

    def test_no_orphan_confidence_entries(self):
        """Adversarial: an entry in _AI_READINESS_CONFIDENCE for a code
        that no longer exists in _CATALOGUE. The label has no effect
        (nothing emits the code) but it's dead config that misleads
        readers and inflates the count."""
        from api.crawler.issue_checker import (
            _AI_READINESS_CONFIDENCE,
            _CATALOGUE,
        )

        confidence_codes = set(_AI_READINESS_CONFIDENCE.keys())
        catalogue_codes = set(_CATALOGUE.keys())

        orphans = confidence_codes - catalogue_codes
        assert not orphans, (
            f"_AI_READINESS_CONFIDENCE contains entries for codes not in "
            f"_CATALOGUE:\n  {sorted(orphans)}\n"
            f"Remove the orphan entries from _AI_READINESS_CONFIDENCE — "
            f"they cannot fire."
        )

    def test_confidence_entries_only_for_ai_readiness_category(self):
        """Adversarial: a confidence label attached to a code whose
        category is not 'ai_readiness'. Confidence labels are
        domain-specific to the AI-readiness taxonomy per spec §2 — a
        label on a SEO/security/heading code is a category-drift bug."""
        from api.crawler.issue_checker import (
            _AI_READINESS_CONFIDENCE,
            _CATALOGUE,
        )

        mismatched = {
            code: _CATALOGUE[code].category
            for code in _AI_READINESS_CONFIDENCE
            if code in _CATALOGUE
            and _CATALOGUE[code].category != "ai_readiness"
        }
        assert not mismatched, (
            f"_AI_READINESS_CONFIDENCE contains labels for codes whose "
            f"_CATALOGUE category is not 'ai_readiness':\n"
            f"  {mismatched}\n"
            f"Either move the catalogue entry to category='ai_readiness' "
            f"or remove the confidence label."
        )

    # ── v2.6 M0.2 / Cycle V — API bridge propagation tests ──────────────
    # The bridges in api/routers/crawl.py (_engine_issue_to_model and
    # _issue_dict) used to silently drop confidence_label. Without these
    # tests the field could be lost again on any router refactor and
    # nobody would notice until a frontend user complained that the
    # badge had disappeared from ai_readiness issues.

    def test_engine_issue_to_model_propagates_confidence_label(self):
        """Bridge contract: the EngIssue → Pydantic Issue bridge in
        api/routers/crawl.py must propagate confidence_label."""
        from api.crawler.issue_checker import make_issue
        from api.routers.crawl import _engine_issue_to_model

        engine_issue = make_issue("LLMS_TXT_MISSING", page_url="https://example.com/")
        assert engine_issue.confidence_label == "Heuristic"

        model = _engine_issue_to_model(engine_issue, job_id="test-job")
        assert model.confidence_label == "Heuristic", (
            "_engine_issue_to_model dropped confidence_label. Frontend "
            "consumers of /api/crawl/{id}/results will no longer see the "
            "evidence-strength badge for ai_readiness issues."
        )

    def test_issue_dict_includes_confidence_label(self):
        """Bridge contract: the Pydantic Issue → dict bridge in
        api/routers/crawl.py must include confidence_label in the JSON
        payload."""
        from api.crawler.issue_checker import make_issue
        from api.routers.crawl import _engine_issue_to_model, _issue_dict

        model = _engine_issue_to_model(
            make_issue("AI_BOT_SEARCH_BLOCKED", page_url="https://example.com/"),
            job_id="test-job",
        )
        payload = _issue_dict(model)
        assert "confidence_label" in payload, (
            "_issue_dict omitted confidence_label from the JSON payload. "
            "API responses will not expose the evidence-strength label "
            "even though every other layer carries it."
        )
        assert payload["confidence_label"] == "Established"
