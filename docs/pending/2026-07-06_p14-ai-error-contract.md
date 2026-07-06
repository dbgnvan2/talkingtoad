# P14 fix — AI error contract: `analyze_with_ai` raises instead of returning error strings

Date: 2026-07-06
Pattern: P14 (error state returned as string, rendered as content)

## The bug

`api/services/ai_analyzer.py::analyze_with_ai(prompt_key, context) -> str` signalled
failure by **returning a sentinel error string** instead of raising:

- `"AI analysis skipped: No API key configured (…)"` (on `ProviderAuthError`)
- `"Error calling AI: <exc>"` (on any other exception)
- `"Error calling AI: prompt template missing key …"` (on a missing context key)

Because success and failure were both `str`, callers could — and did — render an
error message as if it were AI content:

- `/api/ai/analyze` (title_meta_optimize / semantic_alignment) returned the error
  string directly as the `suggestion` field — **no sentinel check at all**.
- `/api/ai/page-advisor` and `/api/ai/site-advisor` fed the error string into
  `recommendations` / `raw_response` as content — **no sentinel check**.
- `/api/crawl/{id}/executive-summary` cached the error string on the job
  (`update_job(executive_summary=...)`) and returned it as `summary`.
- The PDF report path fed the error string in as report content.
- `/api/ai/test` and `/api/ai/analyze` (issue_advisor) *did* guard via
  `str.startswith("AI analysis skipped" | "Error calling AI")` — brittle sentinel checks.

A sibling instance lived in `api/services/geo_llm.py::_call_llm`, which returned
`"AI analysis failed: …"` filtered by a `_is_ai_error` prefix check.

## The fix (raise-based, class-wide)

1. New typed exception `AIAnalysisError(Exception)` defined in `ai_analyzer.py`.
2. `analyze_with_ai` now **raises `AIAnalysisError`** on every runtime failure
   (no key → from `ProviderAuthError`; any provider/API error; missing template key).
   Success return is unchanged: the plain suggestion string. `ValueError` still
   raised for an unknown `prompt_key`.
3. `geo_llm._call_llm` now **raises `AIAnalysisError`** instead of returning a
   sentinel string; `classify_geo_llm` catches it and returns an empty verdict `{}`
   (no spurious finding). `_is_ai_error` and `_ERROR_PREFIXES` deleted;
   `parse_geo_verdict` still guards against empty/garbage/non-JSON (L4).
4. Every caller wrapped in `try/except AIAnalysisError` and routed to its error channel;
   all `startswith("AI analysis skipped" | "Error calling")` sentinel checks removed.

## Callers updated

| Call site | Error channel on `AIAnalysisError` |
|---|---|
| `api/routers/ai.py` `/test` | `{success: False, message: str(exc)}`; sentinel check removed |
| `api/routers/ai.py` `/analyze` (all types) | `{"error": str(exc)}`; sentinel check removed |
| `api/routers/ai.py` `/page-advisor` | `{"page_url": …, "error": str(exc)}` (was: error → recommendations) |
| `api/routers/ai.py` `/site-advisor` | `{"job_id": …, "error": str(exc)}` (was: error → recommendations) |
| `api/routers/crawl.py` executive-summary | `_err("AI_UNAVAILABLE", …, 503)`; error never cached on job |
| `api/routers/crawl.py` PDF report | `executive_summary` stays `None`; error never in report |
| `api/services/geo_llm.py` `classify_geo_llm` | returns `{}` (empty verdict) |

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| AC1 | `analyze_with_ai` raises `AIAnalysisError` on no-key (not a string) | `tests/test_ai_api.py::test_analyze_with_ai_raises_on_provider_auth_error` |
| AC2 | `analyze_with_ai` raises on provider/API error | `tests/test_ai_api.py::test_analyze_with_ai_raises_on_provider_api_error` |
| AC3 | `analyze_with_ai` raises on missing template key | `tests/test_ai_api.py::test_analyze_with_ai_raises_on_missing_template_key` |
| AC4 | `/test` routes error to `success:False message`, no `sample` (content) | `tests/test_ai_test_endpoint.py::test_ai_test_failure_shape_no_api_key_read` |
| AC5 | `/analyze` issue_advisor: error → `{error}`, never `suggestion` | `tests/test_issue_advisor.py::test_issue_advisor_no_api_key_returns_error_not_suggestion` |
| AC6 | `/page-advisor`: error → `{error}`, never `recommendations` | `tests/test_issue_advisor.py::test_page_advisor_ai_error_routed_not_rendered` |
| AC7 | `/site-advisor`: error → `{error}`, never `recommendations` | `tests/test_issue_advisor.py::test_site_advisor_ai_error_routed_not_rendered` |
| AC8 | executive-summary: error → 503, never cached as `executive_summary` | `tests/test_crawl_router_contracts.py::TestExecutiveSummaryAIErrorNotContent::test_ai_error_returns_503_and_is_not_cached` |
| AC9 | `geo_llm._call_llm` raises `AIAnalysisError` (not a sentinel string) | `tests/test_r8_geo_llm.py::test_call_llm_failure_raises_not_returns_sentinel` |
| AC10 | `classify_geo_llm` returns `{}` (no finding) on LLM failure | `tests/test_r8_geo_llm.py::test_classify_returns_empty_on_llm_failure` |

## Not regressed

- LLM call still owns timeout/retry inside `ai_router` (external-api.md E1); no change there.
- No hardcoded model IDs introduced (llm-integration.md L1).
