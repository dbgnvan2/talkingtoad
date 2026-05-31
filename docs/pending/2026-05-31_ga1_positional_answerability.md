---
status: pending
proposed: 2026-05-31
author: Architect (GA1 verify cycle, TalkingToad session)
type: bug-fix
source: PLAN-V3.0-UNIFIED.md GA1 verification — 3 documented deltas
supersedes: parts of docs/pending/2026-05-30_cycle_gg_answerability_audit.md (Cycle GG)
---

# GA1.fix — Positional + H3 Answerability Auditor (GEO_SUMMARY_BURIED)

## Classification: BUG FIX (not enhancement)

`GEO_SUMMARY_BURIED` is documented and labelled as a *positional* "answer is
buried" check, but the shipped Cycle GG code measures something different —
**how many** content nodes a section has, not **where** the first one appears.

Evidence it is drift, not intent:
- **Help text (registry) already promises positional behaviour:** *"Reorder each
  H2 section so the core answer leads in 1–2 sentences… AI retrievers and
  skimming humans both miss answers that aren't immediately under the heading."*
- The field/variable is named `first_content_depth` but holds a **total count**.
- `is_answer_buried` fires at `count >= 4` content nodes — so a clean section with
  one lead paragraph followed by four more paragraphs is flagged (**false
  positive**), while a section whose answer is genuinely pushed below a hero
  image + video + figure is **not** measured positionally at all.
- `<h3>` sections (where FAQ-style answers — the most citation-relevant content —
  live) are never walked.

→ Fix now. Three defects to correct: **(1)** positional semantics, **(2)** `<h3>`
coverage, **(3)** rename the misleading field.

## Goal

Flag a section when its **first substantive content node (`<p>`/`<ul>`/`<ol>`/`<li>`)
appears too far down** the section — i.e., the answer is pushed below non-content
blocks (images, figures, video, embeds, wrapper divs). Do **not** flag a section
merely for being long.

## Design

- **Scope:** every `<h2>` **and** `<h3>`. A "section" = the heading plus the
  content that follows it **in document order** until the next heading of **any**
  level.
- **Document-order walk, not direct-siblings-only.** The Cycle GG walker used
  `find_next_siblings()`, which misses content wrapped in a `<div>` right after the
  heading. Replace with a document-order scan (`heading.find_all_next()` bounded by
  the next heading) so wrapped content is still found.
- **Decorative tags skipped** (do not count toward depth):
  `svg`, `script`, `style`, `noscript` (unchanged set).
- **Depth definition:** walking the section in document order and skipping
  decoratives, `depth` of the first content node = (number of non-decorative,
  non-content **block** elements encountered before it) + 1.
  - Non-content blocks that *push the answer down* and therefore count toward
    depth: `img`, `picture`, `figure`, `video`, `iframe`, `embed`, `object`,
    `canvas`, `blockquote`, plus any wrapper element that contains **no**
    content node.
  - A wrapper (`div`/`section`/`article`) that **contains** the first content node
    does **not** add an extra level — we descend into it; the content node inside
    is what we score.
- **Buried test:** `depth >= _BURIED_THRESHOLD`.
  - **Recommended `_BURIED_THRESHOLD = 3`** — honours Gemini's "answer must reside
    in the first **two** `<p>/<ul>/<li>` nodes" (positions 1–2 OK, 3+ buried). The
    Gemini evaluator's "depth 4" example still triggers (4 ≥ 3).
  - *(Open decision A — confirm 3 vs 4 on approval.)*
- **No `<h2>`/`<h3>` in the page → silent skip** (return `None`), unchanged from GG.
- **Pure CPU. No network, no LLM.** (Gemini 3.1 data-isolation constraint preserved.)

### Open decisions for approval
- **A. Threshold:** 3 (recommended, matches "first two nodes") or 4 (matches the
  literal "depth 4" evaluator example, fewer flags).
- **B. Content tag set:** include `<ol>` alongside `<ul>` (recommended — an ordered
  list is just as extractable). Gemini listed only `ul`.
