/**
 * issueHelp.js
 *
 * Help content for every issue code TalkingToad can emit.
 * Keyed by issue_code (uppercase, matching api/crawler/issue_checker.py _CATALOGUE).
 *
 * Each entry has:
 *   - title:      Short human-readable name shown in the UI
 *   - category:   Matches the API category field
 *   - severity:   critical | warning | info
 *   - definition: What the issue is, in plain English
 *   - impact:     Why it matters — consequences for the site or visitors
 *   - fix:        Concrete steps to resolve it
 *
 * MAINTENANCE NOTE:
 *   When issue codes are added or changed in api/crawler/issue_checker.py,
 *   update this file, docs/issue-codes.md, and frontend/public/help.html.
 *
 * Phase 1 codes — active in the MVP results UI.
 * Extended codes — also active in Phase 1 UI (security, URL structure, etc.)
 * Phase 2 codes — collected in Phase 1 crawl, displayed in the UI from Phase 2 onwards.
 */

const issueHelp = {

  // ═══════════════════════════════════════════════════════════════════════════
  // METADATA
  // ═══════════════════════════════════════════════════════════════════════════

  TITLE_MISSING: {
    title: "Page title missing",
    category: "metadata",
    severity: "critical",
    mission_impact: "Google doesn't know what to call this page in search results.",
    definition:
      "This page has no <title> tag in its HTML. Every web page should have a unique " +
      "title tag in its <head> section — it is the clickable headline shown in search " +
      "results and in the browser tab.",
    impact:
      "Search engines won't know what to call this page in search results. Without a title, " +
      "Google generates one automatically — usually by pulling text from the page, often " +
      "poorly. This directly harms search visibility and the click-through rate from " +
      "search results.",
    fix:
      "Add a <title> tag to the page's <head> section with a clear, descriptive title " +
      "between 30 and 60 characters. In WordPress, most themes and SEO plugins (Yoast SEO, " +
      "Rank Math) have a dedicated 'SEO Title' field on each page's edit screen.",
  },

  TITLE_DUPLICATE: {
    title: "Duplicate page title",
    category: "metadata",
    severity: "warning",
    definition:
      "Two or more pages on this site share exactly the same page title. Each page should " +
      "have a unique title that describes its specific content.",
    impact:
      "Search engines use titles to understand what makes each page distinct. Duplicate " +
      "titles make it harder to rank well for relevant searches, because search engines " +
      "may not be able to tell which page is most relevant — or may choose to show only " +
      "one of them.",
    fix:
      "Write a unique title for each affected page that clearly describes what makes that " +
      "page different from the others. Include the page topic and your organisation name, " +
      "e.g. 'Counselling for Anxiety — Living Systems'.",
  },

  TITLE_TOO_SHORT: {
    title: "Page title too short",
    category: "metadata",
    severity: "warning",
    definition:
      "The page title is fewer than 30 characters. Short titles often lack enough context " +
      "to be useful to visitors or search engines.",
    impact:
      "A very short title may not include enough keywords or context for search engines to " +
      "understand the page's topic, reducing the likelihood of the page appearing in relevant " +
      "searches. It may also look thin or unhelpful in search results.",
    fix:
      "Expand the title to between 30 and 60 characters. Include the specific topic of the " +
      "page and your organisation name — for example, 'About Us — Living Systems Counselling " +
      "Society' instead of just 'About'.",
  },

  TITLE_TOO_LONG: {
    title: "Page title too long",
    category: "metadata",
    severity: "warning",
    definition:
      "The page title exceeds 60 characters. Google typically displays around 50–60 " +
      "characters in search results before cutting the title off with an ellipsis (…).",
    impact:
      "The end of your title — often the most distinguishing part — will be cut off in " +
      "search results, making the listing less informative and less clickable to potential " +
      "visitors.",
    fix:
      "Shorten the title to under 60 characters while keeping the most important keywords " +
      "at the beginning. Put the specific page topic first, then the organisation name.",
  },

  META_DESC_MISSING: {
    title: "Meta description missing",
    category: "metadata",
    severity: "critical",
    definition:
      "This page has no meta description tag. The meta description is the short paragraph " +
      "(typically 1–2 sentences) that appears below the page title in search engine results, " +
      "helping visitors decide whether to click.",
    impact:
      "Without a meta description, Google writes one automatically by pulling random text " +
      "from the page. Auto-generated descriptions are often unhelpful or confusing, which " +
      "reduces the likelihood that people will click through to your site from search results.",
    fix:
      "Add a meta description of 70–160 characters that clearly explains what visitors will " +
      "find on this page and why they should visit. In WordPress, the Yoast SEO or Rank Math " +
      "plugin adds a 'Meta Description' field to every page's edit screen.",
  },

  META_DESC_DUPLICATE: {
    title: "Duplicate meta description",
    category: "metadata",
    severity: "warning",
    definition:
      "The same meta description appears on two or more pages. Each page should have a " +
      "unique description that reflects its specific content.",
    impact:
      "Duplicate descriptions don't help search engines or visitors distinguish between your " +
      "pages. They make each result look identical in search listings, reducing click-through " +
      "rates and making it harder for search engines to rank the right page for a given query.",
    fix:
      "Write a unique meta description for each affected page that reflects its own content " +
      "and purpose. Avoid generic descriptions like 'Welcome to our website' that could apply " +
      "to any page.",
  },

  META_DESC_TOO_SHORT: {
    title: "Meta description too short",
    category: "metadata",
    severity: "warning",
    definition:
      "The meta description is fewer than 70 characters. Short descriptions leave valuable " +
      "space unused and provide limited context.",
    impact:
      "Short descriptions give search engines less information to work with and are often " +
      "less persuasive to visitors scanning search results. They may also be replaced by " +
      "Google with automatically selected text from the page.",
    fix:
      "Expand the description to between 70 and 160 characters. Describe what the page " +
      "covers, who it is for, and what action a visitor might take — written in natural, " +
      "readable language.",
  },

  META_DESC_TOO_LONG: {
    title: "Meta description too long",
    category: "metadata",
    severity: "warning",
    definition:
      "The meta description exceeds 160 characters. Search engines typically display around " +
      "155–160 characters before cutting the text off.",
    impact:
      "The end of your description will be replaced with '…' in search results, which looks " +
      "untidy and may cut off important information or calls to action.",
    fix:
      "Shorten the description to under 160 characters, keeping the most important " +
      "information at the beginning. Lead with what the page is about, not background context.",
  },

  OG_TITLE_MISSING: {
    title: "Open Graph title missing",
    category: "metadata",
    severity: "info",
    definition:
      "This page is missing an Open Graph title tag (<meta property=\"og:title\">). " +
      "Open Graph tags control how your page appears when someone shares a link to it on " +
      "social media platforms like Facebook and LinkedIn.",
    impact:
      "When this page is shared on social media, the platform will try to guess a title " +
      "from the page content, which may be inaccurate, poorly formatted, or missing entirely. " +
      "This makes shared links look less professional and less clickable.",
    fix:
      "Add <meta property=\"og:title\" content=\"Your Page Title\"> to the page's <head>. " +
      "Most SEO plugins (Yoast, Rank Math) manage this automatically when you fill in the " +
      "SEO title field. Check the plugin's social media settings.",
  },

  OG_DESC_MISSING: {
    title: "Open Graph description missing",
    category: "metadata",
    severity: "info",
    definition:
      "This page is missing an Open Graph description tag (<meta property=\"og:description\">). " +
      "This tag controls the summary text shown alongside the link preview when the page " +
      "is shared on social media.",
    impact:
      "Social media platforms will attempt to pull description text from the page body when " +
      "this tag is absent, often producing unpredictable or unhelpful results. Link previews " +
      "without a proper description look less professional and attract fewer clicks.",
    fix:
      "Add <meta property=\"og:description\" content=\"Your description here\"> to the " +
      "page's <head>. Most SEO plugins handle this automatically — check the social media " +
      "settings section of your SEO plugin.",
  },

  CANONICAL_MISSING: {
    title: "Canonical tag missing",
    category: "metadata",
    severity: "warning",
    definition:
      "This page has no canonical tag, and either it has URL query parameters (like ?page=2) " +
      "or its content closely matches another page on the site. A canonical tag " +
      "(<link rel=\"canonical\">) tells search engines which version of a page is the " +
      "'official' one to index.",
    impact:
      "Without a canonical tag, search engines may treat similar or parameterised URLs as " +
      "separate competing pages, splitting ranking signals between them. This is called " +
      "'duplicate content' and can dilute your search rankings across the affected pages.",
    fix:
      "Add <link rel=\"canonical\" href=\"https://yoursite.com/preferred-url/\"> to the " +
      "page's <head>, pointing to the definitive version of the URL. In WordPress, Yoast SEO " +
      "handles this automatically for most pages — check that the plugin is active.",
  },

  CANONICAL_EXTERNAL: {
    title: "Canonical points to external domain",
    category: "metadata",
    severity: "warning",
    definition:
      "This page has a canonical tag that points to a URL on a completely different website. " +
      "This explicitly tells search engines that the authoritative version of this content " +
      "exists on another domain — not yours.",
    impact:
      "All search ranking credit for this page will be directed to the external site. Your " +
      "page will be treated as a copy and will not rank in search results. Unless you " +
      "intentionally published this content elsewhere first, this is almost certainly a " +
      "configuration error.",
    fix:
      "Review the canonical tag on this page. If the content originated on your site, change " +
      "the canonical URL to point to this page itself (a self-referencing canonical). If the " +
      "content was syndicated from another site, the external canonical may be correct — " +
      "confirm with your web developer.",
  },

  FAVICON_MISSING: {
    title: "Favicon missing",
    category: "metadata",
    severity: "info",
    definition:
      "The homepage has no favicon — the small icon that appears in browser tabs, bookmarks, " +
      "browser history, and search results on some devices.",
    impact:
      "Favicons don't directly affect search rankings, but they reinforce your brand identity " +
      "and help visitors recognise your site in a crowded list of browser tabs. A missing " +
      "favicon can make a site look unfinished or untrustworthy, particularly on first visit.",
    fix:
      "Create a square image of your logo or brand mark at least 32×32 pixels (512×512 " +
      "recommended), save it as a .ico or .png file, and upload it to your site. In WordPress, " +
      "go to Appearance → Customise → Site Identity → Site Icon.",
  },

  THIN_CONTENT: {
    title: "Thin content — too few words",
    category: "crawlability",
    severity: "warning",
    mission_impact: "This page has very little text; Google may think it isn't useful to visitors.",
    definition:
      "This page has fewer than 300 words of readable body content. Thin content pages " +
      "provide limited value to visitors and may be seen as low-quality by search engines.",
    impact:
      "Pages with very little content are less likely to rank well in search results, as " +
      "they provide little value to a visitor's query. Google's quality guidelines " +
      "specifically call out thin content as a quality issue. Multiple thin-content pages " +
      "can reduce the perceived quality of your entire site.",
    fix:
      "Expand the page content to at least 300 words of meaningful, relevant information. " +
      "Describe the topic thoroughly enough to genuinely answer a visitor's question. If " +
      "the page is intentionally brief (e.g., a contact page), consider adding more context " +
      "about your organisation or services.",
  },

  PAGINATION_LINKS_PRESENT: {
    title: "Pagination links present",
    category: "crawlability",
    severity: "info",
    definition:
      "This page includes rel=\"next\" or rel=\"prev\" link elements, signalling to search " +
      "engines that it is part of a paginated series — such as a blog archive split across " +
      "multiple pages.",
    impact:
      "This is generally fine and helps search engines understand the relationship between " +
      "paginated pages. No immediate action is required unless the pagination structure is " +
      "misconfigured or the linked pages are inaccessible.",
    fix:
      "No action required in most cases. Ensure the linked next/prev pages are crawlable " +
      "and not blocked by robots.txt or noindex tags. Verify that pagination URLs are not " +
      "generating excessive duplicate content.",
  },

  AMPHTML_BROKEN: {
    title: "AMP version link is broken",
    category: "crawlability",
    severity: "warning",
    definition:
      "This page declares an AMP (Accelerated Mobile Pages) version via a " +
      "<link rel=\"amphtml\"> tag, but the AMP URL is not reachable — it returned a " +
      "non-200 status code when checked.",
    impact:
      "A broken AMP link means visitors accessing your content through AMP-served contexts " +
      "(e.g., certain Google Search mobile results) may encounter errors. Search engines may " +
      "de-prioritise or remove AMP versions if the declared URL is inaccessible.",
    fix:
      "Either fix the AMP URL so it returns a 200 status, or remove the rel=\"amphtml\" " +
      "link element from the page if AMP is no longer in use on your site. If your site has " +
      "stopped using AMP, search for and remove all amphtml link tags.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // HEADINGS
  // ═══════════════════════════════════════════════════════════════════════════

  H1_MISSING: {
    title: "H1 heading missing",
    category: "heading",
    severity: "critical",
    definition:
      "This page has no H1 heading tag. An H1 is the main heading of a page — typically " +
      "the largest, most prominent text — and there should be exactly one on every page.",
    impact:
      "Search engines use the H1 to understand the primary topic of a page. Missing H1 " +
      "tags make it harder for search engines to categorise your content, and can directly " +
      "reduce rankings for the search terms most relevant to that page.",
    fix:
      "Add a single <h1> tag that clearly states the main topic of the page. In most CMS " +
      "platforms, the page or post title you enter is automatically output as the H1 by the " +
      "theme. If H1 tags are missing, your theme may have a bug — check with your web developer.",
  },

  H1_MULTIPLE: {
    title: "Multiple H1 headings",
    category: "heading",
    severity: "warning",
    definition:
      "This page has more than one H1 tag. Best practice is to use exactly one H1 per " +
      "page — the primary heading that introduces the main topic.",
    impact:
      "Multiple H1 tags send mixed signals to search engines about which topic is primary " +
      "for the page, diluting its focus. It also creates a confusing experience for visitors " +
      "using screen readers, who rely on headings to navigate page content.",
    fix:
      "Review the page and keep only one H1 that introduces the main topic. Demote additional " +
      "H1 tags to H2 or H3, depending on where they fall in the content hierarchy.",
  },

  HEADING_SKIP: {
    title: "Heading levels skipped",
    category: "heading",
    severity: "warning",
    definition:
      "The heading structure on this page skips one or more levels — for example, jumping " +
      "from H1 directly to H3 with no H2 in between, or from H2 to H4.",
    impact:
      "Skipped heading levels create accessibility problems: screen reader users navigate " +
      "pages by heading structure, and gaps are disorienting. Search engines also interpret " +
      "heading hierarchy as a signal of content organisation — a broken hierarchy suggests " +
      "the content is poorly structured.",
    fix:
      "Review the heading tags on this page and ensure no levels are skipped. Use H1 for " +
      "the main topic, H2 for major sections, H3 for subsections within those, and so on. " +
      "In WordPress, headings are set using the paragraph style selector in the block editor.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // BROKEN LINKS
  // ═══════════════════════════════════════════════════════════════════════════

  BROKEN_LINK_404: {
    title: "Broken link — page not found (404)",
    category: "broken_link",
    severity: "critical",
    mission_impact: "Visitors clicking this will see an error page instead of your content.",
    definition:
      "This link points to a page that doesn't exist. The server responded with a " +
      "'404 Not Found' status, meaning the destination page has either been deleted or " +
      "its URL has changed.",
    impact:
      "Visitors who click this link will land on an error page, creating a frustrating dead " +
      "end. Search engines also note broken links as a signal of poor site maintenance, " +
      "which can gradually harm overall site quality scores. Internal broken links prevent " +
      "search engines from fully crawling your site.",
    fix:
      "Find the correct current URL for the destination content and update the link. If the " +
      "content has been permanently removed with no replacement, delete the link. If you " +
      "control the destination site, consider setting up a 301 redirect from the old URL " +
      "to the new one.",
  },

  BROKEN_LINK_410: {
    title: "Broken link — page permanently removed (410)",
    category: "broken_link",
    severity: "critical",
    definition:
      "This link points to a page that has been permanently and intentionally removed. " +
      "The server returned a '410 Gone' response, which explicitly signals that the content " +
      "is gone for good — unlike a 404, which might be temporary.",
    impact:
      "Visitors clicking this link will see an error page. The 410 status also tells search " +
      "engines to immediately remove the URL from their index. Any links pointing to a 410 " +
      "page waste link authority that could otherwise benefit your site.",
    fix:
      "Remove the link from your site. The destination is permanently gone. If there is a " +
      "relevant alternative page, update the link to point there instead.",
  },

  BROKEN_LINK_5XX: {
    title: "Broken link — server error (5xx)",
    category: "broken_link",
    severity: "critical",
    definition:
      "The destination of this link is returning a server error — a 5xx status code such " +
      "as 500 Internal Server Error or 502 Bad Gateway. The server is responding but " +
      "failing to serve the page correctly.",
    impact:
      "Visitors will see an error page rather than the expected content. Repeated 5xx errors " +
      "reduce visitor trust and signal poor reliability to search engines.",
    fix:
      "Check whether the linked site is experiencing a temporary outage. If the error " +
      "persists after several hours, treat the link as unreliable and either remove it or " +
      "replace it with a link to an alternative resource.",
  },

  BROKEN_LINK_503: {
    title: "Broken link — 503 Service Unavailable (may be bot protection)",
    category: "broken_link",
    severity: "warning",
    definition:
      "The destination of this link returned a 503 status code. This is often returned by " +
      "Cloudflare and other CDN providers when they detect automated requests, even when the " +
      "page loads normally for real visitors in a browser.",
    impact:
      "This may be a false alarm caused by bot protection on the destination site. It could " +
      "also be a genuine temporary outage. Visitors are unlikely to be affected.",
    fix:
      "Open the link in a browser to confirm whether it loads for real visitors. If it works " +
      "normally, no action is needed — the link is fine and the 503 is the destination site " +
      "blocking automated checks. If it fails for visitors too, remove or replace the link.",
  },

  PAGE_TIMEOUT: {
    title: "Page timed out — could not be crawled",
    category: "crawlability",
    severity: "warning",
    definition:
      "This internal page did not respond within the timeout period. The crawler attempted to " +
      "fetch it but received no response in time. The page was not audited for SEO issues.",
    impact:
      "If the page consistently times out, visitors may also experience slow or failed loads. " +
      "Search engines that cannot crawl a page will not index it.",
    fix:
      "Visit the page in a browser to see if it loads. If it is slow, check your hosting " +
      "server performance and page weight. If it consistently fails, contact your web host.",
  },

  EXTERNAL_LINK_TIMEOUT: {
    title: "External link timed out — check manually",
    category: "broken_link",
    severity: "info",
    definition:
      "The crawler attempted to verify this external link but received no response within the " +
      "timeout period. The destination server may be slow, temporarily down, or blocking " +
      "automated requests.",
    impact:
      "The link may work fine for real visitors (who have longer browser timeouts) or it may " +
      "genuinely be slow or broken. This cannot be confirmed automatically.",
    fix:
      "Click the link to confirm it loads in your browser. If it opens quickly, no action is " +
      "needed. If it is consistently slow or fails, consider replacing it with a faster or " +
      "more reliable source.",
  },

  EXTERNAL_LINK_SKIPPED: {
    title: "Link not verified — check manually",
    category: "broken_link",
    severity: "info",
    definition:
      "This link points to a social media platform (such as LinkedIn, Facebook, or Instagram) " +
      "that blocks automated requests. The crawler cannot confirm whether the link is working " +
      "without a real browser session.",
    impact:
      "These links may be perfectly fine — most are. However, if the URL is mis-typed or the " +
      "profile/page has been deleted, visitors will land on an error page or a 'this page " +
      "does not exist' message. The crawler cannot detect this automatically.",
    fix:
      "Click each link in the list below and confirm it opens the correct profile or page. " +
      "For LinkedIn, make sure you are signed in — some profiles redirect to a login wall " +
      "for signed-out visitors even when the page exists.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // REDIRECTS
  // ═══════════════════════════════════════════════════════════════════════════

  REDIRECT_TRAILING_SLASH: {
    title: "Trailing slash redirect — handled automatically by your CMS",
    category: "redirect",
    severity: "info",
    definition:
      "A link on your site points to a URL without a trailing slash (e.g. /about), but your " +
      "server redirects it to the version with a trailing slash (e.g. /about/). Your CMS — " +
      "WordPress, Drupal, and most others — does this automatically, so visitors never notice.",
    impact:
      "No visible impact for visitors. However, the extra redirect adds a small delay (one extra " +
      "HTTP request) before the page loads. For most nonprofit sites this is negligible, but " +
      "fixing it eliminates the unnecessary round trip.",
    fix:
      "Update internal links to include the trailing slash so no redirect is needed. In WordPress, " +
      "this is the URL exactly as it appears in the browser address bar after the redirect. " +
      "You do not need to change any server settings — just the link href values.",
  },

  REDIRECT_CASE_NORMALISE: {
    title: "Case normalisation redirect — handled automatically by your server",
    category: "redirect",
    severity: "info",
    definition:
      "A link on your site uses uppercase letters in the URL path (e.g. /About-Us), but your " +
      "server redirects it to the lowercase version (/about-us). Web servers and CMS platforms " +
      "typically handle this redirect automatically.",
    impact:
      "No visible impact. The redirect is transparent to visitors and search engines will follow " +
      "it. However, it wastes one HTTP round trip and could, if widespread, dilute crawl budget " +
      "on very large sites.",
    fix:
      "Update any internal links that use uppercase URLs to use lowercase instead. This prevents " +
      "the redirect from happening at all. Check page slugs and navigation menus for uppercase characters.",
  },

  REDIRECT_301: {
    title: "Permanent redirect (301)",
    category: "redirect",
    severity: "info",
    definition:
      "This URL responds with a 301 Permanent Redirect, sending visitors and search engines " +
      "to a different URL. A 301 tells search engines that this page has permanently moved " +
      "and they should update their records to use the new URL.",
    impact:
      "301 redirects are generally handled well by search engines and do pass ranking " +
      "signals to the destination URL. However, internal links on your own site that point " +
      "to redirecting URLs add a small amount of overhead (one extra HTTP request per link).",
    fix:
      "Update any internal links on your own site to point directly to the final destination " +
      "URL, bypassing the redirect. This is a low-priority housekeeping task but worth " +
      "addressing during regular site maintenance.",
  },

  REDIRECT_302: {
    title: "Temporary redirect (302)",
    category: "redirect",
    severity: "warning",
    definition:
      "This URL responds with a 302 Temporary Redirect. A 302 is intended for genuinely " +
      "temporary moves — it signals to search engines that they should keep the original " +
      "URL in their index because the move may be reversed.",
    impact:
      "If this redirect is actually permanent, using a 302 instead of a 301 means search " +
      "engines may not fully transfer ranking signals to the new URL. The original URL may " +
      "also continue to be crawled unnecessarily. This can harm your search rankings.",
    fix:
      "If this redirect is permanent, change it to a 301 redirect. In WordPress, the " +
      "Redirection plugin can help you manage this. If the redirect is genuinely temporary, " +
      "a 302 is correct and no action is needed.",
  },

  REDIRECT_CHAIN: {
    title: "Redirect chain",
    category: "redirect",
    severity: "warning",
    definition:
      "This URL redirects to another URL which itself redirects again, creating a chain of " +
      "two or more hops before the visitor reaches the final destination (e.g., A → B → C).",
    impact:
      "Each additional hop slows down page loading — the browser must make multiple requests " +
      "before showing anything. Ranking signals also dilute slightly at each hop. Search " +
      "engines may stop following chains after a certain number of hops.",
    fix:
      "Update the first redirect to point directly to the final destination URL, cutting out " +
      "the intermediate steps. Review your redirect plugin rules for the original URL " +
      "and update the target.",
  },

  REDIRECT_LOOP: {
    title: "Redirect loop",
    category: "redirect",
    severity: "critical",
    mission_impact: "This page is stuck in a circle and will never load for a visitor.",
    definition:
      "This URL is part of an infinite redirect loop — it eventually redirects back to " +
      "itself, creating a cycle that can never resolve. Examples: A → B → A, or A → B → C → A.",
    impact:
      "The page is completely inaccessible to visitors and search engines. Browsers will " +
      "display an error such as 'This page isn't working — too many redirects'. The URL " +
      "cannot be indexed or accessed until the loop is fixed. This is an urgent issue.",
    fix:
      "Check your CMS permalink settings, redirect plugin rules, .htaccess file (Apache), " +
      "or Nginx configuration for conflicting rules. Look for two rules that each redirect " +
      "to the other. The loop must be broken before the page becomes accessible. Contact " +
      "your web developer or hosting provider if unsure.",
  },

  META_REFRESH_REDIRECT: {
    title: "Meta refresh redirect",
    category: "redirect",
    severity: "warning",
    definition:
      "This page uses an HTML meta tag to automatically redirect visitors to another page " +
      "after a short delay: <meta http-equiv=\"refresh\" content=\"0; url=https://newpage.com\">. " +
      "This is an old technique for page redirection.",
    impact:
      "Meta refresh redirects do not pass ranking signals as reliably as server-side 301 " +
      "redirects. They can also cause a brief visible flash of the old page before the " +
      "redirect fires, creating a poor user experience. Some assistive technologies do not " +
      "handle them correctly.",
    fix:
      "Replace the meta refresh redirect with a server-side 301 redirect. Configure this in " +
      "your .htaccess file (Apache), Nginx configuration, or through your CMS's redirect " +
      "management feature (e.g., the Redirection plugin for WordPress).",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // CRAWLABILITY
  // ═══════════════════════════════════════════════════════════════════════════

  LOGIN_REDIRECT: {
    title: "Redirects to login page",
    category: "crawlability",
    severity: "info",
    definition:
      "When the crawler tried to access this URL, it was redirected to a login or " +
      "authentication page. This means the page requires a user to be logged in before " +
      "it can be viewed.",
    impact:
      "Search engines cannot access password-protected pages, so this page will not appear " +
      "in search results. This is normal for private member areas or staff intranets. If " +
      "you intended this page to be publicly visible, the login redirect is a problem.",
    fix:
      "If this page should be public, review your CMS access or membership settings and " +
      "remove the login requirement for this URL. If it is intentionally private, no action " +
      "is needed.",
  },

  ROBOTS_BLOCKED: {
    title: "Blocked by robots.txt",
    category: "crawlability",
    severity: "warning",
    definition:
      "Your site's robots.txt file contains a rule that prevents search engine crawlers " +
      "from accessing this page. The crawler found this URL by following links but cannot " +
      "audit its content.",
    impact:
      "Search engines cannot index this page, so it will not appear in search results. If " +
      "the block is intentional (admin pages, private areas), this is correct. If not, the " +
      "page is invisible to search engines.",
    fix:
      "Open your robots.txt file (at yoursite.com/robots.txt) and review the Disallow " +
      "rules. If you want search engines to access this page, remove or narrow the relevant " +
      "rule. Take care — a broad Disallow rule can accidentally block your entire site. " +
      "Test changes using Google Search Console's robots.txt tester.",
  },

  NOINDEX_META: {
    title: "Noindex meta tag present",
    category: "crawlability",
    severity: "warning",
    mission_impact: "You have a \"Do Not Disturb\" sign on this page; Google is ignoring it.",
    definition:
      "This page contains a meta robots tag instructing search engines not to include it " +
      "in their index: <meta name=\"robots\" content=\"noindex\">. Search engines will " +
      "visit the page but will not store or display it in search results.",
    impact:
      "This page will not appear in search results, regardless of how good its content is. " +
      "If this is intentional (a thank-you page, staging content), no action is needed. " +
      "If not, the page is actively being hidden from search engines.",
    fix:
      "If you want this page in search results, remove the noindex directive. In WordPress " +
      "with Yoast SEO, edit the page and look for the 'Search Appearance' section — there " +
      "is usually a toggle labelled 'Allow search engines to show this post in search results'.",
  },

  NOINDEX_HEADER: {
    title: "Noindex HTTP header present",
    category: "crawlability",
    severity: "warning",
    definition:
      "The server is sending an HTTP response header (X-Robots-Tag: noindex) that instructs " +
      "search engines not to index this page. This has the same effect as a noindex meta " +
      "tag but is set at the server level, making it less visible.",
    impact:
      "This page will not appear in search results. Because this is a server-level setting, " +
      "it is easy to overlook. It may have been set intentionally (e.g., for a staging " +
      "environment) and then forgotten.",
    fix:
      "Check your server configuration, hosting settings, or any SEO or caching plugins " +
      "that might be adding this header. In WordPress, check Settings → Reading for the " +
      "'Discourage search engines' checkbox. Staging environment settings are a common " +
      "culprit when sites go live.",
  },

  NOT_IN_SITEMAP: {
    title: "Page missing from sitemap",
    category: "crawlability",
    severity: "info",
    definition:
      "The crawler found this page by following links, but the URL is not listed in your " +
      "XML sitemap. Sitemaps act as a map for search engines, listing all the pages you " +
      "consider important and want regularly crawled.",
    impact:
      "Search engines are less likely to discover and regularly re-crawl pages not in the " +
      "sitemap, particularly if they are not heavily linked to from other pages. This is " +
      "low-urgency for well-linked pages but can cause indexing delays for others.",
    fix:
      "Add this URL to your XML sitemap. If you use a sitemap plugin (Yoast SEO, Rank Math), " +
      "check whether this page is excluded by a setting, a noindex tag, or an access " +
      "restriction that prevents the plugin from including it.",
  },

  PDF_TOO_LARGE: {
    title: "PDF file too large",
    category: "crawlability",
    severity: "warning",
    definition:
      "A PDF linked from your site is larger than 5MB. This is detected from the " +
      "Content-Length HTTP header returned by the server.",
    impact:
      "Large PDFs are slow to download, particularly for visitors on mobile or slower " +
      "connections. Search engines may skip or only partially index very large PDFs. " +
      "Visitors may abandon the download before it completes.",
    fix:
      "Compress the PDF before uploading it. Use Adobe Acrobat (File → Reduce File Size), " +
      "Smallpdf (smallpdf.com), or ilovepdf.com to reduce the file size. Remove unnecessary " +
      "embedded fonts, reduce image resolution within the PDF, or split large documents into " +
      "smaller, more focused files.",
  },

  HIGH_CRAWL_DEPTH: {
    title: "Page buried deep in site structure",
    category: "crawlability",
    severity: "warning",
    definition:
      "This page is more than 4 clicks away from your homepage — meaning a visitor (or " +
      "search engine crawler) would have to follow more than 4 links in sequence to reach " +
      "it, starting from your homepage.",
    impact:
      "Search engines give less authority and crawl priority to pages buried deep in the " +
      "site structure. Pages more than 4–5 clicks from the homepage may be crawled less " +
      "frequently or given lower ranking weight. They are also harder for visitors to " +
      "discover naturally.",
    fix:
      "Improve your internal linking so this page can be reached in 3 clicks or fewer from " +
      "the homepage. Add links to deeply buried pages from your main navigation, sidebar, " +
      "or from relevant higher-level pages that are already well-linked.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // SITEMAP
  // ═══════════════════════════════════════════════════════════════════════════

  SITEMAP_MISSING: {
    title: "No XML sitemap found",
    category: "sitemap",
    severity: "info",
    definition:
      "The crawler could not find an XML sitemap for this domain. It checked the standard " +
      "location (/sitemap.xml) and the robots.txt file for a Sitemap: directive, and found " +
      "nothing at either location.",
    impact:
      "Without a sitemap, search engines must discover all of your pages purely by following " +
      "links. Pages with few or no internal links pointing to them may never be found, " +
      "crawled, or indexed — effectively making them invisible in search results.",
    fix:
      "Create an XML sitemap and submit it to Google Search Console. If you use WordPress, " +
      "install Yoast SEO, Rank Math, or a dedicated sitemap plugin — these generate a " +
      "sitemap automatically at /sitemap.xml. Squarespace and Wix do this automatically. " +
      "Once created, add 'Sitemap: https://yoursite.com/sitemap.xml' to your robots.txt file.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // DUPLICATES
  // ═══════════════════════════════════════════════════════════════════════════

  TITLE_META_DUPLICATE_PAIR: {
    title: "Title and meta description both duplicated",
    category: "duplicate",
    severity: "warning",
    definition:
      "This page shares both its page title AND its meta description with at least one " +
      "other page on the site. Both fields are identical across multiple pages.",
    impact:
      "When both the title and description are duplicated, search engines have very little " +
      "to distinguish between the affected pages. They may choose to show only one of them " +
      "for a given search, or rank neither well. Visitors see what appears to be the same " +
      "listing repeated, reducing trust.",
    fix:
      "Write unique titles and meta descriptions for every affected page. Each page's title " +
      "and description should describe that page's specific content — not a generic " +
      "description that could apply to multiple pages.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // SECURITY  (§E1)
  // ═══════════════════════════════════════════════════════════════════════════

  HTTP_PAGE: {
    title: "Page served over HTTP (not HTTPS)",
    category: "security",
    severity: "critical",
    definition:
      "This page is served over HTTP rather than HTTPS. HTTP does not encrypt the " +
      "connection between the visitor's browser and your server, leaving data transmitted " +
      "to and from this page exposed.",
    impact:
      "Modern browsers display a 'Not Secure' warning for HTTP pages, which can undermine " +
      "visitor trust and deter donations or contact form submissions. Search engines use " +
      "HTTPS as a ranking signal — HTTP pages may rank lower. Any data submitted through " +
      "forms on an HTTP page is transmitted unencrypted.",
    fix:
      "Enable HTTPS on your hosting account — most hosts provide free SSL certificates via " +
      "Let's Encrypt. Configure a server-side 301 redirect from all HTTP URLs to their " +
      "HTTPS equivalents. Contact your hosting provider if you need assistance enabling SSL.",
  },

  MIXED_CONTENT: {
    title: "Mixed content — HTTP resources on HTTPS page",
    category: "security",
    severity: "warning",
    definition:
      "This HTTPS page is loading one or more resources (images, scripts, or stylesheets) " +
      "over HTTP. Although the page itself is secure, the HTTP resources create a security " +
      "vulnerability known as mixed content.",
    impact:
      "Browsers may block or warn about mixed content. Blocked resources can break page " +
      "layout or functionality. Scripts loaded over HTTP are particularly dangerous — an " +
      "attacker on the network could intercept and modify them, potentially compromising " +
      "your visitors' data.",
    fix:
      "Update all resource URLs on this page to use HTTPS. Check for HTTP URLs in img src " +
      "attributes, script src attributes, link href attributes, and iframe src attributes. " +
      "In WordPress, the Better Search Replace plugin can help update HTTP URLs stored in " +
      "your database.",
  },

  MISSING_HSTS: {
    title: "HSTS header missing",
    category: "security",
    severity: "info",
    definition:
      "This HTTPS page is not sending an HTTP Strict Transport Security (HSTS) header. " +
      "HSTS is a security policy that instructs browsers to only access your site over " +
      "HTTPS in future visits, even if the visitor types http:// directly.",
    impact:
      "Without HSTS, a visitor who types your URL without https:// could be briefly " +
      "vulnerable to a downgrade attack on their first visit to the page. HSTS eliminates " +
      "this window of vulnerability for return visitors. It is a best-practice security " +
      "hardening measure rather than an urgent vulnerability.",
    fix:
      "Add the response header: Strict-Transport-Security: max-age=31536000; includeSubDomains " +
      "to all HTTPS responses from your server. This is typically configured in your web " +
      "server settings (.htaccess for Apache, server block for Nginx) or through your " +
      "hosting provider's control panel.",
  },

  UNSAFE_CROSS_ORIGIN_LINK: {
    title: "External link missing rel=\"noopener\"",
    category: "security",
    severity: "info",
    definition:
      "This page contains one or more links to external websites that open in a new tab " +
      "(target=\"_blank\") without the rel=\"noopener\" or rel=\"noreferrer\" attribute. " +
      "Without these attributes, the opened page can access the window.opener JavaScript " +
      "object.",
    impact:
      "In older browsers, a malicious external page accessed via an unprotected " +
      "target=\"_blank\" link could redirect your original tab — a technique known as " +
      "'tab-napping'. Modern browsers have improved protections, but adding the attribute " +
      "is still considered best practice and a minor security hardening measure.",
    fix:
      "Add rel=\"noopener noreferrer\" to all <a target=\"_blank\"> links pointing to " +
      "external URLs. For example: <a href=\"https://example.com\" target=\"_blank\" " +
      "rel=\"noopener noreferrer\">. Most modern page builders and link editors in WordPress " +
      "add this automatically when you check 'Open in new tab'.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // URL STRUCTURE  (§E2)
  // ═══════════════════════════════════════════════════════════════════════════

  URL_UPPERCASE: {
    title: "URL contains uppercase letters",
    category: "url_structure",
    severity: "warning",
    definition:
      "This URL contains uppercase letters in its path — for example, /About-Us instead " +
      "of /about-us. On most web servers, URLs are case-sensitive, meaning /About and " +
      "/about are treated as different pages.",
    impact:
      "Uppercase URL variants can create duplicate content — search engines may index both " +
      "/About and /about as separate pages, splitting ranking signals between them. Visitors " +
      "who type or share the URL may reach inconsistent versions depending on which case " +
      "they use.",
    fix:
      "Update your CMS to use lowercase-only URLs and set up 301 redirects from any existing " +
      "uppercase URL variants to their lowercase equivalents. In WordPress, avoid capital " +
      "letters when setting page slugs. Most CMS platforms default to lowercase automatically.",
  },

  URL_HAS_SPACES: {
    title: "URL contains encoded spaces",
    category: "url_structure",
    severity: "warning",
    definition:
      "This URL contains spaces encoded as %20 in the path or query string. Spaces are " +
      "invalid in URLs and must be percent-encoded, but their presence indicates the URL " +
      "was not properly formatted when created.",
    impact:
      "URLs with encoded spaces are harder to read and share, look unprofessional, and can " +
      "break in some email clients and messaging apps when pasted as plain text. They also " +
      "suggest the page slug was set incorrectly in the CMS.",
    fix:
      "Edit the URL to replace spaces with hyphens (-). In WordPress, this means editing " +
      "the page slug in the page editor. After changing the URL, set up a 301 redirect " +
      "from the old URL (with %20) to the new hyphenated version.",
  },

  URL_HAS_UNDERSCORES: {
    title: "URL uses underscores instead of hyphens",
    category: "url_structure",
    severity: "info",
    definition:
      "This URL path uses underscores (_) as word separators instead of hyphens (-). " +
      "For example, /about_us instead of /about-us.",
    impact:
      "Google's guidance is to prefer hyphens over underscores in URL paths. Google treats " +
      "hyphens as word separators (so 'about-us' is read as two words: 'about' and 'us') " +
      "but may treat underscores as word-joiners (so 'about_us' could be read as one word: " +
      "'aboutus'). This can affect how the URL's keywords are weighted for search rankings.",
    fix:
      "Consider updating URLs to use hyphens instead of underscores. This is a low-priority " +
      "change — only undertake it with proper 301 redirects in place, and only for pages " +
      "where search rankings matter. The effort may not be worth it on well-established " +
      "pages with existing traffic and backlinks.",
  },

  URL_TOO_LONG: {
    title: "URL too long",
    category: "url_structure",
    severity: "info",
    definition:
      "This URL exceeds 115 characters in total length. While there is no hard browser " +
      "limit for most URLs, very long URLs are problematic in practice.",
    impact:
      "Long URLs are difficult to read, share, or remember. They may be truncated in search " +
      "results and some browsers, making them less useful as navigation cues. Very long URLs " +
      "can also suggest the site structure or permalink settings need review.",
    fix:
      "Shorten the URL slug to be more concise while still descriptive. Edit the page in " +
      "your CMS and update the URL/slug field. After changing the URL, set up a 301 redirect " +
      "from the old long URL to the new shorter one to preserve any existing links.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // PHASE 2 CODES
  // Collected during Phase 1 crawl; displayed in the UI from Phase 2 onwards.
  // ═══════════════════════════════════════════════════════════════════════════

  IMG_ALT_MISSING: {
    title: "Image missing alt text",
    category: "image",
    severity: "warning",
    mission_impact: "People using screen readers cannot \"see\" what this image is about.",
    definition:
      "This image has no alt attribute at all. The alt attribute provides a text " +
      "description of an image for screen readers, search engines, and situations where " +
      "the image cannot be displayed.",
    impact:
      "Screen reader users who are blind or have low vision will have no way to understand " +
      "what this image shows — a significant accessibility barrier. Search engines also " +
      "cannot 'see' images and rely on alt text to understand their content.",
    fix:
      "Add an alt attribute to the image tag that describes what the image shows in one " +
      "concise sentence, e.g. alt=\"Two counsellors meeting with a client in an office\". " +
      "In WordPress, set the alt text for each image in the Media Library or in the block " +
      "editor's image settings panel.",
  },

  IMG_ALT_EMPTY: {
    title: "Image has empty alt text",
    category: "image",
    severity: "info",
    definition:
      "This image has an alt attribute, but it is empty (alt=\"\"). An empty alt attribute " +
      "is the correct technique for purely decorative images that add no information — it " +
      "tells screen readers to skip the image entirely.",
    impact:
      "If this image conveys information, mood, or meaning — such as a photo of your team, " +
      "a chart, or an illustration — the empty alt text means that information is lost to " +
      "screen reader users and search engines. If the image is genuinely decorative, an " +
      "empty alt is correct.",
    fix:
      "Review each flagged image. If it conveys meaningful content, add a descriptive alt " +
      "text. If it is purely decorative and adds no information, the empty alt is correct " +
      "and can be left as-is.",
  },

  IMG_OVERSIZED: {
    title: "Image file too large",
    category: "image",
    severity: "warning",
    definition:
      "This image has a file size exceeding 200KB as reported by the server's " +
      "Content-Length header. Large images are one of the most common causes of slow page " +
      "loading on nonprofit websites.",
    impact:
      "Oversized images significantly slow down page loading, particularly on mobile " +
      "connections. Slow pages frustrate visitors and increase the likelihood they will " +
      "leave before the page loads. Google uses page speed as a ranking factor, so " +
      "consistently large images can harm your search rankings.",
    fix:
      "Compress the image before uploading it. Tools like Squoosh (squoosh.app), TinyPNG " +
      "(tinypng.com), or ImageOptim (Mac) can dramatically reduce file size with minimal " +
      "visible quality loss. Aim for images under 100KB where possible. Also ensure image " +
      "dimensions match the display size — a 4000px wide photo in a 300px column is wasteful " +
      "regardless of compression.",
  },

  INTERNAL_REDIRECT_301: {
    title: "Internal link causes a 301 redirect",
    category: "redirect",
    severity: "info",
    definition:
      "An internal link on your site points to a URL that permanently redirects (301) to another URL. " +
      "Visitors and search engines follow the redirect and reach the right page, but an extra " +
      "round trip is required on every visit.",
    impact:
      "Search engines pass slightly less link authority through redirects than direct links. " +
      "For large sites with many redirecting internal links, this can add up and slow down crawling. " +
      "Fixing these is a quick win that removes unnecessary server load.",
    fix:
      "Update the internal link to point directly to the final destination URL. " +
      "Check your navigation menus, footer links, and in-content links for outdated URLs.",
  },

  ORPHAN_PAGE: {
    title: "Orphan page — no internal links point here",
    category: "crawlability",
    severity: "warning",
    definition:
      "This page was found during the crawl (e.g. via sitemap) but no other page on your site " +
      "links to it. It is an 'orphan' — isolated from the rest of your site's link structure.",
    impact:
      "Search engines discover pages primarily by following links. An orphan page may be crawled " +
      "less frequently, accumulate less internal link authority, and rank poorly even if its " +
      "content is good. Visitors also cannot navigate to it organically.",
    fix:
      "Add at least one internal link to this page from a relevant hub page, navigation menu, " +
      "or related content page. If the page is no longer needed, consider removing it or redirecting it.",
  },

  SCHEMA_MISSING: {
    title: "No structured data (schema markup) on this page",
    category: "crawlability",
    severity: "info",
    definition:
      "This page contains no JSON-LD or microdata structured data markup. Schema markup is a " +
      "standardised vocabulary that helps search engines understand what your content is about " +
      "and display richer search results.",
    impact:
      "Without schema, search engines rely entirely on reading your raw content. Adding schema " +
      "can unlock 'rich results' (star ratings, event details, FAQs) that stand out in search " +
      "and attract more clicks. For nonprofits, Organisation and Event schema are especially valuable.",
    fix:
      "Add Organisation schema to your homepage to describe your nonprofit. Add Event schema for " +
      "any events pages. Consider FAQPage schema for common questions. " +
      "Google's Structured Data Markup Helper (search.google.com/structured-data/helper) can " +
      "generate the markup. Most WordPress SEO plugins (Yoast, Rank Math) add schema automatically.",
  },


  MISSING_VIEWPORT_META: {
    title: "Mobile viewport tag missing",
    category: "crawlability",
    severity: "warning",
    mission_impact: "Your site may look broken or tiny on the phones your supporters use.",
    definition:
      "This page is missing a <meta name=\"viewport\"> tag in its <head> section. " +
      "The viewport tag tells mobile browsers how to scale and display the page on small screens. " +
      "Without it, browsers default to rendering the page at desktop width and zooming out — " +
      "making text tiny and the layout difficult to use on a phone.",
    impact:
      "Google primarily uses the mobile version of your site to decide where it ranks in search " +
      "results (this is called 'mobile-first indexing'). A page that renders poorly on mobile " +
      "is more likely to rank lower and drive visitors away. Most nonprofit supporters browse on " +
      "mobile devices.",
    fix:
      'Add the following tag inside your page\'s <head> section: ' +
      '<meta name="viewport" content="width=device-width, initial-scale=1">. ' +
      "In WordPress, most themes include this automatically. If yours doesn't, " +
      "add it to your theme's header.php template, or use a plugin like 'Header and Footer Scripts'.",
  },

  IMG_BROKEN: {
    title: "Broken image",
    category: "broken_link",
    severity: "critical",
    mission_impact: "Visitors see a broken image icon instead of your photo or graphic.",
    definition:
      "One or more images on this page have a src URL that returns an error (404 Not Found or " +
      "another HTTP error). The image file either no longer exists at that location or the " +
      "URL path is incorrect.",
    impact:
      "Broken images create a poor first impression for supporters visiting your site. They also " +
      "signal to search engines that the page is not being maintained, which can affect your " +
      "ranking. Donors and program participants may lose confidence if they see broken content.",
    fix:
      "Find the broken image in your CMS media library and re-upload it, or update the " +
      "image src URL in the page editor to point to the correct file. In WordPress, use the " +
      "'Broken Link Checker' plugin to locate and fix broken image references site-wide.",
  },

  LINK_EMPTY_ANCHOR: {
    title: "Link has no text",
    category: "metadata",
    severity: "warning",
    definition:
      "One or more links on this page have no visible text inside them — the <a> tag is empty " +
      "or contains only an image without an alt attribute. Screen readers announce these as " +
      "'link' with no description, and search engines cannot determine where the link leads.",
    impact:
      "Empty links are inaccessible to people using screen readers and assistive technology. " +
      "Search engines use anchor text as a signal of what the linked page is about — empty " +
      "anchor text passes no useful signal. This is also a WCAG 2.1 accessibility failure.",
    fix:
      "Add descriptive text inside each empty link. If the link is an icon or image, add an " +
      "aria-label attribute to the <a> tag (e.g., aria-label=\"Donate now\") or add an " +
      "alt attribute to the image inside the link. In a page editor, ensure every clickable " +
      "button or image link has a clear label.",
  },

  INTERNAL_NOFOLLOW: {
    title: "Internal link with nofollow",
    category: "crawlability",
    severity: "warning",
    definition:
      'One or more links on this page point to other pages on your own site but carry a ' +
      'rel="nofollow" attribute. The nofollow attribute is a signal to search engines to ' +
      "not follow the link and not pass any 'link equity' (ranking value) to the destination.",
    impact:
      "Applying nofollow to your own internal links prevents search engines from discovering " +
      "or valuing those pages. It can suppress the ranking of pages you likely want visitors " +
      "to find — such as service pages, donation pages, or program descriptions.",
    fix:
      'Remove the rel="nofollow" attribute from links to your own site\'s pages. Reserve ' +
      'nofollow for links to external sites you do not vouch for, or for user-generated ' +
      "content. In WordPress, check your navigation menus and page editors for any nofollow " +
      "settings added by SEO plugins.",
  },

  PAGE_SIZE_LARGE: {
    title: "Page is too large",
    category: "crawlability",
    severity: "warning",
    definition:
      "The HTML response for this page exceeds 150 KB. This is the raw size of the HTML " +
      "document itself — not counting images, scripts, or stylesheets loaded separately. " +
      "Very large HTML pages take longer to download and can slow down how quickly the page " +
      "appears for visitors.",
    impact:
      "Slow-loading pages lead to higher bounce rates — visitors leave before the page " +
      "finishes loading. Google uses page speed as a ranking factor. Supporters on mobile " +
      "data plans may abandon large pages entirely. Crawlers may also time out on very large pages.",
    fix:
      "Review what is generating so much HTML. Common causes include: very long pages with " +
      "hundreds of sections, excessive inline scripts or styles embedded in the HTML, " +
      "or a page builder that generates complex nested markup. Consider paginating long content, " +
      "moving scripts to external files, and cleaning up unused page builder blocks. " +
      "Tools like Google PageSpeed Insights can help diagnose the cause.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // v1.6 NEW CHECKS
  // ═══════════════════════════════════════════════════════════════════════════

  LANG_MISSING: {
    title: "No language declared",
    category: "metadata",
    severity: "warning",
    definition:
      "The page's <html> element is missing a lang attribute (e.g. lang=\"en\"). " +
      "This attribute tells browsers, screen readers, and search engines what language " +
      "the page is written in.",
    impact:
      "Screen readers use the lang attribute to choose the correct pronunciation rules, " +
      "so missing it harms accessibility for visually impaired visitors. Search engines " +
      "also use it to match your content to searches in the correct language.",
    fix:
      "Add lang=\"en\" (or the appropriate language code) to your site's <html> tag. " +
      "In WordPress, most themes include this by default — check your theme or add it " +
      "via a plugin such as Yoast SEO.",
  },

  TITLE_H1_MISMATCH: {
    title: "Title and heading disagree",
    category: "metadata",
    severity: "warning",
    definition:
      "The page's <title> tag and its H1 heading share no significant words. " +
      "While they don't need to be identical, both should describe the same topic.",
    impact:
      "Visitors who find your page in search results click based on the title they see. " +
      "If the main heading on the page describes something different, it creates confusion " +
      "and can increase bounce rates. Search engines also treat a strong mismatch as a " +
      "consistency signal.",
    fix:
      "Update the title or H1 so they both describe the same topic. Typically the H1 is " +
      "the page subject and the title adds your organisation name (e.g. H1: \"About Us\", " +
      "title: \"About Us | My Charity\"). Both should use some of the same key words.",
  },

  HTTPS_REDIRECT_MISSING: {
    title: "HTTP not redirected to HTTPS",
    category: "security",
    severity: "critical",
    definition:
      "When someone visits your site's http:// address (without the 's'), they are not " +
      "automatically redirected to the secure https:// version. Both addresses currently " +
      "resolve to a page rather than one redirecting to the other.",
    impact:
      "Search engines treat http:// and https:// as completely separate URLs, which splits " +
      "your SEO value across two versions of your site. Visitors arriving on the insecure " +
      "version will see a 'Not Secure' warning in their browser, reducing trust. Modern " +
      "browsers also block form submissions and logins on HTTP pages.",
    fix:
      "Configure a 301 redirect from all http:// URLs to their https:// equivalents. " +
      "In WordPress hosting panels this is usually a one-click setting (e.g. 'Force HTTPS' " +
      "in cPanel, Cloudflare, or your host's dashboard). If you manage the server directly, " +
      "add the redirect in your .htaccess file or Nginx config.",
  },

  CANONICAL_SELF_MISSING: {
    title: "No canonical tag",
    category: "metadata",
    severity: "info",
    definition:
      "This indexable page has no <link rel=\"canonical\"> tag. A canonical tag tells " +
      "search engines which URL is the definitive version of a page.",
    impact:
      "Without a canonical tag, search engines must guess which URL is preferred if " +
      "multiple variations exist (e.g. with/without www, with/without trailing slash, " +
      "or with tracking parameters). Adding one is a best-practice preventive measure " +
      "even if you don't currently have duplicate URL problems.",
    fix:
      "Add <link rel=\"canonical\" href=\"[exact-page-url]\"> to the page's <head>. " +
      "Yoast SEO and Rank Math add self-referencing canonicals automatically — " +
      "if you're using one of these plugins, check that the feature is enabled.",
  },

};

export default issueHelp;

/**
 * Helper: get help content for a given issue code.
 * Returns null if no help entry exists for the code.
 *
 * @param {string} issueCode - e.g. "BROKEN_LINK_404"
 * @returns {{ title, category, severity, definition, impact, fix } | null}
 */
export function getIssueHelp(issueCode) {
  return issueHelp[issueCode] ?? null;
}

/**
 * Helper: get all issue codes for a given category.
 *
 * @param {string} category - e.g. "metadata", "security", "redirect"
 * @returns {string[]} array of issue codes
 */
export function getCodesByCategory(category) {
  return Object.entries(issueHelp)
    .filter(([, v]) => v.category === category)
    .map(([k]) => k);
}
