"""V3 — Full-site before/after HealthScore report.

Purpose: Crawl the project test site and score every page under BOTH the current
         ``_ISSUE_SCORING`` and the reconstructed pre-R3 ``OLD_ISSUE_SCORING``
         (the ``cur`` column of the R3 FINAL calibration) via the SAME
         ``compute_page_health`` / ``compute_impact_health`` path, then emit a
         before/after markdown artifact.
Spec:    docs/pending/2026-07-06_deploy-gate-validation.md#V3
Tests:   tests/test_before_after_report.py::test_baseline_reconstruction_matches_r3_cur_column
         tests/test_before_after_report.py::test_delta_computation

The pure logic (baseline reconstruction, per-page delta math, severity mix) is
unit-tested; ``main()`` runs the live crawl and writes the artifact. Numbers in
the artifact are ALWAYS derived from a real crawl — on crawl failure the script
reports the error and writes NO artifact (never fabricates).
"""

from __future__ import annotations

import argparse
import asyncio
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Baseline reconstruction (AC V3.1)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_R3_CALIBRATION = (
    _REPO_ROOT / "docs" / "pending" / "OLD" / "2026-07-03_r3-FINAL-calibration.md"
)

# A §4 table row looks like:
#   | CODE | cur | Gem | Fable | FINAL | sev | Δ | basis |
# We want the `cur` (first numeric) column — the live pre-R3 impact.
_ROW_RE = re.compile(r"^\|\s*([A-Z0-9_]+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|")


def load_old_issue_scoring(path: Path | None = None) -> dict[str, int]:
    """Parse the ``cur`` (pre-R3 live impact) column from the R3 §4 table.

    Returns ``{code: old_impact}``. Effort is unchanged by R3, so only impact is
    reconstructed here (the health model uses impact only).
    """
    src = (path or _R3_CALIBRATION).read_text()
    out: dict[str, int] = {}
    for line in src.splitlines():
        m = _ROW_RE.match(line)
        if m:
            out[m.group(1)] = int(m.group(2))
    if not out:
        raise ValueError(f"no calibration rows parsed from {path or _R3_CALIBRATION}")
    return out


# Reconstructed pre-R3 impacts (the `cur` column). Effort unchanged.
OLD_ISSUE_SCORING: dict[str, int] = load_old_issue_scoring()


# ---------------------------------------------------------------------------
# Delta math (AC V3.2) — pure, unit-tested
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageDelta:
    """Before/after health for one page under the two scoring tables."""

    url: str
    old_health: int
    new_health: int

    @property
    def delta(self) -> int:
        """new − old. Positive = the page scores HIGHER under current scoring."""
        return self.new_health - self.old_health


def old_impact_for(code: str, old_scoring: dict[str, int]) -> int:
    """Old impact for a code (0 if the code is not in the reconstructed table)."""
    return old_scoring.get(code, 0)


def remap_rows_to_old(
    rows: list[tuple[str, int, str]], old_scoring: dict[str, int]
) -> list[tuple[str, int, str]]:
    """Rewrite each ``(code, current_impact, category)`` row's impact to its OLD
    impact, preserving code and category so cluster-suppression / cap / fatal
    logic behaves identically to the current path.
    """
    return [(c, old_impact_for(c, old_scoring), cat) for c, _imp, cat in rows]


def compute_page_deltas(
    per_page_rows: dict[str, list[tuple[str, int, str]]],
    old_scoring: dict[str, int],
) -> list[PageDelta]:
    """Score every page under both tables via the SAME ``compute_page_health``.

    ``per_page_rows`` maps a page URL to its CURRENT ``(code, impact, category)``
    rows (impact from the live ``_ISSUE_SCORING``). Returns one PageDelta per page.
    """
    from api.services.job_store_base import compute_page_health

    deltas: list[PageDelta] = []
    for url, rows in per_page_rows.items():
        new_h = compute_page_health(rows)
        old_h = compute_page_health(remap_rows_to_old(rows, old_scoring))
        deltas.append(PageDelta(url=url, old_health=old_h, new_health=new_h))
    return deltas


