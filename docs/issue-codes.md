# Issue Code Reference

Full reference for every issue code TalkingToad can detect.
Each entry includes: what the issue is, why it matters for a nonprofit site, and how to fix it in plain English.

**Source of truth for scoring:** `api/crawler/issue_checker.py` (`_ISSUE_SCORING`, `_CATALOGUE`)
**Frontend help content:** `frontend/src/data/issueHelp.js`

---

## Diagnostic `extra` data

All issue codes now include an optional `extra` field containing diagnostic data specific to the issue type. This allows the frontend to display contextual details without a second API call. When no extra data applies, the field is `null`.

**Common `extra` fields by issue:**

| Issue code | Extra fields | Example |
|---|---|---|
| `TITLE_TOO_SHORT` / `TITLE_TOO_LONG` | `title`, `length` | `{"title": "About", "length": 5}` |
| `META_DESC_TOO_SHORT` / `META_DESC_TOO_LONG` | `description`, `length` | `{"description": "...", "length": 42}` |
| `TITLE_H1_MISMATCH` | `title`, `h1` | `{"title": "About Us | Org", "h1": "Welcome"}` |
| `H1_MISSING` | `headings_found` | `{"headings_found": [{"level": 2, "text": "..."}]}` |
| `H1_MULTIPLE` | `h1_tags`, `count` | `{"h1_tags": ["About", "Welcome"], "count": 2}` |
| `HEADING_SKIP` | `outline_snippet`, `skip_detail` | `{"skip_detail": "H1 → H3 (skipped H2)"}` |
| `BROKEN_LINK_404` / `_410` / `_5XX` / `_503` | `status_code`, `source_url` | `{"status_code": 404, "source_url": "https://..."}` |
| `URL_UPPERCASE` | `path` | Included implicitly via the issue's `page_url` |
| `THIN_CONTENT` | `word_count` | `{"word_count": 87}` |
| `HIGH_CRAWL_DEPTH` | `crawl_depth` | `{"crawl_depth": 6}` |
| `IMG_ALT_MISSING` | `missing_alt_count`, `images` | `{"missing_alt_count": 3, "images": [...]}` |
| `LINK_EMPTY_ANCHOR` | `empty_anchor_count`, `empty_anchors` | `{"empty_anchor_count": 2, "empty_anchors": [...]}` |
| `SEMANTIC_DENSITY_LOW` | `ratio`, `breakdown`, `diagnosis` | `{"ratio": 0.08, "diagnosis": "..."}` |
| `PAGE_SIZE_LARGE` | `size_bytes`, `size_kb` | `{"size_bytes": 350000, "size_kb": 342}` |
| `CANONICAL_EXTERNAL` | `canonical_url` | `{"canonical_url": "https://other.com/page"}` |
| `NOINDEX_META` / `NOINDEX_HEADER` | `source`, `content` | `{"source": "meta robots tag", "content": "noindex"}` |
| `META_REFRESH_REDIRECT` | `refresh_url` | `{"refresh_url": "https://..."}` |
| `DOCUMENT_PROPS_MISSING` | PDF metadata fields | `{"title": null, "subject": null}` |
| `CONVERSATIONAL_H2_MISSING` | `h2_headings` | `{"h2_headings": ["Our Mission", ...]}` |
| `PDF_TOO_LARGE` | `size_kb`, `limit_kb` | `{"size_kb": 12500, "limit_kb": 10240}` |

---

## Severity levels

- 🔴 **Critical** — Fix first; directly harms search visibility or breaks the page for visitors
- 🟡 **Warning** — Should be fixed; will measurably improve results
- 🔵 **Info** — Worth knowing; low urgency or informational only

---

## METADATA

---

### TITLE_MISSING
**Severity:** 🔴 critical | **Impact:** 9 | **Effort:** 1

**What it is**
This page has no `<title>` tag. The title is the clickable headline shown in search results and in the browser tab.

**Why it matters**
Without a title, Google generates one automatically — usually by pulling text from the page, often poorly. This directly harms click-through rates from search results.

**How to fix**
Add a title tag between 30–60 characters that clearly describes the page. In WordPress, use the SEO Title field in Yoast SEO or Rank Math on the page's edit screen.

---

### TITLE_TOO_SHORT
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 1

**What it is**
The page title is under 30 characters — too short to give search engines enough context.

**Why it matters**
Short titles often lack keywords or context, reducing how often the page appears in relevant searches.

**How to fix**
Expand to 30–60 characters. Include the page topic and your organisation name — e.g., `About Us — Living Systems Counselling` instead of `About`.

---

### TITLE_TOO_LONG
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 1

**What it is**
The page title exceeds 60 characters. Google typically cuts titles off at around 60 characters in search results.

**Why it matters**
The most distinguishing part of the title — often at the end — is hidden in search results, making the listing less informative.

**How to fix**
Shorten to under 60 characters. Put the specific page topic first, then the organisation name.

---

### TITLE_DUPLICATE
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

**What it is**
Two or more pages share exactly the same title.

**Why it matters**
Duplicate titles make it harder for search engines to tell pages apart. They may only show one of the duplicates in results, and it may not be the one you want.

**How to fix**
Write a unique title for each page that reflects its specific content.

---

### META_DESC_MISSING
**Severity:** 🔴 critical | **Impact:** 7 | **Effort:** 1

**What it is**
No meta description tag. The meta description is the short paragraph below the title in search results.

**Why it matters**
Without one, Google writes its own — usually unhelpful. A good description increases the likelihood that people click through to your site.

**How to fix**
Add a 70–160 character description summarising what visitors will find on this page. In WordPress, use the Meta Description field in Yoast SEO or Rank Math.

---

### META_DESC_TOO_SHORT
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 1

The meta description is under 70 characters. Expand it to give search engines and visitors more context (70–160 characters).

---

### META_DESC_TOO_LONG
**Severity:** 🟡 warning | **Impact:** 3 | **Effort:** 1

The meta description exceeds 160 characters and will be cut off in search results. Shorten it to under 160 characters.

---

### META_DESC_DUPLICATE
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

Two or more pages share the same meta description. Write a unique description for each page that reflects its specific content.

---

### TITLE_META_DUPLICATE_PAIR
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2

Both the title and meta description are duplicated on another page. Update both to be unique. This is more serious than either duplicate alone.

---

### OG_TITLE_MISSING
**Severity:** 🔵 info | **Impact:** 4 | **Effort:** 1

**What it is**
No Open Graph title tag (`<meta property="og:title">`). This controls the headline shown when the page is shared on social media.

**How to fix**
Add an `og:title` tag. Yoast SEO and Rank Math set this automatically based on your SEO title.

---

### OG_DESC_MISSING
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 1

No Open Graph description tag. This controls the preview text shown when the page is shared on social media. Add `<meta property="og:description">`.

---

### OG_IMAGE_MISSING
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 1

