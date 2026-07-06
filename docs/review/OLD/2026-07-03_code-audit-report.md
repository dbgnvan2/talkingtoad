---
status: audit-in-progress
audit_date: 2026-07-03
auditor: Claude Code (Opus 4.8) — WITH repo access
scope: Phases 1–3 of CLAUDE_CODE_AUDIT_PROMPT.md
priority_order: factual correctness > minimal assumptions > explicit uncertainty
---

# TalkingToad Scoring & Checker Audit — Code-Verified Report

This is the review the two prior reviewers could not do: every claim below is checked
against the actual checker code and cited to `file:line`. Confidence tags:
**High** = verified in code / vendor-confirmed; **Medium** = inferred from partial evidence;
**Low** = genuinely uncertain. Each claim is tagged **[code]** (verified in source),
**[inferred]**, or **[external]** (web/vendor knowledge).

> **Status:** Phases 1–3 complete. Phase 4 in the scoring change plan; work backlog in the remediation plan.

> **Independent verification (2026-07-03):** the 15 load-bearing code claims in this report (the dead
> JS-render trio, the citation misfire, the aggregation formula, no-retry, the `Claude-User` data bug,
> the invalid `"error"` severity, the LLM dead codes, mixed-content lumping, orphan raw-HTML-only,
> the conservative title/H1 test, the two distinct ratio checks, freshness page-type awareness, the
> 62/151 confidence count, duplicate-metadata triple-fire, and the empty-anchor gaps) were re-checked
> by a separate agent with no audit context, refute-by-default, against the live code. **Result: all
> 15 CONFIRMED, none refuted or partial.** It added three corroborations: (a) the citation orphan/
> inaccessible branches are *doubly* unreachable — `diagnose_citation_issue` checks `lacks_citations`
> first and returns one code (`citation_model.py:114`); (b) `PAGE_TIMEOUT` also swallows
> `SSRF_BLOCKED` status-0 results (`fetcher.py:152-154,172-174`); (c) a *correct* labelled-element
> helper already exists at `parser.py:1254-1270`, so R2.1 is a reuse, not a rebuild. These are folded
> into the remediation plan. The scoring *judgments* (Phase 4 numbers) are NOT covered by this check —
> they still need human/SME review before the R2/R3 migration.

---

## Phase 1 — Conditional checker claims, resolved against code

### 1. `LINK_EMPTY_ANCHOR` — accessible-name coverage — **partial; concern real but mitigated**

**What the code does.** Detection is `_find_empty_anchors` / `_count_empty_anchors`
(`api/crawler/parser.py:873–914`). An `<a href>` is flagged only when **all** of these hold:
- `tag.get_text(strip=True)` is empty (`parser.py:899`) — so **visually-hidden `.sr-only` text still counts as a name** and suppresses the flag (its text is in the DOM). Good.
- no child `<img>` has non-empty `alt` (`parser.py:902–904`). Good — icon-image links with alt are exempt.
- `href` is not `#`/`javascript:`/`mailto:`/`tel:`/`data:` (`parser.py:896`). Good.

`_count_empty_anchors` then **excludes anchors that have `aria-label`** (`parser.py:876–877`),
and the emission gate is `if page.empty_anchor_count > 0` (`api/crawler/issue_checker.py:375`).
There is also a **user-managed exemption list** for known icon hrefs
(`issue_checker.py:396–397`, populated via `engine.py:123`, `routers/crawl.py:298`).

**Gaps (false-positive sources that remain):** the check does **not** honour
`aria-labelledby`, the anchor's own `title` attribute, an inline `<svg><title>`/`role="img"`
accessible name, or `<img role>`/`aria-label` on a child SVG. Icon links built with
`<svg><title>…</title></svg>` or `aria-labelledby` will be flagged despite having an
accessible name.

**Verdict.** The concern is **real but already substantially mitigated** (visible text +
img-alt + aria-label + user exemptions all suppress it). Residual FP risk is limited to
SVG-title / aria-labelledby icon links. **Impact 6 is slightly high**; the mitigations argue
it is not a 4-level nuisance either. Recommend **keep detection, add `aria-labelledby` +
`<svg><title>` + `title`-attr recognition** (Phase 5 candidate), then impact 5–6 is defensible.
Confidence: **High [code]**.

### 2. `ORPHAN_PAGE` — raw-HTML-only link discovery — **concern real**

**What the code does.** `check_cross_page` builds `linked_urls` purely from
`page.links` (`api/crawler/checkers/cross_page.py:128–144`), which are parsed from the
**raw fetched HTML** (`parser.py`), self-links excluded (`cross_page.py:143`), homepage
exempted (`cross_page.py:151`). There is **no rendered-DOM pass** in the main crawl — the only
JS renderer (`api/services/js_renderer.py`) is a separate, unwired service (see Cross-cutting
finding A). So links injected by JavaScript or produced by query/loop grids (the JetEngine
loop-grid case) are invisible, and their targets will be reported as orphans.

