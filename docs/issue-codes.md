---
status: current
auto_generated: true
generator: scripts/generate_issue_codes_doc.py
---

# Issue Codes Reference

> **This file is auto-generated.** Do not edit by hand — your changes will be overwritten the next time the generator runs. To update an issue code, edit `api/crawler/issue_checker.py` (`_CATALOGUE`, `_ISSUE_SCORING`, `_AI_READINESS_CONFIDENCE`) and re-run `python scripts/generate_issue_codes_doc.py`.

**170 issue codes** across 13 categories.

## Table of contents

- [METADATA](#metadata) (18)
- [HEADING](#heading) (4)
- [BROKEN_LINK](#broken_link) (8)
- [REDIRECT](#redirect) (8)
- [CRAWLABILITY](#crawlability) (17)
- [SITEMAP](#sitemap) (1)
- [SECURITY](#security) (6)
- [URL_STRUCTURE](#url_structure) (4)
- [IMAGE](#image) (14)
- [AI_READINESS](#ai_readiness) (75)
- [ANALYTICS](#analytics) (7)
- [RENDERING](#rendering) (4)
- [SEMANTIC_HTML](#semantic_html) (4)

---

<a id="metadata"></a>
## METADATA

Title, meta description, OG tags, canonical, favicon.

_18 codes in this category._

### ANCHOR_TEXT_GENERIC
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Links use non-descriptive anchor text like 'click here' or 'read more'

**Recommendation:** Replace generic link text with descriptive text that tells the reader (and search engines) where the link goes. Instead of 'click here', write 'view our counselling services'.

**Plain-English:** Non-Descriptive Link Text

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 2.4.4)](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context) (standard)

> A link's purpose should be determinable from its text; "click here" conveys nothing when links are listed out of context.

---

### CANONICAL_EXTERNAL
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 3

Canonical points to a different domain

**Recommendation:** Review this canonical tag — it is pointing search engines to a page on a different website.

**Plain-English:** External Preferred URL

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) (vendor)

> A canonical pointing to another domain asks Google to index that domain's URL instead of this one.

---

### CANONICAL_MISSING
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2

No canonical tag — page has query strings or is a near-duplicate

**Recommendation:** Add a canonical tag pointing to the preferred URL for this page to prevent duplicate content issues.

**Plain-English:** Ambiguous Preferred URL

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) (vendor)

> A rel=canonical tells Google which URL to treat as authoritative among duplicates, such as query-string variants.

---

### CANONICAL_SELF_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 1

Indexable page has no canonical tag — consider adding a self-referencing canonical

**Recommendation:** Add <link rel="canonical" href="[this-page-url]"> to the page <head>. A self-referencing canonical is a best-practice signal to search engines confirming which URL is the preferred version of this page.

**Plain-English:** No Canonical Tag

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) (vendor)

> Google supports a self-referencing canonical as an explicit statement of the preferred URL.

**What the source does not say:** Google states a canonical is not required. We report the absence as a suggestion, not a fault.

---

### FAVICON_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

No favicon found (homepage only)

**Recommendation:** Add a favicon to your site. This small icon appears in browser tabs and bookmarks and reinforces your brand.

**Plain-English:** Missing Website Icon

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/favicon-in-search) (vendor)

> Google can show a site's favicon beside its search results, and defines how the icon is declared and discovered.

---

### LANG_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 1

Page is missing the lang attribute on the <html> element

**Recommendation:** Add a lang attribute to your <html> tag, e.g. <html lang="en">. This tells search engines and screen readers what language your content is in, improving accessibility and search accuracy for multilingual queries.

**Plain-English:** No Language Declared

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 3.1.1)](https://www.w3.org/WAI/WCAG22/Understanding/language-of-page) (standard)

> The default human language of a page must be programmatically determinable, which the lang attribute provides.

---

### LINK_EMPTY_ANCHOR
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Link has no visible anchor text — screen readers and search engines cannot describe its destination

**Recommendation:** Add descriptive text inside the link. If it is an icon-only link, add an aria-label attribute (e.g. aria-label="Donate now").

**Plain-English:** Empty Link Text

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 2.4.4)](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context) (standard)

> A link with no discernible text has no announceable purpose.

---

### LINK_STACKED_DUPLICATE
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2

**What it is**
Page builders often emit an invisible full-card overlay link plus separate links on the title and the image, all going to the same page. Visually it looks like one clickable card.

**Why it matters**
A screen-reader user hears the same destination announced two or three times, and crawlers see several links where the editor intended one, which muddies which anchor text describes the destination.

**How to fix**
In your page-builder's card or listing template, keep a single link with descriptive text and remove the duplicates. If the overlay link is the one you keep, give it a descriptive aria-label and make the inner elements non-interactive.

**Plain-English:** Stacked Duplicate Links

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. Several links to one destination inside a card (the common "whole card is clickable" pattern) make a screen-reader user hear the same destination repeatedly. It is a usability observation, not a WCAG failure, and the pattern is not wrong in itself.

---

### META_DESC_DUPLICATE
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Same meta description on multiple pages

**Recommendation:** Write a unique meta description for this page that reflects its specific content.

**Plain-English:** Duplicate Summary Snippet

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/snippet) (vendor)

> Google advises a distinct description per page; identical descriptions cannot differentiate results.

---

### META_DESC_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 1 | **Fixability:** wp_fixable

**What it is**
A meta description is a brief summary of a page's content that appears under the title in search results. It helps users decide whether to click on your link.

**Why it matters**
While not a direct ranking factor, a missing description forces search engines to pick random text from your page, which often looks unappealing and reduces click-through rates.

**How to fix**
Add a <meta name='description'> tag to your page. Use your SEO plugin to write a compelling summary that includes your primary keywords.

**Plain-English:** Missing Summary Snippet

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/snippet) (vendor)

> Google uses the meta description as one source for the result snippet when it summarises the page well.

---

### META_DESC_TOO_LONG
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 1 | **Fixability:** wp_fixable

Meta description over 160 characters

**Recommendation:** Shorten the description to under 160 characters. Longer descriptions are cut off in search results.

**Plain-English:** Too-Long Summary Snippet

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/snippet) (vendor)

> Google truncates snippets to the available width and may generate its own text instead.

**What the source does not say:** The 160-character figure is ours. Google publishes no description length and states snippet length varies.

---

### META_DESC_TOO_SHORT
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 1 | **Fixability:** wp_fixable

Meta description under 70 characters

**Recommendation:** Expand the description to 70–160 characters to give search engines more context.

**Plain-English:** Too-Short Summary Snippet

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 70-character floor is ours. Google publishes no minimum and frequently writes its own snippet regardless. A very short description simply has less chance of answering the query.

---

### SOCIAL_PREVIEW_METADATA_MISSING
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 1 | **Fixability:** content_edit

**What it is**
Open Graph and Twitter Card tags control the title, description, and image shown when your page is shared on social platforms. They are typically all set by one plugin/theme option.

**Why it matters**
Shared links look unprofessional — missing image, wrong title, or plain-text preview — reducing click-through from social platforms.

**How to fix**
Populate og:title, og:description, og:image and twitter:card (via your SEO plugin or theme). The finding lists exactly which tags are missing.

**Plain-English:** Missing Social Preview Metadata

**Basis:** published source — [The Open Graph protocol](https://ogp.me/) (standard)

> Open Graph tags declare the title, description and image a platform uses when a URL is shared.

---

### TITLE_DUPLICATE
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Same title used on multiple pages

**Recommendation:** Make each page title unique. Describe what makes this page different from others on your site.

**Plain-English:** Duplicate Page Name

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/title-link) (vendor)

> Google advises a unique, descriptive title for each page so results are distinguishable.

---

### TITLE_H1_MISMATCH
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 2 | **Fixability:** wp_fixable

The page title and the H1 heading share no significant words

**Recommendation:** Align the page title and H1 heading so they describe the same topic. They do not need to be identical, but both should clearly reflect the page's main subject. Significant mismatch confuses users who click a search result and then see an unrelated heading.

**Plain-English:** Title and Heading Disagree

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. A title and an H1 that share no significant words usually means one of them does not describe the page. No source requires them to match, and a deliberate difference is legitimate.

---

### TITLE_MISSING
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 1 | **Fixability:** wp_fixable

**What it is**
The title tag is the most important on-page SEO element. It tells search engines and users what the page is about and appears as the clickable headline in search results.

**Why it matters**
Without a title tag, search engines may not index your page correctly, and users won't see a relevant headline in search results, significantly reducing your click-through rate.

**How to fix**
Add a <title> tag to the <head> section of your HTML. In WordPress, you can typically set this using your SEO plugin (Yoast, Rank Math) or the page editor.

**Plain-English:** Missing Name Tag

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/title-link) (vendor)

> Google uses the title element as the primary source for the title link shown in search results.

---

### TITLE_TOO_LONG
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 1 | **Fixability:** wp_fixable

Title over 60 characters

**Recommendation:** Aim for about 60 characters. Google does not publish a title length limit — it truncates by pixel width, and may rewrite a title regardless of length — so treat 60 as a guide, not a rule.

**Plain-English:** Too-Long Page Name

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/title-link) (vendor)

> Google may rewrite or truncate a title link when it does not suit the query or the available width.

**What the source does not say:** The 60-character figure is ours. Google publishes no title length limit; truncation is by pixel width, which varies by device and characters used.

---

### TITLE_TOO_SHORT
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 1 | **Fixability:** wp_fixable

Title under 30 characters

**Recommendation:** Expand the title to 30–60 characters. Include your organisation name and the page topic.

**Plain-English:** Too-Short Page Name

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/title-link) (vendor)

> Google advises titles be descriptive and concise rather than vague or generic.

**What the source does not say:** The 30-character floor is ours. Google publishes no minimum. A short title is not automatically a poor one.

---

<a id="heading"></a>
## HEADING

H1 presence and uniqueness, heading hierarchy, empty headings.

_4 codes in this category._

### H1_MISSING
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 1 | **Fixability:** content_edit

No H1 tag found on page

**Recommendation:** Add a single H1 heading that clearly states the main topic of this page.

**Plain-English:** Missing Main Heading

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 1.3.1)](https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships) (standard)

> Structure conveyed visually must be available programmatically; a top-level heading is how a page states its subject.

---

### H1_MULTIPLE
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

More than one H1 on the page

**Recommendation:** Remove extra H1 tags. Each page should have exactly one H1 that introduces the main topic.

**Plain-English:** Multiple Main Headings

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and Google has said publicly that multiple H1s are fine. The HTML standard permits them. We report it as a structure-clarity signal, not a ranking fault, and score it accordingly. Anyone told this must be fixed for Google's sake has been misinformed.

---

### HEADING_EMPTY
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 1 | **Fixability:** content_edit

One or more heading tags have no text content

**Recommendation:** Remove empty heading tags or add descriptive text. Empty headings confuse screen readers and waste heading structure.

**Plain-English:** Empty Heading

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 2.4.6)](https://www.w3.org/WAI/WCAG22/Understanding/headings-and-labels) (standard)

> Headings must describe topic or purpose; a heading with no text describes nothing and still occupies the outline.

---

### HEADING_SKIP
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 3 | **Fixability:** content_edit

Heading levels skip (e.g., H1 → H3)

**Recommendation:** Fix the heading structure so levels are not skipped. Use H1, then H2, then H3 in order.

**Plain-English:** Skipped Heading Level

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 1.3.1)](https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships) (standard)

> Heading levels express document structure; a skipped level misstates the nesting to anyone navigating by headings.

**What the source does not say:** Skipping a level is advisory in WCAG, not a conformance failure. We report it as structure, not as an accessibility violation.

---

<a id="broken_link"></a>
## BROKEN_LINK

Internal and external links returning 4xx/5xx, login redirects.

