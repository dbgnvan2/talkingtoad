"""Class-1 foundational invariant tests (v2.3 Cycle C / docs-review §6).

The docs-folder review register identifies a set of upstream layers that
every per-page check depends on. If any breaks, per-check results
silently become unreliable. This file pins the most-critical invariants
so a regression here fails the build loudly.

Invariants covered:

1. **Parser no-mutation invariant** — parse_page() and the individual
   extractor helpers must not mutate the shared BeautifulSoup tree.
   This was the source of docs-review Defect #2 (copy.copy → copy.deepcopy
   fix) and would cause correlated silent failures across link extraction,
   heading extraction, and word count if it regressed.

2. **Catalogue ↔ scoring parity** — every code in _CATALOGUE must have
   a corresponding entry in _ISSUE_SCORING (extends the existing
   catalogue ↔ help parity test).

Other Class-1 invariants from the review are already covered by:

- URL normalisation: `tests/test_normaliser.py`
- Catalogue ↔ help parity:
  `tests/test_architecture_constraints.py::TestIssueCodeParity`
- AI-readiness confidence labels:
  `tests/test_architecture_constraints.py::TestAIReadinessConfidenceLabels`
- Job-store interface parity: `tests/test_job_store.py` +
  `tests/test_redis_job_store.py` (Redis store has 84 dedicated tests)
- Health-score determinism: `tests/test_job_store.py` exercises
  get_summary; trailing-slash matching is implicit in the existing
  test fixtures
- Text-extraction scope agreement: now moot — extraction is consolidated
  in parser._extract_first_n_words and GEO checks read pre-populated
  ParsedPage fields rather than re-extracting (Path B / Path C from the
  original review register no longer exist).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixture HTML — exercises every extractor:
# title, meta, OG, canonical, H1, headings_outline, links (internal +
# external), schema JSON-LD, viewport, lang, words, images, anchors, etc.
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Test Page Title</title>
  <meta name="description" content="A test page used by class-1 invariant tests.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta property="og:title" content="OG Test Title">
  <meta property="og:description" content="OG description text">
  <meta property="og:image" content="https://example.com/og.png">
  <meta name="twitter:card" content="summary">
  <link rel="canonical" href="https://example.com/test/">
  <link rel="icon" href="/favicon.ico">
  <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "Article", "headline": "Test"}
  </script>
</head>
<body>
  <nav>
    <a href="/nav-link">Nav</a>
  </nav>
  <header>Header content</header>

  <main>
    <h1>Main Heading</h1>
    <h2>Second-Level Heading</h2>
    <p>This is the first paragraph of body content. It contains enough
    words to populate the first_200_words and first_600_words buffers
    in the ParsedPage model. The text intentionally includes a numeric
    statistic, like 42 visitors per month, to satisfy the
    STATISTICS check.</p>

    <p>This paragraph has an internal link: <a href="/about">About Us</a>
    and an external link: <a href="https://external.example.org/page">
    External</a>.</p>

    <h3>Third heading</h3>
    <p>An <img src="/missing-alt.jpg"> image without alt text.</p>
    <p>An anchor without text: <a href="/empty"></a></p>
    <ul>
      <li>List item one</li>
      <li>List item two</li>
    </ul>
  </main>

  <footer>
    <a href="/footer-link">Footer link</a>
  </footer>
</body>
</html>
"""


@pytest.fixture
def fixture_html() -> str:
    return _FIXTURE_HTML


# ---------------------------------------------------------------------------
# Invariant 1 — parser no-mutation
# ---------------------------------------------------------------------------


