# GEO Rewrite Prompt Generator — Implementation Plan

**Date:** 2026-05-03  
**Status:** Draft — awaiting user approval before implementation  
**Spec source:** Meta-Prompt (provided by user)

---

## Goal

Build a feature that reads the GEO analyzer's actual scoring logic, reverse-engineers the exact combination of checks needed to reach a score ≥ 90, and produces a ready-to-paste LLM prompt that a writer can use to rewrite any page to hit that target. The prompt is grounded in *this tool's specific thresholds*, not generic GEO advice.

The feature has two outputs:
1. **The rewrite prompt** — a structured, paste-ready LLM prompt with role, rubric, prohibitions, and iteration instructions
2. **The annotation sheet** — maps each prompt section to the specific analyzer check it addresses, plus a list of checks that are weakly defined or require fabrication to satisfy

---

## Scoring System Inventory (Step 1 — from code)

This section documents every check, its weight, and the pass threshold as read from the codebase. This is the authoritative input to path calculation.

### LLM-based checks (`api/services/geo_analyzer.py`)

| Check | Evidence tier | Weight | Pass condition | How scored |
|---|---|---|---|---|
| `QUERY_MATCH_SCORE` | Empirical | 3 | score ≥ 0.70 | `(answered + 0.5 × partial) / total queries`. LLM generates 7 queries, scores each Yes/Partial/No |
| `JS_RENDERED_CONTENT_DIFFERS` | Mechanistic | 2 | No flag | Token-set diff: rendered adds ≤ 20% new tokens vs raw HTML |
| `CONTENT_CLOAKING_DETECTED` | Mechanistic | 2 | No flag | Jaccard similarity of top-10 keywords ≥ 0.30 |
| `UA_CONTENT_DIFFERS` | Mechanistic | 2 | No flag | GPTBot/ClaudeBot token count ≥ 80% of rendered token count |
| `CHUNKS_NOT_SELF_CONTAINED` | Mechanistic | 2 | ratio ≥ 0.50 | Fraction of H2/H3 sections that pass standalone comprehension test (capped at 8 sections) |
| `CENTRAL_CLAIM_BURIED` | Mechanistic | 2 | Claim in first 150 words | LLM identifies central claim, checks if it appears in first 150 words |
| `PROMOTIONAL_CONTENT_INTERRUPTS` | Conventional | 1 | ≤ 1 mid-article promo section | LLM classifies each section as main_content or promotional; flags if >1 mid-article promo |

### Static checks (`api/crawler/issue_checker.py`, `_run_geo_checks`)

These fire during crawl (per-page). They appear in the Issues tab, not in the GEO report score, but they are part of the overall AI Readiness picture and are included in the rubric.