_8 codes in this category._

### BROKEN_LINK_404
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** wp_fixable

Link destination returns 404 Not Found

**Recommendation:** Remove or update this link. The page it points to no longer exists.

**Plain-English:** Dead Link

**Basis:** published source — [IETF RFC 9110 §15.5.5](https://www.rfc-editor.org/rfc/rfc9110) (standard)

> 404 means the origin server found no current representation for the target resource.

---

### BROKEN_LINK_410
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** wp_fixable

Link destination returns 410 Gone

**Recommendation:** Remove this link. The destination has been permanently removed.

**Plain-English:** Removed Link

**Basis:** published source — [IETF RFC 9110 §15.5.11](https://www.rfc-editor.org/rfc/rfc9110) (standard)

> 410 means the resource is permanently gone and the condition is expected to be permanent.

---

### BROKEN_LINK_503
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 3

Link destination returns 503 — may be temporarily down or blocking automated checks

**Recommendation:** Visit the link manually to see if it loads for real visitors. If the problem persists, the destination site may be down or blocking crawlers.

**Plain-English:** Temporarily Blocked Link

**Basis:** published source — [IETF RFC 9110 §15.6.4](https://www.rfc-editor.org/rfc/rfc9110) (standard)

> 503 means the server is temporarily unable to handle the request — a transient condition, not a broken destination.

---

### BROKEN_LINK_5XX
**Severity:** 🔵 info | **Tier:** high | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

Link destination returns a server error

**Recommendation:** Check whether the linked site is down. If the problem persists, remove or replace the link.

**Plain-English:** Broken Server Link

**Basis:** published source — [IETF RFC 9110 §15.6](https://www.rfc-editor.org/rfc/rfc9110) (standard)

> A 5xx status means the server failed to fulfil an apparently valid request.

---

### EXTERNAL_LINK_SKIPPED
**Severity:** 🔵 info | **Tier:** low | **Impact:** 0 | **Effort:** 1

Link not verified — social media platforms block automated checks

**Recommendation:** Open this link in a browser to confirm it is working correctly.

**Plain-English:** Unverified Social Link

**Basis:** measured during the crawl — not a published claim.

> TalkingToad chose not to verify this destination, typically because the platform blocks automated checks. Recorded so an unverified link is never silently counted as working. Says nothing about whether the link works.

---

### EXTERNAL_LINK_TIMEOUT
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 1

External link did not respond — destination may be slow or unavailable

**Recommendation:** Click the link to confirm it works in a browser. If it consistently fails, the destination site may be down or the domain may have expired.

**Plain-English:** Slow External Link

**Basis:** measured during the crawl — not a published claim.

> The destination did not respond within TalkingToad's timeout. Recorded as unverified, not as broken: a slow response and a dead host are different findings and must not be reported as the same one.

---

### PLACEHOLDER_LINK
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2

**What it is**
A placeholder link is a styled link or button whose href is a stand-in ('#', 'javascript:void(0)') rather than a real URL. It often 'works' via JavaScript for human clicks but resolves to nothing for an automated follower.

**Why it matters**
AI crawlers and task agents follow href values. A key action whose href is a placeholder is a dead end — the agent cannot complete the journey (e.g. reach your donation or contact page), and the page graph looks broken.

**How to fix**
Set the link's href to the actual target page. Reserve '#'/'javascript:void(0)' for genuine in-page controls (accordions, tabs) — not for navigation.

**Plain-English:** Dead Call-to-Action Link

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement that a call-to-action whose href is "#" or "javascript:void(0)" with no handler is a dead control. No standard forbids it — the pattern is legitimate for JS-driven widgets — so this is reported on navigational elements only, where a destination is expected.

---

### WRONG_PLACEHOLDER_LINK
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

**What it is**
A link whose destination is an obvious placeholder — example.com, example.org, localhost, 127.0.0.1, or a bare search-engine homepage used as filler — rather than the page it was meant to point to.

**Why it matters**
An agent following the link lands somewhere meaningless (or unreachable), breaking the task or citation trail. These are almost always unfinished template content that shipped by mistake.

**How to fix**
Edit the link to use the real URL. If the link is a legitimate reference to that domain, ignore the flag — the check is conservative and uses link text and position to avoid false positives.

**Plain-English:** Link to Placeholder Domain

**Basis:** published source — [IETF RFC 2606](https://www.rfc-editor.org/rfc/rfc2606) (standard)

> example.com, example.net and example.org are reserved for documentation and cannot serve a real destination.

---

<a id="redirect"></a>
## REDIRECT

Redirect chains, loops, and per-status-code findings.

_8 codes in this category._

### INTERNAL_REDIRECT_301
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 1

Internal page URL redirects with a 301 — links should point to the final URL

**Recommendation:** Update all internal links pointing to this URL to use the final destination directly. This eliminates an unnecessary redirect for every visitor.

**Plain-English:** Internal Redirect Link

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/301-redirects) (vendor)

> Google recommends updating internal links to point at the final URL rather than relying on a redirect.

---

### META_REFRESH_REDIRECT
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2

Page uses a <meta http-equiv="refresh"> tag to redirect users

**Recommendation:** Replace meta refresh redirects with server-side 301 redirects.

**Plain-English:** HTML Redirect (Outdated)

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 2.2.1)](https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable) (standard)

> A timed client-side redirect moves users without their control unless the delay can be adjusted or turned off.

---

### REDIRECT_301
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2

Page returns a permanent redirect

**Recommendation:** Update any internal links pointing here to use the final destination URL directly.

**Plain-English:** Permanent Redirect

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/301-redirects) (vendor)

> A 301 is the permanent-move signal Google uses to transfer a URL's indexing signals to the target.

---

### REDIRECT_302
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2

Page returns a temporary redirect

**Recommendation:** Confirm whether this redirect is intentional. If permanent, change it to a 301 redirect.

**Plain-English:** Temporary Redirect

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/301-redirects) (vendor)

> A 302 signals a temporary move, so Google keeps indexing the original URL.

---

### REDIRECT_CASE_NORMALISE
**Severity:** 🔵 info | **Tier:** low | **Impact:** 0 | **Effort:** 1

Redirect normalises URL case — your web server handles this automatically

**Recommendation:** No urgent action needed. Your server redirects uppercase URLs to lowercase automatically. To eliminate the extra redirect, update internal links to use lowercase-only URLs.

**Plain-English:** Auto-Corrected URL (Case)

**Basis:** TalkingToad's own judgement. No published source states this.

> TalkingToad's own judgement that a redirect existing only to normalise URL case is routine server behaviour and not a defect. It is reported for completeness, not as something to fix. No source is claimed because no source is needed for a decision to say less.

---

### REDIRECT_CHAIN
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 3

Page involves a multi-hop redirect chain

**Recommendation:** Consolidate the redirect chain to a single direct redirect to the final destination.

**Plain-English:** Multi-Hop Detour

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/301-redirects) (vendor)

> Google advises keeping redirect chains short; long chains cost crawl budget and risk being abandoned.

**What the source does not say:** Google does not publish a maximum hop count. The hop count at which TalkingToad reports is ours.

---

### REDIRECT_LOOP
**Severity:** 🔴 critical | **Impact:** 10 | **Effort:** 4

Redirect loop detected

**Recommendation:** Fix the redirect configuration immediately. This page cannot load and is invisible to search engines.

**Plain-English:** Spinning Page

**Basis:** published source — [IETF RFC 9110](https://www.rfc-editor.org/rfc/rfc9110) (standard)

> A client must detect and break redirect cycles; a looping URL can never be retrieved.

---

### REDIRECT_TRAILING_SLASH
**Severity:** 🔵 info | **Tier:** low | **Impact:** 0 | **Effort:** 1

Redirect adds or removes a trailing slash — your CMS handles this automatically

**Recommendation:** No urgent action needed. Your CMS corrects this for visitors automatically. To eliminate the extra round trip, update internal links to use the canonical URL with the trailing slash your server expects.

**Plain-English:** Auto-Corrected URL (Slash)

**Basis:** TalkingToad's own judgement. No published source states this.

> As above: adding or removing a trailing slash is standard CMS behaviour. Reported so the redirect is visible, explicitly not scored as a fault.

---

<a id="crawlability"></a>
## CRAWLABILITY

robots.txt blocks, noindex directives, thin content, orphan pages.

_17 codes in this category._

### AMPHTML_BROKEN
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 3

Page declares an AMP version via <link rel="amphtml"> but the AMP URL is not reachable

**Recommendation:** Fix the AMP URL or remove the amphtml link element if AMP is no longer in use.

**Plain-English:** Broken Mobile Version

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. A declared AMP version that does not resolve is a broken reference by inspection. AMP itself is deprecated as a Google Search requirement, so this is reported as cleanup, not as an SEO fault.

---

### CONTENT_STALE
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 3 | **Fixability:** content_edit

Page content has not been modified in over 12 months

**Recommendation:** Review and refresh this page's content. Search engines favour recently updated pages, and visitors may lose trust in outdated information. Even small updates signal freshness.

**Plain-English:** Stale Content

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 12-month window is ours. Age is not a defect — reference content is often correct for years. It flags pages worth a review, and is deliberately scored low.

---

### HIGH_CRAWL_DEPTH
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 3

Page is more than 4 clicks from the homepage

**Recommendation:** Improve internal linking so this page can be reached in 3 clicks or fewer from the homepage.

**Plain-English:** Hard-to-Reach Page

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 4-click figure is ours. Google publishes no depth limit. Deeply buried pages tend to be crawled less often and are harder for people to reach; neither effect has a published threshold.

---

### INTERNAL_NOFOLLOW
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

Internal link carries rel="nofollow", which may prevent search engines from discovering linked pages

**Recommendation:** Remove the nofollow attribute from internal links. Reserve rel="nofollow" for links to external or user-generated content.

**Plain-English:** Blocked Internal Link

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/qualify-outbound-links) (vendor)

> rel="nofollow" tells Google not to use the link for discovery or ranking, which on an internal link works against the site.

---

### LOGIN_REDIRECT
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 1

Page redirects to a login screen

**Recommendation:** This page requires a login to access. The crawler cannot audit it. Review manually if needed.

**Plain-English:** Login-Protected Page

**Basis:** measured during the crawl — not a published claim.

> The URL redirected to a login screen during this crawl, so its content was not read. Frequently intended. Recorded so the page is not counted as a healthy public page.

---

### MISSING_VIEWPORT_META
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 1

Page is missing the viewport meta tag

**Recommendation:** Add <meta name="viewport" content="width=device-width, initial-scale=1"> to the <head>. Without it, mobile browsers render the page at desktop width and zoom out, making it hard to use.

**Plain-English:** Not Mobile-Friendly

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/page-experience) (vendor)

> Google evaluates whether pages work on mobile devices; without a viewport meta tag a page is rendered at desktop width and zoomed out.

---

### NOINDEX_HEADER
**Severity:** 🔴 critical | **Impact:** 10 | **Effort:** 2

Page has a noindex HTTP header

**Recommendation:** Check your server configuration. This page is being hidden from search engines via an HTTP header.

**Plain-English:** Hidden from Search (Server)

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/block-indexing) (vendor)

> X-Robots-Tag&#58; noindex in the HTTP response has the same effect as the meta tag, and applies to non-HTML files too.

---

### NOINDEX_META
**Severity:** 🔴 critical | **Impact:** 10 | **Effort:** 1 | **Fixability:** wp_fixable

Page has a noindex meta tag

**Recommendation:** Confirm whether this page should be excluded from search results. Remove the noindex tag if not.

**Plain-English:** Hidden from Search

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/block-indexing) (vendor)

> A noindex meta tag instructs Google to drop the page from its index entirely.

---

### NOT_IN_SITEMAP
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 1 | **Fixability:** wp_fixable

