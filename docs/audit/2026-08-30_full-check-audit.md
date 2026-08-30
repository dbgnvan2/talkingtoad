# Complete audit of all 170 issue codes

**Started:** 2026-08-30 · **Scope:** every code in `_CATALOGUE`, no sampling.
**Method:** for each code — (1) read the detection predicate, (2) identify the
oracle (published standard / sibling implementation / real artifact), (3) verify
against real crawl data where the code fired, (4) assign a verdict.

**Verdicts:** `OK` · `FALSE-POSITIVE` · `OVERSTATED` (fires correctly, claim too
strong) · `DEAD` (cannot fire) · `UNVERIFIED` (with the reason).

Real-data reference: job `a87e2d61` — livingsystems.ca, 256 pages, all analyses,
68 of 170 codes fired.

---

## Findings

### F1 — `AI_BOT_TABLE_STALE` is DEAD: catalogued, documented, never emitted

`validate_table_freshness()` (`api/services/ai_bots.py:215`) has **zero callers**
anywhere in the codebase. No `make_issue("AI_BOT_TABLE_STALE", ...)` exists. The
code has a `_CATALOGUE` entry, an `issueHelp.js` entry, a row in
`docs/issue-codes.md`, and a spec line in
`docs/specs/ai-readiness/v2-extended-module.md` describing it as a shipped
site-level check. It has fired **0 times across every crawl in the database.**

The safeguard it represents is real: the AI-bot table lists GPTBot, ClaudeBot,
PerplexityBot and friends, and that roster changes constantly. The warning that
it has gone stale cannot ever appear.

**Verdict: DEAD (P21).** Fix: call `validate_table_freshness()` on the
site-level AI-readiness path and emit the code, with a test that fails if the
call is removed.

### F2 — the AI-bot table's own review deadline contradicts itself

Same file, four lines apart:

```python
"""... The table requires review every 6 months to stay current ..."""   # line 5
# Last reviewed: May 3, 2026
# Next review due: November 3, 2026                                       # 6 months
LAST_REVIEWED = datetime(2026, 5, 3)
REVIEW_CADENCE_DAYS = 365  # Must review annually                         # 12 months
```

The docstring and the comment promise a 6-month cadence (due 2026-11-03); the
enforced constant is 365 days (due 2027-05-03). Whoever reads the comment
believes the table is checked twice as often as it is — and per F1, it is not
checked at all. **Verdict: OVERSTATED / config bug.** Fix alongside F1; the
cadence belongs in config (rule 8), not split across a comment and a constant.

### F3 — `CONTENT_IMAGE_HEAVY` is mathematically unreachable

`extractability.diagnose_extractability` returns this code only when the page is
**not extractable** (`score > 50` is False, so deductions ≥ 50) *and* the three
higher-priority issues are absent. Excluding those three, the only deductions
available are `image_heavy` (−10), `no_structured_data` (−5) and
`unstructured_markup` (−5): **20 maximum, score 80, always extractable.**

Proven, not argued: an exhaustive sweep of **900 input combinations** across
word count, heading count, image count, JSON-LD and text ratio returned it
**0 times**. It has fired 0 times in 156 jobs.

`CONTENT_UNSTRUCTURED` sits one rung above it (−55) and **is** reachable —
confirmed by the same sweep — it simply has not occurred on this site.

**Verdict: DEAD.** Either raise the `image_heavy` deduction so the branch can be
reached, or delete the code and its catalogue/help/doc entries. It must not stay
as a documented capability that cannot fire.

### F4 — `HIGH_CRAWL_DEPTH` is dead on every site that has a sitemap

On the 256-page crawl, **255 of 256 pages have `crawl_depth = NULL`**; only the
homepage has a depth. The check is `if page.crawl_depth is not None and
page.crawl_depth > 4` (`issue_checker.py:455`), so it cannot fire. **0 hits in
156 jobs.**

Cause: sitemap URLs are seeded into the frontier with depth `None`
(`engine.py` §3, `depth_map[norm] = None`). Later, when the same URL is
discovered through a real link, the depth is not corrected:

