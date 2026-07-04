---
status: proposed-remediation-plan
audit_date: 2026-07-03
auditor: Claude Code (Opus 4.8)
companions: 2026-07-03_code-audit-report.md (Phases 1-3) · 2026-07-03_scoring-change-plan.md (Phase 4)
goal: make TalkingToad the best SEO / GEO web-page review tool possible
governance: audit-prompt (Phases 1-4 report-only; Phase 5 code-quality fixes may land directly with tests)
---

# TalkingToad — Audit Remediation Plan

Every finding from the audit, sequenced into buildable work items. Priority order:
**P0 correctness bugs → P1 scoring integrity → P2 detection precision → P3 feature builds.**
Each item lists acceptance criteria mapped to a specific test (per CLAUDE.md planning rules).
Per repo governance, each substantive item still needs a `docs/pending/` micro-spec approved
before code — this plan is the backlog that feeds those.

Legend: **[C]** correctness · **[S]** scoring · **[P]** precision · **[F]** feature · **[Q]** code-quality.

## Implemented 2026-07-03 (P0 + Phase 5 batch)

Shipped with tests in `tests/test_audit_2026_07_p0.py` (all green; full suite 1745 passed, 3
**pre-existing unrelated** failures in `test_usage_aggregation.py` — billing code, not touched here):
- **R0.1** citation misfire quarantined (`issue_checker.py`) — `test_citation_missing_not_emitted_on_substantial_page`.
- **R0.2** `Claude-User` honors_robots + registry recommendation + **frontend help** (`issueHelp.js`) corrected — `test_claude_user_honors_robots`, `test_user_fetch_recommendation_not_blanket_ineffective`.
- **R0.3** retry + exponential backoff for transient failures (`fetcher.py`) — `test_transient_5xx_retried_then_success`, `test_persistent_5xx_still_returns_5xx`, `test_network_error_retried_then_success`, `test_success_not_retried`.
- **R0.4** `_classify_fetch_error` — SSRF no longer mislabeled as timeout; error_type tagged (`engine.py`) — `test_classify_fetch_error_*`. (R0.4-full: dedicated `FETCH_FAILED` code still deferred to the scoring PR.)
- **R0.5** invalid `severity="error"` → `warning` for `CONTENT_CLOAKING_DETECTED` (registry + `issueHelp.js`) — `test_all_catalogue_severities_valid`.
- **R-Q1** `make_issue` unknown-code now raises a clear `KeyError` (docstring matches) — `test_make_issue_unknown_code_raises_keyerror`.
- **R-Q2** stale docstring counts fixed (131/49 → 151/62) — bijection asserted by `test_scoring_catalogue_bijection`.
- **R-Q3** already satisfied by existing `test_every_ai_readiness_code_has_confidence_label`.
- **R-Q4** `_AI_READINESS_CONFIDENCE` grouping tidied (misplaced entries moved under correct section comments).
- `docs/issue-codes.md` regenerated from the catalogue (sync test green).

### Implemented 2026-07-03 (scoring-value migration batch — R1 + R2 + R5)

Shipped with tests in `tests/test_audit_2026_07_p0.py` (full suite 1766 passed; same 3 pre-existing
unrelated `test_usage_aggregation.py` failures):
- **R2** the 20 evidence-based impact/effort changes applied to `_ISSUE_SCORING` — `test_scoring_migration_applied` (parametrized ×20).
- **R5** fixability corrections `ORPHAN_PAGE` and `BROKEN_LINK_5XX` → `content_edit`; fixability-group tests updated — `test_fixability_corrections_applied`.
- **R1** dead-code allowlist justifications corrected (`test_class1_invariants.py`) — the JS-trio ("engine consumes JSRenderResult" was false → unwired/R7), citation codes (quarantined/R6), and extractability codes (actually live via dynamic dispatch, were mislabeled "not feasible") now grouped by real reason.
- `docs/issue-codes.md` regenerated.

### Implemented 2026-07-03 (Path A — store parity + R4 cluster suppression)

Full suite 1784 passed; same 3 pre-existing unrelated `test_usage_aggregation.py` failures.
- **Store-parity fix (newly discovered blocker).** Redis (prod) computed the MAIN health score with
  the density model, not the impact model — so R2/R3/R4 never reached production. Both stores now
  route through one shared `job_store_base.compute_impact_health`; the dead Redis
  `_compute_health_score` was removed. **One-time effect: production main health scores shift from
  the density model to the impact model.** Folded into `docs/functional-specification.md`.
