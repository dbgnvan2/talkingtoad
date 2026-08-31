# Learnings — TalkingToad (failure patterns & fix log)

> **What this is:** institutional memory of how *this* codebase has failed, so the same
> **class** of bug is caught in review instead of production. After fixing any real bug,
> add a **Fix log** entry and, if it's a new generic pattern, fold it into the global
> catalogue (below).
>
> **Generic pattern catalogue + full review checklist live globally** at
> `~/.claude/standards/learnings.md` (auto-loaded by Claude Code for every repo). This file
> keeps the **TalkingToad-specific** open risks and fix log, plus an inline copy of the
> checklist for convenience. Read the checklist before reviewing or writing any
> **checker, fetch, scoring, or report** code.

---

## Review checklist (run before merging checker / fetch / scoring / report changes)

1. **External calls (P5):** does every outbound call (`fetcher.py`, robots, sitemap, external-link
   check, image check, AI/LLM via `AIRouter`, future PageSpeed API) go through `is_ssrf_safe()`
   and have timeout + retry/backoff? Are *all siblings* hardened, not just the one in scope?
2. **Failure visibility (P2):** on partial failure, is anything logged/counted, or does data
   silently vanish? Can "found nothing" be told apart from "the call failed"?
3. **Transient vs terminal (P1):** is a retryable failure (429, timeout, bot-block) being written
   as a permanent negative (`is_broken`, `not_available`)? Keep the "unverified" path for
   bot-blocked hosts (LinkedIn/FB/IG).
4. **Scope completeness (P3):** have all sources/locations been enumerated? (JSON-LD in `<body>`
   not just `<head>`; `@graph` nesting; nested/gzip sitemaps; all heading sources; every page type)
5. **Hardcoded assumptions (P4):** any literal year/date/threshold/topic-word in logic that belongs
   in `docs/thresholds.md` / config? (The catalogue's `_ISSUE_SCORING` and thresholds are the home
   for numbers — not inline magic.)
6. **Ground-truth check (P6):** is a status trusted without verifying the artifact? A WP fix marked
   "applied" must be re-verified against the live page (re-scan), not assumed.
7. **Scoring adversarial test (P7):** what input scores high for the *wrong* reason? Does the Health
   Score / Agent-Readiness Score move monotonically (more failures ⇒ never a higher score)?
8. **Dirty-state / second-run (P8):** does this read state that persists between crawls (prior job
   rows, Performance Ledger, cached results, re-applied fixes)? Is there a test that pre-populates
   that state and asserts the feature ignores prior-run content / is idempotent?
9. **Input starvation / size caps (P9):** for every cap in a data path (500-page crawl, 50
   ext-links/page, 500/job, 200 images/job, 50 query-variants/path, 300 KB HTML, the 1500-word GEO
   window, AI token/excerpt budgets): on a *real, large* site, what fraction of input survives? Is
   the drop announced ("N of M")? Are test fixtures big enough to make the cap actually bite?
10. **Fix→test map (P10):** does each fix in the change map to a test? Is the *highest-impact /
    most-likely-to-regress* fix tested FIRST, not just the easy constant-membership ones? Are
    genuine integration paths (live HTTP, WP API, LLM) flagged as untested rather than implied covered?
11. **Architecture constraints:** a scan must never call the WP API; catalogue ↔ `issueHelp.js` ↔
    scoring ↔ confidence-label parity holds for every new code; serialization includes every field
    the frontend reads.
12. **Absence over a narrowed population (P31):** does the check conclude *nothing* links to /
    mentions / references this? That is only decidable over the whole site. Can `scope_urls` (partial
    scan), `max_pages`, a cancellation, `skip_wp_archives`, or a fetch failure shrink the page set it
    reasons over — and is it told? **Does narrowing the scan raise the finding count?** Thread
    completeness in as data, and report the suppressed state as "skipped, covered N of M" — never as
    zero, which every surface renders as a clean bill of health.

> Pattern definitions (P1–P10) and the reasoning behind each item: `~/.claude/standards/learnings.md`.

---

## Open risks (found by review, not yet bitten)

- **`RedisJobStore` is unexercised code, and several docs assert it is production.** The owner
  has never configured Upstash; `get_job_store()` returns Redis only when
  `UPSTASH_REDIS_REST_URL` **and** `UPSTASH_REDIS_REST_TOKEN` are both set, so it has always
  returned SQLite (startup log: `sqlite_store: job_store_init`). Verified divergences, all
  currently dormant: **10 public methods exist on SQLite and not on Redis** (including
  `get_exempt_anchor_url_set`, called unconditionally at `crawl.py:443` in `run_crawl_task` —
  every crawl would raise `AttributeError` on Redis); **10 `CrawlJob` fields are write-only** —
  `update_job` persists them and `_mapping_to_job` never reads them back, so `phase` returns
  `'queued'` and the whole `robots_txt_*` / `sitemap_*` family returns `None` after a real
  round-trip (proven against an in-memory hash); **14 of 40 `CrawledPage` fields** and
  `Issue.fixability` are not serialised; `list_recent_jobs` / `list_jobs_by_domain` are `[]`
  stubs. The Redis tests cannot see any of this — they drive an `AsyncMock`, which returns a
  Mock for any attribute, so a missing method is indistinguishable from a working one (P6).
  `CLAUDE.md` and `docs/deployment-railway.md` both present Redis as the production store, and
  the deployment doc's `DATABASE_URL=redis://…` instruction does not match `get_job_store()`,
  which would treat that value as a **SQLite file path**. Decision pending: delete the backend
  (removes five contract pairs outright) or bind it with real round-trip parity tests. Until
  then, treat every "production runs Redis" claim in this file as unverified.

- **New fetches must route through `is_ssrf_safe()`.** Any Phase-2/3 outbound call (PageSpeed
  Insights, render-comparison, competitor crawl, GA4) is a fresh chance to bypass SSRF — wire it in.
- **Silent display/computation caps.** Several caps protect the crawler but can starve a check or hide
  rows on large sites. Audit each against real-scale data and announce "N of M" rather than truncating
  silently (P9). The GEO 1500-word window and any AI excerpt budget are the highest-risk.
- **`skip_wp_archives` narrows the link graph orphan detection reasons over.** Default-on, it skips
  WordPress author/category/tag/date/paginated archives *before* their outbound links are read — so
  a post linked only from a category archive still reads as `ORPHAN_PAGE`. Not gated (gating on a
  default-on setting would disable the check on every crawl); stated in the issue's caveat instead.
  Revisit if it produces real false positives (P31).
- **CPT / custom-taxonomy archive roots are flagged as orphans on complete crawls.** `is_wp_noise_path()`
  knows only built-in author/category/tag archives, so `/training`, `/team_members`,
  `/training_categories/*`, `/team-member-role/*` are crawled and flagged. Technically true, not
  actionable. An authoritative fix exists — `/wp-json/wp/v2/types` and `/taxonomies` expose archive
  slugs, and `resolve_scope_urls` already talks to WP REST — so no URL would be classified by pattern.
- **Suppressing ORPHAN_PAGE RAISES the health score.** `ORPHAN_PAGE` carries impact `(4, 2)`, so a
  partial scan that previously lost points to 20 false orphans now loses none and scores *higher* —
  coverage fell and the grade improved. The score was wrong before too (deflated by false positives),
  but the direction is the wrong way round and checklist item 7 requires the score never to rise as
  coverage falls. Not fixed here: changing what the score counts is a scoring-model change and needs
  its own spec + `scoring_model_version` bump. Partially mitigated — the PDF and Excel now carry the
  coverage note, so a reader sees the caveat beside the number.
- **`how_it_can_mislead` is data no component reads.** Added to `ORPHAN_PAGE` alongside ~30
  pre-existing entries that carry the field; no help surface renders it yet. Wiring it is v4
  content-pass work, tracked in `PLAN-V4.0.md`.
- **Transient external failures.** 429/timeout on external-link or image checks must not persist as
  permanent "broken"; keep them retryable / "unverified" (P1).
- **Schema parsing robustness.** `@graph` flattening, multiple JSON-LD blocks, and malformed JSON must
  not silently drop a page's structured data (P2/P3) — relevant to the new `SCHEMA_*` checks.
- **Score monotonicity.** Health Score and the Agent Health score must never increase when
  more issues are found; a monotonicity test guards the agent score
  (`tests/test_agent_readiness_checks.py::TestAgentHealthScore::test_agent_score_monotonic_non_increasing`).
  Holds because all impacts are ≥ 0 — re-check if any check is ever given a negative/bonus impact (P7).