- **C. Do tables count as content?** Recommend **yes** — a `<table>` is extractable
  answer content, so a leading table = not buried. (GG didn't consider tables.)

## Files to modify

| File | Change |
|---|---|
| `api/services/extractability.py` | Rewrite `ContentNodeAuditor` to a document-order positional walk over `<h2>`+`<h3>`; `walk_section_content_nodes()` returns `first_content_depth` = **position** (not count); keep `is_answer_buried(results, threshold=_BURIED_THRESHOLD)`; `audit_answerability()` reads the renamed flag. Set `_BURIED_THRESHOLD = 3`. Extend `_CONTENT_TAGS`/add `_PUSHDOWN_TAGS`. |
| `api/crawler/parser.py` | Rename pre-computed `is_h2_answer_buried` → `is_answer_buried` on `ParsedPage` (cover h2+h3); update the compute block (~L220–231) and the constructor kwarg (~L296) and the field comment (~L127–133). Keep `bool \| None` (None = no headings / legacy). |
| `api/crawler/checkers/registry.py` | Update `GEO_SUMMARY_BURIED.description` from "buried under content nodes under an H2 heading" → positional wording covering H2+H3 (recommendation text already correct). Catalogue/scoring `(7,3)`/confidence "Heuristic" unchanged. |
| `frontend/src/data/issueHelp.js` | Sync `GEO_SUMMARY_BURIED` wording to positional + H3 (parity). |
| `docs/issue-codes.md` | Regenerate (auto-gen) so it matches the catalogue. |
| `tests/test_extractability.py` | Replace the count-based `TestContentNodeAuditor` cases (the 5-node burial test, the `test_burial_threshold_boundary_exactly_four` I added this session, the decorative test) with positional cases below. |

**Back-compat note:** `audit_answerability(parsed_page, soup=None)` keeps its public
signature. Internally, when reading the pre-computed flag, accept **both** the new
`is_answer_buried` and the legacy `is_h2_answer_buried` (`getattr` fallback) so any
persisted/Redis `ParsedPage` from before this fix still resolves to "no signal"
rather than crashing.

## Test plan (`tests/test_extractability.py`)

**Positional correctness (unit):**
- `answer leads (depth 1)` under `<h2>` → not buried.
- `answer at depth 2` (one image, then `<p>`) → not buried (within first two).
- `answer at depth 3` (image + figure, then `<p>`) → **buried** (threshold boundary, 2↔3).
- `answer at depth 4` (Gemini evaluator case: 3 media blocks then `<p>`) → **buried**.

**The false-positive guard (the whole point of the fix) — adversarial:**
- **`verbose section, answer leads`**: `<h2>` + one lead `<p>` + four more `<p>` →
  depth 1 → **NOT buried.** (This is the exact input the old count-based code wrongly
  flagged. "What would a correct-looking-but-wrong result look like?" → the old code
  returning `GEO_SUMMARY_BURIED` here. Assert it does **not**.)

**`<h3>` coverage (the missed-case fix) — adversarial:**
- FAQ-style `<h3>` with the answer pushed to depth 4 → **buried** (old h2-only code
  returned `None`; assert the fix now flags it).

**Wrapper handling:**
- `<h2>` immediately followed by `<div><p>answer</p></div>` → first content node found
  inside the wrapper at depth 1 → **not buried** (proves document-order descent works).

**Decorative skip (unchanged behaviour, re-asserted):**
- `<h2>` + `svg`/`script`/`style`/`noscript` + `<p>` → depth 1 → not buried.

**Precomputed-flag path + back-compat:**
- `audit_answerability(page)` (no soup) reads `is_answer_buried`; legacy
  `is_h2_answer_buried`-only instance resolves to `None` (no crash).
- No-heading page → `None` (silent skip).

## Security check
- **SSRF:** No — pure local DOM walk, no fetch.
- **Auth:** N/A — runs at crawl/parse time, not an endpoint.
- **WordPress:** No.
- **XSS:** No — no user text injected into HTML.

## Documentation impact
- `docs/issue-codes.md` — regenerate (catalogue wording change).
- `frontend/src/data/issueHelp.js` — parity sync.
- `PLAN-V3.0-UNIFIED.md` — flip GA1 to ✅ once merged; note the fix closed all 3 deltas.
- READ-ONLY (untouched): `docs/functional-specification.md`, `docs/thresholds.md`
  (no numeric threshold table change — `_BURIED_THRESHOLD` is an internal constant,
  not a published threshold; confirm with maintainer if it should be surfaced there).

## Acceptance criteria
1. The positional + H3 tests above are added and **pass**.
2. The verbose-section false-positive guard **passes** (no flag when answer leads).
3. The `<h3>` buried case **flags**.
4. Catalogue ↔ issueHelp.js ↔ issue-codes.md parity tests **pass**.
5. Full suite green, 0 regressions.