- **R4 cluster suppression** — `page_suppressed_codes` + `_CLUSTER_SUPPRESSION` (4 rules) applied in
  the shared helper, so both stores and both the main + agent scores charge one root cause once.
  Issues stay visible; scoring-only.
- Tests: `tests/test_r4_cluster_suppression.py` (unit + interactions + parity via the shared
  function); Redis summary tests updated to the shared helper.

### Implemented 2026-07-03 (R3 structural pieces — page-health model + cluster merge)

From the validated-merge spec (`docs/pending/2026-07-03_r3-model-b-calibration.md`), the low-regret
structural half shipped; the high-variance impact recalibration is held for a second opinion.
- **Per-category cap (20) + page-fatal bypass** in the shared `compute_impact_health` — correlated
  minor issues and per-occurrence broken-link stacking can no longer zero a page, while genuine
  page-fatal codes bypass the cap and still score a dead page low. Both stores; scoring-only.
- **Cluster merge** — `JS_DEPENDENT_NAVIGATION` added to the JS-shell cluster; two of Gemini's
  proposed clusters dropped as already mutually exclusive; `HTTPS_REDIRECT_MISSING⊳HTTP_PAGE` dropped
  as cross-scope (site vs page).
- Threaded `category` through the scoring path (both stores). Docs updated (functional spec, thresholds).
- Tests: `tests/test_r4_cluster_suppression.py` (caps, page-fatal bypass, per-occurrence); two
  `test_api.py` health tests updated to the capped model. Full suite 1785 passed; same 3 pre-existing
  unrelated failures.

### Implemented 2026-07-03 (R3 — full calibration, two-opinion triangulation)

Both expert opinions (Gemini + Fable) received and triangulated with the audit (130/151 codes
converged; 21 divergences adjudicated). Adopted Fable's synthesis (hard-capped Model B). Spec:
`docs/pending/2026-07-03_r3-FINAL-calibration.md`.
- **R3.1** — 120 impacts recalibrated; impact now **derived** from a `_CALIBRATION` record via
  `derive_impact()` (matrix + Aggarwal measured lane + page-fatal 10-tier + documented overrides);
  `_AI_READINESS_CONFIDENCE` regenerated.
- **R3.2** — severity **derived from impact** (`severity_from_impact`: ≥8 critical / 4–7 warning /
  ≤3 info) — one source of truth, fixing the impact/severity drift.
- **R3.3** — priority `impact×10 − effort×6`; `quick_win` computed field (impact≥4 & effort≤1).
- Tests: `tests/test_r3_calibration.py` (derivation parity, severity, 10-tier, measured lane,
  priority, quick-win). Docs regenerated (issue-codes.md, functional-spec, thresholds). Full suite
  1790 passed; only the 3 pre-existing unrelated failures.

**Held / next:** validate on a real before/after crawl of livingsystems.ca (scores rise — intended);
R3.4 optional extra suppression clusters; R2.x precision fixes; R6-R8 features. Frontend
`issueHelp.js` per-code severity labels may now lag the derived severities (spawned as a follow-up).

---

## P0 — Correctness bugs (small, high-impact, do first)

### R0.1 [C] Citation model fed hardcoded empty data
`issue_checker.py:598-602` builds `PageCitations(citations=[], attribution_style="none")`, so
`lacks_citations` is **always True** on any >200-word page → `CITATIONS_MISSING_SUBSTANTIAL_CONTENT`
fires site-wide; `CITATIONS_ORPHANED` / `CITATIONS_SOURCES_INACCESSIBLE` can never fire
(`citation_model.py:88-98`).
- **Fix (interim):** stop emitting the misfiring code until real citations are parsed (R6), OR
  gate it behind actual extracted-link data. Do not ship a −3 that measures nothing.
- **AC:** `test_citations_not_emitted_without_real_data` — a >200-word page with no citation parser
  wired produces **no** `CITATIONS_MISSING_SUBSTANTIAL_CONTENT`. Adversarial (P7): a page that
  genuinely has citations must not be flagged once R6 lands.