**What it is**
This page has no `og:image` meta tag. The Open Graph image controls the preview image shown when your page is shared on Facebook, LinkedIn, and other social platforms.

**Why it matters**
Posts shared without a preview image get significantly less engagement. For nonprofits relying on social media for donations and awareness, missing preview images directly reduce reach.

**How to fix**
Add `<meta property="og:image" content="https://yoursite.com/image.jpg">`. Use a high-quality image at least 1200x630 pixels. In WordPress, set this in the Yoast or Rank Math Social tab on each page.

---

### TWITTER_CARD_MISSING
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 1

**What it is**
This page has no `<meta name="twitter:card">` tag. Twitter Cards control how your page appears when shared on Twitter/X.

**Why it matters**
Without a Twitter Card tag, links shared on Twitter/X appear as plain URLs without a rich preview. Tweets with rich previews get significantly more engagement than plain text links.

**How to fix**
Add `<meta name="twitter:card" content="summary_large_image">` to the page `<head>`. Most SEO plugins (Yoast, Rank Math) have a Twitter/Social tab where you can configure this.

---

### CANONICAL_MISSING
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2

**What it is**
This page has query string parameters or is a near-duplicate of another page, but has no canonical tag telling search engines which URL is preferred.

**Why it matters**
Without a canonical, search engines may split ranking signals across multiple URL variants or duplicate pages, weakening all of them.

**How to fix**
Add `<link rel="canonical" href="[preferred-url]">` to the page head. Most SEO plugins handle this automatically.

---

### CANONICAL_SELF_MISSING
**Severity:** 🔵 info | **Impact:** 5 | **Effort:** 1

**What it is**
This indexable page has no canonical tag at all. A self-referencing canonical (`<link rel="canonical" href="[this-url]">`) is a best-practice signal confirming which URL is the preferred version.

**Why it matters**
Without it, if your page is accessed via multiple URL variants (with/without www, with/without trailing slash, via tracking parameters), search engines must guess which version to index.

**How to fix**
Add a self-referencing canonical. Yoast SEO and Rank Math do this automatically if enabled — check that the feature is turned on.

---

### CANONICAL_EXTERNAL
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

The canonical tag on this page points to a URL on a different domain. This tells search engines to treat a different site's page as the authoritative version of this content. Verify this is intentional.

---

### LANG_MISSING
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 1

**What it is**
The `<html>` element is missing a `lang` attribute (e.g., `lang="en"`).

**Why it matters**
Screen readers use the lang attribute to choose correct pronunciation rules. Search engines use it to match content to language-specific searches. It is also required for WCAG accessibility compliance.

**How to fix**
Add `lang="en"` (or the relevant language code) to your `<html>` tag. Most WordPress themes include this by default — if it is missing, the theme may need updating.

---

### TITLE_H1_MISMATCH
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2

**What it is**
The page title and the H1 heading share no significant words. Before comparing, the crawler strips a site-name suffix from the title (text after `|`, `-`, `–`, `—`, `·`) and removes common stop words.

**Why it matters**
Visitors click based on the title they see in search results. If the heading on the page describes something different, it creates confusion and increases bounce rates.

**How to fix**
Ensure the title and H1 both describe the same topic. They do not need to be identical — `About Us | My Charity` and `About Us` is fine. But `Contact Us | My Charity` and `Donate Today` is a problem.

**False positives — theme-injected banner H1s**
Some WordPress themes (Salient, Avada, Divi, etc.) inject the parent-page title as an H1 banner on every sub-page. For example, a page titled "Bowen Family Systems Theory" may have an H1 of "Clinical Internship Programs" from its parent page's banner. TalkingToad suppresses this flag automatically when the title matches an H2 on the same page. For full suppression across all H1 checks, enable **Ignore banner H1s** in Advanced Settings or add the banner text to the **Suppress H1 text** list.

---

### FAVICON_MISSING
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 2

No favicon found on the homepage. The favicon is the small icon that appears in browser tabs and bookmarks. Most CMS platforms add one by default — check your theme or site settings.

---

## HEADINGS

---

### H1_MISSING
**Severity:** 🔴 critical | **Impact:** 8 | **Effort:** 1

**What it is**
No H1 heading on the page.

**Why it matters**
The H1 is the primary signal to search engines about what the page is about. Missing H1 is one of the most impactful technical SEO errors.

**How to fix**
Add a single H1 heading that clearly states the main topic of the page. In WordPress, the page title you set in the editor typically becomes the H1.

---

### H1_MULTIPLE
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2

More than one H1 on the page. Each page should have exactly one H1. Remove or demote the extra H1 tags to H2.

---

### HEADING_SKIP
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 3

Heading levels are skipped — for example, the page jumps from H1 straight to H3 with no H2 in between. This breaks the document outline that screen readers use to navigate. Fix the heading structure so levels are used in order.

---

### HEADING_EMPTY
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 1

**What it is**
One or more heading tags (`<h2>`, `<h3>`, etc.) on this page contain no text. The tag exists in the HTML but is either completely empty or contains only whitespace.

**Why it matters**
Empty headings break the document outline that screen readers use to navigate. A screen reader user who jumps to headings will land on a blank heading with no context. Search engines also see an empty heading as a structural error.

**How to fix**
Find the empty heading tags in your page editor and either add descriptive text or remove the heading tag entirely. In WordPress, switch to the Code Editor view to locate empty `<h2></h2>` or `<h3></h3>` tags.

---

## BROKEN LINKS

---

### BROKEN_LINK_404
**Severity:** 🔴 critical | **Impact:** 10 | **Effort:** 2

**What it is**
A link on your site points to a URL that returns 404 Not Found. This applies both to external links on your pages and to internal pages that have been deleted or moved.

**Why it matters**
Dead links damage visitor trust and waste crawl budget. An internal 404 is especially damaging — it means a page your own site links to does not exist.

**How to fix**
Remove or update the link. If the destination page was moved, set up a 301 redirect from the old URL to the new one.

---

### BROKEN_LINK_410
**Severity:** 🔴 critical | **Impact:** 8 | **Effort:** 2

The link destination returns 410 Gone — the page has been permanently removed. Remove this link. Unlike a 404, a 410 explicitly tells search engines the page is gone for good.

---

### BROKEN_LINK_5XX
**Severity:** 🔴 critical | **Impact:** 7 | **Effort:** 3

The link destination returns a 5xx server error. The destination server is failing to respond. If the problem persists over time, remove or replace the link.

---

### BROKEN_LINK_503
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 3

**What it is**
The link destination returns 503 Service Unavailable. This is commonly returned by bot-protection systems (Cloudflare, Akamai) even when the page loads fine for real visitors.

**Why it matters**
This may be a false positive — the destination site may be working correctly but blocking automated checks.

**How to fix**
Click the link manually to confirm it works in a browser. If it loads correctly for you, no action is needed. If it consistently fails for real users too, the destination may be down.

---

