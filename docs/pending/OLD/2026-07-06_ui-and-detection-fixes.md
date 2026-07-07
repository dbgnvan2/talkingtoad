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

## Fix B.2 — llms.txt validation aligned to llmstxt.org (false positives on valid files)
Follow-on to Fix B. Even after the decode fix, the `engine.py` llms.txt check
(`else:` body-validation block) still false-positived on spec-valid files. Per
https://llmstxt.org the ONLY required element is a Markdown `# Title` H1; the
`>` blockquote summary, detail text, `##` link sections and link count are all
OPTIONAL (no cap). The old code wrongly required text/plain MIME + a `>`
blockquote + ≥1 URL and flagged >20 URLs. Real Yoast-generated files
(e.g. livingsystems.ca/llms.txt: H1 + plain-text summary + 14 `##` sections +
50 links, no blockquote, text/plain, leading UTF-8 BOM) were falsely flagged.
- Change: replaced the whole body-validation block with a single check —
  strip a leading UTF-8 BOM, then flag `LLMS_TXT_INVALID` only when there is no
  `^# \S` H1 line (soft-404 / non-Markdown). The `LLMS_TXT_MISSING` branch
  (status ≠ 200) is unchanged.
- `registry.py` `LLMS_TXT_INVALID` recommendation rewritten to state the spec
  (H1 required; `>` summary and `##` sections optional; no URL cap; ensure
  served as Markdown/plain text, not a soft-404). `docs/issue-codes.md`
  regenerated via `scripts/generate_issue_codes_doc.py`; `docs/thresholds.md`
  llms.txt row corrected (removed the "> 20 URLs → INVALID" rule).
- Tests (`tests/test_crawl_engine.py::TestLlmsTxtValidation`):
  `test_yoast_style_llms_txt_valid_no_blockquote_50_links` (regression: BOM +
  H1 + plain-text summary + 5 `##` sections + 50 links, text/plain → NOT
  flagged; exercises `.lstrip('﻿')`), `test_h1_only_no_links_no_blockquote_valid`
  (optional elements → valid), `test_soft_404_html_body_flagged_invalid`
  (adversarial: HTML no-`# ` body → INVALID), `test_missing_llms_txt_flagged_missing`
  (404 → MISSING, unchanged). The old "garbage still flagged" test was replaced —
  an H1-bearing body with no blockquote is now correctly VALID.

## Fix C — Page Priority "Refresh" misleading + no way to close
`PagePriorityPanel.jsx`: once ranked, the action is a subtle gray **Hide**
button that collapses the table via `setPages(null)`. `▶ Rank pages` (indigo)
returns for the initial/re-open state; `Ranking…` while loading. "Refresh"
removed.
- Test: `PagePriorityPanel.test.jsx` "shows a Hide control after ranking that
  collapses the table" (asserts no Refresh label, Hide collapses table, Rank
  pages returns).
