---
status: draft-review
proposed: 2026-07-02
author: Hermes Agent
type: review
scope: broken links + redirects + crawlability + sitemap + duplicate (part 2 of 5)
---

# Scoring Weight Review — Part 2: Broken Links, Redirects, Crawlability, Sitemap, Duplicate

> Each entry shows current weight, assessment, and recommendation. Priority formula: `(impact × 10) − (effort × 2)`.

---

## Current Scoring Reference

| Code | Current (impact, effort) | Priority rank | Severity |
|------|--------------------------|---------------|----------|
| BROKEN_LINK_404 | (10, 2) | 96 | critical |
| BROKEN_LINK_410 | (8, 2) | 76 | critical |
| BROKEN_LINK_5XX | (7, 3) | 64 | critical |
| BROKEN_LINK_503 | (4, 3) | 34 | warning |
| LINK_EMPTY_ANCHOR | (7, 2) | 66 | warning |
| ANCHOR_TEXT_GENERIC | (4, 2) | 36 | warning |
| EXTERNAL_LINK_SKIPPED | (2, 1) | 18 | info |
| EXTERNAL_LINK_TIMEOUT | (3, 1) | 28 | info |
| REDIRECT_LOOP | (10, 4) | 92 | critical |
| REDIRECT_CHAIN | (6, 3) | 54 | warning |
| REDIRECT_301 | (3, 2) | 26 | info |
| REDIRECT_302 | (5, 2) | 46 | warning |
| REDIRECT_TRAILING_SLASH | (2, 1) | 18 | info |
| REDIRECT_CASE_NORMALISE | (2, 1) | 18 | info |
| INTERNAL_REDIRECT_301 | (4, 1) | 38 | info |
| META_REFRESH_REDIRECT | (5, 2) | 46 | warning |
| PAGE_TIMEOUT | (6, 3) | 54 | warning |
| LOGIN_REDIRECT | (2, 1) | 18 | info |
| ROBOTS_BLOCKED | (9, 2) | 86 | warning |
| NOINDEX_META | (10, 1) | 98 | warning |
| NOINDEX_HEADER | (10, 2) | 96 | warning |
| NOT_IN_SITEMAP | (4, 1) | 38 | info |
| SITEMAP_MISSING | (6, 2) | 56 | info |
| PDF_TOO_LARGE | (4, 2) | 36 | warning |
| THIN_CONTENT | (6, 4) | 52 | warning |
| HIGH_CRAWL_DEPTH | (5, 3) | 44 | warning |
| ORPHAN_PAGE | (6, 4) | 52 | warning |
| PAGINATION_LINKS_PRESENT | (2, 2) | 16 | info |
| AMPHTML_BROKEN | (4, 3) | 34 | warning |
| PAGE_SIZE_LARGE | (5, 3) | 44 | warning |
| CONTENT_STALE | (3, 4) | 22 | info |
| SCHEMA_MISSING | (5, 2) | 46 | info |
| MISSING_VIEWPORT_META | (6, 1) | 58 | warning |
| INTERNAL_NOFOLLOW | (5, 2) | 46 | warning |
| PARA_TOO_LONG | (4, 2) | 36 | info |

---

## Broken Link Checks

### BROKEN_LINK_404 — (10, 2) → 96

**Assessment:** Impact 10 is correct. A 404 link is a dead end for users and search engines. It wastes crawl budget and hurts user trust. Effort 2 is right for nonprofits with WordPress (easy to update or redirect). Keep.

**Recommendation:** KEEP AS-IS (10, 2)

---

### BROKEN_LINK_410 — (8, 2) → 76

**Assessment:** Impact 8 is correct. A 410 is a deliberate "gone" signal. Slightly less harmful than a 404 because it's intentional, but still a broken user experience if the link should work. Keep.

**Recommendation:** KEEP AS-IS (8, 2)

---

### BROKEN_LINK_5XX — (7, 3) → 64

**Assessment:** Impact 7 is correct. Server errors suggest infrastructure problems. Effort 3 is right — the fix might be on the destination site, not yours. Keep.

**Recommendation:** KEEP AS-IS (7, 3)

---

### BROKEN_LINK_503 — (4, 3) → 34

**Assessment:** Impact 4 is reasonable. 503s are typically temporary (maintenance, rate-limiting). Less urgent than hard 404s. Keep.

**Recommendation:** KEEP AS-IS (4, 3)