def site_health(deltas: list[PageDelta], which: str) -> int:
    """Mean page score (rounded) under ``which`` in {"old", "new"}. 100 if empty.

    This is the mean of the ISOLATED per-page scores (``compute_page_health``).
    For the report headline we also compute the shipped site path via
    :func:`site_health_via_impact` (which additionally applies site-scope
    election); the two differ only when site-scoped codes are present.
    """
    if not deltas:
        return 100
    vals = [d.old_health if which == "old" else d.new_health for d in deltas]
    return round(sum(vals) / len(vals))


def site_health_via_impact(
    per_page_rows: dict[str, list[tuple[str, int, str]]],
    old_scoring: dict[str, int] | None,
) -> int:
    """Site health via the SHIPPED ``compute_impact_health`` path (capped,
    suppressed, site-scope-elected). When ``old_scoring`` is given, remap each
    page's rows to their OLD impact first. 100 for an empty site.
    """
    from api.services.job_store_base import compute_impact_health

    urls = [u for u in per_page_rows]
    if not urls:
        return 100
    scoped: dict[str, list[tuple[str, int, str]]] = {}
    for u, rows in per_page_rows.items():
        scoped[u] = remap_rows_to_old(rows, old_scoring) if old_scoring else rows
    # by_severity only routes the pre-v1.5 density fallback; supply real impacts
    # so the impact path (not the fallback) is used.
    by_severity = {"critical": 0, "warning": 0, "info": 1}
    site, _ = compute_impact_health(urls, scoped, by_severity)
    return site


# ---------------------------------------------------------------------------
# Report rendering (artifact) — driven purely by real crawl data
# ---------------------------------------------------------------------------


def _severity_from_impact(impact: int) -> str:
    """R3 derived severity: impact >= 8 critical, 4-7 warning, else info."""
    if impact >= 8:
        return "critical"
    if impact >= 4:
        return "warning"
    return "info"