```python
# Only update depth_map if we haven't seen this URL yet
# (first discovery via HTML gives the shallowest depth)
if norm not in depth_map:
    depth_map[norm] = child_depth
```

The comment's premise — that first discovery is via HTML — is false whenever a
sitemap exists, because seeding runs first and claims every URL. On a WordPress
site (this product's entire market) the sitemap lists everything, so depth is
never computed for anything.

This is not a false positive; it is a **silently disabled check**, and nothing
tells the user that click-depth was never measured. Same family as the
ORPHAN_PAGE defect: the sitemap narrows what is knowable and a check degrades to
permanent silence without disclosure.

**Verdict: DEAD (undisclosed).** Fix: let link discovery overwrite a `None`
depth (`if depth_map.get(norm) is None:`), and disclose when depth is unknown
for a page rather than silently skipping it.

### F5 — `IMG_NO_SRCSET` and `IMG_OVERSCALED` cannot fire: intrinsic width is never collected

Both gate on `img.width`:

```python
if not img.has_srcset:
    if img.width and img.rendered_width and img.width > img.rendered_width:
```

`width` is **NULL for all 79 images** on the latest crawl, and for **1,950 of
2,154 images (90.5%)** across the whole database. Both codes have fired **0
times in 156 jobs** — as have `IMG_DUPLICATE_CONTENT` and `IMG_SLOW_LOAD`.

Meanwhile **22 of 79 images on the latest crawl genuinely have no srcset**, so
there was something real to report and the check could not see it.

**Verdict: DEAD (data dependency never satisfied).** Fix: either collect
intrinsic dimensions (read them from the image header during the existing fetch)
or gate the codes off and declare them unavailable — but not silently.

### F6 — "not measured" is rendered to the user as a technical score of 0

`_calculate_scores` sets `tech = 0` when dimensions are missing, with the comment
`# No data = no score`. The **overall** score handles this correctly — it drops
the technical weight and renormalises, which is honest. But the raw `0` is
persisted and displayed: `ImageAnalysisPanel.jsx:997` renders
`<ScoreBar label="Technical" score={image.technical_score} />`.

On the latest crawl **all 79 images store `technical_score = 0.0`**, so every
image shows an empty Technical bar. The user reads "technically terrible"; the
truth is "never measured".

Third instance this week of the same root confusion — absence rendered as a
failing result (P31/P32). Note the panel's own test fixture uses
`technical_score: 85` and `55`, values that do not occur in production.

**Verdict: FALSE-POSITIVE (display).** Fix: render "not measured" when
`has_tech_data` is false; persist `None`, not `0`.

### F7 — verified CORRECT (checked against real artifacts, no defect)

| Code | Evidence |
|---|---|
| `LANDMARK_MAIN_MISSING` | 111 hits. Verified `/differentiation-the-key-to-better-relationships`: 0 `<main>`, 0 `role="main"`. Correct. |
| `LANDMARK_NAV_MISSING` | 0 hits. Verified the same pages carry 6 `<nav>` elements. Correctly silent. |
| `SOCIAL_PREVIEW_METADATA_MISSING` | 73 hits, all `og:image`. Verified missing on the named pages. Correct — and a false alarm from my own prevalence heuristic, which misread a URL in the title field. |
| `UNSAFE_CROSS_ORIGIN_LINK` | 156 hits from 4 template links. Detection factually correct (`target="_blank"`, no `rel`). Name overstates a risk browsers closed in 2021; severity `info`, impact `0`, so no score distortion. **OVERSTATED wording only.** |
| `IMG_ALT_MISSING` | Fixed this session — see the alt spec. 156 → 0. |
| `ORPHAN_PAGE` | Fixed in `cb421cf`. |
### F8 — `REDIRECT_TRAILING_SLASH`: the crawler causes the redirect it reports

**147 of 147** findings on the latest crawl differ **only** by a trailing slash.
Lifetime: **3,590** — the highest-volume code in the database.

The chain, verified end to end:

1. The site's canonical form carries a trailing slash. Its own sitemap:
   `<loc>https://livingsystems.ca/bowen_family_systems_blog/</loc>`. Its own
   internal links: `href="https://livingsystems.ca/about/"`. Every one slashed.
2. `normalise_url()` strips it (`normaliser.py:83-85`, "Strip trailing slash
   unless path is bare root").
3. The crawler fetches the **stripped** form.
4. WordPress 301-redirects back to the slashed form. Verified live:
   `/counselling` → **301** → `/counselling/`; `/counselling/` → **200**.
5. We report the redirect as a defect on the site.

No visitor and no search engine ever encounters this redirect: every link and
sitemap entry already uses the destination form. **We manufacture the request
that produces it.**

The check is structurally incapable of reporting a genuine problem. If a site
canonicalises *without* trailing slashes, our stripped request matches the
canonical form, returns 200, and the code never fires. It can therefore only
ever fire when the site is correctly configured the other way — i.e. it fires
exactly when there is nothing wrong.

Severity `info`, impact `(0, 1)` — no score distortion, but 147 rows per crawl
telling the owner to fix correct configuration.

**Verdict: FALSE-POSITIVE (self-inflicted).** Fix: suppress when the redirect
target differs from the fetched URL only by a trailing slash **and** the site's
own links/sitemap use the target form; or fetch the URL in the form the site
publishes and normalise only for identity/dedupe.

### F9 — correction: `INTERNAL_REDIRECT_301` is NOT the same artifact

I initially inferred from two samples (`redirect_to: /about/`,
`/contact_us/`) that this shared F8's root cause. Measuring all 8 findings
disproved it: **0 differ only by a trailing slash; all 8 are genuine slug
changes** —

```
/bowen-theory                      -> /about/
/contact                           -> /contact_us/
/religion-with-matt-steele         -> /politics-with-dr-davis/
/about/contact                     -> /contact_us/
```

Real redirects a visitor can hit, correctly flagged, impact `(2, 1)`.
**Verdict: OK.** Recorded because the near-miss is the point: the same eyeball
inference that produced this week's bugs nearly produced a false finding *about*
them. The measurement, not the reasoning, decided it.

### F10 — verified CORRECT against real artifacts

| Code | Hits | Evidence checked |
|---|---|---|
| `CONSENT_MODE_MISSING` | 156 | GA/GTM present (9 refs) and **zero** `gtag('consent'…)` in the live HTML. Correct. |
| `META_DESC_TOO_LONG` | 51 | Flagged descriptions verified visibly over the limit. Correct. |
| `ANCHOR_TEXT_GENERIC` | 78 | Evidence names `"Learn More"` and `"click here"`. Textbook. Correct. |
| `INTERNAL_REDIRECT_301` | 8 | All 8 genuine slug changes (F9). Correct. |
| `LANDMARK_MAIN_MISSING` | 111 | Flagged page has 0 `<main>`, 0 `role="main"`. Correct. |
| `SOCIAL_PREVIEW_METADATA_MISSING` | 73 | `og:image` genuinely absent. Correct. |

### Data-dependency sweep — columns never populated, and what depends on them

| Column | Populated | Consequence |
|---|---|---|
| `images.width` | 204 / 2,154 (9.5%); **0** on latest | F5 — `IMG_NO_SRCSET`, `IMG_OVERSCALED` dead; F6 — technical score shown as 0 |
| `crawled_pages.crawl_depth` | 178 / 14,788 (1.2%) | F4 — `HIGH_CRAWL_DEPTH` dead |
| `crawled_pages.amphtml_url` | 0 | `AMPHTML_BROKEN` silent — **legitimate**, site has no AMP |
| `crawled_pages.meta_refresh_url` | 0 | `META_REFRESH_REDIRECT` silent — extraction and persistence both verified present; genuinely absent on this site |
| `crawled_pages.ai_citation_*` | 0 | `AI_CITED_PAGE`, `AI_HIGH_VALUE_UNCITED` need an external citation feed not wired to this crawl |
| `images.geo_*`, `long_description` | ~0 | AI/GEO enrichment not run on these crawls |
| `crawled_pages.redirect_chain_json` | 0 | `REDIRECT_CHAIN` fires (183 lifetime) but the chain is never persisted — the **evidence** behind the finding is unavailable to the user. UNVERIFIED, low priority |
### F11 — `ENTITY_SAMEAS_MISSING` flags pages whose primary entity IS linked

74 findings on the latest crawl (365 lifetime), impact `(2, 1)` — it costs score.

Verified on `/differentiation-the-key-to-better-relationships`: the page's JSON-LD
**does** carry `sameAs`, on the `["Organization","Place"]` node, pointing at the
charity's Facebook, LinkedIn and Instagram profiles. Exactly what the code asks
for.

The detector (`cross_page.py:414-425`) flags when **any** matching node lacks
`sameAs`, rather than when **no** node has it:

```python
if _types_of(obj) & {"Organization","LocalBusiness","NGO","Corporation","Person"}:
    same = obj.get("sameAs")
    if not has:
        flagged = True          # ← any single node without sameAs flags the page
```

That page's graph has 20 nodes, two of which match: the `Organization` (has
`sameAs`) and a `Person` (does not). WordPress/Yoast emits that author `Person`
node automatically on every article, and an author node is not expected to carry
`sameAs`. So **every article page on any Yoast site is flagged regardless of how
completely the organisation is linked** — which is 74 of 256 here.

The finding's own text is "No sameAs Entity Links". The user reads that as "my
organisation is not linked to its social profiles" — the opposite of the truth.

Compounding it: **all 74 findings have an empty `extra`.** No evidence, no node
name, nothing to act on. There is no way for the reader to discover that the
flagged node is an auto-generated author stub.

**Verdict: FALSE-POSITIVE (score-affecting).** Fix: flag only when *no*
matching node carries `sameAs`, or scope the check to the primary
Organization/LocalBusiness entity; and attach the offending `@type` and `@id` as
evidence.

### F12 — the independent verifier's own error rate (stated, not hidden)

Two of my own leads were wrong, and both matter for how the verifier should be
read:

- **`THIN_CONTENT`** — my verifier counted 513/312/382 words where the crawler
  said 267/70/118. The crawler is right: `_count_words` strips nav/footer chrome
  (`_EXCLUDED_TAGS`); my regex counted the whole page. A 70-content-word bio page
  is genuinely thin. **Crawler correct.**
- **`STATISTICS_COUNT_LOW`** — my verifier found 112 `\d+%` tokens; every one was
  CSS (`width:100%`) in the raw HTML. Visible text contains **zero** percent
  tokens. **Crawler correct.**

Error rate: **5 false leads in 45 independent re-derivations (11%)**. The
verifier is a lead generator, exactly as the V4 spec insists the prevalence
triage must be labelled. Every disagreement was resolved by looking at the
artifact, never by trusting either implementation.

### F13 — codes CONFIRMED by independent re-derivation from raw HTML

Re-derived with an implementation sharing no code with the crawler, one real
flagged page each:

`HEADING_SKIP` (levels 1,1,2,4 — a real skip) · `H1_MULTIPLE` (2 h1s) ·
`MIXED_CONTENT` (1 http ref) · `CONVERSATIONAL_H2_MISSING` (0 question-form h2s) ·
`COMPARISON_TABLE_MISSING` (no `<table>`) · `IMG_FORMAT_LEGACY` ·
`PAGINATION_LINKS_PRESENT` · `SCHEMA_VISIBLE_MISMATCH` · `JSON_LD_INVALID` ·
`SCHEMA_TYPE_MISMATCH` · `LINK_EMPTY_ANCHOR` · `AI_CONTENT_NOT_IN_TEXT` ·
`BOILERPLATE_RATIO_HIGH` · `NEAR_DUPLICATE_BODY` · `LINK_STACKED_DUPLICATE` ·
`SEMANTIC_DENSITY_LOW` · `QUERY_COVERAGE_WEAK` · `FIRST_VIEWPORT_NO_ANSWER` ·
`GEO_SUMMARY_BURIED` · `SECTION_CROSS_REFERENCES`

Plus the earlier batch: `TITLE_TOO_LONG`, `TITLE_TOO_SHORT`, `META_DESC_MISSING`,
`META_DESC_TOO_LONG`, `H1_MISSING`, `URL_UPPERCASE`, `URL_HAS_UNDERSCORES`,
`SOCIAL_PREVIEW_METADATA_MISSING`, `THIN_CONTENT`, `CONSENT_MODE_MISSING`,
`ANCHOR_TEXT_GENERIC`, `INTERNAL_REDIRECT_301`, `LANDMARK_MAIN_MISSING`,
`LANDMARK_NAV_MISSING`, `STATISTICS_COUNT_LOW`.

**35 codes confirmed correct against real artifacts.**

---

## Coverage status — what this audit did and did not establish

Every one of the **170** codes was put through three whole-catalogue sweeps:

| Sweep | Method | Covers |
|---|---|---|
| Emission mapping | AST/regex for a `make_issue` call site per code | 170/170 |
| Firing history | lifetime + latest counts across 156 jobs, 14,788 pages | 170/170 |
| Data-dependency | every column of `crawled_pages` / `images` that is never populated, traced to the checks that gate on it | 170/170 |

On top of that, **35 codes were individually verified against real artifacts**
by re-deriving the finding with an independent implementation, and every code
showing a prevalence or reachability smell was investigated to a verdict.

**What is NOT established:** roughly 120 codes fired plausibly and were not
individually re-derived. They are recorded as `fired; NOT individually verified`
in the per-code table — not as "correct". Saying otherwise would repeat the
mistake this audit exists to correct.

### Results

| Verdict | Count | Codes |
|---|---|---|
| **DEAD** — cannot fire | 5 | `AI_BOT_TABLE_STALE`, `CONTENT_IMAGE_HEAVY`, `HIGH_CRAWL_DEPTH`, `IMG_NO_SRCSET`, `IMG_OVERSCALED` |
| **FALSE-POSITIVE** | 3 | `IMG_ALT_MISSING` *(fixed)*, `REDIRECT_TRAILING_SLASH`, `ENTITY_SAMEAS_MISSING` |
| **OVERSTATED** | 2 | `UNSAFE_CROSS_ORIGIN_LINK` (name), image `technical_score` shown as 0 |
| **SUSPECT** | 2 | `IMG_DUPLICATE_CONTENT`, `IMG_SLOW_LOAD` — 0 hits in 156 jobs, same dimension/timing dependency as F5 |
| **CONFIRMED correct** | 35 | see F13 |
| Not run (gated feature) | 12 | Playwright / PageSpeed / GSC-dependent |
| Not individually verified | ~111 | listed in the per-code table |

### The pattern behind the defects

Of the 8 defects, **6 share one root**: a fact the crawler could not obtain is
treated as a fact about the site.

- `HIGH_CRAWL_DEPTH` — depth never computed → silence, undisclosed
- `IMG_NO_SRCSET` / `IMG_OVERSCALED` — width never collected → silence
- image `technical_score` — dimensions missing → rendered as **0**, i.e. failure
- `IMG_ALT_MISSING` — correct decorative markup read as absence
- `ORPHAN_PAGE` (fixed) — unfetched page read as no inbound link

That is P31 and P32 in the same family: **absence of measurement presented as a
measurement.** The remaining two are different — `REDIRECT_TRAILING_SLASH` is
self-inflicted by our own normalisation, and `ENTITY_SAMEAS_MISSING` is an
any/all quantifier error.

### Recommended order

1. `ENTITY_SAMEAS_MISSING` — costs score, 74/256 pages, actively misleading text
2. `REDIRECT_TRAILING_SLASH` — 3,590 lifetime findings, all self-inflicted
3. `HIGH_CRAWL_DEPTH` — one-line fix (`if depth_map.get(norm) is None:`), restores a whole check
4. Image dimensions — unblocks `IMG_NO_SRCSET`, `IMG_OVERSCALED`, and the technical score
5. `AI_BOT_TABLE_STALE` — wire the existing function, or delete the code
6. `CONTENT_IMAGE_HEAVY` — reachable threshold, or delete
7. `UNSAFE_CROSS_ORIGIN_LINK` — rename during the V1 authority pass

Each needs its own micro-spec before implementation, per the repo workflow.
