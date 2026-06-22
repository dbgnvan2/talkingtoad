# Agent Friendly Web Checks Spec v1

**Version:** 1.0  
**Date:** June 2026  
**Author:** Dave / Living Systems Counselling Society  
**Initial Test Site:** livingsystems.ca  

---

## 1. Purpose

This specification defines the checks required to evaluate how accessible a website is to AI agents and crawlers. It covers two distinct use cases:

- **Citation agents** — AI systems (ChatGPT, Perplexity, Claude, Google AI Overviews) that crawl and cite website content when answering user questions
- **Task-executing agents** — AI that browses and acts on a website on a user's behalf (filling forms, navigating, booking)

Most current practical value comes from optimizing for citation agents. Task-executing agent standards (MCP, NLWeb, WebMCP) are emerging and should be monitored but not yet built around for most small nonprofit sites.

---

## 2. Background and Context

AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended) now account for a significant and growing share of web crawl traffic. Unlike traditional search engine crawlers, their purpose is to train and fuel language models that answer questions directly — not to build blue-link search indexes.

AI agents read websites via three channels, in order of importance:

1. **The accessibility tree** — a browser-native API that distills the DOM into roles, names, and states of interactive elements. This is the primary channel AI agents use.
2. **Raw HTML** — the DOM structure, element nesting, attributes, and content.
3. **Screenshots** — a visual snapshot processed by a vision model. Slow and token-expensive; used as a fallback when structure is ambiguous.

The practical implication: **WCAG accessibility compliance and AI agent optimization are largely the same work.** Semantic HTML, heading hierarchy, alt text, and form labels serve screen readers, search engines, and AI agents through the same mechanism.

---

## 3. Check Categories

Checks are organized into three tiers by priority and impact.

---

### Tier 1 — Foundational (Highest Priority)

These are prerequisites. A site that fails Tier 1 checks is effectively invisible to AI systems regardless of content quality.

#### 3.1 Crawler Access — robots.txt

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| AI crawlers not blocked | robots.txt allows GPTBot, ClaudeBot, PerplexityBot, Google-Extended | Any of the above blocked by Disallow directive | Critical |
| robots.txt exists and is reachable | Returns HTTP 200 with text/plain | Returns 5xx (crawlers treat as "crawl nothing") | Critical |
| No blanket Disallow | `Disallow: /` not present for AI user-agents | Entire site blocked | Critical |
| Sitemap declared | `Sitemap:` directive present in robots.txt | Absent | Warning |

**How to check:** Fetch `yoursite.com/robots.txt` and inspect user-agent directives for each of the four AI crawlers listed above.

---

#### 3.2 Indexability — Meta Robots Tag

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| Page not set to noindex | No `<meta name="robots" content="noindex">` | noindex present | Critical |
| Page not set to nofollow | No `<meta name="robots" content="nofollow">` | nofollow present on pages with navigation | Warning |
| X-Robots-Tag HTTP header | No noindex directive in header | noindex present in header | Critical |

**Note:** A staging environment will typically have noindex set intentionally and correctly. Verify that the production deployment removes this tag.

---

#### 3.3 JavaScript Rendering

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| Core content in server-rendered HTML | Main text content present in raw HTML fetch | Content only appears after JS execution | Critical |
| Navigation links in raw HTML | Nav links present without JS | Nav loaded dynamically | Warning |
| Images not entirely JS-dependent | At least some images present in raw HTML | All images loaded via JS/lazy-load placeholders only | Warning |

**How to check:** Fetch the page with a plain HTTP client (curl, or this crawler tool) and compare content to what a browser renders. A gap indicates JS dependency.

---

#### 3.4 Heading Structure

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| Single H1 present | Exactly one H1 per page | H1 missing | Critical |
| No multiple H1s | One H1 | More than one H1 on same page | Warning |
| No skipped heading levels | H1 → H2 → H3 in sequence | H1 → H3 with no H2, etc. | Warning |
| Headings reflect content | H1 matches page topic | Heading used for visual styling only | Info |

---

#### 3.5 Semantic HTML

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| Buttons use `<button>` | Interactive buttons use semantic button element | `<div>` or `<span>` used as clickable button | Warning |
| Links use `<a>` | All links use anchor elements | Non-semantic elements used for navigation | Warning |
| Navigation uses `<nav>` | Navigation wrapped in nav element | Navigation in div without role | Info |
| Main content uses `<main>` | Primary content in main element | Absent | Info |
| No ghost elements | No invisible/transparent overlays in DOM that are not interactable | Off-screen or transparent elements present in accessibility tree | Warning |