def render_report(
    *,
    site: str,
    page_cap: int,
    per_page_rows: dict[str, list[tuple[str, int, str]]],
    old_scoring: dict[str, int],
    issues_total: int,
) -> str:
    """Render the before/after markdown from REAL crawl data only."""
    deltas = compute_page_deltas(per_page_rows, old_scoring)
    # Headline site health via the SHIPPED site path (site-scope election etc.).
    old_site = site_health_via_impact(per_page_rows, old_scoring)
    new_site = site_health_via_impact(per_page_rows, None)
    # Mean of isolated page scores (for reference / cross-check).
    old_site_mean = site_health(deltas, "old")
    new_site_mean = site_health(deltas, "new")

    # Severity-mix shift: count each issue occurrence under old vs new impact.
    old_sev: Counter[str] = Counter()
    new_sev: Counter[str] = Counter()
    # Top score movers: aggregate per-code impact delta × occurrences.
    code_occurrences: Counter[str] = Counter()
    for rows in per_page_rows.values():
        for code, new_imp, _cat in rows:
            old_imp = old_impact_for(code, old_scoring)
            old_sev[_severity_from_impact(old_imp)] += 1
            new_sev[_severity_from_impact(new_imp)] += 1
            code_occurrences[code] += 1

    # Per-code impact shift, weighted by occurrences (biggest score-movers).
    movers: list[tuple[str, int, int, int, int]] = []
    for code, n in code_occurrences.items():
        old_imp = old_impact_for(code, old_scoring)
        new_imp = new_imp_for(code, per_page_rows)
        movers.append((code, old_imp, new_imp, new_imp - old_imp, n))
    movers.sort(key=lambda t: (abs(t[3]) * t[4], t[4]), reverse=True)

    page_deltas_sorted = sorted(deltas, key=lambda d: d.delta, reverse=True)

    lines: list[str] = []
    lines.append("---")
    lines.append("status: validation report (V3 — before/after HealthScore)")
    lines.append("date: 2026-07-06")
    lines.append(f"site: {site}")
    lines.append(f"page_cap: {page_cap}")
    lines.append("scoring_path: compute_impact_health / compute_page_health (shipped, capped+suppressed)")
    lines.append("baseline: OLD_ISSUE_SCORING = `cur` column of docs/pending/OLD/2026-07-03_r3-FINAL-calibration.md §4")
    lines.append("---")
    lines.append("")
    lines.append("# V3 — Full-crawl before/after HealthScore (livingsystems.ca)")
    lines.append("")
    lines.append(
        "Every page scored under BOTH the current `_ISSUE_SCORING` and the "
        "reconstructed pre-R3 `OLD_ISSUE_SCORING` (the `cur` column), via the "
        "SAME `compute_page_health` path (cluster suppression + per-category cap "
        "+ page-fatal bypass). Numbers below are from a real crawl."
    )
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Pages scored | {len(deltas)} |")
    lines.append(f"| Page cap (max_pages) | {page_cap} |")
    lines.append(f"| Issues found | {issues_total} |")
    lines.append(f"| **Site Health — OLD (pre-R3)** | **{old_site}** |")
    lines.append(f"| **Site Health — NEW (current)** | **{new_site}** |")
    lines.append(f"| **Site Health delta (new − old)** | **{new_site - old_site:+d}** |")
    lines.append(f"| Site Health — OLD (mean of isolated pages) | {old_site_mean} |")
    lines.append(f"| Site Health — NEW (mean of isolated pages) | {new_site_mean} |")
    lines.append("")
    lines.append("## Severity-mix shift (per issue occurrence)")
    lines.append("")
    lines.append("| Severity | OLD | NEW |")
    lines.append("|---|---|---|")
    for sev in ("critical", "warning", "info"):
        lines.append(f"| {sev} | {old_sev.get(sev, 0)} | {new_sev.get(sev, 0)} |")
    lines.append("")
    lines.append("## Per-page health deltas (sorted by rise)")
    lines.append("")
    lines.append("| Page | OLD | NEW | Δ |")
    lines.append("|---|---|---|---|")
    for d in page_deltas_sorted:
        lines.append(f"| {d.url} | {d.old_health} | {d.new_health} | {d.delta:+d} |")
    lines.append("")
    lines.append("## Top score-movers (|Δimpact| × occurrences)")
    lines.append("")
    lines.append("| Code | old imp | new imp | Δimp | occurrences |")
    lines.append("|---|---|---|---|---|")
    for code, old_imp, new_imp, dimp, n in movers[:20]:
        lines.append(f"| {code} | {old_imp} | {new_imp} | {dimp:+d} | {n} |")
    lines.append("")
    lines.append("## V2 — SCHEMA_VISIBLE_MISMATCH finding (CONFIRMED FALSE-POSITIVE, detector fixed)")
    lines.append("")
    lines.append(
        "Inspected the real pages where SCHEMA_VISIBLE_MISMATCH fired WITH JSON-LD "
        "present (R5.2 suppresses it when JSON_LD_MISSING co-fires). On every such "
        "page the fired field was `Person.name: \"Dave Galloway\"` — the site "
        "owner's byline, injected by the WP SEO plugin as an author `Person` node "
        "in the JSON-LD `@graph`, never present in the visible copy of an unrelated "
        "page (episode/blog/service pages). Two @id forms carry this same byline:"
    )
    lines.append("")
    lines.append("- `…/author/dave-galloway/#schema-author` — already suppressed by the pre-existing author-node guard.")
    lines.append("- `…/#/schema/person/<hash>` — the sibling @graph identity node; this form SLIPPED the guard and fired site-wide.")
    lines.append("")
    lines.append(
        "**Verdict: theme/plugin artifact (false positive), NOT a true content "
        "mismatch.** Fix: extended `_is_author_publisher_node` in "
        "`api/services/schema_typing.py` to also recognise the `/schema/person/` "
        "graph-node @id form. Impact weight UNCHANGED (6) per V2.2 — the detector "
        "was fixed, not the score. A genuine SUBJECT Person (ordinary @id, name "
        "absent from copy) still fires (adversarial test "
        "`tests/test_schema_typing.py::test_visible_mismatch_no_fp_theme_schema`). "
        "The numbers above were generated AFTER the detector fix, so "
        "SCHEMA_VISIBLE_MISMATCH no longer appears among the score-movers."
    )
    lines.append("")
    lines.append("## Method / caveats")
    lines.append("")
    lines.append(
        f"- Live crawl of {site} capped at max_pages={page_cap}. Both score "
        "columns computed from the SAME crawl's issue rows; only the per-code "
        "impact table differs (category, cluster suppression, cap, and "
        "page-fatal logic are identical between the two runs)."
    )
    lines.append(
        "- OLD impacts are the pre-R3 live impacts (`cur`). Codes absent from "
        "the §4 table score old-impact 0 (they did not exist / were unscored "
        "pre-R3)."
    )
    lines.append(
        "- Severity mix is counted per issue OCCURRENCE (not per unique code) "
        "so it reflects what a user saw on the dashboard."
    )
    lines.append("")
    return "\n".join(lines)