Crawlable page not listed in sitemap

**Recommendation:** Add this URL to your XML sitemap so search engines can find it more reliably.

**Plain-English:** Missing from Sitemap

**Basis:** published source — [sitemaps.org protocol](https://www.sitemaps.org/protocol.html) (standard)

> A sitemap lists the URLs a site wants crawled; a crawlable page absent from it is not advertised for discovery.

**What the source does not say:** Omission from a sitemap does not prevent indexing. Reported as a discovery gap, not a fault.

---

### ORPHAN_PAGE
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Page has no internal links pointing to it — search engines may not discover it

**Recommendation:** Add at least one internal link to this page from a navigation menu, hub page, or relevant content page so search engines and visitors can find it.

**Plain-English:** Disconnected Page

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers) (vendor)

> Google discovers pages primarily by following links; a page nothing links to must be found some other way.

**What the source does not say:** Only sound over a complete link graph. TalkingToad suppresses this check on a partial scan rather than infer absence from a subset.

---

### PAGE_SIZE_LARGE
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 3

HTML page response is unusually large — slower to load, especially on mobile connections

**Recommendation:** Reduce page weight by removing unused HTML, lazy-loading off-screen content, and deferring non-critical scripts. Large pages cost more mobile data and take longer to render.

**Plain-English:** Overweight Page

**Basis:** published source — [web.dev (Google)](https://web.dev/articles/lcp) (vendor)

> Response size is one determinant of how quickly the main content can be rendered.

**What the source does not say:** The size at which we report is ours. No source sets an HTML weight limit.

---

### PAGE_TIMEOUT
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 3

Page did not respond within the timeout period

**Recommendation:** Check the page manually. A persistent timeout may indicate a slow server, heavy page weight, or a broken URL. Consider increasing server response speed.

**Plain-English:** Slow-Loading Page

**Basis:** measured during the crawl — not a published claim.

> The page did not respond within TalkingToad's own timeout during this crawl. Records that the page was not read, so it is never counted as clean. Not a verdict on the site's speed for a visitor.

---

### PAGINATION_LINKS_PRESENT
**Severity:** 🔵 info | **Tier:** low | **Impact:** 0 | **Effort:** 2

Page declares rel="next" or rel="prev" pagination link elements

**Recommendation:** No action required. Ensure the linked pages are crawlable.

**Plain-English:** Paginated Content

**Basis:** TalkingToad's own judgement. No published source states this.

> Purely informational. Google announced in 2019 that it no longer uses rel=next/prev for indexing. Reported so the markup is visible; explicitly not scored as a fault, and not a recommendation to remove it.

---

### PARA_TOO_LONG
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

One or more paragraphs exceed 150 words, making content harder to scan and extract

**Recommendation:** Break long paragraphs into shorter units of 50–100 words each. Short paragraphs improve both human readability and AI passage extraction — AI systems prefer self-contained, focused chunks.

**Plain-English:** Overly Long Paragraphs

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 150-word figure is ours. No standard sets a paragraph length. Long paragraphs are harder to scan on a phone; that is a readability opinion, not a ranking claim.

---

### PDF_TOO_LARGE
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 2

PDF file exceeds 10 MB

**Recommendation:** Reduce the PDF file size. Large PDFs are slow to download and may be skipped by crawlers.

**Plain-English:** Oversized Document

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 10 MB figure is ours. It reflects what is reasonable to ask a visitor on a mobile connection to download, not any published limit.

---

### ROBOTS_BLOCKED
**Severity:** 🔴 critical | **Impact:** 9 | **Effort:** 2

Page blocked by robots.txt

**Recommendation:** Check whether this page should be blocked. If not, update your robots.txt file.

**Plain-English:** Blocked by Crawl Rules

**Basis:** published source — [IETF RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) (standard)

> A Disallow rule instructs a conforming crawler not to fetch the matching paths.

---

### THIN_CONTENT
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 3 | **Fixability:** content_edit

Page has fewer than 300 words of body content

**Recommendation:** Expand the page content to at least 300 words to provide more value to users and search engines.

**Plain-English:** Low Information

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) (vendor)

> Google advises pages provide substantial, complete and comprehensive coverage of their topic.

**What the source does not say:** The 300-word figure is ours. Google publishes no word count and states explicitly that there is no minimum. A short page can be complete.

---

<a id="sitemap"></a>
## SITEMAP

Sitemap presence and per-URL coverage.

_1 codes in this category._

### SITEMAP_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2

No sitemap found for this domain

**Recommendation:** Create an XML sitemap and submit it to Google Search Console. Most CMS platforms can generate one automatically.

**Plain-English:** No Sitemap

**Basis:** published source — [sitemaps.org protocol](https://www.sitemaps.org/protocol.html) (standard)

> A sitemap lets a site tell crawlers which URLs are available and is the standard mechanism for URL discovery.

---

<a id="security"></a>
## SECURITY

HTTPS, HSTS, mixed content, unsafe cross-origin links.

_6 codes in this category._

### HTTPS_REDIRECT_MISSING
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2

HTTP version of the site does not redirect to HTTPS

**Recommendation:** Configure a server-side 301 redirect from http:// to https:// for all URLs on your domain. Without this, visitors who type your address without 'https' will reach an insecure version of your site — and search engines treat HTTP and HTTPS as separate, competing URLs.

**Plain-English:** Insecure URL Not Redirected

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/fundamentals/seo-starter-guide) (vendor)

> Google's own starter guidance is written around a site served over HTTPS, with one scheme serving each URL.

---

### HTTP_PAGE
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2

Page is served over HTTP, not HTTPS

**Recommendation:** Migrate to HTTPS and configure a server-side 301 redirect from HTTP to HTTPS.

**Plain-English:** Unsecured Page

**Basis:** published source — [Google Search Central](https://web.dev/articles/why-https-matters) (vendor)

> Google states HTTPS protects the integrity and confidentiality of a site's traffic and is a prerequisite for many web platform features.

---

### MISSING_HSTS
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 2

HTTPS page is missing the Strict-Transport-Security header

**Recommendation:** Add Strict-Transport-Security: max-age=31536000; includeSubDomains to all HTTPS responses.

**Plain-English:** Security Header Missing

**Basis:** published source — [IETF RFC 6797](https://www.rfc-editor.org/rfc/rfc6797) (standard)

> Strict-Transport-Security instructs a browser to use HTTPS only, closing the first-request downgrade window.

---

### MIXED_CONTENT
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

HTTPS page loads resources over HTTP

**Recommendation:** Update all resource URLs to use HTTPS. Check images, scripts, stylesheets, and iframes.

**Plain-English:** Partially Unsecured Page

**Basis:** published source — [MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/Security/Mixed_content) (standard)

> Browsers block or downgrade insecure subresources on an HTTPS page, so mixed content breaks the page's security guarantee.

---

### UNSAFE_CROSS_ORIGIN_LINK
**Severity:** 🔵 info | **Tier:** low | **Impact:** 0 | **Effort:** 1

External link opens in a new tab without rel="noopener" or rel="noreferrer"

**Recommendation:** Add rel="noopener noreferrer" to all <a target="_blank"> links pointing to external URLs.

**Plain-English:** Unsafe External Link

**Basis:** published source — [OWASP](https://owasp.org/www-community/attacks/Reverse_Tabnabbing) (industry)

> A target="_blank" link without rel="noopener" lets the opened page rewrite the opener's location.

---

### WWW_CANONICALIZATION
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

Both www and non-www versions of the site resolve without redirecting to each other

**Recommendation:** Configure a 301 redirect so one version (www or non-www) redirects to the other. This consolidates link equity and avoids duplicate content.

**Plain-English:** www/non-www Not Consolidated

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/canonicalization) (vendor)

> When several URLs serve the same content Google picks one canonical; serving both www and non-www without redirecting leaves that choice to Google.

---

<a id="url_structure"></a>
## URL_STRUCTURE

URL format: uppercase, spaces, underscores, length.

_4 codes in this category._

### URL_HAS_SPACES
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

URL contains encoded spaces (%20)

**Recommendation:** Replace spaces in URLs with hyphens.

**Plain-English:** Spaces in Web Address

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/url-structure) (vendor)

> Google recommends simple, readable URLs; percent-encoded spaces make a URL harder to read and to share intact.

---

### URL_HAS_UNDERSCORES
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

URL path uses underscores instead of hyphens

**Recommendation:** Use hyphens as word separators in URL paths. Google treats underscores as word-joiners.

**Plain-English:** Underscores in Web Address

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/url-structure) (vendor)

> Google recommends hyphens rather than underscores to separate words in a URL path.

---

### URL_TOO_LONG
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

URL exceeds 200 characters

**Recommendation:** Shorten the URL slug. Long URLs are harder to share and may be truncated in search results.

**Plain-English:** Overly Long Web Address

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 200-character figure is ours. Google states no URL length limit for ranking. Long URLs are harder to share and more often truncated in display, which is a usability argument, not a ranking one.

---

### URL_UPPERCASE
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

URL path contains uppercase characters

**Recommendation:** Use lowercase-only URLs. Most web servers will auto-redirect uppercase URLs to lowercase, but this creates an unnecessary extra redirect. Update internal links and page slugs to use lowercase only to avoid that redirect entirely.

**Plain-English:** Mixed-Case Web Address

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. URL paths are case-sensitive on most servers, so mixed case invites duplicate URLs for one page. Google does not require lowercase paths; consistency is the point, not the case itself.

---

<a id="image"></a>
## IMAGE

Image accessibility, performance, format, srcset, and content checks.

_14 codes in this category._

### IMG_ALT_DUP_FILENAME
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 1 | **Fixability:** wp_fixable

Image alt text matches the filename

**Recommendation:** Write descriptive alt text instead of using the filename. Describe what the image shows to help search engines and screen reader users.

**Plain-English:** Alt Text is Filename

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. Alt text identical to the filename is almost always auto-generated rather than written, so it rarely serves the equivalent purpose WCAG 1.1.1 requires. Occasionally a filename genuinely is the best description, so this is reported, not asserted.

---

### IMG_ALT_GENERIC
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 1 | **Fixability:** wp_fixable

Image alt text uses a generic term like 'image', 'photo', or 'picture'

**Recommendation:** Replace generic alt text with a specific description of what the image shows. Instead of 'photo', describe the scene, people, or objects depicted.

**Plain-English:** Generic Alt Text

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 1.1.1)](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content) (standard)

> The alternative must serve the equivalent purpose; "image" or "photo" conveys nothing the element did not already announce.

---

### IMG_ALT_MISSING
**Severity:** 🔵 info | **Tier:** high | **Impact:** 3 | **Effort:** 2 | **Fixability:** wp_fixable

One or more images are missing an alt attribute or have empty/blank alt text

**Recommendation:** Add a descriptive alt attribute to every <img> tag. Describe what the image shows in plain language, e.g. alt="Counsellor speaking with a young person". Every image should have meaningful alt text for accessibility and SEO.

**Plain-English:** Images Missing Alt Text

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 1.1.1)](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content) (standard)

> Non-text content must have a text alternative serving the equivalent purpose.

---

### IMG_ALT_MISUSED
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

Alt text usage is incorrect for image type (decorative image has alt text)

**Recommendation:** Decorative images should have empty alt="" to be skipped by screen readers. Only meaningful images should have descriptive alt text.

**Plain-English:** Alt Text Misused

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 1.1.1)](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content) (standard)

> Purely decorative images must be implemented so assistive technology can ignore them — which alt="" does and descriptive alt text defeats.

---

### IMG_ALT_TOO_LONG
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 1 | **Fixability:** wp_fixable

Image alt text is too long (over 125 characters)

**Recommendation:** Shorten the alt text to under 125 characters. Be concise while still describing the image content. Screen readers may truncate longer alt text.