---

#### 3.6 Broken Links

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| No placeholder links | No `href="#"` on navigational CTAs | `#` used as href on buttons/links intended to navigate | Critical |
| No incorrect placeholder targets | All links resolve to intended destination | Links pointing to wrong domain (e.g., google.com as placeholder) | Critical |
| No 404s | All internal links return 200 | Any internal link returns 404 | Critical |
| No broken external links | External links return 200 or 301 | External links return 404, 410, 5xx | Warning |

---

### Tier 2 — Content Structure for Citability

A site that passes Tier 1 is visible to AI crawlers. Tier 2 determines whether AI systems choose to cite it.

#### 3.7 Structured Data (JSON-LD Schema)

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| Organization schema present | `<script type="application/ld+json">` with Organization type on homepage | Absent | Warning |
| LocalBusiness or relevant type | Schema type matches site purpose | Generic or absent | Warning |
| FAQPage schema on FAQ content | FAQ content marked up with FAQPage schema | FAQ content present but not marked up | Warning |
| No schema validation errors | Schema parses without errors | Malformed JSON-LD | Warning |

**Note:** FAQPage schema has been documented to produce meaningfully higher citation rates in AI-generated answers. It is high priority for any site with FAQ or Q&A content.

**Recommended schema types for nonprofit counselling/training sites:**
- `Organization`
- `LocalBusiness` or `MedicalOrganization` (for counselling)
- `FAQPage`
- `Event` (for training sessions)
- `Course` (for training programs)

---

#### 3.8 Image Alt Text

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| All informational images have alt text | `alt` attribute present and descriptive | `alt` missing entirely | Warning |
| Decorative images have empty alt | Decorative images have `alt=""` | Decorative images have keyword-stuffed alt or no alt | Info |
| Alt text is descriptive | Alt describes what the image shows | Alt is generic ("image", "photo") or keyword-stuffed | Info |

---

#### 3.9 Content Structure

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| Answer-first writing | Key information in first paragraph | Information buried after preamble | Info |
| Plain text contact info | Address, phone, email in raw HTML | Contact info only in images or JS-rendered elements | Warning |
| Consistent factual claims | Dates, years, facts consistent across the page | Contradictory claims (e.g., "since 1971" vs. "registered 1974") | Info |

---

#### 3.10 Meta Description

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| Meta description present | `<meta name="description">` present and non-empty | Missing or empty | Warning |
| Appropriate length | 70–160 characters | Under 70 or over 160 characters | Info |
| Unique per page | Each page has a distinct description | Same description on multiple pages | Warning |

---

#### 3.11 Open Graph Tags

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| og:title present | `<meta property="og:title">` present | Missing | Info |
| og:description present | `<meta property="og:description">` present | Missing | Info |

These control how content appears when cited or shared. Less critical for pure AI citation but relevant for social-sharing agents.

---

#### 3.12 Content Freshness

| Check | Pass Condition | Fail Condition | Severity |
|---|---|---|---|
| Dates visible on content | Publication or update date present on articles/posts | No date visible | Info |
| Content updated within 2 years | Key pages updated recently | Core pages have no updates in 2+ years | Info |

**Note:** Freshness matters more in rapidly changing domains. For Bowen Theory / counselling content, evergreen content remains citable for years. Prioritize freshness for news and blog posts.

---

### Tier 3 — Emerging Standards (Monitor, Don't Build Around Yet)

These standards are in active development. Implementation is premature for most small nonprofit sites as of mid-2026, but awareness is warranted.

#### 3.13 llms.txt

A proposed (not yet standardized) plain-text file at `/llms.txt` providing AI systems with a structured summary of the site's content and purpose. Low cost to implement; unclear adoption by major LLMs. Worth adding when drafting is straightforward.

#### 3.14 WebMCP

A proposed web standard from Google allowing websites to expose structured tools to browser-based AI agents. Entered Chrome origin trial May 2026. Relevant for sites with transactional features (booking, forms, e-commerce). Not yet appropriate for production implementation on a counselling/training site.

#### 3.15 NLWeb / Model Context Protocol (MCP) Endpoints

