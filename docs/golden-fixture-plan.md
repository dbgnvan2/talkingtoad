# Golden Fixture Site — plan & scoping

> **Status: MVP built (2026-07-23).** Lives in `tests/golden_site/` (server +
> `build_pages.py` + `pages/`) driven by `tests/test_golden_site.py`. The real
> crawl engine runs against the served site and asserts per-page ground truth.
> Current coverage: **~58 distinct issue codes** across 45 crawled pages. See
> `tests/golden_site/README.md`. The phase-2 gaps below (images/TLS/JS/PDF/
> external links) are not yet built.

**Goal:** a controlled test website of *N* pages with a **known ground-truth set
of issues**, crawled end-to-end by the real engine, so we can assert detection
is working. Two failure directions, both "something is wrong":

- a **planted** issue is **not** surfaced → false negative / regression;
- an issue appears on a **clean control page** → false positive.

This is the missing **end-to-end** net. Unit tests check checkers in isolation on
hand-built `ParsedPage` objects; the golden site exercises the whole pipeline —
fetch → parse → check → cross-page → score → aggregate → serialize — catching
integration bugs unit tests can't (parser↔checker wiring, the cross-page pass
running at all, scoring aggregation, the full-crawl-vs-rescan divergence, P16
layer-skew).

---

## Design (recommended)

1. **`tests/golden_site/` — static fixture pages.** Hand-crafted `.html`, plus
   `robots.txt` and `sitemap.xml`. Each page is built to trigger *exactly* an
   intended set of codes (and nothing incidental). Includes:
   - **issue pages** — one condition family per page where possible;
   - **cross-page sets** — deliberate title/meta duplicates, a near-duplicate
     body pair, an orphan page, inconsistent Organization names across pages;
   - **clean control pages** — perfect pages that must produce **zero** issues
     (the false-positive tripwire).
2. **`manifest.yaml`** — the ground truth: `page → { expect: [codes], forbid: [codes] }`
   (control pages use `expect: []`).
3. **Local server harness** (pytest fixture) — serves the directory over HTTP on
   `localhost:PORT`, and handles the conditions a static file can't: 404s for
   planted broken links, 301/302 for redirect codes, gzipped sitemap, a JS-shell
   page. A *real* server (not respx) is deliberate — it drives the true fetch path.
4. **Assertion test** — `run_crawl("golden", "http://localhost:PORT/")`, group
   issues by page, then assert per page: every `expect` code present, no `forbid`
   code present, controls silent. One failure names the page + the missing/extra
   code.

---

## Coverage — what a static golden site can and cannot reach

| Well covered (static HTML + server tricks) — ~110–130 / 155 codes |
|---|
| metadata (title/meta/OG/canonical/favicon/lang) · headings · links incl. broken (404 pages) · redirects (301/302/chain/loop) · crawlability (thin, noindex-meta, orphan, sitemap-missing, high-depth) · url_structure · semantic_html · most ai_readiness/GEO (schema present/incomplete/typed, dates, author byline+credentials, conversational-H2, first-viewport, statistics/quotations/citations, llms.txt, AI-bot robots directives) · **all cross-page** (title/meta dup, near-dup body, boilerplate, entity name/sameAs/author consistency) |

| Needs extra scaffolding (phase 2) | Out of scope for a crawl site |
|---|---|
| **Images** (IMG_OVERSIZED/POOR_COMPRESSION/OVERSCALED/FORMAT_LEGACY/SLOW_LOAD/DUPLICATE) → include real crafted image assets | **WP fix *flows*** — need a WordPress REST API → separate WP-staging test |
| **TLS/security** (HTTP_PAGE, MIXED_CONTENT, MISSING_HSTS, HTTPS_REDIRECT_MISSING, WWW_CANONICALIZATION) → serve http+https w/ self-signed cert | **AI/LLM verdict codes** (advisor, geo_llm burial) → need an LLM (or a mocked one) |
| **JS-render diff** (JS_RENDERED_CONTENT_DIFFERS, UA_CONTENT_DIFFERS, JS_DEPENDENT_NAVIGATION) → Playwright path (RAW_HTML_JS_DEPENDENT is fakeable now) | **GSC / citation / performance** (AI_CITED_PAGE, AI_HIGH_VALUE_UNCITED, refresh/authority) → crawl-independent; test via seeded data |
| **PDF** (PDF_TOO_LARGE, DOCUMENT_PROPS_MISSING) → include PDF fixtures | |

---

## Effort estimate

| Piece | Effort |
|---|---|
| Server harness (serve dir + 404/redirect/robots/sitemap) + assertion runner | ~0.5–1 day |
| ~20–30 fixture pages covering critical static-reachable codes + controls + manifest | ~1.5–2.5 days |
| Phase-2 extensions (images / PDF / TLS / JS-render) | ~1–2 days *each area* |
| **MVP** (~15 issue pages + 3 controls, no images/TLS/JS) | **~2 days** |

The labour is authoring HTML that trips exactly one intended condition with no
accidental extras — tractable because the detection logic is known, but fiddly.

---

## Recommended path

Build the **MVP** first: ~15 issue pages hitting the critical detection paths
(metadata, headings, links/redirects, crawlability, the GEO/ai_readiness core,
and the cross-page family) + 3 clean control pages + `manifest.yaml` + the harness
+ one pytest. Then extend to images/PDF/TLS/JS in a second pass. The MVP alone
gives a real end-to-end regression net and doubles as a demo/QA site.
