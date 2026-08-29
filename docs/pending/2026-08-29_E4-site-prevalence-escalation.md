# Micro-spec E4: Escalate site-wide prevalence — 56 pages missing a description is not "info"

Date: 2026-08-29
Status: **proposal — awaiting approval**
Area: new `api/services/prevalence.py`, new `api/config/prevalence.json`;
`api/services/report_generator.py`, `api/routers/crawl.py`, `frontend/src/pages/Results.jsx`

> **Scoring is not changed by this spec.** `_ISSUE_SCORING`, `_CATEGORY_IMPACT_CAP`,
> `compute_page_health`, `compute_impact_health`, the R3/R5 calibration and every
> `_IssueSpec.severity` stay exactly as they are. E4 adds a **site-level prevalence lens**
> alongside the per-page severity model. Re-rating codes would invalidate
> `test_r3_calibration.py`, `test_r5_severity.py` and `test_scoring_paths_unified.py` for a
> problem those tests were never about.

## Problem (verified on job `05cd2496`, 2026-08-29)

TalkingToad: health **89**, **0 critical**, 173 warnings, **1,964 info** — 92% of findings
informational. An independent audit of the same site, same week, scored the SEO foundation
**58/100** and the AEO readiness **58/100**.

Both are defensible per-finding. The gap is that nothing in TalkingToad escalates when the
same minor defect is everywhere:

| Code | Severity | Pages affected | Share of 272 |
|---|---|---|---|
| `CONSENT_MODE_MISSING` | info | 170 | 63% |
| `SEMANTIC_DENSITY_LOW` | info | 168 | 62% |
| `CONVERSATIONAL_H2_MISSING` | info | 135 | 50% |
| `LANDMARK_MAIN_MISSING` | info | 111 | 41% |
| `ANCHOR_TEXT_GENERIC` | info | 87 | 32% |
| `META_DESC_MISSING` | info | 56 | 21% |
| `BROKEN_LINK_404` | info | 10 targets | — |

`META_DESC_MISSING` on one page is genuinely minor. On 56 pages it is a template and
editorial-process defect, and the external audit made it a P1 with a testable exit criterion.
`BROKEN_LINK_404` is `severity="info"`, impact 2 (`registry.py:177`, `:761`); the external
audit rated the same nine targets **P0, Impact High**.

The per-page model is right to refuse to let one dead link dominate a page score. The report
is wrong to let 56 instances of one defect read as 56 pieces of trivia.

## Change

### E4.1 — Compute prevalence

```python
# api/services/prevalence.py
def compute_prevalence(rows, indexable_pages: int) -> list[Prevalence]:
    """Per-code site prevalence. Pure; no I/O. Spec: this file."""
```

`Prevalence` = `(code, pages_affected, indexable_pages, share, tier, is_systemic)`.

Denominator is **indexable pages** — `pages_crawled` minus pages carrying `NOINDEX_META` /
`NOINDEX_HEADER` / `ROBOTS_BLOCKED`, and minus non-HTML assets. Using raw `pages_crawled`
would let a large noindex'd archive dilute every share (the denominator question from the
self-review checklist). Site-scoped codes (`_SITE_SCOPED_CODES`, `registry.py:610`) and
one-per-job codes (`FAVICON_MISSING`, `SITEMAP_MISSING`, `LLMS_TXT_MISSING`, …) are excluded
entirely — they fire once by design and a share is meaningless for them.

### E4.2 — Tiers live in config, not code (rule 9)

`api/config/prevalence.json`:

```json
{
  "tiers": [
    {"name": "systemic", "min_share": 0.30, "min_pages": 20,
     "label": "Systemic — a template or process defect, not a page defect"},
    {"name": "widespread", "min_share": 0.10, "min_pages": 10, "label": "Widespread"},
    {"name": "scattered", "min_share": 0.0, "min_pages": 0, "label": "Scattered"}
  ],
  "never_escalate": ["EXTERNAL_LINK_SKIPPED", "PAGINATION_LINKS_PRESENT", "AI_CITED_PAGE"],
  "always_systemic": ["BROKEN_LINK_404", "BROKEN_LINK_410"]
}
```

Both thresholds must be met (a share alone would call 3-of-8 pages "systemic").
`never_escalate` holds codes that are informational by nature. `always_systemic` holds codes
whose remediation is inherently template-level regardless of count — the nine broken targets
on this site are one reusable-block edit, which is precisely why the external audit called
them P0. A loader with a schema check reads it once at import; a test asserts every listed
code exists in `_CATALOGUE` (guards against silent drift, same class as the issueHelp parity
test).