**Verdict.** Concern **confirmed [code]**. On dynamic/page-builder sites `ORPHAN_PAGE` is
unreliable and needs either a caveat in the finding text or a rendered-DOM link pass.
This compounds with the fixability error in Phase 3 (`ORPHAN_PAGE` is labelled
`developer_needed`, effort 4 — both wrong; adding internal links is content work).
Confidence: **High [code]**.

### 3. `ROBOTS_BLOCKED` — expected-block exemptions — **partially handled; no crawl/index distinction**

**What the code does.** In `engine.py` the crawl loop skips admin paths
(`is_admin_path`, `engine.py:398–400`) and WordPress-noise paths
(`is_wp_noise_path` when `skip_wp_archives`, `engine.py:402–404`) **before** the robots check,
so those are silently skipped and **not** flagged. Any *other* robots-disallowed URL that was
discovered as a link is flagged `ROBOTS_BLOCKED` (`engine.py:408–411`).

**Gaps.** `/wp-admin/` is covered by `is_admin_path`, but cart/checkout/search/param URLs are
only exempt insofar as `is_wp_noise_path` matches them — not a general "expected block"
allow-list. The messaging does **not** distinguish crawl-blocking (robots.txt) from
index-blocking (noindex) anywhere.

**Verdict.** Impact 9 is high for what is often an intentional block. Concern **partly real**:
recommend an "expected disallow" allow-list (cart/search/filter params) and copy that clarifies
this blocks *crawling*, not *indexing*. Confidence: **High [code]** on behaviour;
**Medium [inferred]** on impact.

### 4. `MIXED_CONTENT` — active vs passive — **concern real (no distinction)**

**What the code does.** `_count_mixed_content` (`parser.py:773–792`) counts `http://` resources
across `_MIXED_CONTENT_TAGS = {img:src, script:src, iframe:src}` (`parser.py:766`) **plus**
`<link rel=stylesheet>`. All are summed into one `mixed_content_count`; the checker emits a
single `MIXED_CONTENT` on `count > 0` (`api/crawler/checkers/security.py:40–42`).

**Verdict.** Concern **confirmed [code]**. The code does **not** separate *active* mixed content
(script/iframe/stylesheet — **blocked** by browsers, a real breakage) from *passive*
(img/media — **auto-upgraded or allowed with a warning**). A single `<img src=http://>` is scored
identically to a blocked `<script>`. Recommend splitting into active (higher impact) vs passive
(lower/informational), or at minimum reporting the breakdown in `extra`. Confidence: **High [code]**.

### 5. Image checks — stacking + LCP — **stacking confirmed; no LCP weighting**

**What the code does.** In `_check_performance` (`api/crawler/image_analyzer.py:230–290`) the four
image issues are **independent `if` branches on one image**:
`IMG_OVERSIZED` (`:234`), `IMG_SLOW_LOAD` (`:248`), `IMG_OVERSCALED` (`:260`),
`IMG_POOR_COMPRESSION` (`:275`). A single oversized, slow, over-scaled, badly-compressed hero
image emits **all four** — plus a fifth `IMG_OVERSIZED` path exists in `check_asset`
(`api/crawler/checkers/images.py:53`) for standalone asset fetches.

**Verdict.** Stacking **confirmed [code]**: up to 4 codes per image, correlated causes
(oversized ⇒ slow, oversized ⇒ poor bpp). **No LCP element is identified or weighted** anywhere.
This is a Phase 2 stacking cluster. Recommend precedence (oversized/overscaled ⇒ suppress
slow/compression as consequences) or merge into one graded `IMG_PERFORMANCE`. Confidence: **High [code]**.

### 6. `BROKEN_LINK_5XX` / `PAGE_TIMEOUT` / `EXTERNAL_LINK_TIMEOUT` — retry/persistence — **single-observation (concern real)**

**What the code does.** `fetch_page` (`api/crawler/fetcher.py:110+`) is a **single** `client.stream`
attempt with a timeout and **no retry loop / backoff / tenacity decorator** (verified: no retry
constructs in `fetcher.py` or `engine.py`). Every call site fetches once (`engine.py:237,258,436,891`).
`PAGE_TIMEOUT` fires on the **first** error with `status_code==0` (`engine.py:454–458`);
`EXTERNAL_LINK_TIMEOUT` fires once (`engine.py:649`); `BROKEN_LINK_5XX` from a single status map
(`api/crawler/checkers/links.py:52–53`).

**Verdict.** Concern **confirmed [code]** — this is failure pattern **P1** (transient recorded as
terminal). A one-off 5xx/timeout from a CDN hiccup becomes a permanent negative with no
re-check. Recommend 1 retry with backoff before firing any of the three, and/or marking them
retryable. **This is the highest-severity Phase-1 correctness finding.** Confidence: **High [code]**.

### 7. `JS_RENDERED_CONTENT_DIFFERS` — main vs total DOM — **NOT WIRED IN (dead code)** — see Cross-cutting A

**What the code does.** The check **exists and is scored** — `(6,4)` at `registry.py:230` (my first
grep missed it due to a shell glob error; it is **not** a phantom). The computation is
`js_renderer.py:205–215`: `added_ratio = |rendered_tokens − raw_tokens| / |rendered_tokens|`,
threshold `>0.20` (`_DIFF_THRESHOLD`, `js_renderer.py:41`). Tokens are a **set** of visible words
with `script/style/nav/footer` stripped (`_tokenize`, `js_renderer.py:70–83`) — i.e. neither pure
main-content nor raw total-DOM, but de-duplicated visible text. Using a set (unique tokens) and
excluding nav/footer materially reduces the "fires on every page" risk the reviewers feared.

