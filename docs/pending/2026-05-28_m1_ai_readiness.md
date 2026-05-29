---
status: pending
proposed: 2026-05-28
revised: 2026-05-28 (post-audit findings appended)
author: System Architect
source: PLAN-V3.0.md
---

# Milestone 1: AI-Readiness v2.0 Gaps

## Goal
Complete the remaining v2.0 AI-readiness parser requirements and heuristics.

## Requirements

### M1.2 — Schema Block Extraction
- Implement `extract_schema_blocks()` in `api/crawler/parser.py`.
- Ensure JSON-LD extraction handles `@graph` nesting and malformed JSON.
- Persist new `schema_blocks` field in `ParsedPage`.

### M1.4 — Passage Heuristics
- Implement `api/services/passage_heuristics.py`.
- Define heuristics: `AI_PARAGRAPH_TOO_LONG`, `AI_NO_DEFINITIONS`.
- Ensure threshold logic uses total visible text to prevent false positives.

## Acceptance Criteria
1. `ParsedPage` successfully serializes `schema_blocks` through the database.
2. `passage_heuristics.py` is fully unit-tested with mocked HTML fixtures.
3. No regressions in existing AI-readiness test suite.

---

## Audit findings (Cycle W pre-execution)

Most of M1.2 already shipped. M1.4 needs scoping decisions before implementation. Details:

### M1.2 status: **75% already exists**

| Item | Status | Evidence |
|---|---|---|
| `_extract_schema_blocks()` in parser.py | **EXISTS** (since at least Cycle L) | `api/crawler/parser.py:452` |
| `@graph` nesting handled | **YES** — flattens `@graph` arrays into top-level blocks | `parser.py:459-463` |
| Malformed JSON handled | **YES** — wrapped in `try/except (json.JSONDecodeError, TypeError)` | `parser.py:468` |
| List-of-objects root handled | **YES** — added in Cycle L V3 fix (`_run_geo_checks` also defends against list blocks) | `parser.py:466-467` + `checkers/ai_readiness.py:159-176` |
| `ParsedPage.schema_blocks` field | **EXISTS** as `list[dict] \| None` | `parser.py:101` |
| Wired into ParsedPage construction | **YES** | `parser.py:229` |
| Database persistence (round-trip through SQLite/Redis) | **NEEDS VERIFICATION** — ParsedPage is a transient parser output; only the API `Page` model is stored. If schema_blocks needs to survive a rescan or be queryable by `/api/crawl/{id}/results`, the storage layer needs a column. If it's only consumed during in-process `check_page`, current behaviour is fine. |

**Recommendation:** scope M1.2 down to *verifying* that schema_blocks survives wherever it's actually needed. If the only consumer is `_run_geo_checks` during the same in-memory crawl pass, no DB change is required. If frontend needs to display schema validation results later, add a column.

### M1.4 status: **scoping ambiguity + one real gap**

| Item | Status | Evidence |
|---|---|---|
| `AI_PARAGRAPH_TOO_LONG` issue code | **EXISTS** under the name `PARA_TOO_LONG` | `registry.py:241, 1271` |
| Per-page trigger logic | **EXISTS** in `checkers/crawlability.py:44` | reads `page.long_paragraph_count` |
| 150-word threshold | **APPLIED** in `parser.py:1113` (`_count_long_paragraphs(soup, threshold: int = 150)`) | matches spec value exactly |
| Strips `<nav>`, `<footer>`, `<aside>` before counting | **NO — REAL BUG** | `_count_long_paragraphs` iterates `soup.find_all("p")` with no element exclusion. The user's threshold-audit warning is correct: false positives on footer/nav text. Adjacent functions (`_count_long_paragraphs` neighbours `_check_query_coverage_weak` at line 1137 which DOES strip these tags) confirm the asymmetry. |
| `AI_NO_DEFINITIONS` issue code | **DOES NOT EXIST** | not in `_CATALOGUE` |
| Related: `FIRST_VIEWPORT_NO_ANSWER` | **EXISTS** and its description explicitly mentions "definition" as one of the answer signals: *"First 200 words contain no direct answer signal (definition, TL;DR, summary phrase)"* | `registry.py:1128-1131` |
| `api/services/passage_heuristics.py` file | **DOES NOT EXIST** | confirmed by `ls` |

**Scoping ambiguities to resolve before implementation:**