### IMG_BROKEN
**Severity:** 🔴 critical | **Impact:** 8 | **Effort:** 2

**What it is**
An image on this page returns a 4xx or 5xx error — the image file does not exist or cannot be loaded.

**Why it matters**
Broken images display as broken-image placeholders visible to all visitors. They also represent missed opportunities for image search visibility.

**How to fix**
Replace or remove the broken image. Use your CMS media library to re-upload the file or correct the image URL.

---

### EXTERNAL_LINK_TIMEOUT
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 1

An external link did not respond within the timeout period. The destination site may be slow or temporarily unavailable. Click the link manually to confirm it loads for real visitors.

---

### EXTERNAL_LINK_SKIPPED
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 1

This link points to a platform (LinkedIn, Facebook, Instagram, etc.) that blocks automated requests. The link could not be verified by the crawler. Open it in a browser to confirm it is working.

---

## REDIRECTS

---

### INTERNAL_REDIRECT_301
**Severity:** 🔵 info | **Impact:** 4 | **Effort:** 1

**What it is**
An internal link on your site points to a URL that immediately redirects with a 301. The link works, but adds an unnecessary extra HTTP round-trip for every visitor.

**How to fix**
Update the internal link to point directly to the final destination URL. This eliminates the redirect for both visitors and search engines.

---

### REDIRECT_301
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 2

An external URL that was checked returns a 301 permanent redirect. This is informational — update any links pointing here to use the final destination directly.

---

### REDIRECT_302
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

A URL returns a 302 temporary redirect. If this redirect is actually permanent, change it to a 301 so search engines transfer ranking signals to the final URL.

---

### REDIRECT_CHAIN
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 3

This URL redirects through two or more intermediate hops before reaching the final destination (e.g., A → B → C). Each hop slows down page loading and slightly dilutes ranking signals. Update the first redirect to point directly to the final URL.

---

### REDIRECT_LOOP
**Severity:** 🔴 critical | **Impact:** 10 | **Effort:** 4

**What it is**
This URL is part of an infinite redirect cycle — it eventually redirects back to itself. Browsers show a "too many redirects" error.

**Why it matters**
The page is completely inaccessible to visitors and search engines.

**How to fix**
Check your CMS permalink settings, redirect plugin rules, or `.htaccess` file for conflicting rules. Contact your web developer if you are unsure.

---

### REDIRECT_TRAILING_SLASH
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 1

Your server or CMS automatically adds or removes a trailing slash from the URL. This redirect is handled automatically — it is informational. To eliminate the extra round-trip, update internal links to use the canonical form the server expects.

---

### REDIRECT_CASE_NORMALISE
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 1

Your server automatically redirects uppercase URL paths to lowercase. This redirect is handled automatically. Update internal links to use lowercase URLs to avoid the extra redirect.

---

### META_REFRESH_REDIRECT
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

This page uses an HTML `<meta http-equiv="refresh">` tag to redirect visitors. Replace it with a server-side 301 redirect — meta refresh redirects pass ranking signals less reliably and create a visible flash of the old page before redirecting.

---

## CRAWLABILITY

---

### ROBOTS_BLOCKED
**Severity:** 🟡 warning | **Impact:** 9 | **Effort:** 2

**What it is**
Your `robots.txt` file blocks search engine crawlers from accessing this page. The crawler found the URL via links but cannot audit its content.

**Why it matters**
Search engines cannot index this page, so it will not appear in search results. If this is intentional (admin areas, private content), it is correct. If not, the page is invisible to search engines.

**How to fix**
Review your `robots.txt` file and remove or narrow the Disallow rule for this URL. Test changes in Google Search Console's robots.txt tester before saving.

---

### NOINDEX_META
**Severity:** 🟡 warning | **Impact:** 10 | **Effort:** 1

This page has `<meta name="robots" content="noindex">`. Search engines will visit it but not include it in results. If this is intentional, no action is needed. If not, remove the noindex tag. In WordPress, check the 'Search Appearance' section in Yoast SEO or Rank Math.

---

### NOINDEX_HEADER
**Severity:** 🟡 warning | **Impact:** 10 | **Effort:** 2

The server sends an `X-Robots-Tag: noindex` HTTP header. This hides the page from search results. It is set at the server level — check your server config, hosting settings, or any SEO/caching plugins. Also check WordPress Settings → Reading for the 'Discourage search engines' checkbox.

---

### PAGE_TIMEOUT
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 3

This page did not respond within the timeout period. Check the page manually. A persistent timeout may indicate a slow server, a heavy page, or a broken URL.

---

### LOGIN_REDIRECT
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 1

This URL redirects to a login page. Search engines cannot access it, so it will not appear in search results. If the page should be public, remove the login requirement. If it is intentionally private, no action is needed.

---

### THIN_CONTENT
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 4

**What it is**
Fewer than 300 words of visible body text (excluding navigation, headers, and footers).

**Why it matters**
Google considers thin content low-value. Consistently thin pages can reduce the ranking ability of the entire site.

**How to fix**
Expand the page with useful, relevant content. If the page is intentionally minimal (e.g., a contact page), consider adding a noindex tag.

---

### HIGH_CRAWL_DEPTH
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 3

This page is more than 4 clicks from the homepage. Search engines crawl deeply buried pages less frequently. Improve internal linking so the page can be reached in 3–4 clicks.

---

### ORPHAN_PAGE
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 4

**What it is**
No other crawled page links to this page. Search engines may not discover it reliably.

**Why it matters**
Pages with no inbound links receive no internal PageRank signals and may not be crawled regularly after initial indexing.

**How to fix**
Add at least one internal link to this page from a navigation menu, a hub page, or a relevant content page.

---

### CONTENT_STALE
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 4

**What it is**
This page has not been modified in over 12 months, based on the Last-Modified HTTP header sent by the server.

**Why it matters**
Search engines use content freshness as a ranking signal. Stale content can gradually lose ranking position. Visitors may also lose trust in outdated information, especially for nonprofits where program details, staff, and event information change frequently.

**How to fix**
Review and refresh the page content. Update dates, statistics, staff names, and program details. Even small edits signal freshness to search engines. If the content is evergreen and still accurate, consider republishing it with a current date.

---

### MISSING_VIEWPORT_META
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 1

**What it is**
The page is missing `<meta name="viewport" content="width=device-width, initial-scale=1">`.

**Why it matters**
Without it, mobile browsers render the page at desktop width and zoom out — making text tiny and buttons nearly impossible to tap. Google uses mobile-friendliness as a ranking factor.

**How to fix**
Add the viewport meta tag to the page `<head>`. In WordPress, this is part of the theme — if it is missing, the theme likely needs updating.

---

### SCHEMA_MISSING
**Severity:** 🔵 info | **Impact:** 5 | **Effort:** 2

**What it is**
No structured data markup (JSON-LD or microdata) found on this indexable page.

**Why it matters**
Schema markup helps search engines understand your organisation, events, services, and FAQs — potentially unlocking richer search result listings.