### R0.2 [C] `Claude-User` honor-robots is factually wrong
`ai_bots.py` sets `"Claude-User": {"honors_robots": False}`; `registry.py:982` recommendation text
repeats it. Web-verified 2026-07-03: Anthropic honors robots.txt on all three Claude bots.
- **Fix:** `honors_robots: True` for Claude-User; correct the `registry.py:982` copy to name only
  ChatGPT-User / Perplexity-User as ambiguous/non-honoring.
- **AC:** `test_claude_user_honors_robots` asserts the table value; `test_user_fetch_recommendation_text`
  asserts the recommendation no longer claims Claude-User ignores robots.txt.

### R0.3 [C] No retry — transient failures become permanent negatives (P1)
`fetcher.py:110+` is single-attempt; `BROKEN_LINK_5XX`, `PAGE_TIMEOUT`, `EXTERNAL_LINK_TIMEOUT`
fire on first observation (`engine.py:454,649`, `links.py:52`).
- **Fix:** 1 retry + backoff before firing any of the three; mark them retryable in state.
- **AC:** `test_transient_5xx_retried_before_firing` (mock: 5xx then 200 → no issue);
  `test_persistent_5xx_still_fires`. Harden the class together (P5): apply to all three siblings.

### R0.4 [C] `PAGE_TIMEOUT` overloaded
`engine.py:454` emits `PAGE_TIMEOUT` for **any** `status_code==0` (DNS, refused, SSRF block, timeout).
- **Fix:** distinguish real timeouts from other status-0 errors; emit a generic `FETCH_FAILED`
  (new code) or route SSRF/DNS to distinct messaging.
- **AC:** `test_dns_failure_not_reported_as_timeout`, `test_ssrf_block_not_reported_as_timeout`.

### R0.5 [C/Q] `CONTENT_CLOAKING_DETECTED` has invalid severity `"error"`
Grid shows `severity="error"` but `Severity = Literal["critical","warning","info"]`
(`models/issue.py:16`). Latent (code is dead) but would fail validation if emitted.
- **Fix:** set `"warning"`. **AC:** `test_all_catalogue_severities_valid` — every `_CATALOGUE`
  severity ∈ the Literal.

---

## P1 — Scoring integrity

### R1 [S] Retire / quarantine dead scored codes
8 codes are scored but unreachable (audit report §2.2): JS trio, 3 LLM checks, `CITATIONS_ORPHANED`,
`CITATIONS_SOURCES_INACCESSIBLE`. They inflate apparent feature surface and (if ever wired wrong)
could dump large impacts.
- **Fix:** exclude PENDING-IMPL codes from the **active** score until their feature ships (R6-R8);
  correct the `_DEAD_CODE_ALLOWLIST` justifications in `test_class1_invariants.py:300-326` (the JS-trio
  and citation justifications are currently false).
- **AC:** `test_pending_impl_codes_excluded_from_score`; `test_dead_allowlist_justifications_accurate`
  (each allowlisted code either has a real emission path or is explicitly `pending_impl=True`).

### R2 [S] Apply the Phase 4 scoring value migration
20 impact/effort changes + 2 fixability corrections (`ORPHAN_PAGE`, `BROKEN_LINK_5XX`). Patch is in
`2026-07-03_scoring-change-plan.md`.
- **AC:** `test_issue_scoring_matches_change_plan` asserts each migrated `(impact, effort)`; update
  `docs/issue-codes.md` + `docs/thresholds.md`; parity tests stay green.

### R3 [S] Confidence × effect_size model migration (the calibration fix)
Only 62/151 codes have a confidence tier; impacts are 151 hand-set numbers. Adopt the two-axis model
(audit report §3.2): add `effect_size` to every `_IssueSpec`, extend `confidence_label` to all 151,
derive impact from the 3×3 matrix + `measured_effect` exception lane.
- **Fix resolves the 15 confidence-cap flags** in the change plan (e.g. `QUERY_COVERAGE_WEAK`,
  `SECTION_CROSS_REFERENCES`, `GEO_SUMMARY_BURIED`) by giving each an honest effect_size instead of
  force-capping.
- **AC:** `test_every_code_has_confidence_and_effect_size`; `test_impact_derived_from_matrix`
  (impact == f(confidence, effect_size, measured_effect)); `test_impact_within_confidence_cap_unless_measured`.

