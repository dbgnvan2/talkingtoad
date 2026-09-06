# QA Gate — v2 audit spec r5 (the four owner decisions, be32330)

**Gate date:** 2026-09-06
**Range:** `origin/main..HEAD` = `be32330` (1 commit, docs only):
  `be32330` docs(spec): r5 — the four open decisions, answered by the owner
**Gate type:** independent (Hermes, fresh context — no agent verifies its own work)
**Scope:** documentation-only batch — `docs/pending/2026-09-06_v2-audit-implementation.md` (r5 revision) and `TODO.md`. No source code changed. The useful question is forward: if an implementer built exactly what the spec now says, would the result be correct, and does the spec claim anything about the codebase that is not true?
**Verdict: APPROVED** — no blocking findings. Each of the four decisions was checked against the real code at a named line; every codebase claim the r5 text rests on verified true; the specified acceptance tests are implementable and would fail against the opposite behaviour; both suites green at HEAD; workflow compliance clean.

## Paste-ready verdict block for Claude Code

```
QA GATE — v2 audit spec r5 (be32330, docs-only): APPROVED, no blocking
findings. Nothing to fix before pushing. The four owner decisions were
verified against the code, not taken on the commit message's word:

1. LOW_INBOUND_LINKS ungated on archives_skipped — premise true. The
   link_graph_complete gate it mirrors is real: check_cross_page.py:196
   `if link_graph_complete:` wraps _check_orphan_pages, engine.py:1679
   sets link_graph_complete=(orphan_status == "complete") with
   orphan_status in {skipped_single_page, skipped_partial_scan,
   skipped_truncated, complete} (engine.py:1644-1652). ORPHAN_PAGE today
   is disclosed-not-gated on archives (engine.py:1663-1667 comment says
   exactly this; coverage_notes.py:33-43 emits the caveat on "complete").
   Self-link exclusion to mirror: cross_page.py:246-249.
2. IMG_MISSING_DIMENSIONS counts decorative images + decorative_count —
   signals true. parser.py:1773-1778 stores rendered_width/rendered_height
   (via _parse_dimension: None for missing/empty/unparseable, "100px"->100,
   parser.py:1883-1900) and is_decorative; _detect_decorative matches the
   spec's four signals verbatim (role="presentation", aria-hidden="true",
   alt="" only — no size guard, so an alt="" full-width hero IS marked
   decorative, parser.py:1796-1819), <32px both dims via its own
   int(tag.get("width", 999)). The P32 incident the rationale cites is on
   record: docs/audit/2026-08-30_full-check-audit.md (156 -> 0),
   docs/pending/2026-08-30_alt-empty-vs-missing.md, fix commit 4890d71 —
   whose own diff narrates the "adversarial (P7)"-headed test asserting the
   implementation's answer (== 1) until 2026-08-30. Mixed-fixture test
   asserting count AND decorative_count is implementable; a count-only
   implementation would indeed pass a suppressor (the test spec is sound).
3. Codes 3/4 over all pages — mechanism claim true. _check_entity_values
   (cross_page.py:664) prefers the start-URL page (682-683), falls back to
   candidates[0] over node-carrying pages only when no start match
   (684-687); a homepage that carries no entity node therefore yields a rep
   with no nodes and the checks silently no-op — verified. Existing
   ENTITY_* codes sit in the same function (ENTITY_VALUE_PLACEHOLDER 694,
   ENTITY_HOURS_DEFAULT 706, ENTITY_FIELD_EMPTY 718, ENTITY_NAP_INCOMPLETE
   725), so the "do not silently widen" constraint and criterion 18's
   before/after requirement are real, not precautionary.
4. Evidence tier into PDF/Excel for every category — surfaces true. Drawer:
   IssueHelpPanel.jsx renders data-testid="help-confidence" from
   issueHelp.json (via the issueHelp.js loader), confidence populated for
   all 170 codes (verified: 170/170, 0 absent). PDF: report_generator.py
   renders "Evidence: {confidence_label}" gated ONLY on
   `if first.confidence_label:` (1637-1648) — no category check, so a label
   supplied to any code renders everywhere. Excel: Confidence column exists
   only on the AI Readiness sheet (excel_generator.py:153-168, filtered to
   category ai_readiness). _AI_READINESS_CONFIDENCE: 75 entries, exactly
   the 75 ai_readiness codes (no foreign keys, none missing — verified by
   script). make_issue("IMG_ALT_MISSING").confidence_label is None,
   ENTITY_NAP_INCOMPLETE's is "Established", ENTITY_HOURS_DEFAULT's is
   "Heuristic" — all as the spec states. The ENTITY_HOURS_DEFAULT drawer
   drift story is documented in tests/test_confidence_help_parity.py:10-17,
   and its reader skips absent confidence fields (line 40) exactly as the
   spec warns. Do NOT add the three non-ai codes to the dict:
   test_confidence_entries_only_for_ai_readiness_category
   (test_architecture_constraints.py:514) goes red.

Evidence (re-run at HEAD):
- backend: ./venv/bin/python -m pytest tests/ -p no:cacheprovider
  --tb=short -q -> 5554 passed, 1 skipped, 2 deselected, 177.47s, exit 0.
- frontend: cd frontend && npx vitest run -> 396 passed / 50 files.
- eslint: N/A — no js/jsx files in this commit (two .md files only).
- static scan over added lines: nothing (docs only).
- workflow: single unpushed commit = pending-spec doc (allowed); clean
  tree; TODO.md Parked header (4) matches its four bullets; functional
  spec/thresholds untouched (correct — no implementation yet, no numeric
  bounds changed).

Non-blocking observations (none change the verdict):
- spec §1.4: "shallowest is its docstring" — the word is in the inline
  comment at cross_page.py:679-680, not the function docstring (665-670,
  which says "the homepage where possible"). Substance unaffected.
- spec §1.2 attributes both-direction ai-only enforcement to
  test_confidence_entries_only_for_ai_readiness_category; the reverse
  direction (every ai code labelled) is enforced by
  test_every_ai_readiness_code_has_confidence_label
  (test_architecture_constraints.py:430). Two tests, one name.
- pre-existing (untouched by r5): spec §1.5 says "cafdf6e, two commits
  before this spec landed" — cafdf6e is the direct parent of the spec-set
  commit 47f7f09 (verified via rev-parse), i.e. one commit before.
- commit message calls the CLS reconciliation a "new parked item"; it
  pre-existed (unchanged context in the diff). Only the skip_wp_archives
  item is new. 5 -> 4 count is correct.
- report_generator.py:1637's comment "(AI Readiness issues)" is stale vs
  its generic gate — helps criterion 17, no action needed.
```

