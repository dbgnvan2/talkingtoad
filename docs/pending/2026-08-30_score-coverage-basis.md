# The health score must carry the coverage it was computed over

**Date:** 2026-08-30
**Status:** Approved — user said "proceed with all of this"
**Scoring model:** `2026-07-06-r5` → `2026-08-30-r6`

## Problem

Measured on livingsystems.ca, two crawls 49 minutes apart:

| Job | Analyses enabled | Issues | **Health** |
|---|---|---|---|
| `d1394998` | `link_integrity` only | 356 | **100** |
| `a87e2d61` | all | 2,206 | **87** |

**The scan that skipped eight categories scored a perfect 100.**

Page Health is `100 − Σ impact`. A category that never runs contributes no
issues, so it costs nothing, and "we did not look" is arithmetically identical
to "we found nothing". This breaks the project's own review-checklist item 7
(more failure must never raise the score) and it has already misled the site
owner in practice.

## What NOT to do

Do not deduct for unchecked categories. Inventing a penalty for a check that did
not run is fabricating a finding — the same class of error as the defects this
week's audit fixed. A partial scan's score is not *worse*; it is **not
comparable**.

## Fix — S1: the score carries its basis

`get_summary` gains `health_score_basis`:

```
{
  "mode": "all" | "partial",
  "categories_scored":   [...],     # categories that could contribute impact
  "categories_unscored": [...],     # switched off — contributed nothing
  "comparable": bool,               # False when mode == "partial"
}
```

Derived from the job's `analysis_coverage` (already persisted, C1). No second
source of truth, and legacy audits without that record report `mode: "all"`,
matching how they were actually crawled.

## Fix — S2: no surface may present a partial score as a whole-site score

- **Results header:** the score renders with its basis — "87 / 100 across all
  categories" vs "100 / 100 across link integrity only (6 categories not
  scored)". A bare number is never shown for a partial scan.
- **PDF and Excel:** the existing `analysis_coverage_note` gains a sentence
  naming the score's basis, next to the number.
- **Job comparison:** two scores with different bases are not comparable; the
  comparison surface must say so rather than showing a delta.

## Fix — S3: version bump

`SCORING_MODEL_VERSION` → `2026-08-30-r6`. Historical audits keep their stamp,
so a reader can tell which model produced a number. The arithmetic is unchanged
— only the claim attached to it — but the stamp is what lets a future comparison
know the basis field exists.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| S1.1 | A partial scan reports `mode="partial"`, `comparable=False`, and names the unscored categories | `tests/test_score_basis.py::test_s1_partial_scan_basis` |
| S1.2 | Adversarial: a full scan reports `mode="all"`, `comparable=True`, empty `categories_unscored` | `…::test_s1_full_scan_basis` |
| S1.3 | A legacy audit with no `analysis_coverage` reports `mode="all"` — it was crawled that way | `…::test_s1_legacy_job_basis` |
| S1.4 | `categories_scored` + `categories_unscored` partition the catalogue's categories | `…::test_s1_basis_partitions_categories` |
| S2.1 | The score is never rendered without its basis on a partial scan | `frontend/.../SummaryPanelCoverage.test.jsx` |
| S2.2 | PDF and Excel name the basis beside the number | `…::test_s2_exports_name_the_basis` |
| S3.1 | New jobs stamp `2026-08-30-r6` | `…::test_s3_version_bumped` |

S1.1 is the one that fails today: nothing distinguishes the 100 from the 87.
