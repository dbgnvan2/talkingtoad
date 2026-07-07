---
status: current
last_reviewed: 2026-05-27
---

# User Guide — TalkingToad SEO Crawler

## What is TalkingToad?

TalkingToad checks your nonprofit website for common SEO problems — things that make it harder for people to find you in Google and other search engines. It's free, runs in your browser, and gives you plain-English explanations of what to fix, including the ability to apply fixes directly to WordPress without touching any code.

---

## How to Run a Check

1. **Enter your website URL** — e.g., `https://livingsystems.ca`
2. **Choose what to check** — tick the analysis areas you want (all are on by default)
3. Click **Start Crawl**
4. Wait for the crawl to finish (progress is shown on screen)
5. Review the results on the **Results Dashboard**

### Scanning a Single Page

To check one specific page without crawling the whole site, paste its full URL into the **"or scan a single page"** box below the main form and click **Scan Page**. Results appear instantly on the Results page.

This is useful for verifying that a fix worked without running a full re-crawl.

---

## Choosing What to Check

Use the four checkboxes on the start screen to focus the crawl:

| Toggle | What it checks |
|---|---|
| **Link Integrity** | Broken links, missing images, redirect chains |
| **SEO Essentials** | Page titles, meta descriptions, language, canonical tags, duplicate content |
| **Site Structure** | Heading hierarchy (H1–H6 order) |
| **Indexability** | robots.txt, XML sitemaps, noindex tags, orphan pages, thin content |

Security checks (HTTPS, mixed content, unsafe links) always run regardless of your selection.

If you only want a quick metadata review, untick everything except **SEO Essentials** — the crawl will be faster and the results list shorter.

---

## Understanding the Results

### Health Score

The **Health Score** at the top of the Results page gives your site a number from 0 to 100:
- **80–100** — Good shape. Minor issues only.
- **50–79** — Some work needed. Focus on Critical items first.
- **0–49** — Significant problems. Start with the red items.

The score is reduced by issue impacts — critical issues reduce it the most.

### Agent Health Score

Next to the Health Score you'll see a separate **Agent Health** score (0–100). It answers a
different question: *how ready is your site for AI assistants?* Search is shifting from people
clicking links to AI tools (ChatGPT, Google's AI answers, Perplexity, Claude) reading your site
and answering on your behalf — and, increasingly, agents that *act* on your site.

Agent Health uses the same 0–100 scale but only counts the checks that matter to those AI
visitors: whether AI crawlers are allowed in, whether your content and navigation are readable
without running JavaScript, whether buttons and links are real and labelled, and whether your
homepage states who you are (Organization schema) and how to contact you in plain text. A high
Health Score with a low Agent Health Score means your site is solid for traditional SEO but
harder for AI tools to use — worth fixing as AI search grows.

### Issue Categories

Results are grouped by type:

| Category | What it covers |
|---|---|
| **Broken Links** | Dead links (404, 410), broken images, timed-out links |
| **Metadata** | Page titles, descriptions, language tag, canonical tags, OG social tags |
| **Headings** | H1 missing, multiple H1s, skipped heading levels |
| **Redirects** | Redirect loops, chains, temporary redirects, meta refresh |
| **Crawlability** | robots.txt blocks, noindex, orphan pages, thin content, viewport tag, schema markup |
| **Duplicates** | Duplicate titles, descriptions, or both together |
| **Sitemap** | Missing sitemap, pages not listed in sitemap |
| **Security** | HTTP pages, HTTPS redirect missing, mixed content, HSTS |
| **URL Structure** | Uppercase URLs, spaces, underscores, overly long URLs |
| **AI Readiness** | AI-crawler access, structured data, content extractability, homepage Organization schema & contact info |
| **Rendering** | Navigation/content that only appears after JavaScript runs (invisible to AI crawlers) |
| **Semantic HTML** | Fake buttons (div/span), unlabelled controls, missing `<main>`/`<nav>` landmarks |

#### Noindex pages

Pages marked **noindex** are deliberately hidden from search engines, so TalkingToad does not penalise them for content or SEO issues — the only finding reported for such a page is the noindex tag itself. This keeps intentionally-hidden pages (thank-you pages, staging drafts) from cluttering your results with fixes you don't need.

#### Site-wide issues counted once

Some problems affect your whole site rather than a single page — serving pages over **HTTP instead of HTTPS**, missing **www canonicalization**, a missing **HSTS** header, or **mixed content**. These site-scoped issues are counted **once per site**, not once per page, so a single misconfiguration doesn't inflate your issue total across hundreds of pages.

### Top 5 Priority Fixes

The summary tab shows your five highest-priority issues to fix first. Each issue has an **Impact** score (how badly it hurts SEO) and an **Effort** score (how hard it is to fix). The priority ranking combines both.

### Quick Wins

Alongside the priority list you'll see a separate **Quick Wins** list. These are issues that are both **high impact** and **low effort** — the easy, high-value fixes that give you the most improvement for the least work. Quick Wins are picked independently of the priority ranking, so it's worth scanning this list even after you've worked through your Top Priority Fixes.

### Severity Colours

After the 2026-07 severity recalibration, most issues now surface as **Info** — only page-fatal problems (such as `noindex` on a page you want indexed, or redirect loops) remain **Critical**. **Broken links** are now scored as **minor** (low impact) rather than critical: they're worth fixing, but they rarely sink your search visibility on their own.

- 🔴 **Critical** — Fix these first; they directly harm your search visibility (reserved for page-fatal problems)
- 🟡 **Warning** — Should be fixed; will improve your results
- 🔵 **Info** — Worth knowing; low urgency

### Page Priority queue

The **Page Priority** panel ranks the crawled pages so you know which ones to work on first. When you're done reviewing the ranked list, click **Hide** to collapse it and clear the table; re-opening the panel re-ranks the pages honestly from the current crawl. (The button used to read "Refresh" but only re-displayed the same crawl's numbers without re-scanning — "Hide" makes what it does clear.)

