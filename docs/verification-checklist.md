# TalkingToad — Critical Verification Checklist

> **Scope:** the things that, if broken, make the app produce **wrong, unsafe, or
> fabricated** results — not cosmetic/warning-level issues. A few warning-level
> items are kept **only** where they act as a *canary* confirming a whole
> subsystem ran (marked 🐤).
>
> **[CI]** = asserted by the automated suite (`pytest tests/` + `npm run test`);
> a green suite *is* the check. **[LIVE]** = needs a real run / manual confirmation
> the tests can't fully substitute for (real network, real WordPress, real LLM,
> real TLS, stale-runtime effects).
>
> Fastest full gate: `pytest tests/ -q` (expect ~2056 passed) **and**
> `cd frontend && npx vitest run` (expect ~207 passed). Everything marked [CI]
> below is inside that gate; focus human time on the [LIVE] rows.

---

## 1. Security — must never regress (highest priority)

- [ ] **SSRF blocked at start AND on every redirect hop** — private/internal IPs
      (`127.0.0.1`, `169.254.169.254`, `10.x`, `192.168.x`, `localhost`) refused,
      including a public host that 302-redirects to an internal one. **[CI]**
      `test_content_discovery.py` (guarded client), `test_crawl_engine.py`;
      **[LIVE]** point a scan at a URL you control that 302s to `169.254.169.254`
      and confirm it's refused, not fetched.
- [ ] **Auth fail-closed in production** — empty `AUTH_TOKEN` in prod rejects
      `/api/ai/*`, `/api/geo/*`, `/api/*` utility routers; only `/api/health` is
      public. **[CI]** `test_advisor_auth.py`; **[LIVE]** hit a protected route on
      the deployed instance with no/So wrong bearer → 401/403.
- [ ] **WP domain validation on every WP-touching call** — mismatch returns 403
      `DOMAIN_MISMATCH`; no call reaches a domain other than the job's. **[CI]**
      `test_architecture_constraints.py::test_scan_never_calls_wordpress_api` +
      fix-router tests; **[LIVE]** attempt a fix with credentials for a *different*
      domain → 403.
- [ ] **No URL/slug/permalink changes via WP API, ever** — and no automated
      image-link rewriting in posts. **[CI]** architecture tests; **[LIVE]** code
      review any new `/api/fixes/*` route.
- [ ] **XSS escaping** on any helper injecting user text into HTML (e.g.
      `change_heading_text`). **[CI]** heading-fixer tests.
- [ ] **Scan is read-only** — a crawl never issues a WP write/HEAD-only for
      images, never a full GET download for image checks. **[CI]**
      `test_architecture_constraints.py::test_image_scan_uses_head_requests`.
- [ ] **Secrets only from env/config** — no keys in source, `wp-credentials.json`
      / `.env*` git-ignored. **[LIVE]** `git ls-files | grep -Ei 'secret|cred|\.env'`
      returns nothing tracked.

## 2. Crawl correctness

- [ ] **robots.txt respected**; admin/login paths skipped; expected-disallow
      carve-outs (cart/checkout/search) honoured. **[CI]** `test_robots.py`,
      `test_crawl_engine.py`.
- [ ] **External-link caps** (50/page, 500/job) and **redirect loop/chain**
      detection hold. **[CI]** `test_crawl_engine.py`.
- [ ] **Transient ≠ terminal (P1)** — a 429/timeout/5xx is retried and recorded as
      *retryable*, never written as a permanent BROKEN/TIMEOUT negative. **[CI]**
      fetcher retry tests; **[LIVE]** worth re-confirming after any fetcher change.
- [ ] **Partial failure surfaced, never silently dropped (P2)** — "found nothing"
      is distinguishable from "the call failed"; drops are counted/logged. **[CI]**
      discovery + scope tests (`scope_skipped`, `scope_notes`).
- [ ] **Content-scope (partial scan) uses an authoritative allowlist, not URL
      guessing** — a Post whose permalink mimics a Page is excluded under
      "Pages only". **[CI]** `test_crawl_scope.py` (adversarial lookalike).
- [ ] 🐤 **Canary: a normal crawl of a real small site completes** with pages
      crawled > 0, a health score, and issues in ≥3 categories. **[LIVE]** run
      against `livingsystems.ca` (or any small site) end-to-end.

## 3. Scoring integrity (R3→R5 model)

- [ ] **Impact is derived, not drifting** — `_ISSUE_SCORING[code].impact ==
      derive_impact(code)` for all codes; severity == `severity_from_impact`.
      **[CI]** `test_r3_calibration.py`, `test_r5_severity.py`.
- [ ] **Parity 4-way** — catalogue ↔ `issueHelp.js` ↔ scoring ↔ confidence-label,
      and `issue-codes.md` regenerated from `_CATALOGUE`. **[CI]**
      `test_architecture_constraints.py`, `test_issue_codes_doc_in_sync.py`.
      *Canary for the whole catalogue: if this is green, no code is half-registered.*
- [ ] **Per-category cap** (20) prevents one root cause flooring a page; **site-
      scoped codes** (TLS cluster, entity, near-dup) charged **once** site-wide,
      not per page. **[CI]** `test_site_scope.py`, `test_r5_clusters.py`.