- **WP4 placeholder-link false positives (highest live FP risk).** `PLACEHOLDER_LINK` /
  `WRONG_PLACEHOLDER_LINK` run on real HTML where `href="#"` legitimately drives accordions/tabs and
  links to `example.com`/`google.com` can be real references. Detection is deliberately conservative
  (CTA class/text gating, `role`/`aria-expanded`/`data-toggle` exclusion, known-host + empty-path
  gating) but the first production crawls should be eyeballed. If FPs appear, tighten — do not loosen
  to "flag any `#` link" (P7).
- **Agent-readiness signals are parser-precomputed.** Like the GEO checks, the WP2–WP5 signals are
  computed in `parser.py` while `soup` is in scope and stored as `ParsedPage` flags; checkers only read
  them. New agent checks must follow this pattern (no re-parsing in the checker, no raw HTML on the
  model) and wrap computation defensively so a parse quirk never aborts the crawl (P2).

---

## Fix log

Newest first. Format: **Issue → Root cause → What would have caught it → Fix → Pattern.**

- **2026-08-31 — the documented way to start the backend could not start the backend, and the app answered HTTP 500 on every page (reported by the owner).**
  - *Issue:* the owner reported 500s across the running app. Nothing in the app was broken. `frontend/vite.config.js` proxies `/api` → `localhost:8000`, and Vite's proxy returns **500** — not a connection error — when nothing is listening there, so a backend that never started is indistinguishable from a backend that crashed. The backend never started because the command in `CLAUDE.md` **cannot work**: `cd api && uvicorn main:app`. `api/main.py:33` imports absolutely (`from api.routers import crawl as crawl_router`), so run from inside `api/` the repo root is not on `sys.path` and the import raises `ModuleNotFoundError: No module named 'api'` before uvicorn binds.
  - *Root cause:* "how to start the backend" is stated in **four** places — `CLAUDE.md`, `docs/deployment-railway.md`, `docs/specs/core-crawler/v1.4-nonprofit-crawler.md`, `Dockerfile`. Three say `uvicorn api.main:app` and are correct; one drifted. Nothing bound the copies. Identical shape to the 2026-08-07 category-list bug, with one aggravating difference: the drifted copy is **documentation an agent reads as instruction at the top of every session**, so the wrong command is what gets followed and re-suggested.
  - *What would have caught it:* any test that ran a documented command. There was none — the suite verified the app's behaviour thoroughly and never verified that the app could be started the way the docs say. 3,513 tests, zero of them about startup.
  - *Fix:* `CLAUDE.md` now carries the same command as the other three, with the reason (absolute imports ⇒ repo root as CWD) beside it so the next edit cannot silently undo it, plus a note that a dead backend presents as 500s. New `tests/test_startup_contract.py` extracts every `uvicorn <target>` from all four sources and **imports each target in a subprocess from its documented working directory** — it does not string-match. A test asserting `target == "api.main:app"` would stay green while the app was unstartable for a different reason (renamed module, broken import inside `main.py`); it would pin the string, not the property. Two tests were red before the fix and green after; three more guard the guard, including one asserting a source that stops yielding commands is a failure rather than a vacuous pass, and two adversarial cases pinning that the wrong target and the wrong CWD genuinely fail — a check that cannot fail proves nothing (P27).
  - *Two corrections to my own analysis, worth more than the fix:* (a) I reported in a dual-implementation inventory that the router's `check_page` call drifted from the engine's on **four** kwargs. Re-testing before writing the spec, **three did not survive**: `hsts_checked_hosts` and `favicon_emitted` only dedupe *across* pages, so on a single-page scan both paths emit identically, and `page_size_limit_kb` is not a user setting at all — it is an engine-local default of 300 against a checker default of 300, the same number. Only `sitemap_urls` is real drift (`NOT_IN_SITEMAP` is silently dead on the single-page path). A plausible mechanism is not a defect; **check each member of a claimed class before building a spec on the count.** (b) The 2026-08-31 entry below attributes blank robots/sitemap panels to Redis and states "production runs Redis". The owner has never configured Upstash, and the startup log reads `sqlite_store: job_store_init` — `get_job_store()` has always returned SQLite. That root cause is **wrong**, the symptom is still unexplained, and `redis_store.py` is unexercised code (see Open risks).
  - *Pattern:* **P3/P12** — an instruction mirrored across N sites with no test binding the copies. Plus a new one worth naming: **a repo can test its product exhaustively and never test its own entry point.** Anything a human or agent is told to run is a contract; the test must execute it, not match its text.

