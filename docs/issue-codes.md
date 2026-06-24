---
status: current
auto_generated: true
generator: scripts/generate_issue_codes_doc.py
---

# Issue Codes Reference

> **This file is auto-generated.** Do not edit by hand — your changes will be overwritten the next time the generator runs. To update an issue code, edit `api/crawler/issue_checker.py` (`_CATALOGUE`, `_ISSUE_SCORING`, `_AI_READINESS_CONFIDENCE`) and re-run `python scripts/generate_issue_codes_doc.py`.

**151 issue codes** across 13 categories.

## Table of contents

- [METADATA](#metadata) (20)
- [HEADING](#heading) (4)
- [BROKEN_LINK](#broken_link) (8)
- [REDIRECT](#redirect) (8)
- [CRAWLABILITY](#crawlability) (18)
- [DUPLICATE](#duplicate) (1)
- [SITEMAP](#sitemap) (1)
- [SECURITY](#security) (6)
- [URL_STRUCTURE](#url_structure) (4)
- [IMAGE](#image) (14)
- [AI_READINESS](#ai_readiness) (62)
- [RENDERING](#rendering) (1)
- [SEMANTIC_HTML](#semantic_html) (4)

---

<a id="metadata"></a>
## METADATA

Title, meta description, OG tags, canonical, favicon.

_20 codes in this category._

### ANCHOR_TEXT_GENERIC
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Links use non-descriptive anchor text like 'click here' or 'read more'

**Recommendation:** Replace generic link text with descriptive text that tells the reader (and search engines) where the link goes. Instead of 'click here', write 'view our counselling services'.

**Plain-English:** Non-Descriptive Link Text

---

### CANONICAL_EXTERNAL
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

Canonical points to a different domain

**Recommendation:** Review this canonical tag — it is pointing search engines to a page on a different website.

**Plain-English:** External Preferred URL

---

### CANONICAL_MISSING
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2

No canonical tag — page has query strings or is a near-duplicate

**Recommendation:** Add a canonical tag pointing to the preferred URL for this page to prevent duplicate content issues.

**Plain-English:** Ambiguous Preferred URL

---

### CANONICAL_SELF_MISSING
**Severity:** 🔵 info | **Impact:** 5 | **Effort:** 1

Indexable page has no canonical tag — consider adding a self-referencing canonical

**Recommendation:** Add <link rel="canonical" href="[this-page-url]"> to the page <head>. A self-referencing canonical is a best-practice signal to search engines confirming which URL is the preferred version of this page.

**Plain-English:** No Canonical Tag

---

### FAVICON_MISSING
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

No favicon found (homepage only)

**Recommendation:** Add a favicon to your site. This small icon appears in browser tabs and bookmarks and reinforces your brand.

**Plain-English:** Missing Website Icon

---

### LANG_MISSING
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 1

Page is missing the lang attribute on the <html> element

**Recommendation:** Add a lang attribute to your <html> tag, e.g. <html lang="en">. This tells search engines and screen readers what language your content is in, improving accessibility and search accuracy for multilingual queries.

**Plain-English:** No Language Declared

---

### LINK_EMPTY_ANCHOR
**Severity:** 🟡 warning | **Impact:** 7 | **Effort:** 2 | **Fixability:** content_edit

Link has no visible anchor text — screen readers and search engines cannot describe its destination

**Recommendation:** Add descriptive text inside the link. If it is an icon-only link, add an aria-label attribute (e.g. aria-label="Donate now").

**Plain-English:** Empty Link Text

---

### META_DESC_DUPLICATE
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Same meta description on multiple pages

**Recommendation:** Write a unique meta description for this page that reflects its specific content.

**Plain-English:** Duplicate Summary Snippet

---

### META_DESC_MISSING
**Severity:** 🔴 critical | **Impact:** 7 | **Effort:** 1 | **Fixability:** wp_fixable

**What it is**
A meta description is a brief summary of a page's content that appears under the title in search results. It helps users decide whether to click on your link.

**Why it matters**
While not a direct ranking factor, a missing description forces search engines to pick random text from your page, which often looks unappealing and reduces click-through rates.

**How to fix**
Add a <meta name='description'> tag to your page. Use your SEO plugin to write a compelling summary that includes your primary keywords.

**Plain-English:** Missing Summary Snippet

---

### META_DESC_TOO_LONG
**Severity:** 🟡 warning | **Impact:** 3 | **Effort:** 1 | **Fixability:** wp_fixable

Meta description over 160 characters

**Recommendation:** Shorten the description to under 160 characters. Longer descriptions are cut off in search results.

**Plain-English:** Too-Long Summary Snippet

---

### META_DESC_TOO_SHORT
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 1 | **Fixability:** wp_fixable

Meta description under 70 characters

**Recommendation:** Expand the description to 70–160 characters to give search engines more context.

**Plain-English:** Too-Short Summary Snippet

---

### OG_DESC_MISSING
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 1 | **Fixability:** wp_fixable

Open Graph description tag missing

**Recommendation:** Add an og:description meta tag. This controls the description shown when your page is shared on social media.

**Plain-English:** Missing Social Share Description

---

### OG_IMAGE_MISSING
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 1 | **Fixability:** content_edit

Open Graph image tag (og:image) is missing

**Recommendation:** Add an og:image meta tag with a URL to a high-quality preview image (1200x630px recommended). This controls the image shown when your page is shared on Facebook, LinkedIn, and other social platforms.

**Plain-English:** Missing Social Share Image

---

### OG_TITLE_MISSING
**Severity:** 🔵 info | **Impact:** 4 | **Effort:** 1 | **Fixability:** wp_fixable

Open Graph title tag missing

**Recommendation:** Add an og:title meta tag. This controls how your page title appears when shared on social media.

**Plain-English:** Missing Social Share Title

---

### TITLE_DUPLICATE
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2 | **Fixability:** content_edit

Same title used on multiple pages

**Recommendation:** Make each page title unique. Describe what makes this page different from others on your site.

**Plain-English:** Duplicate Page Name

---

### TITLE_H1_MISMATCH
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2 | **Fixability:** wp_fixable

The page title and the H1 heading share no significant words

**Recommendation:** Align the page title and H1 heading so they describe the same topic. They do not need to be identical, but both should clearly reflect the page's main subject. Significant mismatch confuses users who click a search result and then see an unrelated heading.

**Plain-English:** Title and Heading Disagree

---

### TITLE_MISSING
**Severity:** 🔴 critical | **Impact:** 9 | **Effort:** 1 | **Fixability:** wp_fixable

**What it is**
The title tag is the most important on-page SEO element. It tells search engines and users what the page is about and appears as the clickable headline in search results.

**Why it matters**
Without a title tag, search engines may not index your page correctly, and users won't see a relevant headline in search results, significantly reducing your click-through rate.

**How to fix**
Add a <title> tag to the <head> section of your HTML. In WordPress, you can typically set this using your SEO plugin (Yoast, Rank Math) or the page editor.

**Plain-English:** Missing Name Tag

---

### TITLE_TOO_LONG
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 1 | **Fixability:** wp_fixable

Title over 60 characters

**Recommendation:** Shorten the title to under 60 characters. Google truncates longer titles in search results.

**Plain-English:** Too-Long Page Name

---

### TITLE_TOO_SHORT
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 1 | **Fixability:** wp_fixable

Title under 30 characters

**Recommendation:** Expand the title to 30–60 characters. Include your organisation name and the page topic.

**Plain-English:** Too-Short Page Name

---

### TWITTER_CARD_MISSING
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 1 | **Fixability:** content_edit

Missing Twitter/X Card meta tag

**Recommendation:** Add a <meta name="twitter:card" content="summary_large_image"> tag. This controls how your page appears when shared on Twitter/X.

**Plain-English:** Missing Twitter/X Card

---

<a id="heading"></a>
## HEADING

H1 presence and uniqueness, heading hierarchy, empty headings.

_4 codes in this category._

### H1_MISSING
**Severity:** 🔴 critical | **Impact:** 8 | **Effort:** 1 | **Fixability:** content_edit

No H1 tag found on page

**Recommendation:** Add a single H1 heading that clearly states the main topic of this page.

**Plain-English:** Missing Main Heading

---

### H1_MULTIPLE
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2 | **Fixability:** content_edit

More than one H1 on the page

**Recommendation:** Remove extra H1 tags. Each page should have exactly one H1 that introduces the main topic.

**Plain-English:** Multiple Main Headings

---

### HEADING_EMPTY
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 1 | **Fixability:** content_edit

One or more heading tags have no text content

**Recommendation:** Remove empty heading tags or add descriptive text. Empty headings confuse screen readers and waste heading structure.

**Plain-English:** Empty Heading

---

### HEADING_SKIP
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 3 | **Fixability:** content_edit

Heading levels skip (e.g., H1 → H3)

**Recommendation:** Fix the heading structure so levels are not skipped. Use H1, then H2, then H3 in order.

**Plain-English:** Skipped Heading Level

---

<a id="broken_link"></a>
## BROKEN_LINK

Internal and external links returning 4xx/5xx, login redirects.

_8 codes in this category._

### BROKEN_LINK_404
**Severity:** 🔴 critical | **Impact:** 10 | **Effort:** 2 | **Fixability:** wp_fixable

Link destination returns 404 Not Found

**Recommendation:** Remove or update this link. The page it points to no longer exists.

**Plain-English:** Dead Link

---

### BROKEN_LINK_410
**Severity:** 🔴 critical | **Impact:** 8 | **Effort:** 2 | **Fixability:** wp_fixable

Link destination returns 410 Gone

**Recommendation:** Remove this link. The destination has been permanently removed.

**Plain-English:** Removed Link

---

### BROKEN_LINK_503
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 3

Link destination returns 503 — may be temporarily down or blocking automated checks

**Recommendation:** Visit the link manually to see if it loads for real visitors. If the problem persists, the destination site may be down or blocking crawlers.

**Plain-English:** Temporarily Blocked Link

---

### BROKEN_LINK_5XX
**Severity:** 🔴 critical | **Impact:** 7 | **Effort:** 3 | **Fixability:** wp_fixable

Link destination returns a server error

**Recommendation:** Check whether the linked site is down. If the problem persists, remove or replace the link.

**Plain-English:** Broken Server Link

---

### EXTERNAL_LINK_SKIPPED
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 1

Link not verified — social media platforms block automated checks

**Recommendation:** Open this link in a browser to confirm it is working correctly.

**Plain-English:** Unverified Social Link

---

### EXTERNAL_LINK_TIMEOUT
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 1

External link did not respond — destination may be slow or unavailable

**Recommendation:** Click the link to confirm it works in a browser. If it consistently fails, the destination site may be down or the domain may have expired.

**Plain-English:** Slow External Link

---

### PLACEHOLDER_LINK
**Severity:** 🔴 critical | **Impact:** 7 | **Effort:** 2

**What it is**
A placeholder link is a styled link or button whose href is a stand-in ('#', 'javascript:void(0)') rather than a real URL. It often 'works' via JavaScript for human clicks but resolves to nothing for an automated follower.

**Why it matters**
AI crawlers and task agents follow href values. A key action whose href is a placeholder is a dead end — the agent cannot complete the journey (e.g. reach your donation or contact page), and the page graph looks broken.

**How to fix**
Set the link's href to the actual target page. Reserve '#'/'javascript:void(0)' for genuine in-page controls (accordions, tabs) — not for navigation.

**Plain-English:** Dead Call-to-Action Link

---

### WRONG_PLACEHOLDER_LINK
**Severity:** 🔴 critical | **Impact:** 7 | **Effort:** 2 | **Fixability:** content_edit

**What it is**
A link whose destination is an obvious placeholder — example.com, example.org, localhost, 127.0.0.1, or a bare search-engine homepage used as filler — rather than the page it was meant to point to.

**Why it matters**
An agent following the link lands somewhere meaningless (or unreachable), breaking the task or citation trail. These are almost always unfinished template content that shipped by mistake.

**How to fix**
Edit the link to use the real URL. If the link is a legitimate reference to that domain, ignore the flag — the check is conservative and uses link text and position to avoid false positives.

**Plain-English:** Link to Placeholder Domain

---

<a id="redirect"></a>
## REDIRECT

Redirect chains, loops, and per-status-code findings.

_8 codes in this category._

### INTERNAL_REDIRECT_301
**Severity:** 🔵 info | **Impact:** 4 | **Effort:** 1

Internal page URL redirects with a 301 — links should point to the final URL

**Recommendation:** Update all internal links pointing to this URL to use the final destination directly. This eliminates an unnecessary redirect for every visitor.

**Plain-English:** Internal Redirect Link

---

### META_REFRESH_REDIRECT
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

Page uses a <meta http-equiv="refresh"> tag to redirect users

**Recommendation:** Replace meta refresh redirects with server-side 301 redirects.

**Plain-English:** HTML Redirect (Outdated)

---

### REDIRECT_301
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 2

Page returns a permanent redirect

**Recommendation:** Update any internal links pointing here to use the final destination URL directly.

**Plain-English:** Permanent Redirect

---

### REDIRECT_302
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

Page returns a temporary redirect

**Recommendation:** Confirm whether this redirect is intentional. If permanent, change it to a 301 redirect.

**Plain-English:** Temporary Redirect

---

### REDIRECT_CASE_NORMALISE
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 1

Redirect normalises URL case — your web server handles this automatically

**Recommendation:** No urgent action needed. Your server redirects uppercase URLs to lowercase automatically. To eliminate the extra redirect, update internal links to use lowercase-only URLs.

**Plain-English:** Auto-Corrected URL (Case)

---

### REDIRECT_CHAIN
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 3

Page involves a multi-hop redirect chain

**Recommendation:** Consolidate the redirect chain to a single direct redirect to the final destination.

**Plain-English:** Multi-Hop Detour

---

### REDIRECT_LOOP
**Severity:** 🔴 critical | **Impact:** 10 | **Effort:** 4

Redirect loop detected

**Recommendation:** Fix the redirect configuration immediately. This page cannot load and is invisible to search engines.

**Plain-English:** Spinning Page

---

### REDIRECT_TRAILING_SLASH
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 1

Redirect adds or removes a trailing slash — your CMS handles this automatically

**Recommendation:** No urgent action needed. Your CMS corrects this for visitors automatically. To eliminate the extra round trip, update internal links to use the canonical URL with the trailing slash your server expects.

**Plain-English:** Auto-Corrected URL (Slash)

---

<a id="crawlability"></a>
## CRAWLABILITY

robots.txt blocks, noindex directives, thin content, orphan pages.

_18 codes in this category._

### AMPHTML_BROKEN
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 3

Page declares an AMP version via <link rel="amphtml"> but the AMP URL is not reachable

**Recommendation:** Fix the AMP URL or remove the amphtml link element if AMP is no longer in use.

**Plain-English:** Broken Mobile Version

---

### CONTENT_STALE
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 4 | **Fixability:** content_edit

Page content has not been modified in over 12 months

**Recommendation:** Review and refresh this page's content. Search engines favour recently updated pages, and visitors may lose trust in outdated information. Even small updates signal freshness.

**Plain-English:** Stale Content

---

### HIGH_CRAWL_DEPTH
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 3

Page is more than 4 clicks from the homepage

**Recommendation:** Improve internal linking so this page can be reached in 3 clicks or fewer from the homepage.

**Plain-English:** Hard-to-Reach Page

---

### INTERNAL_NOFOLLOW
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

Internal link carries rel="nofollow", which may prevent search engines from discovering linked pages

**Recommendation:** Remove the nofollow attribute from internal links. Reserve rel="nofollow" for links to external or user-generated content.

**Plain-English:** Blocked Internal Link

---

### LOGIN_REDIRECT
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 1

Page redirects to a login screen

**Recommendation:** This page requires a login to access. The crawler cannot audit it. Review manually if needed.

**Plain-English:** Login-Protected Page

---

### MISSING_VIEWPORT_META
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 1

Page is missing the viewport meta tag

**Recommendation:** Add <meta name="viewport" content="width=device-width, initial-scale=1"> to the <head>. Without it, mobile browsers render the page at desktop width and zoom out, making it hard to use.

**Plain-English:** Not Mobile-Friendly

---

### NOINDEX_HEADER
**Severity:** 🟡 warning | **Impact:** 10 | **Effort:** 2

Page has a noindex HTTP header

**Recommendation:** Check your server configuration. This page is being hidden from search engines via an HTTP header.

**Plain-English:** Hidden from Search (Server)

---

### NOINDEX_META
**Severity:** 🟡 warning | **Impact:** 10 | **Effort:** 1 | **Fixability:** wp_fixable

Page has a noindex meta tag

**Recommendation:** Confirm whether this page should be excluded from search results. Remove the noindex tag if not.

**Plain-English:** Hidden from Search

---

### NOT_IN_SITEMAP
**Severity:** 🔵 info | **Impact:** 4 | **Effort:** 1 | **Fixability:** wp_fixable

Crawlable page not listed in sitemap

**Recommendation:** Add this URL to your XML sitemap so search engines can find it more reliably.

**Plain-English:** Missing from Sitemap

---

### ORPHAN_PAGE
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 4

Page has no internal links pointing to it — search engines may not discover it

**Recommendation:** Add at least one internal link to this page from a navigation menu, hub page, or relevant content page so search engines and visitors can find it.

**Plain-English:** Disconnected Page

---

### PAGE_SIZE_LARGE
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 3

HTML page response is unusually large — slower to load, especially on mobile connections

**Recommendation:** Reduce page weight by removing unused HTML, lazy-loading off-screen content, and deferring non-critical scripts. Large pages cost more mobile data and take longer to render.

**Plain-English:** Overweight Page

---

### PAGE_TIMEOUT
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 3

Page did not respond within the timeout period

**Recommendation:** Check the page manually. A persistent timeout may indicate a slow server, heavy page weight, or a broken URL. Consider increasing server response speed.

**Plain-English:** Slow-Loading Page

---

### PAGINATION_LINKS_PRESENT
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 2

Page declares rel="next" or rel="prev" pagination link elements

**Recommendation:** No action required. Ensure the linked pages are crawlable.

**Plain-English:** Paginated Content

---

### PARA_TOO_LONG
**Severity:** 🔵 info | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

One or more paragraphs exceed 150 words, making content harder to scan and extract

**Recommendation:** Break long paragraphs into shorter units of 50–100 words each. Short paragraphs improve both human readability and AI passage extraction — AI systems prefer self-contained, focused chunks.

**Plain-English:** Overly Long Paragraphs

---

### PDF_TOO_LARGE
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

PDF file exceeds 10 MB

**Recommendation:** Reduce the PDF file size. Large PDFs are slow to download and may be skipped by crawlers.

**Plain-English:** Oversized Document

---

### ROBOTS_BLOCKED
**Severity:** 🟡 warning | **Impact:** 9 | **Effort:** 2

Page blocked by robots.txt

**Recommendation:** Check whether this page should be blocked. If not, update your robots.txt file.

**Plain-English:** Blocked by Crawl Rules

---

### SCHEMA_MISSING
**Severity:** 🔵 info | **Impact:** 5 | **Effort:** 2 | **Fixability:** wp_fixable

No structured data (schema markup) found on this page

**Recommendation:** Consider adding JSON-LD structured data to help search engines understand the page content. At minimum, add Organisation schema to your homepage. Google's Rich Results Test can validate your markup.

**Plain-English:** No Structured Data

---

### THIN_CONTENT
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 4 | **Fixability:** content_edit

Page has fewer than 300 words of body content

**Recommendation:** Expand the page content to at least 300 words to provide more value to users and search engines.

**Plain-English:** Low Information

---

<a id="duplicate"></a>
## DUPLICATE

Cross-page title / meta description / title+meta pair duplicates.

_1 codes in this category._

### TITLE_META_DUPLICATE_PAIR
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2 | **Fixability:** content_edit

Both title and meta description duplicated on another page

**Recommendation:** This page and another share identical title and meta description. Update both to be unique.

**Plain-English:** Identical Title & Description

---

<a id="sitemap"></a>
## SITEMAP

Sitemap presence and per-URL coverage.

_1 codes in this category._

### SITEMAP_MISSING
**Severity:** 🔵 info | **Impact:** 6 | **Effort:** 2

No sitemap found for this domain

**Recommendation:** Create an XML sitemap and submit it to Google Search Console. Most CMS platforms can generate one automatically.

**Plain-English:** No Sitemap

---

<a id="security"></a>
## SECURITY

HTTPS, HSTS, mixed content, unsafe cross-origin links.

_6 codes in this category._

### HTTPS_REDIRECT_MISSING
**Severity:** 🔴 critical | **Impact:** 9 | **Effort:** 2

HTTP version of the site does not redirect to HTTPS

**Recommendation:** Configure a server-side 301 redirect from http:// to https:// for all URLs on your domain. Without this, visitors who type your address without 'https' will reach an insecure version of your site — and search engines treat HTTP and HTTPS as separate, competing URLs.

**Plain-English:** Insecure URL Not Redirected

---

### HTTP_PAGE
**Severity:** 🔴 critical | **Impact:** 9 | **Effort:** 2

Page is served over HTTP, not HTTPS

**Recommendation:** Migrate to HTTPS and configure a server-side 301 redirect from HTTP to HTTPS.

**Plain-English:** Unsecured Page

---

### MISSING_HSTS
**Severity:** 🔵 info | **Impact:** 4 | **Effort:** 2

HTTPS page is missing the Strict-Transport-Security header

**Recommendation:** Add Strict-Transport-Security: max-age=31536000; includeSubDomains to all HTTPS responses.

**Plain-English:** Security Header Missing

---

### MIXED_CONTENT
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2

HTTPS page loads resources over HTTP

**Recommendation:** Update all resource URLs to use HTTPS. Check images, scripts, stylesheets, and iframes.

**Plain-English:** Partially Unsecured Page

---

### UNSAFE_CROSS_ORIGIN_LINK
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 1

External link opens in a new tab without rel="noopener" or rel="noreferrer"

**Recommendation:** Add rel="noopener noreferrer" to all <a target="_blank"> links pointing to external URLs.

**Plain-English:** Unsafe External Link

---

### WWW_CANONICALIZATION
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

Both www and non-www versions of the site resolve without redirecting to each other

**Recommendation:** Configure a 301 redirect so one version (www or non-www) redirects to the other. This consolidates link equity and avoids duplicate content.

**Plain-English:** www/non-www Not Consolidated

---

<a id="url_structure"></a>
## URL_STRUCTURE

URL format: uppercase, spaces, underscores, length.

_4 codes in this category._

### URL_HAS_SPACES
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 3 | **Fixability:** content_edit

URL contains encoded spaces (%20)

**Recommendation:** Replace spaces in URLs with hyphens.

**Plain-English:** Spaces in Web Address

---

### URL_HAS_UNDERSCORES
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 4 | **Fixability:** content_edit

URL path uses underscores instead of hyphens

**Recommendation:** Use hyphens as word separators in URL paths. Google treats underscores as word-joiners.

**Plain-English:** Underscores in Web Address

---

### URL_TOO_LONG
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 4 | **Fixability:** content_edit

URL exceeds 200 characters

**Recommendation:** Shorten the URL slug. Long URLs are harder to share and may be truncated in search results.

**Plain-English:** Overly Long Web Address

---

### URL_UPPERCASE
**Severity:** 🟡 warning | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

URL path contains uppercase characters

**Recommendation:** Use lowercase-only URLs. Most web servers will auto-redirect uppercase URLs to lowercase, but this creates an unnecessary extra redirect. Update internal links and page slugs to use lowercase only to avoid that redirect entirely.

**Plain-English:** Mixed-Case Web Address

---

<a id="image"></a>
## IMAGE

Image accessibility, performance, format, srcset, and content checks.

_14 codes in this category._

### IMG_ALT_DUP_FILENAME
**Severity:** 🟡 warning | **Impact:** 3 | **Effort:** 1 | **Fixability:** wp_fixable

Image alt text matches the filename

**Recommendation:** Write descriptive alt text instead of using the filename. Describe what the image shows to help search engines and screen reader users.

**Plain-English:** Alt Text is Filename

---

### IMG_ALT_GENERIC
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 1 | **Fixability:** wp_fixable

Image alt text uses a generic term like 'image', 'photo', or 'picture'

**Recommendation:** Replace generic alt text with a specific description of what the image shows. Instead of 'photo', describe the scene, people, or objects depicted.

**Plain-English:** Generic Alt Text

---

### IMG_ALT_MISSING
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2 | **Fixability:** wp_fixable

One or more images are missing an alt attribute or have empty/blank alt text

**Recommendation:** Add a descriptive alt attribute to every <img> tag. Describe what the image shows in plain language, e.g. alt="Counsellor speaking with a young person". Every image should have meaningful alt text for accessibility and SEO.

**Plain-English:** Images Missing Alt Text

---

### IMG_ALT_MISUSED
**Severity:** 🟡 warning | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

Alt text usage is incorrect for image type (decorative image has alt text)

**Recommendation:** Decorative images should have empty alt="" to be skipped by screen readers. Only meaningful images should have descriptive alt text.

**Plain-English:** Alt Text Misused

---

### IMG_ALT_TOO_LONG
**Severity:** 🟡 warning | **Impact:** 2 | **Effort:** 1 | **Fixability:** wp_fixable

Image alt text is too long (over 125 characters)

**Recommendation:** Shorten the alt text to under 125 characters. Be concise while still describing the image content. Screen readers may truncate longer alt text.

**Plain-English:** Alt Text Too Long

---

### IMG_ALT_TOO_SHORT
**Severity:** 🟡 warning | **Impact:** 3 | **Effort:** 1 | **Fixability:** wp_fixable

Image alt text is too short (under 5 characters)

**Recommendation:** Expand the alt text to at least 5 characters. Describe what the image shows, not just a single word.

**Plain-English:** Alt Text Too Short

---

### IMG_BROKEN
**Severity:** 🔴 critical | **Impact:** 8 | **Effort:** 2

Image src URL returns an error response (4xx/5xx)

**Recommendation:** Replace or remove the broken image. Use your CMS media library to re-upload the file or update the src URL to point to the correct location.

**Plain-English:** Broken Image

---

### IMG_DUPLICATE_CONTENT
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 2

Same image content used under multiple URLs

**Recommendation:** Consolidate duplicate images to a single URL. This saves server space and improves caching efficiency.

**Plain-English:** Duplicate Image

---

### IMG_FORMAT_LEGACY
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 2 | **Fixability:** content_edit

Image uses legacy format (JPEG/PNG/GIF) where WebP would save significant space

**Recommendation:** Convert to WebP format for 25-35% smaller file sizes with the same quality. Most modern browsers support WebP.

**Plain-English:** Legacy Image Format

---

### IMG_NO_SRCSET
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 3

Large image lacks srcset for responsive delivery

**Recommendation:** Add a srcset attribute to serve appropriately sized images to mobile devices. This improves load times on smaller screens.

**Plain-English:** Missing Responsive Images

---

### IMG_OVERSCALED
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 3 | **Fixability:** content_edit

Image intrinsic size is more than 2x its display size (wasted bandwidth)

**Recommendation:** Resize the image to match its display dimensions. Use srcset to serve appropriately sized images to different devices.

**Plain-English:** Overscaled Image

---

### IMG_OVERSIZED
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2 | **Fixability:** content_edit

Image file exceeds 200 KB

**Recommendation:** Compress this image. Use Squoosh, TinyPNG, or ImageOptim to reduce the file size without visible quality loss.

**Plain-English:** Oversized Image

---

### IMG_POOR_COMPRESSION
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Image has poor compression efficiency (high bytes per pixel)

**Recommendation:** Re-compress the image using WebP format for better efficiency. Use tools like Squoosh or ImageOptim for lossless compression.

**Plain-English:** Poor Compression

---

### IMG_SLOW_LOAD
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

Image takes too long to load (over 1 second)

**Recommendation:** Optimize the image by compressing it, reducing dimensions, or using a CDN. Consider lazy loading for below-the-fold images.

**Plain-English:** Slow Loading Image

---

<a id="ai_readiness"></a>
## AI_READINESS

Site readiness for AI search engines (Google AI Overviews, ChatGPT, Perplexity, etc.). Every code in this category carries a confidence label per the v2.0 spec: **Established** (vendor-confirmed effect), **Reasonable proxy** (industry consensus + Google's published best practices), **Heuristic** (industry consensus only, no vendor confirmation).

_62 codes in this category._

### AI_BOT_BLANKET_DISALLOW
**Severity:** 🔴 critical | **Confidence:** Established | **Impact:** 9 | **Effort:** 1

robots.txt blocks all bots with User-agent: * / Disallow: /

**Recommendation:** Update robots.txt to allow at least AI search bots. Remove 'Disallow: /' or add specific allow rules for AI crawlers.

**Plain-English:** All Bots Blocked

---

### AI_BOT_DEPRECATED_DIRECTIVE
**Severity:** 🟡 warning | **Confidence:** Established | **Impact:** 2 | **Effort:** 1

robots.txt references a deprecated AI bot user agent

**Recommendation:** Remove deprecated directives (anthropic-ai, claude-web) and replace with current bot names (ClaudeBot, Claude-SearchBot, Claude-User).

**Plain-English:** Deprecated AI Bot Name in robots.txt

---

### AI_BOT_NO_AI_DIRECTIVES
**Severity:** 🔵 info | **Confidence:** Reasonable proxy | **Impact:** 1 | **Effort:** 1

robots.txt has no explicit directives for known AI bots

**Recommendation:** Add explicit AI bot rules to make your intent clear. Example: allow all search bots while optionally blocking training bots.

**Plain-English:** No AI Bot Configuration

---

### AI_BOT_SEARCH_BLOCKED
**Severity:** 🟡 warning | **Confidence:** Established | **Impact:** 8 | **Effort:** 1

A major AI search bot is disallowed in robots.txt

**Recommendation:** Allow AI search bots in robots.txt. This bot enables ChatGPT, Gemini, and other AI engines to include your site in their answers.

**Plain-English:** AI Search Bot Blocked

---

### AI_BOT_TABLE_STALE
**Severity:** 🔵 info | **Confidence:** Heuristic | **Impact:** 0 | **Effort:** 1

Internal AI bot reference table has not been reviewed in >12 months

**Recommendation:** Review and update the TalkingToad AI bot reference table.

**Plain-English:** AI Bot Table Needs Review

---

### AI_BOT_TRAINING_DISALLOWED
**Severity:** 🔵 info | **Confidence:** Established | **Impact:** 0 | **Effort:** 1

An AI training bot is disallowed in robots.txt

**Recommendation:** This may be intentional. If accidental, allow the bot. Blocking training bots does not affect AI search visibility.

**Plain-English:** AI Training Bot Disallowed

---

### AI_BOT_USER_FETCH_BLOCKED
**Severity:** 🟡 warning | **Confidence:** Established | **Impact:** 4 | **Effort:** 1

An AI user-fetch bot is disallowed in robots.txt — this block has no effect

**Recommendation:** Remove the block. User-fetch bots (ChatGPT-User, Claude-User) do not honor robots.txt by design. Blocking them signals misconfiguration.

**Plain-English:** AI User Bot Blocked (Ineffective)

---

### AI_CITED_PAGE
**Severity:** 🔵 info | **Confidence:** Established | **Impact:** 0 | **Effort:** 0 | **Fixability:** content_edit

This page has been cited by AI engines in the last 30 days, indicating established AI visibility.

**Recommendation:** Maintain content quality and freshness to sustain AI citation status.

**Plain-English:** AI-Cited Page

---

### AI_CONTENT_NOT_IN_TEXT
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Important content on this page is not in textual form — it is carried by images/video or locked inside an embed (iframe/PDF) that AI systems cannot read as text

**Recommendation:** Provide the key information as real on-page text. Add a textual summary or transcript alongside any image, video, or embedded document so AI systems and screen readers can access it.

**Plain-English:** Content Not Available as Text

---

### AI_HIGH_VALUE_UNCITED
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

This healthy, content-rich page has zero AI citations despite recent data, suggesting an AI visibility gap.

**Recommendation:** Improve content structure, add schema markup, and build backlinks to increase AI discoverability.

**Plain-English:** High-Value Page Not AI-Cited

---

### AI_MAIN_CONTENT_LOW_RATIO
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 1 | **Fixability:** content_edit

The main content area contains less than 40% of the page's visible text. Navigation, sidebar, and footer content dominates, making it harder for AI systems and readers to identify the primary content.

**Recommendation:** Consider reducing navigation/sidebar/footer content, or expanding the main content area. Ensure the main content is at least 40% of the page's visible text.

**Plain-English:** Low Main Content Ratio

---

### AI_NO_VISUAL_COMPANION
**Severity:** 🔵 info | **Confidence:** Reasonable proxy | **Impact:** 1 | **Effort:** 1 | **Fixability:** content_edit

A substantial text page (article/service/FAQ) has no images or video to support its content

**Recommendation:** Add at least one relevant, high-quality image or video. Visuals help both readers and AI systems understand and surface your content.

**Plain-English:** No Supporting Visual

---

### AI_PREVIEW_BLOCKED_AT_BOT
**Severity:** 🔵 info | **Confidence:** Established | **Impact:** 3 | **Effort:** 1

An X-Robots-Tag directive specifically blocks an AI crawler (e.g. GPTBot, Google-Extended) from indexing this page

**Recommendation:** This is intentional if you don't want AI engines using this page. If you DO want AI citation, remove the AI-bot-specific directive.

**Plain-English:** AI Bot Blocked

---

### AI_PREVIEW_SUPPRESSED
**Severity:** 🔵 info | **Confidence:** Established | **Impact:** 3 | **Effort:** 1

An X-Robots-Tag response header suppresses this page's search/AI preview (nosnippet or max-snippet:0)

**Recommendation:** If you want this page to be eligible for AI Overviews and citations, remove the nosnippet / max-snippet:0 directive from the X-Robots-Tag header (often set in server config or an SEO plugin).

**Plain-English:** AI Preview Suppressed

---

### AI_TXT_MISSING
**Severity:** 🔵 info | **Confidence:** Heuristic | **Impact:** 1 | **Effort:** 1

No /ai.txt file found at site root

**Recommendation:** Consider creating /ai.txt to declare AI usage policies and content permissions. Emerging convention; no confirmed AI engine support yet.

**Plain-English:** No ai.txt File

---

### AUTHOR_BYLINE_MISSING
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Blog or article page has no author byline, rel=author, or JSON-LD author field

**Recommendation:** Add an author byline with name and optionally credentials. Include rel='author' on the author link and an 'author' field in your JSON-LD BlogPosting schema.

**Plain-English:** No Author Attribution

---

### BLOG_SECTIONS_MISSING
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 5 | **Effort:** 2 | **Fixability:** content_edit

Blog or article page lacks sufficient heading structure for AI citation anchors

**Recommendation:** Add H2/H3 headings to break content into named sections. AI engines use headings as citation anchors — a long post with fewer than 3 headings cannot be accurately quoted or cited by AI.

**Plain-English:** No Section Headings for AI Citation

---

### CENTRAL_CLAIM_BURIED
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 5 | **Effort:** 3 | **Fixability:** content_edit

The page's main claim or answer does not appear in the first 150 words

**Recommendation:** State the central point in the opening paragraph. AI systems weight early content more heavily when deciding what to extract and cite.

**Plain-English:** Main Point Buried

---

### CHUNKS_NOT_SELF_CONTAINED
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 5 | **Effort:** 4 | **Fixability:** content_edit

More than half of the page's H2/H3 sections are not understandable in isolation

**Recommendation:** Each section should open with a context sentence that restates the subject. AI retrieval systems serve individual chunks, not whole pages.

**Plain-English:** Sections Lack Context

---

### CITATIONS_MISSING_SUBSTANTIAL_CONTENT
**Severity:** 🔵 info | **Confidence:** Reasonable proxy | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

Page has 200+ words but no citations or source attribution

**Recommendation:** Add citations to factual claims. Use inline references or a Sources section.

**Plain-English:** Missing Citations

---

### CITATIONS_ORPHANED
**Severity:** 🔵 info | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 1 | **Fixability:** content_edit

Page has citations without surrounding context

**Recommendation:** Ensure each citation appears within a sentence that explains its relevance.

**Plain-English:** Citations Without Context

---

### CITATIONS_SOURCES_INACCESSIBLE
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 4 | **Effort:** 3 | **Fixability:** content_edit

Page cites sources that are broken or inaccessible

**Recommendation:** Replace broken citation links with working alternatives.

**Plain-English:** Inaccessible Citation Sources

---

### CODE_BLOCK_MISSING_TECHNICAL
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Technical how-to/guide page with numbered steps has no <pre> or <code> blocks

**Recommendation:** Wrap command-line examples, code snippets, and configuration in <code> or <pre> tags. This makes them unambiguously extractable by AI systems.

**Plain-English:** No Code Blocks in Technical Guide

---

### COMPARISON_TABLE_MISSING
**Severity:** 🔵 info | **Confidence:** Heuristic | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

Page contains comparison language ('vs', 'versus', 'compared to') but no table

**Recommendation:** Add a structured comparison table. Tables are the most extractable format for comparisons — AI systems can read them as structured data.

**Plain-English:** Comparison Without Table

---

### CONTACT_INFO_NOT_IN_HTML
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

**What it is**
Contact information that exists on the page only as an image (e.g. a phone number in a banner graphic) or that is inserted by client-side JavaScript is invisible to anything reading the raw HTML.

**Why it matters**
When an AI assistant is asked 'how do I contact this organisation?', it can only answer from text it can read. Image- or JS-only contact details are missed, so the agent cannot surface your phone, email, or address.

**How to fix**
Render contact details as plain HTML text in the footer or a contact block. Optionally add ContactPoint / PostalAddress schema to reinforce them.

**Plain-English:** Contact Info Not in Text

---

### CONTENT_CLOAKING_DETECTED
**Severity:** ⚪ error | **Confidence:** Reasonable proxy | **Impact:** 8 | **Effort:** 4

Rendered content appears to shift the page's topic versus raw HTML — possible cloaking

**Recommendation:** Ensure raw HTML and rendered content describe the same topic. Serving different content to AI crawlers than to users violates search quality guidelines.

**Plain-English:** Possible Content Cloaking

---

### CONTENT_DATE_STALE_VISIBLE
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Visible/declared modified date is old enough to read as stale for its page type

**Recommendation:** Review the content for accuracy and update the visible date if the information is still current. For evergreen content, consider removing the date entirely or adding a note that it has been reviewed.

**Plain-English:** Stale Visible Date

---

### CONTENT_IMAGE_HEAVY
**Severity:** 🔵 info | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 3 | **Fixability:** content_edit

Page has significantly more images than text sections

**Recommendation:** Add descriptive captions and surrounding text for each image. AI systems rely on text context to interpret visual content.

**Plain-English:** Image-Heavy Layout

---

### CONTENT_NOT_EXTRACTABLE_NO_TEXT
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 6 | **Effort:** 4 | **Fixability:** content_edit

Page has no visible text — only images, video, or interactive media

**Recommendation:** Add descriptive text, captions, or transcripts. AI systems cannot extract information from images or videos without accompanying text.

**Plain-English:** No Text Content

---

### CONTENT_STAT_OUTDATED
**Severity:** 🔵 info | **Confidence:** Heuristic | **Impact:** 2 | **Effort:** 1 | **Fixability:** content_edit

Body text references a year that is ≥24 months old without mentioning the current year.

**Recommendation:** Update the statistic or reference to the current year, or add context that acknowledges the original year while explaining continued relevance.

**Plain-English:** Outdated Year Reference

---

### CONTENT_THIN
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 3 | **Fixability:** content_edit

Page has very little text (under 100 words)

**Recommendation:** Expand the page with substantive content. Thin pages provide insufficient context for AI systems to generate accurate summaries.

**Plain-English:** Thin Content

---

### CONTENT_UNSTRUCTURED
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

Page has substantial text but no heading structure

**Recommendation:** Add H2 and H3 headings to break content into sections. Headings help AI systems identify topics and extract structured information.

**Plain-English:** No Heading Structure

---

### CONVERSATIONAL_H2_MISSING
**Severity:** 🔵 info | **Confidence:** Heuristic | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

H2 headings do not use conversational interrogatives (How, What, Why)

**Recommendation:** Rewrite some H2 headings as questions. LLMs prefer direct question-answer pairings for more accurate retrieval and citing.

**Plain-English:** Non-Conversational Headings

---

### DATE_MODIFIED_MISSING
**Severity:** 🔵 info | **Confidence:** Reasonable proxy | **Impact:** 2 | **Effort:** 1

Blog or article page has no last-modified date in JSON-LD

**Recommendation:** Add dateModified to your JSON-LD schema to signal content freshness to AI systems.

**Plain-English:** Missing Last-Modified Date

---

### DATE_PUBLISHED_MISSING
**Severity:** 🔵 info | **Confidence:** Reasonable proxy | **Impact:** 3 | **Effort:** 1

Blog or article page has no publication date in JSON-LD or meta tags

**Recommendation:** Add datePublished to your JSON-LD schema and/or <meta property='article:published_time'>.

**Plain-English:** Missing Publication Date

---

### DOCUMENT_PROPS_MISSING
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

PDF is missing internal Title or Subject metadata

**Recommendation:** Update PDF document properties to include a clear Title and Subject. AIs use these properties for source labels and citations.

**Plain-English:** Missing Document Info

---

### EXTERNAL_CITATIONS_LOW
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 7 | **Effort:** 2 | **Fixability:** content_edit

500+ word page has no outbound links to external authoritative sources in body text

**Recommendation:** Add links to authoritative external sources (.gov, .edu, research papers, official docs). Aggarwal et al. (2023) found citations measurably increase AI engine quotability.

**Plain-English:** No External Citations

---

### FAQ_SCHEMA_MISSING
**Severity:** 🔵 info | **Confidence:** Reasonable proxy | **Impact:** 3 | **Effort:** 2

Page has an FAQ section but no FAQPage JSON-LD schema

**Recommendation:** Add FAQPage schema to your FAQ section so AI systems can extract Q&A pairs directly.

**Plain-English:** FAQ Without Schema

---

### FIRST_VIEWPORT_NO_ANSWER
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 5 | **Effort:** 2 | **Fixability:** content_edit

First 200 words contain no direct answer signal (definition, TL;DR, summary phrase)

**Recommendation:** Lead with a concise definition or summary ('X is...', 'In short...', 'Key takeaway:'). AI systems read top-to-bottom; putting the answer in the first 200 words maximises the chance it is retrieved and cited.

**Plain-English:** No Lead Answer

---

### GEO_SUMMARY_BURIED
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 7 | **Effort:** 3 | **Fixability:** content_edit

The first paragraph or list does not lead its H2 or H3 section — the core answer is pushed below images, media, or preamble

**Recommendation:** Reorder each H2/H3 section so the core answer leads in 1–2 sentences, with supporting content following. AI retrievers and skimming humans both miss answers that aren't immediately under the heading.

**Plain-English:** Answer Buried Under H2/H3

---

### JSON_LD_INVALID
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2

A JSON-LD block is present but missing @type or @context (invalid schema)

**Recommendation:** Ensure every JSON-LD block includes both @type and @context fields. Malformed schema blocks are ignored by search engines and AI parsers.

**Plain-English:** Invalid JSON-LD Schema

---

### JSON_LD_MISSING
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 7 | **Effort:** 2

No JSON-LD structured data found on this indexable page

**Recommendation:** Add <script type="application/ld+json"> markup. Schema is the 'knowledge graph' used by AI systems for RAG-based answers.

**Plain-English:** Missing AI Schema

---

### JS_RENDERED_CONTENT_DIFFERS
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 6 | **Effort:** 4

Rendered page contains substantially more content than raw HTML (>20% more tokens)

**Recommendation:** Pre-render key content as HTML so AI crawlers can access it without JavaScript. Consider server-side rendering or static generation for important pages.

**Plain-English:** JS-Gated Content

---

### LINK_PROFILE_PROMOTIONAL
**Severity:** 🔵 info | **Confidence:** Heuristic | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Over 80% of outbound body-text links point to the same organisation's own domains

**Recommendation:** Add external citations to authoritative third-party sources. An all-internal link profile signals low authority to AI systems.

**Plain-English:** All-Internal Link Profile

---

### LLMS_TXT_INVALID
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

/llms.txt format is invalid

**Recommendation:** Ensure your /llms.txt uses text/plain MIME type and includes a Markdown-style H1 title, a blockquote summary, and a list of high-value URLs (max 20).

**Plain-English:** Invalid AI Instruction File

---

### LLMS_TXT_MISSING
**Severity:** 🔵 info | **Confidence:** Heuristic | **Impact:** 6 | **Effort:** 1 | **Fixability:** content_edit

No llms.txt found at root

**Recommendation:** Create an /llms.txt file to help LLMs and AI agents (Gemini, Perplexity) accurately crawl and cite your high-value content.

**Plain-English:** Missing AI Instruction File

---

### ORPHAN_CLAIM_TECHNICAL
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 6 | **Effort:** 2 | **Fixability:** content_edit

Technical/how-to page has 3+ factual claims not paired with a source link or attribution

**Recommendation:** Add a source link or attribution ('according to [source]') next to each specific capability claim, number, or procedure step.

**Plain-English:** Unsourced Technical Claims

---

### PROMOTIONAL_CONTENT_INTERRUPTS
**Severity:** 🔵 info | **Confidence:** Heuristic | **Impact:** 3 | **Effort:** 3 | **Fixability:** content_edit

Mid-article sections classified as promotional interrupt the content flow

**Recommendation:** Move promotional or sales content to the end or to a sidebar. AI systems may de-weight or skip sections they identify as promotional.

**Plain-English:** Promotional Content in Article

---

### QUERY_COVERAGE_WEAK
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 7 | **Effort:** 2 | **Fixability:** content_edit

Page H1 topic terms are under-represented in the intro or section headings — AI retrieval systems may not associate this page with its target query

**Recommendation:** Ensure the language from your H1 (the page's primary topic) appears naturally in the first 200 words and in at least one H2 section heading. AI systems score pages by query–content similarity; if your topic terms don't appear where they look first, the page may be skipped.

**Plain-English:** Weak Query Coverage

---

### QUOTATIONS_MISSING
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 6 | **Effort:** 2 | **Fixability:** content_edit

500+ word page contains no direct quotations from named sources

**Recommendation:** Add quoted statements from named experts or sources. Use <blockquote> for longer quotes. Aggarwal et al. (2023) found quotations measurably increase AI citation rates.

**Plain-English:** No Expert Quotations

---

### RAW_HTML_JS_DEPENDENT
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 6 | **Effort:** 3

Page raw HTML is a JavaScript app shell with near-zero visible text

**Recommendation:** Render critical content server-side (SSR) or as static HTML. AI crawlers may not execute JavaScript, so JS-gated content is invisible to them.

**Plain-English:** JS-Only Content (No SSR)

---

### SCHEMA_DEPRECATED_TYPE
**Severity:** 🔵 info | **Confidence:** Reasonable proxy | **Impact:** 2 | **Effort:** 1 | **Fixability:** content_edit

Page uses deprecated schema.org types

**Recommendation:** Replace deprecated schema types with modern equivalents from schema.org.

**Plain-English:** Deprecated Schema Type

---

### SCHEMA_ORG_MISSING
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 5 | **Effort:** 2 | **Fixability:** wp_fixable

**What it is**
Organization schema is the structured-data block that states who you are — name, logo, URL, social profiles, contact points. On the homepage it anchors your entire site's identity in the knowledge graph.

**Why it matters**
AI systems build an entity profile of your organisation from Organization schema. Without it, they must infer your identity from prose, which is less reliable and weakens your chance of being correctly named and cited.

**How to fix**
Add a <script type="application/ld+json"> Organization block to your homepage (TalkingToad's Entity Schema Factory can generate one), or enable Organization schema in your SEO plugin.

**Plain-English:** No Organization Schema

---

### SCHEMA_TYPE_CONFLICT
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

Page declares multiple conflicting schema types

**Recommendation:** Use a single coherent @type. For multiple entities use @graph or nesting.

**Plain-English:** Conflicting Schema Types

---

### SCHEMA_TYPE_MISMATCH
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 4 | **Effort:** 2 | **Fixability:** content_edit

Page schema type does not match inferred page type

**Recommendation:** Ensure JSON-LD @type matches the page content (Article for blog posts, Person for team bios, Service for service pages).

**Plain-English:** Mismatched Schema Type

---

### SCHEMA_VISIBLE_MISMATCH
**Severity:** 🟡 warning | **Confidence:** Established | **Impact:** 5 | **Effort:** 2 | **Fixability:** content_edit

A value declared in JSON-LD structured data does not appear in the page's visible text

**Recommendation:** Make sure every value in your structured data (headline, name, FAQ answers, address) is also present in the visible page content — Google requires markup to match what users see.

**Plain-English:** Schema Not in Visible Text

---

### SECTION_CROSS_REFERENCES
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 6 | **Effort:** 2 | **Fixability:** content_edit

Page contains backward-reference phrases ('as mentioned above', 'as discussed earlier') that break section independence

**Recommendation:** Remove or replace phrases like 'as mentioned above' with the actual information being referenced. AI systems cite individual passages in isolation — a passage that refers to earlier content cannot be understood or quoted on its own.

**Plain-English:** Section Back-References

---

### SECTION_VAGUE_OPENER
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 5 | **Effort:** 2 | **Fixability:** content_edit

One or more H2/H3 sections begin with a vague demonstrative reference ('This method…', 'It allows…', 'These features…') instead of an explicit subject

**Recommendation:** Replace vague openers with explicit nouns: instead of 'This approach improves…' write 'RAG retrieval improves…'. Each section must make sense in isolation — AI systems extract sections as independent passages and cannot infer context.

**Plain-English:** Vague Section Openers

---

### SEMANTIC_DENSITY_LOW
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 5 | **Effort:** 3

Text-to-HTML ratio is below 10%

**Recommendation:** Clean up excessive code-bloat (styles, scripts, nested divs). High code-to-text ratios consume more AI tokens and confuse retrieval engines.

**Plain-English:** High Code-to-Text Ratio

---

### STATISTICS_COUNT_LOW
**Severity:** 🟡 warning | **Confidence:** Heuristic | **Impact:** 7 | **Effort:** 2 | **Fixability:** content_edit

500+ word page contains no statistics (numbers paired with units, percentages, or dates)

**Recommendation:** Add specific data points: percentages, measurements, dates, counts. Aggarwal et al. (2023) found statistics measurably increase citation by generative engines.

**Plain-English:** No Statistics

---

### STRUCTURED_ELEMENTS_LOW
**Severity:** 🔵 info | **Confidence:** Heuristic | **Impact:** 3 | **Effort:** 2 | **Fixability:** content_edit

Page has very few structured elements (lists, tables, code blocks) relative to content length

**Recommendation:** Add bullet lists, numbered lists, or tables to break up prose. Structured elements are more reliably extracted by AI chunkers than continuous paragraphs.

**Plain-English:** Low Structured Element Count

---

### UA_CONTENT_DIFFERS
**Severity:** 🟡 warning | **Confidence:** Reasonable proxy | **Impact:** 7 | **Effort:** 3

AI crawler user agents (GPTBot, ClaudeBot) receive substantially less content than a browser

**Recommendation:** Ensure AI crawler requests receive the same content as regular browsers. Serving stripped content to AI bots prevents citation and indexing.

**Plain-English:** AI Bot Content Stripping

---

<a id="rendering"></a>
## RENDERING

_1 codes in this category._

### JS_DEPENDENT_NAVIGATION
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 3

**What it is**
A site's navigation menu should be real HTML links that are present the moment the page is delivered. When the menu is built entirely by JavaScript in the browser, the raw HTML an automated client receives has no links to follow.

**Why it matters**
AI crawlers (GPTBot, ClaudeBot, PerplexityBot) and task agents frequently do not execute JavaScript. If your navigation is JS-only, they see a page with no way forward and cannot reach your other pages — large parts of your site become invisible to them.

**How to fix**
Use server-side rendering or static-site generation so the <nav> contains real <a href> links in the initial HTML. A <noscript> fallback list of links also helps.

**Plain-English:** Navigation Needs JavaScript

---

<a id="semantic_html"></a>
## SEMANTIC_HTML

_4 codes in this category._

### INTERACTIVE_NO_ACCESSIBLE_NAME
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

**What it is**
An accessible name is the label an agent or screen reader announces for a control. A button with only an icon, or an input with no label, has no name.

**Why it matters**
An agent deciding which control performs an action relies on the accessible name. An unnamed control is ambiguous or unusable — the agent cannot tell what it does and may skip it.

**How to fix**
Add visible text, an aria-label (e.g. aria-label="Search"), a <label for> for form fields, or a title attribute to each unnamed interactive element.

**Plain-English:** Unlabelled Control

---

### LANDMARK_MAIN_MISSING
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 2

**What it is**
The <main> landmark marks the principal content of a page, distinct from the header, navigation, sidebar, and footer.

**Why it matters**
Without a <main> landmark, agents and assistive technology must heuristically guess which part of the page is the real content, and may extract navigation or boilerplate instead of your actual information.

**How to fix**
Wrap your primary content in <main>…</main> (one per page). Most themes have a content template where this can be added.

**Plain-English:** No Main Content Landmark

---

### LANDMARK_NAV_MISSING
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 2

**What it is**
The <nav> landmark marks a block of navigation links. It tells structural readers 'these links are how you move around the site'.

**Why it matters**
Without a <nav> landmark, an agent cannot reliably distinguish navigation from ordinary in-content links, making site traversal less reliable.

**How to fix**
Wrap your main menu in <nav>…</nav>. Add aria-label if you have more than one navigation region (e.g. 'Primary', 'Footer').

**Plain-English:** No Navigation Landmark

---

### NON_SEMANTIC_BUTTON
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 3

**What it is**
Buttons and links should be real <button>/<a> elements. A <div> or <span> with a click handler looks clickable to a sighted mouse user but is invisible as a control to anything reading the page structurally.

**Why it matters**
Task-executing agents and assistive technology identify what they can operate from element roles. A <div> with no role is not recognised as a button, so an agent cannot click it — the action it triggers becomes unreachable.

**How to fix**
Replace the <div>/<span> with a <button> (for actions) or <a href> (for navigation). If you must keep the element, add role="button", tabindex="0", and an accessible name.

**Plain-English:** Fake Button (div/span)

---
