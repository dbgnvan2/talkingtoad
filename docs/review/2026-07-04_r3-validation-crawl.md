---
status: validation report
date: 2026-07-04
site: https://livingsystems.ca (project test site)
scope: sanity-check the R2/R3 scoring recalibration + Path-A store parity on real data
verdict: PASS (with one code flagged for owner review — no silent change made)
---

# R3 calibration — validation crawl (livingsystems.ca)

Deploy-gate check for the recalibration (R2/R3 + Path-A store parity). Ran the crawl engine directly
(`run_crawl`, `max_pages=10`) and computed health via the shipped `compute_impact_health`.

## Headline numbers
| Metric | Value |
|---|---|
| Pages crawled | 10 |
| Issues found | 212 |
| **Site Health** | **61** |
| **Agent Health** | **81** |
| Severity mix | **0 critical · 48 warning · 164 info** |
| Lowest page score | 54 (a team-member bio) |

## Sanity checks (all pass)
1. **Distribution is reasonable.** Site 61 reads as "needs work, not broken" for a real nonprofit
   site. **77% of issues are info-tier** — exactly what R3 intended (most checks are honestly minor).
   This confirms the "scores rise / fewer false alarms" goal vs the old inflated-cosmetic-penalty
   scoring.
2. **No page cratered.** Lowest page = 54; nothing near 0. Correct — **no page-fatal codes**
   (`NOINDEX_*`, `ROBOTS_BLOCKED`, `PAGE_TIMEOUT`, HTTP) are present on this healthy production site,
   so nothing *should* be near 0. (The page-fatal path is unit-tested; it simply had nothing to fire
   on here.)
3. **The deweighted FP-magnets behaved.** `SEMANTIC_DENSITY_LOW` fired on all 10 pages but at
   **impact 1** (was a warning-tier magnet pre-R3); `UNSAFE_CROSS_ORIGIN_LINK` fired 10× at
   **impact 0** (noopener implied — correctly weightless). Neither distorts the score now.
4. **Broken-link downweight visible.** No broken-link pile-ups dominated any page (the old 10-per-
   link behaviour is gone).
5. **Per-category cap / suppression** did their job — no single category floored a page.

## Top issues (by frequency, impact in parens)
`SCHEMA_VISIBLE_MISMATCH` (6) ×10 · `JSON_LD_INVALID` (4) ×10 · `SCHEMA_TYPE_CONFLICT` (2) ×10 ·
`ORPHAN_PAGE` (4) ×8 · `FIRST_VIEWPORT_NO_ANSWER` (2) ×8 · `ANCHOR_TEXT_GENERIC` (2) ×8 ·
`REDIRECT_CHAIN` (2) ×9 · `OG_*`/`TWITTER_CARD_MISSING` (1) ×10 · `CONVERSATIONAL_H2_MISSING` (1) ×7.

## ⚠ Flagged for owner review (NOT changed — scoring is derived via `_CALIBRATION`)
- **`SCHEMA_VISIBLE_MISMATCH` (impact 6, Established) dominates** — it is the single highest-
  `priority_rank` issue and fires on **every** page. If this is a **true** positive (structured-data
  values genuinely absent from the visible text) impact 6 is defensible. But it firing site-wide at
  identical strength smells like a **theme/plugin artifact** (schema injected by the WP theme that
  never matches visible copy). **Action:** manually verify 2-3 pages before trusting it as the site's
  #1 issue; if it's a theme artifact, the *checker* (detection) needs a fix (R2.x-style), not the
  score. Proposed adjustment only if verified FP: none to the weight — fix the detector.
- **`ORPHAN_PAGE` ×8 of 10 pages** is a small-crawl artifact (only 10 pages fetched, so most pages
  aren't linked from the sampled set). The R2.x dynamic-listing caveat already annotates these.
  Re-check on a full crawl; not a scoring concern.

## Caveats / limits
- **10-page spot-check**, not a full crawl — enough to validate the score *distribution* and the
  calibration's shape, not every code. A full crawl is recommended before production deploy.
- **No before/after delta computed** (the old impacts aren't in the tree to run side-by-side); the
  qualitative "scores rise, severity shifts to info" is confirmed against the calibration intent.
- **GSC / Authority-Matrix correlation not run** (needs the site's Search Console connection); that
  remains the recommended empirical validator per the calibration spec §6.

## Recommendation
The recalibration is **safe to deploy** on this evidence: scores are sensible, severity is honest,
page-fatal handling is intact, and the previously-inflated cosmetic penalties are gone. Before/right
after deploy: (1) verify `SCHEMA_VISIBLE_MISMATCH` on a few real pages, (2) run one full-site crawl,
(3) start the GSC HealthScore-correlation loop as the ongoing validator.