1. **Code naming.** The spec uses `AI_PARAGRAPH_TOO_LONG` but the existing code is `PARA_TOO_LONG`. Adding a new code with the longer name would create a duplicate. Either:
   - (a) Treat the spec text as informal and patch the existing `PARA_TOO_LONG` to fix the nav/footer/aside bug, **or**
   - (b) Rename `PARA_TOO_LONG` to `AI_PARAGRAPH_TOO_LONG` (catalogue churn — breaks frontend `issueHelp.js`, every parity test, the docs generator, every existing assertion that names the code).
   - **Recommendation:** (a). The bug fix is the substantive work; the code-name change is cosmetic and expensive.

2. **`AI_NO_DEFINITIONS` scope.** The existing `FIRST_VIEWPORT_NO_ANSWER` already covers "no definition in first 200 words" (definitions are listed as one of the answer signals). Is the proposed new code:
   - (a) A renaming / replacement of `FIRST_VIEWPORT_NO_ANSWER` (same content, narrower trigger),
   - (b) An additional check that fires per-section (every H2/H3 block lacks a definition opener) — much broader scope,
   - (c) Something else?
   - **Recommendation:** without the user's clarification, do not implement. Adding overlapping codes inflates the issue count and confuses users.

3. **`passage_heuristics.py` as a new file.** The existing per-page check sites are split across `checkers/crawlability.py` (PARA_TOO_LONG) and `checkers/ai_readiness.py` (FIRST_VIEWPORT_NO_ANSWER, GEO checks). Creating a separate `passage_heuristics.py` introduces a fourth home for the same family of checks unless we also migrate the existing checks into it. That's an architectural decision (the Cycle K split deliberately organised by *domain*, not by *granularity*) that needs explicit user approval.

### Threshold audit recommendation: confirmed valid + needs implementation

The user's threshold audit (item 3) correctly identifies that the 150-word
threshold is safe **iff** nav/footer/aside are excluded. The current
`_count_long_paragraphs` does NOT do this exclusion. The fix is a 5-line
change mirroring the pattern used 24 lines down in `_check_query_coverage_weak`:

```python
def _count_long_paragraphs(soup: BeautifulSoup, threshold: int = 150) -> int:
    """Count <p> elements whose word count exceeds threshold."""
    # Work on a body-scoped copy so the noise-removal does not mutate
    # the soup that later parsing steps depend on.
    body = soup.find("body") or soup
    # Strip the same chrome elements that _count_visible_body_words and
    # _check_query_coverage_weak strip — without this the threshold fires
    # on long boilerplate footer/nav text.
    for noise in body.find_all(["script", "style", "nav", "header", "footer", "aside"]):
        noise.decompose()
    count = 0
    for p in body.find_all("p"):
        if len(p.get_text(separator=" ", strip=True).split()) > threshold:
            count += 1
    return count
```

**WARNING — mutation hazard:** `soup.decompose()` mutates the parse tree in
place. If `_count_long_paragraphs` is called before other parsing functions
that depend on `<nav>` / `<footer>` / etc., it will silently delete content
they expected to read. The safer pattern is to clone the body or iterate
without decomposing (`p` must not be inside a noise ancestor). Implementation
must use the safer pattern.

## User scoping decisions (approved 2026-05-28)

1. **Code naming:** keep `PARA_TOO_LONG` as-is — patch the nav/footer
   bug, no rename. `AI_PARAGRAPH_TOO_LONG` was informal spec language.
2. **`AI_NO_DEFINITIONS`:** already covered by `FIRST_VIEWPORT_NO_ANSWER`
   (its description explicitly names "definition" as an answer signal).
   No new code added.
3. **`passage_heuristics.py`:** **not created.** New checks (none in
   this cycle anyway) belong in `checkers/ai_readiness.py` per the
   Cycle K domain-based split.

## Final execution scope (Cycle W)

1. **M1.2:** verification-only. `_extract_schema_blocks()` + the
   `schema_blocks` field already exist with `@graph` flattening,
   malformed-JSON tolerance, and list-of-root defense. The only
   open verification is whether any consumer needs DB persistence
   (currently no caller does — `_run_geo_checks` reads it in the
   same in-process pass).
2. **M1.4:** patch `_count_long_paragraphs` in `api/crawler/parser.py`
   to exclude chrome elements (`script`, `style`, `nav`, `header`,
   `footer`, `aside`) before counting `<p>` tags. Use a
   non-mutating ancestor-check approach to avoid the `.decompose()`
   hazard called out in the audit. Add an adversarial test with a
   long `<footer>` paragraph + short article body that fails pre-fix.
