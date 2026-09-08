# QA Gate — non-HTML asset gate (8afce81 fix + 31bdf95 fold)

**Gate date:** 2026-09-08
**Range:** `origin/main..HEAD` = 2 commits:
  - `8afce81` fix(checkers): a PDF is not a page with a missing title
  - `31bdf95` docs: §4.18 — non-HTML responses are audited as assets, on every path
**Gate type:** independent (Hermes, fresh context — no agent verifies its own work)
**Cycle shape:** owner-reported bug (six PDFs reported blank on job 52a5aa00) → in-session diagnosis → fix + tests in one commit, spec folded into `functional-specification.md` §4.18 in the second. The spec-review round-trip commits that usually precede an item (r1–r5 style) are absent for this cycle; see observation NB-1.
**Verdict: APPROVED** — no blocking findings. The gate now lives in `check_page` itself and is correctly reachable from every path; the three defects named in the commit message are each real, each fixed, and each pinned by a test; both suites green at HEAD (5573 passed backend, 396 passed frontend); static scan clean; docs fold accurate. Two non-blocking observations, one of them worth taking into the next cycle: the router rescan path still does not run `check_asset`, so file-size findings (`PDF_TOO_LARGE` / `IMG_OVERSIZED`) remain crawl-path-only and §4.18's "whichever path reached it" sentence over-promises for them (NB-2).

## Paste-ready verdict block for Claude Code

```
QA GATE — non-HTML asset gate (8afce81 + 31bdf95): APPROVED, no blocking
findings. Push is fine. Verified independently, not on the commit
message's word:

1. Gate placement is real. is_non_html_response() sits at the top of
   check_page (issue_checker.py) and returns _check_non_html_page(), so
   the crawl engine AND every _fetch_and_check_page caller (rescan-url,
   recheck-all, page-details, scan-page) inherit it. parse_page now
   carries content_type + is_html_response on ParsedPage; the fetcher
   already lower-cases and parameter-strips Content-Type (fetcher.py:318),
   so the predicate is fed clean input. 20+ hand-built ParsedPage helpers
   in other tests pass neither field -> defaults keep full-suite
   behaviour, so the change is inert on every pre-existing test shape.
2. The predicate's two edges are correct: an HTML content type keeps the
   full suite on an empty body (genuinely text-free HTML still reports
   CONTENT_NOT_EXTRACTABLE_NO_TEXT - nh10), and an unset content type on
   a record with no parsed HTML is NOT audited as a page (nh5b, the
   typeless-woff2 case). "Can only remove checks from a response that
   was not HTML" holds.
3. DOCUMENT_PROPS_MISSING is revived on the real crawl path: engine's
   asset branch now calls check_page (engine.py ~955), which the AF5 fix
   from August never reached. Keyed on parsed pdf_metadata, not the .pdf
   suffix, so an extension-less attachment URL that 301s to a PDF fires
   (nh3c) - verified: 4 findings for 5 PDFs matches the parsed-metadata
   keying, not the suffix test.
4. URL-structure checks now run on the router path
   (_fetch_and_check_page, crawl.py:394) where they never ran, closing
   the P1/P6 deletion: recheck-all had deleted URL_UPPERCASE findings and
   written them to fixed_issues as RESOLVED without evaluating them. The
   D2 single-page-scan disclosure derives from the registry's
   needs_full_crawl flag, and URL_UPPERCASE is not in it, so scan-page
   inheriting the checks stays consistent with its declared coverage.
5. No new issue codes, no scoring change, no numeric thresholds -> no
   registry/issueHelp/issue-codes parity churn (suite parity tests
   green). 4xx non-HTML asset path still emits status-only (broken-link
   evidence preserved, engine ~855-877). Unknown binaries now pass
   check_asset, but its checks are content-type-keyed (pdf/image only),
   so videos/fonts still yield nothing.
6. Tests: tests/test_non_html_asset_checks.py - 18 cases; the claimed
   five mutations are not independently reproducible from the artifacts
   (in-session runs), but each behaviour they would protect is pinned by
   a named test (nh1/nh2 gate, nh3c metadata keying, nh7 crawl wiring,
   nh9 url-structure, nh8c dual-path agreement).

Full suite: 5573 passed, 1 skipped, 2 deselected (integration), 196s.
Frontend: 396 passed / 50 files. Static scan of added lines: clean.
Lint: no JS/TSX changed in this range - nothing to lint.

Non-blocking, take into the next cycle:
- NB-2 (recommended follow-up): the router paths never call check_asset,
  so PDF_TOO_LARGE / IMG_OVERSIZED are crawl-only. A recheck-all over an
  oversized PDF still drops the size finding - the same path-disagreement
  class this fix just closed for URL_UPPERCASE. §4.18's rule sentence
  ("file size (check_asset) ... whichever path reached it") promises more
  than _fetch_and_check_page delivers; nh8c's agreement test cannot see
  it because the fixture PDF is small. Fix is one call -
  check_asset(result, ...) in _fetch_and_check_page - plus a size-code
  agreement test, or amend the §4.18 sentence.
- NB-1 (process): this cycle has no docs/pending micro-spec file in git
  history - the spec exists only as the §4.18 fold written in the same
  batch as the code. Owner-reported triage with in-session approval
  plausibly happened; the repo trail still lacks the pre-code artifact
  CLAUDE.md prescribes. Either commit a lightweight pending record for
  owner-triage fixes or say so explicitly in CLAUDE.md.
```

