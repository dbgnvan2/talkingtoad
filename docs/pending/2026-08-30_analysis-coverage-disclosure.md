# A scan with analyses switched off looks identical to a clean site

**Date:** 2026-08-30
**Status:** Proposed — awaiting approval
**Reported by:** user — "The latest scan went from 1 warning to 118 and 356 info
to 2088 — what the heck happened."

## Problem

Two full crawls of livingsystems.ca, 49 minutes apart, same 500-page budget, same
`content_scope: full`:

| Job | `enabled_analyses` | Pages | Warnings | Info |
|---|---|---|---|---|
| `d1394998` 03:15 | `['link_integrity']` | 272 | **1** | 355 |
| `a87e2d61` 04:04 | `None` (all) | 256 | **118** | 2088 |

Nothing regressed. The earlier scan ran **only** the link-integrity group; every
other category was switched off and therefore produced nothing:

| Category | `d1394998` | `a87e2d61` |
|---|---|---|
| ai_readiness | 0 | 769 |
| metadata | 0 | 354 |
| image | 0 | 237 |
| analytics | 0 | 159 |
| semantic_html | 0 | 111 |
| url_structure | 0 | 91 |
| crawlability | 0 | 90 |
| heading | 0 | 58 |
| security *(always runs)* | 172 | 158 |
| redirect | 169 | 155 |
| broken_link | 15 | 24 |

The two categories that ran in **both** went slightly *down*. The entire 1,733-issue
jump is categories that were disabled.

The defect is not the numbers — they are correct. It is that **the results screen
and the report never say which analyses ran.** A scan with eight categories off
renders exactly like a thorough scan of a healthy site: same layout, same tiles,
same headline score, just fewer findings. The user cannot tell "we looked and it
was clean" from "we never looked", and reasonably read the difference between two
scans as a regression in the tool.

This is the same failure shape as the ORPHAN_PAGE work shipped in `cb421cf`
(**P31**): an absent finding reads as a passing one, and a suppressed check that
does not announce itself is a fabricated all-clear. There it was one check; here
it is up to eight whole categories, and the health score is computed over them.

**Worse than the issue lists:** `health_score` and `agent_health_score` are
derived from the issues that were emitted. Disabling categories therefore *raises*
both. `d1394998` — the scan that checked almost nothing — will show the best
score in the job history. Same inversion as the backlog item in `LEARNINGS.md`
where suppressing ORPHAN_PAGE raised the score, and the same rule broken:
coverage falls, grade improves.

## Root cause

`CrawlSettings.enabled_analyses` (`api/crawler/engine.py:189`) restricts which
categories run, resolved through `_ANALYSIS_CATEGORY_MAP` (`engine.py:152`):

| Group | Categories |
|---|---|
| `link_integrity` | broken_link, redirect |
| `seo_essentials` | metadata, url_structure |
| `site_structure` | heading |
| `indexability` | crawlability, sitemap |
| `ai_readiness` | ai_readiness, rendering, semantic_html |
| `analytics` | analytics |
| `image` | image |
| *(always)* | security |

The selection is persisted in `settings_json` and is otherwise **never read
back for display**. No API response, no results tile, no PDF section states it.
`None` (= all) and a one-group selection are indistinguishable downstream.

## Fix

### C1 — carry the resolved coverage out of the crawl

Return `analysis_coverage` in the crawl summary, alongside the existing
`orphan_detection`:

```
analysis_coverage = {
  "mode": "all" | "partial",
  "groups_enabled":  ["link_integrity"],
  "groups_disabled": ["seo_essentials", "site_structure", "indexability",
                      "ai_readiness", "analytics", "image"],
  "categories_checked":   [...],   # resolved via _ANALYSIS_CATEGORY_MAP
  "categories_unchecked": [...],
}
```

Derived from `settings.enabled_analyses` and the existing map — no new source of
truth. Persisted on the job like `orphan_detection`, so historical audits keep
their own record. `None` on audits crawled before this field existed.

### C2 — say so on every surface that shows findings or a score

- **Results header:** when `mode == "partial"`, a banner naming what was not
  checked. Not a footnote — it qualifies every number on the page.
- **Category tiles:** an unchecked category renders as **"not checked"**, never
  as `0`. This is the C1-critical case: a `0` tile for a category that never ran
  is the same fabricated all-clear as ORPHAN_PAGE's green ✓.
- **Health score:** display the coverage qualifier next to the score. The score
  itself is **not** recalculated here (see C3).
- **PDF `_render_caveats_section`** and **Excel summary:** extend the existing
  `orphan_coverage_note` helper in `api/services/coverage_notes.py` with a
  sibling `analysis_coverage_note`, wired into the same two call sites.

No change to navigation or page structure (CLAUDE.md GUI rule) — this adds
disclosure to existing surfaces only.

### C3 — NOT in scope: making the score coverage-aware

Whether a partial scan should suppress the health score, scale it, or label it
provisional is a **scoring-model change** requiring its own spec and a
`scoring_model_version` bump. C2 discloses the problem beside the number; it does
not change the number. Recorded in `LEARNINGS.md` open risks next to the existing
ORPHAN_PAGE score inversion — they are the same defect and should be fixed
together, in one deliberate scoring change.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| C1.1 | A partial-analysis crawl reports `mode="partial"` with the correct enabled/disabled groups | `tests/test_analysis_coverage.py::test_c1_partial_selection_recorded` |
| C1.2 | Adversarial: `enabled_analyses=None` reports `mode="all"` and an empty `groups_disabled` | `…::test_c1_full_scan_reports_all` |
| C1.3 | `categories_unchecked` never contains `security` (it always runs) | `…::test_c1_security_always_checked` |
| C1.4 | Round-trips through both stores; legacy jobs read back `None` | `…::test_c1_round_trip_and_legacy_none` |
| C1.5 | Present in the summary endpoint the frontend reads | `…::test_c1_summary_endpoint_carries_coverage` |
| C2.1 | An unchecked category tile renders "not checked", **not** `0` | `frontend/src/pages/__tests__/CategoryCoverage.test.jsx` |
| C2.2 | Adversarial: a checked category that genuinely found nothing still renders `0` | same file |
| C2.3 | The partial-scan banner renders, and does not on a full scan | same file |
| C2.4 | PDF and Excel carry the note | `tests/test_analysis_coverage.py::TestExportSurfaces` |

C2.1/C2.2 are the pair that matters: they pin the distinction between "checked,
clean" and "never looked", which is the whole point.

## Adjacent issues found, not fixed

1. **The score inversion (C3)** — shares a root with the ORPHAN_PAGE backlog item.
2. **`enabled_analyses` has no UI record of what was chosen** on re-runs, so
   comparing two jobs in the history is guesswork — C1's persisted field makes a
   job-to-job coverage diff possible later.
3. **`_ANALYSIS_CATEGORY_MAP` is the only place group→category lives**, and
   `tests/test_engine_analysis_map.py` already enforces total coverage; C1 must
   derive from it rather than re-listing groups, or the two will drift.