Protocol-level integrations that allow AI agents to query and interact with a site's data and functions in a structured way. Requires backend API development. Out of scope for WordPress/Elementor sites in the near term.

---

## 4. Issue Code Reference

| Code | Category | Tier | Severity | Description | Recommendation |
|---|---|---|---|---|---|
| `AI_CRAWLER_BLOCKED` | crawler_access | 1 | Critical | Named AI crawler blocked in robots.txt | Add explicit Allow rule for GPTBot, ClaudeBot, PerplexityBot, Google-Extended |
| `ROBOTS_UNREACHABLE` | crawler_access | 1 | Critical | robots.txt returns 5xx | Fix server error; 5xx causes crawlers to treat the entire site as blocked |
| `NOINDEX_META` | indexability | 1 | Critical | Page has noindex meta tag | Remove noindex tag on production. Confirm this is intentional on staging. |
| `NOINDEX_HEADER` | indexability | 1 | Critical | Page has noindex X-Robots-Tag header | Review server configuration; page is hidden from all crawlers |
| `NOFOLLOW_META` | indexability | 1 | Warning | Page has nofollow meta tag | Confirm intentional; prevents crawlers following links from this page |
| `JS_DEPENDENT_CONTENT` | rendering | 1 | Critical | Core content not in server-rendered HTML | Enable server-side rendering for main content |
| `JS_DEPENDENT_NAVIGATION` | rendering | 1 | Warning | Navigation links only present after JS execution | Ensure nav is in server-rendered HTML |
| `H1_MISSING` | heading | 1 | Critical | No H1 tag on page | Add a single H1 describing the main topic of the page |
| `H1_MULTIPLE` | heading | 1 | Warning | More than one H1 on page | Remove extra H1 tags; each page should have exactly one |
| `HEADING_SKIP` | heading | 1 | Warning | Heading levels skipped (e.g. H1 → H3) | Fix heading order so levels are not skipped |
| `NON_SEMANTIC_BUTTON` | semantic_html | 1 | Warning | Interactive button uses div or span | Replace with `<button>` element |
| `PLACEHOLDER_LINK` | broken_link | 1 | Critical | Link href is `#` on a navigational CTA | Replace with correct destination URL |
| `WRONG_PLACEHOLDER_LINK` | broken_link | 1 | Critical | Link points to incorrect/placeholder domain | Replace with correct destination URL |
| `BROKEN_LINK_404` | broken_link | 1 | Critical | Link destination returns 404 | Remove or update link |
| `BROKEN_LINK_5XX` | broken_link | 1 | Warning | Link destination returns server error | Investigate; remove or replace if persistent |
| `SCHEMA_MISSING` | structured_data | 2 | Warning | No JSON-LD schema found | Add Organization schema at minimum; add FAQPage where applicable |
| `SCHEMA_FAQ_MISSING` | structured_data | 2 | Warning | FAQ content present but no FAQPage schema | Add FAQPage JSON-LD to FAQ content |
| `IMG_ALT_MISSING` | image | 2 | Warning | Image missing alt attribute | Add descriptive alt text |
| `IMG_ALT_EMPTY_INFORMATIONAL` | image | 2 | Info | Non-decorative image has empty alt | Add descriptive alt text if image conveys meaning |
| `META_DESC_MISSING` | metadata | 2 | Warning | No meta description | Add a 70–160 character description |
| `META_DESC_TOO_LONG` | metadata | 2 | Info | Meta description over 160 characters | Shorten to under 160 characters |
| `META_DESC_DUPLICATE` | metadata | 2 | Warning | Same meta description on multiple pages | Write unique descriptions per page |
| `OG_TITLE_MISSING` | metadata | 2 | Info | og:title missing | Add og:title meta tag |
| `OG_DESC_MISSING` | metadata | 2 | Info | og:description missing | Add og:description meta tag |
| `CONTACT_INFO_NOT_IN_HTML` | content | 2 | Warning | Address/phone/email not in raw HTML | Ensure contact details are in server-rendered text, not images or JS |
| `FACTUAL_INCONSISTENCY` | content | 2 | Info | Contradictory facts on same page or site | Reconcile conflicting dates, years, or claims |
| `NO_DATE_ON_CONTENT` | content | 2 | Info | Article or post has no visible date | Add publication or last-updated date |