## Evidence

| Check | Command | Result |
|---|---|---|
| Repo state | `git status` / `git log --oneline origin/main..HEAD` | clean tree; exactly the 2 commits above; nothing else unpushed |
| Full suite | `./venv/bin/python -m pytest tests/ -p no:cacheprovider --tb=short -q` | **5573 passed, 1 skipped, 2 deselected** in 196.19s (exit 0) — matches the fix commit's own claim |
| New-file suite | `pytest tests/test_non_html_asset_checks.py tests/test_pdf_metadata.py` | 23 passed (18 new + 5 pdf_metadata regression) in 2.48s |
| Frontend | `cd frontend && npx vitest run` | **396 passed (396)** / 50 files, 5.17s |
| Lint | changed files in range | no .js/.jsx/.ts/.tsx changed — nothing to lint (pre-existing SummaryPanel.jsx warning unaffected) |
| Static scan | `git diff origin/main..HEAD` added lines grepped | clean: no secrets/keys, no os.system/shell=True/subprocess, no eval/exec/pickle, no SQL f-string execution (`execute(f`) |
| Fix-vs-spec | code read at named lines vs §4.18 text | every §4.18 claim verified (details below) |
| Workflow | pending file history, parity, thresholds | no new codes/scoring/thresholds; parity suite green; §4.18 + §10.2 folded; architecture.md 6g updated; LEARNINGS.md item 31 + fix-log entry; TODO.md parking entry added |

## Diff vs micro-spec (§4.18), claim by claim

- "The gate now lives in `check_page` itself" — verified: `is_non_html_response()` returns `_check_non_html_page(page)` before any HTML work in `check_page` (issue_checker.py:338-347). Engine's HTML branch and the router's `_fetch_and_check_page` both call `check_page`; no other caller needed a change.
- Predicate semantics (content-type not HTML; OR no content-type AND no HTML body parsed) — verified in code and by nh4 (with/without CT identical on HTML), nh5 (hand-built page keeps suite), nh10 (empty HTML body still flagged), nh5b (typeless binary not audited as page). `parse_page` non-HTML branch sets `is_html_response=False`; HTML branch `True`; default `True` keeps ~20 hand-built `ParsedPage` fixtures across the suite behaviour-identical (verified: none of them set `content_type`).
- "59 of the 63 findings false" — consistent with `HTML_ONLY_CODES` (11 codes) × six URLs minus legit findings; DOCUMENT_PROPS_MISSING deliberately absent from the set. Not independently recounted from the live job (DB row count not re-derived), but the mechanism is fully reproduced in tests.
- Engine branch revived `check_page` for assets — verified engine.py merged non-HTML branch (check_asset + check_page under try/except); nh7 proves DOCUMENT_PROPS_MISSING now fires on a real `run_crawl`.
- `DOCUMENT_PROPS_MISSING` keys on parsed PDF metadata, not `.pdf` suffix — verified: `_pdf_document_property_issues` reads `page.pdf_metadata` (populated by parse_page only when content type contains "pdf" — AF5 location preserved above the early return); old suffix test deleted. nh3c pins the extension-less 301-to-PDF case.
- Router path runs URL-structure checks — verified crawl.py:394; nh9 (PDF), nh9b (HTML mixed-case). Engine's crawl-side equivalent confirmed at engine.py:749 (pre-fetch, every frontier URL). D2 single-page-scan disclosure derives from registry `needs_full_crawl` (crawl.py:483-493) — URL_UPPERCASE not in it, so no disclosure drift; the binding test is in the green suite.
- "An HTML type keeps the full suite even on an empty body" — nh10. Edge verified consistent: a `text/html` empty body that falls to parse_page's non-HTML branch still has a content type, and the predicate lets the content type win → full suite → CONTENT_NOT_EXTRACTABLE_NO_TEXT. Both engine and router reach the same answer.
- HTML 4xx / non-HTML 4xx error handling unchanged — verified engine.py ~840-885: broken-link evidence preserved, asset-branch 4xx continues with `page_issues = []`.
- No new codes / thresholds — registry, issueHelp.js, issue-codes.md, thresholds.md all untouched in range; no numeric bounds introduced by the change.