| Check | Evidence tier | Impact/Effort | Threshold |
|---|---|---|---|
| `STATISTICS_COUNT_LOW` | Empirical | 7/2 | ≥ 1 statistic match in first 150 words + heading text. Matches: `\d[\d,]*%`, numeric units (KB/MB/ms/users/etc.), years 1900–2099, "N of M" patterns |
| `EXTERNAL_CITATIONS_LOW` | Empirical | 7/2 | ≥ 1 external domain link in body. Fires only on 500+ word pages with zero external links |
| `QUOTATIONS_MISSING` | Empirical | 6/2 | ≥ 1 `<blockquote>` OR attribution pattern ("according to", "stated", "says", etc.) on 500+ word pages |
| `ORPHAN_CLAIM_TECHNICAL` | Empirical | 6/2 | Technical pages: ≤ 2 unsourced factual claims. Triggered by URL path patterns (/docs/, /guide/, /tutorial/, /how-to/) |
| `RAW_HTML_JS_DEPENDENT` | Mechanistic | 6/3 | text-to-HTML ratio ≥ 5% AND no SPA shell marker (`<div id="root">` etc.) |
| `FIRST_VIEWPORT_NO_ANSWER` | Mechanistic | 5/2 | First 150 words contain a definition/answer signal (TL;DR, "in short", "X is a/an Y", "refers to", "defined as") on 200+ word pages |
| `CHUNKS_NOT_SELF_CONTAINED` | Mechanistic | 5/4 | (Also LLM-graded above) |
| `CENTRAL_CLAIM_BURIED` | Mechanistic | 5/3 | (Also LLM-graded above) |
| `AUTHOR_BYLINE_MISSING` | Mechanistic | 4/2 | Article/BlogPosting pages: `rel="author"`, `itemprop="author"`, JSON-LD `author`, byline CSS class, or `meta[name=author]` present |
| `CODE_BLOCK_MISSING_TECHNICAL` | Mechanistic | 4/2 | Technical pages: ≥ 1 `<code>` or `<pre>` block |
| `LINK_PROFILE_PROMOTIONAL` | Mechanistic | 4/2 | External link profile: not all links are promotional (`?ref=`, `?aff=`, `/go/`, etc.) |
| `JSON_LD_INVALID` | Conventional | 4/2 | All JSON-LD blocks have `@type` and `@context` |
| `COMPARISON_TABLE_MISSING` | Mechanistic | 3/2 | Pages with "vs/versus/compared to" headings: ≥ 1 `<table>` |
| `STRUCTURED_ELEMENTS_LOW` | Mechanistic | 3/2 | 500+ word pages: ≥ 1 `<ul>`, `<ol>`, `<table>`, `<dl>`, `<pre>`, or `<code>` |
| `FAQ_SCHEMA_MISSING` | Conventional | 3/2 | FAQ-pattern headings: FAQPage JSON-LD schema present |
| `PROMOTIONAL_CONTENT_INTERRUPTS` | Conventional | 3/3 | (Also LLM-graded above) |
| `DATE_PUBLISHED_MISSING` | Mechanistic | 3/1 | Article pages: `datePublished` in JSON-LD or `og:article:published_time` |
| `DATE_MODIFIED_MISSING` | Mechanistic | 2/1 | Article pages: `dateModified` in JSON-LD or `og:article:modified_time` |
| `AI_TXT_MISSING` | Conventional | 1/1 | `/ai.txt` exists at site root |

---

## GEO Report Score Calculation (for 90+ path)

The `overall_score` in the GEO report is computed over LLM findings only:

```
overall_score = Σ(finding.score × tier_weight) / Σ(tier_weight)

tier_weights = {Empirical: 3, Mechanistic: 2, Conventional: 1}
```

A finding is added to the report only when it **fails** (or has a partial score). If a check passes cleanly, it contributes no finding — the denominator still includes its weight implicitly (the numerator gets a perfect 1.0 × weight).

**To reach overall_score ≥ 0.90:** With the current findings (7 possible), a page needs to pass with high partial credit on most. The minimum viable path:

| Scenario | Score |
|---|---|
| All 7 checks pass | 1.00 |
| QUERY_MATCH_SCORE at 0.86 (6/7 answered), all others pass | ~0.97 |
| QUERY_MATCH_SCORE at 0.70 (5/7 answered), all others pass | ~0.93 |
| CENTRAL_CLAIM_BURIED fail (0.5 score), all others perfect | ~0.91 |
| CHUNKS_NOT_SELF_CONTAINED at 0.60 ratio, all others perfect | ~0.95 |
| PROMOTIONAL_CONTENT_INTERRUPTS fail, all others perfect | ~0.97 |
| JS_RENDERED_CONTENT_DIFFERS fail + CENTRAL_CLAIM_BURIED fail | ~0.81 — **below 90** |

**Mandatory to reach 90:**
1. `QUERY_MATCH_SCORE` ≥ 0.70 (Empirical weight 3 — single biggest lever)
2. No JS rendering flags (if Playwright available; combined weight 6)
3. `CENTRAL_CLAIM_BURIED` must pass (main point in first 150 words)

**High-value, pursue if feasible:**
4. `CHUNKS_NOT_SELF_CONTAINED` ≥ 0.50 (Mechanistic weight 2)
5. No `PROMOTIONAL_CONTENT_INTERRUPTS` (Conventional weight 1, easy to fix)

