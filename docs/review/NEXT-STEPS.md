# Audit remediation — remaining work (handoff / next-steps)

> **Purpose:** each remaining item is independent and best done in its **own fresh conversation**
> (token-efficient — no need to carry the whole audit history). Source of truth for scope +
> acceptance criteria is [`2026-07-03_remediation-plan.md`](2026-07-03_remediation-plan.md).
> Full findings: [`2026-07-03_code-audit-report.md`](2026-07-03_code-audit-report.md).
>
> **Done so far (on `main`):** P0 correctness bugs, Phase-5 code-quality, R1 dead-code, R2/R5 scoring
> migration, Path-A store parity, R4 cluster suppression, R3 structural caps, **R3 full Model-B
> calibration** (impact derived from `_CALIBRATION`, severity derived from impact, priority
> `impact×10−effort×6` + `quick_win`), and the `issueHelp.js` severity sync.
>
> **Standing rules (every item):** repo `CLAUDE.md` governance — features need a `docs/pending/`
> micro-spec first; tests-first; run `pytest tests/ -q` (only the 3 `test_usage_aggregation.py`
> failures are pre-existing/unrelated — ignore them); regenerate `docs/issue-codes.md` if the
> catalogue changes; commit + `git push origin main` per item. Scoring/impact is now **derived** via
> `registry.py:derive_impact()` — don't hand-edit `_ISSUE_SCORING`; change `_CALIBRATION` instead and
> let the parity test (`test_r3_calibration.py`) confirm.

---

## Queue (each = one fresh session; paste the prompt line to start)

### 1. R2.x — detection-precision fixes (batch)
**Why:** Phase-1 findings that improve accuracy (not scoring). All smallish + related → one session.
Items (audit report §Phase 1 + remediation R6-pre): `LINK_EMPTY_ANCHOR` accessible-name (reuse the
existing helper at `parser.py:1254-1270` — handles `aria-labelledby`/`title`/`<svg><title>`);
`MIXED_CONTENT` active vs passive split; image LCP/stacking precedence; `ORPHAN_PAGE` dynamic-listing
caveat; staging-vs-production awareness for `NOINDEX_*`/`AI_BOT_BLANKET_DISALLOW`; freshness page-type
awareness for `CONTENT_STALE`/`CONTENT_STAT_OUTDATED`; unify the AI-bot tables (`parser.py:176`
`_AI_BOT_NAMES` vs `ai_bots.py:AI_BOTS`); `ROBOTS_BLOCKED` expected-disallow allow-list.
**Paste to start:** *"Read docs/review/NEXT-STEPS.md item 1 and docs/review/OLD/2026-07-03_remediation-plan.md (R2.x / R6-pre). Implement the R2.x detection-precision fixes with tests, one micro-spec covering the batch. Don't change scoring."*

### 2. R6 — real citation parser
**Why:** the 3 citation codes are quarantined (fed hardcoded-empty data). Wire a real parser so
`CITATIONS_MISSING_SUBSTANTIAL_CONTENT` measures the actual page and `CITATIONS_ORPHANED` /
`CITATIONS_SOURCES_INACCESSIBLE` can fire. Re-enable the block in `issue_checker.py` (currently
`if False:` under the R0.1 quarantine) + implement the source-accessibility HTTP check
(`citation_model.py:97` TODO). Reuse the R0.3 retry hardening for accessibility fetches.
**Paste to start:** *"Read docs/review/NEXT-STEPS.md item 2. Implement R6: a real citation parser that un-quarantines the citation checks (issue_checker.py citation block) and the source-accessibility check (citation_model.py). Micro-spec first, then tests. Adversarial test: a well-cited page scores clean."*

### 3. R7 — wire in the JS-render trio (Playwright)
**Why:** `JS_RENDERED_CONTENT_DIFFERS`, `CONTENT_CLOAKING_DETECTED`, `UA_CONTENT_DIFFERS` are scored
but never emitted (`run_js_render_checks` has no non-test caller). Wire it into the crawl behind a
`HAS_PLAYWRIGHT` guard; consume `JSRenderResult` into issues. Needs Playwright + chromium in the
Railway container (Dockerfile). Feeds R2.x orphan rendered-DOM discovery.
**Paste to start:** *"Read docs/review/NEXT-STEPS.md item 3. Implement R7: wire api/services/js_renderer.py run_js_render_checks into the crawl behind a Playwright-available guard and emit the three codes; add the Dockerfile deps. Micro-spec first. Tests must cover graceful skip when Playwright absent."*