**Plain-English:** Alt Text Too Long

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 125-character figure is ours. WCAG sets no length. The figure is long-standing practitioner convention reflecting older screen readers; a longer alt is not a conformance failure, and a complex image may need one.

---

### IMG_ALT_TOO_SHORT
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 1 | **Fixability:** wp_fixable

Image alt text is too short (under 5 characters)

**Recommendation:** Expand the alt text to at least 5 characters. Describe what the image shows, not just a single word.

**Plain-English:** Alt Text Too Short

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 5-character floor is ours. WCAG sets no minimum, and a very short alt can be exactly right ("Logo"). It flags the case where alt was filled in to silence a checker.

---

### IMG_BROKEN
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

Image src URL returns an error response (4xx/5xx)

**Recommendation:** Replace or remove the broken image. Use your CMS media library to re-upload the file or update the src URL to point to the correct location.

**Plain-English:** Broken Image

**Basis:** published source — [IETF RFC 9110](https://www.rfc-editor.org/rfc/rfc9110) (standard)

> A 4xx or 5xx response means no representation was returned, so the image cannot render.

---

### IMG_DUPLICATE_CONTENT
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 2

Same image content used under multiple URLs

**Recommendation:** Consolidate duplicate images to a single URL. This saves server space and improves caching efficiency.

**Plain-English:** Duplicate Image

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. Byte-identical images under different URLs each occupy the cache separately and are each downloaded once. Not a ranking claim, and duplicates are sometimes deliberate.

---

### IMG_FORMAT_LEGACY
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Image uses legacy format (JPEG/PNG/GIF) where WebP would save significant space

**Recommendation:** Convert to WebP format for 25-35% smaller file sizes with the same quality. Most modern browsers support WebP.

**Plain-English:** Legacy Image Format

**Basis:** published source — [web.dev (Google)](https://web.dev/articles/serve-images-webp) (vendor)

> WebP typically produces substantially smaller files than equivalent-quality JPEG or PNG.

---

### IMG_NO_SRCSET
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 3

Large image lacks srcset for responsive delivery

**Recommendation:** Add a srcset attribute to serve appropriately sized images to mobile devices. This improves load times on smaller screens.

**Plain-English:** Missing Responsive Images

**Basis:** published source — [web.dev (Google)](https://web.dev/articles/serve-responsive-images) (vendor)

> srcset lets the browser choose a source matched to the device, avoiding the download of pixels it cannot display.

---

### IMG_OVERSCALED
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 3 | **Fixability:** content_edit

Image intrinsic size is more than 2x its display size (wasted bandwidth)

**Recommendation:** Resize the image to match its display dimensions. Use srcset to serve appropriately sized images to different devices.

**Plain-English:** Overscaled Image

**Basis:** published source — [web.dev (Google)](https://web.dev/articles/serve-responsive-images) (vendor)

> Serving an image substantially larger than its display size transfers bytes the user can never see.

**What the source does not say:** The 2x ratio is ours. No source sets a threshold, and 2x is deliberately lenient so high-density displays are not flagged.

---

### IMG_OVERSIZED
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Image file exceeds 200 KB

**Recommendation:** Compress this image. Use Squoosh, TinyPNG, or ImageOptim to reduce the file size without visible quality loss.

**Plain-English:** Oversized Image

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 200 KB figure is ours. No source publishes a per-image weight limit; what matters is the page total and the connection. The figure is a practical budget for a nonprofit site on mobile, and is configurable.

---

### IMG_POOR_COMPRESSION
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Image has poor compression efficiency (high bytes per pixel)

**Recommendation:** Re-compress the image using WebP format for better efficiency. Use tools like Squoosh or ImageOptim for lossless compression.

**Plain-English:** Poor Compression

**Basis:** published source — [Chrome Lighthouse documentation (Google)](https://developer.chrome.com/docs/lighthouse/performance/uses-optimized-images) (vendor)

> Images that are not efficiently encoded transfer more bytes than their visual quality requires.

**What the source does not say:** The bytes-per-pixel threshold is ours. It is a proxy: some images legitimately need a high bit rate.

---

### IMG_SLOW_LOAD
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2

Image takes too long to load (over 1 second)

**Recommendation:** Optimize the image by compressing it, reducing dimensions, or using a CDN. Consider lazy loading for below-the-fold images.

**Plain-English:** Slow Loading Image

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 1-second figure is ours. It is measured from the crawler's network, not the user's, so it indicates a slow origin rather than a slow experience for any particular visitor.

---

<a id="ai_readiness"></a>
## AI_READINESS

Site readiness for AI search engines (Google AI Overviews, ChatGPT, Perplexity, etc.). Every code in this category carries a confidence label per the v2.0 spec: **Established** (vendor-confirmed effect), **Reasonable proxy** (industry consensus + Google's published best practices), **Heuristic** (industry consensus only, no vendor confirmation).

_75 codes in this category._

### AI_BOT_BLANKET_DISALLOW
**Severity:** 🔴 critical | **Confidence:** Established | **Impact:** 9 | **Effort:** 1

robots.txt blocks all bots with User-agent: * / Disallow: /

**Recommendation:** Update robots.txt to allow at least AI search bots. Remove 'Disallow: /' or add specific allow rules for AI crawlers.

**Plain-English:** All Bots Blocked

**Basis:** published source — [IETF RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) (standard)

> User-agent: * with Disallow: / instructs every conforming crawler to fetch nothing.

---

### AI_BOT_DEPRECATED_DIRECTIVE
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Established | **Impact:** 2 | **Effort:** 1

robots.txt references a deprecated AI bot user agent

**Recommendation:** Remove deprecated directives (anthropic-ai, claude-web) and replace with current bot names (ClaudeBot, Claude-SearchBot, Claude-User).

**Plain-English:** Deprecated AI Bot Name in robots.txt

**Basis:** published source — [OpenAI bot documentation](https://platform.openai.com/docs/bots) (vendor)

> The vendors publish their current user-agent tokens; a rule naming a token no longer in use has no effect.

---

### AI_BOT_NO_AI_DIRECTIVES
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 1

robots.txt has no explicit directives for known AI bots

**Recommendation:** Add explicit AI bot rules to make your intent clear. Example: allow all search bots while optionally blocking training bots.

**Plain-English:** No AI Bot Configuration

**Basis:** TalkingToad's own judgement. No published source states this.

> Informational, and deliberately not a recommendation. It reports that robots.txt names no AI crawler either way. Whether to allow or block them is the organisation's decision, and TalkingToad takes no position on it.

---

### AI_BOT_SEARCH_BLOCKED
**Severity:** 🔴 critical | **Confidence:** Established | **Impact:** 9 | **Effort:** 1

A major AI search bot is disallowed in robots.txt

**Recommendation:** Allow AI search bots in robots.txt. This bot enables ChatGPT, Gemini, and other AI engines to include your site in their answers.

**Plain-English:** AI Search Bot Blocked

**Basis:** published source — [OpenAI bot documentation](https://platform.openai.com/docs/bots) (vendor)

> OpenAI documents its crawler user agents and states that disallowing them in robots.txt stops those fetches.

---

### AI_BOT_TABLE_STALE
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 0 | **Effort:** 1

Internal AI bot reference table has not been reviewed in >12 months

**Recommendation:** Review and update the TalkingToad AI bot reference table.

**Plain-English:** AI Bot Table Needs Review

**Basis:** measured during the crawl — not a published claim.

> TalkingToad's own table of AI crawler user agents has not been refreshed within the freshness window. A statement about this tool, not about the site, surfaced because a stale table produces confident wrong answers.

---

### AI_BOT_TRAINING_DISALLOWED
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Established | **Impact:** 0 | **Effort:** 1

An AI training bot is disallowed in robots.txt

**Recommendation:** This may be intentional. If accidental, allow the bot. Blocking training bots does not affect AI search visibility.

**Plain-English:** AI Training Bot Disallowed

**Basis:** published source — [OpenAI bot documentation](https://platform.openai.com/docs/bots) (vendor)

> GPTBot is the documented training crawler and honours a robots.txt disallow.

**What the source does not say:** Blocking training crawlers is a legitimate choice. TalkingToad reports the state and does not recommend allowing it.

---

### AI_BOT_USER_FETCH_BLOCKED
**Severity:** 🔵 info | **Tier:** high | **Confidence:** Established | **Impact:** 3 | **Effort:** 1

An AI user-fetch bot is disallowed in robots.txt

**Recommendation:** Decide deliberately. robots.txt compliance for user-fetch bots is vendor-specific: Anthropic's Claude-User honors robots.txt (so this block does stop it — a real visibility cost if unintended), while OpenAI's ChatGPT-User treats robots.txt as 'may not apply' and Perplexity-User ignores it. Remove the block only if you want these assistants to fetch the page.

**Plain-English:** AI User Bot Blocked

**Basis:** published source — [OpenAI bot documentation](https://platform.openai.com/docs/bots) (vendor)

> OpenAI documents a separate user-triggered fetch agent, so blocking it stops retrieval on behalf of a person who asked for the page by name.

---

### AI_CITED_PAGE
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Established | **Impact:** 0 | **Effort:** 0 | **Fixability:** content_edit

This page has been cited by AI engines in the last 30 days, indicating established AI visibility.

**Recommendation:** Maintain content quality and freshness to sustain AI citation status.

**Plain-English:** AI-Cited Page

**Basis:** measured during the crawl — not a published claim.

> A citation of this URL was recorded by the configured citation source within the window. An observation, not a prediction. It establishes nothing about pages with no recorded citation, which may simply not have been sampled.

---

### AI_CONTENT_NOT_IN_TEXT
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Important content on this page is not in textual form — it is carried by images/video or locked inside an embed (iframe/PDF) that AI systems cannot read as text

**Recommendation:** Provide the key information as real on-page text. Add a textual summary or transcript alongside any image, video, or embedded document so AI systems and screen readers can access it.

**Plain-English:** Content Not Available as Text

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 1.1.1)](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content) (standard)

> Information carried only by an image needs a text alternative to be available to anything that reads text.

---

### AI_HIGH_VALUE_UNCITED
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

This healthy, content-rich page has zero AI citations despite recent data, suggesting an AI visibility gap.

**Recommendation:** Improve content structure, add schema markup, and build backlinks to increase AI discoverability.

**Plain-English:** High-Value Page Not AI-Cited

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the weakest kind. That a page we rate as high-value has no recorded citation may mean it is not being surfaced, or only that our sampling did not see one. Absence of a citation is not evidence of a problem, which is why this is labelled Heuristic and scored low.

---

### AI_MAIN_CONTENT_LOW_RATIO
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 1 | **Fixability:** content_edit

The main content area contains less than 40% of the page's visible text. Navigation, sidebar, and footer content dominates, making it harder for AI systems and readers to identify the primary content.

**Recommendation:** Consider reducing navigation/sidebar/footer content, or expanding the main content area. Ensure the main content is at least 40% of the page's visible text.

**Plain-English:** Low Main Content Ratio

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 40% figure is ours. It depends on TalkingToad identifying the main content area correctly, which on an unusual template it may not.

---

### AI_NO_VISUAL_COMPANION
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 1 | **Fixability:** content_edit

A substantial text page (article/service/FAQ) has no images or video to support its content

**Recommendation:** Add at least one relevant, high-quality image or video. Visuals help both readers and AI systems understand and surface your content.

**Plain-English:** No Supporting Visual

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the weakest kind. A long text page with no image may be harder to engage with. Nothing establishes an effect on AI retrieval, and it is scored accordingly.

---

### AI_PREVIEW_BLOCKED_AT_BOT
**Severity:** 🟡 warning | **Confidence:** Established | **Impact:** 4 | **Effort:** 1

An X-Robots-Tag directive specifically blocks an AI crawler (e.g. GPTBot, Google-Extended) from indexing this page

**Recommendation:** This is intentional if you don't want AI engines using this page. If you DO want AI citation, remove the AI-bot-specific directive.

**Plain-English:** AI Bot Blocked

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag) (vendor)

> X-Robots-Tag directives can be addressed to a named user agent, applying to that crawler only.

---

### AI_PREVIEW_SUPPRESSED
**Severity:** 🟡 warning | **Confidence:** Established | **Impact:** 4 | **Effort:** 1

An X-Robots-Tag response header suppresses this page's search/AI preview (nosnippet or max-snippet:0)

**Recommendation:** If you want this page to be eligible for AI Overviews and citations, remove the nosnippet / max-snippet:0 directive from the X-Robots-Tag header (often set in server config or an SEO plugin).

**Plain-English:** AI Preview Suppressed

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag) (vendor)

> Google documents nosnippet and max-snippet in the X-Robots-Tag header as suppressing the text preview for a page.

---

### AI_TXT_MISSING
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 1

No /ai.txt file found at site root

**Recommendation:** Consider creating /ai.txt to declare AI usage policies and content permissions. Emerging convention; no confirmed AI engine support yet.

**Plain-English:** No ai.txt File

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and weak. ai.txt is one of several competing proposals for declaring AI usage preferences, adopted by no major engine. Reported for completeness and scored near zero; robots.txt is the mechanism that actually works today.

---

### AUTHOR_BYLINE_MISSING
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Blog or article page has no author byline, rel=author, or JSON-LD author field

**Recommendation:** Add an author byline with name and optionally credentials. Include rel='author' on the author link and an 'author' field in your JSON-LD BlogPosting schema.

**Plain-English:** No Author Attribution

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) (vendor)

> Google's guidance asks who wrote the content and whether the site makes authorship clear.

---

### AUTHOR_CREDENTIALS_MISSING
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

**What it is**
A bare author name (no title, bio, or profile link) tells AI who wrote the page but nothing about why they're credible.

**Why it matters**
Expertise and authority signals help AI and search decide whom to trust and cite. A name alone is a weak signal.

**How to fix**
Add jobTitle / description / sameAs / url to the author Person in your JSON-LD.

**Plain-English:** Author Credentials Missing

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. Google's helpful-content guidance discusses expertise but publishes no credential requirement and no way to verify one. That a byline carries no stated credential is an observation about the page, not a measure of the author.

---

### AUTHOR_IDENTITY_INCONSISTENT
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

**What it is**
Article schema names the author. Conflicting name↔URL pairings make it unclear whether pages share one author.

**Why it matters**
Fragmented author identity weakens the expertise/authority signals AI uses to trust and attribute content.

**How to fix**
Use one canonical author name + profile URL across all articles.

**Plain-English:** Inconsistent Author Identity

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. The same person named differently across a site gives a consumer no single identity to resolve. Name variants are often legitimate.

---

### BLOG_SECTIONS_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Blog or article page lacks sufficient heading structure for AI citation anchors

**Recommendation:** Add H2/H3 headings to break content into named sections. AI engines use headings as citation anchors — a long post with fewer than 3 headings cannot be accurately quoted or cited by AI.

**Plain-English:** No Section Headings for AI Citation

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. A long article with almost no headings offers no structure to navigate or excerpt by. The section count that triggers this is ours.

---

### BOILERPLATE_RATIO_HIGH
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

**What it is**
The share of this page's text that also appears across many other pages (nav, footer, repeated CTAs) is high relative to its unique content.

**Why it matters**
Template-heavy pages have low citability and are prime AI-replacement targets.

**How to fix**
Expand the page with original, page-specific substance.

**Plain-English:** Mostly Boilerplate

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the ratio is ours. When most of a page's text is the same header, footer and sidebar found sitewide, little of the page is about its own subject. Correct and unavoidable on short pages.

---

### CENTRAL_CLAIM_BURIED
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 3 | **Fixability:** content_edit

The page's main claim or answer does not appear in the first 150 words

**Recommendation:** State the central point in the opening paragraph. AI systems weight early content more heavily when deciding what to extract and cite.

**Plain-English:** Main Point Buried

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, made by a language model over the page's opening (roughly the first thousand words; there is no fixed word window). No engine operator publishes anything about where an answer should sit. The reasoning is that a summariser reading a truncated page sees the opening first — plausible, unconfirmed.

---

### CHUNKS_NOT_SELF_CONTAINED
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 4 | **Fixability:** content_edit

More than half of the page's H2/H3 sections are not understandable in isolation

**Recommendation:** Each section should open with a context sentence that restates the subject. AI retrieval systems serve individual chunks, not whole pages.

**Plain-English:** Sections Lack Context

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the half-of-sections threshold is ours. Retrieval systems commonly index passages rather than pages, so a section that only makes sense after the one above it may be retrieved without its context. How any given engine chunks a page is not published.

---

### CITATIONS_MISSING_SUBSTANTIAL_CONTENT
**Severity:** 🔵 info | **Tier:** high | **Confidence:** Heuristic | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

Page has 200+ words but no citations or source attribution

**Recommendation:** Add citations to factual claims. Use inline references or a Sources section.

**Plain-English:** Missing Citations

**Basis:** published source — [Aggarwal et al., GEO: Generative Engine Optimization (KDD 2024)](https://arxiv.org/abs/2311.09735) (research)

> Adding cited sources was among the interventions that raised visibility in the study's generative engines.

**What the source does not say:** The 200-word trigger is ours. Plenty of legitimate pages cite nothing.

---

### CITATIONS_ORPHANED
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 1 | **Fixability:** content_edit

Page has citations without surrounding context

**Recommendation:** Ensure each citation appears within a sentence that explains its relevance.

**Plain-English:** Citations Without Context

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. A citation with no surrounding sentence explaining what it supports cannot be evaluated by a reader or summarised faithfully. No source states this.

---

### CITATIONS_SOURCES_INACCESSIBLE
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 3 | **Fixability:** content_edit

Page cites sources that are broken or inaccessible

**Recommendation:** Replace broken citation links with working alternatives.

**Plain-English:** Inaccessible Citation Sources

**Basis:** published source — [IETF RFC 9110](https://www.rfc-editor.org/rfc/rfc9110) (standard)

> A cited URL returning 4xx or 5xx cannot be retrieved, so the citation cannot be checked by anyone following it.

---

### CODE_BLOCK_MISSING_TECHNICAL
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

Technical how-to/guide page with numbered steps has no <pre> or <code> blocks

**Recommendation:** Wrap command-line examples, code snippets, and configuration in <code> or <pre> tags. This makes them unambiguously extractable by AI systems.

**Plain-English:** No Code Blocks in Technical Guide

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. Numbered technical steps with no code or preformatted block often mean commands are inline in prose, where they are easy to mistranscribe. Not every technical guide involves code.

---

### COMPARISON_TABLE_MISSING
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

Page contains comparison language ('vs', 'versus', 'compared to') but no table

**Recommendation:** Add a structured comparison table. Tables are the most extractable format for comparisons — AI systems can read them as structured data.

**Plain-English:** Comparison Without Table

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. A page using comparison language without a table leaves the comparison implicit. Detected from phrasing, so it will flag pages where "versus" was incidental.

---

### CONTACT_INFO_NOT_IN_HTML
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

**What it is**
Contact information that exists on the page only as an image (e.g. a phone number in a banner graphic) or that is inserted by client-side JavaScript is invisible to anything reading the raw HTML.

**Why it matters**
When an AI assistant is asked 'how do I contact this organisation?', it can only answer from text it can read. Image- or JS-only contact details are missed, so the agent cannot surface your phone, email, or address.

**How to fix**
Render contact details as plain HTML text in the footer or a contact block. Optionally add ContactPoint / PostalAddress schema to reinforce them.

**Plain-English:** Contact Info Not in Text

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 1.1.1)](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content) (standard)

> Contact details rendered only as an image or injected by script are not present as text for any reader of the served page.

---

### CONTENT_CLOAKING_DETECTED
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 6 | **Effort:** 4

Rendered content appears to shift the page's topic versus raw HTML — possible cloaking

**Recommendation:** Ensure raw HTML and rendered content describe the same topic. Serving different content to AI crawlers than to users violates search quality guidelines.

**Plain-English:** Possible Content Cloaking

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/essentials/spam-policies) (vendor)

> Google defines cloaking as presenting different content to users and search engines, and treats it as a policy violation.

**What the source does not say:** TalkingToad detects a topic shift between raw and rendered content. That is a signal, not a finding of intent, and a common cause is a personalisation script rather than deception.

---

### CONTENT_DATE_STALE_VISIBLE
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Reasonable proxy | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Visible/declared modified date is old enough to read as stale for its page type

**Recommendation:** Review the content for accuracy and update the visible date if the information is still current. For evergreen content, consider removing the date entirely or adding a note that it has been reviewed.

**Plain-English:** Stale Visible Date

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the staleness window is ours. A visible date that reads as old undermines a reader's confidence in time-sensitive content. Age is not error, and much content is correct indefinitely.

---

### CONTENT_IMAGE_HEAVY
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 3 | **Fixability:** content_edit

Page has significantly more images than text sections

**Recommendation:** Add descriptive captions and surrounding text for each image. AI systems rely on text context to interpret visual content.

**Plain-English:** Image-Heavy Layout

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. A page carrying far more images than text sections may hold its meaning in pictures, which a text reader cannot see. Entirely correct for a gallery.

---

### CONTENT_NOT_EXTRACTABLE_NO_TEXT
**Severity:** 🔴 critical | **Confidence:** Established | **Impact:** 9 | **Effort:** 4 | **Fixability:** content_edit

Page has no visible text — only images, video, or interactive media

**Recommendation:** Add descriptive text, captions, or transcripts. AI systems cannot extract information from images or videos without accompanying text.

**Plain-English:** No Text Content

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 1.1.1)](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content) (standard)

> Content carried only as images or media has no text equivalent, so anything consuming text — assistive technology or a crawler — receives nothing.

---

### CONTENT_STAT_OUTDATED
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 1 | **Fixability:** content_edit

Body text references a year that is ≥24 months old without mentioning the current year.

**Recommendation:** Update the statistic or reference to the current year, or add context that acknowledges the original year while explaining continued relevance.

**Plain-English:** Outdated Year Reference

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 24-month window is ours. A bare old year in body text may be a stale statistic or may be a historical reference, which TalkingToad cannot reliably tell apart.

---

### CONTENT_THIN
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 3 | **Fixability:** content_edit

Page has very little text (under 100 words)

**Recommendation:** Expand the page with substantive content. Thin pages provide insufficient context for AI systems to generate accurate summaries.

**Plain-English:** Thin Content

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) (vendor)

> Google advises content offer substantial value rather than little of substance.

**What the source does not say:** The 100-word figure is ours. Google publishes no word count and states there is no minimum. A contact page can be complete at 40 words.

---

### CONTENT_UNSTRUCTURED
**Severity:** 🔵 info | **Tier:** high | **Confidence:** Reasonable proxy | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

Page has substantial text but no heading structure

**Recommendation:** Add H2 and H3 headings to break content into sections. Headings help AI systems identify topics and extract structured information.

**Plain-English:** No Heading Structure

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 1.3.1)](https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships) (standard)