### llms.txt validation

If your site publishes an `/llms.txt` file, TalkingToad now validates it against the **llmstxt.org specification** rather than stricter invented rules. Only a top-level `# Title` heading is required for the file to be considered valid — a summary, section links, and the number of links are all **optional**, and there is no cap on how many links you may list. A standard plugin-generated file (for example one produced by Yoast) will validate cleanly. A soft-404 or non-Markdown body is still flagged.

---

## Connecting external services

The **Connections** panel (opened from the Results header) lets you check that TalkingToad can reach the two external services it uses, without leaving the results view.

- **Test LLM connection** — runs a real round-trip against your configured AI provider (Gemini/OpenAI) and reports success or the exact error. Use this if AI-powered suggestions aren't appearing.
- **Test GSC connection** — checks whether Google Search Console is connected and lists the properties TalkingToad can see.

### Connecting Google Search Console

Linking Google Search Console lets TalkingToad blend real search-performance data (clicks, impressions) into its authority analysis. The link is **app-wide and one-time** — once connected, every crawl can use it.

1. Run a crawl and open the **Results** page.
2. Open the **GSC** panel (or the Connections panel).
3. Click **Connect**. Google always shows the account picker, so you choose exactly which Google account TalkingToad connects as.

TalkingToad connects as **one** Google account — the panel shows **"Connected as {your email}"** so you always know which account is in use. (Accounts linked before this feature show "account not identified" until you reconnect once.)

Each property in the dropdown is labelled with your access level — **Owner**, **Full**, **Restricted**, or **Unverified**. TalkingToad auto-selects the property you have the strongest access to. **The account you connect as must be an Owner or Full user of the property you pick** — if you select a Restricted or Unverified property, ingest may be denied and the panel warns you. Either pick an Owner/Full property or grant this account access in Search Console.

If TalkingToad is configured for GSC but not yet linked, the panel shows a **Connect** button with step-by-step guidance. If GSC hasn't been configured on this install at all, the panel stays quietly empty (there is nothing to connect to yet).

---

## Fix Manager (WordPress Sites)

The **Fix Manager** tab lets you connect TalkingToad to your WordPress site and apply fixes directly — no coding required.

### Setup

You will need a credentials file (`wp-credentials.json`) with your WordPress login details. Ask your developer to help you create this the first time.

### How it works

1. Click **Scan for Fixes** — TalkingToad connects to your WordPress site and generates a list of issues that can be fixed automatically (missing titles, meta descriptions, noindex pages, etc.)
2. **Review each fix** — TalkingToad shows the current value and a suggested replacement. You can edit the suggestion before approving.
3. Click **Approve** on each fix you are happy with (or **Skip** to leave it unchanged)
4. Click **Apply Approved Fixes** — TalkingToad writes the changes to WordPress

Fixes are applied one at a time. If something goes wrong, the process stops so you can review the error before continuing.