---

## 5. Severity Definitions

| Severity | Meaning |
|---|---|
| **Critical** | Blocks AI crawler access entirely, or prevents content from being indexed or cited. Fix before any other work. |
| **Warning** | Reduces AI citability or agent task success. Fix as part of normal site maintenance. |
| **Info** | Best practice; improves citability and agent experience but not blocking. Address when practical. |

---

## 6. Evaluation Approach

### 6.1 What to Fetch

For each page under evaluation:

1. Fetch raw HTML via HTTP (no JS execution) — simulates how most AI crawlers see the page
2. Fetch `robots.txt` from the site root
3. Optionally fetch a rendered version via headless browser for comparison

### 6.2 Scope

- **Homepage:** All Tier 1 and Tier 2 checks apply
- **Interior pages:** All checks except those scoped to homepage only (favicon, Organization schema)
- **robots.txt / sitemap:** Checked once per crawl job, not per page

### 6.3 Relationship to the Nonprofit Crawler Spec

This specification extends the Nonprofit Website Crawler Tool (v1.4). The checks defined here map to the existing issue code architecture in that spec. Tier 1 checks fall within Phase 1 scope. Tier 2 checks on structured data and image alt text fall within Phase 2 scope.

Additions required to the Nonprofit Crawler Spec to implement this spec fully:

- Explicit named AI crawler checks in the robots.txt parser (GPTBot, ClaudeBot, PerplexityBot, Google-Extended)
- JS-dependency detection (compare raw HTML fetch to expected content)
- JSON-LD schema detection and type identification (already planned in Phase 2)
- Placeholder link detection (`href="#"` on CTA elements)
- Factual consistency check (out of scope for automated tooling — flag for manual review)

---

## 7. Living Systems Site Evaluation (June 2026)

Evaluation of `daveg24.sg-host.com` (staging environment).

| Check | Status | Notes |
|---|---|---|
| AI crawler access | 🔴 Blocked | `noindex, nofollow` in meta robots — expected on staging, must be removed on production |
| robots.txt | ⚠️ Unknown | Not verified; SiteGround staging typically blocks by default |
| H1 present | 🔴 Fail | Page opens with H2; no H1 found |
| Core content in server-rendered HTML | 🟡 Partial | Text content present; all images are 1×1 SVG placeholders |
| Image alt text | 🔴 Fail | All images are placeholders; no alt text on any image |
| JSON-LD schema | 🔴 Absent | No structured data of any kind found |
| Placeholder links | 🔴 Fail | Multiple CTAs link to `#`; one link points to google.com |
| Semantic HTML | 🟢 Adequate | Nav, headings, links appear structurally correct |
| Meta description | 🟡 Present | May be over 160 characters; verify length |
| Contact info in HTML | 🟢 Pass | Address, phone, email in plain text in footer |
| og:title / og:description | 🔴 Missing | Neither present |
| Factual consistency | 🟡 Minor | "Since 1971" vs "registered society since 1974" — reconcile |

**Priority fixes for production launch (in order):**

1. Remove `noindex, nofollow` from production meta robots
2. Verify and configure robots.txt to allow AI crawlers
3. Add H1 to homepage
4. Add JSON-LD Organization schema to homepage
5. Replace all `href="#"` placeholder CTAs with correct destinations
6. Fix the google.com placeholder link
7. Fix image loading and add alt text to all informational images
8. Add FAQPage schema where FAQ content exists
9. Add og:title and og:description

---

## 8. Open Questions

1. **robots.txt on production (livingsystems.ca):** Confirm current state — does it explicitly allow or block AI crawlers? Default WordPress installs typically allow all crawlers, but this should be verified rather than assumed.

2. **Image loading on staging:** Are the 1×1 SVG placeholders a staging artifact (images not yet uploaded), a lazy-load issue, or an Elementor configuration problem? This affects how urgent the alt text fixes are.

3. **Elementor and server-side rendering:** Elementor Pro generates server-rendered HTML for most content types, but some dynamic widgets (posts loops, forms) may be JS-dependent. A render comparison should be done before launch.

4. **llms.txt:** Low effort to draft once the production content is finalized. Recommend adding after core Tier 1 issues are resolved.

---

*Spec v1.0 — based on evaluation of livingsystems.ca staging site and current AI crawler optimization research as of June 2026.*