### R4 [S] Cluster suppression at aggregation time (fixes score inflation)
Audit report §2.3. Issues stay visible in the UI; each root cause charged once.
- Schema parent-suppress (or deprecate `SCHEMA_MISSING`); duplicate-metadata merge; not-in-text
  precedence (`RAW_HTML_JS_DEPENDENT` suppresses symptoms); thin-content pick-one; image-performance
  precedence; per-category page cap (~20) as backstop.
- **AC:** `test_schemaless_homepage_charged_once` (−7/−12 not −17); `test_duplicate_pair_not_triple_charged`
  (−6 not −15); `test_spa_homepage_not_stacked` (−6 not −20); `test_per_category_page_cap`.
  Dirty-state test (P8): re-aggregating an existing job applies suppression without double-counting.

### R5 [S] Effort = scope rubric, independent of fixability
Audit report §3.4 (revised). Keep both fields; define effort by work-size tiers (1 element → 4
infra); apply the 8 scope corrections in the change plan. Do **not** derive effort from fixability.
- **AC:** `test_effort_scope_rubric_documented`; `test_robots_codes_stay_low_effort` (developer_needed
  + effort 1 is valid, not a contradiction).

---

## P2 — Detection precision (Phase 1 findings)

### R6-pre [P] (grouped small precision fixes)
- **R2.1 `LINK_EMPTY_ANCHOR`** — add `aria-labelledby`, `<svg><title>`, anchor `title` recognition
  to `_find_empty_anchors` (`parser.py:880-914`). **Reuse, don't rebuild:** a correct labelled-element
  helper already exists in the same file at `parser.py:1254-1270` (it checks `aria-label`, `title`,
  `aria-labelledby`, child aria-label) — the anchor helper is the inconsistent one (P5: fix the
  pattern class-wide). **AC:** `test_svg_title_anchor_not_flagged`, `test_aria_labelledby_not_flagged`.
- **R2.2 `MIXED_CONTENT`** — split active (script/iframe/css — blocked) vs passive (img/media —
  auto-upgraded); score/report separately (`parser.py:766-792`, `security.py:40`). **AC:**
  `test_passive_mixed_content_lower_than_active`.
- **R2.3 Image stacking + LCP** — precedence so OVERSIZED/OVERSCALED suppress SLOW/COMPRESSION;
  identify + weight the LCP image (`image_analyzer.py:230-290`). **AC:** `test_one_bad_image_not_quadruple_charged`.
- **R2.4 `ORPHAN_PAGE`** — add a caveat in the finding for JS/query-driven listings (raw-HTML-only
  discovery, `cross_page.py:128`), pending a rendered-DOM link pass (ties to R7). **AC:**
  `test_orphan_finding_carries_dynamic_caveat`.
- **R2.5 Staging awareness** — production-domain heuristic that escalates `NOINDEX_*` /
  `AI_BOT_BLANKET_DISALLOW` as "possible leftover staging directive" (owner's SiteGround-cutover
  risk). **AC:** `test_noindex_on_production_domain_escalated`.
- **R2.6 Freshness page-type awareness** — extend `_PAGE_TYPE_CADENCE` to `CONTENT_STALE` +
  `CONTENT_STAT_OUTDATED` (currently flat; `issue_checker.py:333`, `ai_readiness.py:404`). **AC:**
  `test_evergreen_page_not_flagged_stale`.
- **R2.7 Unify AI-bot tables** — `parser.py:176 _AI_BOT_NAMES` (X-Robots) diverges from `AI_BOTS`
  and includes deprecated `anthropic-ai`. Derive both from `AI_BOTS`. **AC:** `test_single_ai_bot_source`.
- **R2.8 `ROBOTS_BLOCKED`** — add expected-disallow allow-list (cart/search/filter params) and
  crawl-vs-index wording (`engine.py:408`). **AC:** `test_expected_disallow_not_flagged`.

---

## P3 — Feature builds (owner chose "build, don't cut")