> Structure conveyed visually must be programmatically determinable; substantial text with no headings exposes no structure at all.

---

### CONVERSATIONAL_H2_MISSING
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

H2 headings do not use conversational interrogatives (How, What, Why)

**Recommendation:** Rewrite some H2 headings as questions. LLMs prefer direct question-answer pairings for more accurate retrieval and citing.

**Plain-English:** Non-Conversational Headings

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and a contested one. Phrasing headings as questions is common advice for AI search and no operator has confirmed it helps. Scored low deliberately, because writing every heading as a question makes for worse pages.

---

### DATE_MODIFIED_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Reasonable proxy | **Impact:** 2 | **Effort:** 1

Blog or article page has no last-modified date in JSON-LD

**Recommendation:** Add dateModified to your JSON-LD schema to signal content freshness to AI systems.

**Plain-English:** Missing Last-Modified Date

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/publication-dates) (vendor)

> Google documents dateModified as the declared signal for when content last changed.

---

### DATE_PUBLISHED_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Reasonable proxy | **Impact:** 2 | **Effort:** 1

Blog or article page has no publication date in JSON-LD or meta tags

**Recommendation:** Add datePublished to your JSON-LD schema and/or <meta property='article:published_time'>.

**Plain-English:** Missing Publication Date

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/publication-dates) (vendor)

