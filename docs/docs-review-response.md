# Docs Review Response — Triage & Remediation Plan

> **Companion document to** the external docs-folder review register
> ("TalkingToad — Documentation & Defect Review Register").
>
> **Purpose:** Triage every finding in the review against the current
> codebase, mark verified status, and propose concrete remediation. This
> doc is the QA-reviewer-friendly summary of "what's already fixed, what
> still needs work, and what decisions remain."
>
> **Last verified:** 2026-05-27 against `main` commit `8b5ada0`.

---

## Executive summary

| Section | Items | Already fixed | Still open | Needs decision |
|---|---|---|---|---|
| 1. Code defects (P1–P3) | 12 | 8 | 4 (frontend) | 0 |
| 2. Self-flagged weak checks | 7 | 0 | 7 | 1 (rename) |
| 3. GEO scoring buffer bugs (F1–F10) | 10 | TBD | TBD | 0 |
| 4. Unresolved contradictions | 6 | 1 (#3 deployment) | 5 | 6 |
| 5. Doc defects | 5 | 2 (broken paths, version drift partial) | 3 | 0 |
| 6. Class-1 invariants | 7 | 4 partially covered by tests | 3 | 0 |
| 7. Doc improvements | 7 | 1 (broken paths) | 6 | 0 |

**Headline:** the foundational P1 data-corruption risks called out in the
review (#2 parser tree mutation, #5 apply_fix empty-write) are **already
fixed in code**. Most of Section 1 is either fixed or addressable in
small focused commits. Sections 2 and 3 require deeper verification.

---

## Section 1 — Code defects: verified status

Each item below was verified against the current source on `main`.

### ✅ #1 NOINDEX_HEADER (originally P2)

**Status:** Fixed. `ParsedPage.robots_source` field exists (`parser.py:90`),
is populated correctly from headers (`parser.py:178, 224`), and the check
at `issue_checker.py:2224` uses `page.robots_source == "header"` to
distinguish header-set noindex from meta. No action needed.

### ✅ #2 Parser tree mutation — P1 data-corruption (originally P1)

**Status:** Fixed. `parser.py:511` uses `copy.deepcopy(body)` before
calling `.decompose()`, preserving the shared soup tree. The correlated
failure (links/headings/word-count corrupted together) cannot occur.
**Recommend:** add a regression test that parses a known fixture, runs
all extractors, and asserts no cross-contamination — this protects
against a future copy.copy revert. See Section 6 #1 below.

### ✅ #3 URL_HAS_SPACES on `+` (originally P2)

**Status:** Fixed. Current `check_url_structure` (`issue_checker.py:2451`)
only tests `if "%20" in urlparse(url).path` — scoped to path, no `+`
check. No false-positive on query strings with `+`.

### ✅ #4 CANONICAL_SELF_MISSING double-fire (originally P2)

**Status:** Fixed. `issue_checker.py:1568` has an explicit guard:
`if page.canonical_url is None and not any(i.code == "CANONICAL_MISSING" for i in issues)`.
The two issues cannot both fire on the same page.

### ✅ #5 apply_fix empty value — P1 data-destruction (originally P1)

**Status:** Fixed. `wp_fixer.py:406-408`:

```python
# Guard: never write an empty string to a text field — it would silently clear live content
if field != "indexable" and not proposed.strip():
    return False, "Proposed value is empty — edit the fix before applying"
```

The whitespace-stripped guard catches both `""` and `" "` cases.
**Recommend:** add an explicit test case `test_apply_fix_rejects_empty_proposed`
to lock this behaviour in. See remediation plan below.

### ✅ #6 Dead help entries (originally P3)

**Status:** Fixed. `grep` confirms `PAGE_TOO_LARGE`, `NO_VIEWPORT_META`,
`NO_SCHEMA`, and `EXCESSIVE_EXTERNAL_DEPS` are not present in
`issueHelp.js`. The architecture parity test
(`test_architecture_constraints.py::TestIssueCodeParity`) enforces this
going forward.

### 🟡 #7 FixManager — no confirm on Clear/Apply (originally P2)

**Status:** Not yet fixed in code; needs UI dialog. **Blocked** on
`feature/multi-page-geo` branch merge (the branch has uncommitted
changes to `FixManager.jsx`). Tracked in plan as v2.7 M10 item — to be
addressed when the toast/dialog notification system lands.

### 🟡 #8 FixManager initial load swallows errors (originally P2)

**Status:** Not yet fixed. Same blocker as #7. Add error-banner UI as
part of the v2.7 toast system work.

### 🟡 #9 FixManager apiFetch no timeout (originally P3)

**Status:** Not yet fixed. The `apiFetch` helper in
`frontend/src/api.js` doesn't set an `AbortController` timeout.
Recommend: add a default 60s timeout configurable per-call. Small
focused commit, can land independently of the branch merge.

### 🟡 #10 CSV export silent failures (originally P3)

**Status:** Not yet fixed. Same blocker as #7. Will fold into the v2.7
toast system migration.

### ✅ #11 IMG_OVERSIZED tests (originally P2)

**Status:** Fixed. Four tests at `test_issue_checker.py:1396`, `1401`,
`1406`, `1411` cover positive/negative/configured-threshold cases.

### ✅ #12 docs/overview.md stale threshold (originally P3)

**Status:** Fixed. `overview.md:137` says 300 KB, matches code constant
`_DEFAULT_PAGE_SIZE_LIMIT_KB = 300` at `issue_checker.py:1436`.

---

## Section 2 — Self-flagged weak checks (need triage decisions)

These checks are documented as low-reliability. For each:
**Recommendation = Keep / Gate / Fix-scope / Remove**.

| Check | Reviewer's concern | Recommendation | Justification |
|---|---|---|---|
| `ORPHAN_CLAIM_TECHNICAL` | `_count_orphan_claims()` is a stub | **Remove from `_CATALOGUE`** (mark as v3.0 candidate) | Stub code that never fires is worse than no code — it gives the impression a check exists. Remove the catalogue entry and `issueHelp.js` entry; document in v3.0 plan as "future work." |
| `STATISTICS_COUNT_LOW` | Only scans first ~150 words + unbounded heading text | **Fix scope** | Extend scan to body content (first 600 words). Heading text exclusion is a real adversarial concern — fix that in the same PR. M0.9 P6 area. |
| `CHUNKS_NOT_SELF_CONTAINED` | Silently tests only first 8 sections | **Gate behind config flag** + surface the 8-section limit in the issue text | Already a Heuristic-tier check. Make the limit explicit in `extra.sections_checked`; add a config knob `passage_heuristic_section_cap`. |
| `CONTENT_CLOAKING_DETECTED` | Silently absent when Playwright missing → score inflation | **Gate behind config + emit `CHECK_SKIPPED_NO_PLAYWRIGHT`** | Critical correctness issue. Without Playwright, this check cannot run; instead of silently dropping it from the denominator, emit an explicit skip and adjust the score appropriately (or skip the score entirely for that page). |
| `PROMOTIONAL_CONTENT_INTERRUPTS` | LLM sees only first ~300 chars/section | **Fix scope** to 1500 chars/section | Trivially fixable; current limit creates frequent false negatives. |
| `QUERY_MATCH_SCORE` | Denominator is LLM-returned count, unvalidated | **Validate LLM output** | Add a sanity-check assertion that the LLM returned ~7 queries (configurable expected count); fail loudly if not. |
| `SEMANTIC_DENSITY_LOW` | Jargon name; underlying check is OK | **Rename deferred**, document the rename plan | Renaming breaks stored issues. Plan a one-shot rename in v3.0 with a migration script that updates stored `issue_code` values. Until then, keep the name and add an alias in `issueHelp.js`. |

**Recommended single PR:** "v2.x M0.13 — weak-check triage." Each
sub-item above is a small focused commit:
- Remove `ORPHAN_CLAIM_TECHNICAL`
- Fix `STATISTICS_COUNT_LOW` scope
- Gate `CHUNKS_NOT_SELF_CONTAINED` behind config + surface limit
- Add `CHECK_SKIPPED_NO_PLAYWRIGHT` skip-marker emission
- Fix `PROMOTIONAL_CONTENT_INTERRUPTS` scope
- Add LLM-output validation for `QUERY_MATCH_SCORE`
- Defer rename, document plan

---

## Section 3 — GEO scoring buffer bugs (F1–F10)

These all stem from one root cause: multiple text-buffer extractions
with different scopes (`first_150_words` vs `first_200_words` vs char
limits) and no enforced agreement.

**Recommended structural fix instead of per-bug fixes:**

Introduce a single `PageContentSpans` dataclass that pre-computes all
the slice buffers once (`first_N_words`, `first_M_chars`, full body,
intro), with explicit names that match what they contain. Every GEO
check reads from this dataclass. The buffer-agreement bugs (F1, F2, F7,
F8) become impossible by construction.

**Verification needed before fixing:**

I need to read `geo_analyzer.py` and the scoring map to know which of
F1–F10 are still present vs already addressed by the GEO implementation
plans. Tracked as remediation step "Section 3 verification".

---

## Section 4 — Unresolved contradictions — recommended decisions

For each, my recommendation (since the user asked me to proceed on
ambiguity without asking):

### 4.1 `first_150_words` → `first_200_words` rename

**Recommend:** Keep the name; document in code that the actual scope is
200 words. Per the contradicting plan, renaming touches 20+ call sites
with cascading test changes. The risk/reward is poor — confusion is
solved by a one-line module docstring saying "buffer name is historical;
actual extraction is 200 words." When the structural refactor (Section 3
recommendation) lands, the named-spans approach replaces this entirely.

### 4.2 WordPress credential file schema

**Recommend:** Pick the **cookie-based shape** that's actually in the code:
`{ site_url, login_url, username, password }` (this is what
`WPClient.from_credentials_file` reads). Update `wordpress-integration/README.md`
and `architecture.md` to match. The "Application Password" variant is
aspirational; document it as a v3.0 roadmap item if you want to support it.

### 4.3 Deployment model (Vercel-only vs Vercel+Railway)

**Already resolved.** v2.3 M0.7 (`deployment-railway.md`) is the
canonical guide. Mark `overview.md`, `architecture.md` "Vercel
Deployment" sections, and the v1.4 spec deployment section as
`status: superseded-by deployment-railway.md`. Add the status banner;
don't delete (history matters).

### 4.4 `URL_TOO_LONG` threshold (115 vs 200 chars)

**Recommend:** Verify the current code value, then update all docs to
match. Industry consensus is ~115 chars (Google still indexes longer,
but UX suffers and they may truncate in SERPs). Suggested: **115 chars**
to align with the v1.5-extensions spec which is the most recent.

### 4.5 `FIRST_VIEWPORT_NO_ANSWER` window (150 vs 200 words)

**Recommend:** **200 words**, since that's also what `first_200_words`
actually extracts (per F1). Aligning the rule with the implementation
eliminates one named contradiction.

### 4.6 Alt-text issue taxonomy

**Recommend:** Use the **split codes** (`IMG_ALT_TOO_SHORT`,
`_TOO_LONG`, `_GENERIC`, `_DUP_FILENAME`) — that's what
`_CATALOGUE` actually has and what `frontend/src/data/issueHelp.js`
references. Mark the single `IMG_ALT_QUALITY` in `image-scan-spec.md`
as superseded; update the spec.

---

## Section 5 — Documentation defects

### 5.1 Broken links in `specs/README.md` and sub-READMEs

**Status:** Still open. M0.10 fixed `docs/README.md` but the spec
sub-READMEs still have broken relative paths. **Action:** sweep + fix
the four files (`specs/README.md`, `specs/core-crawler/README.md`,
`specs/image-analysis/README.md`, `specs/ai-readiness/README.md`,
`specs/wordpress-integration/README.md`). Small focused commit.

### 5.2 Three different line counts across `REVIEW.md`, `REVIEW_SPEC.md`, `REMEDIATION_STATUS.md`

**Status:** Partially addressed — `CLAUDE.md` is current. The three
review docs are now historical. **Action:** add a "Status: superseded"
banner to `REVIEW.md` (dated 2024 — likely 2026 typo, mark superseded)
and `REVIEW_SPEC.md` (mostly satisfied by v2.x work). Update the dates.

### 5.3 Version string drift (1.4 / 1.8 / 1.9.1 / 2.3)

**Status:** Partially fixed (M0.1). `/api/health`, `CLAUDE.md`, and
`docs/README.md` now all say 2.3. **Remaining:** `api.md` says 1.9.1
in its preamble, v1.4 spec says 1.4 (correct — it's a historical spec),
`specs/README.md` says "v1.9.1". **Action:** sweep + bring all
non-historical docs to 2.3.

### 5.4 Image specs labelled v2.0 under v1.9 filenames

**Status:** Still open. **Action:** decide which version is canonical
(probably v1.9.1 since that's what shipped), rename file or fix title,
fix the duplicate `## 7` section number.

### 5.5 Hand-maintained `issue-codes.md`

**Status:** Still open. **Action:** This is exactly what Section 7 #1
addresses. See the recommendation below.

---

## Section 6 — Class-1 foundational invariants

The reviewer correctly identifies these as "if any is broken, everything
downstream is suspect." Current test coverage:

| Invariant | Has tests? | Recommendation |
|---|---|---|
| 1. Parser tree integrity | ⚠️ Partial — `test_parser.py` covers individual extractors but not the no-mutation invariant | **Add** `test_parser_extractors_dont_mutate_shared_soup` that runs all extractors and verifies no cross-contamination |
| 2. URL normalization | ✅ Solid — `test_normaliser.py` exists | No action |
| 3. Text-extraction scope agreement (Path A/B/C) | ❌ Not enforced | **Add** the P4-1 tests from the scoring audit |
| 4. Catalogue ↔ help ↔ scoring parity | ✅ Architecture-parity test covers help/catalogue; needs extension for `_ISSUE_SCORING` | **Extend** existing test to also assert every catalogue code has a scoring entry |
| 5. Job-store interface parity (SQLite ↔ Redis) | ⚠️ Partial — REVIEW_SPEC flagged this but Redis store now has 84 tests | **Add** an explicit Protocol-conformance test: every method on `JobStoreBase` must be implemented on both backends and behave identically on a fixture |
| 6. Health-score determinism + slash match | ⚠️ Some test coverage but not a deterministic invariant | **Add** a property-based test that recomputes health from a fixture issue list |
| 7. Scoring-map ↔ analyzer parity | ❌ Not enforced | **Add** the Phase A test from the GEO scoring audit |

**Recommended single PR:** "v2.x M0.14 — class-1 invariant test
hardening." Each invariant gets its own test file or test class. Total
estimated effort: 1–2 days.

---

## Section 7 — Documentation improvements

### 7.1 Generate `issue-codes.md` from code ⭐ HIGH PRIORITY

**Already in PLAN-V3.0 as M10.4.** Bring it forward: write a script
`scripts/generate_issue_codes_doc.py` that reads `_CATALOGUE` +
`_ISSUE_SCORING` + `_AI_READINESS_CONFIDENCE` and emits
`docs/issue-codes.md`. Run in CI; fail the build if generated content
differs from committed. **Solves Section 5.5 permanently.**

### 7.2 Single canonical thresholds table

**Action:** Create `docs/thresholds.md` (or extend `docs/overview.md`)
with every numeric threshold the app uses, sourced from the code's
constants. URL length, thin-content word count, image size, alt-text
bounds, page size, first-N-words, text-to-HTML ratio.

### 7.3 Date and status-stamp every doc

**Action:** Add a yaml frontmatter to every doc in `docs/`:
```yaml
---
status: current | superseded-by <doc>
last_reviewed: 2026-MM-DD
---
```
Pre-existing pre-v2.0 docs that are now stale (REVIEW.md,
REVIEW_SPEC.md, some implementation plans) get
`status: superseded-by ...`.

### 7.4 Single source of truth for version / deployment / credentials

**Action:** Pick the canonical doc for each:
- Version → `CLAUDE.md` header is the truth; everything else links to it
- Deployment → `docs/deployment-railway.md`
- Credentials → new `docs/credentials.md` (file doesn't exist yet)

### 7.5 Mark implementation plans done vs planned

**Action:** Add a `## Status` header to every plan in
`docs/implementation_plan_*.md`. Already done for GEO plans. Add to
`docs/fix-agent-spec.md`.

### 7.6 Fix residual broken links in sub-READMEs

**Action:** See Section 5.1.

### 7.7 Reconcile image specs

**Action:** See Section 5.4.

---

## Companion deliverable: Functional Specification

In parallel with the above, the user requested a
`docs/functional-specification.md` — a single document a third-party QA
reviewer can use to verify the app does what it claims.

**Audience:** Independent QA / external reviewer.

**Scope:** Shipped features (v2.x), with a "Known Limitations" section
for v3.0 roadmap items.

**Structure** (per agreed plan):
1. Purpose & Scope
2. Core User Journeys (5–8 journeys with acceptance criteria)
3. Feature Catalogue (capability table)
4. Audit Capabilities (every issue check with trigger conditions)
5. Fix Capabilities (every WP fix with preconditions and side effects)
6. AI Capabilities
7. Non-functional requirements
8. Verification matrix (feature → test file pointer)

**Estimated effort:** 2–3 focused sessions to write end-to-end. Best
done in its own PR so it can be reviewed independently of the fixes.
Once landed, becomes the artifact reviewers actually use.

---

## Proposed remediation order

Ranked by reviewer's correctness priority + my recommendation:

1. **(Done)** Verify P1 items #2 and #5 — already fixed in code
2. **(In progress)** This triage document
3. **Section 5.1** — sweep broken links in spec sub-READMEs (small, focused)
4. **Section 5.3 / 5.4 / 7.5** — version + doc-status stamp sweep (small, focused)
5. **Functional specification** — substantial document, separate PR
6. **Section 6 invariants** — class-1 hardening test PR
7. **Section 2** — weak-checks triage PR (per-item commits)
8. **Section 7.1** — auto-generate issue-codes.md (permanent fix for Section 5.5)
9. **Section 3** — GEO scoring buffer bugs (verify which are still present, then structural fix)
10. **Section 4 contradiction-resolutions** — small doc updates per recommendation
11. **Frontend defects #7, #8, #10** — folded into v2.7 M10 toast/dialog work
12. **Frontend defect #9** — standalone small commit (apiFetch timeout)

---

*Last updated: 2026-05-27. This document is the canonical response to
the docs-folder review register. It will be updated as remediation
items land.*