- [ ] **Cluster suppression** — a parent present ⇒ children contribute 0 to score
      (still shown in the list). **[CI]** `test_r4_cluster_suppression.py`.
- [ ] **Per-target occurrence counting** — N broken links on a page collapse to
      one row with `impact × min(1+0.25(n−1), 2.0)`, and **the full crawl and the
      rescan path score it identically**. **[CI]** `test_per_target_occurrences.py`
      (incl. dual-path).
- [ ] **Every saved audit stamped with `scoring_model_version`** so old scores
      aren't silently compared to new. **[CI]** `test_scoring_version.py`.
- [ ] **Monotonicity** — more failing checks never *raise* a score (page health,
      agent-readiness, citability grade). **[CI]** `test_citability_grade.py` and
      agent-readiness tests.

## 4. Issue detection — false-positive & false-negative guards

- [ ] **Adversarial "looks-right-but-wrong" guards hold** for the gameable
      checkers: entity name casing/suffix normalisation, near-duplicate boilerplate
      stripping, big-duplicate-cluster monotonicity, partners-page not flagged as
      self-inconsistent, schema-completeness codes only fire when the schema
      `@type` is present. **[CI]** `test_entity_consistency.py`,
      `test_near_duplicate_body.py`, `test_schema_completeness_eeat.py`.
- [ ] **Dirty/old-crawl state (P8)** — pages missing new fields
      (`schema_blocks`, `first_1500_words`, `citability_grade`) render/score with
      no crash and no fabricated zeros. **[CI]** the `*_missing_fields` / dirty-state
      tests.
- [ ] 🐤 **Canary: cross-page pass ran** — on a multi-page site with a real
      duplicate, `TITLE_DUPLICATE`/`NEAR_DUPLICATE_BODY`/`ORPHAN_PAGE` appear.
      **[LIVE]** (confirms the post-crawl `check_cross_page` executed at all).

## 5. WordPress fix pipeline (when used)

- [ ] **Background/launch buttons disabled immediately** with a server-side
      `pgrep` guard and a page-load status re-check. **[LIVE]** click a batch
      optimize / long fix twice fast → second is refused.
- [ ] **Fix status reconciles to the artifact (P6)** — a "applied"/"done" flag is
      verified against the actual WP field value now, not assumed. **[LIVE]** apply
      a title trim, then read the WP value back and confirm it matches.
- [ ] **Background worker guarded (P15)** — batch optimizer / any thread writing a
      status dict wraps its whole body in try/except and writes `error` on failure
      (never stuck at `running`/`starting`). **[CI]** batch-optimizer tests;
      **[LIVE]** kill a batch mid-run → status becomes `error`/`cancelled`, spinner
      resolves.

## 6. AI / LLM / reports — no fabrication

- [ ] **Error strings never rendered as content (P14)** — an AI failure yields an
      error-shaped result, not `"AI analysis skipped: …"` shown as findings; an
      empty/refused LLM verdict produces **no** spurious issue. **[CI]** advisor /
      geo_llm tests; **[LIVE]** disconnect the AI provider and confirm the UI shows
      an honest error, not fake analysis.
- [ ] **External calls hardened as a class (P5)** — every LLM/HTTP/subprocess call
      has timeout + retry + backoff. **[LIVE]** grep new code for unguarded
      `client.get`/`await` on external calls.
- [ ] **Reports reconcile to data** — PDF/Excel/CSV contain only real crawl
      results, Latin-1-safe, no invented rows; a "0 issues" report matches an
      actually-clean crawl. **[CI]** report/excel tests; **[LIVE]** spot-check one
      generated PDF against the on-screen results.

## 7. Deploy / runtime sanity (P16)

- [ ] **The running instance serves the new code**, not a cached process — after a
      deploy, probe a `/version`-style stamp or the changed endpoint's *response
      shape*, and confirm which PID owns the port. **[LIVE]** don't trust
      "edited + looks unchanged"; verify the served behaviour.
- [ ] **Frontend/backend field-name contract** — the SPA reads the exact field
      names the API returns (snake_case), no `undefined` in outgoing requests.
      **[CI]** contract tests (`test_rewriter_integration.py`, api schema tests).

---

## How to run the gate

Run each line from the repo root. (Lines are comment-free so they paste cleanly
into an interactive `zsh` — which, unlike `bash`, does **not** treat `#` lines as
comments. Use `python3`, not `python`.)

Backend suite (~2056+ passed):

```bash
pytest tests/ -q
```

Frontend suite + hooks-rules lint (errors block the build):

```bash
cd frontend && npx vitest run && npx eslint src && cd ..
```

Docs/catalogue in sync — regenerate and confirm **no** git diff:

```bash
python3 scripts/generate_issue_codes_doc.py && git diff --exit-code docs/issue-codes.md
```

A green gate covers every **[CI]** row. The **[LIVE]** rows are the human
checklist — most are one deliberate action against a real site / WP / provider.
The **golden fixture site** (see `docs/golden-fixture-plan.md`, if built)
automates the biggest [LIVE] gap: end-to-end detection through the real crawl
pipeline.
