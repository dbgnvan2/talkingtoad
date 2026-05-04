"""
Issue detection logic for the TalkingToad crawler.

Implements all Phase 1 issue codes from spec §3.1 and §7.1.
Per-page checks run during the crawl; cross-page duplicate checks run after.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from api.crawler.fetcher import FetchResult
from api.crawler.normaliser import is_same_domain, normalise_url
from api.crawler.parser import ParsedPage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generic anchor text patterns (Step 3a)
# ---------------------------------------------------------------------------

_GENERIC_ANCHOR_TEXTS = frozenset({
    "click here", "read more", "learn more", "here", "more", "this",
    "link", "more info", "find out more", "go", "see more", "details",
    "continue reading", "click", "download",
})


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    """A single SEO issue found during a crawl."""

    code: str
    category: str
    severity: str           # critical | warning | info
    description: str
    recommendation: str
    page_url: str | None = None
    extra: dict | None = None   # optional supplementary data (e.g. redirect chain)
    impact: int = 0             # v1.5 impact score (0–10)
    effort: int = 0             # v1.5 effort score (0–5)
    priority_rank: int = 0      # v1.5 priority: (impact × 10) − (effort × 2)
    human_description: str = "" # plain-English label for nonprofit staff
    # Expanded help for PDF reports
    what_it_is: str = ""
    impact_desc: str = ""
    how_to_fix: str = ""
    fixability: str = "developer_needed"  # wp_fixable | content_edit | developer_needed


# ---------------------------------------------------------------------------
# Issue catalogue (spec §7.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _IssueSpec:
    category: str
    severity: str
    description: str
    recommendation: str
    human_description: str = ""   # plain-English label for nonprofit staff
    what_it_is: str = ""
    impact_desc: str = ""
    how_to_fix: str = ""
    fixability: str = "developer_needed"  # wp_fixable | content_edit | developer_needed


# ---------------------------------------------------------------------------
# v1.5 Priority scoring table (impact, effort) per issue code
# ---------------------------------------------------------------------------
# priority_rank = (impact × 10) − (effort × 2)
# Impact 1–10: how badly the issue hurts SEO / UX
# Effort  1–5: how hard it is to fix (1 = trivial, 5 = major dev work)

_ISSUE_SCORING: dict[str, tuple[int, int]] = {
    # code:                       (impact, effort)
    "BROKEN_LINK_404":            (10, 2),
    "BROKEN_LINK_410":            (8,  2),
    "BROKEN_LINK_5XX":            (7,  3),
    "BROKEN_LINK_503":            (4,  3),
    "REDIRECT_LOOP":              (10, 4),
    "REDIRECT_CHAIN":             (6,  3),
    "REDIRECT_301":               (3,  2),
    "REDIRECT_302":               (5,  2),
    "REDIRECT_TRAILING_SLASH":    (2,  1),
    "REDIRECT_CASE_NORMALISE":    (2,  1),
    "TITLE_MISSING":              (9,  1),
    "TITLE_DUPLICATE":            (5,  2),
    "TITLE_TOO_SHORT":            (5,  1),
    "TITLE_TOO_LONG":             (4,  1),
    "META_DESC_MISSING":          (7,  1),
    "META_DESC_DUPLICATE":        (4,  2),
    "META_DESC_TOO_SHORT":        (4,  1),
    "META_DESC_TOO_LONG":         (3,  1),
    "OG_TITLE_MISSING":           (4,  1),
    "OG_DESC_MISSING":            (3,  1),
    "CANONICAL_MISSING":          (6,  2),
    "CANONICAL_EXTERNAL":         (5,  2),
    "TITLE_META_DUPLICATE_PAIR":  (6,  2),
    "FAVICON_MISSING":            (3,  2),
    "H1_MISSING":                 (8,  1),
    "H1_MULTIPLE":                (6,  2),
    "HEADING_SKIP":               (4,  3),
    "NOINDEX_META":               (10, 1),
    "NOINDEX_HEADER":             (10, 2),
    "ROBOTS_BLOCKED":             (9,  2),
    "NOT_IN_SITEMAP":             (4,  1),
    "SITEMAP_MISSING":            (6,  2),
    "HTTP_PAGE":                  (9,  2),
    "MIXED_CONTENT":              (6,  2),
    "MISSING_HSTS":               (4,  2),
    "UNSAFE_CROSS_ORIGIN_LINK":   (3,  1),
    "URL_TOO_LONG":               (2,  4),
    "URL_UPPERCASE":              (3,  2),
    "URL_HAS_SPACES":             (5,  3),
    "URL_HAS_UNDERSCORES":        (2,  4),
    "THIN_CONTENT":               (6,  4),
    "HIGH_CRAWL_DEPTH":           (5,  3),
    "PAGE_TIMEOUT":               (6,  3),
    "EXTERNAL_LINK_TIMEOUT":      (3,  1),
    "EXTERNAL_LINK_SKIPPED":      (2,  1),
    "META_REFRESH_REDIRECT":      (5,  2),
    "PAGINATION_LINKS_PRESENT":   (2,  2),
    "AMPHTML_BROKEN":             (4,  3),
    "PDF_TOO_LARGE":              (4,  2),
    "IMG_OVERSIZED":              (5,  2),
    "IMG_ALT_MISSING":            (5,  2),
    # v1.9image - New image issue codes
    "IMG_ALT_TOO_SHORT":          (3,  1),
    "IMG_ALT_TOO_LONG":           (2,  1),
    "IMG_ALT_GENERIC":            (4,  1),
    "IMG_ALT_DUP_FILENAME":       (3,  1),
    "IMG_ALT_MISUSED":            (3,  2),
    "IMG_SLOW_LOAD":              (4,  2),
    "IMG_OVERSCALED":             (4,  3),
    "IMG_POOR_COMPRESSION":       (4,  2),
    "IMG_FORMAT_LEGACY":          (2,  2),
    "IMG_NO_SRCSET":              (2,  3),
    "IMG_DUPLICATE_CONTENT":      (2,  2),
    "LOGIN_REDIRECT":             (2,  1),
    "INTERNAL_REDIRECT_301":      (4,  1),
    "ORPHAN_PAGE":                (6,  4),
    "SCHEMA_MISSING":             (5,  2),
    "MISSING_VIEWPORT_META":      (6,  1),
    "IMG_BROKEN":                 (8,  2),
    "LINK_EMPTY_ANCHOR":          (7,  2),
    "INTERNAL_NOFOLLOW":          (5,  2),
    "PAGE_SIZE_LARGE":            (5,  3),
    # v1.6 new checks
    "LANG_MISSING":               (6,  1),
    "TITLE_H1_MISMATCH":          (6,  2),
    "HTTPS_REDIRECT_MISSING":     (9,  2),
    "CANONICAL_SELF_MISSING":     (5,  1),
    # v1.7 AI-Readiness Module
    "LLMS_TXT_MISSING":           (6,  1),
    "LLMS_TXT_INVALID":           (4,  2),
    "SEMANTIC_DENSITY_LOW":       (5,  3),
    "DOCUMENT_PROPS_MISSING":     (4,  2),
    "JSON_LD_MISSING":            (7,  2),
    "CONVERSATIONAL_H2_MISSING":  (4,  2),
    "BLOG_SECTIONS_MISSING":      (5,  2),
    # v1.9.2 new checks
    "OG_IMAGE_MISSING":           (3,  1),
    "TWITTER_CARD_MISSING":       (3,  1),
    "CONTENT_STALE":              (3,  4),
    # Phase 3 new checks
    "ANCHOR_TEXT_GENERIC":        (4,  2),
    "HEADING_EMPTY":              (4,  1),
    "WWW_CANONICALIZATION":       (5,  2),
    # v2.0 AI-Readiness: AI Bot Access
    "AI_BOT_SEARCH_BLOCKED":      (8,  1),
    "AI_BOT_TRAINING_DISALLOWED": (0,  1),
    "AI_BOT_USER_FETCH_BLOCKED":  (4,  1),
    "AI_BOT_DEPRECATED_DIRECTIVE":(2,  1),
    "AI_BOT_NO_AI_DIRECTIVES":    (1,  1),
    "AI_BOT_BLANKET_DISALLOW":    (9,  1),
    "AI_BOT_TABLE_STALE":         (0,  1),
    # v2.0 AI-Readiness: Schema Typing
    "SCHEMA_TYPE_MISMATCH":       (4,  2),
    "SCHEMA_DEPRECATED_TYPE":     (2,  1),
    "SCHEMA_TYPE_CONFLICT":       (3,  2),
    # v2.0 AI-Readiness: Content Extractability
    "CONTENT_NOT_EXTRACTABLE_NO_TEXT": (6, 4),
    "CONTENT_THIN":               (4,  3),
    "CONTENT_UNSTRUCTURED":       (3,  2),
    "CONTENT_IMAGE_HEAVY":        (2,  3),
    # v2.0 AI-Readiness: Citation & Attribution
    "CITATIONS_MISSING_SUBSTANTIAL_CONTENT": (3, 2),
    "CITATIONS_ORPHANED":         (2,  1),
    "CITATIONS_SOURCES_INACCESSIBLE": (4, 3),
}


_CATALOGUE: dict[str, _IssueSpec] = {
    # ── Metadata ──────────────────────────────────────────────────────────
    "TITLE_MISSING": _IssueSpec(
        category="metadata", severity="critical",
        description="Page has no <title> tag",
        recommendation="Add a unique title tag between 30–60 characters that clearly describes this page.",
        human_description="Missing Name Tag",
        what_it_is="The title tag is the most important on-page SEO element. It tells search engines and users what the page is about and appears as the clickable headline in search results.",
        impact_desc="Without a title tag, search engines may not index your page correctly, and users won't see a relevant headline in search results, significantly reducing your click-through rate.",
        how_to_fix="Add a <title> tag to the <head> section of your HTML. In WordPress, you can typically set this using your SEO plugin (Yoast, Rank Math) or the page editor.",
        fixability="wp_fixable",
    ),
    "TITLE_DUPLICATE": _IssueSpec(
        category="metadata", severity="warning",
        description="Same title used on multiple pages",
        recommendation="Make each page title unique. Describe what makes this page different from others on your site.",
        human_description="Duplicate Page Name",
        fixability="content_edit",
    ),
    "TITLE_TOO_SHORT": _IssueSpec(
        category="metadata", severity="warning",
        description="Title under 30 characters",
        recommendation="Expand the title to 30–60 characters. Include your organisation name and the page topic.",
        human_description="Too-Short Page Name",
        fixability="wp_fixable",
    ),
    "TITLE_TOO_LONG": _IssueSpec(
        category="metadata", severity="warning",
        description="Title over 60 characters",
        recommendation="Shorten the title to under 60 characters. Google truncates longer titles in search results.",
        human_description="Too-Long Page Name",
        fixability="wp_fixable",
    ),
    "META_DESC_MISSING": _IssueSpec(
        category="metadata", severity="critical",
        description="No meta description",
        recommendation="Add a meta description of 70–160 characters summarising what visitors will find on this page.",
        human_description="Missing Summary Snippet",
        what_it_is="A meta description is a brief summary of a page's content that appears under the title in search results. It helps users decide whether to click on your link.",
        impact_desc="While not a direct ranking factor, a missing description forces search engines to pick random text from your page, which often looks unappealing and reduces click-through rates.",
        how_to_fix="Add a <meta name='description'> tag to your page. Use your SEO plugin to write a compelling summary that includes your primary keywords.",
        fixability="wp_fixable",
    ),
    "META_DESC_DUPLICATE": _IssueSpec(
        category="metadata", severity="warning",
        description="Same meta description on multiple pages",
        recommendation="Write a unique meta description for this page that reflects its specific content.",
        human_description="Duplicate Summary Snippet",
        fixability="content_edit",
    ),
    "META_DESC_TOO_SHORT": _IssueSpec(
        category="metadata", severity="warning",
        description="Meta description under 70 characters",
        recommendation="Expand the description to 70–160 characters to give search engines more context.",
        human_description="Too-Short Summary Snippet",
        fixability="wp_fixable",
    ),
    "META_DESC_TOO_LONG": _IssueSpec(
        category="metadata", severity="warning",
        description="Meta description over 160 characters",
        recommendation="Shorten the description to under 160 characters. Longer descriptions are cut off in search results.",
        human_description="Too-Long Summary Snippet",
        fixability="wp_fixable",
    ),
    "OG_TITLE_MISSING": _IssueSpec(
        category="metadata", severity="info",
        description="Open Graph title tag missing",
        recommendation="Add an og:title meta tag. This controls how your page title appears when shared on social media.",
        human_description="Missing Social Share Title",
        fixability="wp_fixable",
    ),
    "OG_DESC_MISSING": _IssueSpec(
        category="metadata", severity="info",
        description="Open Graph description tag missing",
        recommendation="Add an og:description meta tag. This controls the description shown when your page is shared on social media.",
        human_description="Missing Social Share Description",
        fixability="wp_fixable",
    ),
    "OG_IMAGE_MISSING": _IssueSpec(
        category="metadata", severity="info",
        description="Open Graph image tag (og:image) is missing",
        recommendation="Add an og:image meta tag with a URL to a high-quality preview image (1200x630px recommended). This controls the image shown when your page is shared on Facebook, LinkedIn, and other social platforms.",
        human_description="Missing Social Share Image",
        fixability="content_edit",
    ),
    "TWITTER_CARD_MISSING": _IssueSpec(
        category="metadata", severity="info",
        description="Missing Twitter/X Card meta tag",
        recommendation="Add a <meta name=\"twitter:card\" content=\"summary_large_image\"> tag. This controls how your page appears when shared on Twitter/X.",
        human_description="Missing Twitter/X Card",
        fixability="content_edit",
    ),
    "CANONICAL_MISSING": _IssueSpec(
        category="metadata", severity="warning",
        description="No canonical tag — page has query strings or is a near-duplicate",
        recommendation="Add a canonical tag pointing to the preferred URL for this page to prevent duplicate content issues.",
        human_description="Ambiguous Preferred URL",
        fixability="developer_needed",
    ),
    "CANONICAL_EXTERNAL": _IssueSpec(
        category="metadata", severity="warning",
        description="Canonical points to a different domain",
        recommendation="Review this canonical tag — it is pointing search engines to a page on a different website.",
        human_description="External Preferred URL",
        fixability="developer_needed",
    ),
    "FAVICON_MISSING": _IssueSpec(
        category="metadata", severity="info",
        description="No favicon found (homepage only)",
        recommendation="Add a favicon to your site. This small icon appears in browser tabs and bookmarks and reinforces your brand.",
        human_description="Missing Website Icon",
        fixability="content_edit",
    ),
    # ── Headings ──────────────────────────────────────────────────────────
    "H1_MISSING": _IssueSpec(
        category="heading", severity="critical",
        description="No H1 tag found on page",
        recommendation="Add a single H1 heading that clearly states the main topic of this page.",
        human_description="Missing Main Heading",
        fixability="content_edit",
    ),
    "H1_MULTIPLE": _IssueSpec(
        category="heading", severity="warning",
        description="More than one H1 on the page",
        recommendation="Remove extra H1 tags. Each page should have exactly one H1 that introduces the main topic.",
        human_description="Multiple Main Headings",
        fixability="content_edit",
    ),
    "HEADING_SKIP": _IssueSpec(
        category="heading", severity="warning",
        description="Heading levels skip (e.g., H1 → H3)",
        recommendation="Fix the heading structure so levels are not skipped. Use H1, then H2, then H3 in order.",
        human_description="Skipped Heading Level",
        fixability="content_edit",
    ),
    "HEADING_EMPTY": _IssueSpec(
        category="heading", severity="warning",
        description="One or more heading tags have no text content",
        recommendation="Remove empty heading tags or add descriptive text. Empty headings confuse screen readers and waste heading structure.",
        human_description="Empty Heading",
        fixability="content_edit",
    ),
    # ── Broken links ──────────────────────────────────────────────────────
    "BROKEN_LINK_404": _IssueSpec(
        category="broken_link", severity="critical",
        description="Link destination returns 404 Not Found",
        recommendation="Remove or update this link. The page it points to no longer exists.",
        human_description="Dead Link",
        fixability="wp_fixable",
    ),
    "BROKEN_LINK_410": _IssueSpec(
        category="broken_link", severity="critical",
        description="Link destination returns 410 Gone",
        recommendation="Remove this link. The destination has been permanently removed.",
        human_description="Removed Link",
        fixability="wp_fixable",
    ),
    "BROKEN_LINK_5XX": _IssueSpec(
        category="broken_link", severity="critical",
        description="Link destination returns a server error",
        recommendation="Check whether the linked site is down. If the problem persists, remove or replace the link.",
        human_description="Broken Server Link",
        fixability="wp_fixable",
    ),
    "BROKEN_LINK_503": _IssueSpec(
        category="broken_link", severity="warning",
        description="Link destination returns 503 — may be temporarily down or blocking automated checks",
        recommendation="Visit the link manually to see if it loads for real visitors. "
                       "If the problem persists, the destination site may be down or blocking crawlers.",
        human_description="Temporarily Blocked Link",
        fixability="developer_needed",
    ),
    "EXTERNAL_LINK_SKIPPED": _IssueSpec(
        category="broken_link", severity="info",
        description="Link not verified — social media platforms block automated checks",
        recommendation="Open this link in a browser to confirm it is working correctly.",
        human_description="Unverified Social Link",
        fixability="developer_needed",
    ),
    "EXTERNAL_LINK_TIMEOUT": _IssueSpec(
        category="broken_link", severity="info",
        description="External link did not respond — destination may be slow or unavailable",
        recommendation="Click the link to confirm it works in a browser. If it consistently fails, "
                       "the destination site may be down or the domain may have expired.",
        human_description="Slow External Link",
        fixability="developer_needed",
    ),
    # ── Redirects ─────────────────────────────────────────────────────────
    "REDIRECT_LOOP": _IssueSpec(
        category="redirect", severity="critical",
        description="Redirect loop detected",
        recommendation="Fix the redirect configuration immediately. This page cannot load and is invisible to search engines.",
        human_description="Spinning Page",
        fixability="developer_needed",
    ),
    "REDIRECT_301": _IssueSpec(
        category="redirect", severity="info",
        description="Page returns a permanent redirect",
        recommendation="Update any internal links pointing here to use the final destination URL directly.",
        human_description="Permanent Redirect",
        fixability="developer_needed",
    ),
    "REDIRECT_302": _IssueSpec(
        category="redirect", severity="warning",
        description="Page returns a temporary redirect",
        recommendation="Confirm whether this redirect is intentional. If permanent, change it to a 301 redirect.",
        human_description="Temporary Redirect",
        fixability="developer_needed",
    ),
    "REDIRECT_CHAIN": _IssueSpec(
        category="redirect", severity="warning",
        description="Page involves a multi-hop redirect chain",
        recommendation="Consolidate the redirect chain to a single direct redirect to the final destination.",
        human_description="Multi-Hop Detour",
        fixability="developer_needed",
    ),
    "REDIRECT_TRAILING_SLASH": _IssueSpec(
        category="redirect", severity="info",
        description="Redirect adds or removes a trailing slash — your CMS handles this automatically",
        recommendation="No urgent action needed. Your CMS corrects this for visitors automatically. "
                       "To eliminate the extra round trip, update internal links to use the canonical URL "
                       "with the trailing slash your server expects.",
        human_description="Auto-Corrected URL (Slash)",
        fixability="developer_needed",
    ),
    "REDIRECT_CASE_NORMALISE": _IssueSpec(
        category="redirect", severity="info",
        description="Redirect normalises URL case — your web server handles this automatically",
        recommendation="No urgent action needed. Your server redirects uppercase URLs to lowercase automatically. "
                       "To eliminate the extra redirect, update internal links to use lowercase-only URLs.",
        human_description="Auto-Corrected URL (Case)",
        fixability="developer_needed",
    ),
    "META_REFRESH_REDIRECT": _IssueSpec(
        category="redirect", severity="warning",
        description="Page uses a <meta http-equiv=\"refresh\"> tag to redirect users",
        recommendation="Replace meta refresh redirects with server-side 301 redirects.",
        human_description="HTML Redirect (Outdated)",
        fixability="developer_needed",
    ),
    # ── Crawlability ──────────────────────────────────────────────────────
    "PAGE_TIMEOUT": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page did not respond within the timeout period",
        recommendation="Check the page manually. A persistent timeout may indicate a slow server, "
                       "heavy page weight, or a broken URL. Consider increasing server response speed.",
        human_description="Slow-Loading Page",
        fixability="developer_needed",
    ),
    "LOGIN_REDIRECT": _IssueSpec(
        category="crawlability", severity="info",
        description="Page redirects to a login screen",
        recommendation="This page requires a login to access. The crawler cannot audit it. Review manually if needed.",
        human_description="Login-Protected Page",
        fixability="developer_needed",
    ),
    "ROBOTS_BLOCKED": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page blocked by robots.txt",
        recommendation="Check whether this page should be blocked. If not, update your robots.txt file.",
        human_description="Blocked by Crawl Rules",
        fixability="developer_needed",
    ),
    "NOINDEX_META": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page has a noindex meta tag",
        recommendation="Confirm whether this page should be excluded from search results. Remove the noindex tag if not.",
        human_description="Hidden from Search",
        fixability="wp_fixable",
    ),
    "NOINDEX_HEADER": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page has a noindex HTTP header",
        recommendation="Check your server configuration. This page is being hidden from search engines via an HTTP header.",
        human_description="Hidden from Search (Server)",
        fixability="developer_needed",
    ),
    "NOT_IN_SITEMAP": _IssueSpec(
        category="crawlability", severity="info",
        description="Crawlable page not listed in sitemap",
        recommendation="Add this URL to your XML sitemap so search engines can find it more reliably.",
        human_description="Missing from Sitemap",
        fixability="wp_fixable",
    ),
    "PDF_TOO_LARGE": _IssueSpec(
        category="crawlability", severity="warning",
        description="PDF file exceeds 10 MB",
        recommendation="Reduce the PDF file size. Large PDFs are slow to download and may be skipped by crawlers.",
        human_description="Oversized Document",
        fixability="developer_needed",
    ),
    "IMG_OVERSIZED": _IssueSpec(
        category="image", severity="warning",
        description="Image file exceeds 200 KB",
        recommendation="Compress this image. Use Squoosh, TinyPNG, or ImageOptim to reduce the file size without visible quality loss.",
        human_description="Oversized Image",
        fixability="content_edit",
    ),
    "PAGINATION_LINKS_PRESENT": _IssueSpec(
        category="crawlability", severity="info",
        description="Page declares rel=\"next\" or rel=\"prev\" pagination link elements",
        recommendation="No action required. Ensure the linked pages are crawlable.",
        human_description="Paginated Content",
        fixability="developer_needed",
    ),
    "THIN_CONTENT": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page has fewer than 300 words of body content",
        recommendation="Expand the page content to at least 300 words to provide more value to users and search engines.",
        human_description="Low Information",
        fixability="content_edit",
    ),
    "AMPHTML_BROKEN": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page declares an AMP version via <link rel=\"amphtml\"> but the AMP URL is not reachable",
        recommendation="Fix the AMP URL or remove the amphtml link element if AMP is no longer in use.",
        human_description="Broken Mobile Version",
        fixability="developer_needed",
    ),
    "HIGH_CRAWL_DEPTH": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page is more than 4 clicks from the homepage",
        recommendation="Improve internal linking so this page can be reached in 3 clicks or fewer from the homepage.",
        human_description="Hard-to-Reach Page",
        fixability="developer_needed",
    ),
    "ORPHAN_PAGE": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page has no internal links pointing to it — search engines may not discover it",
        recommendation="Add at least one internal link to this page from a navigation menu, hub page, "
                       "or relevant content page so search engines and visitors can find it.",
        human_description="Disconnected Page",
        fixability="developer_needed",
    ),
    "CONTENT_STALE": _IssueSpec(
        category="crawlability", severity="info",
        description="Page content has not been modified in over 12 months",
        recommendation="Review and refresh this page's content. Search engines favour recently updated pages, "
                       "and visitors may lose trust in outdated information. Even small updates signal freshness.",
        human_description="Stale Content",
        fixability="content_edit",
    ),
    "SCHEMA_MISSING": _IssueSpec(
        category="crawlability", severity="info",
        description="No structured data (schema markup) found on this page",
        recommendation="Consider adding JSON-LD structured data to help search engines understand the page content. "
                       "At minimum, add Organisation schema to your homepage. "
                       "Google's Rich Results Test can validate your markup.",
        human_description="No Structured Data",
        fixability="wp_fixable",
    ),
    # ── Sitemap ───────────────────────────────────────────────────────────
    "SITEMAP_MISSING": _IssueSpec(
        category="sitemap", severity="info",
        description="No sitemap found for this domain",
        recommendation="Create an XML sitemap and submit it to Google Search Console. Most CMS platforms can generate one automatically.",
        human_description="No Sitemap",
        fixability="developer_needed",
    ),
    # ── Duplicate content ─────────────────────────────────────────────────
    "TITLE_META_DUPLICATE_PAIR": _IssueSpec(
        category="duplicate", severity="warning",
        description="Both title and meta description duplicated on another page",
        recommendation="This page and another share identical title and meta description. Update both to be unique.",
        human_description="Identical Title & Description",
        fixability="content_edit",
    ),
    # ── Security (§E1) ────────────────────────────────────────────────────
    "HTTP_PAGE": _IssueSpec(
        category="security", severity="critical",
        description="Page is served over HTTP, not HTTPS",
        recommendation="Migrate to HTTPS and configure a server-side 301 redirect from HTTP to HTTPS.",
        human_description="Unsecured Page",
        fixability="developer_needed",
    ),
    "MIXED_CONTENT": _IssueSpec(
        category="security", severity="warning",
        description="HTTPS page loads resources over HTTP",
        recommendation="Update all resource URLs to use HTTPS. Check images, scripts, stylesheets, and iframes.",
        human_description="Partially Unsecured Page",
        fixability="developer_needed",
    ),
    "MISSING_HSTS": _IssueSpec(
        category="security", severity="info",
        description="HTTPS page is missing the Strict-Transport-Security header",
        recommendation="Add Strict-Transport-Security: max-age=31536000; includeSubDomains to all HTTPS responses.",
        human_description="Security Header Missing",
        fixability="developer_needed",
    ),
    "UNSAFE_CROSS_ORIGIN_LINK": _IssueSpec(
        category="security", severity="info",
        description="External link opens in a new tab without rel=\"noopener\" or rel=\"noreferrer\"",
        recommendation="Add rel=\"noopener noreferrer\" to all <a target=\"_blank\"> links pointing to external URLs.",
        human_description="Unsafe External Link",
        fixability="developer_needed",
    ),
    "WWW_CANONICALIZATION": _IssueSpec(
        category="security", severity="warning",
        description="Both www and non-www versions of the site resolve without redirecting to each other",
        recommendation="Configure a 301 redirect so one version (www or non-www) redirects to the other. This consolidates link equity and avoids duplicate content.",
        human_description="www/non-www Not Consolidated",
        fixability="developer_needed",
    ),
    # ── URL structure (§E2) ───────────────────────────────────────────────
    "URL_UPPERCASE": _IssueSpec(
        category="url_structure", severity="warning",
        description="URL path contains uppercase characters",
        recommendation="Use lowercase-only URLs. Most web servers will auto-redirect uppercase URLs to lowercase, "
                       "but this creates an unnecessary extra redirect. Update internal links and page slugs "
                       "to use lowercase only to avoid that redirect entirely.",
        human_description="Mixed-Case Web Address",
        fixability="content_edit",
    ),
    "URL_HAS_SPACES": _IssueSpec(
        category="url_structure", severity="warning",
        description="URL contains encoded spaces (%20)",
        recommendation="Replace spaces in URLs with hyphens.",
        human_description="Spaces in Web Address",
        fixability="content_edit",
    ),
    "URL_HAS_UNDERSCORES": _IssueSpec(
        category="url_structure", severity="info",
        description="URL path uses underscores instead of hyphens",
        recommendation="Use hyphens as word separators in URL paths. Google treats underscores as word-joiners.",
        human_description="Underscores in Web Address",
        fixability="content_edit",
    ),
    "URL_TOO_LONG": _IssueSpec(
        category="url_structure", severity="info",
        description="URL exceeds 200 characters",
        recommendation="Shorten the URL slug. Long URLs are harder to share and may be truncated in search results.",
        human_description="Overly Long Web Address",
        fixability="content_edit",
    ),
    # ── v1.5 bug fixes — codes that existed in scoring but had no catalogue entry ──
    "IMG_ALT_MISSING": _IssueSpec(
        category="image", severity="warning",
        description="One or more images are missing an alt attribute or have empty/blank alt text",
        recommendation="Add a descriptive alt attribute to every <img> tag. Describe what the image shows "
                       "in plain language, e.g. alt=\"Counsellor speaking with a young person\". "
                       "Every image should have meaningful alt text for accessibility and SEO.",
        human_description="Images Missing Alt Text",
        fixability="wp_fixable",
    ),
    # ── v1.5 new codes ────────────────────────────────────────────────────
    "INTERNAL_REDIRECT_301": _IssueSpec(
        category="redirect", severity="info",
        description="Internal page URL redirects with a 301 — links should point to the final URL",
        recommendation="Update all internal links pointing to this URL to use the final destination directly. "
                       "This eliminates an unnecessary redirect for every visitor.",
        human_description="Internal Redirect Link",
        fixability="developer_needed",
    ),
    "MISSING_VIEWPORT_META": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page is missing the viewport meta tag",
        recommendation='Add <meta name="viewport" content="width=device-width, initial-scale=1"> to the <head>. '
                       "Without it, mobile browsers render the page at desktop width and zoom out, making it hard to use.",
        human_description="Not Mobile-Friendly",
        fixability="developer_needed",
    ),
    "IMG_BROKEN": _IssueSpec(
        category="image", severity="critical",
        description="Image src URL returns an error response (4xx/5xx)",
        recommendation="Replace or remove the broken image. Use your CMS media library to re-upload the file "
                       "or update the src URL to point to the correct location.",
        human_description="Broken Image",
        fixability="developer_needed",
    ),
    # ── v1.9image - Enhanced Image Analysis ─────────────────────────────────
    "IMG_ALT_TOO_SHORT": _IssueSpec(
        category="image", severity="warning",
        description="Image alt text is too short (under 5 characters)",
        recommendation="Expand the alt text to at least 5 characters. Describe what the image shows, "
                       "not just a single word.",
        human_description="Alt Text Too Short",
        fixability="wp_fixable",
    ),
    "IMG_ALT_TOO_LONG": _IssueSpec(
        category="image", severity="warning",
        description="Image alt text is too long (over 125 characters)",
        recommendation="Shorten the alt text to under 125 characters. Be concise while still describing "
                       "the image content. Screen readers may truncate longer alt text.",
        human_description="Alt Text Too Long",
        fixability="wp_fixable",
    ),
    "IMG_ALT_GENERIC": _IssueSpec(
        category="image", severity="warning",
        description="Image alt text uses a generic term like 'image', 'photo', or 'picture'",
        recommendation="Replace generic alt text with a specific description of what the image shows. "
                       "Instead of 'photo', describe the scene, people, or objects depicted.",
        human_description="Generic Alt Text",
        fixability="wp_fixable",
    ),
    "IMG_ALT_DUP_FILENAME": _IssueSpec(
        category="image", severity="warning",
        description="Image alt text matches the filename",
        recommendation="Write descriptive alt text instead of using the filename. Describe what the "
                       "image shows to help search engines and screen reader users.",
        human_description="Alt Text is Filename",
        fixability="wp_fixable",
    ),
    "IMG_ALT_MISUSED": _IssueSpec(
        category="image", severity="warning",
        description="Alt text usage is incorrect for image type (decorative image has alt text)",
        recommendation="Decorative images should have empty alt=\"\" to be skipped by screen readers. "
                       "Only meaningful images should have descriptive alt text.",
        human_description="Alt Text Misused",
        fixability="content_edit",
    ),
    "IMG_SLOW_LOAD": _IssueSpec(
        category="image", severity="warning",
        description="Image takes too long to load (over 1 second)",
        recommendation="Optimize the image by compressing it, reducing dimensions, or using a CDN. "
                       "Consider lazy loading for below-the-fold images.",
        human_description="Slow Loading Image",
        fixability="developer_needed",
    ),
    "IMG_OVERSCALED": _IssueSpec(
        category="image", severity="warning",
        description="Image intrinsic size is more than 2x its display size (wasted bandwidth)",
        recommendation="Resize the image to match its display dimensions. Use srcset to serve "
                       "appropriately sized images to different devices.",
        human_description="Overscaled Image",
        fixability="content_edit",
    ),
    "IMG_POOR_COMPRESSION": _IssueSpec(
        category="image", severity="warning",
        description="Image has poor compression efficiency (high bytes per pixel)",
        recommendation="Re-compress the image using WebP format for better efficiency. "
                       "Use tools like Squoosh or ImageOptim for lossless compression.",
        human_description="Poor Compression",
        fixability="content_edit",
    ),
    "IMG_FORMAT_LEGACY": _IssueSpec(
        category="image", severity="info",
        description="Image uses legacy format (JPEG/PNG/GIF) where WebP would save significant space",
        recommendation="Convert to WebP format for 25-35% smaller file sizes with the same quality. "
                       "Most modern browsers support WebP.",
        human_description="Legacy Image Format",
        fixability="content_edit",
    ),
    "IMG_NO_SRCSET": _IssueSpec(
        category="image", severity="info",
        description="Large image lacks srcset for responsive delivery",
        recommendation="Add a srcset attribute to serve appropriately sized images to mobile devices. "
                       "This improves load times on smaller screens.",
        human_description="Missing Responsive Images",
        fixability="developer_needed",
    ),
    "IMG_DUPLICATE_CONTENT": _IssueSpec(
        category="image", severity="info",
        description="Same image content used under multiple URLs",
        recommendation="Consolidate duplicate images to a single URL. This saves server space "
                       "and improves caching efficiency.",
        human_description="Duplicate Image",
        fixability="developer_needed",
    ),
    "LINK_EMPTY_ANCHOR": _IssueSpec(
        category="metadata", severity="warning",
        description="Link has no visible anchor text — screen readers and search engines cannot describe its destination",
        recommendation='Add descriptive text inside the link. If it is an icon-only link, add an aria-label attribute (e.g. aria-label="Donate now").',
        human_description="Empty Link Text",
        fixability="content_edit",
    ),
    "ANCHOR_TEXT_GENERIC": _IssueSpec(
        category="metadata", severity="warning",
        description="Links use non-descriptive anchor text like 'click here' or 'read more'",
        recommendation="Replace generic link text with descriptive text that tells the reader (and search engines) where the link goes. Instead of 'click here', write 'view our counselling services'.",
        human_description="Non-Descriptive Link Text",
        fixability="content_edit",
    ),
    "INTERNAL_NOFOLLOW": _IssueSpec(
        category="crawlability", severity="warning",
        description='Internal link carries rel="nofollow", which may prevent search engines from discovering linked pages',
        recommendation='Remove the nofollow attribute from internal links. Reserve rel="nofollow" for links to '
                       "external or user-generated content.",
        human_description="Blocked Internal Link",
        fixability="developer_needed",
    ),
    "PAGE_SIZE_LARGE": _IssueSpec(
        category="crawlability", severity="warning",
        description="HTML page response is unusually large — slower to load, especially on mobile connections",
        recommendation="Reduce page weight by removing unused HTML, lazy-loading off-screen content, and deferring "
                       "non-critical scripts. Large pages cost more mobile data and take longer to render.",
        human_description="Overweight Page",
        fixability="developer_needed",
    ),
    # ── v1.6 new codes ────────────────────────────────────────────────────────
    "LANG_MISSING": _IssueSpec(
        category="metadata", severity="warning",
        description="Page is missing the lang attribute on the <html> element",
        recommendation='Add a lang attribute to your <html> tag, e.g. <html lang="en">. '
                       "This tells search engines and screen readers what language your content is in, "
                       "improving accessibility and search accuracy for multilingual queries.",
        human_description="No Language Declared",
        fixability="developer_needed",
    ),
    "TITLE_H1_MISMATCH": _IssueSpec(
        category="metadata", severity="warning",
        description="The page title and the H1 heading share no significant words",
        recommendation="Align the page title and H1 heading so they describe the same topic. "
                       "They do not need to be identical, but both should clearly reflect the page's main subject. "
                       "Significant mismatch confuses users who click a search result and then see an unrelated heading.",
        human_description="Title and Heading Disagree",
        fixability="wp_fixable",
    ),
    "HTTPS_REDIRECT_MISSING": _IssueSpec(
        category="security", severity="critical",
        description="HTTP version of the site does not redirect to HTTPS",
        recommendation="Configure a server-side 301 redirect from http:// to https:// for all URLs on your domain. "
                       "Without this, visitors who type your address without 'https' will reach an insecure version "
                       "of your site — and search engines treat HTTP and HTTPS as separate, competing URLs.",
        human_description="Insecure URL Not Redirected",
        fixability="developer_needed",
    ),
    "CANONICAL_SELF_MISSING": _IssueSpec(
        category="metadata", severity="info",
        description="Indexable page has no canonical tag — consider adding a self-referencing canonical",
        recommendation='Add <link rel="canonical" href="[this-page-url]"> to the page <head>. '
                       "A self-referencing canonical is a best-practice signal to search engines "
                       "confirming which URL is the preferred version of this page.",
        human_description="No Canonical Tag",
        fixability="developer_needed",
    ),
    # ── AI Readiness ──────────────────────────────────────────────────────
    "LLMS_TXT_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="No llms.txt found at root",
        recommendation="Create an /llms.txt file to help LLMs and AI agents (Gemini, Perplexity) "
                       "accurately crawl and cite your high-value content.",
        human_description="Missing AI Instruction File",
        fixability="content_edit",
    ),
    "LLMS_TXT_INVALID": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="/llms.txt format is invalid",
        recommendation="Ensure your /llms.txt uses text/plain MIME type and includes a Markdown-style "
                       "H1 title, a blockquote summary, and a list of high-value URLs (max 20).",
        human_description="Invalid AI Instruction File",
        fixability="content_edit",
    ),
    "SEMANTIC_DENSITY_LOW": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Text-to-HTML ratio is below 10%",
        recommendation="Clean up excessive code-bloat (styles, scripts, nested divs). "
                       "High code-to-text ratios consume more AI tokens and confuse retrieval engines.",
        human_description="High Code-to-Text Ratio",
        fixability="developer_needed",
    ),
    "DOCUMENT_PROPS_MISSING": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="PDF is missing internal Title or Subject metadata",
        recommendation="Update PDF document properties to include a clear Title and Subject. "
                       "AIs use these properties for source labels and citations.",
        human_description="Missing Document Info",
        fixability="content_edit",
    ),
    "JSON_LD_MISSING": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="No JSON-LD structured data found on this indexable page",
        recommendation="Add <script type=\"application/ld+json\"> markup. Schema is the "
                       "'knowledge graph' used by AI systems for RAG-based answers.",
        human_description="Missing AI Schema",
        fixability="developer_needed",
    ),
    "CONVERSATIONAL_H2_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="H2 headings do not use conversational interrogatives (How, What, Why)",
        recommendation="Rewrite some H2 headings as questions. LLMs prefer direct question-answer "
                       "pairings for more accurate retrieval and citing.",
        human_description="Non-Conversational Headings",
        fixability="content_edit",
    ),
    "BLOG_SECTIONS_MISSING": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Blog or article page lacks sufficient heading structure for AI citation anchors",
        recommendation="Add H2/H3 headings to break content into named sections. AI engines use "
                       "headings as citation anchors — a long post with fewer than 3 headings "
                       "cannot be accurately quoted or cited by AI.",
        human_description="No Section Headings for AI Citation",
        fixability="content_edit",
    ),
    # v2.0 AI Bot Access
    "AI_BOT_SEARCH_BLOCKED": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="A major AI search bot is disallowed in robots.txt",
        recommendation="Allow AI search bots in robots.txt. This bot enables ChatGPT, Gemini, "
                       "and other AI engines to include your site in their answers.",
        human_description="AI Search Bot Blocked",
        fixability="developer_needed",
    ),
    "AI_BOT_TRAINING_DISALLOWED": _IssueSpec(
        category="ai_readiness", severity="info",
        description="An AI training bot is disallowed in robots.txt",
        recommendation="This may be intentional. If accidental, allow the bot. "
                       "Blocking training bots does not affect AI search visibility.",
        human_description="AI Training Bot Disallowed",
        fixability="developer_needed",
    ),
    "AI_BOT_USER_FETCH_BLOCKED": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="An AI user-fetch bot is disallowed in robots.txt — this block has no effect",
        recommendation="Remove the block. User-fetch bots (ChatGPT-User, Claude-User) do not honor "
                       "robots.txt by design. Blocking them signals misconfiguration.",
        human_description="AI User Bot Blocked (Ineffective)",
        fixability="developer_needed",
    ),
    "AI_BOT_DEPRECATED_DIRECTIVE": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="robots.txt references a deprecated AI bot user agent",
        recommendation="Remove deprecated directives (anthropic-ai, claude-web) and replace with "
                       "current bot names (ClaudeBot, Claude-SearchBot, Claude-User).",
        human_description="Deprecated AI Bot Name in robots.txt",
        fixability="developer_needed",
    ),
    "AI_BOT_NO_AI_DIRECTIVES": _IssueSpec(
        category="ai_readiness", severity="info",
        description="robots.txt has no explicit directives for known AI bots",
        recommendation="Add explicit AI bot rules to make your intent clear. Example: allow all "
                       "search bots while optionally blocking training bots.",
        human_description="No AI Bot Configuration",
        fixability="developer_needed",
    ),
    "AI_BOT_BLANKET_DISALLOW": _IssueSpec(
        category="ai_readiness", severity="critical",
        description="robots.txt blocks all bots with User-agent: * / Disallow: /",
        recommendation="Update robots.txt to allow at least AI search bots. Remove 'Disallow: /' "
                       "or add specific allow rules for AI crawlers.",
        human_description="All Bots Blocked",
        fixability="developer_needed",
    ),
    "AI_BOT_TABLE_STALE": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Internal AI bot reference table has not been reviewed in >12 months",
        recommendation="Review and update the TalkingToad AI bot reference table.",
        human_description="AI Bot Table Needs Review",
        fixability="developer_needed",
    ),
    # v2.0 Schema Typing
    "SCHEMA_TYPE_MISMATCH": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Page schema type does not match inferred page type",
        recommendation="Ensure JSON-LD @type matches the page content (Article for blog posts, "
                       "Person for team bios, Service for service pages).",
        human_description="Mismatched Schema Type",
        fixability="content_edit",
    ),
    "SCHEMA_DEPRECATED_TYPE": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page uses deprecated schema.org types",
        recommendation="Replace deprecated schema types with modern equivalents from schema.org.",
        human_description="Deprecated Schema Type",
        fixability="content_edit",
    ),
    "SCHEMA_TYPE_CONFLICT": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Page declares multiple conflicting schema types",
        recommendation="Use a single coherent @type. For multiple entities use @graph or nesting.",
        human_description="Conflicting Schema Types",
        fixability="content_edit",
    ),
    # v2.0 Content Extractability
    "CONTENT_NOT_EXTRACTABLE_NO_TEXT": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Page has no visible text — only images, video, or interactive media",
        recommendation="Add descriptive text, captions, or transcripts. AI systems cannot extract "
                       "information from images or videos without accompanying text.",
        human_description="No Text Content",
        fixability="content_edit",
    ),
    "CONTENT_THIN": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Page has very little text (under 100 words)",
        recommendation="Expand the page with substantive content. Thin pages provide insufficient "
                       "context for AI systems to generate accurate summaries.",
        human_description="Thin Content",
        fixability="content_edit",
    ),
    "CONTENT_UNSTRUCTURED": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Page has substantial text but no heading structure",
        recommendation="Add H2 and H3 headings to break content into sections. Headings help AI "
                       "systems identify topics and extract structured information.",
        human_description="No Heading Structure",
        fixability="content_edit",
    ),
    "CONTENT_IMAGE_HEAVY": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page has significantly more images than text sections",
        recommendation="Add descriptive captions and surrounding text for each image. AI systems "
                       "rely on text context to interpret visual content.",
        human_description="Image-Heavy Layout",
        fixability="content_edit",
    ),
    # v2.0 Citation & Attribution
    "CITATIONS_MISSING_SUBSTANTIAL_CONTENT": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page has 200+ words but no citations or source attribution",
        recommendation="Add citations to factual claims. Use inline references or a Sources section.",
        human_description="Missing Citations",
        fixability="content_edit",
    ),
    "CITATIONS_ORPHANED": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page has citations without surrounding context",
        recommendation="Ensure each citation appears within a sentence that explains its relevance.",
        human_description="Citations Without Context",
        fixability="content_edit",
    ),
    "CITATIONS_SOURCES_INACCESSIBLE": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Page cites sources that are broken or inaccessible",
        recommendation="Replace broken citation links with working alternatives.",
        human_description="Inaccessible Citation Sources",
        fixability="content_edit",
    ),
}


_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "not", "no",
    "its", "it", "this", "that", "we", "our", "your", "their", "my",
})


def _sig_words(text: str) -> set[str]:
    """Return significant (non-stop, length>=2) lowercase words from *text*."""
    return {
        w.lower() for w in re.findall(r"\w+", text)
        if len(w) >= 2 and w.lower() not in _STOP_WORDS
    }


def _titles_mismatch(title: str, h1: str) -> bool:
    """Return True if the page title and the H1 heading share no significant words.

    Strips a common site-name suffix (text after ' | ', ' - ', ' – ', ' · ')
    from the title before comparing so that "About Us | My Charity" and
    "About Us" are treated as matching rather than mismatching.
    The middle dot (·) is included because Yoast uses it as a common separator.
    """
    # Strip site-name suffix — pipe, hyphen, en-dash, em-dash, middle dot
    clean_title = re.split(r"\s[|·\-–—]\s", title)[0].strip()
    title_words = _sig_words(clean_title)
    h1_words = _sig_words(h1)
    if not title_words or not h1_words:
        return False  # too short to compare meaningfully
    return title_words.isdisjoint(h1_words)


def make_issue(
    code: str,
    page_url: str | None = None,
    extra: dict | None = None,
    *,
    job_id: str = "",
) -> Issue:
    """Construct an :class:`Issue` from a code in the catalogue.

    Automatically populates *impact*, *effort*, and *priority_rank* from
    :data:`_ISSUE_SCORING`.  Unknown codes get zeroes for all three.

    Args:
        code: The issue code from the catalogue.
        page_url: The URL of the page where the issue was found.
        extra: Optional supplementary data.
        job_id: The crawl job ID (used for image analysis module).
    """
    spec = _CATALOGUE[code]
    impact, effort = _ISSUE_SCORING.get(code, (0, 0))
    priority_rank = (impact * 10) - (effort * 2)
    return Issue(
        code=code,
        category=spec.category,
        severity=spec.severity,
        description=spec.description,
        recommendation=spec.recommendation,
        page_url=page_url,
        extra=extra,
        impact=impact,
        effort=effort,
        priority_rank=priority_rank,
        human_description=spec.human_description,
        what_it_is=spec.what_it_is,
        impact_desc=spec.impact_desc,
        how_to_fix=spec.how_to_fix,
        fixability=spec.fixability,
    )


# ---------------------------------------------------------------------------
# Per-page checks
# ---------------------------------------------------------------------------

_DEFAULT_PAGE_SIZE_LIMIT_KB = 300


def check_page(
    page: ParsedPage,
    *,
    sitemap_urls: set[str] | None = None,
    favicon_emitted: bool = False,
    hsts_checked_hosts: set[str] | None = None,
    page_size_limit_kb: int = _DEFAULT_PAGE_SIZE_LIMIT_KB,
    suppress_h1_strings: list[str] | None = None,
    suppress_banner_h1: bool = False,
    exempt_anchor_urls: set[str] | None = None,
    ignored_image_patterns: list[str] | None = None,
) -> list[Issue]:
    """Run all per-page issue checks.

    Args:
        page: The parsed page to check.
        sitemap_urls: Set of normalised URLs found in the sitemap (or None if no sitemap).
        favicon_emitted: True if FAVICON_MISSING has already been emitted this job.
        hsts_checked_hosts: Mutable set of hosts already checked for HSTS (pass the same
            set across all pages in a job so we only emit once per host).

    Returns:
        List of issues found. Cross-page checks (duplicates, near-duplicates) are
        not included — call :func:`check_cross_page` after all pages are crawled.
    """
    issues: list[Issue] = []
    url = page.url

    # Pages with noindex directives are intentionally excluded from search — skip SEO
    # checks that would only apply to indexed pages. We still run crawlability checks
    # (to surface the noindex issue itself) and security checks.
    is_indexable = page.is_indexable

    # Build effective H1 list — filter out theme-injected headings the user
    # has explicitly suppressed (e.g. a Salient page-header banner title that
    # repeats on every post page).
    # Normalise both sides: strip whitespace and compare case-insensitively so
    # that minor variations (trailing \xa0, different capitalisation) don't
    # silently defeat the suppression.
    _suppress_norm = {s.strip().casefold() for s in (suppress_h1_strings or [])}
    effective_h1s = [h for h in page.h1_tags if h.strip().casefold() not in _suppress_norm]
    effective_outline = [
        h for h in page.headings_outline
        if not (h["level"] == 1 and h["text"].strip().casefold() in _suppress_norm)
    ]

    # When suppress_banner_h1 is enabled, detect and remove the theme-injected
    # banner H1.  Two signals identify a banner:
    #   1. Position: the first H1 in the DOM (themes inject banners before content)
    #   2. CSS class: common theme banner classes (entry-title, page-title, etc.)
    # The first H1 is removed if it mismatches the title OR has a banner class.
    # Only applied when there are 2+ H1s so we never remove the only heading.
    _BANNER_CLASSES = re.compile(
        r'entry-title|page-title|page-header|banner-title|hero-title|archive-title',
        re.IGNORECASE,
    )

    if suppress_banner_h1 and page.title and len(effective_h1s) >= 2:
        first_h1 = effective_h1s[0]
        # Check CSS classes on the first H1 in the outline
        first_h1_outline = next(
            (h for h in effective_outline if h.get("level") == 1),
            None,
        )
        has_banner_class = bool(
            first_h1_outline
            and _BANNER_CLASSES.search(first_h1_outline.get("classes", ""))
        )
        is_mismatch = _titles_mismatch(page.title, first_h1)

        if is_mismatch or has_banner_class:
            _banner_text = first_h1.strip().casefold()
            effective_h1s = effective_h1s[1:]
            effective_outline = [
                h for h in effective_outline
                if not (
                    h["level"] == 1
                    and h.get("text", "").strip().casefold() == _banner_text
                )
            ]

    if is_indexable:
        # ── Title ──────────────────────────────────────────────────────────
        if not page.title:
            issues.append(make_issue("TITLE_MISSING", url,
                                     extra={"h1": effective_h1s[0] if effective_h1s else None}))
        else:
            length = len(page.title)
            if length < 30:
                issue = make_issue("TITLE_TOO_SHORT", url)
                issue.extra = {"title": page.title, "length": length}
                issues.append(issue)
            elif length > 60:
                issue = make_issue("TITLE_TOO_LONG", url)
                issue.extra = {"title": page.title, "length": length}
                issues.append(issue)

        # ── Meta description ───────────────────────────────────────────────
        if not page.meta_description:
            issues.append(make_issue("META_DESC_MISSING", url))
        else:
            length = len(page.meta_description)
            if length < 70:
                issue = make_issue("META_DESC_TOO_SHORT", url)
                issue.extra = {"description": page.meta_description, "length": length}
                issues.append(issue)
            elif length > 160:
                issue = make_issue("META_DESC_TOO_LONG", url)
                issue.extra = {"description": page.meta_description, "length": length}
                issues.append(issue)

        # ── OG tags ────────────────────────────────────────────────────────
        if not page.og_title:
            issues.append(make_issue("OG_TITLE_MISSING", url,
                                     extra={"title": page.title}))
        if not page.og_description:
            issues.append(make_issue("OG_DESC_MISSING", url,
                                     extra={"meta_description": page.meta_description}))
        if not page.og_image:
            issues.append(make_issue("OG_IMAGE_MISSING", url))
        if not page.twitter_card:
            issues.append(make_issue("TWITTER_CARD_MISSING", url))

        # ── Canonical tag ──────────────────────────────────────────────────
        _check_canonical(page, issues)

        # ── Canonical self (best-practice for all indexable pages) ──────────
        # Only emit if CANONICAL_MISSING hasn't already fired — that issue is
        # more specific and actionable; emitting both on the same page is redundant.
        if page.canonical_url is None and not any(i.code == "CANONICAL_MISSING" for i in issues):
            issues.append(make_issue("CANONICAL_SELF_MISSING", url,
                                     extra={"expected_canonical": url}))

        # ── Language attribute ─────────────────────────────────────────────
        if not page.lang_attr:
            issues.append(make_issue("LANG_MISSING", url))

        # ── Title vs H1 consistency ────────────────────────────────────────
        # Use effective_h1s (suppressed strings removed) so theme-injected
        # headings don't trigger a false mismatch.
        if page.title and effective_h1s:
            if all(_titles_mismatch(page.title, h1) for h1 in effective_h1s):
                # Before flagging, check whether the title matches an H2.
                # Many WordPress themes inject the parent-page title as an H1
                # banner on sub-pages, while the real content heading is an H2.
                # If the title shares significant words with any H2 we treat
                # the H1 as a structural/navigation element and skip the flag.
                h2_texts = [
                    h["text"] for h in (page.headings_outline or [])
                    if h.get("level") == 2 and h.get("text")
                ]
                title_matches_h2 = any(
                    not _titles_mismatch(page.title, h2) for h2 in h2_texts
                )
                if not title_matches_h2:
                    issues.append(make_issue("TITLE_H1_MISMATCH", url,
                                             extra={"title": page.title, "h1": effective_h1s[0]}))

        # ── Headings ───────────────────────────────────────────────────────
        _check_headings(page, issues, effective_h1s=effective_h1s, effective_outline=effective_outline)

    # ── Favicon (homepage only, once per job — checked regardless of noindex) ──
    if page.has_favicon is False and not favicon_emitted:
        issues.append(make_issue("FAVICON_MISSING", url))

    # ── Crawlability ───────────────────────────────────────────────────────
    _check_crawlability(page, issues)

    # ── Not in sitemap (only meaningful for indexable pages) ──────────────
    # Skip pages with query strings — paginated URLs, search results, and
    # filtered views are intentionally absent from sitemaps.
    if sitemap_urls is not None and is_indexable and not urlparse(url).query:
        if page.final_url not in sitemap_urls and page.url not in sitemap_urls:
            issues.append(make_issue("NOT_IN_SITEMAP", url))

    # ── Security (§E1) ────────────────────────────────────────────────────
    _check_security(page, issues, hsts_checked_hosts=hsts_checked_hosts)

    # ── Pagination links (§E3) ────────────────────────────────────────────
    if page.pagination_next or page.pagination_prev:
        issues.append(make_issue(
            "PAGINATION_LINKS_PRESENT", url,
            extra={"next": page.pagination_next, "prev": page.pagination_prev},
        ))

    # ── Meta refresh redirect (§E4) ───────────────────────────────────────
    if page.meta_refresh_url is not None:
        issues.append(make_issue("META_REFRESH_REDIRECT", url,
                                 extra={"refresh_url": page.meta_refresh_url}))

    # ── Thin content (§E5) ────────────────────────────────────────────────
    if page.word_count is not None and 0 < page.word_count < 300 and page.is_indexable:
        issues.append(make_issue("THIN_CONTENT", url, extra={"word_count": page.word_count}))

    # ── Crawl depth (§E7) ────────────────────────────────────────────────
    if page.crawl_depth is not None and page.crawl_depth > 4:
        issues.append(make_issue("HIGH_CRAWL_DEPTH", url,
                                 extra={"crawl_depth": page.crawl_depth}))

    # ── Content staleness ────────────────────────────────────────────────
    if page.last_modified and page.is_indexable:
        try:
            from email.utils import parsedate_to_datetime
            from datetime import timezone as _tz
            lm_dt = parsedate_to_datetime(page.last_modified)
            if lm_dt.tzinfo is None:
                lm_dt = lm_dt.replace(tzinfo=_tz.utc)
            age_days = (datetime.now(_tz.utc) - lm_dt).days
            if age_days > 365:
                issues.append(make_issue("CONTENT_STALE", url,
                    extra={"last_modified": page.last_modified, "age_days": age_days}))
        except Exception:
            pass

    # ── Image alt text ────────────────────────────────────────────────────
    if page.img_missing_alt_count > 0:
        srcs = page.img_missing_alt_srcs or []
        # Filter out images matching ignored patterns (e.g. theme SVG icons)
        if ignored_image_patterns:
            srcs = [s for s in srcs if not any(p in s for p in ignored_image_patterns)]
        if srcs:
            issue = make_issue("IMG_ALT_MISSING", url,
                               extra={"missing_alt_count": len(srcs),
                                      "img_missing_alt_srcs": srcs[:10]})
            listed = ", ".join(srcs[:5])
            suffix = f" and {len(srcs) - 5} more" if len(srcs) > 5 else ""
            issue.description = (
                f"{len(srcs)} image{'s' if len(srcs) > 1 else ''} "
                f"missing alt text: {listed}{suffix}"
            )
            issues.append(issue)

    # ── Viewport meta (mobile-friendliness) ──────────────────────────────
    if not page.has_viewport_meta:
        issues.append(make_issue("MISSING_VIEWPORT_META", url))

    # ── Structured data (schema.org) ──────────────────────────────────────
    if not page.schema_types and is_indexable:
        issues.append(make_issue("SCHEMA_MISSING", url))

    # ── Empty anchor text ─────────────────────────────────────────────────
    if page.empty_anchor_count > 0:
        anchors = page.empty_anchor_hrefs or []
        # Support both old format (list[str]) and new format (list[dict])
        if anchors and isinstance(anchors[0], str):
            anchors = [{"href": h, "aria_label": None, "has_children": False} for h in anchors]
        # Filter out URLs the user has explicitly exempted (e.g. social media icon links)
        if exempt_anchor_urls:
            anchors = [a for a in anchors if a["href"] not in exempt_anchor_urls]
        if anchors:
            issue = make_issue("LINK_EMPTY_ANCHOR", url,
                               extra={"empty_anchor_count": len(anchors),
                                      "empty_anchors": anchors[:10],
                                      # Keep legacy field for backwards compat
                                      "empty_anchor_hrefs": [a["href"] for a in anchors[:10]]})
            href_list = [a["href"] for a in anchors[:5]]
            listed = ", ".join(href_list)
            suffix = f" and {len(anchors) - 5} more" if len(anchors) > 5 else ""
            issue.description = (
                f"{len(anchors)} link{'s' if len(anchors) > 1 else ''} "
                f"with no anchor text: {listed}{suffix}"
            )
            issues.append(issue)

    # ── Generic anchor text ──────────────────────────────────────────────
    if page.is_indexable and page.links:
        generic_links = [
            link for link in page.links
            if link.text and link.text.strip().lower() in _GENERIC_ANCHOR_TEXTS
        ]
        if generic_links:
            issues.append(make_issue("ANCHOR_TEXT_GENERIC", url,
                extra={"count": len(generic_links),
                        "examples": [{"href": l.url, "text": l.text} for l in generic_links[:5]]}))

    # ── Internal nofollow links ───────────────────────────────────────────
    if page.internal_nofollow_count > 0:
        issues.append(make_issue("INTERNAL_NOFOLLOW", url,
                                 extra={"internal_nofollow_count": page.internal_nofollow_count}))

    # ── Page size ─────────────────────────────────────────────────────────
    _page_size_threshold = page_size_limit_kb * 1024
    if page.response_size_bytes > _page_size_threshold:
        size_kb = round(page.response_size_bytes / 1024, 1)
        issue = make_issue("PAGE_SIZE_LARGE", url,
                           extra={"size_bytes": page.response_size_bytes,
                                  "size_kb": size_kb,
                                  "limit_kb": page_size_limit_kb})
        issue.description = f"Page HTML is {size_kb} KB (exceeds {page_size_limit_kb} KB limit)"
        issues.append(issue)

    # ── AI Readiness (§1.7) ───────────────────────────────────────────────
    # Semantic Density (Text-to-HTML ratio < 10%)
    if page.text_to_html_ratio is not None and page.text_to_html_ratio < 0.10 and page.is_indexable:
        extra: dict = {
            "ratio": round(page.text_to_html_ratio, 4),
            "ratio_pct": f"{page.text_to_html_ratio * 100:.1f}%",
        }
        if page.code_breakdown:
            extra["breakdown"] = page.code_breakdown
            # Diagnose the biggest contributor
            bd = page.code_breakdown
            parts = [
                ("Inline scripts", bd.get("script_kb", 0)),
                ("Inline styles", bd.get("style_kb", 0)),
                ("SVG graphics", bd.get("svg_kb", 0)),
                ("HTML markup", bd.get("markup_kb", 0)),
            ]
            parts.sort(key=lambda x: x[1], reverse=True)
            biggest = parts[0]
            total = bd.get("html_total_kb", 1)
            if biggest[1] > 0:
                extra["diagnosis"] = (
                    f"{biggest[0]} ({biggest[1]} KB) account for "
                    f"{biggest[1] / total * 100:.0f}% of the page. "
                    f"Visible text is only {bd.get('text_kb', 0)} KB "
                    f"out of {total} KB total."
                )
        issues.append(make_issue("SEMANTIC_DENSITY_LOW", url, extra=extra))

    # JSON-LD Missing
    if not page.has_json_ld and page.is_indexable and not url.endswith(".pdf"):
        issues.append(make_issue("JSON_LD_MISSING", url))

    # Conversational H2s — also fires when no H2s exist on a substantial page
    if page.is_indexable and not url.endswith(".pdf"):
        h2s = [h["text"] for h in (page.headings_outline or []) if h.get("level") == 2]
        if not h2s and page.word_count and page.word_count >= 300:
            # Substantial content with zero H2s — AI has nothing to anchor citations to
            issues.append(make_issue("CONVERSATIONAL_H2_MISSING", url,
                                     extra={"h2_headings": [], "word_count": page.word_count}))
        elif h2s:
            interrogatives = re.compile(r"\b(how|what|why|who|where|when|which)\b", re.I)
            if not any(interrogatives.search(h) for h in h2s):
                issues.append(make_issue("CONVERSATIONAL_H2_MISSING", url,
                                         extra={"h2_headings": h2s[:8]}))

    # Blog/article pages without enough heading sections for AI citation
    if page.is_indexable and page.word_count and page.word_count >= 500:
        is_blog_like = (
            "BlogPosting" in (page.schema_types or [])
            or "Article" in (page.schema_types or [])
            or any(seg in url for seg in ["/blog/", "/post/", "/article/", "/news/", "/stories/", "/insight"])
        )
        if is_blog_like:
            meaningful_headings = [
                h for h in (page.headings_outline or [])
                if h.get("level") in (2, 3) and len(h.get("text", "").strip()) > 5
            ]
            if len(meaningful_headings) < 3:
                issues.append(make_issue("BLOG_SECTIONS_MISSING", url, extra={
                    "word_count": page.word_count,
                    "heading_count": len(meaningful_headings),
                }))

    # ── Schema Typing (v2.0) ─────────────────────────────────────────────────
    if page.is_indexable and page.schema_types:
        try:
            from api.services.schema_typing import validate_schema_typing
            is_appropriate, issue_reason = validate_schema_typing(page)
            if not is_appropriate and issue_reason:
                if issue_reason.startswith("deprecated_schema:"):
                    issues.append(make_issue("SCHEMA_DEPRECATED_TYPE", url,
                                            extra={"schema_types": page.schema_types}))
                elif issue_reason.startswith("schema_conflict:"):
                    issues.append(make_issue("SCHEMA_TYPE_CONFLICT", url,
                                            extra={"schema_types": page.schema_types}))
                elif issue_reason.startswith("schema_mismatch:"):
                    page_type = issue_reason.split(":")[-1]
                    issues.append(make_issue("SCHEMA_TYPE_MISMATCH", url,
                                            extra={"inferred_page_type": page_type,
                                                   "schema_types": page.schema_types}))
        except Exception as e:
            logger.warning("schema_typing_error", extra={"url": url, "error": str(e)})

    # ── Content Extractability (v2.0) ─────────────────────────────────────────
    if page.is_indexable:
        try:
            from api.services.extractability import diagnose_extractability, assess_extractability
            extractability_issue = diagnose_extractability(page)
            if extractability_issue:
                assessment = assess_extractability(page)
                issues.append(make_issue(extractability_issue, url,
                                        extra={"score": assessment["score"],
                                               "issues": assessment["issues"]}))
        except Exception as e:
            logger.warning("extractability_error", extra={"url": url, "error": str(e)})

    # ── Citation Assessment (v2.0) ────────────────────────────────────────────
    if page.is_indexable and page.word_count and page.word_count > 200:
        try:
            from api.services.citation_model import PageCitations, assess_citation_readiness, diagnose_citation_issue
            page_citations = PageCitations(
                url=url,
                citations=[],
                attribution_style="none",
            )
            citation_issue = assess_citation_readiness(page_citations, page.word_count)
            diagnosis = diagnose_citation_issue(citation_issue)
            if diagnosis:
                issues.append(make_issue(diagnosis, url,
                                        extra={"word_count": page.word_count}))
        except Exception as e:
            logger.warning("citation_check_error", extra={"url": url, "error": str(e)})

    # PDF Metadata
    if url.lower().endswith(".pdf") and page.pdf_metadata is not None:
        meta = page.pdf_metadata
        if not meta.get("title") or not meta.get("subject"):
            issues.append(make_issue("DOCUMENT_PROPS_MISSING", url, extra=meta))

    return issues


def _check_security(
    page: ParsedPage,
    issues: list[Issue],
    *,
    hsts_checked_hosts: set[str] | None,
) -> None:
    url = page.url

    # HTTP_PAGE — non-HTTPS final URL
    if url.startswith("http://"):
        issues.append(make_issue("HTTP_PAGE", url,
                                 extra={"http_url": url,
                                        "https_url": "https://" + url[7:]}))
        return  # HTTPS-only checks below don't apply

    # MIXED_CONTENT
    if page.mixed_content_count > 0:
        issues.append(make_issue("MIXED_CONTENT", url,
                                 extra={"mixed_count": page.mixed_content_count}))

    # MISSING_HSTS — emit once per host
    if page.has_hsts is False:
        host = urlparse(url).netloc
        if hsts_checked_hosts is None or host not in hsts_checked_hosts:
            issues.append(make_issue("MISSING_HSTS", url,
                                     extra={"host": host}))
            if hsts_checked_hosts is not None:
                hsts_checked_hosts.add(host)

    # UNSAFE_CROSS_ORIGIN_LINK
    if page.unsafe_cross_origin_count > 0:
        issues.append(make_issue("UNSAFE_CROSS_ORIGIN_LINK", url,
                                 extra={"unsafe_link_count": page.unsafe_cross_origin_count}))


def _check_canonical(page: ParsedPage, issues: list[Issue]) -> None:
    url = page.url
    parsed_page = urlparse(url)

    if page.canonical_url is not None:
        # Has a canonical tag
        if not is_same_domain(page.canonical_url, url):
            issue = make_issue("CANONICAL_EXTERNAL", url)
            issue.extra = {"canonical_url": page.canonical_url}
            issues.append(issue)
        # Self-referencing canonical → OK, no issue
    else:
        # No canonical tag — check the two scoping conditions
        # Condition 1: has query string parameters
        if parsed_page.query:
            issues.append(make_issue("CANONICAL_MISSING", url))
        # Condition 2 (near-duplicate): handled in check_cross_page after all pages crawled


def _check_headings(
    page: ParsedPage,
    issues: list[Issue],
    *,
    effective_h1s: list[str] | None = None,
    effective_outline: list[dict] | None = None,
) -> None:
    url = page.url
    h1s = effective_h1s if effective_h1s is not None else page.h1_tags
    outline = effective_outline if effective_outline is not None else page.headings_outline

    h1_count = len(h1s)
    if h1_count == 0:
        # Include first few headings so user can see what exists
        top_headings = [f"H{h['level']}: {h['text']}" for h in outline[:5]]
        issues.append(make_issue("H1_MISSING", url,
                                 extra={"headings_found": top_headings} if top_headings else None))
    elif h1_count > 1:
        issue = make_issue("H1_MULTIPLE", url)
        issue.extra = {"h1_tags": h1s, "count": h1_count}
        issues.append(issue)

    # Empty headings
    empty_headings = [h for h in outline if not h.get("text", "").strip()]
    if empty_headings:
        issues.append(make_issue("HEADING_EMPTY", url,
            extra={"empty_levels": [f"H{h['level']}" for h in empty_headings]}))

    # Detect skipped heading levels
    levels = [h["level"] for h in outline]
    for i in range(1, len(levels)):
        if levels[i] > levels[i - 1] + 1:
            issue = make_issue("HEADING_SKIP", url)
            # Include the heading outline so user can see the skip
            issue.extra = {
                "outline": [f"H{h['level']}: {h['text']}" for h in outline],
                "skip_at": i,  # Index where skip occurred
            }
            issues.append(issue)
            break  # Report once per page


def _check_crawlability(page: ParsedPage, issues: list[Issue]) -> None:
    url = page.url
    if not page.is_indexable:
        if page.robots_source == "header":
            issues.append(make_issue("NOINDEX_HEADER", url,
                                     extra={"source": "X-Robots-Tag HTTP header",
                                            "directive": page.robots_directive}))
        else:
            issues.append(make_issue("NOINDEX_META", url,
                                     extra={"source": "meta robots tag",
                                            "directive": page.robots_directive}))


# ---------------------------------------------------------------------------
# Cross-page checks (run after all pages are crawled)
# ---------------------------------------------------------------------------

def check_cross_page(pages: list[ParsedPage], start_url: str | None = None) -> list[Issue]:
    """Run duplicate-detection checks across all crawled pages.

    Detects:
    - TITLE_DUPLICATE: same title on multiple pages
    - META_DESC_DUPLICATE: same meta description on multiple pages
    - TITLE_META_DUPLICATE_PAIR: both title and meta_desc duplicated together
    - CANONICAL_MISSING (near-duplicate condition): same title+meta_desc, no canonical
    - ORPHAN_PAGE: page has no internal links pointing to it

    Args:
        pages: All crawled HTML pages.
        start_url: Normalised start URL of the crawl (homepage — excluded from orphan check).

    Returns a flat list of issues (one per affected URL, not per pair).
    """
    issues: list[Issue] = []

    # Build lookup maps — skip redirect pages (3xx status or has redirect_url)
    title_map: dict[str, list[str]] = {}       # title → [urls]
    desc_map: dict[str, list[str]] = {}        # meta_desc → [urls]
    pair_map: dict[tuple, list[str]] = {}      # (title, desc) → [urls]

    for page in pages:
        # Skip redirects — they shouldn't be flagged as duplicates
        if page.redirect_url or (300 <= page.status_code < 400):
            continue

        t = page.title
        d = page.meta_description

        if t:
            title_map.setdefault(t, []).append(page.url)
        if d:
            desc_map.setdefault(d, []).append(page.url)
        if t and d:
            pair_map.setdefault((t, d), []).append(page.url)

    # TITLE_DUPLICATE
    for title, urls in title_map.items():
        if len(urls) > 1:
            for url in urls:
                other_urls = [u for u in urls if u != url]
                issue = make_issue("TITLE_DUPLICATE", url)
                issue.extra = {
                    "title": title,  # The actual duplicated title
                    "duplicate_urls": other_urls,  # Other pages with same title
                }
                issues.append(issue)

    # META_DESC_DUPLICATE
    for desc, urls in desc_map.items():
        if len(urls) > 1:
            for url in urls:
                other_urls = [u for u in urls if u != url]
                issue = make_issue("META_DESC_DUPLICATE", url)
                issue.extra = {
                    "description": desc,  # The actual duplicated description
                    "duplicate_urls": other_urls,  # Other pages with same description
                }
                issues.append(issue)

    # TITLE_META_DUPLICATE_PAIR and CANONICAL_MISSING (near-duplicate condition)
    duplicate_urls: set[str] = set()
    for (title, desc), urls in pair_map.items():
        if len(urls) > 1:
            for url in urls:
                other_urls = [u for u in urls if u != url]
                issue = make_issue("TITLE_META_DUPLICATE_PAIR", url)
                issue.extra = {
                    "title": title,  # The actual duplicated title
                    "description": desc,  # The actual duplicated description
                    "duplicate_urls": other_urls,  # Other pages with same pair
                }
                issues.append(issue)
                duplicate_urls.add(url)

    # CANONICAL_MISSING — near-duplicate condition (spec §3.1.2 condition 2)
    page_by_url = {p.url: p for p in pages}
    for url in duplicate_urls:
        page = page_by_url.get(url)
        if page and page.canonical_url is None and not urlparse(url).query:
            # No query string (that's condition 1, already emitted in check_page)
            # and no canonical → emit CANONICAL_MISSING for near-duplicate condition
            issues.append(make_issue("CANONICAL_MISSING", url))

    # ORPHAN_PAGE — pages with no internal links pointing to them
    linked_urls: set[str] = set()
    for page in pages:
        for link in page.links:
            if link.is_internal:
                try:
                    linked_urls.add(normalise_url(link.url))
                except Exception:
                    pass

    for page in pages:
        try:
            norm = normalise_url(page.url)
        except Exception:
            continue
        if norm == start_url:
            continue  # homepage is always the entry point
        if norm not in linked_urls:
            issues.append(make_issue("ORPHAN_PAGE", page.url,
                                     extra={"title": page.title}))

    return issues


# ---------------------------------------------------------------------------
# Redirect and broken-link issue helpers (called by engine)
# ---------------------------------------------------------------------------

def issue_for_status(status_code: int, url: str) -> Issue | None:
    """Return a broken-link issue if *status_code* indicates a broken link, else None.

    Only standard HTTP 4xx/5xx codes (400–599) are considered broken.
    Non-standard codes such as LinkedIn's 999 anti-bot response are ignored.
    503 is treated as a warning (not critical) because it is commonly returned by
    bot-protection layers and CDNs even when the page loads fine for real visitors.
    """
    if status_code == 404:
        return make_issue("BROKEN_LINK_404", url, extra={"status_code": status_code})
    if status_code == 410:
        return make_issue("BROKEN_LINK_410", url, extra={"status_code": status_code})
    if status_code == 503:
        return make_issue("BROKEN_LINK_503", url, extra={"status_code": status_code})
    if 500 <= status_code <= 599:
        return make_issue("BROKEN_LINK_5XX", url, extra={"status_code": status_code})
    return None


def _is_trailing_slash_only(url: str, final_url: str) -> bool:
    """Return True if the only difference between *url* and *final_url* is a trailing slash."""
    return url.rstrip("/") == final_url.rstrip("/")


def _is_case_normalise_only(url: str, final_url: str) -> bool:
    """Return True if the only difference is URL path casing (server auto-lowercase)."""
    from urllib.parse import urlparse as _urlparse
    u, f = _urlparse(url), _urlparse(final_url)
    return (
        u.scheme == f.scheme
        and u.netloc.lower() == f.netloc.lower()
        and u.path.lower() == f.path.lower()
        and u.query == f.query
        and u.path != f.path          # path IS different (otherwise no redirect)
    )


_PDF_SIZE_LIMIT   = 10 * 1024 * 1024  # 10 MB
_IMAGE_SIZE_LIMIT_KB = 200  # default, overridable per job


def check_asset(result: FetchResult, *, img_size_limit_kb: int = _IMAGE_SIZE_LIMIT_KB) -> list[Issue]:
    """Run checks appropriate for a non-HTML asset (PDF, image, etc.).

    HTML-specific checks (title, meta, headings) are intentionally skipped.
    Only checks the file size using the Content-Length response header.

    Args:
        result: The fetch result for the asset.
        img_size_limit_kb: Flag images larger than this many KB as IMG_OVERSIZED.
    """
    issues: list[Issue] = []
    ct = result.content_type
    try:
        size = int(result.headers.get("content-length", 0) or 0)
    except (ValueError, TypeError):
        size = 0

    img_limit_bytes = img_size_limit_kb * 1024

    if "pdf" in ct and size > 0 and size > _PDF_SIZE_LIMIT:
        size_kb = round(size / 1024, 1)
        issue = make_issue("PDF_TOO_LARGE", result.url)
        issue.description = f"PDF file is {size_kb} KB (exceeds 10 MB limit)"
        issue.extra = {"size_kb": size_kb, "limit_kb": _PDF_SIZE_LIMIT // 1024}
        issues.append(issue)
    elif ct.startswith("image/") and size > 0 and size > img_limit_bytes:
        issue = make_issue("IMG_OVERSIZED", result.url)
        # Override description to show the actual threshold used
        size_kb = round(size / 1024, 1)
        issue.description = f"Image file is {size_kb} KB (exceeds {img_size_limit_kb} KB limit)"
        issue.extra = {"size_kb": size_kb, "limit_kb": img_size_limit_kb}
        issues.append(issue)

    return issues


def check_url_structure(url: str) -> list[Issue]:
    """Return URL structure issues for *url* (spec §E2).

    These checks are pure string operations — no fetching required.
    Called by the engine before fetching each URL.
    """
    issues: list[Issue] = []
    path = urlparse(url).path

    if len(url) > 200:
        issues.append(make_issue("URL_TOO_LONG", url,
                                 extra={"length": len(url), "limit": 200}))
    if any(c.isupper() for c in path):
        issues.append(make_issue("URL_UPPERCASE", url,
                                 extra={"path": path}))
    if "%20" in urlparse(url).path:
        issues.append(make_issue("URL_HAS_SPACES", url,
                                 extra={"path": path}))
    if "_" in path:
        issues.append(make_issue("URL_HAS_UNDERSCORES", url,
                                 extra={"path": path}))

    return issues


def check_amphtml_links(
    pages: list[ParsedPage],
    amp_statuses: dict[str, int],
) -> list[Issue]:
    """Emit AMPHTML_BROKEN for pages whose AMP URL returned a non-200 status.

    Args:
        pages: All crawled pages (only those with amphtml_url are checked).
        amp_statuses: Mapping of {amphtml_url: status_code} from the engine's
            post-crawl AMP HEAD requests.
    """
    issues: list[Issue] = []
    for page in pages:
        if not page.amphtml_url:
            continue
        status = amp_statuses.get(page.amphtml_url)
        if status is not None and status != 200:
            issues.append(make_issue(
                "AMPHTML_BROKEN", page.url,
                extra={"amphtml_url": page.amphtml_url, "amp_status": status},
            ))
    return issues


def issues_for_redirect(
    url: str,
    first_status: int,
    redirect_chain: list[str],
    final_url: str | None = None,
    base_url: str | None = None,
) -> list[Issue]:
    """Return redirect issues for a URL that redirected.

    Args:
        url: The original URL that was fetched.
        first_status: HTTP status code of the first response in the chain.
        redirect_chain: Intermediate URLs (not including the final destination).
        final_url: The URL after all redirects have been followed (used to detect
            auto-corrected redirects like trailing-slash and case normalisation).
        base_url: The crawl start URL — used to distinguish internal from external
            301 redirects. If provided and the URL is internal, INTERNAL_REDIRECT_301
            is emitted instead of the generic REDIRECT_301.
    """
    result: list[Issue] = []

    # Detect whether the redirect is one that CMSes and servers handle automatically,
    # so we can flag it as informational rather than actionable.
    if final_url and first_status == 301 and len(redirect_chain) <= 1:
        if _is_trailing_slash_only(url, final_url):
            result.append(make_issue("REDIRECT_TRAILING_SLASH", url,
                                     extra={"from": url, "to": final_url}))
            return result
        if _is_case_normalise_only(url, final_url):
            result.append(make_issue("REDIRECT_CASE_NORMALISE", url,
                                     extra={"from": url, "to": final_url}))
            return result

    if first_status == 301:
        if base_url and is_same_domain(url, base_url):
            issue = make_issue("INTERNAL_REDIRECT_301", url)
        else:
            issue = make_issue("REDIRECT_301", url)
        issue.extra = {"redirect_to": final_url or (redirect_chain[0] if redirect_chain else None)}
        result.append(issue)
    elif first_status == 302:
        issue = make_issue("REDIRECT_302", url)
        issue.extra = {"redirect_to": final_url or (redirect_chain[0] if redirect_chain else None)}
        result.append(issue)

    if len(redirect_chain) > 1:
        issue = make_issue("REDIRECT_CHAIN", url)
        # Build full chain: original → intermediates → final
        full_chain = [url] + redirect_chain + ([final_url] if final_url else [])
        issue.extra = {"chain": full_chain, "hops": len(redirect_chain)}
        result.append(issue)

    return result