### 4. R8 — the 3 LLM-driven checks
**Why:** `CENTRAL_CLAIM_BURIED`, `CHUNKS_NOT_SELF_CONTAINED`, `PROMOTIONAL_CONTENT_INTERRUPTS` are
scored but unimplemented (need an LLM classifier). Build on the existing Gemini/OpenAI integration
(`ai_analyzer.py`); follow `~/.claude/standards/llm-integration.md` (timeout/retry, error-as-content
guard P14). Document per-crawl cost/latency.
**Paste to start:** *"Read docs/review/NEXT-STEPS.md item 4. Implement R8: the 3 LLM-driven GEO checks via an LLM classifier on the existing AI integration. Micro-spec first; tests must cover the error-as-content guard (P14) and a structured verdict."*

### 5. Deploy-gate — validation crawl of livingsystems.ca (before/after)  — MOSTLY DONE (V-series 2026-07-06)
**Why:** the whole R2/R3 recalibration + Path-A store parity should be validated on real data before
production deploy — scores will **rise** (intended correction). Run a crawl, capture site/page
HealthScores, sanity-check the distribution, and correlate against GSC (Authority Matrix) where
possible. No code change expected; produce a short before/after report in `docs/review/`.
**Status (2026-07-06, V-series):**
- V3 before/after crawl **DONE** — real full crawl (119 pages, max_pages=120): site health
  **73 → 88 (+15)**, warnings 453 → 166, info 477 → 764. Artifact:
  `docs/review/2026-07-06_full-crawl-before-after.md`
  (`scripts/before_after_healthscore.py`; tests `tests/test_before_after_report.py`).
- V2 `SCHEMA_VISIBLE_MISMATCH` flag from the 07-04 crawl — **confirmed FALSE POSITIVE** (WP SEO-plugin
  author-byline `Person` graph node, @id `…/#/schema/person/<hash>`). Detector fixed in
  `api/services/schema_typing.py` (`_is_author_publisher_node`), weight unchanged. Adversarial test
  `tests/test_schema_typing.py::test_visible_mismatch_no_fp_theme_schema`.
- V4 Authority-Matrix — logic + synthetic report **DONE** (`scripts/gsc_authority_matrix.py`,
  `tests/test_gsc_authority_matrix.py`, `docs/review/2026-07-06_gsc-authority-matrix.md`); the **LIVE
  run is BLOCKED-ON-CONNECTION** (owner must connect GSC via the Connections panel / `GET
  /api/gsc/connect` first, then re-run the script in that server process).
**Do NOT archive this file until V4's live run has been done.**

---

## Optional / lower priority
- **R3.4 — CLOSED (V1, 2026-07-06).** The extra scoring-time suppression clusters shipped under R5:
  the blanket-robots parent `AI_BOT_BLANKET_DISALLOW` suppresses its per-bot children
  (`AI_BOT_SEARCH_BLOCKED`, `AI_BOT_USER_FETCH_BLOCKED`, `ROBOTS_BLOCKED`, `AI_BOT_NO_AI_DIRECTIVES`)
  in `api/services/job_store_base.py:_CLUSTER_SUPPRESSION`, and `NOINDEX_*` scope-reduction is live
  (`_noindex_reduced_codes`, exempts security/redirect). Evidence: `tests/test_r5_clusters.py`
  (`test_cluster_suppresses_children[robots]`, `test_clusters_never_touch_security_redirect`, and the
  V1 case `test_v1_blanket_robots_suppresses_only_present_children`). No further work.
- **Pre-existing, unrelated:** the 3 `test_usage_aggregation.py` failures (billing/cost code) predate
  this audit — worth a separate look, not part of the scoring work.