**BUT:** `run_js_render_checks` is **called only from tests** (`tests/test_js_renderer.py`), never
from `engine.py` or any router, and **no `make_issue("JS_RENDERED_CONTENT_DIFFERS"/"UA_CONTENT_DIFFERS"/"CONTENT_CLOAKING_DETECTED")` call exists anywhere in `api/`**. Playwright is also optional
(`HAS_PLAYWRIGHT`, `js_renderer.py:27–31`) and degrades to skipped.

**Verdict.** The tokenisation design is **reasonable** (concern would be Medium if wired), but
in production these three codes **can never fire** — they are **dead scored codes**. This is a
major Phase 5 finding. Confidence: **High [code]**.

### 8. `NOINDEX_META` / `AI_BOT_BLANKET_DISALLOW` — staging-vs-production awareness — **none**

**What the code does.** `_check_crawlability` reads `page.is_indexable` and emits `NOINDEX_HEADER`
vs `NOINDEX_META` based only on `robots_source` (`api/crawler/checkers/crawlability.py:13–34`).
`AI_BOT_BLANKET_DISALLOW` fires on `User-agent:* Disallow:/` (`api/services/ai_readiness.py:46–47`,
`_is_blanket_disallow` `:136–141`). **Neither has any staging/production heuristic** — no check of
hostname patterns (`staging.`, `dev.`, `.local`), no environment awareness.

**Verdict.** The owner's stated real risk — staging directives surviving a SiteGround→production
cutover — is **not addressed [code]**. These are correctly high-impact when they fire, but there
is no signal that "this looks like a production domain still carrying a staging block," which is
exactly the case worth escalating. Recommend a production-domain heuristic that raises severity /
adds a "possible leftover staging directive" note. Confidence: **High [code]**.

### 9. `TITLE_H1_MISMATCH` — aggressiveness — **very conservative (fires only on total divergence)**

**What the code does.** `_titles_mismatch` (`registry.py:1613–1627`) strips a site-name suffix
(split on ` | `, ` - `, ` – `, ` — `, ` · `; `registry.py:1622`), reduces both sides to
significant words via `_sig_words` (non-stopword, len≥2; `registry.py:1606–1611`), and returns
`title_words.isdisjoint(h1_words)` — i.e. it fires **only when title and H1 share ZERO significant
words** (`registry.py:1627`). Too-short inputs return `False` (`:1625–1626`).

**Verdict.** This is **not aggressive — it is the opposite.** It fires only on genuine semantic
divergence and will **miss partial mismatches** (false negatives), never fire on surface
differences. So FP-driven arguments to lower impact don't apply; if anything the check *under*-fires.
Hermes 6 vs Claude 5 is a minor calibration call, not a detection-precision problem.
Confidence: **High [code]**.

### 10. `SEMANTIC_DENSITY_LOW` vs `AI_MAIN_CONTENT_LOW_RATIO` — separate computations — **confirmed distinct**

**What the code does.**
- `SEMANTIC_DENSITY_LOW`: fires when `page.text_to_html_ratio < 0.10` (`issue_checker.py:442–467`).
  This is **visible-text bytes ÷ total-HTML bytes** — inflated markup (Elementor/Divi/Gutenberg
  page-builders inject huge HTML) drives it down independent of content quality. It even
  self-diagnoses the biggest byte contributor (`issue_checker.py:449–466`).
- `AI_MAIN_CONTENT_LOW_RATIO`: fires when `page.main_content_ratio < _MAIN_CONTENT_LOW_RATIO`
  (`issue_checker.py:550–557`), where `main_content_ratio` = **`<main>/<article>` text ÷ `<body>`
  text** (`_main_content_ratio`, `parser.py:222–238`).

**Verdict.** Both exist and measure **different things** [code]: one is text-vs-markup byte density,
the other is main-region-vs-chrome text share. The Claude review's point stands —
`SEMANTIC_DENSITY_LOW` is a **page-builder false-positive magnet** (scored 5,3) while
`AI_MAIN_CONTENT_LOW_RATIO` (scored 2,1) is the more meaningful "content buried in chrome" signal.
Deprecating/deweighting `SEMANTIC_DENSITY_LOW` is defensible. Confidence: **High [code]**.

### 11. `CONTENT_STAT_OUTDATED` / `CONTENT_DATE_STALE_VISIBLE` / `CONTENT_STALE` — page-type awareness — **mixed (1 of 3 aware)**

**What the code does.**
- `CONTENT_DATE_STALE_VISIBLE`: **page-type aware** — `_PAGE_TYPE_CADENCE`
  (`api/crawler/checkers/ai_readiness.py:329–338`: article 12mo, service/about/home/contact/faq/
  unknown 24mo, `team_member` never) via `infer_page_type` (`ai_readiness.py:377–379`). Good.
