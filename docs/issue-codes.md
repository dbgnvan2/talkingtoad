# Issue Code Reference

Full reference for every issue code TalkingToad can detect.
Each entry includes: what the issue is, why it matters for a nonprofit site, and how to fix it in plain English.

**Source of truth for scoring:** `api/crawler/issue_checker.py` (`_ISSUE_SCORING`, `_CATALOGUE`)
**Frontend help content:** `frontend/src/data/issueHelp.js`

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

*Last updated: April 2026 — covers all active issue codes in spec v1.4 + v1.5 + v1.6 + v1.7*