---

### LINK_EMPTY_ANCHOR — (7, 2) → 66

**Assessment:** Impact 7 is reasonable but slightly high. An empty anchor means the link has no text — screen readers and search engines can't tell where it goes. For AI extraction, empty anchors waste link equity. However, many empty anchors are intentional (icon-only buttons with aria-labels). Impact 5-6 might be more accurate.

**Recommendation:** LOWER impact from 7 to 6. (6, 2) → 56

---

### ANCHOR_TEXT_GENERIC — (4, 2) → 36

**Assessment:** Impact 4 is about right. "Click here" / "read more" links are poor anchor text but don't actively harm anything — they just pass less contextual link equity. For AI GEO, generic anchors are a missed signal for content relationships. Keep.

**Recommendation:** KEEP AS-IS (4, 2)

---

### EXTERNAL_LINK_SKIPPED — (2, 1) → 18

**Assessment:** Impact 2 is correct. This is an "informational" flag — the link couldn't be checked, not that it's broken. Low impact. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

---

### EXTERNAL_LINK_TIMEOUT — (3, 1) → 28

**Assessment:** Impact 3 is slightly high. A timeout on an external link doesn't necessarily mean the link is broken — it could be a slow server or rate limiting. This is really an info-level check. Impact 2 is more honest.

**Recommendation:** LOWER impact from 3 to 2. (2, 1) → 18

---

## Redirect Checks

### REDIRECT_LOOP — (10, 4) → 92

**Assessment:** Impact 10 is absolutely correct. A redirect loop means the page is unreachable — zero user or crawler access. Effort 4 is right (requires server config changes). Keep.

**Recommendation:** KEEP AS-IS (10, 4)

---

### REDIRECT_CHAIN — (6, 3) → 54

**Assessment:** Impact 6 is reasonable. Redirect chains waste crawl budget and slow page load. They're not blocking access but they degrade performance. Effort 3 is right — consolidating chains requires CMS maintenance. Keep.

**Recommendation:** KEEP AS-IS (6, 3)

---

### REDIRECT_301 — (3, 2) → 26

**Assessment:** Impact 3 is reasonable. A 301 is a permanent redirect — it passes most link equity. The main concern is that internal links should point directly to the final URL. Impact 3 is fine for this info-level check. Keep.

**Recommendation:** KEEP AS-IS (3, 2)

---

### REDIRECT_302 — (5, 2) → 46

**Assessment:** Impact 5 is reasonable. A 302 (temporary redirect) does NOT pass PageRank. If someone set up a 302 where a 301 is needed, it's losing link equity. Keep.

**Recommendation:** KEEP AS-IS (5, 2)

---

### REDIRECT_TRAILING_SLASH — (2, 1) → 18

**Assessment:** Impact 2 is correct. Minor — your server handles it automatically. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

---

### REDIRECT_CASE_NORMALISE — (2, 1) → 18

**Assessment:** Impact 2 is correct. Same as trailing slash — server handles it. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

---

### INTERNAL_REDIRECT_301 — (4, 1) → 38

**Assessment:** Impact 4 is reasonable. Internal pages that redirect via 301 mean internal links point to the wrong URLs. This wastes link equity and crawl budget. Keep.

**Recommendation:** KEEP AS-IS (4, 1)

---

### META_REFRESH_REDIRECT — (5, 2) → 46

**Assessment:** Impact 5 is about right. Meta refresh redirects are an old technique — they're slow (user sees a flash of the old page), don't pass link equity well, and Google treats them less favorably than server-side redirects. However, in 2024+ these are rare enough that the impact may be slightly high. Impact 4 could be justified.

**Recommendation:** KEEP impact 5, or LOWER to 4. (4, 2) → 36

---

## Crawlability Checks

### PAGE_TIMEOUT — (6, 3) → 54

**Assessment:** Impact 6 is reasonable. A page that times out cannot be crawled — it wastes the crawler's resources and leaves the page unindexed if persistent. This is a real technical problem. However, transient timeouts happen (server load, network issues). There may be false positives. Effort 3 is appropriate (server-side fix).

**Recommendation:** KEEP AS-IS (6, 3)

---

### LOGIN_REDIRECT — (2, 1) → 18

**Assessment:** Impact 2 is correct. The page exists behind a login — the crawler can't audit it, but this is expected for member-only areas. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

---

### ROBOTS_BLOCKED — (9, 2) → 86

