---
status: draft-review + claude-overlay
proposed: 2026-07-02
authors: Hermes Agent (original) + Claude Opus 4.8 (overlay)
type: review
scope: broken links + redirects + crawlability + sitemap + duplicate (part 2 of 5)
---

# Scoring Weight Review — Part 2: Broken Links, Redirects, Crawlability, Sitemap, Duplicate
### (with Claude assessment blocks interleaved)

> Hermes's original text is unchanged. After each code, a block marked **◆ CLAUDE — Confidence: …** gives an independent second opinion.

---

## Broken Link Checks

### BROKEN_LINK_404 — (10, 2) → 96

**Assessment:** Impact 10 is correct. A 404 link is a dead end for users and search engines. It wastes crawl budget and hurts user trust. Effort 2 is right for nonprofits with WordPress (easy to update or redirect). Keep.

**Recommendation:** KEEP AS-IS (10, 2)

> **◆ CLAUDE — Confidence: High**
> Agree, (10, 2). One factual caveat: "wastes crawl budget" is a large-site concern — Google has said crawl budget isn't a practical issue for sites under ~10k URLs, which Living Systems is. The real cost here is broken navigation and lost link equity to the intended target, which fully justifies 10 regardless.

---

### BROKEN_LINK_410 — (8, 2) → 76

**Assessment:** Impact 8 is correct. A 410 is a deliberate "gone" signal. Slightly less harmful than a 404 because it's intentional, but still a broken user experience if the link should work. Keep.

**Recommendation:** KEEP AS-IS (8, 2)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (8, 2). Google processes 410 slightly faster than 404 for removal, but from a *linking page's* perspective a link to a 410 is just as broken. Correctly a notch below 404.

---

### BROKEN_LINK_5XX — (7, 3) → 64

**Assessment:** Impact 7 is correct. Server errors suggest infrastructure problems. Effort 3 is right — the fix might be on the destination site, not yours. Keep.

**Recommendation:** KEEP AS-IS (7, 3)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (7, 3), with a reliability caveat: 5xx is frequently transient (deploys, load, rate-limiting). Consider requiring a repeat observation before firing at full severity, or the check will produce flapping criticals. Score is fine; detection discipline matters more here.

---

### BROKEN_LINK_503 — (4, 3) → 34

**Assessment:** Impact 4 is reasonable. 503s are typically temporary (maintenance, rate-limiting). Less urgent than hard 404s. Keep.

**Recommendation:** KEEP AS-IS (4, 3)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (4, 3). 503 with Retry-After is explicitly "come back later"; treating it as low-urgency is correct.

---

### LINK_EMPTY_ANCHOR — (7, 2) → 66

**Assessment:** Impact 7 is reasonable but slightly high. An empty anchor means the link has no text — screen readers and search engines can't tell where it goes. For AI extraction, empty anchors waste link equity. However, many empty anchors are intentional (icon-only buttons with aria-labels). Impact 5-6 might be more accurate.

**Recommendation:** LOWER impact from 7 to 6. (6, 2) → 56

> **◆ CLAUDE — Confidence: Medium-High**
> Agree with lowering. Important detection point: an icon link with a valid `aria-label` or visually-hidden text is **not** an empty anchor — it has an accessible name. If the check keys on visible text only, it will false-positive heavily on icon nav/social buttons. Score 6 is fine *if* accessible-name is checked; if it isn't, drop to 4 to offset the noise.

---

### ANCHOR_TEXT_GENERIC — (4, 2) → 36

**Assessment:** Impact 4 is about right. "Click here" / "read more" links are poor anchor text but don't actively harm anything — they just pass less contextual link equity. For AI GEO, generic anchors are a missed signal for content relationships. Keep.

