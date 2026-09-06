# TalkingToad v2 — Research & Advice: what a great nonprofit SEO+AEO audit should look for

**Date:** 2026-09-06
**Status:** advisory — informs `docs/pending/2026-09-06_v2-audit-framework.md`; not itself a spec.
**Audience:** owner + implementation agents.

> Naming note: "v2" here is the owner's framing for the *audit-product upgrade* — "a great
> product for nonprofits to run a website audit like the Living Systems one." Repo semver is
> currently 3.0.0, and `PLAN-V4.0.md` is the in-flight education layer. This note is about the
> *audit substance*; the repo's version tags are orthogonal.

---

## Sources

- Google Search Central — *Optimizing your website for generative AI features on Google Search* (2026-07-10)
- Google Search Essentials + crawling/indexing documentation
- Semrush — *The technical SEO checklist for search engines and AI search* (2026-06-23)
- HubSpot — *Answer engine optimization best practices* (2026)
- Shortlist — *The Technical SEO Audit Checklist: 50+ things we actually check*
- Internal: the `seo-site-audit` skill (hard-won from livingsystems.ca audits), the Living Systems SEO & AEO Audit action-items doc.

---

## Three findings that shape v2

1. **AEO/GEO is not a separate discipline.** Google's generative-AI features are "rooted in our
   core Search ranking and quality systems." SEO fundamentals carry straight through; the "answer
   engine" work is a deeper pass over the same checks, not a new category bolted on.
2. **Consequence changed, not the checklist.** A technical fault that once dented rankings now
   risks invisibility across search *and* AI surfaces simultaneously (Semrush).
3. **Google explicitly disavows part of the AEO toolkit.** `llms.txt`, "chunking", special AI
   markup/markdown, rewriting-for-AI, inauthentic mentions, and special AI-only schema are all
   called out as non-factors *for Google Search*. (They still matter to ChatGPT/Perplexity/agents
   — see the positioning decision below.)

---

## The framework — 10 categories a complete audit covers

1. **Crawlability & indexation** — robots.txt (incl. per-bot AI directives), sitemap present + referenced, noindex (meta *and* `X-Robots-Tag`), self-referencing canonicals, one host, crawl budget, JS rendering, soft-404s, orphans.
2. **Architecture & internal linking** — click depth ≤3, broken links, descriptive anchors, redirect chains/loops, pagination discoverability, breadcrumbs + `BreadcrumbList`.
3. **On-page & metadata** — unique titles/descriptions, one H1 + logical hierarchy, image alt.
4. **Performance & Core Web Vitals** — LCP <2.5s / INP <200ms / CLS <0.1, image optimization (WebP/AVIF, **explicit dimensions → CLS**, lazy-load with LCP exclusions), render-blocking resources, caching/CDN.
5. **HTTPS, security, status codes** — HTTPS everywhere, mixed content, HSTS, correct 404/410 vs soft-404.
6. **Mobile & international** — viewport, responsive, mobile usability, `hreflang`, correct `lang`/`og:locale`.
7. **Local & entity** — NAP consistency (site + GBP + directories), `LocalBusiness`/`Organization` schema completeness (address, coords, hours-or-suppressed, service area, logo, legal name, phone), one canonical identity.
8. **Content & E-E-A-T** — non-commodity content, unique POV, named authors + credentials, freshness, editorial cross-linking.
9. **Analytics & measurement** — tag once, consent mode, conversion-event tracking, cross-domain/outbound, 404 tracking.
10. **AEO/AI-readiness increment** — AI crawler access, extractable plain text, answer-first structure, question-shaped headings, cited sources, unique stats/original research, valid schema matching visible content, measure via GSC "Generative AI performance" report.

---

## Gap vs TalkingToad today