- **2026-08-31 — a 404 was audited as a page, and I spent four wrong hypotheses before reading the evidence that was already in the database (reported by the owner).**
  - *Issue:* a scoped scan of the `team_members` post type reported `https://livingsystems.ca/team-members/14528` as a regular page carrying `NOINDEX_META`, `MISSING_HSTS`, `UNSAFE_CROSS_ORIGIN_LINK` and `CONSENT_MODE_MISSING`. The URL returns 404. Every finding described WordPress's **404 template**: the six "unsafe cross-origin links" were the site footer's Facebook/Instagram/LinkedIn icons, and the `noindex, follow` was the 404 template's own, which is correct behaviour for a 404. All four charged the site's health score for a page that does not exist.
  - *Root cause:* `run_crawl` has always guarded this — *"Skip SEO checks on 4xx/5xx pages — they are error pages, not real content"*. `_fetch_and_check_page`, the path behind `scan_single_page` and the per-page rescan button, guarded only `status_code == 0` (a network failure) and then called `check_page` unconditionally. The same URL was therefore audited or not depending on which button reached it. The repo already knew about this dual-path risk: `test_full_crawl_and_rescan_score_broken_links_identically` pins the two paths to agree on **broken links**, and nothing pinned them to agree on **the page itself**.
  - *What would have caught it:* the existing dual-path test, extended one step — from "both paths score the links the same" to "both paths treat the page the same". The narrower invariant looked like coverage of the class and was coverage of one member of it.
  - *My own diagnosis was the slower failure.* The owner asked a specific question — *where did you get that URL?* — and I answered it three times with a hypothesis instead of evidence: the REST API returns drafts to admins (wrong — the crawl is server-side and unauthenticated); discovery constructs ID-based URLs (wrong — `_collect_links` takes `item["link"]` verbatim); the anonymous REST list contains it (unproven — I drew that from a `head -40` of a 100-item response and said so only after asserting it). The evidence that settled it was one query against the local database: no `links` row targeted that URL, and the stored `extra` for `UNSAFE_CROSS_ORIGIN_LINK` listed the site's own footer icons — which identifies the 404 template immediately. I also ran ~12 full crawls against the live site while verifying unrelated fixes and got this machine IP-blocked, which then prevented the one check that would have settled the provenance question.
  - *Fix:* `_fetch_and_check_page` returns the `BROKEN_LINK_*` finding alone for any response `>= 400`. Plus the feature the owner actually wanted: `scan-page?authenticated=true` signs in with the existing `WPClient` cookie login so a draft can be audited before publication — domain-validated, SSRF-guarded, single-page only, with `ORPHAN_PAGE` / `NOT_IN_SITEMAP` / `NOINDEX_META` suppressed as meaningless before publication and the response declaring `visibility: "not-public"` so a clean draft is never read as a clean page.
  - *Pattern:* the **dual-path** class — two entry points to the same work, one hardened, and an invariant test narrow enough to miss it (P5's shape, at the router seam). And a diagnostic lesson worth more than the fix: **when the user asks where a value came from, query the artifact before theorising.** The answer was in a stored `extra` field the whole time.

- **2026-08-31 — four backlog fixes, and the parity test written for one of them found a fifth bug that only existed in production.**
  - *Issue:* (1) `data_source` was hardcoded `"html_only"` on every scan row, while `get_image_summary` counts `images_analyzed` as `data_source='full_fetch'` — so the panel reported **0 analysed** for a crawl that had downloaded, hashed and measured every image. (2) `scan_single_page` still hardcoded `width=None … content_hash=None`, so five image checks were dead on that entry point while working on a full crawl, with nothing saying so. (3) `IMG_DUPLICATE_CONTENT` compared exact URLs, so `logo.png` and `logo.png?ver=6.4` — and the reference site's own Photon `?fit=` URLs — hashed identically and reported a duplicate the user cannot act on. (4) only SQLite's `health_score_basis` was asserted, though production runs Redis.
  - *The fifth:* the contract test for (4) asserted that both stores expose the **same summary key set**, and it went red immediately — SQLite supplied `robots_txt` and `sitemap`, Redis supplied neither, and `CategoryPanel.jsx` reads both. The sitemap and robots panels rendered correctly in development and blank in production, which is the divergence nobody would ever see locally. Found by a parity assertion, not by looking.
  - *Root cause:* (1) and (2) are the same shape as the disclosure bug earlier in the week — a field describing what the code *used* to do, left behind when the code started doing more. (3) is a checker asking a question about an *asset* while keyed on a *request*. (4)/(5): two hand-maintained implementations of one payload, with nothing binding them.
  - *What would have caught it:* for (5), exactly what did — asserting the two backends agree, rather than testing each in isolation. Testing them separately can pass forever while they diverge, because neither test knows what the other expects.
  - *Fix:* `data_source` now reflects what actually happened (`full_fetch` measured / `crawl_meta` HEAD-only / `html_only` markup-only), verified live at 32 full_fetch and 5 crawl_meta. The single-page scan runs the same bounded, SSRF-guarded dimension pass. `_image_identity` strips cache-busting and CDN-sizing parameters before the duplicate comparison, with tests in both directions so it cannot quietly stop catching real duplicates. Redis gained `robots_txt` and `sitemap`, built from the job model that already carried them.
  - *Pattern:* **P25** twice more (a capability wired at one front end, a payload asserted on one backend), and the general lesson that **a parity assertion between two implementations of the same contract finds bugs that testing either one alone cannot** — cheap, mechanical, and needs no external oracle (P32's option b).

- **2026-08-31 — the SSRF guard failed open on resource exhaustion, and the change that made it matter was mine.**
  - *Issue:* `is_ssrf_safe` ended `except (socket.gaierror, OSError): return True`. `gaierror` is a subclass of `OSError`, so the tuple collapsed two very different failures into one verdict. The consequential half: any non-DNS `OSError` — `EMFILE`, `ENOMEM`, a sandbox refusing the socket — made **every** URL evaluate as safe, at exactly the moment the process was least healthy. The IM1 dimension pass then put this guard on a far hotter path: up to 150 HEADs plus 150 GETs per job, each previously an unmemoised `getaddrinfo`, which is precisely the load that produces file-descriptor exhaustion. I widened the exposure and deferred the guard in the same session.
  - *Root cause:* the original comment — "Can't resolve — allow (will fail at fetch time with a clear error)" — is true for the case its author had in mind (NXDOMAIN) and false for the case the code also caught. A single handler over a superclass hid the distinction, and the rationale written beside it only covered the benign half. This is the narrative-beside-the-code shape P9 warns about, applied to an exception clause rather than a magic number.
  - *What would have caught it:* asking, for every `except` in a guard, *which* failures it covers and whether the rationale holds for all of them. A cold security pass found it by reading the handler rather than the comment.
  - *Fix:* the two cases are separated. `gaierror` still allows, and that is deliberate rather than inherited: httpx resolves through the same resolver, so the fetch fails anyway, and denying would report every dead external link on a customer's site as "SSRF_BLOCKED: resolves to a private/internal network" — `link_router` checks every outbound link through this function, so the blast radius of over-tightening is larger than the hole. Any other `OSError` denies: an unverifiable URL is not a verified-safe one. Neither outcome is cached, because both are transient and caching either would turn one blip into a whole TTL of wrong answers (P1).
  - *The guard is bounded on both sides, which is the part worth copying:* reverting to the original turns six tests red; **over**-tightening to deny on `gaierror` turns three red, including a pre-existing test that had pinned the allow deliberately and a new one asserting a dead link is reported as broken rather than blocked. A security fix that can only fail in one direction invites the next person to over-correct it.
  - *Also:* resolution is now memoised per hostname with a 120 s TTL. That was written for a different finding — DNS was inside the window `IMG_SLOW_LOAD` is scored from, so a 400 ms resolver read as 415 ms of image load time — but it also removes most of the lookups that made exhaustion reachable. Failures are deliberately not cached.
  - *Pattern:* a **fail-open guard**, and the meta-rule applied — an AST sweep of every guard-shaped function in `api/` for `except → return True` found this was the only instance. Plus the standing lesson that when a change makes an existing weakness more reachable, the weakness stops being purely pre-existing.

- **2026-08-30 — a cold sweep of the fix commit found 14 more defects, including a regression the fix itself introduced and three tests of mine that could not fail.**
  - *Issue:* the commit repairing 14 cold-review findings was itself swept cold, as its own range. It contained: (a) a **regression** — the soft-404 fix gated on `content_type.startswith("image/")`, so a valid PNG served as `application/octet-stream`, or with no `Content-Type` at all (routine on misconfigured object storage), was discarded before Pillow saw it, taking all five IM1 checks dead site-wide; (b) `load_time_ms` still measuring the crawler — `started` was stamped before `client.stream`, which runs the SSRF guard's blocking `getaddrinfo` inside the timed window, so a 400 ms resolver was reported as 415 ms of image load time against a 1000 ms threshold; (c) my `IMG_BROKEN` test hand-built `ImageInfo(http_status=404)` and called `_check_broken`, asserting only that the checker reads its own argument — mutating the actual fix left it green; (d) the summary contract test used a job with **no images**, so it exercised the `total_images == 0` early return and never the branch a real crawl takes; (e) the panel seam — the last one, the one the commit message said was covered — had no test at all, and deleting the render line left all 281 frontend tests green; (f) breaking out of an `asyncio.as_completed` loop left its wrapper coroutine un-awaited, emitting a `RuntimeWarning` on every budget expiry; (g) `Image.MAX_IMAGE_PIXELS` was being set process-wide from inside the per-image download, lowering the ceiling for every other Pillow consumer.
  - *Root cause:* fixes are written last, fastest, and in the most anchored state. Each of these came from fixing the *previous* finding without re-asking the original question. The content-type gate is the clearest: I was told "a soft-404 HTML page is hashed as the image", and gated on the declared type — which fixes the reported case and breaks a commoner one. The right question was "what is the strongest available evidence that these bytes are an image?", and the answer was Pillow decoding them, not the server's own label.
  - *What would have caught it:* the sweep that did — treating the fix commit as its own change with its own reviewer. Nothing else would have: the whole suite was green, every fix was mutation-proved, and the live crawl looked right.
  - *Fix:* decode first and fall back to the declared type only for what Pillow cannot read (SVG); memoise SSRF resolution per hostname with a TTL, taking DNS out of the timed window (median live `load_time_ms` fell 170 ms → 93 ms) and off the hot path; `asyncio.wait` instead of `as_completed`; the Pillow ceiling set once at import; three tests rewritten to drive real crawls and the production branch; a panel test added and mutation-proved against the exact deletion that had been invisible. `IMG_POOR_COMPRESSION`'s pixel floor gained a 50 KB absolute-weight escape, because the floor alone silenced a 64×64 badge at 150 KB — 37 bpp, and under `IMG_OVERSIZED`'s 200 KB, so nothing fired at all.
  - *Pattern:* **P26's corollary**, measured again: every pass found a defect inside its predecessor's fix. Plus **P27** three times over in my own tests, **P13** (counters bound inside `if candidates:` and read outside it — the same shape as the bug I had fixed an hour earlier in the same function), and the general lesson that **a fix aimed at a reported case should be checked against the commoner case it might exclude**.

- **2026-08-30 — four cold review passes found 20+ real defects in a change I had already reviewed warm, twice. Two of them were disclosures I had documented as shipped and had never wired to anything.**
  - *Issue:* after IM1 (image dimensions), V1 (authority record) and the SSRF work, four independent reviewers were given only the diff and the range — no narrative. They converged on defects that every warm pass had walked past. The worst were not subtle: (a) `images_measured` / `images_measurable` reached **no surface at all** — three documents, including my own functional-spec text, said they "carry the shortfall *the way* `images_collected` / `images_seen_total` carry the image cap", and `images_collected` reaches eight files while mine reached `engine.py` and its own tests; (b) deleting the `health_score_basis` key from the summary payload left **all 3425 tests green** while `SummaryPanel.jsx` reads it, violating CLAUDE.md's non-negotiable API-contract rule; (c) the dimension pass read `response.content` with no ceiling, bounded only by a budget computed from the remote host's own HEAD `content-length`; (d) my commit titled *"one source for the AI confidence label, which had drifted"* removed three backend copies and left a **fourth in the frontend**, drifted the same way, on the one code I had just downgraded because nobody had confirmed it; (e) IM1 woke **five** checks, not the four I documented — the fifth, `IMG_POOR_COMPRESSION`, fires at 4.0 bpp on a 16×16 favicon against a 0.5 threshold, i.e. on every icon on every site.
  - *Root cause:* warm review cannot see the shape of its own assumptions. I verified IM1 by printing `result.images_measured` from a Python script and read "measured 27 of 28" as the feature working — a check one layer below every surface, which is the exact P25 shape I had spent the session flagging in other people's code. The confidence fix was scoped to "the registry", so the frontend copy was never in view. The byte budget felt like a bound because I had written the word "budget"; it bounds what we *intend* to fetch, not what the server *sends*.
  - *What would have caught it:* exactly what did — a pass that does not know how the change was written, covering a failure family the author was not thinking about. The four passes disagreed usefully: the security pass found the unbounded body, the correctness pass found the frontend confidence drift, the test-quality pass proved the `health_score_basis` deletion was invisible, and the failure-pattern pass found the unwired disclosure. **No single reviewer found more than half.** Two of them independently found the unwired disclosure, which is the signal P26 says to trust.
  - *Fix:* the dimension pass now streams and abandons past a hard cap, gates on `content-type` (a soft-404 HTML page was being hashed and sized as the image, fabricating `IMG_DUPLICATE_CONTENT` across every broken `<img>` on a site), preserves `http_status` so `IMG_BROKEN` can finally fire from the scan path, counts a measurement by `"width" in meta` rather than a non-empty dict, bounds concurrency to 6 so `load_time_ms` stops measuring our own connection queue, harvests results as they complete instead of discarding everything on timeout, and uses `continue` rather than `break` so one large image cannot end the pass for every smaller one after it. The disclosure is wired model → both stores → summary → panel with contract tests at each seam. `IMG_POOR_COMPRESSION` gained a 100×100 floor. `enabled_analyses=[]` is no longer read as "no selection". DNS resolution moved off the event loop in the httpx guard hook, matching what I had already written for Playwright ten lines away.
  - *Three defects found in my own fixes, in the same cycle:* my SSRF wiring test asserted the guarded client was **constructed**, not **used** — swapping the actual download to a bare client left the file green; my new contract-test fixture never closed its store, so a single-test run hung forever on the aiosqlite thread (P30: not using a resource is not releasing it); and my derived threshold-honesty check false-positived on the Core Web Vitals codes, where Google genuinely does publish 4 s and 500 ms — fixed by making the record state *whose* number it is (`threshold_note` for ours, `threshold_published_by_source` for theirs) rather than inferring it.
  - *Pattern:* **P26** in its strongest measured form — a falling warm finding count is evidence about the reviewer, not the code. Plus **P21/P25** (built, documented as integrated, wired to nothing), **P9** (a budget that bounds intent rather than bytes), **P27** (a wiring test that asserts construction instead of use), and **P32** (my own honesty check policing a class it did not enumerate — it missed two codes firing on a 20% threshold Google never published).

- **2026-08-30 — the image passes fetched arbitrary URLs from crawled HTML with no SSRF guard, and my first three tests for the fix could not fail.**
  - *Issue:* CLAUDE.md states as a hard constraint that all outbound fetches go through `is_ssrf_safe()`, blocked at start and on every redirect hop. Neither image pass did. The HEAD metadata pass had used the plain crawl client since it was written; the IM1 dimension pass I had added an hour earlier used the same client and made it matter far more, because HEAD leaks little and a GET returns the whole body. An image `src` of `http://169.254.169.254/latest/meta-data/...` would have been fetched and its bytes hashed and stored.
  - *Root cause:* `make_ssrf_guarded_client()` already existed and enforces both hooks. The image code simply reused the crawl client that was in scope. I wrote the new fetch by copying the shape of the sibling beside it, which inherited the sibling's gap — P5 in the security direction, where the class is "outbound calls" and one member had never been hardened.
  - *What would have caught it:* asking, for a new external call, which of the repo's stated security defaults applies to it — the constraint was written down and I did not check the new code against it. It surfaced in the csdp-lite sweep, from the question "what does this constraint say, and does my new call satisfy it?" rather than from any test.
  - *Fix:* both passes now use `make_ssrf_guarded_client()`, closed in a `finally` so the pool is released on the exception path too. Five internal targets plus a public-host-redirecting-inward case are tested.
  - *Second bug, in my own fix:* the first three tests asserted `meta == {}` against unmocked internal addresses. `_fetch_image_dimensions` returns `{}` on **any** failure, so they passed whether the guard refused the request or the connection merely failed. Neutralising the guard hook left all five green — **P27, a test that cannot fail against the defect it names.** Rewritten so each internal URL is mocked to return a *perfectly good image*: `{}` can then only mean the request was never made, and the assertion is `not route.called`. The same mutation now fails all five.
  - *Third thing found, worth stating rather than papering over:* the redirect case cannot be proved by mutating either hook alone — httpx runs the request hook again for the redirected request, so each guard independently refuses it, and only disabling both turns the test red. That is real defence in depth, but claiming the test proves the redirect hook specifically would be a false assurance, so the test says what it actually establishes.
  - *Pattern:* **P5** applied to security rather than robustness — a new call inheriting the gap of the sibling it was modelled on; and **P27**, where the fix's own test was green over a disabled guard. Also the general lesson that a repo's written constraints are a checklist to run new code against, not background reading.

- **2026-08-30 — my own cost control for the new image-dimension pass skipped both of the site's only two overscaled images.**
  - *Issue:* IM1 added a dimension pass so four image checks could fire at all. It fetched only images whose HEAD size was at or above 100 KB. Measured against livingsystems.ca afterwards: of 62 images that declare a display width, exactly two are overscaled — `TrianglesProjection-1.jpg` (1102px into a 300px slot, **30 KB**) and `Triangles1-1.gif` (1124px into a 500px slot, **9 KB**). Neither reaches 100 KB, so `IMG_OVERSCALED` stayed dead on 100% of the real instances while the pass reported itself as having run.
  - *Root cause:* the gate was justified by a sentence I wrote into the spec — "an image below ~100 KB cannot be oversized for its display slot in any way worth reporting" — that was never checked against the data. Overscaling is a **ratio** of intrinsic to display width; it has no lower bound in bytes. A well-compressed 9 KB GIF can be 1124px wide.
  - *What would have caught it:* comparing the gate to the population it filters, before shipping it — the same question P9 asks: on real data, what fraction survives this cap, and are the survivors the ones the check cares about? The unit test I had written (`test_im1_small_image_is_not_downloaded`) actively **pinned the misconception** (P32): it asserted the wrong behaviour, passed, and made the design look verified. The whole cost argument was also unnecessary — the total download for the site is 6.0 MB.
  - *Fix:* the gate is gone. The pass is bounded by a **total byte budget** (`TT_IMAGE_DIMENSION_TOTAL_BYTES`, 48 MB) with a per-image skip for one pathological file (12 MB), a count cap and time budgets — bounds on total cost, which is the thing actually at risk, rather than a per-item proxy that correlates with nothing the checks measure. `images_measured` / `images_measurable` disclose the shortfall so an unmeasured image renders as *not checked*, never *clean* (P31). The misconception test was replaced by its inverse, `test_im1_small_image_is_measured_too`, plus budget and pathological-file tests; all four new guards mutation-proved. Verified live: 32 of 34 images measured for 1.7 MB, and `IMG_OVERSCALED` and `IMG_NO_SRCSET` now fire on exactly the two images an independent Pillow probe had identified.
  - *Pattern:* **P9** — a magic limit capping the input, defended by a narrative the data does not support; and **P32**, a test written to confirm the design rather than to falsify it. Also P26's corollary: this defect was in the fix, an hour old, and the full suite was green over it.

- **2026-08-29 — ORPHAN_PAGE flagged 20 of 37 pages on a partial scan, including every page the user's own hub page links to (reported by the user, from the report).**
  - *Issue:* `ORPHAN_PAGE` ("no internal links point here") fired on pages that are linked. On livingsystems.ca the same checker gave opposite verdicts on the same site: the full 272-page crawl (`3c205407`) flagged **0 of 8** `/training/*` items; a 37-page partial scan of five custom post types (`bcf3351c`, `type_keys = team_members, conference, banner-message, presentation, training`) flagged **8 of 8**, plus 9 team-member pages — 20 of its 37 crawled pages. `/training-2/` is a WordPress **Page**, not one of the selected types, so the crawl never fetched it; its raw HTML carries 7 links to `/training/<slug>/` and 10 to `/team_members/<slug>/`.
  - *Root cause:* `check_cross_page` built `linked_urls` from `page.links` over **the pages that were crawled** and flagged any crawled page absent from that set. The inference is only valid over the whole site. The narrowing itself was correct — the user asked for a partial scan — but the downstream absence-proof kept treating the subset as the population, so "not fetched" was recorded as "not linked". `max_pages` truncation and cancellation are the same shape.
  - *What would have caught it:* a test crawling a site where the only inbound link lives on an out-of-scope page — i.e. exercising the *scoped* path, not just the full one. Every existing orphan test used a complete two- or three-page graph. The signature is backwards from the usual: narrowing the scan makes the check find **more**, so the report looks richer rather than broken. The neighbouring `HIGH_CRAWL_DEPTH` already degraded correctly (fires only when `crawl_depth is not None`) — one checker in the pipeline knew the principle and its sibling guessed.
  - *Fix:* `check_cross_page(..., link_graph_complete: bool = True)`; the orphan pass moved into `_check_orphan_pages()` and runs only when the flag is true. The engine derives it and records `orphan_detection = {status, pages_analysed, pages_out_of_scope, archives_skipped, pages_links_unread}` on the job — persisted in both stores, returned in the crawl summary, rendered by the Orphaned Pages panel, the Results tile, the PDF caveats section and the Excel summary. **Suppressing the check turns the false positives into a false all-clear**, so the gate and the disclosure shipped together: `count === 0` previously rendered "✓ All crawled pages have at least one internal link", a fabricated pass for a scan that never looked. Verified live on livingsystems.ca: the same partial scan went 20 → 0 false orphans, and a full crawl still found 11 real ones (all WP archive roots) with 0 of 8 `/training/*` items flagged — the gate did not disable the feature.
  - *Widened after review (two independent passes, warm + cold, converged on the same three defects — P26):* the `CrawlResult` default was `"complete"`, so any path that forgot the field asserted a whole-site scan → now defaults to `not_run`, making the wrong state unrepresentable rather than patching each caller. `single_page` claimed `"complete"` (one page, no graph, zero orphans, green ✓) → new `skipped_single_page`, also written by `/api/crawl/scan-page` and the failed-crawl path. The panel's `.catch` returned a bare `{count: 0}`, so **any** API failure rendered the all-clear. The link graph was built from `html_pages` only, so a page with no title/meta/h1 — 93 of 256 on livingsystems.ca, mostly image uploads — had its real anchors dropped, inventing orphans on *complete* crawls; links now come from every crawled page while candidates still come from `html_pages`. `pages_analysed` reported `len(all_pages)` (256) instead of the population the check reasons over (163). And `find_orphaned_media` is the **same absence-proof over the same page set** behind the adjacent card, ungated, with every row deep-linking into the WordPress editor — now gated on the same coverage record (P31's "fix the class").
  - *Two bugs found while fixing:* (a) `create_job`'s INSERT is a fixed column list, so setting `orphan_detection` on the model in `/scan-page` would have been **silently dropped** — the same claim-doesn't-reach-the-artifact shape as the bug being fixed (P6); written via `update_job` instead. (b) A scripted `str.replace` in my own fix batch matched a 16-space `continue` as a substring of a 20-space one, de-indenting it and turning the `PAGE_TIMEOUT` emission into dead code. **All 2724 tests stayed green** — nothing asserted that the engine emits `PAGE_TIMEOUT`, only that the registry and scoring know the code. Caught by a new test written for the unread-pages counter, then guarded by `test_unreadable_internal_page_still_reports_page_timeout` and mutation-proved with the exact corruption. P26's corollary in the flesh: the fix commit is the least-reviewed code in the change, and an emission with no test can be deleted without a single red light.
  - *Pattern:* **P31** — an absence-proof computed over a deliberately narrowed population (new generic pattern in `standards/learnings.md`). Distinct from P3 (an *accidental* narrow scope) and P9 (a magic cap to justify): here the upstream narrowing is correct and only the inference over it is unsound. Plus the P2/P24 corollary that a suppressed check must never render as a clean result.
  - *Not fixed (recorded as open risks):* `skip_wp_archives` (default on) drops WordPress archive pages before their outbound links are read — disclosed via `archives_skipped` and a footnote under the all-clear rather than gated, since gating a default-on setting would disable the check on every crawl. Pages the crawl reached but could not read (timeout, login wall, parse failure) are counted in `pages_links_unread` and disclosed for the same reason. On a *complete* crawl the check still flags WP CPT/taxonomy archive roots (`/training`, `/team_members`, `/training_categories/*`) that nothing is meant to link to — true, but not actionable. And **suppressing the check raises the health score** (see Open risks) — a scoring-model change needing its own spec.

- **2026-08-14 — GSC priority-upload shipped with a None-vs-0 ranking corruption + a silent order→restrict scope change (caught by the /csdp learning-qa sweep before push).**
  - *Issue:* (a) The upload parser coerced an **absent** `inquiries` to `0` (`_int(row.get("inquiries"))`), and that flowed to `PerformanceRecord.ga4_conversions_mo` — a field explicitly documented as `int | None = None` so "no data" stays distinct from "measured zero" (P2). A page with *unknown* conversions would rank as *proven-zero*. (b) The GSC seed is fronted in the crawl frontier before discovered links; a seed with **more in-scope URLs than `max_pages`** silently consumes the whole page budget, turning the approved "**order** the frontier" (D-N1) into "**restrict** the crawl to seed pages" — with no warning. (c) The `generated_for == "talkingtoad"` sanity gate the contract (§3) mandated wasn't implemented, so any same-domain JSON with a `pages[]` shape was accepted.
  - *Root cause:* (a) a blanket int-coercion applied to a None-sensitive field; (b) seeding order interacting with the `max_pages` cap, untested at/over budget; (c) relying on the domain guard alone and skipping the marker check.
  - *What would have caught it:* (a) a parser test with a row that omits `inquiries` asserting `conversions is None`; (b) a `/start` test with a seed ≥ `max_pages`; (c) a `generated_for`-rejection test. All three edges were uncovered — every existing fixture supplied `inquiries` and a small seed.
  - *Fix:* (a) `_int_or_none` for `inquiries`; the None passes through to `ga4_conversions_mo`. (b) `/start` appends a loud scope note when `len(seed) >= max_pages` ("non-priority pages may not be crawled — raise Max pages"). (c) reject a file stamped for another tool (absent marker tolerated — domain guard is primary; §3 softened to match). Tests added for all three.
  - *Pattern:* **P2** (None coerced to 0 on a None-sensitive field) + **P9** (a cap silently narrowing coverage, drop not announced). Sibling of the Performance-Bundle ingest, which handles the same field correctly — the new file-sourced path must match it.


- **2026-08-13 — MI7 batch shipped a production-breaking import-order bug (invisible on the 3.14 dev machine) plus the same-form `track-` prefix collision one step down (both caught by the /csdp learning-qa sweep of the already-pushed batch).**
  - *Issue:* (a) The batch inserted three new functions ABOVE the `from api.crawler.checkers.registry import Issue, make_issue` line, and one (`_check_cta_tracking`) used `Issue` in a **function annotation**. Annotations evaluate at def-time on Python < 3.14, so `import api.crawler.checkers.analytics` raised `NameError: name 'Issue' is not defined` on the **`python:3.11-slim`** the Dockerfile pins — i.e. the analytics checker failed to import in production — while the 3.14 dev box (PEP 649 lazy annotations) imported fine and the whole suite stayed green. (b) The 2026-08-09 sweep fixed suffix collisions (`slick-track`) by moving to per-token PREFIX matching, but bare `track-`/`track_` are ordinary word prefixes too, so content classes (`track-order`, `track-list`, `track-changes`, `track-shipment`) still read as tracked — the doubly-harmful form: it hides the gap on that button AND falsely establishes "convention in use" on the page, misfiring MI7 on other genuinely-untracked CTAs.
  - *Root cause:* (a) a name used in a def-time-evaluated position (annotation) imported below its use; the dev/prod Python-version skew hid it. (b) a prefix marker (`track-`) that is indistinguishable by form from `track-<contentword>`; the previous sweep's adversarial test only covered the *suffix* variant.
  - *What would have caught it:* (a) running the suite (or even a bare import) on the pinned 3.11, OR a structural "imports-before-defs" guard that catches it regardless of interpreter; (b) an adversarial `track-order`/`track-list` case in the generic-classes test, and a page-level test asserting a content `track-*` class doesn't establish the convention.
  - *Fix:* (a) hoisted the registry import into the top block, deleted the stray lower one; verified `import` clean on **both** 3.11 and 3.14; added `test_checker_modules_import_before_any_def` (ast: every checker's module-level imports precede its first `def`/`class`) — proven to flag the pre-fix state. (b) added `CTA_TRACKING_CLASS_CONTENT_BLOCKLIST` (config, not logic) excluding the content `track-*` tokens; `track-donate`/`track-donation` intentionally NOT blocklisted (nonprofit domain — likelier a real marker); added `test_mi7_content_track_prefix_classes_are_not_tracking_markers` + `test_mi7_content_track_class_does_not_establish_page_convention`.
  - *Pattern:* (a) **works-on-my-Python** — a def-time annotation over an import ordering, masked by a dev/prod interpreter-version skew (P16-adjacent: verify on the runtime that actually ships, not the one on your desk). (b) **P7** residual — a gameable prefix match, one form below where the prior sweep stopped; a blocklist is inherently incomplete (residual logged in TODO).

- **2026-08-09 — MI7 CTA-tracking shipped with a false-positive marker match AND a red suite hidden by a status grep (both caught by the /csdp learning-qa sweep, after I'd reported "green" 3×).**
  - *Issue:* (a) The new `CTA_TRACKING_MISSING` check matched its short markers (`-track`, `_track`, `track-`) as **substrings over a concatenated blob** of the CTA's own + up to 4 ancestors' class/data-attr text. A universal Slick carousel class (`slick-track`) contains `-track`, so a carousel-wrapped conversion button read as *tracked* — hiding a real gap AND tripping the "convention in use" gate into a misfire on a different button. (b) Adding the 162nd catalogue code left two count guards (`test_audit_2026_07_p0.py`, the `registry.py` docstring via `test_r5_severity`) asserting **161**, so the full suite was **red the whole time** — but my status grep `[0-9]+ passed, [0-9]+ skipped` matched the tail of `2 failed, 2181 passed, 12 skipped` and I reported "2183 passed" three times.
  - *Root cause:* (a) substring-matching a short generic token against a mixed blob, with no per-token anchoring; the 4-ancestor scope widened the blast radius. (b) a success check keyed on the *presence* of "passed" rather than the *absence* of failure — green on both the pass and the fail path.
  - *What would have caught it:* (a) an adversarial test feeding an unrelated `track`-bearing class (`slick-track`) and asserting NOT-tracked; (b) deciding suite success from the **exit code** / `grep -c failed == 0`, never a pass-count scrape.
  - *Fix:* (a) markers now matched **per class token by prefix** (`token.startswith(("track-","track_",…))`), bare suffix markers dropped; the parser returns structured ancestor token lists (`context_classes`/`context_data`) not a blob — `slick-track`/`fast-track`/`data-slick-track` no longer match, real `track-`/`track_` on the element or wrapper still do (verified 12/12 on livingsystems.ca). Added `test_mi7_generic_track_classes_are_not_tracking_markers`; tightened over-broad conversion terms (`give`/`apply`/`order` → specific forms). (b) bumped both count guards to 162.
  - *Pattern:* **P7** (a gameable match — tracked "for the wrong reason") + **P24** (false green from output-parsing that can't tell pass from fail — new generic pattern in `standards/learnings.md`). Adjacent: adding a catalogue member must bump every hardcoded count assertion (grep the class).

- **2026-08-07 — new `analytics` category was invisible in the UI and the PDF (found by a user, not a test).**
  - *Issue:* The `analytics` ("Analytics & Measurement") category shipped in the backend registry, checkers, `categoryHelp.js`, and `issueHelp.js`, but was never added to the three hardcoded category **display/ordering** lists — `frontend/src/pages/Results.jsx` CATEGORIES (tabs), `frontend/src/components/SummaryPanel.jsx` CATEGORIES (the "Issues by Category" grid), and `api/services/report_generator.py` `cat_list` (PDF). So it appeared nowhere: a user's livingsystems.ca crawl showed 13 category tiles with no Analytics tile. The same omission had **already** silently hit `rendering` and `semantic_html` in the PDF `cat_list` (they'd reached the two frontend grids but never the PDF).
  - *Root cause:* the category set is mirrored across ≥4 hardcoded sites (registry = source of truth, two frontend arrays, one PDF list) with **no test binding the display copies to the registry**. Existing parity tests covered issue *codes* (AI-suggestion set, fix-codes) and the *help* files — the copies that happen to have parity tests — but not the category display/ordering lists. Adding a category updated the tested copies and silently skipped the untested ones.
  - *What would have caught it:* a parity test asserting every `registry._CATALOGUE` category appears in all three display lists.
  - *Fix:* added `analytics` to both frontend CATEGORIES arrays and the PDF `cat_list` (which also restored the long-missing `rendering` + `semantic_html`); added `test_category_display_lists_cover_every_backend_category` (`test_frontend_backend_code_parity.py`) covering all three. Excel export verified generic (no hardcoded list). Pre-existing dead key `duplicate` (present in the grids + PDF list but emitted by no `_CATALOGUE` code → always 0) flagged in TODO, not changed.
  - *Pattern:* **P3/P12-adjacent** — an enumeration mirrored across multiple hardcoded lists drifts silently when a member is added and only some copies are updated. Parity tests must bind **every** mirror, including display/ordering lists, not just the data/help copies. Reinforces the meta-rule (grep the whole codebase for the same class before closing): the identical omission had already bitten two earlier categories in the least-visible copy.

- **2026-07-22 — §2 per-target occurrence counting was applied to only one of two issue-emitting paths; deleting SCHEMA_MISSING dropped a coverage case (both caught pre-merge).**
  - *Issue:* The §2 collapse (`collapse_per_target_occurrences`, `links.py`) that folds many broken-link rows into one with an occurrence multiplier was wired into the full-crawl engine only. The **rescan / single-page** path (`crawl.py::_fetch_and_check_page`) emitted the same per-target codes **uncollapsed**, so after a user rescanned a page its broken links reverted to the pre-§2 per-link scoring (and the two paths attributed broken links to *opposite* page_urls — source vs dead target). Separately, deleting `SCHEMA_MISSING` (which fired on `not schema_types`) in favour of `JSON_LD_MISSING` (fired on `not has_json_ld`) silently dropped the "has a malformed/typeless `ld+json` script" case — neither code fired.
  - *Root cause:* A scoring/counting rule added to one sibling emitter, siblings left on the old path (same class as the 2026-07-06 R5 divergence and 2026-07-03 three-health-paths bug). The catalogue merge assumed two codes detected an identical condition when their trigger fields differed.
  - *What would have caught it:* a full-crawl-vs-rescan parity test on a multi-broken-link page (P10/P12), and a malformed-JSON-LD fixture (P2 — don't silently drop structured-data coverage).
  - *Fix:* apply `collapse_per_target_occurrences` in the rescan/scan path too, after aligning it to the engine's `page_url = source, extra.target_url = target` convention; change `JSON_LD_MISSING` to key on `not page.schema_types` (absorbing `SCHEMA_MISSING`'s exact condition). Tests: `test_per_target_occurrences.py` (multiplier curve, collapse, `test_f2_malformed_jsonld_still_flags_structured_data`).
  - *Pattern:* **P12** (a transform added to one path, sibling paths silently keep the old behaviour — always grep for every emitter/consumer of the affected codes) + **P2** (a "merge/delete" must preserve the union of the deleted code's trigger conditions, not assume equivalence).

- **2026-07-22 — Near-duplicate detector was anti-monotonic; entity check flagged third-party orgs (both caught pre-merge).**
  - *Issue:* The new `NEAR_DUPLICATE_BODY` check (P1, `cross_page.py`) compared pages after subtracting "site boilerplate" (shingles on ≥ max(3, 20%) pages). But a cluster of ≥3 duplicate pages pushes *its own* shared body over that doc-frequency threshold, so the shared content was reclassified as boilerplate and subtracted — leaving near-empty sets that scored Jaccard 0. The bigger and more blatant the duplication, the more certain it was to be missed (and mis-reported as N separate `BOILERPLATE_RATIO_HIGH` issues). Separately, `ENTITY_NAME_INCONSISTENT` harvested every `Organization` JSON-LD node, so a partners/funders page legitimately listing several orgs read as the site naming *itself* inconsistently.
  - *Root cause:* Coupling two signals through one transform (boilerplate subtraction feeding both the ratio signal and the near-dup comparison), and treating any `Organization` mention as self-identity. `first_1500_words` already strips nav/footer (parser), so the subtraction was both redundant for near-dup and actively harmful.
  - *What would have caught it:* a P7 **monotonicity** test — N identical pages must yield one cluster of all N as N grows (the tests only covered 2-page pairs, which slipped under the `<3` threshold); and a self-vs-third-party entity test.
  - *Fix:* near-dup now clusters on the **raw** shingle sets; boilerplate is used **only** for `BOILERPLATE_RATIO_HIGH`. `ENTITY_NAME_INCONSISTENT` self-identity = publisher/provider names + a page's Organization node **only when the page has exactly one** (multi-org listings contribute none). Also promoted the `0.20`/`0.15` literals to config and guarded `_MINHASH_PERM ≥ 1`. Regression tests: `test_near_duplicate_body.py::test_large_identical_cluster_still_flagged`, `test_entity_consistency.py::test_e1_partners_page_no_false_positive`.
  - *Pattern:* **P7** (a scoring/matching proxy that is non-monotonic / gameable — "looks-right-but-wrong" input scores wrong) + P4 (magic literals in a detection path). When two signals share a transform, verify one isn't silently destroying the other's input.

- **2026-07-20 — Scan-scoping discovery bypassed the crawl path's SSRF + retry hardening (caught pre-merge).**
  - *Issue:* The new content-type discovery (`api/crawler/content_discovery.py`) issued raw `client.get(..., follow_redirects=True)` on a plain `make_client()` and treated any fetch failure as `None`. Two defects: (a) it followed redirects with **no per-hop SSRF check**, so a validated public host could 302 a `/wp-json/` probe or child-sitemap `loc` to `169.254.169.254`/`10.x`/`localhost` and be fetched — bypassing the invariant `fetch_page` enforces; (b) a transient failure mid-pagination ended the collection early (`if not got: break`), silently under-scoping the crawl while it reported success.
  - *Root cause:* A new class of external calls added alongside `fetch_page` without inheriting its siblings' hardening — no per-hop SSRF re-validation and no transient retry — plus a `None`-means-"done" pagination loop that couldn't tell "collection ended" from "a page failed."
  - *What would have caught it:* the P5 checklist item ("are there other calls of the same kind? do they all share the hardening?") and a P10 fault-injection test where a mid-pagination page 500s.
  - *Fix:* added `make_ssrf_guarded_client()` (request + redirect event hooks re-checking `is_ssrf_safe` every hop) and routed discovery/resolution through it; `_get_json` now retries transient conditions with backoff (shares `fetcher._MAX_RETRIES`/`_RETRY_BACKOFF_S`); paginated reads use `X-WP-TotalPages` so a failed page is reported as `truncated`/`scope_notes`, never a silent end. Tests: `test_content_discovery.py` (SSRF request+redirect block, mid-pagination failure) + `scope_notes` surfaced on `/start`.
  - *Pattern:* **P5** (inconsistent robustness across sibling external calls — here the unhardened sibling was a *security* boundary) + **P1/P2** (transient treated as terminal / silent drop). New external-call sites must route through `fetch_page` or replicate its per-hop-SSRF + retry policy.

- **2026-07-06 — GSC ingest sent `sites/undefined/...` → HTTP 400.**
  - *Issue:* After connecting Search Console, "Ingest" queried `sites/undefined/searchAnalytics/query` and Google rejected `http://undefined` as an invalid site URL.
  - *Root cause:* `list_properties()` returns snake_case `{site_url, permission_level}` (the app's API convention), but `GSCInsightsPanel.jsx` read camelCase `p.siteUrl`/`permissionLevel` → `undefined`. The panel's own test masked it by mocking a fictional camelCase shape, so it stayed green.
  - *What would have caught it:* an API-contract test asserting the panel consumes the *real* `/api/gsc/status` field names, and a test that Ingest sends a real `site_url` (never `undefined`).
  - *Fix:* panel reads `site_url`/`permission_level`; test mocks corrected to the real snake_case contract + a regression asserting the ingest URL never contains `undefined`.
  - *Pattern:* P6/serialization — a frontend/backend field-name mismatch with the test mocking a shape the backend never returns. Sibling of the `/api/gsc/status` missing-`configured` bug.

- **2026-07-06 — `analyze_with_ai` returned provider errors as `str`, rendered as AI content.**
  - *Issue:* `api/services/ai_analyzer.py::analyze_with_ai` signalled failure by **returning a sentinel
    error string** (`"AI analysis skipped: …"`, `"Error calling AI: …"`) rather than raising. Because
    success and failure were both `str`, callers rendered the error as if it were AI output:
    `/api/ai/analyze` returned it directly as `suggestion` (no guard at all); `/page-advisor` and
    `/site-advisor` fed it into recommendations; and the `crawl.py` executive-summary path **cached the
    error string onto the job** and served it as the summary.
  - *Root cause:* A mixed-mode `str` interface — the same return type for content and for failure — with
    ad-hoc `str.startswith`/`_is_ai_error` sentinel checks that several callers simply never made.
  - *What would have caught it:* An adversarial test forcing a provider error and asserting it never
    appears as content in any response or on the job (P14 checklist item 15).
  - *Fix:* `analyze_with_ai` (and `geo_llm._call_llm`) now raise a typed `AIAnalysisError` on failure;
    every caller catches it and routes to its error channel (503 / `{error}` field / skip). Deleted all
    `startswith`-sentinel checks and `geo_llm._is_ai_error`/`_ERROR_PREFIXES`. Adversarial tests added.
    Spec: `docs/pending/OLD/2026-07-06_p14-ai-error-contract.md`.
  - *Pattern:* **P14** — error state returned as string, rendered as content. Resolves the standing
    "error-as-content" class for the AI path; new AI callsites must let `AIAnalysisError` propagate.

- **2026-07-06 — R5: three divergent page-health computations; only one was capped + suppressed.**
  - *Issue:* The category-cap (20) and cluster/noindex suppression logic lived in **one** of three
    health-score computations. `crawl.py` and `citations.py` each recomputed health from a **raw
    uncapped sum**, so the same crawl could report different scores depending on which endpoint served it,
    and suppression/cap never applied on those two paths.
  - *Root cause:* A scoring rule was added to one sibling and its siblings were left on the old raw-sum
    path (classic drift across duplicated computations).
  - *What would have caught it:* A parity test asserting all health-score entry points agree on the same
    fixture (`tests/test_scoring_paths_unified.py`).
  - *Fix:* Unified all three onto a single capped + suppressed path; `crawl.py`/`citations.py` no longer
    recompute a raw sum. Added `scope: page|site` (site-config codes deduct once per site), extended
    suppression clusters + noindex scope-reduction, a Quick-Wins list, runtime-derived severity, and a
    `scoring_model_version` stamp (legacy rows read null). Spec: functional-spec §4.0.1.
  - *Pattern:* **P3/P5** — enumerate all siblings; a scoring change must be applied class-wide, not to
    one of N parallel computations.

- **2026-07-06 — `SCHEMA_VISIBLE_MISMATCH` false-positive from a WP SEO-plugin author graph-node.**
  - *Issue:* WordPress SEO plugins inject the byline author as a sibling `/schema/person/<hash>` graph
    node. This slipped `_is_author_publisher_node`, so `SCHEMA_VISIBLE_MISMATCH` fired **site-wide** on
    every page — a looks-wrong-but-is-right input scored as a failure.
  - *Root cause:* The author/publisher-node guard didn't recognise the plugin's hashed-`@id` Person node
    shape, so a legitimate structural node was treated as a spurious schema mismatch.
  - *What would have caught it:* An adversarial fixture using the real WP `/schema/person/<hash>` node
    asserting no `SCHEMA_VISIBLE_MISMATCH`, alongside a true-positive-preserved test.
  - *Fix:* Extended the guard in `api/services/schema_typing.py` (weight unchanged); added both the
    adversarial and true-positive tests. Confirmed on a real crawl (livingsystems.ca) where site health
    rose 73→88 once the FP cleared. Spec: `docs/pending/2026-07-06_deploy-gate-validation.md` (V2).
  - *Pattern:* **P7** — a detector that false-positives on a valid input; add the adversarial case.

- **2026-07-06 — llms.txt validator was stricter than the llmstxt.org spec.**
  - *Issue:* `LLMS_TXT_INVALID` required a `>` blockquote summary and ≥1 URL, capped URLs at 20, and
    hard-required `text/plain` — none of which the llmstxt.org spec mandates (only the `# Title` H1 is
    required; summary, sections, and link count are optional, no cap). A standard Yoast-generated file
    (H1 + plain summary + 50 links, no blockquote, leading UTF-8 BOM) was wrongly flagged.
  - *Root cause:* Invented editorial validity rules hardcoded in the checker, plus a leading UTF-8 BOM
    that defeated the H1 detection so even the one real requirement mis-fired.
  - *What would have caught it:* A regression test using the exact Yoast shape (BOM + H1 + plain summary
    + sections + 50 links) asserting it validates clean, with soft-404 still flagged.
  - *Fix:* Strip a leading BOM, then flag `INVALID` only when there is no Markdown H1 title (soft-404 /
    non-Markdown body). Removed the blockquote, min-URL, 20-URL cap, and MIME requirements. Updated the
    `LLMS_TXT_INVALID` recommendation, `docs/thresholds.md`, and regenerated `docs/issue-codes.md`.
  - *Pattern:* **P7** (a check that fails a looks-right-**and-is-right** input) + **P4** (editorial rule
    hardcoded in logic; now aligned to the external spec).

- **2026-07-06 — `/api/gsc/status` omitted `configured`, giving a dead-end Connect UI.**
  - *Issue:* `gsc_status()` returned `{connected, properties}` but no `configured` field on its 200
    paths. The panel read `!status.configured` (which was `undefined`) as "not configured" and never
    rendered the **Connect** button in the configured-but-not-linked state — a permanent dead end.
  - *Root cause:* A response missing a field the frontend keys on; the serializer and the frontend
    contract had drifted (the 503 "not configured" path was distinct from the 200 "configured but
    unlinked" state the field was meant to express).
  - *What would have caught it:* An API-contract test asserting `/api/gsc/status` 200 responses include
    `configured: true` (now `tests/test_gsc_integration.py::TestGscStatus::test_status_response_contract_fields`).
  - *Fix:* Added `"configured": True` to all three 200 responses (no-creds, success, except-fallback);
    the `_require_gsc_configured()` 503 path (→ `configured:false` on the client) is unchanged.
  - *Pattern:* **P6/serialization** — a status response must carry every field the frontend keys on;
    verify the contract, don't assume the client can infer a missing field.

- **2026-07-06 — `fetch_page` dropped `text/plain` bodies, so llms.txt/ai.txt saw empty content.**
  - *Issue:* `fetch_page` only decoded HTML/PDF bodies. For a `text/plain` response (a real llms.txt),
    `.html` was `None`, so the llms.txt check saw an empty body and validated it as empty → `INVALID`.
  - *Root cause:* A narrow content-type scope — only two body types were ever decoded — silently
    discarded every other text body with no signal.
  - *What would have caught it:* A fetcher test decoding a `text/plain` response and asserting the body
    is preserved (plus a size bound); an llms.txt respx test using a real plain-text file.
  - *Fix:* Added a `text: str | None` field to `FetchResult`; non-HEAD `text/*` (non-HTML) bodies are now
    decoded into `.text`, and the llms.txt check reads it. Size-bounded like the HTML path.
  - *Pattern:* **P2/P3** — silent drop on a narrow-scope assumption; enumerate the content types a data
    path must handle rather than assuming one or two are complete.

- **2026-07-06 — usage-aggregation tests rotted as wall-clock time advanced (test-only).**
  - *Issue:* The `_seed` helper omitted a timestamp, so `record_ai_usage` stamped rows at `now()`. Once
    real time passed the tests' fixed `2026-05-01..06-30` query window, seeded rows fell outside it, the
    aggregation returned empty, and three assertions failed — with no production bug.
  - *Root cause:* A test fixture depending on wall-clock `now()` against a hardcoded date window; the two
    dates drifted apart as the calendar advanced (a P4/P8-flavoured testing smell).
  - *What would have caught it:* Running the suite after the window's end date — or, structurally, seeding
    rows at a timestamp explicitly inside the query window rather than at `now()`.
  - *Fix:* Stamp seeded rows inside the fixed window. Test-only; no production change.
  - *Pattern:* **P4/P8 (testing)** — a hardcoded date window plus `now()`-stamped fixtures is a
    time-bomb; pin fixture timestamps relative to the window under test.

- **2026-06-22 — Agent-readiness spec's "new" codes collided with already-shipped codes.**
  - *Issue:* The approved micro-spec (written against a v2.6 baseline) listed `SCHEMA_FAQ_MISSING`,
    `JS_DEPENDENT_CONTENT`, `SCHEMA_MISSING`, and `NO_DATE_ON_CONTENT` as **new** codes, but the repo had
    since shipped `FAQ_SCHEMA_MISSING`, `RAW_HTML_JS_DEPENDENT`, a page-level `SCHEMA_MISSING`, and
    `DATE_PUBLISHED_MISSING` covering the same intent. Building the spec verbatim would have created
    duplicate, parallel catalogue entries.
  - *Root cause:* Spec authored against a stale snapshot of `_CATALOGUE`; no reconciliation step had run
    against the live registry before "approved".
  - *What would have caught it:* WP0 — grepping the live `_CATALOGUE` for each proposed code before
    writing any. (Did this; the collisions surfaced immediately.)
  - *Fix:* Reused shipped codes; added only the 9 genuinely-new ones; added a new `SCHEMA_ORG_MISSING`
    for the distinct homepage-Organization gap (the existing `SCHEMA_MISSING` name was taken). Did **not**
    recategorise `AI_BOT_*` into a `crawler_access` category — that would have stripped their confidence
    labels (an architecture-test invariant = lost functionality). Recorded in
    `docs/functional-specification.md` §4.9 and `PLAN-AGENT-READINESS.md`.
  - *Pattern:* P3/P4-adjacent — "reuse before you invent"; always reconcile a spec's catalogue claims
    against the live source of truth (the repo meta-rule: grep the whole catalogue for the class before
    adding a code).

- **2026-08-29 — Two independent "silent join" bugs, found only by running the tool against the live site.**
  - *Issue:* (a) The Performance Ledger join used `WHERE url = ?`. The ledger stores the trailing-slash
    form Search Console reports; the crawler normalises it away. **11 of 272** pages joined, the site's
    highest-impression page was lost entirely, and the report printed 3,717 impressions instead of 27,284.
    (b) `get_links_by_target` had the same exact-match flaw, so the "Show Source Pages" button on the
    Broken Links panel opened onto nothing — compounded by the frontend assigning the whole response
    envelope `{target_url, sources, count}` to its `sources` state, making `.length` undefined.
  - *Root cause:* Producer and consumer normalise URLs differently, and neither side's tests exercised the
    other side's real format — both used the same idealised URL string.
  - *What would have caught it:* Running the feature against real data and looking at the number, which is
    what did catch it. The unit tests were all green: they seeded and queried with the same URL form.
  - *Fix:* A shared `ledger_key` both sides go through; tolerant matching in `get_links_by_target`; and —
    the part that matters — a **loud warning when a join that has rows on both sides matches almost
    nothing**. "No row for this page" and "the key didn't match" had produced identical output.
  - *Pattern:* **P19 + P2.** A join is a producer/consumer contract. Test it with the two sides' *real*
    formats, never one string used twice, and instrument zero-from-non-empty as a warning, not a clean pass.

- **2026-08-29 — Enriching an evidence field silently changed a scoring input.**
  - *Issue:* E2 set `extra["occurrences"]` to the number of pages linking to a broken target, to report
    the true remediation scope. But `occurrences` is what `occurrence_multiplier` reads to scale that
    page's deduction. A footer link broken on 200 pages therefore doubled the deduction on whichever page
    the crawler happened to reach first — making per-page health crawl-order dependent — and amplified
    transient `BROKEN_LINK_503` / `EXTERNAL_LINK_TIMEOUT` findings by up to 2x.
  - *Root cause:* One field carrying two jobs. The name read like "how many of these are there", which is
    true of both the evidence count and the scoring count, so reusing it looked free.
  - *What would have caught it:* Asking "what reads this field?" before widening its meaning. The suite
    stayed green throughout — no test asserted impact for a multi-source target.
  - *Fix:* `occurrences` is the per-page scoring count again; the evidence lives in `occurrence_urls` /
    `occurrence_urls_total`. Both are asserted separately, with the reason in the test name.
  - *Pattern:* **P7/P22.** Before repurposing an existing field, grep for its readers. A field consumed by
    a scorer is part of the scoring contract however descriptive its name sounds.

- **2026-08-29 — A composite score that clamps to its floor on every real site measures nothing.**
  - *Issue:* Site Hygiene shipped as `100 − Σ(tier weight × share)`. On the first real site, nine systemic
    defects produced a penalty of 135 and the score clamped to 0 — indistinguishable from a site with
    twenty, or two hundred.
  - *Root cause:* The weights were chosen against a mental model of one or two systemic defects. No real
    data was run through the formula before it was wired into the report.
  - *What would have caught it:* Computing the score on the live job *before* building the UI around it.
    Every unit test passed: they each exercised one or two codes.
  - *Fix:* Replaced with a coverage measure — the percentage of indexable pages carrying no systemic
    defect. Bounded by construction, no arbitrary weights, monotonic, and it states itself in one sentence.
    Reads 34 on livingsystems.ca beside a Health of 89, which is the honest description of that site.
  - *Pattern:* **P9/P7.** A new composite score must be computed on real, full-scale data before anything
    is built on top of it. "Passes its unit tests" and "discriminates between real inputs" are different
    claims, and only the second one makes a score worth printing.
