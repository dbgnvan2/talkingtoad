# QA Gate — non-HTML asset gate, final gate over the four-commit range (0c842ad)

**Gate date:** 2026-09-08 (third and final gate on this cycle)
**Range:** `origin/main..HEAD` = 4 commits:
  - `8afce81` fix(checkers): a PDF is not a page with a missing title
  - `31bdf95` docs: §4.18 — non-HTML responses are audited as assets, on every path
  - `d4e72d0` fix(rescan): asset size limits run on the router path too (gate NB-2)
  - `0c842ad` test: pin the size codes the agreement test could not see (gate r2)
**First gate:** `docs/cycles/2026-09-08_non-html-asset-qa-gate.md` — APPROVED (2-commit range), NB-2: the router path had gained `check_url_structure` but not `check_asset`.
**Second gate:** `docs/cycles/2026-09-08_non-html-asset-r2-qa-gate.md` — APPROVED (3-commit range), four non-blocking findings NB-1…NB-4.
**This gate:** final review of the full four-commit range, focused on `0c842ad` — the least-reviewed code in the range and all test code. Its claims were verified by executing the tests against live mutations of `api/routers/crawl.py`, not by reading them.
**Verdict: APPROVED.** NB-1, NB-2 and NB-3 are closed as claimed, and each closure test was proven to fail under the mutation it names. NB-4 is recorded in TODO.md (one record-accuracy nit, below — the entry's location list is wrong in one place, non-blocking). Spy restoration is sound: pytest's function-scoped `monkeypatch` fixture, verified in-process. Suite evidence matches the commit's claim exactly: 5581 backend (= 5577 + the 4 new tests), 396 frontend. Static scan clean. The only faults found are in the two debt records this commit wrote, not in code or tests.

## Paste-ready verdict block for Claude Code

```
QA GATE — non-HTML asset, final (8afce81 + 31bdf95 + d4e72d0 + 0c842ad):
APPROVED, no blocking findings. Push is fine.

0c842ad was verified by mutation, not by reading it — each closure test
was executed against a live edit of api/routers/crawl.py and went red
exactly as its commit message claims, then the file was restored:

1. NB-1 closed — nh8d really can see the gap nh8c could not. Deleting the
   check_asset call in _fetch_and_check_page (crawl.py:403-404) reds nh8d
   AND all three nh12 spies (4 failed). The 11 MB content-length fixture
   puts PDF_TOO_LARGE inside the compared set on both paths, with a
   guard assert ("PDF_TOO_LARGE in crawl_codes") proving the fixture
   trips the limit before the equality is compared.
2. NB-2 closed — one named test per call site, and no more. Removing the
   job.settings.img_size_limit_kb threading line at rescan_url reds only
   nh12 (1 failed, 2 passed — the other two spies are the in-run
   controls); at get_page_details reds only nh12b; at _run_single_page_scan
   reds only nh12c. The red is for the right reason: the failing assert
   shows the spy recorded [200] — the fallback default — against the
   asserted [512], i.e. the test reads the kwarg arriving at check_asset
   and pins the wiring, not the parameter.
3. Spy is properly restored. The fixture uses pytest's monkeypatch
   (function-scoped, auto-undo at teardown, guaranteed even on failure —
   the mutation runs above exercised exactly that). In-process probe: after
   nh8d/nh12/nh12b/nh12c ran in one process, api.routers.crawl.check_asset
   is the facade's function again (asserted, passed; probe deleted).
4. NB-3 closed — LEARNINGS.md fix-log entry present and accurate: records
   that d4e72d0 landed one check short of its own rule and why the 400-byte
   agreement fixture was blind to it.
5. NB-4 recorded in TODO.md as its own change. One accuracy nit in the
   record (non-blocking): the entry says "engine.py:110, engine.py:280 and
   registry.py:2614 each spell 200" — engine.py:110 holds no 200 literal
   (that is thresholds.md's stale pointer target; the field now lives at
   engine.py:280), and it omits the third real speller, api/models/job.py:51
   (Field(default=200)). Fix the list to "registry.py:2614, engine.py:280,
   api/models/job.py:51" and note engine.py:110 is the stale doc pointer.
   Also: the "Parked — needs a decision, not a fix (5)" header now holds 6
   items — bump the count.
6. Suite matches the claim: 5581 passed, 1 skipped, 2 deselected (196.4s),
   = 5577 + exactly the 4 new tests. Frontend 396/50, unchanged (no
   frontend code in range). Static scan of added .py lines: clean. No JSX
   in range -> nothing to lint.
```

## Evidence

| Check | Command | Result |
|---|---|---|
| Repo state | `git status -sb` / `git log --oneline origin/main..HEAD` | clean tree; exactly the 4 commits above; nothing else unpushed |
| Full suite | `./venv/bin/python -m pytest tests/ -p no:cacheprovider --tb=short -q` | **5581 passed, 1 skipped, 2 deselected** in 196.38s (exit 0) — matches the 0c842ad commit's own claim exactly |
| Frontend | `cd frontend && npx vitest run` | **396 passed (396)** / 50 files, 4.93s — unchanged (no frontend code in range) |
| Lint | changed files in range | no .js/.jsx/.ts/.tsx changed — nothing to lint |
| Static scan | added .py lines over the range, grepped for secrets/shell/eval/pickle/SQL f-strings | clean — zero hits |
| New tests baseline | `pytest -k "nh8d or nh12"` on the committed tree | 4 passed (nh8d, nh12, nh12b, nh12c) |
| Mutation m1 | check_asset call deleted (crawl.py:403-404) | **nh8d + nh12 + nh12b + nh12c red** (4 failed) |
| Mutation m2 | rescan_url threading line → registry default | **nh12 red only** (1 failed, 2 passed — controls) |
| Mutation m3 | get_page_details threading line → registry default | **nh12b red only** |
| Mutation m4 | _run_single_page_scan threading line → registry default | **nh12c red only** |
| Red-for-right-reason | m2 failure detail | `AssertionError: … the endpoint did not hand the job's own limit …: [200]` / `assert [200] == [512]` — spy recorded the fallback default |
| Spy restoration | in-process probe after the nh12/nh8d run | `crawl.check_asset is facade check_asset` asserted true (probe test deleted after; tree clean) |
| File restored | `git checkout` after each mutation + `git status --short` | empty after every round; suite ran on the pristine tree |

## Focus review — 0c842ad, claim by claim

- "`nh8d` declares 11 MB on both paths and asserts the fixture really trips the limit before comparing" — verified: `_crawl_with_pdf(pdf, content_length=_OVERSIZE)` (11 × 1024 × 1024, above `_PDF_SIZE_LIMIT` = 10 MB at registry.py:2613) on the crawl side vs `_rescan_with_length(…, _OVERSIZE)` on the router side, then `assert "PDF_TOO_LARGE" in crawl_codes` before the set-equality. Mutation m1 proves the equality is load-bearing: with `check_asset` gone from the router path, rescan_codes loses PDF_TOO_LARGE and the equality fails. This is exactly the gap r2's NB-1 said the 400-byte fixture could not see.
- "`nh12`/`nh12b`/`nh12c` intercept `check_asset` at each endpoint and read the kwarg" — verified. The interception works because crawl.py:40 imports `check_asset` into the module namespace and line 403 calls it as a bare module global (resolved at call time), so `monkeypatch.setattr(crawl_router, "check_asset", spy)` reaches the real call. The spy is transparent (calls the captured `real` with the same kwargs), so code under test behaves exactly as in production. Each test drives a genuinely different entry point: `rescan_url` (direct call), `get_page_details.__wrapped__` (bypasses slowapi/FastAPI wrappers down to the raw endpoint), `_run_single_page_scan` — and each asserts the exact single-call list `[512]` / `[768]` / `[384]`, so a second `_fetch_and_check_page` pass through the same endpoint would also fail the test. Mutations m2/m3/m4 prove each of the three call sites has exactly one named test.
- "Verified by deleting each threading line in turn: one named test red per mutation, restored from the verbatim original" — independently reproduced, see evidence. The commit message's mutation map is honest: m1 reds 4, m2/m3/m4 red exactly one each, controls green.
- Spy restoration — the fixture takes pytest's `monkeypatch` (function-scoped, undo at teardown even on failure; the mutation runs are themselves proof the teardown path works under red tests). In-process probe confirmed `crawl.check_asset` is the facade function again after the nh12 tests ran; probe removed.
- "NB-3: the LEARNINGS entry now records…" — verified, LEARNINGS.md fix-log entry present, correctly worded, sits inside the existing 2026-09-08 entry as an appended bullet. NB-4 recorded in TODO.md "Parked" with the NB-4 attribution and rationale — see the one accuracy nit below.
- "Full suite green: 5581 passed" — reproduced exactly.

## Static scan (added lines, .py files over the full range)

No hardcoded secrets/credentials, no `os.system`/`shell=True`/`subprocess`, no `eval`/`exec`, no `pickle`, no SQL built via f-string `execute(`/`executemany(`. 0c842ad adds test code and docs only; the range's .py additions are the fix code already scanned clean in the r2 gate. Clean.

## Workflow compliance

- Micro-spec first: same standing deviation as r2 — no `docs/pending/` file for this cycle. 0c842ad is a gate-NB closure over a fold the gate itself produced; the record lives in the two gate files, the commits, and the §4.18 amendment. Defensible, unchanged.
- Spec folded: yes — §4.18 amended in `functional-specification.md` by 31bdf95 (reviewed in r2); 0c842ad adds no spec text.
- thresholds.md: untouched over the range — correct. NB-4 deliberately not swept in because it moves a documented threshold; recorded in TODO.md instead, matching the constraint.
- Parity: no registry/catalogue/scoring change in range → no issueHelp.js / issue-codes.md churn owed; parity tests green inside the 5581.
- LEARNINGS.md: fix-log entry added by 0c842ad (NB-3 closure). TODO.md: NB-4 entry added by 0c842ad.
- GUI / WP safety / auth: untouched.
- Commit discipline: worktree clean at gate time except this gate file (untracked); `origin/main..HEAD` = the four reviewed commits, nothing else unpushed. Both prior gate files travelled inside the range commits (the r2 file inside 0c842ad itself); this final gate file awaits the push commit per the standing per-item workflow.

## Non-blocking observations

- **NB (record accuracy, in this commit's TODO entry):** the NB-4 entry says "`engine.py:110`, `engine.py:280` and `registry.py:2614` each spell 200". Verified: the three real literal spellers are `registry.py:2614` (`_IMAGE_SIZE_LIMIT_KB = 200`), `engine.py:280` (`CrawlSettings.img_size_limit_kb: int = 200`) and `api/models/job.py:51` (`Field(default=200, ge=10, le=10_000)`). `engine.py:110` holds no 200 literal (comment + PIL import block) — it is the stale `thresholds.md:87` pointer target; `engine.py:119`'s 200 is `_MIN_CRAWL_DELAY_MS`, unrelated. The entry swaps the stale pointer in for the model field r2's NB-4 explicitly named. The debt itself and its proposed cure are correctly described, so nothing blocks — but a future engineer removing "the three literals" would look at engine.py:110, find nothing, and leave the job.py:51 copy (the one the TODO proposes to live-link) in place. One-line fix: `engine.py:280`, `api/models/job.py:51` and `registry.py:2614` each spell 200; `thresholds.md:87`'s pointer at `engine.py:110` is stale (the engine field it names now lives at `engine.py:280`).
- **NB (doc nit, same commit):** the "## Parked — needs a decision, not a fix (5)" header now holds 6 open items — the count wasn't bumped. Same one-line fix as above would carry it.
- Carried from r2, still open by design: first gate's `FastAPIDeprecationWarning` (regex= → pattern=) and slowapi/fpdf deprecation warnings appeared again in this run; not introduced by this range.

## State

Working tree clean at gate time except this gate file (untracked). `origin/main..HEAD` = the four reviewed commits; **nothing has been pushed** — the cycle awaits `git push origin main` per the standing per-item workflow. No DB edits made or recommended; re-running the re-check on affected stored jobs remains the documented correction path for job 52a5aa00's six URLs (unchanged from both prior gates). Mutation testing edited `api/routers/crawl.py` four times and restored it from the committed original after each round; final tree verified clean before the full suite ran.