| # | Category | Covered? | The gap |
|---|---|---|---|
| 1 | Crawlability & indexation | **Strong** | soft-404 detection; per-bot AI directives only partially; crawl-budget/log analysis is out of crawl reach (needs server logs) |
| 2 | Architecture & linking | **Strong** | weak-link tier (1 inbound link) missing — `ORPHAN_PAGE` fires at zero only |
| 3 | On-page & metadata | **Strong** | H1==title redundancy not flagged |
| 4 | Performance & CWV | **Weak** | `RENDERING` (4 codes) needs external CWV data to fire; no static CLS/lazy-load/dimension checks |
| 5 | HTTPS/security | **Covered** | — |
| 6 | Mobile & international | **Weak** | only `MISSING_VIEWPORT_META`; no tap-target/mobile-usability; `og:locale` region not checked |
| 7 | Local & entity | **Partial** | `ENTITY_*` good on NAP/hours; missing logo, `legalName`, `areaServed`/`priceRange`/geo depth |
| 8 | Content & E-E-A-T | **Partial** | author byline/credentials present; freshness present; non-commodity/content-quality is LLM-judged, not crawlable |
| 9 | Analytics | **Partial** | `ANALYTICS_*`, `CTA_TRACKING_*`, `OUTBOUND_LINK_UNTRACKABLE` exist; conversion-event/cross-domain config is config-level, not crawl |
| 10 | AEO/AI-readiness | **Overbuilt + miscast** | 75 codes, but weighted toward "AI-SEO technique" Google disavows (llms.txt, chunking) vs. the crawlability/entity/E-E-A-T Google says actually drives AI visibility |

**Bottom line:** TalkingToad is already excellent at categories 1–3, 5 (the crawl/on-page core).
v2 should close **4, 6, 7** (performance, mobile, entity depth — the repo's own never-built
"Phase 2") and **reposition 10** honestly. That is the whole strategic message: **not more checks —
the right checks, and honest labels about which engine each signal moves.**

---

## The AEO positioning decision

Google (the dominant surface) says it does **not** use `llms.txt`, chunking, or special AI markup.
ChatGPT/Perplexity/agents **do** consume `llms.txt` and self-contained sections. Both are true, so
the product should say so rather than implying one universal "AI-ready" score:

- Keep `LLMS_TXT_*`, `CHUNKS_NOT_SELF_CONTAINED`, and the answer-engine-pattern codes, but **relabel**
  their scope: "relevant to ChatGPT / Perplexity / AI agents — *not* a Google AI Overviews factor."
- Weight the *Google* half of AEO on what Google says moves it: crawlability, non-commodity content,
  E-E-A-T, local/entity detail. That is exactly categories 4/6/7 above, not more AI codes.

This is a copy/positioning change plus scoring honesty — not a code deletion. It prevents
TalkingToad from selling a "100% AI-ready" score a Google-focused nonprofit later learns was
optimizing the wrong engine.

---

## V2 recommendation (prioritized)

**P0 — foundational, platform-agnostic, closes the biggest holes (spec's main tranche):**
- Performance: image dimensions (CLS), lazy-load hygiene, render-blocking — as *reliable static
  checks* where possible, and lab CWV via the existing `js_renderer.py`/`web_vitals.py` path (never
  fake metrics with static guessing).
- Accessibility/WCAG: form-field labels, contrast, focus indicators, error announcements.
- Entity depth: Organization logo, `legalName`, `areaServed`/`priceRange`/geo.
- Weak-link tier (1 inbound internal link).
- The **"Decisions to resolve"** surface — a first-class non-crawl output enumerating the facts only
  the org can decide (legal name, address type, hours, archive indexability, forms/platforms,
  reviewers, backups). This is the consultant-grade differentiator no crawler has.

**P1 — the honest-AEO repositioning + measurement:**
- Relabel/rewright `AI_READINESS` scope per engine; add the GSC "Generative AI performance"
  visibility note to reporting.
- Analytics configuration audit (conversion events, cross-domain) as an opt-in, read-only pass —
  the same shape as the existing WordPress audit.

**P2 — lower value / higher false-positive risk:**
- Typo heuristic over slugs/headings/schema values (three real finds in one audit, but high FP risk —
  default off, `info`/low with an explicit caveat).
- Tap-target/mobile-usability (needs rendering measurement).

## Out of scope / deprioritize

- Off-site authority: local-listing reconciliation (GBP + directory APIs), backlink inventory, and
  outreach all need paid third-party data. Already documented as declined in `docs/overview.md`.
- Crawl-budget/log analysis: needs server logs, which a public crawler can't reach.
- Content *quality* (E-E-A-T depth): LLM-judged at best; keep as advisory, not a scored crawl code.