- `CONTENT_STAT_OUTDATED` (`detect_outdated_stat`, `ai_readiness.py:404–461`): **NOT page-type
  aware** — flat "year ≥24mo old with no current-year mention"; has copyright/date-range guards
  but no evergreen-vs-timely distinction.
- `CONTENT_STALE` (`issue_checker.py:333–346`): **NOT page-type aware** — flat `Last-Modified`
  header `age_days > 365`, applies to every indexable page equally.

**Verdict.** Concern **partly real [code]**: the visible-date check is well-modelled; the other two
are flat thresholds that will nag evergreen pages (About/team/mission) and any page whose server
sends an old `Last-Modified`. Recommend extending `_PAGE_TYPE_CADENCE` awareness to `CONTENT_STALE`
(and ideally `CONTENT_STAT_OUTDATED`). Confidence: **High [code]**.

### 12. `AI_BOT_*` — user-agent table — **well-structured; one factual data bug + a parser-table divergence**

**What the code does.** The canonical table is `AI_BOTS` in `api/services/ai_bots.py`
(last reviewed 2026-05-03, annual cadence). It correctly separates categories:
- **search:** OAI-SearchBot, Claude-SearchBot, PerplexityBot, Applebot
- **training:** GPTBot, ClaudeBot, CCBot
- **user_fetch:** ChatGPT-User, Claude-User, Perplexity-User, Google-Agent, Google-NotebookLM
- **training_optout:** Google-Extended, Applebot-Extended
- **deprecated (`current:False`):** anthropic-ai, claude-web

`AI_BOT_SEARCH_BLOCKED` iterates `get_bots_by_category("search")`
(`ai_readiness.py:54,58–63`) — **fires on search bots, not training** ✓. Training blocks route to
`AI_BOT_TRAINING_DISALLOWED` (`:65–70`), which is correctly scored **impact 0** (blocking training
is a legitimate owner choice). `AI_BOT_DEPRECATED_DIRECTIVE` keys off `current:False`
(`_check_deprecated_directives`, `ai_readiness.py:172–179`) and the deprecated list (anthropic-ai,
claude-web) is current. ✓

