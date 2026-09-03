"""R5.1 — site-scope (external spec §6.3).

TLS/host-config findings are properties of the whole site, not of one page.
A site-scoped code deducts ONCE site-wide (at the worst-affected representative
page), never from other pages — including its page-fatal flooring.

Spec: docs/pending/2026-07-06_scoring-change-remainder.md §R5.1
"""

from __future__ import annotations

from api.crawler.checkers.registry import (
    _CATALOGUE,
    _ISSUE_SCORING,
    _SITE_SCOPED_CODES,
    issue_scope,
)
from api.models.job import CrawlJob
from api.services.job_store_base import compute_impact_health

_NO_SEV = {"critical": 0, "warning": 0, "info": 0}

_SITE_CODES = ["HTTP_PAGE", "HTTPS_REDIRECT_MISSING", "MIXED_CONTENT",
               "MISSING_HSTS", "WWW_CANONICALIZATION",
               # "Search Everywhere" GEO (P1) — site-level findings.
               "ENTITY_NAME_INCONSISTENT", "AUTHOR_IDENTITY_INCONSISTENT",
               "NEAR_DUPLICATE_BODY",
               # Analytics & Measurement (2026-08-06 spec) — site-wide tagging property
               "ANALYTICS_ID_INCONSISTENT",
               # E5 (2026-08-29) — entity VALUE checks are settings facts, not
               # page facts: charging them per page would multiply one
               # misconfiguration across the whole crawl.
               "ENTITY_HOURS_DEFAULT", "ENTITY_NAP_INCOMPLETE",
               "ENTITY_FIELD_EMPTY", "ENTITY_VALUE_PLACEHOLDER"]


def _imp(code: str) -> int:
    return _ISSUE_SCORING[code][0]


def _row(code: str) -> tuple[str, int, str]:
    return (code, _imp(code), _CATALOGUE[code].category)


def test_site_codes_declared_site_scope():
    """R5.1.1 — the five TLS/site-config codes are declared scope='site'."""
    for code in _SITE_CODES:
        assert _CATALOGUE[code].scope == "site", code
        assert issue_scope(code) == "site", code
    # And nothing else silently became site-scoped.
    site_scoped = {c for c, s in _CATALOGUE.items() if s.scope == "site"}
    assert site_scoped == set(_SITE_CODES)
    assert site_scoped == set(_SITE_SCOPED_CODES)


def test_page_codes_default_page_scope():
    for code in ("TITLE_MISSING", "H1_MISSING", "NOINDEX_META"):
        assert issue_scope(code) == "page"


def test_site_scope_single_deduction():
    """R5.1.2 / spec §10(e) — a 50-page all-HTTP site deducts HTTP_PAGE exactly
    ONCE site-wide. The representative page is floored; the other 49 are not."""
    pages = [f"https://x/p{i}" for i in range(50)]
    per_page = {p: [_row("HTTP_PAGE")] for p in pages}

    site, n = compute_impact_health(pages, per_page, dict(_NO_SEV))
    assert n == 50

    # Exactly ONE page carries the HTTP_PAGE deduction; the other 49 score 100.
    # HTTP_PAGE is page-fatal, impact 6 → representative page scores 100-6=94.
    rep_score = 100 - _imp("HTTP_PAGE")
    expected = round((rep_score + 100 * 49) / 50)
    assert site == expected

    # Sanity: if HTTP_PAGE were charged per page (the old bug), every page would
    # lose points and the site score would be far lower.
    per_page_score_if_all_charged = round(100 - _imp("HTTP_PAGE"))
    assert site > per_page_score_if_all_charged


def test_site_scope_representative_is_worst_affected():
    """The single deduction lands on the page with the highest impact for that
    code (worst-affected), not an arbitrary page."""
    pages = ["https://x/a", "https://x/b", "https://x/c"]
    # Same code, different impacts per page; 'b' is worst.
    per_page = {
        "https://x/a": [("HTTP_PAGE", 3, "security")],
        "https://x/b": [("HTTP_PAGE", 9, "security")],
        "https://x/c": [("HTTP_PAGE", 3, "security")],
    }
    site, _ = compute_impact_health(pages, per_page, dict(_NO_SEV))
    # Only 'b' is charged, at impact 9 (fatal → floors by 9); a and c score 100.
    expected = round(((100 - 9) + 100 + 100) / 3)
    assert site == expected


