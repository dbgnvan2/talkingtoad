# QA Gate — non-HTML asset gate, re-gate after NB-2 fix (d4e72d0)

**Gate date:** 2026-09-08 (second gate on this cycle)
**Range:** `origin/main..HEAD` = 3 commits:
  - `8afce81` fix(checkers): a PDF is not a page with a missing title
  - `31bdf95` docs: §4.18 — non-HTML responses are audited as assets, on every path
  - `d4e72d0` fix(rescan): asset size limits run on the router path too (gate NB-2)
**First gate:** `docs/cycles/2026-09-08_non-html-asset-qa-gate.md` — APPROVED over the
two-commit range, with NB-2: the router path had gained `check_url_structure` but not
`check_asset`, so `PDF_TOO_LARGE` / `IMG_OVERSIZED` stayed crawl-only and §4.18's
"whichever path reached it" over-promised for them.
**This gate:** re-review of the full three-commit range, focused on `d4e72d0` — the
least-reviewed code in the range is the fix commit itself (no agent verifies its own work,
and NB-2 was the first gate's own finding).
**Verdict: APPROVED** — NB-2 is fixed as claimed, verified in code, not on the commit
message's word. `check_asset` now runs in `_fetch_and_check_page` (crawl.py:403-404) and
every router entry point threads the job's own `img_size_limit_kb` from the same stored
settings the crawl reads. Suite evidence matches the commit's claim exactly: 5577 backend
(= 5573 + the 4 new tests), 396 frontend. Static scan clean. §4.18's amendment is
substantively accurate. Four non-blocking observations, the first two in the same
"test cannot see the code" family this cycle has been closing.

## Paste-ready verdict block for Claude Code

```
QA GATE — non-HTML asset re-gate (8afce81 + 31bdf95 + d4e72d0): APPROVED, no
blocking findings. Push is fine. The d4e72d0 NB-2 fix was verified
independently, not on the commit message's word:

1. check_asset runs on the router path now, for real. It is appended after
   check_url_structure inside _fetch_and_check_page (crawl.py:403-404), the
   shared core behind ALL four entry points: rescan_url (1791), page-details
   (2118), scan-page via _run_single_page_scan (2344), and recheck-all, whose
   worker calls rescan_url per URL (2745). Import is through the facade
   (issue_checker.py:54 re-exports check_asset), not a raw module import.
2. The job's OWN limit is threaded, not the module default. Each direct call
   site passes `job.settings.img_size_limit_kb if job.settings else
   _IMAGE_SIZE_LIMIT_KB`; the parameter default is the registry constant
   (crawl.py:255). The crawl reads the identical stored value into
   EngineCrawlSettings (crawl.py:1190) and passes it at engine.py:955 — so a
   job configured to 1 MB is judged at 1 MB on both paths, and a re-check of
   an oversized PDF now keeps PDF_TOO_LARGE instead of dropping it like it
   dropped URL_UPPERCASE.
3. Inert on HTML, asserted not assumed: check_asset's two branches are
   content-type-gated ("pdf" in ct / ct.startswith("image/"), images.py:47-53).
   nh11d drives an 11 MB-declared text/html page through the router path and
   asserts neither size code fires. No double-report risk: check_page and
   check_asset produce disjoint code sets.
4. Four tests, mutation mapping clean: nh11 (router path reports an oversized
   PDF) + nh11b (oversized image) go red if the call is removed; nh11c (900 KB
   image under a 1024 KB caller limit -> no finding) goes red if the caller's
   limit is ignored for the 200 KB default. The content-length-header fixture
   (11 MB declared, ~400-byte body) is sound: check_asset reads the header,
   never the body.
5. Suite matches the claim: 5577 passed, 1 skipped, 2 deselected (188.9s),
   = 5573 + exactly the 4 new tests. Frontend 396/50 (unchanged — no frontend
   code in range). Static scan of added .py lines: clean. No JSX in range ->
   nothing to lint.
```

Non-blocking, take into the next cycle:
- NB-1 (top): the amended §4.18 sentence leans on nh8c — "asserts the whole
  finding set is identical between a crawl and a re-check of the same URL" —
  and nh8c's fixture is still the 400-byte PDF whose finding set contains no
  size code. The commit message itself names that 400-byte fixture as the
  reason the first-half agreement test could not see the missing check_asset,
  and the fixture was not changed. The sentence is literally true (nh8c does
  assert full-set equality, over its fixture) but unexercised for the very
  codes this commit adds. Per-path evidence is solid (nh11/nh11b on the
  router; engine-side check_asset pre-existing + unit-covered) and the value
  threading is code-verified, so the invariant holds today — but one fixture
  change (an >10 MB PDF with a matching content-length) would make nh8c's
  equality meaningful for PDF_TOO_LARGE on both paths and retire this
  observation for good.
- NB-2: nh11c pins the _fetch_and_check_page parameter (it passes
  img_size_limit_kb=1024 explicitly), not the three call sites' job-settings
  threading. Delete the `job.settings.img_size_limit_kb` line at any one call
  site and all four nh11 tests stay green. Wiring is verified present at all
  three sites and inherited by recheck-all, so the permanent pin is an
  endpoint-level test: a stored job with settings.img_size_limit_kb=1024,
  rescan of a 900 KB image -> no IMG_OVERSIZED.
- NB-3 (process): no LEARNINGS.md fix-log entry for d4e72d0. The 2026-09-08
  entry (added by 31bdf95) predates the fix and covers only the first half.
  The new lesson is this file's own genre: the fix landed one check short of
  its rule, and the agreement test with a sub-threshold fixture could not see
  it — agreement fixtures must sit above the threshold of the code under
  test. One appended sentence to the existing entry closes it.
- NB-4 (pre-existing, surfaced by this commit): the 200 KB default is literal
  in three code places — registry.py:2614 (_IMAGE_SIZE_LIMIT_KB, "default,
  overridable per job"), api/models/job.py:51 (Field default=200),
  api/crawler/engine.py:280 (dataclass default) — while docs/thresholds.md:87
  locates the value at engine.py:110 (stale line, and it names the engine
  field, not the registry constant this commit made authoritative on the
  router). The sibling page_size_limit_kb escaped this class via a live-link
  default_factory and a patch test (engine.py ~283-290, P8.3); img_size_limit
  _kb has three literals and no live-link test. All equal at 200 today; the
  new code did the right thing (imports the registry constant for the router
  default) — the two model defaults are the remaining copies.

## Evidence

| Check | Command | Result |
|---|---|---|
| Repo state | `git status -sb` / `git log --oneline origin/main..HEAD` | clean tree; exactly the 3 commits above; nothing else unpushed |
| Full suite | `./venv/bin/python -m pytest tests/ -p no:cacheprovider --tb=short -q` | **5577 passed, 1 skipped, 2 deselected** in 188.86s (exit 0) — matches the d4e72d0 commit's own claim exactly |
| Frontend | `cd frontend && npx vitest run` | **396 passed (396)** / 50 files, 4.94s — unchanged from the first gate (no frontend code in range) |
| Lint | changed files in range | no .js/.jsx/.ts/.tsx changed — nothing to lint |
| Static scan | `git diff origin/main..HEAD -- '*.py'` added lines grepped | clean: no secrets/keys, no os.system/shell=True/subprocess, no eval/exec/pickle, no SQL f-string execution; the two grep hits in the full-range scan were the first gate file's own "clean" prose, excluded by the .py filter |
| Fix-vs-NB-2 | code read at named lines vs the first gate's NB-2 | every NB-2 element verified (details below) |
| Workflow | pending history, parity, thresholds, LEARNINGS | no new pending file (fix amends the live §4.18 — NB-1 of the first gate still applies to the cycle as a whole); no registry/catalogue/scoring change -> no parity churn; thresholds.md untouched (no numeric change); LEARNINGS fix log lacks a d4e72d0 entry (NB-3) |

## Diff vs NB-2, claim by claim (d4e72d0)

- "`check_asset` now runs alongside `check_page` on the router path" — verified:
  crawl.py:403-404 appends `check_asset(result, img_size_limit_kb=img_size_limit_kb)`
  in `_fetch_and_check_page`, after the `check_url_structure` line the first half
  added. Reachability traced to all four entry points: `rescan_url` (crawl.py:1791),
  `get_page_details` (2118), `_run_single_page_scan` behind scan-page (2344), and the
  recheck-all worker, which calls `rescan_url` per stored URL (2745) — so recheck-all
  inherits the fix with no change of its own. Import comes through the facade
  (issue_checker.py:54), consistent with the facade rule; `check_asset` produces only
  PDF_TOO_LARGE / IMG_OVERSIZED, disjoint from every `check_page` code, so appending
  after `check_page` cannot double-report.
- "against the job's own `img_size_limit_kb` rather than the module default" — verified
  at all three direct call sites (crawl.py:1796-97, 2129-30, 2350-52), each reading
  `job.settings.img_size_limit_kb` with the registry constant as the None-settings
  fallback; `_fetch_and_check_page`'s parameter default is the registry constant
  (crawl.py:255), so an unthreaded future caller falls back to the same value the job
  model defaults to (job.py:51 = 200). Same-source consistency with the crawl: the crawl
  start copies `settings.img_size_limit_kb` into `EngineCrawlSettings` (crawl.py:1190)
  and the engine's asset branch passes it through at engine.py:955. A job configured to
  1024 KB is judged at 1024 KB on both paths.
- "a job configured to 1 MB must not have its 900 KB image flagged by a path that assumed
  200 KB" — this is nh11c's exact scenario (900 KB image, `img_size_limit_kb=1024`,
  asserts no IMG_OVERSIZED); red under the "job's limit ignored" mutation because 900 KB
  > 200 KB default.
- "Inert on HTML: `check_asset` only fires for a PDF or image content type, asserted
  rather than assumed (nh11d)" — verified in code (images.py:47-53 content-type gates)
  and by nh11d, which pushes an 11 MB-declared `text/html` page through the router path
  and asserts neither size code appears. This also closes the double-report question for
  HTML pages, whose size business is PAGE_SIZE_LARGE's.
- "Four tests, two mutations (the call removed; the job's limit ignored), each red on the
  test that names it" — mutation mapping is clean and reproducible from the tests alone:
  removing the call reds nh11 and nh11b; ignoring the caller's limit (using the default)
  reds nh11c. The content-length-header fixture (11 MB declared over a ~400-byte body)
  is a sound choice — `check_asset` reads `result.headers["content-length"]`, never the
  body — and keeps the fixture small while sitting above `_PDF_SIZE_LIMIT` (10 MB).
- "Full suite green: 5577 passed" — reproduced: 5577 passed (+4 over the first gate's
  5573, exactly the four new tests).

## §4.18 amendment accuracy

The fold (functional-specification.md, 10 lines) names the size codes and the job's own
limit, records that the first-half gate caught the missing `check_asset`, and states both
check families now run on both paths. All true in code. The one imprecision is the final
sentence's reliance on nh8c's agreement assertion without an above-threshold fixture —
see NB-1. No new numeric bounds, so no thresholds.md churn is owed.

## Static scan (added lines, .py files over the full range)

No hardcoded secrets/credentials, no `os.system`/`shell=True`/`subprocess`, no
`eval`/`exec`, no `pickle`, no SQL built via f-string `execute(`/`executemany(`. The new
code constructs no SQL; the only new imports are `check_asset` (facade) and
`_IMAGE_SIZE_LIMIT_KB` (registry) into crawl.py. Clean.

## Workflow compliance

- Micro-spec first: **deviation, unchanged from the first gate (NB-1 there).** No
  `docs/pending/` file exists for this cycle; the d4e72d0 fix amends the already-folded
  §4.18 rather than opening a new spec. For a gate-NB fix of a fold the gate itself
  produced, this is defensible — the record lives in the gate file, the commit, and the
  §4.18 amendment — but the CLAUDE.md trail still shows no pre-code artifact.
- Spec folded: yes — §4.18 amended in `functional-specification.md` with the gate's role
  and the resolution recorded in the spec text itself. First gate's §10.2 limitation
  statement untouched and still accurate.
- thresholds.md: untouched — correct, no numeric bounds changed (200 KB default is
  unchanged). Pre-existing staleness surfaced instead: the thresholds row's location
  pointer says engine.py:110 (see NB-4).
- Parity: no registry/catalogue/scoring change in range -> no issueHelp.js / issue-codes.md
  churn owed; suite parity tests green within the 5577.
- LEARNINGS.md: no new fix-log entry for d4e72d0 (see NB-3). TODO.md: untouched by
  d4e72d0 (the PDF body-text parking entry from 31bdf95 still stands).
- GUI / WP safety / auth: untouched.
- Commit discipline: worktree clean at gate time; `origin/main..HEAD` = the three reviewed
  commits, nothing else unpushed. The first gate file travelled inside d4e72d0; this
  re-gate file is written after the fact and awaits the push commit, per the standing
  per-item workflow.

## Non-blocking observations

- **NB-1 (code/test — the one to take next):** nh8c's agreement fixture is still 400
  bytes, so the "whole finding set identical" assertion §4.18 now leans on does not
  exercise the size codes this commit added — the same sub-threshold-fixture blind spot
  the commit message identifies as the reason the first-half test missed the gap. One
  fixture change (an above-10-MB PDF with a matching content-length header) makes the
  equality load-bearing for PDF_TOO_LARGE on both paths.
- **NB-2 (test depth):** the job-settings threading at the three call sites is
  code-verified but not endpoint-pinned; nh11c exercises the parameter, not the
  `job.settings.img_size_limit_kb` reads. An endpoint-level rescan test against a stored
  job with a non-default limit would pin the wiring this fix is actually about.
- **NB-3 (process):** LEARNINGS.md has no fix-log entry for a real bug this commit fixed
  (re-check dropped PDF_TOO_LARGE / IMG_OVERSIZED). The repo rule says fix-log entries
  follow real bugs; the 2026-09-08 entry covers only the first half of this saga.
- **NB-4 (pre-existing, surfaced):** `img_size_limit_kb` default 200 is literal in three
  code places and thresholds.md's pointer for it is stale (engine.py:110; the live
  sources are registry.py:2614 — which this commit made the router's default — plus the
  two model literals). The sibling `page_size_limit_kb` shows the repo's own cure
  (live-link factory + patch test, P8.3); applying it to `img_size_limit_kb` would make
  the copies visible when they drift.
- First gate's pre-existing `FastAPIDeprecationWarning` (regex= -> pattern=) and the fpdf
  Arial/ln deprecation warnings appeared again in this run; not introduced by this range.

## State

Working tree clean at gate time except this gate file (untracked). `origin/main..HEAD` =
the three reviewed commits; **nothing has been pushed** — the cycle awaits
`git push origin main` per the standing per-item workflow. No DB edits made or recommended;
re-running the re-check on affected stored jobs remains the documented correction path for
job 52a5aa00's six URLs (unchanged from the first gate's state).