**Data bug (factual, web-verified 2026-07-03).** `ai_bots.py` sets
`"Claude-User": {"honors_robots": False}` and `registry.py:982` says *"User-fetch bots
(ChatGPT-User, Claude-User) do not honor robots.txt."* **This is wrong.** Anthropic states **all
three** of its bots — ClaudeBot, Claude-User, Claude-SearchBot — honor robots.txt (Search Engine
Journal; Anthropic support docs, 2026). ChatGPT-User ("may not apply") and Perplexity-User
("agent, not a bot") are correctly `False`. Consequence: blocking a user-fetch agent **does** carry
a real visibility cost for the compliant vendor (Anthropic), so `AI_BOT_USER_FETCH_BLOCKED` should
**not** be floored on an "it does nothing" premise → **keep impact ~4** (Claude's position wins over
Hermes's drop-to-2). Fix `honors_robots` for Claude-User and the `registry.py:982` copy.
Confidence: **High [code + external]**.

**Second table divergence.** A **separate, smaller** bot set drives the per-page X-Robots-Tag parse:
`_AI_BOT_NAMES` in `parser.py:176–179` = `{gptbot, google-extended, claudebot, anthropic-ai, ccbot,
perplexitybot, bytespider, cohere-ai}`. It includes the **deprecated** `anthropic-ai`, and **omits**
Claude-User / ChatGPT-User / OAI-SearchBot / Claude-SearchBot. So `AI_PREVIEW_BLOCKED_AT_BOT`
(X-Robots per page) recognises a different, staler bot list than the robots.txt checker. Recommend
both consumers derive from the single `AI_BOTS` source. Confidence: **High [code]**.

---

## Cross-cutting findings beyond the prompt's checklist

**A. The entire JS-render trio is dead scored code.** `JS_RENDERED_CONTENT_DIFFERS` (6,4),
`CONTENT_CLOAKING_DETECTED` (8,4), `UA_CONTENT_DIFFERS` (7,3) are defined and scored in the
registry but **never emitted** — `run_js_render_checks` has no caller outside tests, and no
`make_issue` call exists for any of the three in `api/`. On any real crawl these three can never
fire. **Decision needed:** wire the service in (behind a Playwright-available guard) **or** mark
the codes deprecated. Until then, three of the highest AI-GEO impacts (incl. an 8) are inert.
(Phase 5 dead-code item.) Confidence: **High [code]**.

**B. `PAGE_TIMEOUT` is overloaded, not timeout-specific.** `engine.py:454` emits `PAGE_TIMEOUT`
for **any** fetch error with `status_code==0` — DNS failure, connection refused, read timeout,
even an SSRF block (`fetcher.py` returns `status_code=0` for SSRF). A blocked-internal or
dead-DNS URL is reported to the user as a "timeout." Combined with the no-retry finding (item 6),
this is a P1/labeling defect. Recommend distinguishing timeout from other status-0 errors.
Confidence: **High [code]**.

**C. `AI_BOT_TABLE_STALE` self-check exists** (`registry.py`, scored 0,1; `ai_bots.py` has
`LAST_REVIEWED=2026-05-03`, `REVIEW_CADENCE_DAYS=365`). Good hygiene — noted so Phase 4 doesn't
mistake its impact-0 for a bug.

---

## What I could NOT verify in Phase 1 (and why)

1. **Runtime stacking magnitude** — how much the item-5/item-4 stacks actually inflate page/site
   grades depends on the aggregation formula, which lives outside registry.py and is **Phase 2**.
   Not yet traced.
2. **`is_spa_shell` / `text_to_html_ratio` / `main_content_ratio` exact parse-time thresholds** —
   read the consumers (`issue_checker`, `ai_readiness`) but not every producer constant in
   `parser.py` (e.g. `_MAIN_CONTENT_LOW_RATIO` value at `parser.py:19`). Values to confirm in Phase 2/4.
3. **Whether `run_js_render_checks` is invoked by a background job / router I haven't grepped by a
   different name** — searched `run_js_render_checks` and all three `make_issue` codes repo-wide;
   found none in `api/`. High confidence it is unwired, but flagged as an assumption.
4. **Live vendor facts beyond the AI-bot honor-robots set** (llms.txt adoption, 302 PageRank,
   FAQ/HowTo rich-result status) — re-verification deferred to the Phase 3/4 items that actually
   depend on them; only the AI-bot compliance facts (item 12) were re-verified now because they
   changed a Phase-1 conclusion.

---

## Phase 2 — Stacking & aggregation analysis

### 2.0 The aggregation formula (traced)

Source: `api/services/job_store_base.py`.

- **Page Health = `max(0, 100 − Σ(impact of every issue on that page))`**
  (`_compute_v15_health_score`, `job_store_base.py:48–119`; per-page sum at SQL `:80–86`, floor at `:115`).
- **Site Health = mean of all crawled pages' Page Health** (pages with no issues = 100)
  (`job_store_base.py:118`).

> **CORRECTION (2026-07-03, found during R4):** the above describes the **SQLite (dev)** path only.
> **Redis (prod) does NOT use the impact model for the main health score.** `redis_store.get_summary`
> (`redis_store.py:240`) calls `_compute_health_score` — the **density model** (severity counts ×
> 50/30/10), which SQLite uses only as a *pre-v1.5 fallback*. So in **production the main health
> score has never used impact**; only `agent_health_score` uses impact in Redis (`redis_store.py:246-263`).
> Consequence: the entire impact-based calibration (R2 migration, R3 model, R4 suppression) affects
> the prod **main** score **not at all** until a store-parity fix lands. This is a High-severity
> divergence [code] that this Phase-2 section originally missed by assuming Redis mirrored SQLite.
- **Agent Health = identical model, restricted to agent-relevant issues** — categories
  `{ai_readiness, rendering, semantic_html}` ∪ codes `{PLACEHOLDER_LINK, WRONG_PLACEHOLDER_LINK}`
  (`_compute_agent_health_score`, `job_store_base.py:154–212`; filter `:134–151`).
- **Fallback:** a density model (`_density_health_score`, `job_store_base.py:32–45`) is used **only**
  for pre-v1.5 crawls where all impacts are 0 (`job_store_base.py:94–96`).
- **Effort is not in the health score at all.** `priority_rank = impact×10 − effort×2`
  (`registry.py:1738`) drives issue *ordering/UI*, not the score. `severity` (critical/warning/info)
  is **also not in the score** — it only drives sort order (`_SEVERITY_ORDER`, `job_store_base.py:28`)
  and the pre-v1.5 fallback.

**Four structural consequences (all High [code]):**

1. **Additive & uncapped per page.** Impacts sum with no per-category cap and no diminishing
   returns until the floor. N overlapping codes for one root cause subtract N×impact.
2. **The `max(0,…)` floor saturates marginal cost.** Once a page reaches ≥100 summed impact it
   scores 0, so *additional* issues are free. The marginal penalty of any issue depends on how
   many others already fired — stacking hurts *healthy* pages fully and *broken* pages not at all.
3. **Severity is decoupled from the score.** A `critical` code with impact 3 costs less than a
   `warning` with impact 7. The two axes were set independently (like fixability vs effort, §Phase 3),
   so the "critical" label and the score can point in opposite directions.
4. **Site = unweighted mean dilutes concentration.** 5 dead pages (score 0) among 95 clean pages
   → site 95. Adding clean/boilerplate pages *raises* site health. Concentrated, high-value-page
   problems are under-represented; homepage-only stacks (below) are the exception that bites.

### 2.1 Cluster-by-cluster inflation (LIVE vs DEAD verified)

A crucial discovery reshapes the prompt's cluster list: **several cluster members are dead or
misfiring code** (see §2.2). Real inflation is computed on the codes that can *actually* fire.

| Cluster | Members (impact) — LIVE unless marked | Real max stack | Root causes | Note |
|---|---|---|---|---|
| **Duplicate-metadata** | TITLE_DUPLICATE 5 + META_DESC_DUPLICATE 4 + TITLE_META_DUPLICATE_PAIR 6 | **−15** | 1 (two pages are dupes) | **Confirmed triple-fire** — `cross_page.py:74–111`: when both title & meta match, all three emit on each page. The PAIR code exists *because* both duplicated, yet the two components also fire. Cleanest triple-count. |
| **Schema (homepage)** | SCHEMA_MISSING 5 + JSON_LD_MISSING 7 + SCHEMA_ORG_MISSING 5 | **−17** | 1 (no structured data) | All fire on a homepage with no schema: `issue_checker.py:371`, `:470`, `metadata.py:40`. Inner pages: −12 (first two). `JSON_LD_INVALID` 4 is mutually exclusive (needs blocks present). |
| **Not-in-text** | AI_CONTENT_NOT_IN_TEXT 4 + CONTENT_NOT_EXTRACTABLE_NO_TEXT 6 + CONTACT_INFO_NOT_IN_HTML 4 + RAW_HTML_JS_DEPENDENT 6 | **−20** | 1–2 (content not in raw HTML) | Distinct checks, can co-fire on a JS/SPA homepage: `issue_checker.py:532`, `:588`, `metadata.py:46`, `ai_readiness.py:33`. Highest real stack. |
| **Thin-content** | THIN_CONTENT 6 + CONTENT_THIN 4 | **−10** | 1 (too few words) | Both fire on a <300-word page: `issue_checker.py:325` (word<300) + extractability `:588`. |
| **Answer-first** | FIRST_VIEWPORT_NO_ANSWER 5 + GEO_SUMMARY_BURIED 7 + ~~CENTRAL_CLAIM_BURIED 5 (DEAD)~~ | **−12** | 1 (answer not up top) | Only 2 of 3 can fire; `CENTRAL_CLAIM_BURIED` never emits (§2.2). GEO_SUMMARY_BURIED's 7 is the Cycle-GG translation artifact. |
| **Section-independence** | SECTION_VAGUE_OPENER 5 + SECTION_CROSS_REFERENCES 6 + ~~CHUNKS_NOT_SELF_CONTAINED 5 (DEAD)~~ | **−11** | 1 (sections not standalone) | Only 2 of 3 fire; `ai_readiness.py:94–105`. |
| **Broken-reference overlap** | BROKEN_LINK_404 10 / 5XX 7 vs ~~CITATIONS_SOURCES_INACCESSIBLE 4 (DEAD)~~ | **no overlap** | — | The citation half **can never fire** (`has_inaccessible_sources=False` hardcoded, `citation_model.py:97–98`). No real double-count. |
| **Cloaking pair** | ~~CONTENT_CLOAKING_DETECTED 8 (DEAD)~~ + ~~UA_CONTENT_DIFFERS 7 (DEAD)~~ | **0** | — | Both dead (JS-render service unwired, §Cross-cutting A). Zero real inflation today. |

**Worst realistic single page:** a JS-built nonprofit homepage with no structured data and thin
text could take **not-in-text −20 + schema −17 + thin −10 + answer-first −12 = −59** from perhaps
**3 root causes** (JS-rendered, no schema, thin), i.e. a 41/100 page that a human would call
"one underlying build problem." Plus the unconditional citation −3 (§2.2). This is the concrete
harm the owner should care about: the tool over-penalises a single fixable cause.

### 2.2 Dead & misfiring codes found while tracing (feeds Phase 5)

The repo has a self-aware `_DEAD_CODE_ALLOWLIST` (`tests/test_class1_invariants.py:300–326`), but
**its justifications are partly false** and it mixes "real, different code path" with "never fires":

**Genuinely DEAD — scored but no reachable emission (High [code]):**
- `JS_RENDERED_CONTENT_DIFFERS` (6,4), `CONTENT_CLOAKING_DETECTED` (8,4), `UA_CONTENT_DIFFERS` (7,3)
  — allowlist claims "emission happens when the engine consumes JSRenderResult"; **no such
  consumption exists** — `run_js_render_checks` has no non-test caller.
- `CENTRAL_CLAIM_BURIED` (5,3), `CHUNKS_NOT_SELF_CONTAINED` (5,4), `PROMOTIONAL_CONTENT_INTERRUPTS`
  (3,3) — "v3.0-planned LLM-driven"; no static emission. Honest dead, but scored & surfaced in help.
- `CITATIONS_ORPHANED` (2,1) — needs `c.context is None` over the citations list, but the list is
  **hardcoded empty** (`issue_checker.py:600`), so `any(...)` over `[]` is always False.
- `CITATIONS_SOURCES_INACCESSIBLE` (4,3) — `has_inaccessible_sources=False` hardcoded with a TODO
  (`citation_model.py:97–98`).

**MISFIRING — fires unconditionally regardless of the page (High [code]):**
- `CITATIONS_MISSING_SUBSTANTIAL_CONTENT` (3) — because `PageCitations` is built with
  `citations=[]`, `attribution_style="none"` (`issue_checker.py:598–602`), `lacks_citations` is
  **always True** for any page >200 words (`citation_model.py:88–92`). So this −3 lands on
  essentially every content page and measures nothing about real citations. This is a P7 (proxy
  that scores the wrong thing) *and* a P6 (status not reconciled to a real artifact).

**Net:** ~8 dead scored codes (including an impact-8 and two impact-7s) and 1 blanket-misfiring
code. Deleting/deprecating the dead ones removes phantom "feature surface"; fixing the citation
stub removes a site-wide −3 bias. Both materially change scores.

### 2.3 Proposed suppression / precedence rules (behavioural changes stated)

Design principle that fits the additive model: **one root cause → one graded charge.** Options,
in the order I recommend implementing them:

1. **Parent-suppresses-child (schema).** If `SCHEMA_MISSING` fires, suppress `JSON_LD_MISSING` and
   `SCHEMA_ORG_MISSING` (make SCHEMA_MISSING the graded parent, or — better — **deprecate
   `SCHEMA_MISSING`** and keep the two specific children, which carry better guidance).
   *Behaviour change:* homepage "no schema" drops from −17 to −7 (JSON_LD) or −12 (JSON_LD + ORG),
   not −17. Recommend: deprecate SCHEMA_MISSING, keep JSON_LD_MISSING (page-level) + SCHEMA_ORG_MISSING
   (homepage identity) — they are genuinely different concerns.
2. **Merge duplicate-metadata into one graded code.** When `TITLE_META_DUPLICATE_PAIR` fires,
   suppress `TITLE_DUPLICATE` + `META_DESC_DUPLICATE` on that page. *Behaviour change:* dupe pages
   go from −15 to −6.
3. **Merge/precede the not-in-text cluster.** Introduce precedence: `RAW_HTML_JS_DEPENDENT` (whole
   page is JS shell) suppresses the narrower `AI_CONTENT_NOT_IN_TEXT` / `CONTENT_NOT_EXTRACTABLE_NO_TEXT`
   / `CONTACT_INFO_NOT_IN_HTML` (which are symptoms of the same shell). *Behaviour change:* SPA
   homepage from −20 to −6.
4. **Thin-content: pick one.** THIN_CONTENT (core) and CONTENT_THIN (extractability) are the same
   finding; keep THIN_CONTENT, drop CONTENT_THIN from the extractability code set (or suppress when
   THIN_CONTENT present). *Behaviour change:* −10 → −6.
5. **Image performance (from Phase 1 item 5).** OVERSIZED/OVERSCALED suppress SLOW_LOAD +
   POOR_COMPRESSION as downstream consequences, or merge into one graded `IMG_PERFORMANCE`.
   *Behaviour change:* worst image −17 → one graded charge.
6. **Add a per-category page cap** as a backstop even after precedence — e.g. cap any single
   category's contribution to one page at ~20, so no cluster the audit missed can dominate.
   *Behaviour change:* bounds the tail; healthy pages with one bad category can't be zeroed by
   correlated codes.

Suppression should happen at aggregation time (where the score is computed), keeping every issue
*visible* in the UI list (so the user still sees all findings) but charged once — this preserves the
GUI/navigation contract in CLAUDE.md while fixing the score inflation.

---

## Phase 3 — Scoring model design

### 3.1 The binding constraint neither prior review could see

**Only 62 of 151 codes carry a confidence label; 89 (59%) have none** (measured:
`_AI_READINESS_CONFIDENCE` is `ai_readiness`-only; the metadata/heading/link/security/URL/image/
crawl codes have no tier). **Both** proposed schemes — Hermes's confidence-cap and Claude's
confidence×effect_size — assume every code has a confidence tier. So the *prerequisite work is
identical either way*: assign a confidence tier to all 151 codes. Given that cost is unavoidable,
the model choice should be made on which is better *per unit of that same work*. Confidence: **High [code]**.

### 3.2 Recommendation: adopt Claude's two-axis model, implemented as a *derivation* (not hand-set impact)

**Decision: two axes — `confidence` × `effect_size` — with a documented "measured single-study"
exception lane.** Reasoning (I am adjudicating, per the owner's mandate):

- Hermes's single cap (Heuristic ≤3, Reasonable ≤6, Established ≤9) is a sound *guardrail* but
  **collapses two independent things** — "how sure are we the effect is real" and "how big is it
  when real." The Aggarwal GEO checks (`STATISTICS_COUNT_LOW`, `EXTERNAL_CITATIONS_LOW`) are the
  proof: single-study evidence (low confidence) but a *measured, large* effect. Flooring them to 3
  alongside pure guesses like `CONVERSATIONAL_H2_MISSING` destroys information. (part0 §3 argued this;
  I concur and the code confirms both are currently impact 7.)
- Claude's two-axis model keeps that information and maps cleanly onto fields that should exist
  anyway. **Better output for the same prerequisite cost.**

**Implementation sketch:**
1. Add `effect_size ∈ {minor=1, moderate=2, major=3}` to every `_IssueSpec`; extend
   `confidence_label ∈ {Heuristic=1, Reasonable proxy=2, Established=3}` to all 151.
2. Derive impact from a documented 3×3 matrix instead of hand-setting it:

   | | effect minor | effect moderate | effect major |
   |---|---|---|---|
   | **Heuristic** | 1 | 2 | 3 (→ 5 w/ exception) |
   | **Reasonable proxy** | 3 | 5 | 6 (→ 7 w/ exception) |
   | **Established** | 5 | 7 | 9–10 |

3. **Exception lane:** a per-code boolean `measured_effect=True` lets a low-confidence code with a
   *published controlled study* use the parenthetical higher band (the Aggarwal GEO checks). Every
   use of the lane must cite the study in the spec — no unaudited promotions.
4. **impact 0 stays reserved** for legitimate-choice / informational codes
   (`AI_BOT_TRAINING_DISALLOWED`, `AI_CITED_PAGE`, `AI_BOT_TABLE_STALE`) — they bypass the matrix.
5. Keep Hermes's caps as an **assertion test**, not the mechanism: `impact ≤ cap(confidence)` unless
   `measured_effect`. This catches future drift automatically.

This turns impact from 151 hand-tuned numbers into `f(confidence, effect_size, measured_effect)` —
auditable, testable, and hard to re-corrupt. Confidence: **Medium** (design; the matrix constants
are a starting point to calibrate in Phase 4).

### 3.3 The priority_rank / effort quirk — real but minor; keep and document

`priority_rank = impact×10 − effort×2` (`registry.py:1738`). Lowering effort **raises**
priority_rank, so "easier than we thought" promotes an item. Quantified: effort ∈ 1–4 ⇒ the effort
term spans only **6 points** (−2…−8), while the impact term spans **90** (10…100). So effort is a
weak tiebreaker, not a driver — the "easier promotes" effect is real but small, and it is arguably
*desirable* (quick-wins-first ordering among similar-impact items). **Recommendation: keep the
formula, document the intent as "quick-wins tiebreaker," and make effort *derived* (§3.4) so the
tiebreaker is at least consistent.** If the owner ever wants strict impact/severity ordering, drop
effort from priority_rank and surface it as a separate "quick win" badge instead. Confidence: **High [code]**.

### 3.4 Reconcile `fixability` vs `effort` — keep them independent; effort is a scope rubric

> **Correction (made while building the Phase 4 table):** my first instinct — *derive effort from
> fixability* — is **wrong**, and generating the table proved it. Basing effort on fixability
> inflated ~60 trivial `developer_needed` one-liners (e.g. `LANG_MISSING`, `REDIRECT_TRAILING_SLASH`,
> `AI_PREVIEW_SUPPRESSED`) to effort 3-4. That re-creates the very fixability↔effort conflation the
> audit is meant to remove — just inverted. **Access (who fixes it) and size (how much work) are
> genuinely orthogonal:** robots.txt is `developer_needed` *and* effort 1.

Distribution (measured): `content_edit` 66, `developer_needed` 64, `wp_fixable` 21 (all 151 have a
fixability). **Correct reconciliation: keep both fields, define each independently, and fix only the
genuine mis-set efforts.** Effort follows a **scope/work-size rubric**:

```
effort 1 = single element / one-line edit      effort 3 = template / multi-page change
effort 2 = single-page content edit            effort 4 = server/infra or site-wide re-architecture
```

Fixability stays a separate "who/what access" field. The part0 "~67 contradictions" are mostly cases
where *effort* was mis-set relative to real work — not evidence the two fields should be merged.

**Effort changes are therefore few and targeted** (full list in the Phase 4 table). The genuine
miscalibrations:
- `URL_TOO_LONG`, `URL_HAS_UNDERSCORES`, `URL_HAS_SPACES`: effort **→ 2** (single-page slug edit; was 3-4).
- `THIN_CONTENT` (**4**→3), `CONTENT_STALE` (**4**→3): moderate content work, not the max.
- `ORPHAN_PAGE` (**4**→2): add internal links = single-page content (with fixability fix, §3.5).
- `CANONICAL_EXTERNAL` (2→**3**): template/server canonical change (Hermes was right; part0 conceded).
- `BROKEN_LINK_5XX` (3→**2**): remove/replace the link = content (with fixability fix, §3.5).

### 3.5 The two named fixability corrections

- **`ORPHAN_PAGE`** — currently `developer_needed`, effort 4 (`registry.py`). **Wrong on both.**
  Adding internal links pointing at the page is content work. → **`content_edit`, effort 2**
  (single-page scope). Both reviews agree; the code's own field was the error.
- **`BROKEN_LINK_5XX`** — currently `wp_fixable`, effort 3. **Wrong.** A 5xx lives on the
  *destination* server; nothing in WordPress can "fix" it. The author's real action is to
  remove/replace the offending link (content), or wait/retry if transient (Phase 1 item 6).
  → **`content_edit`, effort 2**, and mark **retryable** so a transient 5xx isn't a permanent negative.

### 3.6 Phase 3 caveats / what I could not verify

- The 3×3 matrix constants (§3.2) are a *proposed* calibration, not derived from the code — they
  need a pass over all 151 codes in Phase 4 to avoid mass score churn. **Medium.**
- The scope_modifier (§3.4) requires a per-code "site-wide vs single-page" judgment that isn't a
  field today; Phase 4 assigns it. Until then, effort deltas for structural codes are provisional.
- I did not re-verify the non-AI-bot vendor facts (302 PageRank, FAQ/HowTo rich results, llms.txt
  lift) live yet — those attach to specific Phase 4 rows and I'll re-verify them there.