def test_page_issues_include_scope():
    """R5.1.3 / API-contract — the per-page issues JSON payload exposes `scope`
    so the frontend can label site-wide findings. A site-scoped code serialises
    as "site"; a normal code as "page"."""
    from api.crawler.issue_checker import make_issue
    from api.routers.crawl import _engine_issue_to_model, _issue_dict

    site_model = _engine_issue_to_model(
        make_issue("HTTP_PAGE", page_url="https://example.com/"), job_id="j"
    )
    page_model = _engine_issue_to_model(
        make_issue("H1_MISSING", page_url="https://example.com/"), job_id="j"
    )
    site_payload = _issue_dict(site_model)
    page_payload = _issue_dict(page_model)

    assert "scope" in site_payload, "_issue_dict omitted scope from the payload"
    assert site_payload["scope"] == "site"
    assert page_payload["scope"] == "page"


def test_site_scope_other_pages_not_floored():
    """A site-scoped fatal code floors ONLY its representative page. Other pages
    with the same code but real page-scoped issues keep their own scores."""
    pages = ["https://x/rep", "https://x/other"]
    per_page = {
        "https://x/rep": [_row("HTTP_PAGE")],
        # 'other' also detects HTTP_PAGE (still visible in list) plus a real
        # page-scoped issue. HTTP_PAGE must NOT floor 'other'.
        "https://x/other": [_row("HTTP_PAGE"), _row("H1_MISSING")],
    }
    site, _ = compute_impact_health(pages, per_page, dict(_NO_SEV))
    # rep charged HTTP_PAGE (fatal, 6). 'other' charged only H1_MISSING.
    rep = 100 - _imp("HTTP_PAGE")
    other = 100 - _imp("H1_MISSING")
    assert site == round((rep + other) / 2)


def test_near_duplicate_cluster_is_charged_once_however_many_members():
    """ND1 (2026-09-02) — the finding is now emitted on EVERY member of a
    near-duplicate cluster so each page's audit names its partners. That
    multiplies the stored ROWS, and the danger is that it multiplies the
    DEDUCTION too: a 5-page cluster would cost five times what the same
    duplication cost yesterday. `NEAR_DUPLICATE_BODY` is site-scoped, so R5.1's
    representative election must still charge it exactly once.

    Spec: docs/functional-specification.md §4.10 (ND1)
    """
    cluster = [f"https://x/dup{i}" for i in range(5)]
    clean = [f"https://x/ok{i}" for i in range(5)]
    pages = cluster + clean

    # Before ND1: the row existed on the sorted-first member only.
    one_row = {p: ([_row("NEAR_DUPLICATE_BODY")] if p == cluster[0] else []) for p in pages}
    # After ND1: every member carries it.
    every_member = {p: ([_row("NEAR_DUPLICATE_BODY")] if p in cluster else []) for p in pages}

    before, _ = compute_impact_health(pages, one_row, dict(_NO_SEV))
    after, _ = compute_impact_health(pages, every_member, dict(_NO_SEV))

    assert after == before, (
        "emitting the finding on every member changed the health score — "
        "the site-scoped single deduction is not holding")

    # And pin the value, so a scoring change cannot drift both sides together
    # (P32: an oracle computed from the code under test proves nothing).
    rep_score = 100 - _imp("NEAR_DUPLICATE_BODY")
    assert after == round((rep_score + 100 * 9) / 10)