**Recommendation:** KEEP AS-IS (4, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (4, 2). "Read more" repeated across a blog loop grid is the classic pattern (and likely present on your JetEngine listing cards). It's a genuine a11y/extraction weakness but low-severity. 4 holds.

---

### EXTERNAL_LINK_SKIPPED — (2, 1) → 18

**Assessment:** Impact 2 is correct. This is an "informational" flag — the link couldn't be checked, not that it's broken. Low impact. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (2, 1). It's a coverage note, not a defect. Correct.

---

### EXTERNAL_LINK_TIMEOUT — (3, 1) → 28

**Assessment:** Impact 3 is slightly high. A timeout on an external link doesn't necessarily mean the link is broken — it could be a slow server or rate limiting. This is really an info-level check. Impact 2 is more honest.

**Recommendation:** LOWER impact from 3 to 2. (2, 1) → 18

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (2, 1). Many hosts throttle bot HEAD/GET requests, producing false timeouts. Low impact + retry logic is the right posture.

---

## Redirect Checks

### REDIRECT_LOOP — (10, 4) → 92

**Assessment:** Impact 10 is absolutely correct. A redirect loop means the page is unreachable — zero user or crawler access. Effort 4 is right (requires server config changes). Keep.

**Recommendation:** KEEP AS-IS (10, 4)

> **◆ CLAUDE — Confidence: High**
> Agree, (10, 4). Unreachable page = maximum impact. No change.

---

### REDIRECT_CHAIN — (6, 3) → 54

**Assessment:** Impact 6 is reasonable. Redirect chains waste crawl budget and slow page load. They're not blocking access but they degrade performance. Effort 3 is right — consolidating chains requires CMS maintenance. Keep.

**Recommendation:** KEEP AS-IS (6, 3)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (6, 3). Reframe the rationale: the real costs are latency (each hop is a round trip) and Google's ~10-hop follow limit, not crawl budget on a small site. Chains commonly appear post-migration (http→https→www→trailing-slash). Given you're mid-migration to SiteGround, this one is worth watching. Score holds.

---

### REDIRECT_301 — (3, 2) → 26

**Assessment:** Impact 3 is reasonable. A 301 is a permanent redirect — it passes most link equity. The main concern is that internal links should point directly to the final URL. Impact 3 is fine for this info-level check. Keep.

**Recommendation:** KEEP AS-IS (3, 2)

> **◆ CLAUDE — Confidence: High**
> Agree, (3, 2). Minor: 301 passes essentially full PageRank now (Google dropped the small "damping" years ago). A single external-facing 301 is fine; the only cleanup target is *internal* links that should point straight at the destination. Correct.

---

### REDIRECT_302 — (5, 2) → 46

**Assessment:** Impact 5 is reasonable. A 302 (temporary redirect) does NOT pass PageRank. If someone set up a 302 where a 301 is needed, it's losing link equity. Keep.

**Recommendation:** KEEP AS-IS (5, 2)

> **◆ CLAUDE — Confidence: High**
> **Disagree with the reasoning, and I'd lower the score.** The premise "a 302 does NOT pass PageRank" is an outdated myth. Google (Mueller, Illyes) has stated for years that **301 and 302 both pass PageRank**, and a 302 left in place long enough is treated like a 301 for canonicalization. The *actual* residual concern with a 302-where-301-was-intended is **canonicalization**: Google may keep the *old* URL as canonical because it reads the move as temporary, delaying consolidation onto the new URL. That's a real but modest issue. Recommend **(3, 2)** — or 4 if you weight the canonicalization delay heavily. Do not justify it via link-equity loss.

---

### REDIRECT_TRAILING_SLASH — (2, 1) → 18

**Assessment:** Impact 2 is correct. Minor — your server handles it automatically. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (2, 1).

---

### REDIRECT_CASE_NORMALISE — (2, 1) → 18

**Assessment:** Impact 2 is correct. Same as trailing slash — server handles it. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (2, 1).

---

### INTERNAL_REDIRECT_301 — (4, 1) → 38

**Assessment:** Impact 4 is reasonable. Internal pages that redirect via 301 mean internal links point to the wrong URLs. This wastes link equity and crawl budget. Keep.

**Recommendation:** KEEP AS-IS (4, 1)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (4, 1). This is the one 301 case worth flagging — internal links you control should hit the final URL directly. Effort 1 (edit the link) is right. Expect a spike of these right after the SiteGround cutover; treat as a post-migration cleanup pass.

---

### META_REFRESH_REDIRECT — (5, 2) → 46

**Assessment:** Impact 5 is about right. Meta refresh redirects are an old technique — they're slow (user sees a flash of the old page), don't pass link equity well, and Google treats them less favorably than server-side redirects. However, in 2024+ these are rare enough that the impact may be slightly high. Impact 4 could be justified.

**Recommendation:** KEEP impact 5, or LOWER to 4. (4, 2) → 36

> **◆ CLAUDE — Confidence: Medium**
> Agree with lowering to (4, 2). Add: instant meta-refresh is also a WCAG failure (2.2.1/3.2.5) because it can disorient users and defeat the back button. So the case for flagging is a11y as much as SEO. 4 is right.

---

## Crawlability Checks

### PAGE_TIMEOUT — (6, 3) → 54

**Assessment:** Impact 6 is reasonable. A page that times out cannot be crawled — it wastes the crawler's resources and leaves the page unindexed if persistent. This is a real technical problem. However, transient timeouts happen (server load, network issues). There may be false positives. Effort 3 is appropriate (server-side fix).

**Recommendation:** KEEP AS-IS (6, 3)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (6, 3), conditioned on retry logic. A single-observation timeout shouldn't produce a warning-level finding; require persistence. Score is fine.

---

### LOGIN_REDIRECT — (2, 1) → 18

**Assessment:** Impact 2 is correct. The page exists behind a login — the crawler can't audit it, but this is expected for member-only areas. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (2, 1). Expected behavior for gated content; informational.

---

### ROBOTS_BLOCKED — (9, 2) → 86

**Assessment:** Impact 9 is correct for SEO, but may be too high for a nonprofit context. A page blocked by robots.txt cannot be crawled or indexed at all — that's severe if unintended. However, many nonprofit sites intentionally block admin pages, and this check may catch those. Impact 9 is defensible.

**Note for AI GEO:** Blocking AI bots (GPTBot, ClaudeBot) via robots.txt is a separate concern (covered by AI_BOT_SEARCH_BLOCKED at 8). ROBOTS_BLOCKED is about general crawlers.

**Recommendation:** KEEP AS-IS (9, 2)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree with impact 9 *for unintended blocks*, but this code's value depends entirely on suppressing expected blocks (`/wp-admin/`, `/cart/`, `?s=` search, faceted params). If it fires on those, it generates false criticals. Correction to a common misconception (not Hermes's, but worth stating): robots.txt `Disallow` blocks *crawling*, not necessarily *indexing* — a disallowed URL with external links can still appear in results as a URL-only entry. For reliable exclusion you need `noindex` (see NOINDEX_META), not robots.txt. Score holds; gate it on intent.