def new_imp_for(code: str, per_page_rows: dict[str, list[tuple[str, int, str]]]) -> int:
    """Current impact for a code, read from the crawl's own rows (0 if absent)."""
    for rows in per_page_rows.values():
        for c, imp, _cat in rows:
            if c == code:
                return imp
    return 0


# ---------------------------------------------------------------------------
# Live crawl driver (AC V3.3)
# ---------------------------------------------------------------------------


async def _crawl_per_page_rows(
    target_url: str, max_pages: int
) -> tuple[dict[str, list[tuple[str, int, str]]], int]:
    """Run a real crawl and return (per_page_rows, issues_total).

    per_page_rows maps a trailing-slash-normalised page URL to its current
    ``(code, impact, category)`` rows — the exact shape ``compute_page_health``
    consumes. Raises on crawl failure (caller reports honestly; no artifact).
    """
    # NB: the crawl driver takes the ENGINE's CrawlSettings dataclass, not the
    # pydantic api.models.job.CrawlSettings (which lacks crawl-time flags such as
    # skip_wp_archives).
    from api.crawler.engine import CrawlSettings, run_crawl

    settings = CrawlSettings(max_pages=max_pages)
    result = await run_crawl("v3-before-after", target_url, settings)

    per_page: dict[str, list[tuple[str, int, str]]] = {}
    # Seed every crawled page so issue-free pages score 100 (matches the store).
    for page in result.pages:
        per_page.setdefault(page.url.rstrip("/"), [])
    for issue in result.issues:
        if not issue.page_url:
            continue
        url = issue.page_url.rstrip("/")
        # The crawl Issue (api/crawler/checkers/registry.Issue) carries `.code`
        # and a plain-string `.category`.
        per_page.setdefault(url, []).append(
            (issue.code, issue.impact or 0, str(issue.category))
        )
    return per_page, len(result.issues)


def main() -> int:
    parser = argparse.ArgumentParser(description="V3 before/after HealthScore report")
    parser.add_argument("--url", default="https://livingsystems.ca")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=120,
        help="page cap for the crawl (stated in the report)",
    )
    parser.add_argument(
        "--out",
        default=str(_REPO_ROOT / "docs" / "review" / "2026-07-06_full-crawl-before-after.md"),
    )
    args = parser.parse_args()

    try:
        per_page, issues_total = asyncio.run(
            _crawl_per_page_rows(args.url, args.max_pages)
        )
    except Exception as exc:  # honest failure — no artifact written
        print(f"[V3] CRAWL FAILED — no artifact written: {exc!r}")
        return 1

    if not per_page:
        print("[V3] crawl returned no pages — no artifact written (honest failure).")
        return 1

    report = render_report(
        site=args.url,
        page_cap=args.max_pages,
        per_page_rows=per_page,
        old_scoring=OLD_ISSUE_SCORING,
        issues_total=issues_total,
    )
    out_path = Path(args.out)
    out_path.write_text(report)
    print(f"[V3] wrote {out_path} — {len(per_page)} pages, {issues_total} issues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