class TestParserNoMutation:
    """parse_page() must not mutate the shared soup; double-invocation on
    the same HTML must produce identical ParsedPage instances.

    Adversarial: docs-review Defect #2 was exactly this — copy.copy
    (shallow) in _count_words caused .decompose() to corrupt the
    original tree, silently wrong-ing link/heading/word-count for
    every per-page check that ran afterwards. copy.deepcopy fixed it.
    This test would catch the regression.
    """

    def test_double_parse_produces_identical_result(self, fixture_html):
        """Parsing the same HTML twice must yield identical extractions."""
        from api.crawler.fetcher import FetchResult
        from api.crawler.parser import parse_page

        result = FetchResult(
            url="https://example.com/test/",
            final_url="https://example.com/test/",
            status_code=200,
            html=fixture_html,
            headers={"content-type": "text/html"},
        )

        parsed1 = parse_page(result, "https://example.com")
        parsed2 = parse_page(result, "https://example.com")

        # Compare every extracted field. If any extractor mutates the soup,
        # at least one of these would differ between the two calls.
        assert parsed1.title == parsed2.title
        assert parsed1.meta_description == parsed2.meta_description
        assert parsed1.og_title == parsed2.og_title
        assert parsed1.og_description == parsed2.og_description
        assert parsed1.canonical_url == parsed2.canonical_url
        assert parsed1.h1_tags == parsed2.h1_tags
        assert parsed1.headings_outline == parsed2.headings_outline
        assert parsed1.has_viewport_meta == parsed2.has_viewport_meta
        assert parsed1.has_favicon == parsed2.has_favicon
        assert parsed1.schema_types == parsed2.schema_types
        assert parsed1.word_count == parsed2.word_count
        assert parsed1.first_200_words == parsed2.first_200_words
        assert parsed1.first_600_words == parsed2.first_600_words
        assert parsed1.image_urls == parsed2.image_urls
        # Links: compare sets of href to avoid ordering noise
        urls1 = {link.url for link in parsed1.links}
        urls2 = {link.url for link in parsed2.links}
        assert urls1 == urls2

    def test_link_extraction_survives_word_count(self, fixture_html):
        """Adversarial: word-count was the original mutator. Specifically
        check that links AND headings survive a parse — these were the
        casualties of the shallow-copy bug."""
        from api.crawler.fetcher import FetchResult
        from api.crawler.parser import parse_page

        result = FetchResult(
            url="https://example.com/test/",
            final_url="https://example.com/test/",
            status_code=200,
            html=fixture_html,
            headers={"content-type": "text/html"},
        )
        parsed = parse_page(result, "https://example.com")

        # Word count populated (means _count_words ran)
        assert parsed.word_count is not None and parsed.word_count > 0

        # Links survived
        link_urls = {link.url for link in parsed.links}
        assert "/about" in link_urls or "https://example.com/about" in link_urls
        assert any("external.example.org" in u for u in link_urls)

        # Headings survived
        assert "Main Heading" in (parsed.h1_tags or [])
        # At least one second-level heading present
        h2_texts = [h["text"] for h in parsed.headings_outline if h.get("level") == 2]
        assert any("Second-Level" in t for t in h2_texts)

    def test_word_count_buffers_consistent_across_calls(self, fixture_html):
        """The first_200_words and first_600_words buffers must be stable
        across re-parses (no mutation between extractions)."""
        from api.crawler.fetcher import FetchResult
        from api.crawler.parser import parse_page

        result = FetchResult(
            url="https://example.com/test/",
            final_url="https://example.com/test/",
            status_code=200,
            html=fixture_html,
            headers={"content-type": "text/html"},
        )

        parses = [parse_page(result, "https://example.com") for _ in range(3)]
        first_200s = {p.first_200_words for p in parses}
        first_600s = {p.first_600_words for p in parses}
        word_counts = {p.word_count for p in parses}

        assert len(first_200s) == 1, "first_200_words drifted across parses"
        assert len(first_600s) == 1, "first_600_words drifted across parses"
        assert len(word_counts) == 1, "word_count drifted across parses"


# ---------------------------------------------------------------------------
# Invariant 2 — catalogue ↔ scoring parity
# ---------------------------------------------------------------------------


class TestCatalogueScoringParity:
    """Every code in _CATALOGUE must have a corresponding entry in
    _ISSUE_SCORING.

    Adversarial: make_issue() falls back to (0, 0) for impact/effort when
    a code is missing from _ISSUE_SCORING. That silently sets priority_rank
    to 0 — causing the issue to appear at the bottom of any priority-sorted
    view and to contribute 0 to the health score. Without this test, a new
    code added to _CATALOGUE could ship with 0/0 scoring nobody noticed.
    """

    def test_every_catalogue_code_has_scoring(self):
        from api.crawler.issue_checker import _CATALOGUE, _ISSUE_SCORING

        catalogue_codes = set(_CATALOGUE.keys())
        scored_codes = set(_ISSUE_SCORING.keys())

        unscored = catalogue_codes - scored_codes
        assert not unscored, (
            f"_CATALOGUE codes missing from _ISSUE_SCORING:\n"
            f"  {sorted(unscored)}\n"
            f"Add (impact, effort) entries in api/crawler/issue_checker.py "
            f"under _ISSUE_SCORING. Default 0/0 fallback silently buries these "
            f"issues in priority rankings and excludes them from health-score "
            f"calculations."
        )

    def test_no_orphan_scoring_entries(self):
        """Adversarial: an entry in _ISSUE_SCORING for a code that no
        longer exists in _CATALOGUE. The score has no effect (nothing
        emits the code) but it's dead code that misleads readers."""
        from api.crawler.issue_checker import _CATALOGUE, _ISSUE_SCORING

        catalogue_codes = set(_CATALOGUE.keys())
        scored_codes = set(_ISSUE_SCORING.keys())

        orphans = scored_codes - catalogue_codes
        assert not orphans, (
            f"_ISSUE_SCORING contains entries for codes not in _CATALOGUE:\n"
            f"  {sorted(orphans)}\n"
            f"Remove the orphan entries from _ISSUE_SCORING — they cannot fire."
        )

    def test_scoring_values_are_in_valid_ranges(self):
        """impact must be 0–10, effort must be 0–5 (per CLAUDE.md scoring spec)."""
        from api.crawler.issue_checker import _ISSUE_SCORING

        invalid = {}
        for code, (impact, effort) in _ISSUE_SCORING.items():
            if not (0 <= impact <= 10):
                invalid[code] = f"impact={impact} (must be 0-10)"
            elif not (0 <= effort <= 5):
                invalid[code] = f"effort={effort} (must be 0-5)"

        assert not invalid, (
            f"Invalid scoring values:\n"
            + "\n".join(f"  {c}: {msg}" for c, msg in invalid.items())
        )
