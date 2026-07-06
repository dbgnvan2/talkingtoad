---
status: pending-approval (implementation plan)
proposed: 2026-07-06
author: Claude Code
governance: SPEC ONLY — owner sign-off required before code / before running the live crawl
supersedes-open-items:
  - docs/review/NEXT-STEPS.md item 5 (deploy-gate validation crawl)
  - docs/review/2026-07-04_r3-validation-crawl.md follow-ups (SCHEMA_VISIBLE_MISMATCH, full crawl, GSC)
owner-decisions (2026-07-06):
  - run a FULL crawl of livingsystems.ca (the project test site)
  - owner will connect the site's Google Search Console (OAuth) for V4
  - reconstruct the pre-R3 baseline for a true numeric before/after delta
---

# V-series — deploy-gate validation (close the remaining open items)

Closes the last open work surfaced by the 2026-07 scoring audit. NEXT-STEPS.md items 1–4
(R2.x/R6/R7/R8) already shipped; this covers item 5 + the validation-crawl follow-ups.

## Implementation status (2026-07-06)
| Item | Status | Evidence |
|---|---|---|
| **V1** (close R3.4) | **DONE** — `AI_BOT_BLANKET_DISALLOW` already a suppression parent over its four per-bot children in `job_store_base._CLUSTER_SUPPRESSION`; added the explicit subset/never-security-redirect case. | `tests/test_r5_clusters.py::test_v1_blanket_robots_suppresses_only_present_children`; R3.4 marked CLOSED in `docs/review/NEXT-STEPS.md` |
| **V2** (`SCHEMA_VISIBLE_MISMATCH` FP) | **DONE — CONFIRMED FALSE-POSITIVE, detector fixed** (weight unchanged). WP SEO-plugin author-byline `Person` graph node (`@id …/#/schema/person/<hash>`) slipped the author-node guard and fired site-wide. | Fix in `api/services/schema_typing.py:_is_author_publisher_node`; adversarial test `tests/test_schema_typing.py::test_visible_mismatch_no_fp_theme_schema` + true-positive-preserved `::test_visible_mismatch_still_fires_on_true_subject_person`; finding in `docs/review/2026-07-06_full-crawl-before-after.md` |
| **V3** (before/after crawl) | **DONE** — real full crawl (119 pages, max_pages=120): site health **73 → 88 (+15)**; warnings 453 → 166, info 477 → 764. | `scripts/before_after_healthscore.py`; `tests/test_before_after_report.py::{test_baseline_reconstruction_matches_r3_cur_column,test_delta_computation}`; artifact `docs/review/2026-07-06_full-crawl-before-after.md` |
| **V4** (GSC Authority-Matrix) | **DONE (tooling) — LIVE RUN BLOCKED-ON-CONNECTION.** Quadrant/correlation logic + synthetic report built and tested; live run needs the owner to connect GSC OAuth (creds live in-memory in `api/routers/gsc._creds_cache`). | `scripts/gsc_authority_matrix.py`; `tests/test_gsc_authority_matrix.py`; synthetic artifact `docs/review/2026-07-06_gsc-authority-matrix.md`; run steps in the script header |

**V4 live-run handoff:** with the API server running, connect Search Console (Connections panel /
`GET /api/gsc/connect` → Google consent → `/api/gsc/callback`) so `_creds_cache` is populated in that
process, then run `python -m scripts.gsc_authority_matrix --site "https://livingsystems.ca/" --days 30
--max-pages 120`. It exits 2 and writes nothing if creds are absent (never fabricates GSC data).

## V1 — Close R3.4 (extra suppression clusters) — NO CODE
R3.4 (blanket-robots suppresses per-bot children; noindex page suppresses content checks) is
**subsumed by R5**: R5.3 noindex scope-reduction is live (`job_store_base.py:_noindex_reduced_codes`,
exempts security/redirect) and R5.2 extended `_CLUSTER_SUPPRESSION` (incl. the robots cluster);
covered by `tests/test_r5_clusters.py`.
- **AC V1.1** Verify `AI_BOT_BLANKET_DISALLOW` is a suppression parent over its per-bot children in
  `_CLUSTER_SUPPRESSION` (add the rule + a `test_r5_clusters.py` case only if genuinely missing).
- **AC V1.2** Mark R3.4 closed in `docs/review/NEXT-STEPS.md`.