---

### NOINDEX_META — (10, 1) → 98

**Assessment:** Impact 10 is correct. A `noindex` meta tag tells Google to exclude the page entirely from search results. If unintended, this is catastrophic for the page's visibility. Effort 1 is right (trivial removal in WordPress SEO plugin).

**Recommendation:** KEEP AS-IS (10, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (10, 1). The single highest-leverage silent killer, and the classic migration footgun (staging's site-wide noindex shipped to production). Given `daveg24.sg-host.com` is a staging host that *should* be noindexed, make sure the check distinguishes staging-intended noindex from production-accidental noindex at cutover. Score is correct.

---

### NOINDEX_HEADER — (10, 2) → 96

**Assessment:** Impact 10 is correct, same as meta noindex. Effort 2 is right — header-level noindex requires server config changes. Keep.

**Recommendation:** KEEP AS-IS (10, 2)

> **◆ CLAUDE — Confidence: High**
> Agree, (10, 2). `X-Robots-Tag` noindex is harder to spot than the meta tag (invisible in page source), so surfacing it is valuable. Correct.

---

### NOT_IN_SITEMAP — (4, 1) → 38

**Assessment:** Impact 4 is slightly high. Missing from sitemap means Google may still find the page via links, but it's less guaranteed. For a 500-page crawl, some pages being outside the sitemap is common and not critical. Impact 3 is more appropriate.

**Recommendation:** LOWER impact from 4 to 3. (3, 1) → 28

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 1). Sitemaps are a discovery aid, not a requirement; a well-linked page is found regardless. 3 is right.

---

### SITEMAP_MISSING — (6, 2) → 56

**Assessment:** Impact 6 is reasonable. No sitemap at all means Google must discover every page purely through links, which is slower and less reliable. This is an important baseline issue for any site. However, it's an info-level check (not warning or critical). Keep.

**Recommendation:** KEEP AS-IS (6, 2)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (6, 2), with a practical note: WordPress core ships an XML sitemap since 5.5, and Yoast/RankMath generate their own. A *truly* missing sitemap on WordPress usually means core sitemaps were disabled and no SEO plugin replaced them — worth surfacing precisely because it's unusual. 6 holds.

---

### PDF_TOO_LARGE — (4, 2) → 36

**Assessment:** Impact 4 is reasonable. Large PDFs are slow to download and may be skipped by crawlers or truncated. This directly affects whether the PDF content gets indexed. Keep.

**Recommendation:** KEEP AS-IS (4, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (4, 2). Relevant to you: conference handouts and Bowen Theory papers are often large scanned PDFs. Beyond size, watch for image-only (non-OCR'd) PDFs — those are invisible to both Google and AI extractors regardless of file size (see CONTENT_NOT_EXTRACTABLE, Part 4). Score fine.

---

### THIN_CONTENT — (6, 4) → 52

**Assessment:** Impact 6 is too high for the domain. Google's "thin content" penalty was historically a Panda algorithm concern, but modern Google handles thin pages gracefully — they just won't rank for competitive queries. They don't actively penalize the site. For nonprofits with mission-driven content, many legitimate pages are naturally short (team bios, event listings). Impact 4 is more appropriate. Effort 4 is also too high — expanding content is a content-edit task, not a "major dev work" effort.

**Recommendation:** LOWER impact from 6 to 4, LOWER effort from 4 to 2. (4, 2) → 36

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (4, 2). Panda has been part of the core algorithm since 2016, so there's no separate "thin content penalty" — thin pages simply under-perform. Two cautions: (1) exempt legitimately short page types (team bios, event stubs) or you'll flag your CPT archives; (2) for AI GEO specifically, thin pages are genuinely poor citation targets, so don't drop below 4. Well-calibrated at (4, 2).

---

### HIGH_CRAWL_DEPTH — (5, 3) → 44

**Assessment:** Impact 5 is too high. Pages 4+ clicks from the homepage may get less crawl attention and link equity, but for a nonprofit site with clear navigation, many deep pages are perfectly findable. Google crawls deep pages fine. Impact 3 is more appropriate. Effort 3 is also too high — improving internal linking is a content task, not developer work.

**Recommendation:** LOWER impact from 5 to 3, LOWER effort from 3 to 2. (3, 2) → 26

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 2). Click-depth is a weak, correlational signal (deep pages *tend* to be less important, but depth itself isn't a ranking factor). Fine at 3.

---

### ORPHAN_PAGE — (6, 4) → 52

**Assessment:** Impact 6 is reasonable but effort 4 is too high. An orphan page has no internal links — it's invisible to crawlers and users (unless they have the direct URL). This is a real discovery problem. However, fixing it requires adding one or two links from relevant pages — that's content work, not developer work. Effort 2 is more appropriate.

**Recommendation:** KEEP impact 6, LOWER effort from 4 to 2. (6, 2) → 56

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (6, 2). Detection caveat: a page can be "orphaned" in your crawl yet linked from a JetEngine listing/loop grid that renders via query — if your crawler doesn't execute those queries it will report false orphans (the same dynamic-rendering blind spot that hid your card `<h1>`s from a plain fetch). Validate orphans against rendered navigation before trusting the count. Score is right.

---

### PAGINATION_LINKS_PRESENT — (2, 2) → 16

**Assessment:** Impact 2 is correct. This is an observation, not a problem. Keep.

**Recommendation:** KEEP AS-IS (2, 2)

> **◆ CLAUDE — Confidence: High**
> Agree, (2, 2). Note `rel=next/prev` was dropped by Google as an indexing signal in 2019; pagination is now just normal internal linking. Observational only. Correct.

---

### AMPHTML_BROKEN — (4, 3) → 34

**Assessment:** Impact 4 is about right. Broken AMP means Google's preferred mobile version is unavailable — but AMP is declining in importance. For most nonprofits, AMP is no longer necessary. The impact of a broken AMP link specifically is low. Impact 3 could be argued.

**Recommendation:** KEEP impact 4, or LOWER to 3. (3, 3) → 24

> **◆ CLAUDE — Confidence: Medium-High**
> Agree with lowering; I'd go to (2, 3). Since Google's 2021 Page Experience update, AMP is no longer required for Top Stories and its SEO value has collapsed. For a WordPress+Elementor nonprofit, the right move is usually to *remove* AMP entirely, not maintain it — a broken AMP link is near-informational. Correct rationale ("AMP is declining"); push the number lower.

---

### PAGE_SIZE_LARGE — (5, 3) → 44

**Assessment:** Impact 5 is slightly high. Large pages (over 300KB) are slower to load, which affects Core Web Vitals and mobile performance. But for a 300KB threshold, many nonprofit pages with themes and plugins naturally exceed it. Impact 3-4 is more accurate for today's web. Effort 3 is right (theme optimization).

**Recommendation:** LOWER impact from 5 to 4. (4, 3) → 34

> **◆ CLAUDE — Confidence: Medium**
> Agree, (4, 3), but flag the threshold: 300KB total page weight is unrealistically strict for an Elementor site (the CSS/JS framework alone often exceeds it). This will fire on nearly every page and become noise. The more meaningful modern signals are Core Web Vitals (LCP/CLS/INP) and image payload, not raw HTML+asset bytes. Consider raising the threshold or replacing with a CWV-based check. Score fine; threshold is the problem.

---

### CONTENT_STALE — (3, 4) → 22

**Assessment:** Impact 3 is correct for traditional SEO. Google favors fresh content, but old content doesn't necessarily rank worse — evergreen content can perform well for years. However, effort 4 (major dev work) is completely wrong. Reviewing and refreshing content is a content-edit task, effort 1-2 at most.

**For AI GEO:** Stale content is arguably more impactful for AI citation than for Google search. AI engines bias toward recency for citations. But impact 3 is still reasonable.

**Recommendation:** KEEP impact 3, LOWER effort from 4 to 2. (3, 2) → 26

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 2). The AI-recency point is fair but should be applied by page *type*: a Bowen Theory concept page is evergreen and shouldn't be penalized for age, whereas an events/news page going stale is a real problem. If the check can read page type/category, weight staleness only where recency is expected. Score holds.

---

### SCHEMA_MISSING — (5, 2) → 46

**Assessment:** Impact 5 is reasonable for an info-level check. No structured data means the site gets fewer rich results. For AI GEO, schema is one of the most important signals for entity extraction. However, this check is superseded by the more specific JSON_LD_MISSING (impact 7). SCHEMA_MISSING may be duplicative with the newer, better check. Consider whether this code should be deprecated in favor of JSON_LD_MISSING.

**Recommendation:** KEEP AS-IS (5, 2), but note potential redundancy with JSON_LD_MISSING (covered in Part 4).

> **◆ CLAUDE — Confidence: Medium**
> Agree, and I'd escalate the redundancy flag. There appear to be **three** overlapping schema checks across the review: SCHEMA_MISSING (here), JSON_LD_MISSING (Part 4, impact 7), and SCHEMA_ORG_MISSING (Part 5, impact 5). On a page with no structured data, all three could fire and triple-count one condition, inflating aggregate priority. Recommend deprecating SCHEMA_MISSING in favor of JSON_LD_MISSING, and scoping SCHEMA_ORG_MISSING to homepage/identity only. See overview §2.

---

### MISSING_VIEWPORT_META — (6, 1) → 58

**Assessment:** Impact 6 is too high. A missing viewport meta tag makes the page render at desktop width on mobile — a poor user experience but not a ranking disaster. Google's mobile-first indexing means mobile usability matters, but impact 6 exceeds what this individual check deserves (especially since many WordPress themes include viewport meta automatically). Impact 4 is more appropriate.

**Recommendation:** LOWER impact from 6 to 4. (4, 1) → 38

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (4, 1). Under mobile-first indexing a non-responsive page is a genuine usability problem, so I wouldn't go below 4 — but any competent Elementor theme emits the viewport tag, so a real occurrence is rare and usually signals a broken header template. 4 is right.

---

### INTERNAL_NOFOLLOW — (5, 2) → 46

**Assessment:** Impact 5 is slightly high. `nofollow` on internal links prevents PageRank flow to those pages — Google may not discover or index them properly through those links. However, most sites with intentional `nofollow` on internal links are doing it for crawl budget management (login pages, tag pages, etc.). For a nonprofit, accidental internal nofollow is rare. Impact 3-4 is more appropriate.

**Recommendation:** LOWER impact from 5 to 3. (3, 2) → 26

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 2). Correction to the mechanism: since 2020 Google treats `nofollow` as a **hint**, not a directive, for both crawling and indexing — so internal nofollow is even less consequential than the "prevents PageRank flow" framing implies. 3 is right, arguably 2.

---

### PARA_TOO_LONG — (4, 2) → 36

**Assessment:** Impact 4 is too high. Long paragraphs (>150 words) are a readability concern, not an SEO concern. Google doesn't penalize long paragraphs. For AI GEO, long paragraphs may reduce chunk-level extractability, but this is a minor signal. Impact 2 is more appropriate for this info-level check.

**Recommendation:** LOWER impact from 4 to 2. (2, 2) → 16

> **◆ CLAUDE — Confidence: Medium**
> Agree, (2, 2). The AI-chunking angle is real but second-order. Note this overlaps with PARAS_TOO_LONG in Part 5 (same concept, different code) — dedupe. Score fine.

---

## Part 2 Summary — Claude deltas vs Hermes

| Code | Hermes proposed | Claude | Why |
|------|-----------------|--------|-----|
| REDIRECT_302 | keep (5, 2) | (3, 2) | "302 loses PageRank" is a myth; only canonicalization delay remains |
| AMPHTML_BROKEN | (3, 3) | (2, 3) | AMP lost Top Stories privilege in 2021; near-informational now |
| PAGE_SIZE_LARGE | (4, 3) | (4, 3) + fix threshold | 300KB is unrealistic for Elementor; prefer CWV-based check |
| INTERNAL_NOFOLLOW | (3, 2) | (3, 2) | Agree; note nofollow is a *hint* since 2020 |

All other Part 2 items: **agree with Hermes.** Detection cautions (not score changes) logged for LINK_EMPTY_ANCHOR (accessible-name), ORPHAN_PAGE (dynamic-render blind spot), ROBOTS_BLOCKED (crawl vs index), and 5xx/timeout (require persistence).