### R6 [F] Real citation model
Wire a citation/link parser into `PageCitations` so `CITATIONS_MISSING_SUBSTANTIAL_CONTENT`,
`CITATIONS_ORPHANED`, `CITATIONS_SOURCES_INACCESSIBLE` measure the actual page; implement the
source-accessibility HTTP check (currently `has_inaccessible_sources=False` TODO, `citation_model.py:97`).
Reuses R0.3 hardening for the accessibility fetches.
- **AC:** `test_citations_orphaned_fires_on_real_orphan`; `test_inaccessible_source_detected`
  (mock 404 source); adversarial: a well-cited page scores clean.

### R7 [F] Wire in the JS-render trio (Playwright)
`run_js_render_checks` (`js_renderer.py:138`) has no non-test caller. Wire it into the crawl behind
a `HAS_PLAYWRIGHT` guard; consume `JSRenderResult` into `JS_RENDERED_CONTENT_DIFFERS`,
`CONTENT_CLOAKING_DETECTED`, `UA_CONTENT_DIFFERS`. Requires Playwright + chromium in the Railway
container (Dockerfile change). Feeds R2.4 (rendered-DOM link discovery for orphans).
- **AC:** `test_js_render_issues_emitted_when_playwright_present`;
  `test_graceful_skip_when_playwright_absent` (no crash, no false negatives reported as clean).

### R8 [F] Implement the 3 LLM-driven checks
`CENTRAL_CLAIM_BURIED`, `CHUNKS_NOT_SELF_CONTAINED`, `PROMOTIONAL_CONTENT_INTERRUPTS` via an LLM
classifier on the existing Gemini/OpenAI integration (`ai_analyzer.py`). Follow
`~/.claude/standards/llm-integration.md` (timeout/retry/error-as-content guards, P14).
- **AC:** `test_llm_check_returns_structured_verdict`; `test_llm_error_not_rendered_as_finding` (P14);
  cost/latency budget documented per crawl.

---

## Phase 5 — Code-quality fixes (may land directly with tests, per governance)

### R-Q1 `make_issue` unknown-code handling
Docstring claims unknown codes get zeroes; `spec = _CATALOGUE[code]` raises `KeyError` first
(`registry.py`). **Fix:** raise a clear error (recommended) and match the docstring. **AC:**
`test_make_issue_unknown_code_raises_clear_error`.

### R-Q2 Stale docstring counts + parity
Module docstring says 131/49; actual 151/62. **Fix:** derive dynamically or add
`test_scoring_catalogue_parity` (`len(_ISSUE_SCORING)==len(_CATALOGUE)`; every scoring code has a
catalogue entry and vice versa).

### R-Q3 Confidence-label coverage test
**AC:** `test_every_ai_readiness_code_has_confidence_label` (and, post-R3, every code).

### R-Q4 Tidy `_AI_READINESS_CONFIDENCE` grouping
`SCHEMA_VISIBLE_MISMATCH` (Established) and `AI_MAIN_CONTENT_LOW_RATIO` (Heuristic) sit under the
"Reasonable proxy" comment. Cosmetic; move under correct headers.

### R-Q5 Report-only findings (no fix without approval)
- The `_DEAD_CODE_ALLOWLIST` false justifications (R1).
- `CONTENT_CLOAKING_DETECTED` invalid severity (R0.5).
- Any threshold constants that contradict `docs/thresholds.md` (to be swept during R3).

---

## Suggested execution order

1. **P0 (R0.1-R0.5)** — one PR, all correctness bugs + their tests. Immediate score-accuracy win.
2. **R-Q1-R-Q4** — code-quality PR (governance allows direct); unblocks safe refactors.
3. **R1 + R2 + R5** — scoring value migration + dead-code quarantine + effort rubric (one reviewed PR).
4. **R3** — the confidence×effect_size migration (larger; its own spec + PR).
5. **R4** — suppression rules (changes scores; needs dirty-state tests).
6. **R2.x precision fixes** — batched.
7. **R6 → R7 → R8** — feature builds, each its own spec, in ascending infra cost.

## What I could not verify (required list)
- The R3 3×3 matrix constants are provisional (audit report §3.6) — need a calibration pass over all
  151 codes to avoid mass score churn.
- Runtime score deltas from R4 suppression are estimated from impact sums, not measured on a real
  crawl of livingsystems.ca — validate against a live crawl before/after.
- R7 Playwright cost/latency on Railway is unmeasured.
- Non-AI-bot vendor facts beyond 302/FAQ (llms.txt lift, HowTo) were re-verified at the claim level,
  not re-benchmarked.
