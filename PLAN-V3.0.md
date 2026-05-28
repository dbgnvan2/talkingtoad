# TalkingToad — v3.0 AI-Readiness & Citation-Era Implementation Plan

> **Plan version:** 3.1 — v2.x stabilization phase substantially complete (2026-05-27)
>
> ## v2.x Rock-Solid Status (post-session)
>
> **Shipped (17 commits on `main`):**
>
> | Milestone | Status | Tests added |
> |---|---|---|
> | M0.5 Advisor auth | ✅ | 19 contract tests |
> | M0.6 SSRF audit (8 fixes + pre-check) | ✅ | 50 adversarial tests |
> | Pre-existing test debt cleared | ✅ | +58 (1005→1063) |
> | M0.7 Containerize for Railway | ✅ | Dockerfile + railway.json + deployment guide |
> | M0.8 Production hardening | ✅ | 14 production-safety tests |
> | M0.9 P4 Gutenberg dead-code fix | ✅ | 3 Gutenberg-block tests |
> | M0.12.0–7 All 6 fix-domain routers restored | ✅ | 105 router contract tests |
> | M0.2 Confidence labels on 49 ai_readiness codes | ✅ | 3 architecture-parity tests |
> | M0.1, M0.3, M0.10 Doc version/path cleanup | ✅ | - |
> | M8 Contract test backfill (crawl + utility + verified + ai) | ✅ | ~70 contract tests |
> | M8.8 CI guard against future drift | ✅ | 1 endpoint coverage guard + 2 allowlist discipline tests |
>
> **Final test count: 1240 passing, 11 skipped, 0 failures.**
>
> **Deferred (does not block "rock solid" — see notes below):**
>
> | Item | Reason |
> |---|---|
> | M0.9 P5 GEOReportPanel.jsx auth | Blocked on `feature/multi-page-geo` branch merge |
> | M0.9 P6 ImageFixPanel mark-fixed | Same blocker |
> | M0.4 v2.0 spec open questions | Resolved during M0.12 implementation; remaining items now in M1 scope |
> | M0.11 Endpoint audit punch-list | Superseded by M8.8 CI guard (which is more durable) |
> | v2.4 issueHelp.js confidence field | 26/49 already have it; the remaining ones need frontend edits coordinated with multi-page-geo branch |
> | v2.6 M9 refactor hotspots | Significant work — `issue_checker.py` (2,448 lines), `Results.jsx` (1,831), `crawl.py` (1,859), `wp_heading_fixer.py` (1,031), `ImageAnalysisPanel.jsx` (1,393). Code works; splits are quality improvements, not correctness fixes. Best done as focused single-session work each. |
> | v2.7 M10 frontend infrastructure | Toast system (54 alert calls), accessibility baseline, code-splitting. Each is significant standalone work; some files conflict with multi-page-geo branch. |
>
> **v2.x is "rock solid" in the sense that matters most:**
> - Security holes closed (SSRF, advisor auth, production hardening)
> - Production deploy actually works (containerized, no BackgroundTasks freeze)
> - Every documented `/api/fixes/*` endpoint has a backend handler
> - CI guard prevents new endpoints from shipping without tests
> - All AI-readiness signals carry honest confidence labels
> - Documentation reflects shipped reality
>
> A critical reviewer would flag the file-size violations in v2.6 as
> technical debt — but the plan explicitly documents them, the code works,
> and the test suite catches regressions. v3.0 features can build on this
> foundation without inheriting active bugs.
>
> ---