## V2 — `SCHEMA_VISIBLE_MISMATCH` false-positive check
The validation crawl flagged it firing on every page at impact 6. R5.2 now suppresses it when
`JSON_LD_MISSING` co-fires, so it only scores where JSON-LD is present — which sharpens (not removes)
the "is the detector misfiring on theme-injected schema?" question.
- **AC V2.1** From the V3 full crawl, inspect 2–3 real pages where it fires with JSON-LD present:
  compare the JSON-LD values against visible text. Written finding (true-positive vs theme artifact).
- **AC V2.2** IF confirmed false-positive: micro-spec addendum + **tests-first** detector fix in
  `api/services/schema_typing.py` / `api/crawler/parser.py` (leave the weight unchanged — fix
  detection). Adversarial test: a page with theme-injected schema whose values DO appear in visible
  copy must NOT fire `SCHEMA_VISIBLE_MISMATCH`. → `tests/test_schema_typing.py::test_visible_mismatch_no_fp_theme_schema`
- **AC V2.3** IF true-positive: document in the crawl report, no code change.

## V3 — Full-site crawl + before/after HealthScore report
- **AC V3.1** A reconstruction of pre-R3 impacts: parse the `cur` column from
  `docs/pending/OLD/2026-07-03_r3-FINAL-calibration.md` §4 (effort unchanged) into an
  `OLD_ISSUE_SCORING` fixture. Unit-tested against a few known rows.
  → `tests/test_before_after_report.py::test_baseline_reconstruction_matches_r3_cur_column`
- **AC V3.2** A report script (e.g. `scripts/before_after_healthscore.py`) that crawls the full site,
  scores each page under both current `_ISSUE_SCORING` and `OLD_ISSUE_SCORING` via the *same*
  `compute_page_health` path, and emits `docs/review/2026-07-06_full-crawl-before-after.md` with:
  site health old→new, per-page deltas, severity-distribution shift, and top score-movers.
  Delta math unit-tested. → `tests/test_before_after_report.py::test_delta_computation`
- **AC V3.3** Run it (full crawl, authorized) and record the artifact; flag any code whose new score
  looks wrong on real data (feeds V2).
- *Operational gate:* live crawl of livingsystems.ca (owner-authorized).

## V4 — GSC Authority-Matrix correlation (owner connects GSC first)
The Authority-Matrix feature is already shipped (M6.4, `gsc.py`/`gsc_client.py`). Only the run remains.
- **Owner step (blocker):** connect the site's Search Console — `GET /api/gsc/connect` (bearer auth)
  → Google consent → `/api/gsc/callback` stores encrypted creds. I'll provide exact commands.
- **AC V4.1** After connection, run the correlation and emit an Authority-Matrix report
  (per-page HealthScore × GSC clicks/impressions, 2×2 quadrants) into `docs/review/`.
- **AC V4.2** Note any page where structural health and real search performance strongly disagree
  (the empirical calibration validator per R3 spec §6).

## Closeout
- **AC C.1** When V2–V4 are done and their reports written, archive `docs/review/NEXT-STEPS.md` and
  `docs/review/2026-07-04_r3-validation-crawl.md` into `docs/review/OLD/` (repath any pointers).
- **AC C.2** Update `PLAN-V4.0.md` tally; commit per item. Push held until owner approves deploy.

## Acceptance criteria → tests / artifacts
| ID | Verified by |
|---|---|
| V1.1/V1.2 | `tests/test_r5_clusters.py` (+ NEXT-STEPS edit) |
| V2.2 | `tests/test_schema_typing.py::test_visible_mismatch_no_fp_theme_schema` (only if FP) |
| V3.1 | `tests/test_before_after_report.py::test_baseline_reconstruction_matches_r3_cur_column` |
| V3.2 | `tests/test_before_after_report.py::test_delta_computation` |
| V3.3 | Artifact: `docs/review/2026-07-06_full-crawl-before-after.md` |
| V4.1/V4.2 | Artifact: Authority-Matrix report in `docs/review/` |

## Cannot be code-tested (human/operational)
- The live full crawl (authorized) and its distribution sanity-check.
- The V2 true-positive-vs-artifact judgement on real pages.
- The GSC OAuth connection (owner's Google account) — hard blocker for V4.