## Evidence table

| Check | Command | Result |
|---|---|---|
| Range + tree state | `git log origin/main..HEAD --oneline`; `git status --short` | 1 commit (be32330); clean tree; unpushed = pending-spec doc only |
| Commit contents | `git show be32330 --stat` | TODO.md (25 lines changed), docs/pending/2026-09-06_v2-audit-implementation.md (63 lines) — docs only |
| Decision 1 gate premise | read cross_page.py:55-57, 190-199, 214-269; engine.py:1644-1683 | `if link_graph_complete:` at 196; engine sets `link_graph_complete=(orphan_status == "complete")` at 1679; statuses exactly as spec lists; self-link dropped at 246-249; archives disclosed-not-gated (engine comment 1663-1667; coverage_notes.py:33-43) |
| Decision 2 parser signals | read parser.py:1767-1781, 1786-1821, 1883-1900 | rendered_width/rendered_height + is_decorative per image; _parse_dimension None for missing/empty/unparseable, "100px"→100; is_decorative = role=presentation, aria-hidden="true", alt="" (no size guard), <32px both dims |
| Decision 2 incident on record | grep 156/IMG_ALT_MISSING; git show 4890d71 | docs/audit/2026-08-30_full-check-audit.md:151 (156→0), docs/pending/2026-08-30_alt-empty-vs-missing.md; 4890d71 diff narrates the adversarial-headed test that pinned the implementation's answer |
| Decision 3 rep mechanism | read cross_page.py:664-733 | start-URL page preferred (682-683); fallback candidates[0] over node-carrying pages only when no start match (684-687); ENTITY_* emissions at 694-731; homepage-without-node → silent no-op confirmed |
| Decision 4 dict/tests | script run (PYTHONPATH=$PWD venv python) | catalogue 170 (75 ai_readiness); _AI_READINESS_CONFIDENCE 75 keys, zero non-ai keys, zero missing ai codes; ENTITY_NAP_INCOMPLETE=Established, ENTITY_HOURS_DEFAULT=Heuristic, IMG_ALT_MISSING label None; issueHelp.json 170 codes, 0 without confidence |
| Decision 4 export surfaces | read report_generator.py:1637-1648; excel_generator.py:122-168 | PDF "Evidence: {label}" gated on `if first.confidence_label:` only; Excel Confidence column on AI Readiness sheet only (category-filtered) |
| Decision 4 parity test | read tests/test_confidence_help_parity.py | reader skips absent confidence (line 40); drift story + three named codes at 10-17, 67-72 |
| Drawer | read IssueHelpPanel.jsx:1-33; issueHelp.js:1-30; AIReadinessPanel.jsx:261 | data-testid="help-confidence" renders help.confidence; issueHelp.js is a loader over issueHelp.json (single authored source) |
| Criterion numbering | grep "criterion [0-9]" in spec | only cross-ref is 17→12, consistent post-renumber |
| Backend suite | `./venv/bin/python -m pytest tests/ -p no:cacheprovider --tb=short -q` | **5554 passed, 1 skipped, 2 deselected**, 177.47s, exit 0 |
| Frontend suite | `cd frontend && npx vitest run` | **396 passed / 50 files**, 5.52s |
| Lint changed files | n/a | no js/jsx files changed (both files .md) |
| Static scan | `git show be32330` added lines grepped for secrets/os.system/shell/eval/exec/pickle/SQL | clean — docs-only diff |
| TODO.md coherence | read TODO.md:361-380 | Parked header "(4)" matches 4 bullets; skip_wp_archives new, CLS/TOCTOU/Playwright retained |