def test_site_scope_representative_does_not_move_when_more_pages_carry_the_code():
    """Cold-sweep finding (2026-09-02): the R5.1 election broke impact ties by
    the ORDER OF `page_norm_urls` — which is `SELECT url FROM crawled_pages`
    with no ORDER BY, i.e. crawl order — and only a STRICTLY higher impact
    displaced the incumbent. So the elected page depended on how many pages
    carried the code.

    ND1 changed exactly that: `NEAR_DUPLICATE_BODY` went from one row (on the
    alphabetically-first member) to a row on every member, moving the
    representative to the first-CRAWLED member. Where that page is already at
    its category cap the 4-point deduction is absorbed and **the site health
    score RISES with nothing changed on the site** — the failure LEARNINGS
    records against suppressing ORPHAN_PAGE, arriving from the other direction.

    The election must therefore be a function of the affected pages, not of the
    row count or the crawl order.
    """
    loaded = [_row("AI_BOT_SEARCH_BLOCKED"), _row("RAW_HTML_JS_DEPENDENT"),
              _row("SCHEMA_VISIBLE_MISMATCH")]   # 24 ai_readiness — over the cap
    # /zeta is crawled first; /alpha is the alphabetically-first cluster member.
    pages = ["https://x/zeta", "https://x/alpha", "https://x/p1", "https://x/p2"]

    one_row = {"https://x/zeta": list(loaded),
               "https://x/alpha": [_row("NEAR_DUPLICATE_BODY")],
               "https://x/p1": [], "https://x/p2": []}
    every_member = {"https://x/zeta": loaded + [_row("NEAR_DUPLICATE_BODY")],
                    "https://x/alpha": [_row("NEAR_DUPLICATE_BODY")],
                    "https://x/p1": [], "https://x/p2": []}

    before, _ = compute_impact_health(pages, one_row, dict(_NO_SEV))
    after, _ = compute_impact_health(pages, every_member, dict(_NO_SEV))
    assert after == before, (
        f"the site score moved {before} -> {after} because the cluster's row now "
        "appears on a page that absorbs the deduction at its category cap")

    # Pin the absolute value too, so a scoring change cannot drift both sides
    # together and leave the equality vacuously true (P32). /zeta is capped at
    # _CATEGORY_IMPACT_CAP (20) by its three loaded codes -> 80; /alpha is the
    # elected representative and pays NEAR_DUPLICATE_BODY -> 96; p1/p2 -> 100.
    assert after == round((80 + (100 - _imp("NEAR_DUPLICATE_BODY")) + 100 + 100) / 4)


def test_site_scope_representative_is_stable_against_crawl_order():
    """The docstring promises a choice "stable across runs". `crawled_pages` has
    no ORDER BY, so two crawls of the same site that visit pages in a different
    order must still score the same."""
    loaded = [_row("AI_BOT_SEARCH_BLOCKED"), _row("RAW_HTML_JS_DEPENDENT"),
              _row("SCHEMA_VISIBLE_MISMATCH")]
    per_page = {"https://x/zeta": loaded + [_row("NEAR_DUPLICATE_BODY")],
                "https://x/alpha": [_row("NEAR_DUPLICATE_BODY")],
                "https://x/p1": [], "https://x/p2": []}

    order_a = ["https://x/zeta", "https://x/alpha", "https://x/p1", "https://x/p2"]
    order_b = ["https://x/p2", "https://x/alpha", "https://x/p1", "https://x/zeta"]

    a, _ = compute_impact_health(order_a, per_page, dict(_NO_SEV))
    b, _ = compute_impact_health(order_b, per_page, dict(_NO_SEV))
    assert a == b, f"the same site scored {a} and {b} depending on crawl order"


def test_every_cluster_member_now_scores_as_having_the_problem_on_its_own_page():
    """The declared per-page consequence of ND1, pinned so it is a decision and
    not a surprise.

    `compute_page_health` scores ONE page from its own rows and knows nothing
    about site scope — it cannot, having no job context. So the extra rows do
    lower the individual health of the other cluster members, and that feeds the
    Page Priority queue, the striking-distance list and the citability grade.
    That is the intended reading of ND1: five of six near-identical pages used
    to be invisible, and a page that is one of six doorway pages genuinely has a
    content problem worth ranking. What must NOT move is the site score, which
    R5.1 governs — asserted above.
    """
    from api.services.job_store_base import compute_page_health

    member_rows = [_row("NEAR_DUPLICATE_BODY")]
    assert compute_page_health(member_rows) == 100 - _imp("NEAR_DUPLICATE_BODY")
    assert compute_page_health([]) == 100, "a page outside the cluster is untouched"