**Low-value for score (don't distort content):**
6. Static checks don't affect `overall_score` directly but do affect the Issues tab — they're included in the rubric as health checks, not as score mandates

---

## Failure Modes / Anti-Patterns (Step 3)

These are the things the rewrite prompt must explicitly prohibit:

1. **Fabricating statistics** — Inventing numbers ("97% of AI systems prefer…") to pass `STATISTICS_COUNT_LOW`. The check only requires ≥ 1 real statistic in the first 150 words.
2. **Inventing citations** — Adding URLs that don't exist to pass `EXTERNAL_CITATIONS_LOW`. The check fires only when there are *zero* external links; any real link clears it.
3. **Fake author bylines** — Adding a made-up name to pass `AUTHOR_BYLINE_MISSING`.
4. **Padding with fake tables** — Adding a comparison table with invented data to pass `COMPARISON_TABLE_MISSING`. The check only fires on pages with "vs" headings.
5. **Inserting boilerplate FAQ sections** — Adding fake Q&A to pass `FAQ_SCHEMA_MISSING` when the page isn't genuinely FAQ-format.
6. **Over-defining in the opener** — Adding a definition sentence that doesn't accurately describe the page, just to pass `FIRST_VIEWPORT_NO_ANSWER`.
7. **Keyword stuffing in headings** — Rewriting H2s to contain question words just to pass `CONVERSATIONAL_H2_MISSING` when questions don't match the content.
8. **Stripping CTAs that belong in the page** — Removing all promotional content including legitimate calls to action at the end of an article; the check only penalises CTAs *interrupting* mid-article content.

---

## Implementation Plan

### Phase A — Scoring inventory module (`api/services/geo_scoring_map.py`)

A pure-Python module (no LLM, no I/O) that exports the complete machine-readable scoring map as structured data. This is the foundation everything else reads from.

```python
GEO_CHECKS = [
  {
    "code": "QUERY_MATCH_SCORE",
    "label": "Query-Match Score",
    "tier": "Empirical",
    "tier_weight": 3,
    "source": "llm",
    "pass_condition": "score >= 0.70",
    "threshold_description": "≥70% of LLM-generated queries answered Yes or Partial",
    "page_type_conditions": None,   # applies to all pages
    "fix_effort": "medium",
    "can_fix_without_fabrication": True,
  },
  ...
]
```

Each entry must capture:
- `code`, `label`, `tier`, `tier_weight`
- `source`: `"llm"` or `"static"`
- `pass_condition` and `threshold_description` in human-readable form
- `page_type_conditions`: `None` (all pages), or a list of page types (e.g., `["article", "how-to"]`)
- `fix_effort`: `"low"` / `"medium"` / `"high"`
- `can_fix_without_fabrication`: `True` / `False` — whether the rubric item can always be satisfied with real content, or requires content that may not exist (e.g., a real comparison table can't be added to a non-comparison page)

**Acceptance criterion A.1:** `geo_scoring_map.py` exports `GEO_CHECKS` (a list of dicts), `TIER_WEIGHTS` (dict), and `compute_score_from_findings(findings: list[dict]) -> float` replicating `_compute_scores()` exactly.  
**Test:** `tests/test_geo_scoring_map.py::test_compute_score_matches_analyzer` — verifies that feeding the same findings to both functions returns identical scores.

**Acceptance criterion A.2:** Every check present in `geo_analyzer.py` and `issue_checker.py` `_run_geo_checks()` has a corresponding entry in `GEO_CHECKS`.  
**Test:** `tests/test_geo_scoring_map.py::test_all_checks_inventoried` — asserts `{e["code"] for e in GEO_CHECKS}` contains all known GEO codes.

---

### Phase B — Path calculator (`api/services/geo_scoring_map.py`, added function)

A function `compute_90_path(current_findings: list[dict]) -> dict` that:
1. Identifies which checks the page currently fails
2. Computes `marginal_score_gain` for passing each failed check (weight / total_weight)
3. Returns a sorted list: mandatory (passing is required for 90+), high-value (gains ≥ 0.05), low-value
4. Flags any check marked `can_fix_without_fabrication: False` so the prompt can exclude it

**Acceptance criterion B.1:** Given a set of current findings, `compute_90_path` correctly classifies checks as mandatory / high-value / low-value.  
**Test:** `tests/test_geo_scoring_map.py::test_compute_90_path_identifies_mandatory` — scenario: QUERY_MATCH_SCORE failing at 0.0, expected to be in mandatory set.

**Acceptance criterion B.2:** Function never returns a path requiring fabrication-only checks as mandatory.  
**Test:** `tests/test_geo_scoring_map.py::test_no_fabrication_in_mandatory_path`.

---

### Phase C — Prompt generator service (`api/services/geo_rewrite_prompt.py`)

The core service. `generate_rewrite_prompt(report: GEOReport, page_type: str) -> dict`:

Input:
- `report` — the full `GEOReport` from the analyzer (may be None if not yet run)
- `page_type` — detected or user-specified: `"article"`, `"how-to"`, `"comparison"`, `"marketing"`, `"reference"`, `"generic"`

Output dict:
```python
{
  "rewrite_prompt": str,          # ready-to-paste prompt
  "scoring_path": dict,           # from Phase B
  "annotations": list[dict],      # maps each prompt section → analyzer check
  "weak_checks": list[dict],      # checks that may require fabrication or are poorly defined
  "page_type_detected": str,
  "current_score": float,
  "projected_score_if_all_pass": float,
}
```

The `rewrite_prompt` string follows the structure from the spec:
- **(a) ROLE** — "You are a technical editor rewriting web pages for AI retrieval readiness against a specific scoring rubric."
- **(b) INPUT CONTRACT** — what the rewriter receives: original page markdown/HTML, current GEO score report (if available), any user constraints
- **(c) OUTPUT CONTRACT** — format (markdown with required structural elements), length constraints
- **(d) THE RUBRIC** — numbered, concrete instructions derived from `GEO_CHECKS`, filtered to the 90+ path. Each instruction is phrased as a concrete, verifiable action. Instructions that can't be satisfied without fabrication are omitted from the rubric and listed as `[SOURCE NEEDED]` placeholders.
- **(e) HARD PROHIBITIONS** — the anti-pattern list from Step 3
- **(f) PRESERVATION CONSTRAINTS** — factual claims, topic, authorial voice, user-specified constraints
- **(g) UNCERTAINTY HANDLING** — `[SOURCE NEEDED]` pattern, never fabricate rule
- **(h) ITERATION INSTRUCTION** — how to use analyzer delta reports in subsequent runs

Page type must affect the rubric:
- `"article"` — enables author byline, date published, date modified requirements
- `"how-to"` — enables code block, numbered steps requirements
- `"comparison"` — enables comparison table requirement
- `"marketing"` — relaxes FAQ and author requirements; tightens promotional bleed check
- `"reference"` — enables structured elements, JSON-LD validity, external citations requirements
- `"generic"` — applies all non-conditional checks

**Acceptance criterion C.1:** The generated prompt contains all 8 sections (ROLE through ITERATION).  
**Test:** `tests/test_geo_rewrite_prompt.py::test_prompt_has_all_sections`.

**Acceptance criterion C.2:** For a page type `"how-to"`, the prompt includes a code block instruction; for `"marketing"`, it does not.  
**Test:** `tests/test_geo_rewrite_prompt.py::test_page_type_conditions_respected`.

**Acceptance criterion C.3:** A check marked `can_fix_without_fabrication: False` never appears in the numbered rubric.  
**Test:** `tests/test_geo_rewrite_prompt.py::test_no_fabrication_checks_in_rubric`.

**Acceptance criterion C.4:** The `annotations` output maps every rubric item to a `code` from `GEO_CHECKS`.  
**Test:** `tests/test_geo_rewrite_prompt.py::test_all_rubric_items_annotated`.

**Acceptance criterion C.5:** `weak_checks` lists at minimum the three checks identified in the audit below as weakly defined.  
**Test:** `tests/test_geo_rewrite_prompt.py::test_weak_checks_surfaced`.

---

### Phase D — API endpoint (`api/routers/ai.py`)

`POST /api/ai/geo-rewrite-prompt`

Request body:
```json
{
  "job_id": "abc123",
  "url": "https://example.com/article",
  "page_type": "article",
  "use_cached_report": true
}
```

`job_id` + `url` are both optional but at least one must be provided. If `job_id` is given, uses the cached GEO report from the job store. If `use_cached_report` is false or no cached report exists, runs `generate_geo_report` first.

Response:
```json
{
  "success": true,
  "rewrite_prompt": "...",
  "scoring_path": {"mandatory": [...], "high_value": [...], "low_value": [...]},
  "annotations": [...],
  "weak_checks": [...],
  "page_type_detected": "article",
  "current_score": 0.61,
  "projected_score_if_all_pass": 1.0
}
```

**Acceptance criterion D.1:** Endpoint returns 200 with `rewrite_prompt` non-empty when a valid `job_id` is provided.  
**Test:** `tests/test_geo_rewrite_prompt.py::test_endpoint_returns_prompt` (mock GEOReport).

**Acceptance criterion D.2:** If the cached report has a score already ≥ 0.90, the response includes a note that the page already meets the target.  
**Test:** `tests/test_geo_rewrite_prompt.py::test_already_at_target_noted`.

---

### Phase E — Frontend (`frontend/src/components/GEOReportPanel.jsx`)

Add a "Get Rewrite Prompt" section to `GEOReportPanel`, visible after a GEO report has been run and only if `overall_score < 0.90`.

UI elements:
- Page type selector: auto-detected from URL/content, user can override
- "Generate Rewrite Prompt" button (calls `POST /api/ai/geo-rewrite-prompt`)
- Copy-to-clipboard button for the prompt
- Scoring path summary: mandatory / high-value / low-value checks with current pass/fail state
- Annotations table (collapsible): prompt section → analyzer check
- Weak checks warning panel: "These checks may require human-supplied content or cannot be satisfied without fabrication"

**Acceptance criterion E.1:** "Get Rewrite Prompt" button is only shown when `overall_score < 0.90`.  
**Test:** `tests/GEOReportPanel.test.jsx::test_rewrite_button_hidden_at_90` (mock report with score 0.92).

**Acceptance criterion E.2:** Page type selector defaults to auto-detected type; user can change it before generating.  
**Test:** `tests/GEOReportPanel.test.jsx::test_page_type_selector_exists`.

**Acceptance criterion E.3:** Copy button uses `navigator.clipboard.writeText` and shows "Copied!" confirmation.  
**Test:** `tests/GEOReportPanel.test.jsx::test_copy_button_feedback`.

---

### Phase F — `api/api.js` (frontend API function)

```javascript
export async function generateGeoRewritePrompt(jobId, { url, pageType, useCachedReport = true } = {}) { ... }
```

**Acceptance criterion F.1:** Function exists and is called by GEOReportPanel with correct parameters.  
**Test:** checked by E.1 test via mock.

---

## Weak Checks Audit (Step 6, third output)

These are checks the generator must surface in `weak_checks`:

| Check | Issue | Risk |
|---|---|---|
| `STATISTICS_COUNT_LOW` | Only searches `first_150_words` + heading text — body statistics are invisible. A 5000-word research page with 20 citations in the body will still fail if the opening para has no numbers. | **Design gap:** threshold is right, scope is too narrow. Rewrite prompt must note that statistics must appear in the *opening paragraph*, not anywhere on the page. |
| `ORPHAN_CLAIM_TECHNICAL` | Detection of "technical page" is URL-pattern-based; detection of "factual claims" is not implemented — the check never fires in practice (the code path exists but `_count_orphan_claims()` is a stub). | **Unimplemented:** prompt should not include a rubric item for this check. Surfaced as weak. |
| `CHUNKS_NOT_SELF_CONTAINED` | The pass/fail threshold is 50% of sections, but the LLM prompt only checks H2/H3 sections with ≥ 50 characters of text, capped at 8. A page with one very short H2 section and 10 long sections may have only 1 section evaluated. | **Threshold instability:** results depend heavily on section count and text length. Rewrite prompt must instruct rewriter to open each section with a self-contained topic sentence, not assume a count threshold. |
| `CONTENT_CLOAKING_DETECTED` | Requires Playwright. When Playwright is unavailable (most production deployments without the chromium binary), this check never runs — the finding is silently absent and its weight is dropped from the denominator. This inflates scores on JS-heavy sites. | **Conditional availability gap:** prompt should note that this check may not run; the rewrite should still ensure SSR or pre-rendered content. |
| `PROMOTIONAL_CONTENT_INTERRUPTS` | The LLM classifier sees only the first 300 characters of each section. A promotional section with a neutral heading and promotional body will be misclassified as `main_content`. | **Limited context window:** false negatives are common. Prompt should instruct placing all CTAs at the bottom, not just rely on section classification. |

---

## Implementation Order

```
Phase A  (scoring map)          → 2h — no dependencies
Phase B  (path calculator)      → 1h — depends on A
Phase C  (prompt generator)     → 4h — depends on A, B
Phase D  (API endpoint)         → 1h — depends on C
Phase F  (api.js)               → 0.5h — depends on D
Phase E  (frontend UI)          → 3h — depends on C, D, F
Tests                           → included in each phase above
```

Total estimated effort: **11–12 hours**

---

## Adjacent Issues Found, Not Fixed

Per CLAUDE.md rule 8 (surfaced for user decision):

1. **`ORPHAN_CLAIM_TECHNICAL` is a stub** — `_count_orphan_claims()` in `issue_checker.py` appears unimplemented (the issue is registered but the detection logic is a placeholder). Should be either implemented or removed from `_CATALOGUE` and `issueHelp.js` to avoid parity failures.

2. **`compute_90_path` belongs in a separate utility** — currently the scoring calculation lives inside `_compute_scores()` in `geo_analyzer.py`. Before Phase A, consider whether `geo_scoring_map.py` should fully own scoring, or merely mirror it. If `geo_analyzer.py`'s `_compute_scores` ever changes, `geo_scoring_map.py` will silently drift.

3. **`api/services/geo_rewrite_prompt.py` will embed the rubric as strings** — this is editorial content in Python source code, which CLAUDE.md rule 7 flags as technical debt. The rubric text (especially the HARD PROHIBITIONS and PRESERVATION CONSTRAINTS sections) could be externalised to `config/geo_rewrite_rubric.yaml`. Flagged for post-implementation decision.

---

## Verification Checklist (for user sign-off)

After implementation, user should verify:

- [ ] `api/services/geo_scoring_map.py` — exists, exports `GEO_CHECKS`, `TIER_WEIGHTS`, `compute_score_from_findings`, `compute_90_path`
- [ ] `tests/test_geo_scoring_map.py` — all 5 tests pass
- [ ] `api/services/geo_rewrite_prompt.py` — exists, exports `generate_rewrite_prompt`
- [ ] `tests/test_geo_rewrite_prompt.py` — all 7 tests pass
- [ ] `POST /api/ai/geo-rewrite-prompt` — returns 200 with `rewrite_prompt`, `scoring_path`, `annotations`, `weak_checks`
- [ ] Frontend: "Get Rewrite Prompt" button visible only when score < 0.90
- [ ] Frontend: page type selector auto-detects from URL
- [ ] Frontend: copy-to-clipboard with "Copied!" feedback
- [ ] `weak_checks` includes at minimum: `ORPHAN_CLAIM_TECHNICAL` (stub), `STATISTICS_COUNT_LOW` (scope gap), `CHUNKS_NOT_SELF_CONTAINED` (threshold instability)
- [ ] No fabrication-requiring checks appear in the mandatory rubric
- [ ] Zero ESLint errors on frontend build