## Static scan (added lines, full range diff)

No hardcoded secrets/credentials, no `os.system`/`shell=True`/`subprocess`, no `eval`/`exec`, no `pickle`, no SQL built via f-string `execute(`/`executemany(`. The new code constructs no SQL at all (the only query-touching change is the added `check_url_structure(url)` call, which is pure string logic). Clean.

## Workflow compliance

- Micro-spec first: **deviation — NB-1.** No `docs/pending/` file was ever created or deleted for this cycle (verified over full git history with `--diff-filter=A/D` on `docs/pending/`). The spec exists only as the §4.18 fold, committed in the same batch as the implementation.
- Spec folded: yes — §4.18 added to `functional-specification.md` with the limitation recorded in §10.2 (PDF content/AI-readiness "not evaluated, which is not the same as passing"). Pending-file deletion: N/A (no file existed).
- thresholds.md: untouched — correct, no numeric bounds changed.
- Parity: no registry/catalogue change → no issueHelp.js/issue-codes.md churn needed; suite parity tests green.
- LEARNINGS.md: checklist item 31 (reachability, not fields) + full fix-log entry (2026-09-08) with patterns P16/P1/P6/P13/P31. TODO.md: PDF body-text extraction parked under "needs a decision" with the decision it needs stated. architecture.md: crawl step 6g updated to name the gate's location and why it is in `check_page`.
- GUI / WP safety: untouched. Auth: untouched.
- Commit discipline: worktree clean at gate time; only the 2 cycle commits unpushed.

## Non-blocking observations

- **NB-1 (process):** no committed pre-code micro-spec for this cycle (see above). The owner was the reporter and the fix narrative shows in-session engagement, so substantive approval plausibly occurred; the gate cannot see chat. Recommendation: for owner-reported triage fixes, still write a short `docs/pending/YYYY-MM-DD_*.md` before code (even if approval is conversational), or amend CLAUDE.md's micro-spec-first rule to name the owner-triage fast path explicitly — otherwise the repo trail silently loses the spec-before-code step this rulebook exists to enforce.
- **NB-2 (code, recommended follow-up — same failure family the fix just closed):** `check_asset` is not called anywhere in `api/routers/crawl.py` (grep: zero references), so `_fetch_and_check_page` — recheck-all, rescan, page-details, scan-page — never evaluates `PDF_TOO_LARGE` / `IMG_OVERSIZED`. The crawl does (engine.py asset branch). A recheck-all over an oversized PDF therefore still deletes the size finding the crawl produced and records it as resolved — precisely the P1/P6 mechanism fixed here for URL_UPPERCASE, still open for size codes. Pre-existing (the router path never ran check_asset), not a regression, and outside the reported 63 — but §4.18's rule sentence reads "file size (check_asset) … whichever path reached it", which the router path does not deliver, and the dual-path agreement test nh8c cannot detect it because its fixture PDF is ~1 KB. Fix: one `check_asset(result, img_size_limit_kb=…)` call in `_fetch_and_check_page` plus a dual-path agreement assertion that includes a size code (e.g. a >10 MB mock PDF), or narrow the §4.18 sentence to say file size is checked on the crawl path.
- Mutation claim ("five mutations … each red") is an in-session record and not independently reproducible from the repo artifacts; the 18 tests + green suite are the reproducible evidence, and each claimed mutation's protection maps to a named test (nh1/nh2, nh3c, nh7, nh9, nh8c).
- Pre-existing `FastAPIDeprecationWarning` (`regex=` → `pattern=`, crawl.py:3481) surfaced in the run; not introduced by this range.

## State

- Working tree clean at gate time. `origin/main..HEAD` = the two reviewed commits; **nothing has been pushed** — the item awaits `git push origin main` per the standing per-item workflow. Re-running the re-check on affected stored jobs (job 52a5aa00 and its siblings) is the documented correction path for the six corrupted URLs; no DB edits were made and none are recommended.