class TestComparabilityAcrossAnEmissionChange:
    """D5 (2026-09-03) — two scans either side of a change in what the crawler
    EMITS differ in row count for reasons that are not the site.

    ND1 started emitting one `NEAR_DUPLICATE_BODY` row per cluster member; BB3
    reclassified external 503s out of `broken_link`. `comparable` knew only about
    `info_detail` and partial analysis, so a before/after delta read as a change
    in the site. `scoring_model_version` exists for exactly this shape and was
    not extended when emission changed.
    """

    def test_the_emission_version_is_stamped_on_a_new_job(self):
        from api.crawler.checkers.registry import ISSUE_EMISSION_VERSION
        from api.models.job import CrawlJob

        job = CrawlJob(job_id="j", target_url="https://x/")
        assert job.issue_emission_version == ISSUE_EMISSION_VERSION
        assert ISSUE_EMISSION_VERSION, "the stamp must not be empty"

    async def test_the_stamp_survives_a_store_round_trip(self, tmp_path):
        """The one that matters. The column was added, the model field was
        added, the write was added — and `_row_to_job` was not, so every job
        read back carried the model DEFAULT, i.e. the current stamp. The guard
        could never fire, on any pair, ever. Four unit tests of the comparison
        helper all passed against a feature that did nothing (P10/P26 — the
        template for this existed in test_scoring_version.py and was not used).
        """
        from api.services.sqlite_store import SQLiteJobStore

        store = SQLiteJobStore(str(tmp_path / "t.db"))
        await store.init()
        job = CrawlJob(job_id="j", target_url="https://x/")
        job.issue_emission_version = "2026-01-01-e0"
        await store.create_job(job)
        back = await store.get_job("j")
        await store.close()
        assert back.issue_emission_version == "2026-01-01-e0", (
            f"the stamp did not survive the round trip: {back.issue_emission_version}")

    async def test_a_legacy_job_reads_back_as_unstamped_not_as_current(self, tmp_path):
        """Adversarial partner: a row written before the column existed must read
        back as None. Defaulting it to the current stamp is what made the guard
        inert, and it is the same P12 the helper's docstring warns about."""
        import sqlite3

        from api.services.sqlite_store import SQLiteJobStore

        db = tmp_path / "t.db"
        store = SQLiteJobStore(str(db))
        await store.init()
        await store.create_job(CrawlJob(job_id="old", target_url="https://x/"))
        await store.close()
        con = sqlite3.connect(db)
        con.execute("UPDATE crawl_jobs SET issue_emission_version = NULL")
        con.commit(); con.close()

        store = SQLiteJobStore(str(db))
        await store.init()
        back = await store.get_job("old")
        await store.close()
        assert back.issue_emission_version is None, (
            "a pre-stamp job claims the current emission version")

    def test_two_unstamped_jobs_are_not_comparable(self):
        """The pair that separates the real implementation from a naive
        `current == previous`: two legacy jobs, which is every job in the store
        today. The cold sweep proved the naive version passes all the other
        cases (P27)."""
        from api.routers.crawl import _emission_comparability

        ok, reason = _emission_comparability(None, None)
        assert ok is False, "two unstamped jobs were declared comparable"
        assert reason

    def test_two_jobs_with_different_stamps_are_not_comparable(self):
        from api.routers.crawl import _emission_comparability

        ok, reason = _emission_comparability("2026-09-03-e1", "2026-08-01-e0")
        assert ok is False
        assert "emission" in (reason or "").lower(), reason

    def test_equal_stamps_stay_comparable(self):
        from api.routers.crawl import _emission_comparability

        ok, reason = _emission_comparability("2026-09-03-e1", "2026-09-03-e1")
        assert ok is True and reason is None

    def test_a_missing_stamp_is_not_treated_as_equal(self):
        """Adversarial: every job crawled before today has NULL here. Reading
        that as "same as mine" is how a silent false comparison happens (P12 —
        a default reaching a surface and reading as a real measurement)."""
        from api.routers.crawl import _emission_comparability

        ok, reason = _emission_comparability("2026-09-03-e1", None)
        assert ok is False, "an unstamped job was declared comparable"
        assert reason
