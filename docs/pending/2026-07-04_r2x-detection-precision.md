---
status: pending (authorized batch — audit remediation R2.x)
proposed: 2026-07-04
author: Claude Code (Opus 4.8)
scope: Phase-1 detection-precision fixes; NO scoring changes (impact is derived via _CALIBRATION)
companion: docs/review/2026-07-03_remediation-plan.md (R2.x) · 2026-07-03_code-audit-report.md (Phase 1)
---

# R2.x — detection-precision fixes (batch)

> **IMPLEMENTED 2026-07-04.** All 8 items shipped with tests (`tests/test_r2x_precision.py`);
> 4 `test_image_analyzer.py` tests updated to the new consequence-precedence semantics.
> Full suite 1818 passed (only the 3 pre-existing unrelated `test_usage_aggregation.py` failures).
> No scoring changes.

Eight accuracy fixes from the Phase-1 audit. None change `_ISSUE_SCORING`/`_CALIBRATION` (scoring is
derived + already calibrated); they change **what fires and what's reported**, not the weights.

## Items, acceptance criteria → test

1. **`LINK_EMPTY_ANCHOR` accessible name.** `_find_empty_anchors` (parser.py) only honored visible
   text / child `img[alt]` / `aria-label`. Reuse the existing `_accessible_name()` helper
   (parser.py:1252) so `aria-labelledby`, anchor `title`, and child-`aria-label` also count as a
   name. **AC:** `test_anchor_with_aria_labelledby_not_flagged`, `test_anchor_with_title_not_flagged`.

2. **`MIXED_CONTENT` active vs passive.** `_count_mixed_content` lumps all http:// resources. Split
   **active** (script/iframe/stylesheet — browser-blocked) from **passive** (img/media —
   auto-upgraded); expose both counts on `ParsedPage` and in the issue `extra`. Single code kept
   (no scoring change). **AC:** `test_mixed_content_active_passive_breakdown`.

3. **Image consequence-precedence.** In `_check_performance`, a single bad image emitted up to 4
   codes. When `IMG_OVERSIZED` or `IMG_OVERSCALED` (root causes) fire for an image, suppress
   `IMG_SLOW_LOAD` and `IMG_POOR_COMPRESSION` (consequences) for that image; tag a heuristic
   `likely_lcp` in `extra` for the largest image on the page. **AC:**
   `test_oversized_image_suppresses_slow_and_compression`.

4. **`ORPHAN_PAGE` dynamic-listing caveat.** Link discovery is raw-HTML-only (cross_page.py), so
   JS/query-driven listings false-positive. Add a `caveat` note to the issue `extra`. **AC:**
   `test_orphan_page_carries_dynamic_caveat`.

5. **Staging-vs-production awareness.** When `NOINDEX_META`/`NOINDEX_HEADER`/`AI_BOT_BLANKET_DISALLOW`
   fire on a **production-looking** host (not `staging.`/`dev.`/`test.`/`.local`/`localhost`), add a
   `possible_staging_leftover: true` note to `extra`. **AC:** `test_noindex_on_prod_flags_staging_leftover`,
   `test_noindex_on_staging_host_no_flag`.

6. **Freshness page-type awareness.** `CONTENT_STALE` (flat 365-day) and `CONTENT_STAT_OUTDATED`
   (flat) ignore page type. Use `infer_page_type` + `_PAGE_TYPE_CADENCE` so evergreen types
   (`team_member` = never) are exempt and per-type cadence drives `CONTENT_STALE`. **AC:**
   `test_content_stale_exempts_evergreen_page`, `test_content_stat_outdated_exempts_team_member`.

7. **Unify AI-bot tables.** `parser.py:_AI_BOT_NAMES` (X-Robots) diverges from `ai_bots.py:AI_BOTS`
   and includes deprecated `anthropic-ai`. Derive it from `AI_BOTS` (current bots, normalized).
   **AC:** `test_x_robots_ai_bot_names_derived_from_ai_bots`.

8. **`ROBOTS_BLOCKED` expected-disallow allow-list.** Disallowed cart/search/filter/param URLs are
   intentional, not problems. Add an allow-list so those aren't flagged; add crawl-vs-index wording
   to the finding `extra`. **AC:** `test_expected_disallow_not_flagged`, `test_real_disallow_still_flagged`.

## Constraints
- No changes to `_ISSUE_SCORING` / `_CALIBRATION` / severity (derived).
- Tests-first; `pytest tests/ -q` green except the 3 pre-existing `test_usage_aggregation.py` failures.
- Regenerate `docs/issue-codes.md` only if catalogue text changes (it shouldn't here).