> Google documents how it determines a page's publication date and recommends stating it explicitly in structured data and visibly on the page.

---

### DOCUMENT_PROPS_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Established | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

PDF is missing internal Title or Subject metadata

**Recommendation:** Update PDF document properties to include a clear Title and Subject. AIs use these properties for source labels and citations.

**Plain-English:** Missing Document Info

**Basis:** published source — [W3C WAI (WCAG 2.2 technique PDF18)](https://www.w3.org/WAI/WCAG22/Techniques/pdf/PDF18) (standard)

> W3C documents setting a PDF's document-properties Title as the technique that gives the file a name assistive technology and other consumers can read.

---

### ENTITY_FIELD_EMPTY
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Established | **Impact:** 2 | **Effort:** 1

**What it is**
A field like telephone published as an empty list. The markup claims the property exists while carrying nothing, so consumers see a broken value rather than an absent one.

**Why it matters**
An empty value can be worse than an absent one: it satisfies presence checks while giving nothing usable, and it is a reliable sign the settings screen was left half-finished.

**How to fix**
Enter the value in your SEO plugin settings. The field is already configured to be published, so this is a settings edit rather than a decision.

**Plain-English:** Empty Entity Field

**Basis:** published source — [schema.org](https://schema.org/docs/gs.html) (standard)

> A declared property carrying no value states nothing, while appearing in the markup as though it does.

---

### ENTITY_HOURS_DEFAULT
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 1

**What it is**
Local SEO plugins pre-fill opening hours with 9:00-17:00 for all seven days. If nobody changes them, those invented hours are published to search engines as verified fact.

**Why it matters**
Unlike a missing field, this actively asserts something false. It can send someone to a closed door, and it undermines the entity data around it.

**How to fix**
In your SEO plugin's Local SEO settings, either enter the verified opening hours or disable opening-hours output. If the address is an administrative office with no public hours, disable it.

**Plain-English:** Default Opening Hours Published

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. Identical hours on all seven days at an SEO plugin's default value is more often an untouched default than a real schedule. Some organisations genuinely do open the same hours daily, so this is reported, not asserted.

---

### ENTITY_NAME_INCONSISTENT
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

**What it is**
Your Organization schema states your name. When different pages state it differently, machines can't be sure they describe one organisation.

**Why it matters**
AI systems build one entity profile per name. Split names dilute the brand signal that makes you 'the one people search for by name'.

**How to fix**
Standardise Organization.name across all pages/templates to a single spelling.

**Plain-English:** Inconsistent Organisation Name

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. Different organisation names across a site's own structured data give a consumer no single identity to resolve to. Legitimate for a site covering several entities.

---

### ENTITY_NAP_INCOMPLETE
**Severity:** 🟡 warning | **Confidence:** Established | **Impact:** 6 | **Effort:** 2

**What it is**
Structured data declares what kind of entity you are. Declaring a physical location commits you to an address, a phone number and contact details; leaving them out leaves the entity unresolvable.

**Why it matters**
Search engines and AI assistants use these fields to connect your site to a real organisation. Missing fields weaken local visibility, knowledge-panel eligibility and citation confidence.

**How to fix**
Fill in the listed fields in your SEO plugin's Site Representation and Local SEO settings, using the same values shown in your footer and contact page. If you have no customer-facing premises, change the type instead of inventing an address.

**Plain-English:** Incomplete Organization Details

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/structured-data/local-business) (vendor)

> Google documents the identity fields — name, address, telephone — that identify a local business.

---

### ENTITY_SAMEAS_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Reasonable proxy | **Impact:** 2 | **Effort:** 1 | **Fixability:** content_edit

**What it is**
sameAs links connect your entity to authoritative references, letting AI confidently disambiguate and cite your organisation.

**Why it matters**
Without sameAs, there is no explicit link to the knowledge graph, weakening entity resolution and citation confidence.

**How to fix**
Add sameAs URLs to the Organization/Person JSON-LD block.

**Plain-English:** No sameAs Entity Links

**Basis:** published source — [schema.org](https://schema.org/sameAs) (standard)

> sameAs links an entity to its authoritative pages elsewhere, which is how a consumer disambiguates one organisation from a similarly named one.

---

### ENTITY_VALUE_PLACEHOLDER
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Reasonable proxy | **Impact:** 2 | **Effort:** 1

**What it is**
Values like "site logo", "Just another WordPress site", or a one-word description that a theme or plugin left behind and nobody replaced.

**Why it matters**
These fields feed the site's entity description in search and AI answers. A placeholder there is published as your official description of yourself.

**How to fix**
Edit the field in your SEO plugin's Site Representation settings and write the real value. Check the site description, organisation name and legal name together, as they are usually set on the same screen.

**Plain-English:** Placeholder Value in Structured Data

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. A field carrying a template default ("Your Business Name", "123 Main St") is worse than an absent field, because it asserts something false. The list of placeholder values is editorial and may miss cases.

---

### EXTERNAL_CITATIONS_LOW
**Severity:** 🔵 info | **Tier:** high | **Confidence:** Heuristic | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

500+ word page has no outbound links to external authoritative sources in body text

**Recommendation:** Add links to authoritative external sources (.gov, .edu, research papers, official docs). Aggarwal et al. (2023) found citations measurably increase AI engine quotability.

**Plain-English:** No External Citations

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 500-word trigger is ours. A long page linking to no external source gives a reader nothing to corroborate it against. Original reporting and primary material legitimately cite nothing.

---

### FAQ_ANSWERS_NOT_IN_HTML
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 3

FAQ questions are in the HTML but their answers are not — the answer text only appears after a JavaScript click, so AI crawlers (which don't click) can't read it

**Recommendation:** Serve FAQ answer text in the page's HTML source, not injected on click. Use a native accordion block (or an accordion plugin) that outputs the answer text directly to the source, so AI systems and search engines can read every answer.

**Plain-English:** FAQ Answers Hidden From AI

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics) (vendor)

> Answer text revealed only on interaction or injected by script is absent from the served HTML.

---

### FAQ_SCHEMA_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Established | **Impact:** 2 | **Effort:** 2

Page has an FAQ section but no FAQPage JSON-LD schema

**Recommendation:** Add FAQPage schema to your FAQ section so AI systems can extract Q&A pairs directly.

**Plain-English:** FAQ Without Schema

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/structured-data/faqpage) (vendor)

> Google documents FAQPage markup as the way to declare question-and-answer content explicitly.

**What the source does not say:** Google restricted FAQ rich results in 2023. The markup still states the structure unambiguously, which is the basis for reporting it — not a promise of a rich result.

---

### FIRST_VIEWPORT_NO_ANSWER
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

First 200 words contain no direct answer signal (definition, TL;DR, summary phrase)

**Recommendation:** Lead with a concise definition or summary ('X is...', 'In short...', 'Key takeaway:'). AI systems read top-to-bottom; putting the answer in the first 200 words maximises the chance it is retrieved and cited.

**Plain-English:** No Lead Answer

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 200-word window is ours. It detects the absence of an answer-shaped signal, which is a crude proxy for whether the page actually answers anything.

---

### GEO_SUMMARY_BURIED
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 3 | **Fixability:** content_edit

The first paragraph or list does not lead its H2 or H3 section — the core answer is pushed below images, media, or preamble

**Recommendation:** Reorder each H2/H3 section so the core answer leads in 1–2 sentences, with supporting content following. AI retrievers and skimming humans both miss answers that aren't immediately under the heading.

**Plain-English:** Answer Buried Under H2/H3

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. A section whose opening sentence does not lead the section is harder to excerpt. No source states this.

---

### HOWTO_SCHEMA_INCOMPLETE
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2

**What it is**
HowTo schema describes a step-by-step procedure. Without a step array it announces a how-to but gives machines nothing to extract.

**Why it matters**
AI answers and assistants reproduce procedures from structured steps. An empty HowTo block wastes the signal.

**How to fix**
Populate the HowTo `step` array in your structured data.

**Plain-English:** Incomplete HowTo Schema

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/structured-data/how-to) (vendor)

> Google documents the required properties of HowTo markup; an incomplete block does not describe the procedure.

**What the source does not say:** Google retired HowTo rich results in 2023. Reported for structural clarity only.

---

### JSON_LD_INVALID
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2

A JSON-LD block is present but missing @type or @context (invalid schema)

**Recommendation:** Ensure every JSON-LD block includes both @type and @context fields. Malformed schema blocks are ignored by search engines and AI parsers.

**Plain-English:** Invalid JSON-LD Schema

**Basis:** published source — [schema.org](https://schema.org/docs/gs.html) (standard)

> A JSON-LD block without @context and @type declares no vocabulary or type, so no consumer can interpret it.

---

### JSON_LD_MISSING
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2

No JSON-LD structured data found on this indexable page

**Recommendation:** Add <script type="application/ld+json"> markup. Schema is the 'knowledge graph' used by AI systems for RAG-based answers.

**Plain-English:** Missing AI Schema

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data) (vendor)

> Structured data is Google's documented mechanism for stating explicitly what a page is about.

**What the source does not say:** Structured data is not required for indexing. Reported as an opportunity, not a fault.

---

### JS_RENDERED_CONTENT_DIFFERS
**Severity:** 🟡 warning | **Confidence:** Established | **Impact:** 6 | **Effort:** 4

Rendered page contains substantially more content than raw HTML (>20% more tokens)

**Recommendation:** Pre-render key content as HTML so AI crawlers can access it without JavaScript. Consider server-side rendering or static generation for important pages.

**Plain-English:** JS-Gated Content

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics) (vendor)

> Google documents a two-phase crawl in which rendered content is processed later than the served HTML.

**What the source does not say:** The 20% token-difference trigger is ours. Google documents the two-phase crawl but publishes no threshold at which a difference matters.

---

### LINK_PROFILE_PROMOTIONAL
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

Over 80% of outbound body-text links point to the same organisation's own domains

**Recommendation:** Add external citations to authoritative third-party sources. An all-internal link profile signals low authority to AI systems.

**Plain-English:** All-Internal Link Profile

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 80% figure is ours. Outbound links that nearly all point to one organisation read as promotion rather than reference. Entirely legitimate for a site documenting its own work.

---

### LLMS_TXT_INVALID
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

/llms.txt format is invalid

**Recommendation:** Per llmstxt.org, the only required element is a Markdown '# Title' H1 heading; a '>' summary and '## Section' link lists are optional and there is no URL cap. Make sure the file is served as Markdown/plain text and isn't returning a normal web page (soft 404).

**Plain-English:** Invalid AI Instruction File