### What can be fixed automatically

- Missing or poor page titles (SEO title)
- Missing or poor meta descriptions
- Missing OG (social share) titles and descriptions
- Pages incorrectly set to noindex (hidden from search)
- Heading level changes (H1 to H2, H3 to H4, etc.)
- Convert headings to bold text (remove heading status)

### Editing Headings

When viewing a page's details, you can edit headings directly:

1. **Open the page panel** — Click on any page in the results
2. **Find the heading editor** — Below the page details, you'll see the heading outline
3. **Use the dropdown** on each heading to change its level (H1-H6) or convert to bold

**Analyze Sources** — Click this button to see where each heading is stored:
- **Post** (green) — In the main page content, editable via API
- **Block** (blue) — In a reusable block, editable via API
- **Widget** (amber) — In a WordPress widget, edit in WP Admin
- **ACF** (purple) — In a custom field, edit in WP Admin
- **Theme/Plugin** (grey) — Generated by theme or plugin, edit source code or WP Admin

Headings marked as Theme/Plugin cannot be changed via the API — they're generated dynamically by your WordPress theme or a plugin (like custom heading blocks, shortcodes, or page builders).

### Supported SEO plugins

TalkingToad auto-detects whether you are using **Yoast SEO** or **Rank Math** and uses the correct fields for each.

---

## FAQ Schema Generator

If a page has a list of frequently-asked questions and answers, TalkingToad can generate **Schema.org FAQPage** structured data (JSON-LD) for it. Open the page's details and click the **Generate FAQ Schema** option — a modal shows ready-to-paste JSON-LD you can add to the page. Adding this markup helps AI assistants and search engines understand your Q&A content, improving your AI/GEO visibility.

The schema is built only from answers that already appear in the page's HTML; TalkingToad never invents answers, and it does not write anything back to your site — the output is copy/paste only.

---

## Exporting Results

Click **Export CSV** on any results tab to download the data as a spreadsheet. You can share this with your web developer or use it to track progress over time.

### Scoring model version

Each audit is stamped with a **scoring-model version** (currently `2026-07-06-r5`). Because scoring rules evolve, this stamp lets you tell whether two audits used the same rules — results are directly comparable only when their scoring-model versions match.

---

## Usage Notice

This tool is intended for use on websites you own or have permission to audit. Please do not use it to crawl websites without authorisation.

---

## Frequently Asked Questions

**How many pages will it check?**
Up to 500 pages per crawl. Most nonprofit sites are well under this limit.

**How long does a crawl take?**
About 4–8 minutes for a 100-page site. The crawler waits 0.5 seconds between requests to avoid overloading your server.

**Will it slow down my website?**
No — TalkingToad is designed to be gentle. It sends one request at a time with a built-in delay.

**What if my site requires a login?**
TalkingToad checks publicly accessible pages only. Password-protected areas are automatically skipped and noted in the results.

**Why does it skip author pages, category pages, and tag pages?**
WordPress automatically generates these archive pages for every author, category, and tag on your blog. They produce large volumes of repetitive, auto-generated content that creates noise in SEO audit results. TalkingToad skips them by default so you see issues with your real content pages. This behaviour can be disabled in the crawl settings.

**I keep seeing "Title/H1 mismatch" on pages where the title is correct — what's wrong?**
Some WordPress themes (Salient, Avada, Divi, and others) inject the parent-page title as a large H1 banner on every sub-page. For example, a page titled "Bowen Theory Training" might show an H1 of "Clinical Internship Programs" because that is its parent page. TalkingToad tries to detect this automatically, but for persistent false positives you have two options in **Advanced Settings**:
- **Ignore banner H1s automatically** — tick this box and TalkingToad will skip any H1 that shares no words with the page title across the whole site.
- **Suppress H1 text** — type the exact banner text (one per line) to ignore it on every page it appears.

**The crawl found a broken link but it works in my browser — why?**
Some websites and social platforms (LinkedIn, Facebook, Instagram) block automated requests but work fine for real visitors. These are listed as 'Unverified' rather than broken. Click the link yourself to confirm it works.

**What is a canonical tag?**
A canonical tag tells search engines which URL is the preferred version of a page. It prevents duplicate content penalties when the same page is accessible via multiple URLs (e.g., with and without `www`, with tracking parameters, etc.).

**What is an orphan page?**
An orphan page is a page that no other page on your site links to. Search engines may not discover it reliably, and it receives no internal link value from the rest of your site.
