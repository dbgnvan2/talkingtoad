# Cycle GG — Continuation Prompt (7 decisions resolved)

## Context

You previously executed the GEO_SUMMARY_BURIED implementation from `prompt-for-claude.md`. The architect and senior dev reviewed your output. There were 7 open questions in your output that needed design decisions. Those are now resolved below.

Proceed to implement the corrections based on these decisions.

---

## The 7 Resolved Decisions

### Q1: Which IssueSource value to use (INFORMATIONAL, CONTENT_QUALITY, or a new one)?
**Decision: IssueSource.CONTENT_QUALITY** — closest semantic match for a content structure quality check. No new source needed.

### Q2: Should ParsedPage carry raw HTML/soup or should we add a new parameter?
**Decision: Add a new optional `soup` parameter** to the audit call. Do NOT modify ParsedPage — that has wider blast radius. The auditor method signature should accept an optional `soup` parameter.

### Q3: Preferred file for the auditor class?
**Decision: `api/services/extractability.py`** — it's the existing home for extractability logic and already imported in the main pipeline. If it exceeds 300 lines, split later.

### Q4: Audit behaviour for pages with no H2 tags?
**Decision: Return None silently** — no H2s is a structural observation, not an issue. Silent skip keeps the issue catalogue clean.

### Q5: Score penalty and threshold for GEO_SUMMARY_BURIED?
**Decision: Threshold = 4 content nodes, penalty = 20** — as spec'd originally. Start with these values, calibrate after real-world crawling.

### Q6: Integration point in the extractability pipeline?
**Decision: Insert BEFORE quality-based scoring** — structural issues caught early can reduce the quality score. If placed after, the score would already be set.

### Q7: Preferred test style?
**Decision: pytest with pytest-asyncio** — matching repo conventions (pytest fixtures, async test patterns). Do NOT introduce a new test style.

---

## What to Fix

With these decisions, re-examine your previous implementation output and adjust:

1. Ensure IssueSource is CONTENT_QUALITY (not a new type)
2. Make the audit function accept an optional `soup` param (not modify ParsedPage)
3. Verify ContentNodeAuditor lives in `api/services/extractability.py`
4. Pages with no H2 tags should produce no issue (None silently)
5. Penalty should be 20, threshold 4
6. Integration point is before quality scoring
7. Tests use pytest-asyncio matching repo patterns

Run the test suite to confirm all 4 tests still pass after adjustments.