**Basis:** published source — [llmstxt.org](https://llmstxt.org/) (industry)

> The proposal defines the file's expected structure, against which a malformed file can be identified.

---

### LLMS_TXT_MISSING
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 1 | **Fixability:** content_edit

No llms.txt found at root

**Recommendation:** Create an /llms.txt file to help LLMs and AI agents (Gemini, Perplexity) accurately crawl and cite your high-value content.

**Plain-English:** Missing AI Instruction File

**Basis:** published source — [llmstxt.org](https://llmstxt.org/) (industry)

> llms.txt is a published proposal for a root file describing a site's content to language models.

**What the source does not say:** A proposal, not a standard. No engine operator has committed to reading it, so absence is reported as an option, not a defect.

---

### NEAR_DUPLICATE_BODY
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 3 | **Fixability:** content_edit

**What it is**
A comparison of each page's lead content (first ~1500 words, boilerplate stripped) found pages that are near-identical to each other.

**Why it matters**
Generic, repeated content is the most 'absorbable' by AI answers — if many pages say the same thing, one paragraph can replace them all.

**How to fix**
Merge or meaningfully differentiate the flagged pages.

**Plain-English:** Near-Duplicate Page Content

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) (vendor)

> Google consolidates pages it judges duplicates and indexes one of them, so the others may not appear separately.

**What the source does not say:** The similarity threshold is ours, measured after removing shared template text. Near-duplicate lead paragraphs are normal across a service-area set.

---

### ORPHAN_CLAIM_TECHNICAL
**Severity:** 🔵 info | **Tier:** high | **Confidence:** Heuristic | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

Technical/how-to page has 3+ factual claims not paired with a source link or attribution

**Recommendation:** Add a source link or attribution ('according to [source]') next to each specific capability claim, number, or procedure step.

**Plain-English:** Unsourced Technical Claims

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 3-claim trigger is ours. Detecting an unsupported factual claim is a language judgement TalkingToad makes approximately, and it will both miss claims and flag supported ones.

---

### PRODUCT_REVIEW_SCHEMA_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Reasonable proxy | **Impact:** 2 | **Effort:** 2

**What it is**
Product schema can carry reviews and an aggregate rating. Without them the product is described but never rated in machine-readable form.

**Why it matters**
Review stars in search and AI trust signals both come from rating markup; a Product block without it leaves that on the table.

**How to fix**
Add review / aggregateRating to the Product JSON-LD (only with real ratings).

**Plain-English:** Product Missing Review Schema

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/structured-data/product) (vendor)

> Google documents review and aggregateRating as the properties that carry rating information for a product.

---

### PROMOTIONAL_CONTENT_INTERRUPTS
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 3 | **Fixability:** content_edit

Mid-article sections classified as promotional interrupt the content flow

**Recommendation:** Move promotional or sales content to the end or to a sidebar. AI systems may de-weight or skip sections they identify as promotional.

**Plain-English:** Promotional Content in Article

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. Promotional blocks between body sections interrupt the argument and may be excerpted as though they were part of it. Classifying a section as promotional is a language judgement that will misfire.

---

### QUERY_COVERAGE_WEAK
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Page H1 topic terms are under-represented in the intro or section headings — AI retrieval systems may not associate this page with its target query

**Recommendation:** Ensure the language from your H1 (the page's primary topic) appears naturally in the first 200 words and in at least one H2 section heading. AI systems score pages by query–content similarity; if your topic terms don't appear where they look first, the page may be skipped.

**Plain-English:** Weak Query Coverage

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. If the H1's topic terms barely appear in the body, the page may not cover what it announces. A term-overlap proxy, easily fooled by synonyms and by good writing that avoids repetition.

---

### QUOTATIONS_MISSING
**Severity:** 🔵 info | **Tier:** high | **Confidence:** Heuristic | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

500+ word page contains no direct quotations from named sources

**Recommendation:** Add quoted statements from named experts or sources. Use <blockquote> for longer quotes. Aggarwal et al. (2023) found quotations measurably increase AI citation rates.

**Plain-English:** No Expert Quotations

**Basis:** published source — [Aggarwal et al., GEO: Generative Engine Optimization (KDD 2024)](https://arxiv.org/abs/2311.09735) (research)

> Adding quotations from named sources was among the interventions that raised visibility in the study's generative engines.

**What the source does not say:** The 500-word trigger is ours, and the finding is one study on a research corpus, not a vendor statement.

---

### RAW_HTML_JS_DEPENDENT
**Severity:** 🔴 critical | **Confidence:** Established | **Impact:** 9 | **Effort:** 3

Page raw HTML is a JavaScript app shell with near-zero visible text

**Recommendation:** Render critical content server-side (SSR) or as static HTML. AI crawlers may not execute JavaScript, so JS-gated content is invisible to them.

**Plain-English:** JS-Only Content (No SSR)

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics) (vendor)

> Content present only after JavaScript execution is not in the served HTML, and rendering is a deferred second pass.

---

### SCHEMA_DEPRECATED_TYPE
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Established | **Impact:** 2 | **Effort:** 1 | **Fixability:** content_edit

Page uses deprecated schema.org types

**Recommendation:** Replace deprecated schema types with modern equivalents from schema.org.

**Plain-English:** Deprecated Schema Type

**Basis:** published source — [schema.org](https://schema.org/docs/gs.html) (standard)

> schema.org marks superseded types; a consumer is under no obligation to interpret one.

---

### SCHEMA_ORG_MISSING
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2 | **Fixability:** wp_fixable

**What it is**
Organization schema is the structured-data block that states who you are — name, logo, URL, social profiles, contact points. On the homepage it anchors your entire site's identity in the knowledge graph.

**Why it matters**
AI systems build an entity profile of your organisation from Organization schema. Without it, they must infer your identity from prose, which is less reliable and weakens your chance of being correctly named and cited.

**How to fix**
Add a <script type="application/ld+json"> Organization block to your homepage (TalkingToad's Entity Schema Factory can generate one), or enable Organization schema in your SEO plugin.

**Plain-English:** No Organization Schema

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/structured-data/organization) (vendor)

> Google documents Organization structured data as how a site states its identity, logo and contact details.

---

### SCHEMA_TYPE_CONFLICT
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Reasonable proxy | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Page declares multiple conflicting schema types

**Recommendation:** Use a single coherent @type. For multiple entities use @graph or nesting.

**Plain-English:** Conflicting Schema Types

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/structured-data/sd-policies) (vendor)

> Contradictory type declarations leave a consumer no basis for choosing between them.

---

### SCHEMA_TYPE_MISMATCH
**Severity:** 🔵 info | **Tier:** medium | **Confidence:** Reasonable proxy | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Page schema type does not match inferred page type

**Recommendation:** Ensure JSON-LD @type matches the page content (Article for blog posts, Person for team bios, Service for service pages).

**Plain-English:** Mismatched Schema Type

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/structured-data/sd-policies) (vendor)

> Google's structured-data policies require markup to describe the page it is on.

**What the source does not say:** TalkingToad infers the page type from its content. The inference can be wrong, so this is reported rather than asserted.

---

### SCHEMA_VISIBLE_MISMATCH
**Severity:** 🟡 warning | **Confidence:** Established | **Impact:** 6 | **Effort:** 2 | **Fixability:** content_edit

A value declared in JSON-LD structured data does not appear in the page's visible text

**How to fix**
For each field listed below, compare the schema value with the page. If the value is correct but missing from the page, add it to the visible content (heading, paragraph, FAQ, or address block). If the page is correct, update the JSON-LD in your SEO plugin so its value matches the visible text.

**Plain-English:** Schema Not in Visible Text

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/appearance/structured-data/sd-policies) (vendor)

> Google requires structured data to reflect content visible on the page; markup asserting what the page does not say is a policy violation.

---

### SECTION_CROSS_REFERENCES
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

Page contains backward-reference phrases ('as mentioned above', 'as discussed earlier') that break section independence

**Recommendation:** Remove or replace phrases like 'as mentioned above' with the actual information being referenced. AI systems cite individual passages in isolation — a passage that refers to earlier content cannot be understood or quoted on its own.

**Plain-English:** Section Back-References

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. "As mentioned above" breaks when a passage is read on its own. Perfectly good prose for a reader going top to bottom, which is why this is scored low.

---

### SECTION_VAGUE_OPENER
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

One or more H2/H3 sections begin with a vague demonstrative reference ('This method…', 'It allows…', 'These features…') instead of an explicit subject

**Recommendation:** Replace vague openers with explicit nouns: instead of 'This approach improves…' write 'RAG retrieval improves…'. Each section must make sense in isolation — AI systems extract sections as independent passages and cannot infer context.

**Plain-English:** Vague Section Openers

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. A section opening on "this" or "these" with no antecedent in the section reads as incomplete when excerpted. A writing observation.

---

### SEMANTIC_DENSITY_LOW
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 3

Text-to-HTML ratio is below 10%

**Recommendation:** Clean up excessive code-bloat (styles, scripts, nested divs). High code-to-text ratios consume more AI tokens and confuse retrieval engines.

**Plain-English:** High Code-to-Text Ratio

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and the 10% figure is ours. Text-to-HTML ratio is a crude proxy for markup bloat that penalises pages built by any modern page builder regardless of their content. Scored low for that reason.

---

### STATISTICS_COUNT_LOW
**Severity:** 🔵 info | **Tier:** high | **Confidence:** Heuristic | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

500+ word page contains no statistics (numbers paired with units, percentages, or dates)

**Recommendation:** Add specific data points: percentages, measurements, dates, counts. Aggarwal et al. (2023) found statistics measurably increase citation by generative engines.

**Plain-English:** No Statistics

**Basis:** published source — [Aggarwal et al., GEO: Generative Engine Optimization (KDD 2024)](https://arxiv.org/abs/2311.09735) (research)

> Adding statistics to source content measurably raised its visibility in the generative engines the study tested.

**What the source does not say:** The 500-word trigger is ours. The study tested a research corpus, not this site, and no engine operator has confirmed the effect.

---

### STRUCTURED_ELEMENTS_LOW
**Severity:** 🔵 info | **Tier:** low | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 2 | **Fixability:** content_edit

Page has very few structured elements (lists, tables, code blocks) relative to content length

**Recommendation:** Add bullet lists, numbered lists, or tables to break up prose. Structured elements are more reliably extracted by AI chunkers than continuous paragraphs.

**Plain-English:** Low Structured Element Count

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. Lists, tables and code blocks mark structure explicitly where a paragraph only implies it. The count that triggers this is ours, and plenty of good pages are pure prose.

---

### UA_CONTENT_DIFFERS
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 6 | **Effort:** 3

AI crawler user agents (GPTBot, ClaudeBot) receive substantially less content than a browser

**Recommendation:** Ensure AI crawler requests receive the same content as regular browsers. Serving stripped content to AI bots prevents citation and indexing.

**Plain-English:** AI Bot Content Stripping

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/essentials/spam-policies) (vendor)

> Serving different content to a crawler than to a user is cloaking, which Google's spam policies prohibit.

**What the source does not say:** The 20% token-difference trigger is ours. Google's spam policies define cloaking but set no measured threshold, and a smaller difference can still be deliberate.

---

<a id="analytics"></a>
## ANALYTICS

_7 codes in this category._

### ANALYTICS_ID_INCONSISTENT
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 2

**What it is**
Different pages report to different GA4/GTM IDs, or the tag is present on some pages and absent on others — a sign the tag was added page-by-page instead of site-wide.

**Why it matters**
Traffic is split across properties or lost entirely, so no single report reflects the whole site and trends look broken.

**How to fix**
Move the tag into the site-wide header/footer template with a single measurement ID, remove per-page copies, and re-crawl to confirm one consistent ID everywhere.

**Plain-English:** Inconsistent Analytics ID

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. Different measurement IDs across pages of one site usually means a partial migration, splitting the data between properties. A deliberate multi-property setup is legitimate, so this is reported, not asserted.

---

### ANALYTICS_TAG_DUPLICATE
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 1

**What it is**
Two analytics installations were found on one page: for example a GA4 tag added by a plugin AND a Google Tag Manager container that also loads GA4.