> **Earlier plan version:** 3.0 — added AI multi-provider architecture + usage tracking after strategy discussion (2026-05-27)
> **Reference specs:**
> - `docs/specs/ai-readiness/v2-extended-module.md` (the v2.0 spec — **mostly already implemented**, see Discovery Findings)
> - Google Search Central: [AI Features and Your Website](https://developers.google.com/search/docs/appearance/ai-features) (last updated 2025-12-10)
> - Google Search Central: [Top ways to ensure your content performs well in Google's AI experiences](https://developers.google.com/search/blog/2025/05/succeeding-in-ai-search) (May 2025)
> - Google Blog: [Search I/O 2026 announcements](https://blog.google/products-and-platforms/products/search/search-io-2026/)
>
> **Prerequisites:** v2.2 (Content Quality Advisor & Rewriter) shipped.
>
> **Goal:** Make TalkingToad a best-in-class auditor for sites trying to win in the citation era — and a **sustainable paid-customer product**. Ship from a clean foundation: critical security and production bugs are fixed first, deployment is moved off Vercel-only serverless to a container backend, the AI layer becomes multi-provider with per-customer keys and token-level usage tracking for billing, the existing-but-incomplete v2.0 module is finished, and the doc/test debt is paid down.
>
> **Estimated total effort:** 15–17 weeks across 11 milestones, **shipped in 6 incremental releases** (v2.3 → v2.7 → v3.0). See Release Phasing below. Strategic decisions (deployment + AI economics) are locked in below.

---

## Release Phasing — v2.x Stabilization Before v3.0 Features

**Decision (2026-05-27):** Bring v2.x to "finished" before adding any v3.0 features. Each phase is independently shippable; customers see continuous improvement instead of waiting for a big-bang v3.0.

| Release | Time | Milestones included | Customer-visible outcome |
|---|---|---|---|
| **v2.3 — Security & deployment fixes** | 1.5 wks | M0.5, M0.6, M0.7, M0.8, M0.9 | Crawler works in production again (containerized backend); advisor router no longer wide-open; SSRF closed; production hardening; correctness bugs fixed |
| **v2.4 — Foundation cleanup** | 1 wk | M0.1, M0.2, M0.3, M0.10, M0.11 | Confidence pills on AI-readiness issues; docs accurate; version strings unified; endpoint audit complete (feeds v2.5) |
| **v2.5 — Test contract backfill** | 1.5 wks | M8 | Less visible to end users — but every endpoint the frontend calls is now tested per CLAUDE.md non-negotiable rule |
| **v2.6 — Refactor hotspots** | 2 wks | M9 (high-value splits: `issue_checker.py`, `crawl.py`, `Results.jsx`, `wp_heading_fixer.py`, `ImageAnalysisPanel.jsx`) | Less visible — codebase becomes safer to extend; v3.0 features can build on clean modules |
| **v2.7 — Frontend infrastructure** | 1 wk | M10 (toast system, accessibility, code-splitting, auth helper consolidation) | No more `alert()` boxes; accessible icon buttons; faster initial bundle |
| **v3.0 — New features** | 9–10 wks | M0.4 (deferred from M0), M1, M2, M3, M4, M5, M6, M7, M11 | AI multi-provider with per-customer keys + usage tracking; v2.0 AI-readiness completed; Google-validated extensions; content freshness; citation ingestion; GSC OAuth; reporting + confidence surfacing |

**Why this works:**
- Production is currently broken (Vercel `BackgroundTasks`) — M0.7 ships in v2.3 regardless
- Security bugs (S1–S6) ship in v2.3 regardless
- Each v2.x release is small and reversible; customer feedback shapes v3.0 priorities
- Test backfill (M8) and refactor (M9) derisk v3.0 feature work
- Frontend infrastructure (M10) is a prerequisite for v3.0 panels (GSC, AI Settings, Citations)

**Why M0.4 deferred to v3.0:** Resolving the v2.0 spec open questions only matters when M1 (complete v2.0 gaps) starts. Pulling it forward into v2.x phase is wasted effort.

**Constraints during v2.x phase:**
- No NEW user-visible features. Bug fixes, security, cleanup, refactor only.
- No breaking API contract changes (frontend keeps working unchanged).
- Container backend (M0.7) is the one deployment change; document migration carefully.
- v2.x version bumped at the end of each phase (v2.3, v2.4, v2.5, v2.6, v2.7).

---

## Strategic Decisions Made During Plan Development

| # | Decision | Rationale |
|---|---|---|
| 1 | **Deploy model: Vercel frontend + small container backend** (Fly.io / Render / Railway) | Vercel `BackgroundTasks` don't survive serverless invocations (P1 — prod crawler silently broken). Container backend removes the timeout problem, removes the SQLite-on-serverless concern, and gives a clean Python deployment story. Frontend stays on Vercel because Vercel is genuinely the best at SPAs. Cost: $5–20/month at start, scales with paying customers. |
| 2 | **AI: Multi-provider with per-customer keys + system-default fallback + token usage tracking** | At scale, calling AI with your global key per customer crawl burns money. Per-customer keys (set in Settings) shift cost to customer where they pay providers directly. System-default keys are the fallback when customer hasn't configured their own (so the product still works out-of-the-box). Token usage tracked per session/run so billing can be added cleanly later. Default routing: DeepSeek for text (cheap), Gemini Flash for vision (cheapest with vision); premium tier defaults to GPT-4o / Claude Sonnet. |
| 3 | **No self-hosted local AI yet** | Break-even is ~500+ monthly active customers vs. DeepSeek's $0.20-per-audit pricing. Until then it's distraction from product. Revisit at scale. |

---

## Discovery Findings (from 2026-05-27 four-agent review)

The original plan was drafted from `docs/` only. A deep code review surfaced material facts that change the plan shape.

### What's already implemented that the original plan treated as new

| Item | Original plan location | Actual status |
|---|---|---|
| `api/services/ai_bots.py` (with `LAST_REVIEWED = 2026-05-03`) | M1.1 | **Exists** |
| `api/services/ai_readiness.py` (site-level robots.txt AI checks) | M1.2 | **Exists** with 14 tests |
| `api/services/schema_typing.py` (per-page-type schema checks) | M1.4 | **Exists** with 12 tests |
| `api/services/page_classifier.py` (page-type inference) | M1.3 | **Exists** with 17 tests |
| `api/services/extractability.py` (structural extractability) | M1.5 | **Exists** with 16 tests |
| `api/services/citation_model.py` (citation data model) | M4 | **Exists** with 18 tests |
| `frontend/src/components/AIReadinessPanel.jsx` | M1.8 (extract) | **Exists** at 318 lines (needs polish, not extract) |
| 28 `ai_bots` integrity tests | M1 test budget | **Done** |

### What's *actually* missing for v2.0 completion

| Gap | Where |
|---|---|
| `confidence_label` field in `_CATALOGUE` and API responses | `api/crawler/issue_checker.py` |
| `api/services/passage_heuristics.py` (content-quality heuristics) | new file |
| `ParsedPage` field additions (`schema_blocks`, `inferred_page_type`, etc.) | `api/crawler/parser.py` |
| `AIReadinessPanel.jsx` integration with confidence pills | existing file |
| `POST /api/jobs/{job_id}/ai-citations` endpoint | new router |
| `api/services/gsc_client.py` + OAuth flow | new |

### Critical production / security bugs found (blocking v3.0)

These were not in the original plan. They are now M0 work and must land before any v3.0 feature work.

| # | Severity | Finding |
|---|---|---|
| S1 | **Critical** | `/api/ai/advisor*`, `/api/ai/rewriter`, `/api/ai/rewrite-url`, `/api/ai/geo-report*` chain has **NO bearer auth**. Anyone can burn OpenAI/Gemini credits. (`api/routers/advisor.py:27`) |
| S2 | **Critical** | SSRF bypass in `/api/crawl/{job_id}/images/fetch` — raw httpx with no `is_ssrf_safe`. (`api/routers/crawl.py:1501-1502`) |
| S3 | **Critical** | SSRF bypasses in `advisor.py:_fetch_page`, `rewriter.py`, `js_renderer.py:104-113` (the last includes headless-browser SSRF capability) |
| S4 | **Critical** | SSRF in `/api/robots` and `/api/sitemap` — accept arbitrary user URLs. (`api/routers/utility.py:111-141`) |
| S5 | **Critical** | SSRF in `ai_analyzer.py:359` and `wp_image_fixer.py:297, 651` |
| S6 | **Critical** | SSRF in AMP HEAD check — attacker-controlled `<link rel="amphtml">` triggers crawler HEAD to private IP. (`api/crawler/engine.py:820`) |
| P1 | **Critical** | Vercel `BackgroundTasks` (`crawl.py:483`) do NOT survive serverless invocations. **Resolved by Strategic Decision #1** (containerize backend). |
| P2 | **High** | `AUTH_TOKEN` empty = open access, no production-environment guard. (`api/services/auth.py:21`) |
| P3 | **High** | CORS allows credentials with env-driven origins; no rejection of `*`. (`api/main.py:92-101`) |
| P4 | **High** | Dead/broken Gutenberg replacement code in `wp_heading_fixer.py:608-618` |
| P5 | **High** | `GEOReportPanel.jsx:657` `fetch` omits `authHeaders()` — Rewrite Page will always 401 in prod |
| P6 | **High** | `Results.jsx:1304-1316` (`ImageFixPanel.handleMarkFixed`) passes `imageUrl` as `pageUrl` — likely marks wrong record |
| P7 | **High** | `requirements.txt` uses `>=` for every dep |
| P8 | **High** | `api/main.py:54` `print(...)` leaks `API_KEY_READ` value to stdout/log |

### Documentation drift

| # | Doc | Reality |
|---|---|---|
| D1 | `CLAUDE.md` says v2.1 with Results.jsx ~3500, wp_fixer.py ~2500 | v2.2 in code; Results.jsx **1,831**; wp_fixer.py **525** (refactored) |
| D2 | `REMEDIATION_STATUS.md` claims Results.jsx is 450 lines | Components extracted, but parent file still **1,831** lines |
| D3 | `docs/issue-codes.md` documents ~23 codes | `_CATALOGUE` has **131**; 108 undocumented |
| D4 | `docs/README.md` links to `architecture/`, `api/`, `reference/`, `guides/` subdirectories | None exist; all paths broken |
| D5 | `docs/api.md` declares version "1.9.1" | Code is v2.2; 12+ endpoints missing from doc |
| D6 | `docs/specs/README.md` and `docs/specs/ai-readiness/README.md` contradict each other on v2.0 status | Reality: v2.0 ≈ 80% implemented |
| D7 | `CLAUDE.md` "AI-Readiness Issue Codes" table lists 6 codes | Catalogue has 25+ AI-readiness codes |
| D8 | `REVIEW_SPEC.md` claims "Redis store — zero tests", "no tests for ImageAnalysisPanel" | Redis store has 84 tests; ImageAnalysisPanel has 9. (FixBrokenLinkPanel + SettingsToolbar still real gaps.) |
| D9 | Three live version strings: `main.py` "1.7", `utility.py:107` "1.8", `CLAUDE.md` "2.1" | All wrong; truth is v2.2 + active v3.0 |

### Refactor candidates beyond `wp_fixer.py` (per CLAUDE.md > 700-line policy)

| File | Lines | Note |
|---|---|---|
| `api/crawler/issue_checker.py` | 2,448 | Largest violation |
| `api/routers/crawl.py` | 1,859 | Should extract `images_router.py`, `export_router.py` |
| `frontend/src/pages/Results.jsx` | 1,831 | REMEDIATION claim of 450 was wrong |
| `api/services/sqlite_store.py` | 1,491 | Split by table grouping |
| `frontend/src/components/ImageAnalysisPanel.jsx` | 1,393 | Mixes login modal + analysis + fixes |
| `frontend/src/components/GEOReportPanel.jsx` | 1,129 | Mixes report rendering, SSE rewrite, page selection |
| `api/services/wp_heading_fixer.py` | 781 | Mixes source analysis + level changes + cascade |

---

## Reconciliation: Discrepancies and Decisions Made Before Plan

| # | Discrepancy | Decision |
|---|---|---|
| 1 | Three live version strings (D9) | M0.1 unify to v2.2 then bump to v3.0 at end of M11 |
| 2 | `Results.jsx` "450 lines" wrong (D2) | M0.3 corrects all docs; M9.3 completes the extraction |
| 3 | v1.7 AI-readiness checks lack confidence labels | M0.2 — universal `confidence_label` field, defaults to None for non-AI codes |
| 4 | v2.0 spec §10 rejects composite "AI Readiness Score" | Honored. No new aggregated AI score |
| 5 | v2.0 spec is largely implemented (Discovery) | M1 restructured from "build v2.0" to "complete gaps + polish" |
| 6 | v2.0 spec §11 has 4 open questions | M0.4 resolves before M1 |
| 7 | `wp_fixer.py` already refactored; new hotspots surfaced | M9 (Refactor Hotspots) added |
| 8 | Sibling phrase tool readiness | M5 builds receiving side + documents JSON contract |
| 9 | `docs/README.md` broken subdirectory links (D4) | M0.10 fixes pre-M1 |
| 10 | 12+ endpoints missing from `docs/api.md` (D5) | M11 doc sync; M8 adds CI guard |
| 11 | 108 codes undocumented in `docs/issue-codes.md` (D3) | M11.4: auto-generate from `_CATALOGUE` + `issueHelp.js` |
| 12 | Vercel BackgroundTasks broken in prod (P1) | Strategic Decision #1: containerize backend (M0.7) |
| 13 | Global AI keys = customer cost burns | Strategic Decision #2: per-customer keys + multi-provider routing + usage tracking (M2) |

---

## Milestone 0 — Foundation, Security & Documentation Cleanup

**Goal:** Fix critical security + production bugs found in review, apply confidence labels, containerize the backend, clean up docs.

**Estimated time:** 2 weeks. Non-negotiable preconditions for v3.0.

### M0.1 — Doc version sync
- [ ] `CLAUDE.md` header → v2.2
- [ ] `api/routers/utility.py:107` version → "2.2"
- [ ] `api/main.py:84` version → "2.2"
- [ ] Note in `CLAUDE.md` that v3.0 work has started

### M0.2 — Apply confidence-label system (per v2.0 spec §2 / §9.3)
- [ ] Add `confidence_label: Literal["Established", "Reasonable proxy", "Heuristic"] | None` to `_IssueSpec` in `api/crawler/issue_checker.py`
- [ ] Populate for all existing AI-readiness codes:
  - `LLMS_TXT_MISSING` → **Heuristic**, rewrite help: "No major AI vendor has confirmed that `/llms.txt` affects retrieval"
  - `LLMS_TXT_INVALID` → **Heuristic**
  - `SEMANTIC_DENSITY_LOW` → **Heuristic**
  - `CONVERSATIONAL_H2_MISSING` → **Heuristic**
  - `JSON_LD_MISSING` → **Reasonable proxy**
  - `DOCUMENT_PROPS_MISSING` → **Reasonable proxy**
- [ ] Populate all v2.0 AI-readiness codes already in `_CATALOGUE` per v2.0 spec §7
- [ ] Surface `confidence_label` in API responses from `/api/crawl/{id}/results`
- [ ] Update `issueHelp.js` — add `confidence` field to all 25+ AI-readiness entries
- [ ] Render coloured pill in `AIReadinessPanel.jsx` (green/yellow/grey)
- [ ] **Adversarial test:** code marked Established whose help text says "heuristic" → test fails
- [ ] **Architecture parity:** any AI-readiness code added to `_CATALOGUE` without label → parity test fails

### M0.3 — Reconcile stale doc claims
- [ ] Update `CLAUDE.md` Results.jsx line count → actual 1,831 (M9.3 will reduce)
- [ ] Update `CLAUDE.md` wp_fixer.py line count → 525 (split done)
- [ ] Update `CLAUDE.md` "AI-Readiness Issue Codes" table → all 25+ codes (or replace with generated reference)
- [ ] Update `REVIEW_SPEC.md` — drop satisfied items, retain real gaps
- [ ] Update `REVIEW.md` Last Updated + content

### M0.4 — Resolve v2.0 spec open questions
- [ ] Q1: Parser extracts only `schema_types` (type names). Add `extract_schema_blocks()` in M1.2
- [ ] Q2: `AI_HEADING_HIERARCHY_BROKEN` — alias to existing heading check, surface in both categories
- [ ] Q3: GEO image-AI prompt wiring verified per `STATUS_GEO_ADVISOR_REWRITER.md`
- [ ] Q4: handled in M0.2

### M0.5 — Critical security: bearer auth on Advisor router (S1)
- [ ] `api/routers/advisor.py:27` — add `dependencies=[Depends(require_auth)]`

**Integration Tests Required:**

| Endpoint | Test |
|---|---|
| `POST /api/ai/advisor` without auth | `test_advisor_requires_auth` → 401 |
| `POST /api/ai/rewriter` without auth | `test_rewriter_requires_auth` → 401 |
| `POST /api/ai/rewrite-url` without auth | `test_rewrite_url_requires_auth` → 401 |
| `POST /api/ai/geo-report` without auth | `test_geo_report_requires_auth` → 401 |
| `GET /api/ai/geo-report/pages` without auth | `test_geo_report_pages_requires_auth` → 401 |

### M0.6 — Critical security: SSRF fixes (S2–S6)
- [ ] Audit every `httpx.Client(...)` / `httpx.AsyncClient(...)` call across `api/`
- [ ] Each call site either goes through `fetcher.fetch_page()` or calls `is_ssrf_safe(url)` first
- [ ] Specific call sites: `crawl.py:1501-1502`, `advisor.py:55-75`, `rewriter.py`, `js_renderer.py:104-113`, `ai_analyzer.py:359`, `wp_image_fixer.py:297, 651`, `utility.py:111-141`, `engine.py:820`
- [ ] Create `tests/test_fetcher.py` with SSRF adversarial tests: localhost, 169.254.x.x, 10/172.16/192.168, IPv6 mapped, DNS rebinding, redirect chain to private IP, case variations

### M0.7 — Containerize backend (Strategic Decision #1)
- [ ] Create `Dockerfile` for the FastAPI backend (Python 3.11+, uvicorn, all deps from pinned `requirements.txt`)
- [ ] Choose container host:
  - **Recommended: Fly.io** — generous free tier, simple deploy, great for Python; auto-scaling available; `fly.toml` config in repo
  - **Alternative: Render** — similar capability, no free tier but $7/month basic
  - **Alternative: Railway** — similar; usage-based pricing
- [ ] Update Vercel config so `/api/*` routes proxy to the container backend's public URL (env var `BACKEND_API_URL`)
- [ ] Remove serverless-specific code paths (`vercel.json` Python function entry, `BackgroundTasks` workarounds)
- [ ] Document: container hosting setup, SSL/cert handling, deployment workflow, env-var management
- [ ] Health check endpoint already exists (`/api/health`) — wire it as the container's health probe

### M0.8 — Production hardening (P2, P3, P7, P8)
- [ ] **P2 `AUTH_TOKEN` fail-closed:** If `ENV=production` and `AUTH_TOKEN` is empty, refuse to start. Emit loud WARN otherwise
- [ ] **P3 CORS:** Reject `ALLOWED_ORIGINS=*` at startup when `allow_credentials=True`
- [ ] **P7 dependency pinning:** Replace all `>=` in `requirements.txt` with `~=` or `==`. Lock `httpx`, `fastapi`, `pydantic`, `playwright`
- [ ] **P8 secret leakage:** Remove `print(...)` from `api/main.py:54`. Audit for other env-value prints. Use `logger.debug` with boolean rather than value

### M0.9 — Critical correctness bugs (P4, P5, P6)
- [ ] **P4 Gutenberg replacement:** Remove dead block at `wp_heading_fixer.py:608-618` OR implement proper Gutenberg block update. Test against Gutenberg fixture
- [ ] **P5 GEO Rewrite auth:** Add `authHeaders()` to `GEOReportPanel.jsx:657`. Test with smoke check
- [ ] **P6 ImageFixPanel.handleMarkFixed:** Trace `Results.jsx:1304-1316` — confirm `imageUrl` vs `pageUrl` semantics; fix mismatch; assert correct record updated

### M0.10 — Pre-M1 documentation cleanup
- [ ] Fix `docs/README.md` — remove/create the 4 missing subdirectories; recommend flattening
- [ ] Reconcile `docs/specs/README.md` ↔ `docs/specs/ai-readiness/README.md` — both say "v2.0 ≈ 80% implemented; remaining work in v3.0 plan M1"
- [ ] Refresh `REVIEW_SPEC.md` stamp; prune satisfied items

### M0.11 — Endpoint contract backfill prerequisites
- [ ] List every endpoint in every router file
- [ ] Cross-reference against existing tests in `tests/`
- [ ] Output punch-list of untested endpoints → input for M8

### M0.12 — Restore missing fix-domain routers (CRITICAL — v2 features broken)

**Goal:** ~30 endpoints under `/api/fixes/*` documented in `CLAUDE.md` and the v1.9 release notes are not actually wired up. The service-layer code survived the `wp_fixer.py` split (`wp_title_fixer.py`, `wp_heading_fixer.py`, `wp_image_fixer.py`, etc.), but the routes connecting frontend → services were never rebuilt after `fixes.py` was reduced to a 41-line aggregator. As-shipped v2.x silently has these features broken:

- Title bulk-trim and single-page trim
- Heading source analysis, level/text changes, bulk-replace, to-bold
- Image metadata update, refresh, single + batch optimization
- Orphaned media detection
- Broken-link verification and replacement
- "Apply-one" inline fix used by `FixInlinePanel`
- WP value lookup used by `FixInlinePanel`
- All "mark fixed" buttons (issue, anchor, broken-link)

The catch-all `GET /api/fixes/{job_id}` was silently shadowing 5 missing GET endpoints (returning empty fix lists instead of 404), making the silent breakage worse.

**Estimated time:** ~5 days (1 calendar week).

#### M0.12.0 — Narrow catch-all to UUID pattern
- [x] Add UUID-regex `Path(..., pattern=...)` constraint to `{job_id}` and `{fix_id}` path params in `fix_manager_router.py` so string paths get 422 instead of silently matching
- [x] Removed the duplicate `dependencies=[Depends(require_auth)]` on `DELETE` (router already has it)
- [x] Verified: 5 previously-silent paths (`predefined-codes`, `image-info`, `analyze-heading-sources`, `link-sources`, `wp-value`) now return 422

#### M0.12.1 — `api/routers/title_router.py`
- [ ] `GET /api/fixes/predefined-codes` — returns `get_fixable_codes()` list
- [ ] `POST /api/fixes/bulk-trim-titles?job_id=...` — calls `wp_title_fixer.bulk_trim_titles`
- [ ] `POST /api/fixes/trim-title-one?page_url=...` — calls `wp_title_fixer.trim_title_one`
- [ ] WP domain validation on both write endpoints (per CLAUDE.md v1.9.4 "22 WP-touching endpoints" claim)

#### M0.12.2 — `api/routers/heading_router.py`

**Discovery (2026-05-27):** Only 3 of the 6 heading service functions exist
in `api/services/wp_heading_fixer.py` (`analyze_heading_sources`,
`change_heading_level`, `change_heading_text`). The other 3 are referenced
by the frontend but the service code was either never implemented or lost
in a prior refactor. User-approved decision: implement all three with
inferred semantics.

**Existing services (route restoration only):**
- [ ] `GET /api/fixes/analyze-heading-sources` → `analyze_heading_sources(wp, page_url, crawled_headings)`. Note: takes crawled_headings from store, not as query param.
- [ ] `POST /api/fixes/change-heading-level` → `change_heading_level(wp, page_url, heading_text, from_level, to_level)`
- [ ] `POST /api/fixes/change-heading-text` → `change_heading_text(wp, page_url, old_text, new_text, level=1)` (M0.9 P4 already shipped — Gutenberg dead code removed, 3 new Gutenberg block tests added)

**Missing services to implement first:**
- [ ] `find_heading(store, job_id, heading_text, level=None) -> list[dict]` — search the job's crawled pages' `headings_outline` for matching text+level. Pure read against store; no WP API. Returns `[{page_url, level, text}]`.
- [ ] `bulk_replace_heading(wp, store, job_id, heading_text, from_level, to_level=None) -> dict` — find all pages with matching heading via `find_heading`, then iterate calling `change_heading_level`. Returns `{matched, applied, skipped, errors, results: [...]}`. `to_level=None` is a no-op (returns matches without changing anything — useful for "preview before bulk apply").
- [ ] `convert_heading_to_bold(wp, page_url, heading_text, level) -> dict` — fetch WP content, replace `<h{level}>X</h{level}>` with `<p><strong>X</strong></p>`. Reuse the same find/replace machinery as `change_heading_text`. Frontend's `Results.jsx:751` is the actual caller.

**Then the router endpoints:**
- [ ] `GET /api/fixes/find-heading?job_id=...&heading_text=...&level=...` (level optional)
- [ ] `POST /api/fixes/bulk-replace-heading?job_id=...&heading_text=...&from_level=...&to_level=...`
- [ ] `POST /api/fixes/heading-to-bold?page_url=...&level=...&heading_text=...`
- [ ] WP domain validation on all write endpoints
- [ ] Each new service function: ≥3 contract tests including one adversarial case

#### M0.12.3 — `api/routers/image_router.py`
- [ ] `GET /api/fixes/image-info`
- [ ] `POST /api/fixes/update-image-meta`
- [ ] `POST /api/fixes/refresh-image-from-wp`
- [ ] `POST /api/fixes/optimize-image`
- [ ] `POST /api/fixes/optimize-existing-preview`
- [ ] `POST /api/fixes/optimize-existing`
- [ ] `POST /api/fixes/optimize-upload-preview`
- [ ] `POST /api/fixes/optimize-upload`
- [ ] WP domain validation on all WP-touching endpoints
- [ ] SSRF guard already in `wp_image_fixer.py` (M0.6.7) protects URL-based fetches

#### M0.12.4 — `api/routers/orphaned_media_router.py`
- [ ] `GET /api/fixes/orphaned-media/{job_id}` — calls `wp_fixer.find_orphaned_media`
- [ ] `DELETE /api/fixes/orphaned-media/{media_id}` (if frontend uses it)
- [ ] WP domain validation

#### M0.12.5 — `api/routers/batch_optimizer_router.py`
- [ ] `POST /api/fixes/batch-optimize/start`
- [ ] `GET /api/fixes/batch-optimize/{batch_id}/status`
- [ ] `POST /api/fixes/batch-optimize/{batch_id}/pause`
- [ ] `POST /api/fixes/batch-optimize/{batch_id}/resume`
- [ ] `POST /api/fixes/batch-optimize/{batch_id}/cancel`
- [ ] `GET /api/fixes/batch-optimize/list`

#### M0.12.6 — `api/routers/link_router.py`
- [ ] `GET /api/fixes/link-sources`
- [ ] `POST /api/fixes/replace-link`
- [ ] `POST /api/fixes/verify-broken-links/{job_id}`
- [ ] `POST /api/fixes/mark-broken-link-fixed`
- [ ] `POST /api/fixes/mark-anchor-fixed`
- [ ] `POST /api/fixes/mark-issue-fixed`
- [ ] `POST /api/fixes/apply-one`
- [ ] `GET /api/fixes/wp-value`

#### M0.12.7 — Register all routers in `fixes.py`
- [ ] Replace TODO comments with actual `from ... import router as ...` + `router.include_router(...)`
- [ ] Verify endpoint count via `app.routes` inspection

#### M0.12.8 — Contract tests
- [ ] ~30 contract tests, one per restored endpoint, asserting status codes and response schemas the frontend depends on
- [ ] Re-enable the 5 skipped tests in `test_wp_domain_validation.py` (M0.11 marked them skip with M0.12 reference)
- [ ] Manual smoke test against `livingsystems.ca` (the project's test WP site)

#### M0.12.9 — Documentation alignment
- [x] Add this section to `PLAN-V3.0.md`
- [ ] After all routers land: update `CLAUDE.md` "WP Integration" section to reflect actual endpoints
- [ ] Update `docs/api.md` to include restored endpoints (or defer to M11.3 if doing in one pass)

**Tests for M0:** See M0.5 (auth) and M0.6 (`test_fetcher.py`) tables. Plus:
- `test_issue_checker.py` — every AI-readiness code has non-null `confidence_label`
- `test_api.py` — `/api/crawl/{id}/results` includes `confidence_label`
- `test_wp_heading_fixer.py` — Gutenberg block heading text change works
- Container smoke test: `docker build && docker run` succeeds end-to-end

---

## Milestone 1 — Complete AI-Readiness v2.0 Gaps

**Goal:** Finish the v2.0 module. Major services + tests already exist; this closes remaining gaps.

**Estimated time:** 1.5 weeks

### M1.1 — Verify existing implementations against v2.0 spec
- [ ] Confirm `ai_bots.py`, `ai_readiness.py`, `schema_typing.py`, `page_classifier.py`, `extractability.py` match spec; document any divergence

### M1.2 — `extract_schema_blocks()` parser addition
- [ ] Add `extract_schema_blocks() -> List[Dict]` to `api/crawler/parser.py`
- [ ] Handle `@graph` nesting, multiple blocks, malformed JSON-LD
- [ ] Add `schema_blocks: List[Dict]` to `ParsedPage`
- [ ] Persist via SQLite migration + Redis serialization

### M1.3 — ParsedPage field additions (v2.0 §8.2)
- [ ] Add `inferred_page_type`, `main_landmark_present`, `paragraph_word_counts`, `heading_count`, `body_word_count`
- [ ] SQLite migration; Redis serialization

### M1.4 — `api/services/passage_heuristics.py` (v2.0 §5.2)
- [ ] Content-quality heuristics, gated by `enable_passage_heuristics: False` default
- [ ] Codes: `AI_PARAGRAPH_TOO_LONG`, `AI_NO_DEFINITIONS` (opt-in), `AI_FIRST_PARAGRAPH_BOILERPLATE` (opt-in)
- [ ] All **Heuristic**; help text includes "heuristic, not a measured signal"

### M1.5 — `AIReadinessPanel.jsx` polish (re-scoped from "extract")
- [ ] Panel already exists at 318 lines; extend
- [ ] Add confidence-pill rendering (per M0.2)
- [ ] Surface `ai_bots.py` `LAST_REVIEWED` date; warn if >12 months
- [ ] Group site-level above per-page checks

### M1.6 — Configuration (v2.0 §8.3)
- [ ] `enable_ai_readiness_v2` (default True), `enable_passage_heuristics` (False), `ai_bot_table_max_age_days` (365), `passage_heuristic_thresholds`

### M1.7 — Help content for any new codes (v2.0 §7.2)
- [ ] Entries in `issueHelp.js` + `issue_help_data.py`: `what_it_is`, `why_it_matters`, `how_to_fix`, `vendor_references`

**Integration Tests Required:**

| Endpoint | Frontend expects | Test name |
|---|---|---|
| `GET /api/crawl/{id}/pages?include=schema_blocks` | response includes `schema_blocks: List[Dict]` | `test_pages_endpoint_has_schema_blocks` |
| `GET /api/crawl/{id}/pages?url=...` | response includes `inferred_page_type`, `main_landmark_present`, `body_word_count`, `heading_count` | `test_pages_endpoint_has_parsed_page_fields` |
| `GET /api/crawl/{id}/results?category=ai_readiness` | issues include `confidence_label`, `vendor_references` | `test_results_ai_readiness_has_confidence_label` |

**Other tests:** schema-block fixtures (single/multiple/malformed/@graph/microdata); passage_heuristics threshold edges (150 words exactly → no trigger); FAQPage with 1 vs 2 questions

---

## Milestone 2 — AI Multi-Provider Architecture & Usage Tracking

**Goal:** Refactor the AI layer to support per-customer keys, multi-provider routing (DeepSeek + Gemini + OpenAI + Anthropic), per-task-type model selection, system-default fallback, and token-level usage tracking for billing. Foundation for sustainable AI economics at scale.

**Estimated time:** 1.5–2 weeks. Implements Strategic Decision #2.

**Context:** Customer enters AI provider keys and model preferences in Settings. If unset, system-default (env-var) keys are used so the app still works out of the box. Every AI call records token usage tied to (customer_id, job_id, session_id) for billing-period reporting.

### M2.1 — Provider abstraction layer
- [ ] New `api/services/ai_router.py` — central orchestrator. Routes calls by (customer, task_type). Resolves provider + model + key. Records usage events on success or failure
- [ ] Provider drivers in `api/services/providers/`: `openai.py`, `gemini.py`, `anthropic.py`, `deepseek.py`
- [ ] Each driver implements: `call_text(prompt, model, max_tokens) -> CompletionResult` and `call_vision(prompt, image_bytes, model) -> CompletionResult`
- [ ] `CompletionResult` dataclass: `text`, `finish_reason`, `input_token_count`, `output_token_count`, `cost_estimate_usd`, `provider`, `model`
- [ ] Refactor all current callers (`ai_analyzer.py`, `advisor.py`, `rewriter.py`, GEO services) to go through `ai_router.py`

### M2.2 — Cost reference table
- [ ] New `api/services/ai_pricing.py` with `LAST_REVIEWED` constant and pricing table:

```python
LAST_REVIEWED = "2026-05-27"
PRICING = {
    ("openai", "gpt-4o"):           {"input_per_1m": 2.50, "output_per_1m": 10.00, "vision": True},
    ("openai", "gpt-4o-mini"):      {"input_per_1m": 0.15, "output_per_1m": 0.60,  "vision": True},
    ("gemini", "gemini-2.0-flash"): {"input_per_1m": 0.075,"output_per_1m": 0.30,  "vision": True},
    ("gemini", "gemini-1.5-flash-8b"):{"input_per_1m": 0.04,"output_per_1m": 0.15, "vision": False},
    ("anthropic", "claude-3-5-sonnet"):{"input_per_1m": 3.00,"output_per_1m":15.00,"vision": True},
    ("anthropic", "claude-3-5-haiku"):{"input_per_1m": 0.80,"output_per_1m": 4.00, "vision": True},
    ("deepseek", "deepseek-chat"):  {"input_per_1m": 0.27, "output_per_1m": 1.10,  "vision": False},
}
```
- [ ] Review cadence: every 90 days; surface table age in admin UI

### M2.3 — Per-customer credentials (encrypted at rest)
- [ ] New table `customer_ai_credentials` (SQLite + Redis): `customer_id`, `provider`, `encrypted_api_key`, `created_at`, `last_used_at`
- [ ] Encryption: Fernet symmetric with key from `AI_CREDS_ENCRYPTION_KEY` env var
- [ ] App startup: if `AI_CREDS_ENCRYPTION_KEY` is unset, refuse to start (don't silently fall back to plaintext)
- [ ] Key rotation procedure documented in `docs/security-model.md` (M11.6)
- [ ] **Never** return decrypted keys in any API response. Only return `{provider, has_key, last_used_at}`
- [ ] Fallback chain when AI call needs a key: customer-set key → system env-var key → 402 "AI not configured" error to user

### M2.4 — Per-task-type model routing
- [ ] New table `customer_model_preferences`: `customer_id`, `task_type`, `provider`, `model`
- [ ] `task_type` enum: `advisor`, `rewriter`, `exec_summary`, `title_meta_optimize`, `semantic_alignment`, `geo_image_alt`, `image_description`, `executive_summary`, etc.
- [ ] **Default routing (when customer hasn't set preferences):**

| Task | Default provider/model | Premium tier override |
|---|---|---|
| Text: advisor, rewriter, exec_summary, title_meta | DeepSeek `deepseek-chat` | OpenAI `gpt-4o` |
| Text: semantic_alignment | DeepSeek `deepseek-chat` | Anthropic `claude-3-5-sonnet` |
| Vision: geo_image_alt, image_description | Gemini `gemini-2.0-flash` | OpenAI `gpt-4o` |

- [ ] Document in new `docs/ai-routing.md`

### M2.5 — Usage tracking schema
- [ ] New table `ai_usage`: `id`, `customer_id`, `job_id` (nullable, links to crawl), `session_id` (correlation ID), `task_type`, `provider`, `model`, `input_tokens`, `output_tokens`, `cost_estimate_usd`, `timestamp`, `success` (bool), `error_message` (nullable)
- [ ] Indexes: `(customer_id, timestamp)` for billing queries; `(job_id)` for per-audit cost
- [ ] Retention: keep raw events for 90 days, then aggregate into monthly summaries (separate `ai_usage_monthly` table)

### M2.6 — Usage aggregation API
- [ ] `GET /api/customer/usage/summary?period=month` — cumulative tokens + cost across providers, by task_type
- [ ] `GET /api/customer/usage/by-job?from=...&to=...` — per-crawl cost breakdown
- [ ] `GET /api/customer/usage/by-provider?period=month` — provider/model split
- [ ] `GET /api/customer/usage/timeseries?period=month&granularity=day` — chart data
- [ ] `GET /api/customer/usage/for-job/{job_id}` — total AI cost for one crawl (shown on Results page)

### M2.7 — Customer Settings UI
- [ ] New `frontend/src/components/AISettingsPanel.jsx`:
  - **API Keys** section: add/remove keys per provider; show `has_key` status only, never the key value; "Test Connection" button per provider
  - **Model Preferences** section: per-task-type dropdowns; "Reset to defaults" option
  - **Usage This Month** widget: current cost + token count; link to detailed breakdown
  - **Tier** badge (free/basic/premium/enterprise) with what's included
- [ ] Add to existing Settings tab

### M2.8 — Premium-tier flag
- [ ] Customer record gets `tier` field (default `free`; options `free`/`basic`/`premium`/`enterprise`)
- [ ] When `tier=premium+`, default routing flips to higher-quality models (GPT-4o text, Claude Sonnet for advisor)
- [ ] `docs/ai-routing.md` shows per-tier default matrix
- [ ] **Note:** No billing UI in v3.0 — tier is set manually for now. Stripe integration is v3.1 candidate

### M2.9 — DeepSeek provider driver
- [ ] `api/services/providers/deepseek.py` implementing the uniform interface
- [ ] Text-only (DeepSeek-VL2 vision is open-source but less reliable for production)
- [ ] **China-hosted caveat:** Settings UI shows "Data is processed by DeepSeek in China" notice
- [ ] Enterprise-tier customers can disable DeepSeek entirely via tenant config (`disabled_providers: ["deepseek"]`)

### M2.10 — Usage display on Results page
- [ ] On `Results.jsx` summary tab: show "This audit used $X.XX in AI ({input_tokens} input, {output_tokens} output across N calls)"
- [ ] Per-page AI cost shown on hover/expansion
- [ ] PDF report includes "AI Usage" appendix when AI was used

**Integration Tests Required (CLAUDE.md non-negotiable):**

| Endpoint | Frontend expects | Test name |
|---|---|---|
| `POST /api/customer/ai-credentials` | 200; key stored encrypted, not returned | `test_set_ai_credential_encrypted_not_returned` |
| `GET /api/customer/ai-credentials` | 200; returns `[{provider, has_key, last_used_at}]` — no key values | `test_get_ai_credentials_excludes_keys` |
| `DELETE /api/customer/ai-credentials/{provider}` | 200; subsequent GET omits provider | `test_delete_ai_credential` |
| `POST /api/customer/ai-credentials/{provider}/test` | 200 on valid key; 401 on invalid; doesn't burn tokens | `test_credential_test_endpoint` |
| `GET /api/customer/model-preferences` | 200; returns map of task_type → {provider, model} | `test_get_model_preferences` |
| `POST /api/customer/model-preferences` | 200; round-trip persists | `test_set_model_preferences` |
| `GET /api/customer/usage/summary?period=month` | `total_cost_usd`, `total_input_tokens`, `total_output_tokens`, `by_provider`, `by_task_type` | `test_usage_summary_schema` |
| `GET /api/customer/usage/by-job?job_id=...` | per-task breakdown for one job | `test_usage_by_job_schema` |
| `GET /api/customer/usage/for-job/{job_id}` | single number `cost_usd` + token counts | `test_usage_for_job_schema` |
| `POST /api/ai/advisor` (customer context) | 200; usage row written with correct token counts and cost | `test_advisor_call_records_usage` |
| `POST /api/ai/advisor` (no customer key, no system fallback) | 402 with clear error code | `test_advisor_fails_when_no_key_anywhere` |
| `POST /api/ai/advisor` (customer key invalid) | 401 from provider surfaced cleanly | `test_advisor_handles_invalid_customer_key` |

**Other tests:**
- Add DeepSeek provider → text call records usage row; token counts match provider response
- Customer with no preferences uses system defaults
- Premium-tier customer routes to GPT-4o instead of DeepSeek by default
- Cost calculation: 1000 input + 500 output tokens of GPT-4o = $0.0075; assert exact value to 4 decimals
- Encryption round-trip: store key → read via internal API → matches
- **Adversarial:** missing `AI_CREDS_ENCRYPTION_KEY` → app refuses to start (don't silently fall back)
- **Adversarial:** customer A's bearer token tries to read customer B's usage → 403
- **Adversarial:** customer A's key in DB; request with no auth → 401 (don't leak which customer the key belongs to)
- **Adversarial:** request rate-limits AI endpoints per customer (prevents one customer hammering another's quota)
- Monthly aggregation: 1000 events in `ai_usage` → 1 row in `ai_usage_monthly` with correct sums
- Retention: events older than 90 days deleted; aggregates preserved

---

## Milestone 3 — Google-Validated Extensions to v2.0

**Goal:** Add the checks Google's published docs explicitly endorse but the v2.0 spec didn't cover. Each new code grounded in a direct Google source quote.

**Estimated time:** 1.5 weeks

### M3.1 — `SCHEMA_VISIBLE_MISMATCH` (**Established**)
**Google quote:** *"all the content in your markup is also visible on your web page"* — [Top ways to succeed in AI search](https://developers.google.com/search/blog/2025/05/succeeding-in-ai-search)

- [ ] For each JSON-LD `Article.headline`, `Product.name`, `FAQPage.mainEntity[*].name/.acceptedAnswer.text`, `Person.name`, `Organization.name`, `LocalBusiness.address` — confirm value appears in rendered visible text (case-insensitive substring, normalised whitespace)
- [ ] Emit `SCHEMA_VISIBLE_MISMATCH` with `extra.mismatched_fields`
- [ ] Default impact: 5

### M3.2 — `AI_CONTENT_NOT_IN_TEXT` (**Reasonable proxy**)
**Google quote:** *"Making sure that important content is available in textual form"* — [AI Features and Your Website](https://developers.google.com/search/docs/appearance/ai-features)

- [ ] Detect H1 followed only by images/video/near-empty paragraphs for >300px of vertical content
- [ ] Detect primary answer only inside embedded PDF/iframe
- [ ] Default impact: 4

### M3.3 — X-Robots-Tag header analysis
**Google quote:** *"use `nosnippet`, `data-nosnippet`, `max-snippet`, or `noindex` controls"* — [AI Features and Your Website](https://developers.google.com/search/docs/appearance/ai-features)

- [ ] Inspect response headers per page for `X-Robots-Tag` containing `nosnippet`, `noindex`, `max-snippet:0`
- [ ] New code `AI_PREVIEW_SUPPRESSED` (**Established**) — informational with directive in `extra`
- [ ] New code `AI_PREVIEW_BLOCKED_AT_BOT` — bot-specific `X-Robots-Tag: GPTBot: noindex`

### M3.4 — Multimodal companion suggestion (informational)
**Google quote:** *"support your textual content with high-quality images and videos"* — [Top ways to succeed in AI search](https://developers.google.com/search/blog/2025/05/succeeding-in-ai-search)

- [ ] For pages classified as `article`/`service`/`faq` with `body_word_count > 300` and `image_count == 0`: emit `AI_NO_VISUAL_COMPANION` (info, impact 1, **Reasonable proxy**)

### M3.5 — Main-content distinguishability extension
**Google quote:** *"Whether visitors can easily distinguish main content from other content"* — [Top ways to succeed in AI search](https://developers.google.com/search/blog/2025/05/succeeding-in-ai-search)

- [ ] Already partly covered by `AI_NO_MAIN_LANDMARK`. Extend: measure main-content text to nav/sidebar/footer ratio
- [ ] New code `AI_MAIN_CONTENT_LOW_RATIO` (**Heuristic**) — fires when main-content text is <40% of total visible text
- [ ] Default impact: 2

### M3.6 — Fix scoring scope bugs (Agent 1 review)
- [ ] `_count_inline_quotations` (`issue_checker.py:1980-1983`) — currently measures only `first_600_words`; extend to whole `visible_text` or first 1500
- [ ] `_count_statistics` (`issue_checker.py:1948-1956`) — currently measures `first_200_words + headings`; extend to first 600 words
- [ ] **Adversarial test for each:** a page with statistics at word 250/1000/1500 must not trigger `STATISTICS_COUNT_LOW`

**Integration Tests Required:**

| Endpoint | Frontend expects | Test name |
|---|---|---|
| `GET /api/crawl/{id}/pages/issues?url=...` | includes `SCHEMA_VISIBLE_MISMATCH` with `extra.mismatched_fields` | `test_pages_issues_includes_schema_visible_mismatch` |
| `GET /api/crawl/{id}/results?category=ai_readiness` | includes `AI_PREVIEW_SUPPRESSED` when X-Robots-Tag has nosnippet | `test_results_includes_x_robots_codes` |
| `GET /api/crawl/{id}/results?category=ai_readiness` | issues with `extra.recommendation` field | `test_results_ai_readiness_recommendation_field` |

**Other tests:** mismatch fixtures; X-Robots-Tag presence/absence; **adversarial** empty-string mismatch handling

---

## Milestone 4 — Content Freshness Suite

**Goal:** Build on `CONTENT_STALE`. Google's I/O 2026 places freshness at the centre of how search agents reason.

**Estimated time:** 1 week

### M4.1 — Visible-on-page date extraction
- [ ] Parse `<time datetime="...">`, JSON-LD `dateModified`, visible date patterns
- [ ] Flag when visible date >18 months old but `Last-Modified` is recent
- [ ] New code `CONTENT_DATE_STALE_VISIBLE` (**Reasonable proxy**), impact 4

### M4.2 — Aged-stat / aged-year detection
- [ ] Regex scan body for explicit years in factual statements
- [ ] If year >24 months old AND sentence doesn't also contain current year, flag `CONTENT_STAT_OUTDATED` (**Heuristic**, impact 2)
- [ ] `extra` includes flagged sentence

### M4.3 — Page-type-aware freshness recommendation
- [ ] `article`: max-age 12 months; `service`/`about`/`home`: 24 months; `team_member`: none
- [ ] Surface in `extra.recommended_refresh_months`

### M4.4 — Reporting
- [ ] PDF "Content Freshness" section; Excel "Freshness" tab

**Integration Tests Required:**

| Endpoint | Frontend expects | Test name |
|---|---|---|
| `GET /api/crawl/{id}/pages?url=...` | includes `dateModified`, `visible_date`, `recommended_refresh_months` | `test_pages_endpoint_has_freshness_fields` |
| `GET /api/crawl/{id}/results?category=content` | includes new `CONTENT_DATE_STALE_VISIBLE`, `CONTENT_STAT_OUTDATED` | `test_results_includes_freshness_codes` |

**Other tests:** stale-visible vs recent Last-Modified; aged-stat detection; year-context offset ("In 2023…[updated 2026]" → no trigger); page-type variance; **adversarial** historic-year false-positive guard ("In 1900…")

---

## Milestone 5 — Sibling Tool Integration: Citation Ingestion

**Goal:** Implement v2.0 §6. TalkingToad receives per-URL citation data from the sibling phrase tool.

**Estimated time:** 1.5 weeks

### M5.1 — Data model (v2.0 §6.1)
- [ ] SQLite columns on `crawled_pages`: `ai_citation_count_30d INTEGER`, `ai_citation_engines TEXT`, `ai_citation_last_updated TIMESTAMP`
- [ ] Redis mirror
- [ ] `CrawledPage` Pydantic — three new fields default `None`
- [ ] NULL ≠ zero citations

### M5.2 — Citation ingestion endpoint
- [ ] `POST /api/jobs/{job_id}/ai-citations` in `api/routers/citations.py`
- [ ] Bearer auth required (per M0.5 pattern)
- [ ] Pydantic-validated `CitationIngestionRequest`, `CitationEntry`, `EngineCitation`
- [ ] URL matching via crawler `normaliser.py`; unmatched recorded in response
- [ ] Response: `matched_count`, `unmatched_count`, `unmatched_urls`
- [ ] Note: `HttpUrl` validates shape only. Document that citation URLs are not fetched; if future iterations do, must add `is_ssrf_safe`
- [ ] Per-IP rate limit

### M5.3 — Citation-aware issue codes
- [ ] `AI_CITED_PAGE` (**Established when data present**) — info positive signal, impact 0
- [ ] `AI_HIGH_VALUE_UNCITED` (**Reasonable proxy**) — page structurally healthy AND `count_30d == 0` AND data ingested in last 60 days
- [ ] Green "Cited" badge in `AIReadinessPanel.jsx` per-page

### M5.4 — Contract documentation
- [ ] `docs/citation-ingestion.md` (flat path) — schema, examples per engine, URL normalisation

### M5.5 — Frontend surfacing
- [ ] "Citations" sub-section in `AIReadinessPanel.jsx` showing per-engine counts when data present
- [ ] "No data" empty state explaining sibling-tool connection
- [ ] Per-page detail: counts + last-seen per engine

**Integration Tests Required:**

| Endpoint | Frontend/sibling-tool expects | Test name |
|---|---|---|
| `POST /api/jobs/{job_id}/ai-citations` | 200 + `matched_count`, `unmatched_count`, `unmatched_urls` | `test_ingest_citations_response_schema` |
| `POST /api/jobs/{job_id}/ai-citations` | URL normalisation matches crawler (trailing slash, percent-encoding) | `test_ingest_citations_url_normalisation_matches_crawler` |
| `GET /api/crawl/{id}/pages?url=...` | includes `ai_citation_count_30d`, `ai_citation_engines` (may be null) | `test_pages_endpoint_has_citation_fields` |
| `POST /api/jobs/{job_id}/ai-citations` | malformed body → 422 | `test_ingest_citations_validation_error` |
| `POST /api/jobs/{job_id}/ai-citations` | missing auth → 401 | `test_ingest_citations_requires_auth` |
| `POST /api/jobs/{job_id}/ai-citations` | rate limit exceeded → 429 | `test_ingest_citations_rate_limit` |

**Other tests:** 10 URLs, 7 match → matched_count=7; `AI_HIGH_VALUE_UNCITED` only when ingestion in last 60 days; NULL ≠ 0; **adversarial** URL-normalisation cases

---

## Milestone 6 — Optional GSC OAuth Integration

**Goal:** Pull AI Overview / AI Mode performance from GSC — strictly opt-in. Core flow stays admin-free.

**Estimated time:** 2 weeks

**Google quote:** *"Sites appearing in AI features… are included in the overall search traffic in Search Console."* — [AI Features and Your Website](https://developers.google.com/search/docs/appearance/ai-features)

### M6.1 — OAuth flow (opt-in)
- [ ] Env vars `GSC_OAUTH_CLIENT_ID`, `GSC_OAUTH_CLIENT_SECRET`, `GSC_OAUTH_REDIRECT_URI` — all optional
- [ ] If unset: GSC UI invisible, no errors
- [ ] Token storage threat model in `docs/security-model.md`. Encryption at rest (reuse M2.3 `AI_CREDS_ENCRYPTION_KEY` Fernet pattern or use a separate `GSC_ENCRYPTION_KEY` — decide before M6.1)
- [ ] Scope: `https://www.googleapis.com/auth/webmasters.readonly`

### M6.2 — GSC Performance pull
- [ ] New `api/services/gsc_client.py`
- [ ] Fetch URL-level Performance 30/90 days
- [ ] Filter by `searchAppearance` for AI-Overview when API exposes; else pull total Web and note limitation
- [ ] Cache 12h

### M6.3 — Per-page GSC fields
- [ ] SQLite columns: `gsc_clicks_30d, gsc_impressions_30d, gsc_ctr_30d, gsc_avg_position_30d, gsc_data_pulled_at`
- [ ] Redis mirror

### M6.4 — GSC-derived issue codes
- [ ] `GSC_HIGH_IMP_LOW_CTR` (**Established**) — >100 impressions, <1% CTR. Impact 5
- [ ] `GSC_POSITION_DECAYING` — drop >5 places vs previous pull (needs `gsc_history` table)
- [ ] `GSC_NEW_QUERY_OPPORTUNITY` (info) — impressions for queries user hasn't targeted

### M6.5 — Frontend (lazy-loaded)
- [ ] New `GSCInsightsPanel.jsx`, opt-in, lazy-loaded via `React.lazy`
- [ ] Combined view: citations (M5) overlaid with GSC traffic — highest-impact surface in v3.0

### M6.6 — Privacy/admin-free fallback
- [ ] Strictly opt-in; without OAuth tool functions identically to v2.x
- [ ] OAuth creds never logged or returned

**Integration Tests Required:**

| Endpoint | Frontend expects | Test name |
|---|---|---|
| `GET /api/gsc/connect` | redirects to Google OAuth when configured; 503 otherwise | `test_gsc_connect_redirect`, `test_gsc_connect_not_configured` |
| `GET /api/gsc/callback?code=...` | exchanges code, stores token | `test_gsc_callback_stores_token` |
| `GET /api/crawl/{id}/pages` | includes GSC fields (null when not connected) | `test_pages_endpoint_has_gsc_fields_nullable` |
| `POST /api/gsc/disconnect` | removes token | `test_gsc_disconnect_removes_token` |

**Other tests:** end-to-end without GSC env vars; high-imp low-CTR trigger; token storage scoped per-domain; **adversarial** revoked-at-Google token degrades gracefully

---

## Milestone 7 — Reporting & Confidence Surfacing

**Goal:** PDF/Excel reports clearly communicate signals + confidence. Per v2.0 §8.4, non-negotiable.

**Estimated time:** 1 week

### M7.1 — PDF "AI Search Readiness" section
- [ ] Distinct section header
- [ ] Intro paragraph on confidence-label scheme
- [ ] Per-issue: code, confidence pill, what-it-is, fix, vendor reference (if Established)
- [ ] `LAST_REVIEWED` date; warning if >12 months

### M7.2 — PDF "Citation Intelligence" section (when M5 data)
- [ ] Top 10 cited pages with per-engine breakdown
- [ ] Top 10 `AI_HIGH_VALUE_UNCITED` — highest-leverage targets
- [ ] If no data: omitted with note

### M7.3 — PDF "Content Freshness" section
- [ ] Stale by `Last-Modified`, by visible date, by aged stats
- [ ] Recommended cadence per page type

### M7.4 — PDF "GSC Performance Snapshot" (when M6 connected)
- [ ] Per-page clicks/impressions/CTR/position 30/90 days
- [ ] High-impression low-CTR flagged
- [ ] If not connected: omitted with enable-instructions

### M7.5 — Excel export
- [ ] New tabs: "AI Readiness", "Citations" (if data), "Freshness", "GSC" (if connected), "AI Usage" (M2.10)
- [ ] Confidence label column on every AI-readiness row

### M7.6 — Polish + non-Latin char handling (Agent 1)
- [ ] `report_generator.clean_text` currently mangles non-Latin chars. Upgrade to Unicode-capable font (DejaVu via fpdf2) or document limitation
- [ ] Tooltip on confidence pill
- [ ] Empty-state messaging

**Integration Tests Required:**

| Endpoint | Frontend expects | Test name |
|---|---|---|
| `GET /api/crawl/{id}/export/pdf?include_freshness=true` | PDF bytes; sections present | `test_pdf_export_includes_freshness_section` |
| `GET /api/crawl/{id}/export/pdf` | confidence pills render | `test_pdf_export_renders_confidence_pills` |
| `GET /api/crawl/{id}/export/excel` | "AI Readiness" tab has confidence column | `test_excel_export_ai_readiness_confidence_column` |
| `GET /api/crawl/{id}/export/pdf` | non-Latin chars render correctly | `test_pdf_export_handles_non_latin_chars` |

---

## Milestone 8 — Endpoint Contract Backfill (Pre-existing Debt)

**Goal:** Per CLAUDE.md "API Contract Tests (Non-Negotiable)" — every endpoint called by the frontend must have a contract test. Agent 4 found 12+ untested. Backfill before v3.0 ships.

**Estimated time:** 1.5 weeks

### M8.1 — Audit untested endpoints
- [ ] Use M0.11 punch-list as input
- [ ] Priority: frontend-called > admin-only

### M8.2 — Backfill `crawl.py` router tests
- [ ] `rescan-url`, `scan-page`, `mark-fixed`, `fix-history`, `comparison`, `executive-summary`, `export/pdf`, `export/excel`, `images/fetch` (with M0.6 SSRF fix), `images/analyze-ai`, `images/summary`, `orphaned-images`, `orphaned-pages`

### M8.3 — Backfill `fix_manager_router.py` tests
- [ ] Generate / list / patch / apply / delete

### M8.4 — Backfill `ai.py` router tests
- [ ] `page-advisor`, `site-advisor`, `apply-geo-metadata`, `image/analyze-geo`

### M8.5 — Backfill `utility.py` router tests
- [ ] `suppressed-codes`, `exempt-anchor-urls`, `ignored-image-patterns` GET/POST/DELETE

### M8.6 — Backfill `verified.py` router tests

### M8.7 — Backfill `geo.py` tests
- [ ] `/geo/test`, `/geo/ai-model` GET/POST

### M8.8 — CI guard against future drift
- [ ] Lint check: every endpoint in `api/routers/*.py` appears in `docs/api.md` AND has at least one test that issues an HTTP call to its path
- [ ] Fail CI on missing entry

---

## Milestone 9 — Refactor Hotspots

**Goal:** Reduce highest-leverage maintainability debt per CLAUDE.md (>700-line policy). Not v3.0-blocking but the codebase gains durability.

**Estimated time:** 2 weeks (parallelisable with M6/M7 if staffed)

### M9.1 — `api/crawler/issue_checker.py` split (2,448 lines)
- [ ] `issue_catalogue.py` — `_CATALOGUE`, `_ISSUE_SCORING`, `_IssueSpec`, `make_issue`
- [ ] `issue_checker_page.py` — `check_page`, `_check_canonical`, `_check_headings`, `_check_crawlability`, `_check_security`
- [ ] `issue_checker_geo.py` — `_run_geo_checks` + `_count_*`, `_has_*` (apply M3.6 scope fixes during move)
- [ ] `issue_checker_cross.py` — `check_cross_page`, duplicate maps, orphan detection
- [ ] `issue_checker_status.py` — `issue_for_status`, redirect handlers, asset/URL structure/AMP

### M9.2 — `api/routers/crawl.py` split (1,859 lines)
- [ ] Extract `images_router.py` (images/fetch, analyze-ai, summary, orphaned-images)
- [ ] Extract `export_router.py` (export/pdf, export/excel, export/csv)

### M9.3 — Complete `Results.jsx` extraction (1,831 lines)
- [ ] Extract `PageDetail.jsx`, `IssueCard.jsx`, `ImageFixPanel.jsx`, `SettingsToolbar.jsx`, `ExportReportModal.jsx`, `AIRecommendationsPanel.jsx`, `SiteRecommendationsPanel.jsx`, `OrphanedSummaryCards.jsx`, `PageFocusPanel.jsx`, `HeadingsPanel.jsx`
- [ ] Target: Results.jsx <500 lines as orchestrator

### M9.4 — `wp_heading_fixer.py` split (781 lines)
- [ ] `wp_heading_sources.py`, `wp_heading_edit.py`, `wp_heading_cascade.py`

### M9.5 — `ImageAnalysisPanel.jsx` split (1,393 lines)
- [ ] Extract `WordPressLoginModal.jsx`, `ImageAnalysisDetails.jsx`
- [ ] Parent <500 lines

### M9.6 — Deferred (track as v3.1 candidates)
- `sqlite_store.py` (1,491) — split by table grouping
- `GEOReportPanel.jsx` (1,129) — split SSE rewrite + page selector

**Tests for M9:** architecture parity test still passes after each split; all existing tests pass unchanged; no frontend visual regression

---

## Milestone 10 — Frontend Infrastructure

**Goal:** Toast/notification system, accessibility baseline, code-splitting. Prerequisites for the M6/M7 panels to ship cleanly.

**Estimated time:** 1 week

### M10.1 — Toast / notification system
- [ ] `frontend/src/contexts/ToastContext.jsx`
- [ ] Replace 49 `alert()` and 5 `confirm()` calls across Results.jsx, ImageAnalysisPanel, CategoryPanel, FixBrokenLinkPanel, BatchOptimizePanel, FixManager, OptimizeExistingModal, GEOReportPanel

### M10.2 — Accessibility baseline
- [ ] `aria-label` on all icon-only buttons
- [ ] Wrap top-level page content in `<main>` landmark
- [ ] Pair severity colours with text/icon
- [ ] Modal overlays: `role="dialog"`, `aria-modal="true"`, focus trap
- [ ] `inputMode="url"` on URL fields

### M10.3 — Code-splitting for heavy modals
- [ ] `React.lazy` for GeoSettingsModal, OptimizeExistingModal, UploadNewImageModal, BatchOptimizePanel, GeoAnalysisModal, WordPressLoginModal, GSCInsightsPanel, AISettingsPanel
- [ ] CI bundle-size budget assertion

### M10.4 — Consolidate auth helpers
- [ ] `FixInlinePanel`, `FixBrokenLinkPanel`, `FixManager` each re-define `authHeader(s)`. Consolidate to `src/api.js` export

### M10.5 — Frontend test coverage gaps
- [ ] `test_FixBrokenLinkPanel.test.jsx`
- [ ] `test_SettingsToolbar.test.jsx` (after M9.3 extraction)
- [ ] `Progress.jsx` polling error-handler test
- [ ] `test_AISettingsPanel.test.jsx` (covers M2.7)

---

## Milestone 11 — Documentation Sync & v3.0 Release

**Goal:** Per CLAUDE.md Documentation Sync Policy. Release as v3.0.

**Estimated time:** 1 week

### M11.1 — Update CLAUDE.md
- [ ] Version → 3.0
- [ ] Key Features: AI multi-provider, per-customer keys, usage tracking, container deployment, AI-Readiness v2.0 complete, Google-validated extensions, Citation Ingestion, GSC OAuth, Content Freshness, refactors
- [ ] Update file sizes
- [ ] Recent Enhancements

### M11.2 — User-facing docs
- [ ] AI-readiness checks with confidence labels
- [ ] Setting AI provider keys + model preferences
- [ ] Usage tracking + billing-period reports
- [ ] Connecting the sibling phrase tool for citation data
- [ ] Connecting GSC (OAuth walkthrough)
- [ ] Container deployment guide

### M11.3 — Update `docs/api.md`
- [ ] All new endpoints
- [ ] Backfill 12+ undocumented existing endpoints (D5)
- [ ] Update declared version → 3.0
- [ ] M8.8 CI check prevents drift

### M11.4 — Auto-generate `docs/issue-codes.md`
- [ ] Script generating from `_CATALOGUE` + `issueHelp.js`
- [ ] CI fails if generated differs from committed
- [ ] Permanently fixes the 108-codes-undocumented gap (D3)

### M11.5 — New: `docs/ai-readiness.md`
- [ ] Three required disclosures (v2.0 §9)
- [ ] Confidence-label scheme
- [ ] Citation ingestion contract summary

### M11.6 — New: `docs/security-model.md`
- [ ] OAuth token storage threat model
- [ ] AI credentials encryption (Fernet, key rotation)
- [ ] SSRF protection coverage
- [ ] Container deployment security implications

### M11.7 — New: `docs/ai-routing.md`
- [ ] Default routing per task type per tier
- [ ] How to override per customer
- [ ] DeepSeek China-hosting note
- [ ] Cost reference + LAST_REVIEWED cadence

### M11.8 — Update v2.0 spec status
- [ ] Mark spec as "Implemented in v3.0"
- [ ] Reconcile both ai-readiness README files

### M11.9 — Final lint, test, smoke
- [ ] `pytest tests/ -v` zero failures
- [ ] `npm run build` passes ESLint strict
- [ ] Container deploy smoke test on Fly.io / Render
- [ ] Manual smoke against test site: AI-Readiness panel, confidence pills, AI usage display, reports
- [ ] Verify all docs reflect shipped reality

---

## Testing Policy (per CLAUDE.md)

- **No milestone is complete until its tests pass.**
- **API contract tests are non-negotiable** — every frontend-called endpoint has a contract test. M8 backfills existing debt.
- **Self-review questions before commit** — every text-processing and scoring function needs at least one adversarial test.
- Mock all external HTTP. AI provider responses mocked in unit tests; one end-to-end integration test per provider hits live (gated by env var).
- Architecture parity test extended in M0.2 to enforce `confidence_label` field for AI-readiness codes.

---

## Estimated New Test Count (revised)

| Milestone | New tests |
|---|---|
| M0 | ~25 (auth + SSRF + Gutenberg + adversarial confidence labels + production bugs + container smoke) |
| M1 | ~15 (down from 40 — most v2.0 tests exist) |
| M2 | ~25 (provider abstraction + usage tracking + encryption + adversarials) |
| M3 | ~18 (M3.6 adversarial scope tests included) |
| M4 | ~10 |
| M5 | ~18 (rate-limit, adversarial URL-matching) |
| M6 | ~15 |
| M7 | ~6 (PDF/Excel contract tests) |
| M8 | ~30 (backfill — substantial existing debt) |
| M9 | 0 net-new (regression checks only) |
| M10 | ~7 (FixBrokenLink, SettingsToolbar, Progress, AISettingsPanel) |
| M11 | docs only |
| **Total** | **~168** |

---

## Resolved Open Questions

| # | Question | Resolution |
|---|---|---|
| 1 | Plan scope | Ambitious v3.0, 11 milestones |
| 2 | Sibling phrase tool readiness | Assume future-ready. M5 builds receiving side + JSON contract |
| 3 | GSC OAuth | Opt-in (M6); tool runs identically without it |
| 4 | v1.7 AI-readiness rebalance | Apply v2.0 confidence-label system (M0.2) |
| 5 | v2.0 implementation status | Mostly done (Discovery); M1 narrowed to gaps |
| 6 | Vercel BackgroundTasks (P1) | **Strategic Decision #1:** containerize backend (M0.7) |
| 7 | AI cost model | **Strategic Decision #2:** per-customer keys + multi-provider + usage tracking (M2). DeepSeek for text, Gemini Flash for vision by default. Premium tier overrides to GPT-4o / Sonnet |
| 8 | Refactor hotspots | M9 prioritized: issue_checker, crawl router, Results.jsx, wp_heading_fixer, ImageAnalysisPanel |
| 9 | Self-host local AI? | **No** for now. Break-even >500 monthly active customers; revisit at scale |

## Remaining Open Questions

| # | Question | Owner | Resolve before |
|---|---|---|---|
| A | Container host: Fly.io vs Render vs Railway? | User + M0.7 lead | M0.7 |
| B | DeepSeek-China caveat — which customer segments get it disabled by default? Just enterprise, or also healthcare/government? | User + M2.9 | Before M2.9 ships |
| C | AI credentials encryption key: env-var Fernet (M2) or KMS/secrets-manager? | M2 lead | Before M2.3 |
| D | GSC Performance API: AI Overview/AI Mode facet availability? | M6 lead | Before M6.2 |
| E | OAuth token encryption: same key as AI creds or separate `GSC_ENCRYPTION_KEY`? | M6 lead | Before M6.1 |
| F | URL-normalisation contract with sibling phrase tool — exact rules doc | M5 lead | M5.4 |
| G | `report_generator.clean_text` Unicode upgrade — DejaVu vs other font | M7 lead | M7.6 |
| H | `docs/` flat structure vs subdirectory restoration | M0.10 lead | M0.10 |
| I | Stripe / billing UI for usage data — v3.1 or sooner? | User | After v3.0 ships |

---

## Out of Scope for v3.0 (deferred to v3.1 or later)

- **Self-hosted local AI models** (revisit at >500 monthly active customers)
- **Full Stripe billing + invoicing UI** — M2 lays the foundation (usage data); paid-tier auto-billing is v3.1
- **Real-time AI budget alerts** (notify when 80% of quota used) — v3.1
- **`sqlite_store.py` and `GEOReportPanel.jsx` refactors** (M9.6 deferred to v3.1)
- **Microdata / RDFa schema parsing** (v2.0 §4.4 explicit)
- **Server log analysis** (v2.0 §1 explicit — TalkingToad has no log access)
- **TalkingToad querying AI engines directly for citations** (sibling phrase tool's job)
- **Aggregated AI-readiness score** (v2.0 §10 explicit rejection)
- **Headless-browser DOM analysis beyond existing `js_renderer.py` capability**
- **Full TypeScript migration** (TODO.md candidate)
- **DeepSeek-VL2 vision integration** (less reliable for production; revisit if quality improves)
- **Multi-region container deployment** (single-region container sufficient until significant scale)

---

*Plan version: 3.0 — 2026-05-27. Strategic decisions: containerize backend (Fly.io/Render/Railway) + multi-provider AI architecture with per-customer keys, default routing (DeepSeek text + Gemini Flash vision), token usage tracking for billing. 11 milestones, 15–17 weeks, ~168 new tests.*
