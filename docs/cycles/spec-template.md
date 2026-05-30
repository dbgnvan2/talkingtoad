# Spec Template (4-Part Structure)

This template is used by the Architect (Gemini) to produce every cycle spec.
It produces output compatible with the repo's `docs/pending/` micro-spec convention.

---

**Cycle Label:** <!-- e.g. GG -->
**Feature Domain:** <!-- core-crawler, image-analysis, ai-readiness, wordpress-integration, cross-cutting -->
**Target File(s):** <!-- e.g. api/crawler/issue_checker.py, api/routers/crawl.py -->

---

## Part 1: Signature

Define the function/class signatures involved.

```
def function_name(param1: type, param2: type) -> ReturnType:
```

- Exact function names
- Parameter names and types
- Return type
- Module path (e.g. `api/crawler/engine.py`)

For new files: specify the module path and all exported symbols.
For changes: specify existing function, what changes (add param? change return? refactor body?).

## Part 2: Data Isolation

Define the data model. What data flows in, what data flows out, what is stored.

- Input schema (JSON body or query params for API endpoints)
- Output schema (response shape)
- Database schema changes (new tables, columns, indices)
- State that must NOT leak between requests (async isolation)
- State that must persist across requests (job store, cache)

## Part 3: Negative Constraints

Boundaries the implementation MUST NOT cross.

- What it must NOT do (e.g. "do not call WP API for URL changes")
- What it must NOT break (e.g. "existing issue_codes in _CATALOGUE must remain unchanged")
- Performance limits (e.g. "do not exceed 2s per URL during crawl")
- Security boundaries (e.g. "all external input must go through is_ssrf_safe()")
- Architectural rules (e.g. "do not modify GUI structure without explicit instruction")

## Part 4: Evaluator

How to verify the implementation is correct.

- Test assertions (what pytest should pass)
- Manual validation steps
- Acceptance criteria (binary: pass/fail)
- Existing tests that must still pass
- Edge cases to test

---

## Output Convention

After the Architect fills this template, save to:
`docs/cycles/<cycle_label>/spec.md`

After final Architect approval at cycle end, produce a micro-spec at:
`docs/pending/YYYY-MM-DD_<cycle_label>-<feature-slug>.md`

The micro-spec must follow the repo convention (conversational markdown, not template form)
and be suitable for the Gemini Compiler pipeline to merge into `docs/functional-specification.md`.