**Why it matters**
Double-tagging inflates pageviews and sessions and roughly halves your reported engagement and conversion rates, so every decision made from the data is wrong.

**How to fix**
Pick one delivery path for GA4 (usually GTM) and remove the other. Re-crawl to confirm a single tag remains. This is a heuristic from the page markup — verify in GA4 DebugView or Tag Assistant before removing anything.

**Plain-English:** Duplicate Analytics Tag

**Basis:** published source — [Google Analytics Help](https://support.google.com/analytics/answer/9304153) (vendor)

> Google documents one GA4 tag per page; a second copy double-counts pageviews and events.

---

### ANALYTICS_TAG_MISSING
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 1

**What it is**
This page carries no Google Analytics 4 tag and no Google Tag Manager container, so visits to it are not being recorded.

**Why it matters**
You are flying blind on this page: no sessions, no engagement, no conversions. If it's a donation or contact page, you can't tell whether it works. Pages missing the tag also skew site-wide totals downward.

**How to fix**
Ensure the GA4 tag (or the GTM container that loads it) is present in the shared header/footer template so it appears on every page, then re-crawl to confirm. Detection is markup-only — it confirms the tag is on the page, not that it fires.

**Plain-English:** No Analytics Tag

**Basis:** TalkingToad's own judgement. No published source states this.

> Not an SEO claim at all. It reports that no GA4 or Tag Manager snippet was found, so the organisation cannot see what this page does. Whether to install analytics is the site owner's decision.

---

### CONSENT_MODE_MISSING
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 3

**What it is**
The page loads GA4/GTM but shows no Consent Mode v2 configuration, which is how Google expects analytics to respect a visitor's cookie choice in regulated regions.

**Why it matters**
Without Consent Mode, analytics may collect data before consent (a privacy/GDPR risk for EU/UK visitors) or, if a banner blocks the tag outright, you lose data from everyone who doesn't accept.

**How to fix**
If you serve EU/UK visitors, set up Consent Mode v2 in GTM alongside your consent banner (advisory — this is a heuristic markup check, not legal advice).

**Plain-English:** Consent Mode Not Detected

**Basis:** published source — [Google Analytics Help](https://support.google.com/analytics/answer/9976101) (vendor)

> Google documents Consent Mode as the mechanism for adjusting tag behaviour according to user consent.

**What the source does not say:** Whether consent signalling is legally required depends on jurisdiction. TalkingToad does not give legal advice and does not assert a requirement.

---

### CTA_TRACKING_MISSING
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 1 | **Fixability:** content_edit

**What it is**
GA4 doesn't measure internal button clicks on its own. This page uses a click-tracking convention on some buttons, but a conversion CTA is missing it.

**Why it matters**
If a Donate / Book / Contact button isn't instrumented, you can't see how many people clicked it — the conversion you most need to measure is invisible.

**How to fix**
Add the same click-tracking marker your other buttons use (the class or data-* attribute your GA4 event listener reads) to the untagged conversion buttons. If you track via Google Tag Manager, add a click trigger for them there instead. Verify in GA4 DebugView that the event fires.

**Plain-English:** Conversion Button Not Tracked

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement, and it depends on a convention we infer from the site's own markup&#58; if some buttons are tagged for click tracking and comparable ones are not, the untagged ones are probably an oversight. Silent when no convention is detectable, because then there is nothing to be inconsistent with.

---

### OUTBOUND_LINK_UNTRACKABLE
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 1 | **Fixability:** content_edit

**What it is**
An external link whose only content is an image or icon — it has no visible text, aria-label, or title. GA4 records the click but with an empty link label.

**Why it matters**
You can see that people leave for external sites but not WHICH link they used, so you can't measure partner referrals, donation-processor handoffs, or social links.

**How to fix**
Add an aria-label (or descriptive alt text on the image) to the link so it has an identifiable label in GA4's outbound-click events.

**Plain-English:** Untrackable Outbound Link

**Basis:** TalkingToad's own judgement. No published source states this.

> Our judgement. An image-or-icon-only external link gives analytics no label to report, so its clicks are unattributable in reports. A usability and measurement observation, not a standard.

---

### SELF_REFERENCING_UTM
**Severity:** 🔵 info | **Tier:** medium | **Impact:** 2 | **Effort:** 1 | **Fixability:** content_edit

**What it is**
A link to another page on your own site carries UTM campaign tags (e.g. ?utm_source=…). UTMs are meant for links coming FROM other sites, not internal ones.

**Why it matters**
Clicking an internal UTM'd link restarts the GA4 session and reattributes the visitor to that fake campaign, so your real traffic sources (organic, referral) are under-counted and self-referrals pollute reports.

**How to fix**
Edit the link to point to the clean internal URL with no utm_* parameters. Reserve UTMs for external campaigns (emails, ads, social posts).

**Plain-English:** Self-Referencing Campaign Link

**Basis:** published source — [Google Analytics Help](https://support.google.com/analytics/answer/10917952) (vendor)

> UTM campaign parameters start a new session attributed to that campaign; using them on internal links restarts attribution mid-visit.

---

<a id="rendering"></a>
## RENDERING

_4 codes in this category._

### CWV_CLS_POOR
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2

**What it is**
Cumulative Layout Shift is one of Google's Core Web Vitals. This figure is the 75th percentile across real Chrome users over the last 28 days - not a synthetic test - so it reflects what visitors actually experience.

**Why it matters**
Core Web Vitals are a confirmed Google ranking input, and content that jumps as it loads makes people tap the wrong thing. A page in the 'poor' band is losing both ranking and visitors who leave before it becomes usable.

**How to fix**
Give images and embeds explicit width and height so the browser can reserve their space, and stop banners or ads being injected above content that has already rendered.

**Plain-English:** Poor Cumulative Layout Shift

**Basis:** published source — [web.dev (Google)](https://web.dev/articles/cls) (vendor)

> Cumulative Layout Shift above 0.25 at the 75th percentile is Google's published "poor" band.

---

### CWV_INP_POOR
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 3

**What it is**
Interaction to Next Paint is one of Google's Core Web Vitals. This figure is the 75th percentile across real Chrome users over the last 28 days - not a synthetic test - so it reflects what visitors actually experience.

**Why it matters**
Core Web Vitals are a confirmed Google ranking input, and a page that does not respond to taps feels broken. A page in the 'poor' band is losing both ranking and visitors who leave before it becomes usable.

**How to fix**
Reduce the JavaScript that runs when someone taps or types. Look for large scripts from page builders, chat widgets and analytics tags competing on the main thread, and defer anything not needed for the first interaction.

**Plain-English:** Poor Interaction to Next Paint

**Basis:** published source — [web.dev (Google)](https://web.dev/articles/inp) (vendor)

> Interaction to Next Paint over 500 ms at the 75th percentile is Google's published "poor" band.

---

### CWV_LCP_POOR
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 3

**What it is**
Largest Contentful Paint is one of Google's Core Web Vitals. This figure is the 75th percentile across real Chrome users over the last 28 days - not a synthetic test - so it reflects what visitors actually experience.

**Why it matters**
Core Web Vitals are a confirmed Google ranking input, and a slow main image or heading is the most visible kind of slow. A page in the 'poor' band is losing both ranking and visitors who leave before it becomes usable.

**How to fix**
Find the largest element in the first screenful - usually the hero image or heading - and make it load sooner. Serve the image in a modern format at the right size, exclude it from lazy-loading, and remove render-blocking CSS and fonts ahead of it.

**Plain-English:** Poor Largest Contentful Paint

**Basis:** published source — [web.dev (Google)](https://web.dev/articles/lcp) (vendor)

> Largest Contentful Paint over 4 seconds at the 75th percentile is Google's published "poor" band.

---

### JS_DEPENDENT_NAVIGATION
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 3

**What it is**
A site's navigation menu should be real HTML links that are present the moment the page is delivered. When the menu is built entirely by JavaScript in the browser, the raw HTML an automated client receives has no links to follow.

**Why it matters**
AI crawlers (GPTBot, ClaudeBot, PerplexityBot) and task agents frequently do not execute JavaScript. If your navigation is JS-only, they see a page with no way forward and cannot reach your other pages — large parts of your site become invisible to them.

**How to fix**
Use server-side rendering or static-site generation so the <nav> contains real <a href> links in the initial HTML. A <noscript> fallback list of links also helps.

**Plain-English:** Navigation Needs JavaScript

**Basis:** published source — [Google Search Central](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics) (vendor)

> Google renders JavaScript but in a deferred second pass; links absent from the served HTML are discovered later, if at all.

---

<a id="semantic_html"></a>
## SEMANTIC_HTML

_4 codes in this category._

### INTERACTIVE_NO_ACCESSIBLE_NAME
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 2

**What it is**
An accessible name is the label an agent or screen reader announces for a control. A button with only an icon, or an input with no label, has no name.

**Why it matters**
An agent deciding which control performs an action relies on the accessible name. An unnamed control is ambiguous or unusable — the agent cannot tell what it does and may skip it.

**How to fix**
Add visible text, an aria-label (e.g. aria-label="Search"), a <label for> for form fields, or a title attribute to each unnamed interactive element.

**Plain-English:** Unlabelled Control

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 4.1.2)](https://www.w3.org/WAI/WCAG22/Understanding/name-role-value) (standard)

> Every user-interface component must expose a name; a control with none cannot be operated by assistive technology.

---

### LANDMARK_MAIN_MISSING
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 2

**What it is**
The <main> landmark marks the principal content of a page, distinct from the header, navigation, sidebar, and footer.

**Why it matters**
Without a <main> landmark, agents and assistive technology must heuristically guess which part of the page is the real content, and may extract navigation or boilerplate instead of your actual information.

**How to fix**
Wrap your primary content in <main>…</main> (one per page). Most themes have a content template where this can be added.

**Plain-English:** No Main Content Landmark

**Basis:** published source — [W3C ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/patterns/landmarks/) (standard)

> Landmark regions let assistive-technology users jump to a page's primary content instead of traversing it linearly.

**What the source does not say:** Landmarks are a W3C best practice, not a WCAG success criterion. Absence is not a conformance failure.

---

### LANDMARK_NAV_MISSING
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 2

**What it is**
The <nav> landmark marks a block of navigation links. It tells structural readers 'these links are how you move around the site'.

**Why it matters**
Without a <nav> landmark, an agent cannot reliably distinguish navigation from ordinary in-content links, making site traversal less reliable.

**How to fix**
Wrap your main menu in <nav>…</nav>. Add aria-label if you have more than one navigation region (e.g. 'Primary', 'Footer').

**Plain-English:** No Navigation Landmark

**Basis:** published source — [W3C ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/patterns/landmarks/) (standard)

> A navigation landmark identifies a block of navigational links so it can be found or skipped.

**What the source does not say:** Best practice, not a WCAG success criterion.

---

### NON_SEMANTIC_BUTTON
**Severity:** 🔵 info | **Tier:** low | **Impact:** 1 | **Effort:** 3

**What it is**
Buttons and links should be real <button>/<a> elements. A <div> or <span> with a click handler looks clickable to a sighted mouse user but is invisible as a control to anything reading the page structurally.

**Why it matters**
Task-executing agents and assistive technology identify what they can operate from element roles. A <div> with no role is not recognised as a button, so an agent cannot click it — the action it triggers becomes unreachable.

**How to fix**
Replace the <div>/<span> with a <button> (for actions) or <a href> (for navigation). If you must keep the element, add role="button", tabindex="0", and an accessible name.

**Plain-English:** Fake Button (div/span)

**Basis:** published source — [W3C WAI (WCAG 2.2, SC 4.1.2)](https://www.w3.org/WAI/WCAG22/Understanding/name-role-value) (standard)

> A component's role must be programmatically determinable; a clickable div exposes no role, so it is not announced or reachable as a control.

---