### E4.3 — Surface it

- **Dashboard Summary** gains a line: *"3 systemic defects affecting 30%+ of indexable pages"*.
- New PDF section **"Systemic Defects"**, before per-category detail: each systemic code with
  pages affected, share, the one-line fix, and — where `fixability` says so — that it is one
  template change.
- **"What to Do Next"** is ordered by `(tier, pages_affected, priority_rank)` instead of by
  raw `priority_rank`, so a 56-page template defect precedes a 3-page one.
- `GET /api/crawl/{job_id}/summary` gains `prevalence: [...]`; the Results header renders a
  "Systemic" chip on those codes.

### E4.4 — Report a second, prevalence-aware score alongside health

Health stays as-is and keeps its name. The report adds **"Site Hygiene"** — `100 − Σ over
systemic codes of (tier weight × share)`, clamped to 0–100, with the formula printed beneath
it. Two numbers with stated meanings beat one number that has to carry both jobs. The PDF
states plainly that Health is per-page quality averaged, and Hygiene is how much of the estate
one defect touches.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| E4.1a | Denominator excludes noindex/robots-blocked pages and non-HTML assets | `tests/test_prevalence.py::test_e4_1a_denominator_is_indexable_only` |
| E4.1b | Site-scoped and one-per-job codes get no prevalence entry | `…::test_e4_1b_site_scoped_codes_excluded` |
| E4.1c | **Adversarial (P7):** 200 noindex'd archive pages must not dilute a 56/60 share on indexable pages | `…::test_e4_1c_noindex_archive_does_not_dilute_share` |
| E4.2a | Config loads; every code in `never_escalate`/`always_systemic` exists in `_CATALOGUE` | `…::test_e4_2a_config_codes_exist_in_catalogue` |
| E4.2b | Both `min_share` **and** `min_pages` required — 3-of-8 pages is not systemic | `…::test_e4_2b_small_site_not_falsely_systemic` |
| E4.2c | Malformed config raises at import with a named error, never silently defaults | `…::test_e4_2c_bad_config_fails_loud` |
| E4.3a | Real job fixture → `META_DESC_MISSING` (56/272) and `CONSENT_MODE_MISSING` (170/272) appear as systemic | `tests/test_report_integration.py::test_e4_3a_real_job_systemic_defects` |
| E4.3b | "What to Do Next" places the 56-page defect above a 3-page higher-`priority_rank` one | `…::test_e4_3b_worklist_ordered_by_prevalence` |
| E4.3c | `/summary` contract carries `prevalence` | `tests/test_crawl_router_contracts.py::test_e4_3c_summary_prevalence_contract` |
| E4.4a | Health score is byte-identical to pre-E4 on the same job (scoring untouched) | `tests/test_scoring_paths_unified.py::test_e4_4a_health_unchanged_by_prevalence` |
| E4.4b | **Monotonicity:** more pages affected never raises Hygiene | `tests/test_prevalence.py::test_e4_4b_hygiene_monotonic` |
| E4.4c | Hygiene = 100 on a clean site; formula printed in the PDF | `tests/test_report_generator.py::test_e4_4c_hygiene_clean_site_and_formula_shown` |

Fix→test map (P10): **E4.4a first.** The single largest risk in this spec is silently moving
the health score; that test is the guard, and it is written before any other line.

## Frontend surfaces (P25)

| Surface | Must show | Test |
|---|---|---|
| Results header | systemic count | `frontend/src/pages/__tests__/SystemicChip.test.jsx` |
| PDF | Systemic Defects section | `tests/test_report_integration.py::test_e4_3a_real_job_systemic_defects` |
| Excel | prevalence column on the Issues tab | `tests/test_excel_generator.py::test_e4_excel_prevalence_column` |

## Adjacent issues found, not fixed (rule 10)

- `agent_health_score` (95 on this job) has the same single-number problem and is not covered
  here. Worth its own decision.
- `docs/thresholds.md` will need the two prevalence thresholds at fold-in time.

## Open question for the owner

`always_systemic` currently lists only the two broken-link codes. Should `META_DESC_MISSING`
join it? It is arguably always a template/process defect once it passes a handful of pages —
but the `min_pages` gate already handles that, and hardcoding it would hide small sites where
it genuinely is three forgotten pages. Recommendation: leave it out, let the thresholds decide.