**How to fix**
Add at minimum an `Organisation` schema to your homepage. Yoast SEO Premium and Rank Math include schema tools. Google's Structured Data Markup Helper (search.google.com/structured-data/helper) can generate the markup.

---

### INTERNAL_NOFOLLOW
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

**What it is**
An internal link carries `rel="nofollow"`. This tells search engines not to follow the link or pass PageRank through it.

**Why it matters**
Nofollow on internal links is almost always a mistake. It prevents search engines from discovering linked pages and dilutes the site's internal link graph.

**How to fix**
Remove `nofollow` from internal links. Reserve `rel="nofollow"` for links to external or user-generated content.

---

### LINK_EMPTY_ANCHOR
**Severity:** 🟡 warning | **Impact:** 7 | **Effort:** 2

**What it is**
A link has no visible anchor text — the clickable text between `<a>` and `</a>` is empty. This includes icon-only links whose image has no alt text.

**Why it matters**
Screen readers cannot describe where the link goes. Search engines also use anchor text as a relevance signal.

**How to fix**
Add descriptive text inside the link. For icon-only links, add `aria-label="Donate now"` or similar.

---

### ANCHOR_TEXT_GENERIC
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

**What it is**
One or more links use generic anchor text like 'click here', 'read more', 'learn more', or 'here'. These phrases tell neither the reader nor search engines what the linked page is about.

**Why it matters**
Search engines use anchor text to understand the content of linked pages. Generic text wastes this signal entirely. Screen reader users who navigate by links hear a list of 'click here, click here, click here' with no context.

**How to fix**
Replace generic text with descriptive labels. Instead of 'Click here to donate', write 'Donate to support our programs'. Instead of 'Read more', write 'Read about our community drumming workshops'. The link text should make sense out of context.

---

### PAGE_SIZE_LARGE
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 3

**What it is**
The HTML response for this page exceeds the size threshold (default 300 KB; configurable per crawl). This measures the HTML document itself, not images, scripts, or stylesheets loaded separately.

**Why it matters**
Slow to download, especially on mobile. Large HTML is often caused by excessive inline scripts, page-builder markup, or very long pages.

**How to fix**
Move inline scripts to external files, remove unused page builder blocks, and consider lazy-loading off-screen content. Google PageSpeed Insights can identify specific causes.

---

### PDF_TOO_LARGE
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

A PDF on your site exceeds 10 MB. Large PDFs are slow to download on mobile and may be skipped by crawlers. Compress it at ilovepdf.com or smallpdf.com.

---

### IMG_ALT_MISSING
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

**What it is**
One or more `<img>` tags are missing an alt attribute, or the alt attribute is empty on an informational image.

**Why it matters**
Screen reader users cannot understand what the image shows. Search engines also cannot index images without alt text.

**How to fix**
Add a descriptive alt attribute to every image: `alt="Counsellor speaking with a young person in an office"`. In WordPress, set alt text in the Media Library or the block editor's image settings.

---

### IMG_OVERSIZED
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

An image file exceeds 200 KB. Large images slow page loading significantly, especially on mobile. Compress using Squoosh (squoosh.app), TinyPNG, or ImageOptim before uploading.

---

### IMG_ALT_TOO_SHORT
**Severity:** 🟡 warning | **Impact:** 3 | **Effort:** 1

**What it is**
Alt text is fewer than 5 characters — too brief to meaningfully describe the image content.

**Why it matters**
Very short alt text fails to provide adequate context for screen reader users. Search engines also benefit from descriptive alt text — a one-word label provides minimal SEO value.

**How to fix**
Expand the alt text to describe what the image actually shows. Instead of 'team', write 'Staff members gathered at our annual fundraising gala'. Aim for 5-125 characters. In WordPress, edit the image in the Media Library.

---

### IMG_ALT_TOO_LONG
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 1

**What it is**
Alt text exceeds 125 characters. Overly long alt text can be overwhelming for screen reader users and may dilute keyword relevance.

**Why it matters**
Screen reader users must listen to the entire alt text before they can move on. Overly long descriptions slow down navigation and may cause users to skip images entirely.

**How to fix**
Shorten the alt text to 125 characters or fewer. Focus on the most important aspect of the image. If a longer description is genuinely needed (e.g. for a complex infographic), consider using a separate visible caption or linking to a full text description.

---

### IMG_ALT_GENERIC
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 1

**What it is**
Alt text is a generic placeholder word like 'image', 'photo', 'picture', 'icon', or 'graphic'.

**Why it matters**
Generic alt text provides no useful information. A screen reader user hears 'image' but learns nothing about what the image shows. Search engines cannot determine the image's content or match it to relevant queries.

**How to fix**
Replace the generic text with a description of what the image actually shows. For example, change 'photo' to 'A counsellor meeting with a young family in our community centre'. In WordPress, click on the image in the Media Library and update the Alt Text field.

---

### IMG_ALT_DUP_FILENAME
**Severity:** 🟡 warning | **Impact:** 3 | **Effort:** 1

**What it is**
Alt text matches the filename (e.g. 'DSC_0042' or 'hero-banner-v2'). Filenames rarely describe image content meaningfully.

**Why it matters**
Machine-generated filenames provide no value for accessibility or SEO. Screen reader users hear text like 'DSC underscore zero zero four two' instead of a useful description.

**How to fix**
Write alt text that describes the actual content of the image, ignoring the filename. In WordPress, when uploading images, the Media Library may auto-populate alt text from the filename — always review and replace this with a proper description.

---

### IMG_ALT_MISUSED
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 2

**What it is**
A decorative image has alt text. Decorative images should use `alt=""` so screen readers skip them entirely.

**Why it matters**
When a decorative image has alt text, screen readers announce it unnecessarily, cluttering the listening experience. Decorative images include visual flourishes, spacers, and icons that repeat information already provided in text.

**How to fix**
If the image is truly decorative, remove its alt text or set `alt=""`. If the image does convey information, remove the `role='presentation'` or `aria-hidden` attribute and keep meaningful alt text. Choose one approach — don't mix both.

---

### IMG_SLOW_LOAD
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

**What it is**
Image took more than 1 second to download. Slow-loading images can significantly delay page rendering.