**Assessment:** Impact 9 is correct for SEO, but may be too high for a nonprofit context. A page blocked by robots.txt cannot be crawled or indexed at all — that's severe if unintended. However, many nonprofit sites intentionally block admin pages, and this check may catch those. Impact 9 is defensible.

**Note for AI GEO:** Blocking AI bots (GPTBot, ClaudeBot) via robots.txt is a separate concern (covered by AI_BOT_SEARCH_BLOCKED at 8). ROBOTS_BLOCKED is about general crawlers.

**Recommendation:** KEEP AS-IS (9, 2)

---

### NOINDEX_META — (10, 1) → 98

**Assessment:** Impact 10 is correct. A `noindex` meta tag tells Google to exclude the page entirely from search results. If unintended, this is catastrophic for the page's visibility. Effort 1 is right (trivial removal in WordPress SEO plugin).

**Recommendation:** KEEP AS-IS (10, 1)

---

### NOINDEX_HEADER — (10, 2) → 96

**Assessment:** Impact 10 is correct, same as meta noindex. Effort 2 is right — header-level noindex requires server config changes. Keep.

**Recommendation:** KEEP AS-IS (10, 2)

---

### NOT_IN_SITEMAP — (4, 1) → 38

**Assessment:** Impact 4 is slightly high. Missing from sitemap means Google may still find the page via links, but it's less guaranteed. For a 500-page crawl, some pages being outside the sitemap is common and not critical. Impact 3 is more appropriate.

**Recommendation:** LOWER impact from 4 to 3. (3, 1) → 28

---

### SITEMAP_MISSING — (6, 2) → 56

**Assessment:** Impact 6 is reasonable. No sitemap at all means Google must discover every page purely through links, which is slower and less reliable. This is an important baseline issue for any site. However, it's an info-level check (not warning or critical). Keep.

**Recommendation:** KEEP AS-IS (6, 2)

---

### PDF_TOO_LARGE — (4, 2) → 36

**Assessment:** Impact 4 is reasonable. Large PDFs are slow to download and may be skipped by crawlers or truncated. This directly affects whether the PDF content gets indexed. Keep.

**Recommendation:** KEEP AS-IS (4, 2)

---

### THIN_CONTENT — (6, 4) → 52

**Assessment:** Impact 6 is too high for the domain. Google's "thin content" penalty was historically a Panda algorithm concern, but modern Google handles thin pages gracefully — they just won't rank for competitive queries. They don't actively penalize the site. For nonprofits with mission-driven content, many legitimate pages are naturally short (team bios, event listings). Impact 4 is more appropriate. Effort 4 is also too high — expanding content is a content-edit task, not a "major dev work" effort.

**Recommendation:** LOWER impact from 6 to 4, LOWER effort from 4 to 2. (4, 2) → 36

---

### HIGH_CRAWL_DEPTH — (5, 3) → 44

**Assessment:** Impact 5 is too high. Pages 4+ clicks from the homepage may get less crawl attention and link equity, but for a nonprofit site with clear navigation, many deep pages are perfectly findable. Google crawls deep pages fine. Impact 3 is more appropriate. Effort 3 is also too high — improving internal linking is a content task, not developer work.

**Recommendation:** LOWER impact from 5 to 3, LOWER effort from 3 to 2. (3, 2) → 26

---

### ORPHAN_PAGE — (6, 4) → 52

**Assessment:** Impact 6 is reasonable but effort 4 is too high. An orphan page has no internal links — it's invisible to crawlers and users (unless they have the direct URL). This is a real discovery problem. However, fixing it requires adding one or two links from relevant pages — that's content work, not developer work. Effort 2 is more appropriate.

**Recommendation:** KEEP impact 6, LOWER effort from 4 to 2. (6, 2) → 56

---

### PAGINATION_LINKS_PRESENT — (2, 2) → 16

**Assessment:** Impact 2 is correct. This is an observation, not a problem. Keep.

**Recommendation:** KEEP AS-IS (2, 2)

---

### AMPHTML_BROKEN — (4, 3) → 34

**Assessment:** Impact 4 is about right. Broken AMP means Google's preferred mobile version is unavailable — but AMP is declining in importance. For most nonprofits, AMP is no longer necessary. The impact of a broken AMP link specifically is low. Impact 3 could be argued.

**Recommendation:** KEEP impact 4, or LOWER to 3. (3, 3) → 24

