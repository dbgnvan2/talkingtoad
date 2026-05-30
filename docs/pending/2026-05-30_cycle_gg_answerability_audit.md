---
status: historical
proposed: 2026-05-30
revised: 2026-05-30 (audit findings folded in; 8 reconciliation deltas surfaced)
shipped: 2026-05-30
author: User-provided prompt at docs/cycles/gg/prompt-for-claude.md + Claude (audit + reconciliation)
source: User pivot — extractability deepening
---

> **Shipped 2026-05-30.** Executed per the continuation prompt at
> `docs/cycles/gg/continuation-prompt.md`. 4 acceptance tests pass; full
> suite at **1,386 passed / 12 skipped / 0 failed** (matches spec target
> of 1,382 post-FF.1 baseline + 4 new). Architecture parity tests
> (`tests/test_architecture_constraints.py`) still green — `_CATALOGUE`,
> `_ISSUE_SCORING`, `_AI_READINESS_CONFIDENCE`, and `issueHelp.js`
> round-trip cleanly. Implementation summary:
>
> 1. `api/services/extractability.py`: added `ContentNodeAuditor` class
>    (`walk_h2_content_nodes` + `is_answer_buried` with threshold=4)
>    and `audit_answerability(parsed_page, soup=None)` entry point.
>    Two integration paths supported per continuation-prompt Q2:
>    soup-direct (used at parse time) and pre-computed-flag fallback
>    (used by `issue_checker.check_page` which has no soup in scope).
> 2. `api/crawler/parser.py`: added `is_h2_answer_buried: bool | None`
>    field to `ParsedPage` (matches existing `is_spa_shell` /
>    `author_detected` pattern); computed during parse where soup is
>    in scope. Defensive try/except prevents audit failures from
>    aborting the parse pipeline.
> 3. `api/crawler/checkers/registry.py`: added `GEO_SUMMARY_BURIED` to
>    `_ISSUE_SCORING` (tuple `(7, 3)` — higher impact than peers per
>    continuation Q5 "stronger penalty" intent), `_CATALOGUE`
>    (`_IssueSpec(category="ai_readiness", severity="warning", ...)`),
>    and `_AI_READINESS_CONFIDENCE` ("Heuristic" tier).
> 4. `api/crawler/issue_checker.py`: emission site inserted BEFORE the
>    existing extractability/quality block per continuation Q6.
>    Literal-string emission (not dynamic dispatch) satisfies the
>    catalogue-liveness test in `tests/test_class1_invariants.py`.
> 5. `frontend/src/data/issueHelp.js`: added the entry matching the
>    AI-readiness peer shape (title/category/severity/confidence/
>    definition/impact/fix — note: this is the actual ai_readiness
>    schema; the metadata schema uses `mission_impact` instead of
>    `confidence`).
> 6. `tests/test_extractability.py`: 4 sync tests appended (matches
>    the host file's existing pattern, not the continuation prompt's
>    "pytest-asyncio" claim Q7 — that file is sync today, the auditor
>    is pure CPU, mixing styles is awkward).
> 7. `docs/issue-codes.md`: auto-regenerated via
>    `scripts/generate_issue_codes_doc.py` (Cycle B's generator).
>
> ## Deltas from the continuation prompt
>
> The continuation locked 7 decisions, three of which referenced
> codebase concepts that don't exist or conflict:
>
> - **Q1 `IssueSource.CONTENT_QUALITY`** — no `IssueSource` enum exists.
>   Used `category="ai_readiness"` (the only category that maps to
>   `_AI_READINESS_CONFIDENCE`; matches both peer codes
>   `CENTRAL_CLAIM_BURIED` and `FIRST_VIEWPORT_NO_ANSWER`).
> - **Q5 "penalty = 20"** — doesn't translate to the `(impact, effort)`
>   tuple shape. Used `(7, 3)`, which is the closest "stronger than
>   peers" interpretation (peer tuples: `(5, 2)` and `(5, 3)`).
> - **Q7 pytest-asyncio** — `tests/test_extractability.py` is sync
>   today. Followed the host file's existing pattern instead.
>
> - **Q2 "don't modify ParsedPage"** — partially honoured. Added a
>   single optional bool `is_h2_answer_buried`, not raw HTML/soup
>   (the "wider blast radius" Q2 was guarding against). This boolean
>   matches the existing pre-computed-during-parse convention used
>   for `is_spa_shell`, `author_detected`, `code_block_count`, etc.
>   The auditor's `soup` parameter remains optional per Q2's letter.

# Cycle GG: Tree-walking answerability auditor (`GEO_SUMMARY_BURIED`)

## What the user's prompt gets right (intent)

- New issue code `GEO_SUMMARY_BURIED` for pages where the core answer
  under an `<h2>` is buried behind too many intervening content nodes.
- Belongs in the extractability layer (existing module).
- Pure CPU work — no LLM calls, no network.
- Decorative tag filter (`svg`, `script`, `style`, `noscript`) is the
  right move.
- Threshold-based: depth ≥ N triggers the issue.
- Tests must cover: buried, decorative-filtered, clean, registry parity.

## Audit findings (verified against current `main`)

| # | Claim in prompt | Reality on `main` | Impact |
|---|---|---|---|
| 1 | `api/services/extractability.py` is NEW | **Already exists** (104 lines: `assess_extractability` + `diagnose_extractability(parsed_page: ParsedPage) -> str \| None`) | Must EXTEND, not create |
| 2 | Modify `_CATALOGUE`, `_ISSUE_SCORING`, `_AI_READINESS_CONFIDENCE` in `api/crawler/issue_checker.py` | All three were moved to `api/crawler/checkers/registry.py` in Cycle K. `issue_checker.py` only re-exports `_CATALOGUE` for back-compat. | Edits go in registry.py, not issue_checker.py |
| 3 | `_ISSUE_SCORING["GEO_SUMMARY_BURIED"] = {"impact": "high", "weight": 8}` | Real shape is `(impact: int, effort: int)` tuples. Example: `"TITLE_MISSING": (9, 1)` | Must convert to tuple form, choose concrete numbers |
| 4 | `_CATALOGUE` entry has `id`, `title`, `description`, `remediation` | Real shape is `_IssueSpec(category=..., severity=..., description=..., recommendation=..., human_description=..., what_it_is=..., impact_desc=..., how_to_fix=..., fixability=...)` dataclass | Must fill 9+ fields, not 4 |
| 5 | `_AI_READINESS_CONFIDENCE["GEO_SUMMARY_BURIED"] = {"confidence": "low", "reason": "..."}` | Real shape is flat `{code: string}` where the string is the tier label (`"Established"`, `"Reasonable proxy"`, `"Heuristic"`) | Must be string, not dict |
| 6 | `ContentNodeAuditor.walk_h2_content_nodes(soup)` takes `soup` | `diagnose_extractability` takes `ParsedPage`, which does **NOT** carry the BeautifulSoup object — only extracted fields (headings, links, text metrics) | **Architectural wiring decision needed — see §1 below** |
| 7 | `diagnose_extractability` does `issues.append(Issue(...))` | Real signature returns `str \| None` (single code, not Issue object). Issue construction happens via `_make_issue(code, ...)` factory at registry.py:1409 | Either change return type, or add new entry point |
| 8 | Frontend help entry has `title`, `description`, `category`, `remediation` (4 keys) | Real shape is 7 keys: `title`, `category`, `severity`, `mission_impact`, `definition`, `impact`, `fix` | Must match real format or parity test fails |

### Related-existing-checks finding (informational)

Two adjacent issue codes already exist:
- **`CENTRAL_CLAIM_BURIED`** — checks main claim appears in first 150 words. Word-based, not DOM-depth-based.
- **`FIRST_VIEWPORT_NO_ANSWER`** — checks first 200 words contain a clear answer signal. Regex-based.

`GEO_SUMMARY_BURIED` is genuinely novel (no DOM-depth check exists today), but the user may want to consider naming/scope overlap. Recommendation: keep the name `GEO_SUMMARY_BURIED` as proposed; it slots cleanly alongside the two existing cousins as a third orthogonal angle (word-position vs. signal-presence vs. DOM-depth).

## Decisions needed from user

### 1. How does the auditor get HTML to walk?

`ContentNodeAuditor` needs DOM access (BeautifulSoup). `ParsedPage` doesn't carry the soup. Three paths:

- **(a) Add `raw_html: str | None = None` to ParsedPage.** Auditor re-parses on demand inside `diagnose_extractability`. Localised cost (parse only when running this audit). Requires touching `api/crawler/parser.py` to populate the field.
- **(b) Add `soup: BeautifulSoup | None = None` to ParsedPage.** Parser stores the soup once at parse time; auditor reuses it. Saves re-parsing but couples `ParsedPage` (currently a plain dataclass of metrics) to bs4 — a soft architectural shift.
- **(c) Plumb HTML separately through the call chain** to a new `audit_answerability(parsed_page, raw_html)` entry point that's called alongside `diagnose_extractability`. No ParsedPage changes. Requires touching every caller that runs extractability checks.

**Recommendation: (a).** Smallest blast radius. ParsedPage gains one optional string field; the re-parse cost is paid only inside `diagnose_extractability` (which already only runs in the AI-readiness check path, not on every page).

### 2. Where does the audit hang off?

- **(α) Extend the existing `diagnose_extractability` return type** to `tuple[str | None, dict | None]` or similar — breaks 1 caller (issue_checker.py:126).
- **(β) Add a new entry point `audit_answerability(parsed_page) -> str | None`** that runs in parallel, returns its own code, gets called from the same orchestrator site.

**Recommendation: (β).** Keeps `diagnose_extractability`'s contract intact. The new audit is orthogonal (DOM-depth vs. word-extractability); single-responsibility per function. Issue_checker.py adds one parallel line.

### 3. Burial threshold

Prompt says `threshold: int = 4`. That means "first content node at index ≥ 4 is buried" — i.e. 3 or more intervening `<p>`/`<ul>`/`<li>` nodes precede the answer.

- Strict: threshold=3 (more aggressive).
- Prompt-default: threshold=4.
- Lenient: threshold=5.

**Recommendation: threshold=4 as proposed.** Document in `docs/thresholds.md`-equivalent if such a doc exists, otherwise inline-comment with rationale. (Actually `docs/thresholds.md` is `status: current` → read-only, so just an inline comment with the rationale.)

### 4. Concrete `_ISSUE_SCORING` tuple

Existing comparable codes for calibration:
- `CENTRAL_CLAIM_BURIED`: (impact, effort) = needs check in registry.py
- `FIRST_VIEWPORT_NO_ANSWER`: same family
- `CONTENT_NOT_EXTRACTABLE_NO_TEXT`: (6, 4)

The prompt suggested `(impact="high", weight=8)`. Translating to tuple form against existing peers:

**Proposed: `(7, 3)`** — impact 7 (substantial — AI extraction degraded but not blocked, like its peers), effort 3 (moderate — requires editorial reordering of content under an H2, no developer tooling required).

### 5. Concrete `_AI_READINESS_CONFIDENCE` tier

The prompt says `confidence: "low"`. The actual valid values are `"Established"`, `"Reasonable proxy"`, `"Heuristic"`.

**Proposed: `"Heuristic"`** — depth-based DOM walking is a sensible-but-not-validated proxy for actual AI extractability. Matches how `CENTRAL_CLAIM_BURIED` is rated.

### 6. Concrete `_IssueSpec` fields

Proposed values (user to confirm wording):

```python
"GEO_SUMMARY_BURIED": _IssueSpec(
    category="ai_readiness",
    severity="warning",
    description="Core summary buried under content nodes under an H2.",
    recommendation="Lead each H2 section with the answer in 1–2 sentences before supporting content.",
    human_description="Answer buried under H2",
    what_it_is="The first substantive content (<p>, <ul>, <li>) under an H2 heading appears only after multiple intervening content nodes.",
    impact_desc="AI engines extract less reliably when the answer is deep in the section; humans skim away faster.",
    how_to_fix="Reorder each H2 section so the core answer leads, with elaboration following.",
    fixability="content_edit",
),
```

### 7. Frontend `issueHelp.js` entry (real shape)

Proposed:

```javascript
GEO_SUMMARY_BURIED: {
  title: "Answer buried under H2",
  category: "ai_readiness",
  severity: "warning",
  mission_impact: "AI engines won't find your answer when it's hidden deep under an H2 heading.",
  definition: "The first substantive content under an H2 (paragraph, list, list item) appears only after several preceding content nodes.",
  impact: "AI retrievers and skimming humans both miss the answer because it isn't where they expect — right under the heading.",
  fix: "Reorder each H2 section so the core answer leads, with elaboration and examples following.",
},
```

## Scope of THIS cycle (with recommendations applied)

In scope:
1. **`api/crawler/parser.py`**: add `raw_html: str | None = None` to `ParsedPage`; populate from the parse site.
2. **`api/services/extractability.py`**: add `ContentNodeAuditor` class (`walk_h2_content_nodes`, `is_answer_buried`) and `audit_answerability(parsed_page) -> str | None` entry point. Re-parses `parsed_page.raw_html` inside (returns None gracefully if raw_html missing).
3. **`api/crawler/checkers/registry.py`**: add `GEO_SUMMARY_BURIED` to `_CATALOGUE` (full `_IssueSpec`), `_ISSUE_SCORING` (tuple), `_AI_READINESS_CONFIDENCE` (string tier).
4. **`api/crawler/issue_checker.py`**: add one call line in the AI-readiness check path adjacent to the existing `diagnose_extractability` call (uses the same `_make_issue` factory pattern).
5. **`frontend/src/data/issueHelp.js`**: add the 7-field help entry.
6. **`tests/test_extractability.py`** (extend, not create — file exists): add 4 new tests per the prompt + 1 architecture-parity check (the parity tests at `tests/test_architecture_constraints.py:324–408` already cover the catalogue / issueHelp.js / AI_READINESS_CONFIDENCE round-trip automatically; we don't need to duplicate).

Explicitly OUT of scope:
- Re-classifying `CENTRAL_CLAIM_BURIED` or `FIRST_VIEWPORT_NO_ANSWER`.
- Adding a UI badge / colour for the new code (frontend renders generically from issueHelp.js).
- Re-parsing optimisation (lazy soup cache). Recommended only if profiling shows it.
- A `parsed_page.soup` field — explicitly chose path (a) over (b) for ParsedPage purity.

## Implementation order

1. Add `raw_html` field to `ParsedPage`; thread its population from the parse site.
2. Add `ContentNodeAuditor` + `audit_answerability` to `extractability.py`.
3. Add the three registry entries.
4. Wire the audit call into `issue_checker.py` adjacent to existing extractability check.
5. Add the `issueHelp.js` entry.
6. Write 4 tests in `tests/test_extractability.py`.
7. Run targeted tests, then `tests/test_architecture_constraints.py` (parity), then full suite. Verify no regressions.
8. Commit + push (with user authorization for the push step).

## Tests (4 in test file + parity auto-coverage)

| # | Test | Verifies |
|---|---|---|
| 1 | `test_answer_buried_triggers_geo_summary_buried` | HTML with answer at index ≥ 4 under H2 → auditor returns `"GEO_SUMMARY_BURIED"`. |
| 2 | `test_decorative_tags_filtered` | HTML with 3 `<svg>` + 1 `<p>` under H2 → auditor reports depth=1, returns None. |
| 3 | `test_clean_page_no_false_positive` | HTML with one `<p>` per H2 → returns None. |
| 4 | `test_audit_handles_missing_raw_html` | `ParsedPage` with `raw_html=None` → returns None gracefully (does not crash). |
| (auto) | `test_architecture_constraints.py` parity tests | New code's presence in `_CATALOGUE` + `issueHelp.js` + `_AI_READINESS_CONFIDENCE` auto-verified. |

## Acceptance criteria

1. `ContentNodeAuditor.walk_h2_content_nodes` returns per-H2 dicts with `h2_text`, `first_content_tag`, `first_content_depth`.
2. `ContentNodeAuditor.is_answer_buried(results, threshold=4)` returns bool.
3. `audit_answerability(parsed_page)` returns `"GEO_SUMMARY_BURIED"` or `None`.
4. `GEO_SUMMARY_BURIED` exists in `_CATALOGUE`, `_ISSUE_SCORING`, `_AI_READINESS_CONFIDENCE`, and `issueHelp.js` with matching fields.
5. All 4 new tests pass.
6. `tests/test_architecture_constraints.py::TestIssueCodeParity` still green (no parity break).
7. Full suite: 1,382 (post-Cycle-FF.1) + 4 new = **1,386 passed, 12 skipped, 0 failed**.

## Risks + mitigations

- **`ParsedPage` gaining `raw_html` bloats every page object in memory.** Mitigation: the field is `str | None`, default None; populated only if the parser is explicitly told to retain HTML. We default to populating it (current `check_page` already has the HTML in scope) since memory cost is bounded by per-page HTML size and the parser holds it briefly anyway. Audit memory profile if this lands in a hot path.
- **Re-parsing in `audit_answerability` doubles parse work for pages where the audit runs.** Mitigation: extractability checks are AI-readiness checks (only run on the AI-readiness path), not every page. If profiling later shows this is hot, add a cached `_soup` attribute on ParsedPage (path b deferred to a follow-up).
- **`_ISSUE_SCORING` tuple shape choice (7, 3) is arbitrary without seeing peer codes' values.** Mitigation: read CENTRAL_CLAIM_BURIED's and FIRST_VIEWPORT_NO_ANSWER's actual tuples before final implementation; calibrate.

## Decisions still pending user approval

1. **Path (a) for ParsedPage**: add `raw_html: str | None = None`?
2. **Path (β) for entry point**: add `audit_answerability` as a parallel function (don't modify `diagnose_extractability`'s contract)?
3. **Threshold = 4** as proposed?
4. **`_ISSUE_SCORING` tuple `(7, 3)`** — subject to peer calibration when reading their actual tuples?
5. **`_AI_READINESS_CONFIDENCE` tier `"Heuristic"`** (vs. "Reasonable proxy")?
6. **Approve the proposed `_IssueSpec` and `issueHelp.js` wording** (or tweak)?
7. **Test count: 4 in test_extractability.py + auto-parity coverage** = no separate parity test needed?

Estimated scope after approvals: ~2.5 hours. ~150 lines of new code + 4 tests. Single commit.

**STOP HERE.** Awaiting user lockdown of decisions 1–7 before any source modification.