## Decision-by-decision forward check (would an implementer building this be correct?)

1. **LOW_INBOUND_LINKS, no archives gate.** The spec's stated acceptance test — the check fires on a crawl with `skip_wp_archives=True` — is implementable: the checker runs inside the existing `link_graph_complete` block and receives the same link graph ORPHAN_PAGE uses; archives-skipped affects graph composition but not the gate. The admitted noise (a page whose only second link lives on a skipped archive reads as one-inbound) is exactly ORPHAN_PAGE's disclosed-caveat class, and the spec requires the same disclosure naming archives (§1.5, criterion 16, coverage_notes extension). Internally coherent; consistent with the "adjacent" skip-default question now parked in TODO.
2. **IMG_MISSING_DIMENSIONS counts decorative.** The OR-condition over the two existing parser fields is buildable with zero new parser signals; `decorative_count` is derivable from the same records' `is_decorative`. The mixed-fixture adversarial (count=5, decorative_count=3) cannot pass a suppressor that drops the class, and the half-declared/`width="100px" height="60"` cases behave as specified under `_parse_dimension`. No third reading of the attributes is created — the agreement-test rule is respected by construction.
3. **Codes 3/4 over all pages.** Buildable inside `_check_entity_values`; found_on/found-once/dedup-by-node semantics are precise and testable with the specified fixtures. The constraint that existing ENTITY_* behaviour not be silently widened is real because the per-node check helpers (`_check_nap`, `_check_default_hours`) are page-parameterised and shared — an implementer ranging over all pages must decide per-code, which criterion 18's before/after surface requirement forces into the open.
4. **Evidence tier everywhere from one source.** Both routes the spec offers are code-real: route 2 (report/excel read `api/services/issue_help_data.py`, generated from issueHelp.json with a sync test — loader chain verified) is the minimal change; route 1 (promote to a registry-derived value) must keep `_AI_READINESS_CONFIDENCE` ai-readiness-only as a view or the two constraint tests turn red — the spec says exactly this. Note for the implementer: whichever route, the ai codes' export label then also lives in the dict, so `test_confidence_help_parity.py`'s extension to the export surface is load-bearing, not optional — the spec makes it a criterion-17 requirement. Excel needs the Confidence column added beyond the AI Readiness sheet; PDF already renders generically.

## Non-blocking observations

1. Spec §1.4: "shallowest is its docstring" — the word sits in the comment at cross_page.py:679-680, not the function docstring (665-670). The substantive claim (candidates[0] first-in-list; silent no-op when the homepage carries no node) is accurate.
2. Spec §1.2: "enforced in both directions by test_confidence_entries_only_for_ai_readiness_category" — that test enforces one direction; the other is test_every_ai_readiness_code_has_confidence_label (test_architecture_constraints.py:430). Costless to fix in a later revision.
3. Pre-existing (untouched by r5, flagged because this gate checks doc truth): spec §1.5 says "cafdf6e, two commits before this spec landed" — cafdf6e is the direct parent of the spec-set commit 47f7f09 (verified by rev-parse). Off by one.
4. Commit message: "Two new parked items in their place — … and the CLS reconciliation." The CLS item pre-existed; only skip_wp_archives is new. Counts (5→4) are right.
5. report_generator.py:1637 comment "(AI Readiness issues)" is stale relative to its category-agnostic `if first.confidence_label:` gate — benign, and convenient for criterion 17.

## State

- Tree clean at HEAD (be32330); only unpushed commit is the pending-spec doc itself (allowed — awaiting approval/implementation).
- Spec still pending (correct: implementation has not happened; folding is a completion-time step). thresholds.md/functional-specification.md untouched — correct for a pre-implementation revision.
- This gate file is written but not committed (repo convention: gate files ride the next push).