**Why it matters**
Visitors may see blank spaces or loading placeholders while waiting for slow images. Core Web Vitals (Google's page experience metrics) are negatively affected by slow resource loading. On mobile connections, a 1-second delay per image can add up quickly.

**How to fix**
Reduce the image file size through compression or format conversion (JPEG to WebP). Ensure images are appropriately sized for their display dimensions. Consider lazy loading images below the fold so they don't block initial page rendering.

---

### IMG_OVERSCALED
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 3

**What it is**
Image intrinsic size is more than 2x its display size on the page. For example, a 2000px wide image displayed at 400px wide is being scaled down by 5x.

**Why it matters**
Overscaled images waste bandwidth — visitors download far more data than is actually needed to display the image. This slows page loading and wastes mobile data.

**How to fix**
Resize the image to match its display size before uploading. If the image appears at 600px wide on desktop, resize it to approximately 1200px wide (2x for retina displays). Use srcset to serve different sizes to different devices.

---

### IMG_POOR_COMPRESSION
**Severity:** 🔵 info | **Impact:** 4 | **Effort:** 2

**What it is**
Image has a high bytes-per-pixel ratio and could be compressed further without visible quality loss.

**Why it matters**
Poorly compressed images increase page weight and loading time unnecessarily. Modern compression tools can often reduce file size by 50-80% with no perceptible quality difference.

**How to fix**
Re-compress the image using tools like Squoosh (squoosh.app), TinyPNG, or ImageOptim. For photographs, try quality settings around 75-85%. For graphics with flat colors, use PNG-8 or SVG instead of full-color PNG-24.

---

### IMG_FORMAT_LEGACY
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 2

**What it is**
Large image using JPEG/PNG/GIF instead of modern formats like WebP or AVIF. Legacy formats typically produce larger file sizes for equivalent visual quality.

**Why it matters**
WebP images are typically 25-35% smaller than equivalent JPEG or PNG files. For sites with many images, this adds up to significant bandwidth savings and faster page loads. All modern browsers support WebP.

**How to fix**
Convert images to WebP format using tools like Squoosh, cwebp, or an image optimization plugin. In WordPress, plugins like ShortPixel, Imagify, or Smush can automatically convert uploaded images to WebP.

---

### IMG_NO_SRCSET
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 3

**What it is**
Image is scaled down for display but has no srcset attribute for responsive delivery. A srcset allows browsers to choose the most appropriately sized image file.

**Why it matters**
Without srcset, mobile users download the same large image file as desktop users, even though they only need a fraction of those pixels. This wastes bandwidth and slows page loading on mobile devices.

**How to fix**
Add a srcset attribute with multiple image sizes, or use WordPress's built-in responsive image support (which automatically generates srcset for uploaded images). When adding images manually, include 2-3 size variants (e.g. 400w, 800w, 1200w).

---

### IMG_DUPLICATE_CONTENT
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 2

**What it is**
Same image content is served from multiple different URLs on your site. The crawler detected identical image data (via content hash) being loaded from different file paths.

**Why it matters**
Duplicate images waste storage space and may confuse search engine image indexing. Each URL is treated as a separate image, potentially splitting any image search ranking value.

**How to fix**
Consolidate duplicate images to a single canonical URL. Update any pages loading the duplicate version to use the primary URL. In WordPress, delete duplicate entries from the Media Library and update posts that reference them.

---

### AMPHTML_BROKEN
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 3

This page declares an AMP version via `<link rel="amphtml">`, but the linked AMP URL returns an error. Fix the AMP URL or remove the `amphtml` link if AMP is no longer in use.

---

### PAGINATION_LINKS_PRESENT
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 2

This page declares `<link rel="next">` or `<link rel="prev">` pagination elements. This is informational — no action required unless you have specific pagination SEO concerns.

---

## SITEMAP

---

### SITEMAP_MISSING
**Severity:** 🔵 info | **Impact:** 6 | **Effort:** 2

**What it is**
No XML sitemap found at `/sitemap.xml` or referenced in `robots.txt`.

**Why it matters**
Without a sitemap, search engines must discover all pages by following links. Pages with few inbound links may never be found.

**How to fix**
Create an XML sitemap and submit it to Google Search Console. In WordPress, Yoast SEO and Rank Math generate one automatically at `/sitemap.xml`. Add `Sitemap: https://yoursite.com/sitemap.xml` to your `robots.txt`.

---

### NOT_IN_SITEMAP
**Severity:** 🔵 info | **Impact:** 4 | **Effort:** 1

This page was found by following links but is not listed in your XML sitemap. Search engines may crawl it less frequently. Check whether an SEO plugin is excluding it, or add it manually.

---

## SECURITY

---

### HTTP_PAGE
**Severity:** 🔴 critical | **Impact:** 9 | **Effort:** 2

**What it is**
This page is served over plain HTTP, not HTTPS. HTTP connections are unencrypted.

**Why it matters**
Browsers display a 'Not Secure' warning. Google has used HTTPS as a ranking signal since 2014. Any personal data submitted over HTTP is exposed to interception.

**How to fix**
Install an SSL/TLS certificate (Let's Encrypt is free) and configure a 301 redirect from all `http://` URLs to `https://`. Most hosting control panels offer a one-click 'Force HTTPS' option.

---

### HTTPS_REDIRECT_MISSING
**Severity:** 🔴 critical | **Impact:** 9 | **Effort:** 2

**What it is**
The HTTP version of this site (`http://...`) does not redirect to HTTPS.

**Why it matters**
Visitors who type the address without `https://` land on an insecure version. Search engines treat `http://` and `https://` as separate competing URLs, splitting your SEO value.

**How to fix**
Configure a 301 redirect from all `http://` URLs to `https://`. In hosting control panels look for 'Force HTTPS'. For Apache servers, add a redirect rule to `.htaccess`. Cloudflare can also handle this automatically.

---

### MIXED_CONTENT
**Severity:** 🟡 warning | **Impact:** 6 | **Effort:** 2

This HTTPS page loads one or more resources (images, scripts, stylesheets) over HTTP. Browsers block or warn about insecure resources. Update all resource URLs to use `https://`. In WordPress, the 'Really Simple SSL' plugin can scan and fix `http://` URLs in the database.

---

### MISSING_HSTS
**Severity:** 🔵 info | **Impact:** 4 | **Effort:** 2

**What it is**
This HTTPS page does not send a `Strict-Transport-Security` (HSTS) header.

**Why it matters**
Without HSTS, attackers can use SSL stripping to downgrade connections from HTTPS to HTTP before the browser receives a response.

**How to fix**
Add the header to all HTTPS responses: `Strict-Transport-Security: max-age=31536000; includeSubDomains`. Ask your host or developer if you are unsure how to add response headers.

---

### UNSAFE_CROSS_ORIGIN_LINK
**Severity:** 🔵 info | **Impact:** 3 | **Effort:** 1

A link to an external site opens in a new tab (`target="_blank"`) without `rel="noopener"`. This exposes the original tab to potential redirect by the external page. Add `rel="noopener noreferrer"` to all external `target="_blank"` links. Modern WordPress adds this automatically.

---

### WWW_CANONICALIZATION
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 2

**What it is**
Both the www version (e.g. `www.yoursite.com`) and the non-www version (`yoursite.com`) of your site return a page without redirecting to each other.

**Why it matters**
Search engines treat `www.example.com` and `example.com` as two separate websites. All backlinks, social shares, and internal links are split between two versions, diluting domain authority and search rankings.

**How to fix**
Choose one version (www or non-www) as your canonical domain and configure a 301 redirect from the other. In hosting control panels look for a 'Primary Domain' or 'Redirect' setting. In Cloudflare, use a Page Rule. Also set your preferred domain in Google Search Console.

---

## URL STRUCTURE

---

### URL_UPPERCASE
**Severity:** 🟡 warning | **Impact:** 3 | **Effort:** 2

The URL path contains uppercase letters (e.g., `/About-Us`). Most servers auto-redirect these to lowercase, creating an unnecessary extra redirect. Update internal links and page slugs to use lowercase only.

---

### URL_HAS_SPACES
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 3

The URL contains encoded spaces (`%20`). Spaces in URLs look broken when pasted and can cause link-sharing failures. Replace spaces with hyphens.

---

### URL_HAS_UNDERSCORES
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 4

The URL path uses underscores instead of hyphens as word separators. Google treats underscores as word-joiners, not separators. Use hyphens instead.

---

### URL_TOO_LONG
**Severity:** 🔵 info | **Impact:** 2 | **Effort:** 4

The URL exceeds 200 characters. Very long URLs are truncated in search results and look untrustworthy to users. Shorten the slug to the key words only.

---

---

## AI READINESS

---

### LLMS_TXT_MISSING
**Severity:** 🔵 info | **Impact:** 6 | **Effort:** 1

**What it is**
No `/llms.txt` file found at the site root.

**Why it matters**
`llms.txt` is a new standard for providing AI agents (Gemini, ChatGPT, Perplexity) with a curated map of your site's most important content. Without it, AI agents must crawl your entire site, which can lead to "hallucinations" or outdated information in AI summaries.

**How to fix**
Create a plain text file at `yoursite.com/llms.txt`. Use the **Generate llms.txt** utility in TalkingToad to create a curated list of high-value URLs.

---

### LLMS_TXT_INVALID
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

**What it is**
An `/llms.txt` file exists but does not follow the standard format. It may have the wrong MIME type (not `text/plain`), be missing Markdown structure (H1, blockquote), or contain more than 20 URLs.

**Why it matters**
AI agents may fail to parse an incorrectly formatted file. Curating more than 20 links reduces the "signal-to-noise" ratio for AI retrieval.

**How to fix**
Ensure the file is served as `text/plain` and includes a single `# H1` title, a `> blockquote` summary, and 10–20 high-value links.

---

### SEMANTIC_DENSITY_LOW
**Severity:** 🟡 warning | **Impact:** 5 | **Effort:** 3

**What it is**
The Text-to-HTML ratio is below 10%. The page has significantly more code (scripts, styles, nested divs) than readable text.

**Why it matters**
High code-bloat "confuses" AI tokenizers and retrieval engines (RAG). Cleaning up unnecessary markup ensures AI agents can accurately extract and cite your content using fewer tokens.

**How to fix**
Remove unused page-builder blocks, move inline CSS/JS to external files, and simplify deeply nested HTML structures.

---

### DOCUMENT_PROPS_MISSING
**Severity:** 🟡 warning | **Impact:** 4 | **Effort:** 2

**What it is**
A PDF file is missing internal `Title` or `Subject` metadata in its document properties.

**Why it matters**
AI systems use internal PDF properties (not the file name) for source labels and citations. Missing metadata results in unprofessional or generic labels in AI-generated answers.

**How to fix**
Open the PDF in a reader (Adobe Acrobat, etc.) and fill in the Title and Subject under **File → Properties**. Re-upload the file to your site.

---

### JSON_LD_MISSING
**Severity:** 🟡 warning | **Impact:** 7 | **Effort:** 2

**What it is**
No JSON-LD structured data (`<script type="application/ld+json">`) found on an indexable page.

**Why it matters**
Schema is the "Knowledge Graph" for AI. While search engines can parse Microdata, AI systems prefer the structured JSON-LD format for RAG-based retrieval.

**How to fix**
Add JSON-LD markup to your pages. At minimum, ensure your homepage has `Organization` schema.

---

### CONVERSATIONAL_H2_MISSING
**Severity:** 🔵 info | **Impact:** 4 | **Effort:** 2

**What it is**
H2 headings do not use interrogative words (How, What, Why, Who).

**Why it matters**
LLMs prefer direct question-answer pairings. Conversational headings make your content more "quotable" and easier for AI to match to natural-language user queries.

**How to fix**
Rewrite some subheadings as questions. For example, change `Our Impact` to `What is our impact on the community?`.

---

---

## GEO ANALYZER v2.1

GEO (Generative Engine Optimization) checks measure how well content is structured for retrieval and citation by AI systems (Google AI Overviews, Perplexity, ChatGPT). Checks are grouped by evidence tier:

- **Empirical** — Measured by Aggarwal et al. (2023); controlled evidence that these tactics increase AI citation rates
- **Mechanistic** — Derived from known retrieval mechanics (chunking, rendering, indexing)
- **Conventional** — Industry practice; plausible but not independently measured

---

### STATISTICS_COUNT_LOW
**Severity:** 🟡 warning | **Evidence:** Empirical | **Impact:** 7 | **Effort:** 2

**What it is**
A 500+ word page opens with no statistics, percentages, data ranges, or numeric claims in its first 150 words.

**Why it matters**
Aggarwal et al. (2023) found that pages with statistics are measurably more likely to be cited by AI systems. Statistics signal factual authority and give AI systems quotable, specific claims rather than vague prose.

**How to fix**
Add at least one specific numeric claim in the opening paragraph: research figures, organisation reach (e.g., "We served 2,400 families last year"), dates, percentages, or measurements. Even a single well-placed statistic materially increases AI quotability.

---

### EXTERNAL_CITATIONS_LOW
**Severity:** 🟡 warning | **Evidence:** Empirical | **Impact:** 7 | **Effort:** 2

**What it is**
A 500+ word page has no outbound links to external sources anywhere in the body text.

**Why it matters**
Aggarwal et al. (2023) found that pages citing external sources are measurably more cited by AI systems. External links signal that your claims are grounded in broader evidence and allow AI systems to cross-reference your assertions.

**How to fix**
Link to at least one or two authoritative external sources — government statistics, research papers, peer organisations, or official documentation. `.gov`, `.edu`, and peer-reviewed sources carry the most weight.

---

### QUOTATIONS_MISSING
**Severity:** 🟡 warning | **Evidence:** Empirical | **Impact:** 6 | **Effort:** 2

**What it is**
A 500+ word page contains no direct quotations from named sources — no `<blockquote>` tags and no attribution patterns ("according to", "stated that", etc.).

**Why it matters**
Aggarwal et al. (2023) found quotations measurably increase AI citation rates. Direct quotes from named authorities increase perceived credibility and give AI systems citable soundbites.

**How to fix**
Add one or more `<blockquote>` quotes from relevant experts, stakeholders, or published sources. Include the source name. Even a sentence-length attribution ("According to the WHO, …") helps.

---

### ORPHAN_CLAIM_TECHNICAL
**Severity:** 🟡 warning | **Evidence:** Empirical | **Impact:** 6 | **Effort:** 2

**What it is**
A technical or how-to page makes three or more specific factual claims with no accompanying source links or attributions.

**Why it matters**
Unsourced claims in technical content reduce AI citation likelihood. AI systems prefer content where specific assertions are traceable to a source. Orphaned claims also make content harder for readers to verify.

**How to fix**
Add a source link or attribution phrase next to each specific factual claim: "According to MDN Web Docs, …", "Research by [source] found …", or a hyperlink to the source.

---

### RAW_HTML_JS_DEPENDENT
**Severity:** 🟡 warning | **Evidence:** Mechanistic | **Impact:** 6 | **Effort:** 3

**What it is**
The raw HTML response is a near-empty SPA shell (detects `<div id="root">` or similar React/Vue mount points with a text-to-HTML ratio below 5%). All visible content is loaded via JavaScript after initial page load.

**Why it matters**
AI crawlers that only fetch raw HTML (not all do JavaScript execution) will see an empty page. Even crawlers that execute JavaScript may miss content due to timing issues. This is the highest-risk rendering pattern for AI indexing.

**How to fix**
Enable server-side rendering (SSR) or static site generation (SSG) for key pages. Frameworks like Next.js, Nuxt, and Gatsby support this. At minimum, ensure critical content (H1, first paragraph, key claims) is present in the raw HTML response.

---

### JS_RENDERED_CONTENT_DIFFERS
**Severity:** 🟡 warning | **Evidence:** Mechanistic | **Impact:** 6 | **Effort:** 4

**What it is**
JavaScript execution adds more than 20% new content tokens versus the raw HTML. The page has substantial content that only appears after JavaScript runs.

**Why it matters**
AI crawlers that skip JS execution will miss this content. Even crawlers that do run JavaScript may index an older or incomplete version. Critical content hidden behind JavaScript is effectively invisible to some AI retrieval pipelines.

**How to fix**
Move key content (product descriptions, service details, key facts) to server-rendered HTML. Reserve JavaScript for interactive UI elements, not primary information delivery.

---

### CONTENT_CLOAKING_DETECTED
**Severity:** 🔴 critical | **Evidence:** Mechanistic | **Impact:** 8 | **Effort:** 4

**What it is**
The JS-rendered page content has a topic Jaccard similarity below 0.30 versus the raw HTML — meaning the visible page is on a substantially different topic than what crawlers see in the raw response.

**Why it matters**
This pattern — different content for crawlers versus users — is called cloaking. Whether intentional or accidental (e.g., a React app loading entirely different content than the SSR shell), it can result in AI systems indexing misleading content and may violate search engine guidelines.

**How to fix**
Ensure the raw HTML and JS-rendered content cover the same topics. If the raw HTML is a loading shell, implement SSR so the meaningful content is in the initial response. If cloaking is unintentional, audit your rendering pipeline.

---

### UA_CONTENT_DIFFERS
**Severity:** 🟡 warning | **Evidence:** Mechanistic | **Impact:** 7 | **Effort:** 3

**What it is**
AI bots (GPTBot, ClaudeBot) receive significantly less content than a normal browser request — less than 80% of the JS-rendered token count. The server is serving different content based on user agent.

**Why it matters**
Intentionally or unintentionally blocking AI crawlers from your content means it won't be indexed for AI-generated answers. If your robots.txt allows these bots but your server is blocking them in practice, you have an inconsistency that harms AI visibility.

**How to fix**
Check that your CDN, WAF, and server aren't blocking or stripping content for AI user agents. If intentional, ensure your robots.txt accurately reflects this policy.

---

### FIRST_VIEWPORT_NO_ANSWER
**Severity:** 🟡 warning | **Evidence:** Mechanistic | **Impact:** 5 | **Effort:** 2

**What it is**
The first 150 words of the page contain no definition or direct answer — no "X is a …", no TL;DR, no "in short" statement, and no definitional signal.

**Why it matters**
AI systems use the first passage of a page as the primary candidate for a featured snippet or AI Overview answer. If the opening doesn't contain a clear, self-contained definition or answer, the page is unlikely to be quoted in response to direct questions.

**How to fix**
Open with a clear definition or direct answer to the core question the page addresses. For example: "OpenBrain is a personal AI memory database that…" or "TL;DR: This guide covers how to…". Place this in the first paragraph, before any context or backstory.

---

### AUTHOR_BYLINE_MISSING
**Severity:** 🟡 warning | **Evidence:** Mechanistic | **Impact:** 4 | **Effort:** 2

**What it is**
A blog post or article page (`BlogPosting`, `Article`, or `NewsArticle` JSON-LD type, or blog-path URL) has no detectable author attribution — no `rel="author"`, `itemprop="author"`, JSON-LD `author` field, or byline CSS class.

**Why it matters**
Author attribution is an E-E-A-T (Experience, Expertise, Authority, Trustworthiness) signal. AI systems and search engines use author identity to assess content credibility. Anonymous articles score lower for expertise signals.

**How to fix**
Add a visible author byline to article pages. In WordPress, ensure the author display is enabled in your theme. Add `itemprop="author"` to the byline element, or include `"author": {"@type": "Person", "name": "..."}` in your JSON-LD.

---

### DATE_PUBLISHED_MISSING
**Severity:** 🔵 info | **Evidence:** Mechanistic | **Impact:** 3 | **Effort:** 1

**What it is**
A blog post or article page has no `datePublished` in JSON-LD and no `og:article:published_time` meta tag.

**Why it matters**
AI systems and search engines use publication dates to assess content freshness and to display dates in search results. Missing dates make it harder for AI to determine whether information is current.

**How to fix**
Add `"datePublished": "2026-01-15"` to your article's JSON-LD schema. In WordPress, Yoast and Rank Math include this automatically. You can also add `<meta property="article:published_time" content="...">`.

---

### DATE_MODIFIED_MISSING
**Severity:** 🔵 info | **Evidence:** Mechanistic | **Impact:** 2 | **Effort:** 1

**What it is**
A blog post or article page has no `dateModified` in JSON-LD and no `og:article:modified_time` meta tag.

**Why it matters**
Last-modified dates signal content freshness to AI systems. A page with a recent `dateModified` is preferred over stale content when AI systems need current information.

**How to fix**
Add `"dateModified": "2026-04-01"` to your JSON-LD schema. In WordPress, update this automatically when the post is edited by configuring Yoast or Rank Math to include the modification date.

---

### CODE_BLOCK_MISSING_TECHNICAL
**Severity:** 🟡 warning | **Evidence:** Mechanistic | **Impact:** 4 | **Effort:** 2

**What it is**
A technical how-to page (URL contains `/tutorial`, `/guide`, `/how-to`, `/docs`, `/setup`, etc., with 3+ numbered steps or step-like headings) has no `<code>` or `<pre>` blocks.

**Why it matters**
Technical content without code blocks is harder for AI systems to parse as instructional content. Code blocks create structured, citable examples and signal to AI that this is authoritative technical guidance rather than marketing prose.

**How to fix**
Add `<code>` blocks for inline commands and `<pre><code>` blocks for multi-line examples, shell commands, or configuration snippets. This is especially important for any step where a reader needs to type or paste something.

---

### COMPARISON_TABLE_MISSING
**Severity:** 🔵 info | **Evidence:** Mechanistic | **Impact:** 3 | **Effort:** 2

**What it is**
A page with comparison language in a heading ("vs", "versus", "compared to", "alternatives") has no `<table>` element.

**Why it matters**
AI systems extract comparison data from tables far more reliably than from prose. A "vs" heading without a structured table means AI systems may miss or misrepresent the comparison in AI-generated answers.

**How to fix**
Add an HTML `<table>` with clear column headers comparing the options. A simple 3–5 row table with feature/attribute rows is enough. Most WordPress page builders have a table block.

---

### CHUNKS_NOT_SELF_CONTAINED
**Severity:** 🟡 warning | **Evidence:** Mechanistic | **Impact:** 5 | **Effort:** 4

**What it is**
Detected (via LLM analysis) that one or more H2/H3 sections cannot be understood without reading the surrounding context — they rely on pronouns, terms, or references defined elsewhere in the page.

**Why it matters**
AI retrieval systems chunk pages by heading sections and evaluate each chunk independently. A chunk that begins with "This works by…" without defining what "this" is, or that refers to a term explained three sections earlier, will be poorly understood when retrieved in isolation.

**How to fix**
Start each H2/H3 section with a self-contained opening sentence that re-states the subject. Avoid opening with pronouns. Each section should be understandable without reading the rest of the page.

---

### CENTRAL_CLAIM_BURIED
**Severity:** 🟡 warning | **Evidence:** Mechanistic | **Impact:** 5 | **Effort:** 3

**What it is**
Detected (via LLM analysis) that the central claim or definition of the page appears more than 150 words into the content — after backstory, context, or introductory material.

**Why it matters**
AI systems prioritise the first passage of content for featured snippet selection and AI Overview generation. If your core claim is buried after a long preamble, it will be overlooked in favour of pages that lead with the answer.

**How to fix**
Restructure the page to state the core claim or definition in the first paragraph. Background and supporting detail can follow. Think of it as inverted-pyramid journalism: answer first, elaborate second.

---

### LINK_PROFILE_PROMOTIONAL
**Severity:** 🟡 warning | **Evidence:** Mechanistic | **Impact:** 4 | **Effort:** 2

**What it is**
The page's outbound link profile is dominated by affiliate or promotional links (URLs with `?ref=`, `?aff=`, `?affiliate=`, `/go/`, or `/ref/` patterns), and has no authority or reference links.

**Why it matters**
High promotional link density signals low editorial independence to AI systems. Pages that primarily link to affiliate destinations score lower for authority than pages linking to research, official sources, or reference material.

**How to fix**
Balance promotional links with authoritative external links to `.gov`, `.edu`, research papers, or official documentation. Ensure your outbound link profile reflects genuine reference intent, not just monetisation.

---

### STRUCTURED_ELEMENTS_LOW
**Severity:** 🔵 info | **Evidence:** Mechanistic | **Impact:** 3 | **Effort:** 2

**What it is**
A 500+ word page has no structured formatting elements — no lists (`<ul>`, `<ol>`), no tables, no definition lists, no code blocks.

**Why it matters**
Structured elements create extractable, scannable content that AI systems can parse into discrete facts. Pure prose without structure forces AI to do more inference to extract key points, reducing accuracy and quotability.

**How to fix**
Break up dense prose with bullet lists, numbered steps, or tables where appropriate. Key facts, features, and process steps are natural candidates for lists.

---

### JSON_LD_INVALID
**Severity:** 🟡 warning | **Evidence:** Conventional | **Impact:** 4 | **Effort:** 2

**What it is**
A `<script type="application/ld+json">` block exists on the page but is missing a `@type` or `@context` property, or is not valid JSON.

**Why it matters**
Invalid JSON-LD is silently ignored by search engines and AI systems. An existing but broken schema block is worse than no schema — it creates the appearance of structured data without the benefit.

**How to fix**
Ensure every JSON-LD block has at minimum `"@context": "https://schema.org"` and a `"@type"` value. Validate your schema at [schema.org/SchemaTextEncoder](https://validator.schema.org/) or Google's Rich Results Test.

---

### FAQ_SCHEMA_MISSING
**Severity:** 🔵 info | **Evidence:** Conventional | **Impact:** 3 | **Effort:** 2

**What it is**
The page has FAQ-like H2/H3 headings (containing question words, "FAQ", or ending with `?`) but has no `FAQPage` JSON-LD schema.

**Why it matters**
`FAQPage` schema explicitly signals Q&A structure to AI systems, making the content a much stronger candidate for direct-answer citations. FAQ headings without schema miss this signal.

**How to fix**
Add `FAQPage` JSON-LD schema listing each question and its answer. Yoast SEO Premium and Rank Math generate this automatically from FAQ blocks. Google Search Console may reward eligible pages with FAQ-style rich results.

---

### PROMOTIONAL_CONTENT_INTERRUPTS
**Severity:** 🔵 info | **Evidence:** Conventional | **Impact:** 3 | **Effort:** 3

**What it is**
Detected (via LLM analysis) that the page interrupts informational content with promotional material — call-to-action blocks, "Sign up now" banners, or sales copy interspersed within substantive sections.

**Why it matters**
AI systems extracting passage-level content may include promotional interruptions in cited quotes, or may deprioritise the page as a trustworthy information source. Clean informational content without promotional interruptions is more likely to be cited accurately.

**How to fix**
Move promotional CTAs to the top or bottom of the page, or into clearly separated sidebar sections. Keep the body content focused on informational value with promotional elements contained in dedicated blocks.

---

### AI_TXT_MISSING
**Severity:** 🔵 info | **Evidence:** Conventional | **Impact:** 1 | **Effort:** 1

**What it is**
No `/ai.txt` file found at the site root.

**Why it matters**
`ai.txt` is an emerging companion to `robots.txt` specifically for AI agents, allowing granular permissions (training, search, user-fetch) per bot. While not yet widely enforced, early adoption ensures forward compatibility as AI crawlers formalise this standard.

**How to fix**
Create a plain text file at `yoursite.com/ai.txt` following the draft specification. TalkingToad's AI Readiness panel provides guidance. At minimum, a permissive `ai.txt` explicitly welcoming AI crawlers signals cooperative intent.

---

*Last updated: May 2026 — covers all active issue codes in spec v1.4 + v1.5 + v1.6 + v1.7 + v2.1 (GEO Analyzer). All issues include diagnostic `extra` data.*