---

### PAGE_SIZE_LARGE — (5, 3) → 44

**Assessment:** Impact 5 is slightly high. Large pages (over 300KB) are slower to load, which affects Core Web Vitals and mobile performance. But for a 300KB threshold, many nonprofit pages with themes and plugins naturally exceed it. Impact 3-4 is more accurate for today's web. Effort 3 is right (theme optimization).

**Recommendation:** LOWER impact from 5 to 4. (4, 3) → 34

---

### CONTENT_STALE — (3, 4) → 22

**Assessment:** Impact 3 is correct for traditional SEO. Google favors fresh content, but old content doesn't necessarily rank worse — evergreen content can perform well for years. However, effort 4 (major dev work) is completely wrong. Reviewing and refreshing content is a content-edit task, effort 1-2 at most.

**For AI GEO:** Stale content is arguably more impactful for AI citation than for Google search. AI engines bias toward recency for citations. But impact 3 is still reasonable.

**Recommendation:** KEEP impact 3, LOWER effort from 4 to 2. (3, 2) → 26

---

### SCHEMA_MISSING — (5, 2) → 46

**Assessment:** Impact 5 is reasonable for an info-level check. No structured data means the site gets fewer rich results. For AI GEO, schema is one of the most important signals for entity extraction. However, this check is superseded by the more specific JSON_LD_MISSING (impact 7). SCHEMA_MISSING may be duplicative with the newer, better check. Consider whether this code should be deprecated in favor of JSON_LD_MISSING.

**Recommendation:** KEEP AS-IS (5, 2), but note potential redundancy with JSON_LD_MISSING (covered in Part 4).

---

### MISSING_VIEWPORT_META — (6, 1) → 58

**Assessment:** Impact 6 is too high. A missing viewport meta tag makes the page render at desktop width on mobile — a poor user experience but not a ranking disaster. Google's mobile-first indexing means mobile usability matters, but impact 6 exceeds what this individual check deserves (especially since many WordPress themes include viewport meta automatically). Impact 4 is more appropriate.

**Recommendation:** LOWER impact from 6 to 4. (4, 1) → 38

---

### INTERNAL_NOFOLLOW — (5, 2) → 46

**Assessment:** Impact 5 is slightly high. `nofollow` on internal links prevents PageRank flow to those pages — Google may not discover or index them properly through those links. However, most sites with intentional `nofollow` on internal links are doing it for crawl budget management (login pages, tag pages, etc.). For a nonprofit, accidental internal nofollow is rare. Impact 3-4 is more appropriate.

**Recommendation:** LOWER impact from 5 to 3. (3, 2) → 26

---

### PARA_TOO_LONG — (4, 2) → 36

**Assessment:** Impact 4 is too high. Long paragraphs (>150 words) are a readability concern, not an SEO concern. Google doesn't penalize long paragraphs. For AI GEO, long paragraphs may reduce chunk-level extractability, but this is a minor signal. Impact 2 is more appropriate for this info-level check.

**Recommendation:** LOWER impact from 4 to 2. (2, 2) → 16

---

## Part 2 Summary

| Code | Current | Proposed | Delta |
|------|---------|----------|-------|
| LINK_EMPTY_ANCHOR | (7, 2) | (6, 2) | -1 impact |
| EXTERNAL_LINK_TIMEOUT | (3, 1) | (2, 1) | -1 impact |
| META_REFRESH_REDIRECT | (5, 2) | (4, 2) | -1 impact |
| NOT_IN_SITEMAP | (4, 1) | (3, 1) | -1 impact |
| THIN_CONTENT | (6, 4) | (4, 2) | -2 impact, -2 effort |
| HIGH_CRAWL_DEPTH | (5, 3) | (3, 2) | -2 impact, -1 effort |
| ORPHAN_PAGE | (6, 4) | (6, 2) | -2 effort |
| AMPHTML_BROKEN | (4, 3) | (3, 3) | -1 impact |
| PAGE_SIZE_LARGE | (5, 3) | (4, 3) | -1 impact |
| CONTENT_STALE | (3, 4) | (3, 2) | -2 effort |
| MISSING_VIEWPORT_META | (6, 1) | (4, 1) | -2 impact |
| INTERNAL_NOFOLLOW | (5, 2) | (3, 2) | -2 impact |
| PARA_TOO_LONG | (4, 2) | (2, 2) | -2 impact |
