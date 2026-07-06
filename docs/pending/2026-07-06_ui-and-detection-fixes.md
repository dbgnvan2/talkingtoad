# UI + detection fixes — 2026-07-06

Three diagnosed bugs fixed. No spec/threshold changes.

## Fix A — GSC status omitted `configured`
`gsc_status()` (`api/routers/gsc.py`) now returns `"configured": True` on all
three 200 paths (no-creds, success, except-fallback). The `_require_gsc_configured()`
503 path is unchanged; `api.js gscStatus()` still maps a 503 to `configured:false`.
This lets `GSCInsightsPanel.jsx` distinguish configured-but-unlinked (shows the
Connect button) from genuinely-not-configured (quiet empty state).
- Tests: `tests/test_gsc_integration.py::TestGscStatus::test_not_connected_when_no_creds`,
  `::test_connected_with_creds` (both now assert `configured is True`);
  `::test_status_response_contract_fields` still passes.
- Frontend contract already correct: `GSCInsightsPanel.test.jsx` "renders Connect
  button when connected:false" uses `configured: true`.

## Fix B — valid text/plain llms.txt falsely flagged LLMS_TXT_INVALID
`fetch_page()` (`api/crawler/fetcher.py`) only decoded HTML/PDF bodies, so
`.html` was None for `text/plain`. Added a `text: str | None` field to
`FetchResult`; non-HEAD `text/*` (non-HTML) bodies are now decoded into `.text`,
bounded by `_MAX_HTML_BYTES`. `engine.py` llms.txt check reads
`llms_res.text or llms_res.html or ""`.
- Note: the ai.txt check in this codebase only inspects `status_code` (no body
  validation), so no body-read change applied there.
- Tests: `tests/test_fetcher.py::TestTextBodyDecoding` (text populated, html None,
  size bound respected); `tests/test_crawl_engine.py::TestLlmsTxtValidation`
  (valid file not flagged; adversarial garbage still flagged — both via real
  fetch_page + respx).

## Fix C — Page Priority "Refresh" misleading + no way to close
`PagePriorityPanel.jsx`: once ranked, the action is a subtle gray **Hide**
button that collapses the table via `setPages(null)`. `▶ Rank pages` (indigo)
returns for the initial/re-open state; `Ranking…` while loading. "Refresh"
removed.
- Test: `PagePriorityPanel.test.jsx` "shows a Hide control after ranking that
  collapses the table" (asserts no Refresh label, Hide collapses table, Rank
  pages returns).
