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

### Re-running a scan (Rescan)

Under **Recent crawls** on the home page, each finished scan has a **Rescan**
button next to *View Results*. One click re-runs that scan **with the same
settings it was run with the first time** — the same page limit, crawl delay,
analysis tick-boxes, ignored headings, content-type selection, and GSC priority
file if you attached one. You don't need to re-enter anything.

This is the normal way to check whether your fixes worked. Because the re-run
uses the original settings, its score is directly comparable to the previous
one — a scan re-run with different settings can show a score change that is
really just a change in what was measured.

The new scan is saved as a **new** entry; your previous scan is kept, which is
what the before-and-after comparison uses. A scan that is still running shows
*View Progress* instead — there is nothing to re-run until it finishes. A
single-page scan re-runs as a single page.

### Re-checking all pages in place

On the Results page, **Re-check all pages** re-fetches every page of *this* scan and updates
its findings and score without starting a new scan or discovering new pages. Use it after a
batch of fixes when you want the current report refreshed. Use **Rescan** on the home page
instead when you want a fresh, comparable scan (new pages included).

### Attaching a GSC priority file (optional)

If you use the companion **GSC reporting app**, it produces a `priority_pages.json` listing your
highest-traffic pages with their Search Console numbers. On the scan-start screen you can attach
that file (the **"GSC priority file"** box). When you do, TalkingToad:

- **scans your most important pages first** (rather than crawling in whatever order it discovers
  links), and
- **ranks the results using your Search Console data** (clicks, impressions, position, inquiries),
  so the Page Priority queue reflects what actually earns traffic.

It's entirely optional — leave it empty and the scan runs exactly as before. The file is read in
your browser and sent with the scan; TalkingToad never reaches into your computer's files. If you
attach the wrong site's file, the scan tells you and ignores it.

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

### Choosing how much "Info" you see (Info detail)

Most findings are **Info** notices — 123 of the 170 checks — and they are not all worth the
same. Each Info notice has a tier: **Key** (the nine highest-value ones, such as images with no
alt text), **Notable** (most of the useful ones, such as a missing meta description), and
**Low** (small polish items, such as a slightly short title).

Under **Advanced settings** on the start screen, **Info detail** lets a scan choose which tiers
are part of the audit:

| Level | What the scan shows and counts |
|---|---|
| **All info** (default) | Every Info notice — exactly what you have always seen |
| **Notable and key only** | Leaves out the Low tier |
| **Key only** | Only the nine Key notices |
| **Hide info** | Critical and Warning findings define the audit |

**This setting changes the Health Score.** A scan at *Notable and key only* counts fewer
notices and scores higher — that is the point, but it also means two scans at different levels
are not comparable, and the results page says so: the level is printed under the score
("scored at Notable and key only · 98 info notices excluded"), the Info card shows the count
that was scored with the excluded count beneath it, and the PDF and Excel exports carry the
same note. **Rescan** re-uses the level, so before-and-after comparisons stay honest.

Nothing is thrown away. Every finding is still recorded; each category tab and the Info view
has a **Show excluded info** button that reveals the left-out notices, dimmed and marked
*not counted in the health score*. Revealing them never changes the score — the score belongs
to the scan, not to the view.

---

## Understanding the Results

### Compared with the previous scan

When an earlier scan of the same site exists, the Summary tab shows the health score and
issue count then and now. If the two scans measured different things — a different *Info
detail* level, or one was a partial scan — the change is struck through with the reason.

### Striking distance

Pages ranking 5–15 in Google with at least 50 monthly impressions are one good rewrite away
from page one. The **Striking distance** section lists them with the search query from your
GSC priority file (when you attached one). **Open page** takes you to the page's audit and
rewriter; **Copy brief** copies a one-sentence instruction you can paste into the rewriter.

### WordPress configuration

**Run WordPress audit** reads your plugins, theme and pending updates through the WordPress
API (read-only; it needs the stored admin credentials). Pending updates and inactive plugins
are worth a look: both are common maintenance gaps.

### Health Score

The **Health Score** at the top of the Results page gives your site a number from 0 to 100:
- **80–100** — Good shape. Minor issues only.
- **50–79** — Some work needed. Focus on Critical items first.
- **0–49** — Significant problems. Start with the red items.

The score is reduced by issue impacts — critical issues reduce it the most.

If the scan was run with an **Info detail** level other than *All info*, the level appears under
the score together with how many Info notices it left out, and the score counts only the tiers
you chose (see *Choosing how much "Info" you see* above).

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

### Fix Focus checklist

Beside the Top 5 Priority Fixes, the **Fix Focus** panel turns your report into a finite, tickable to-do list. It shows the highest-priority fixes split into two lists — **SEO** and **AI/GEO** — grouped by page and capped at the top 10 pages per list (when more qualify, it tells you how many pages and items are hidden). A green **quick win** tag marks the easy, high-value items.

- **Tick items off as you fix them.** Your ticks are **saved with the crawl**, so you can leave and come back without re-running the scan.
- **Verify a page.** After you've fixed something, click **Verify page** on that page. TalkingToad re-scans just that one page: items it confirms are gone turn **verified**, and anything still there is flagged **still present** so a not-quite-fixed item doesn't quietly look done. (A page that's erroring — returning a 4xx/5xx — is not marked verified.)
- **Regenerate** rebuilds the list from your latest scan while keeping the ticks on items that still apply. Use it after you've fixed a batch, or when Verify tells you new issues appeared on a page.

Next to Fix Focus is a **Fix Focus Items Help** panel — a plain-English glossary for the items on your list. Each distinct item is explained **once** (so an item that appears on many pages isn't repeated), listed **A–Z** by the same name shown on the checklist, with what it is and how to fix it. Fix Focus is also available as its own **Fix Focus** tab if you want the full-width view.

### Quick Wins

Alongside the priority list you'll see a separate **Quick Wins** list. These are issues that are both **high impact** and **low effort** — the easy, high-value fixes that give you the most improvement for the least work. Quick Wins are picked independently of the priority ranking, so it's worth scanning this list even after you've worked through your Top Priority Fixes.

### Reading an explanation

Every finding opens into a short explanation written for people who do not do SEO for a
living. It always has the same seven parts, in this order:

1. **Why it matters to a nonprofit** — one sentence, in your terms.
2. **What it is** — what the check looked at and what it found.
3. **Why it matters** — what is at stake and how the mechanism works, jargon defined as it appears.
4. **Good vs bad** — one concrete passing example and one failing one.
5. **How this can mislead** — the honest caveat. It opens with the *evidence tier*
   (shown as a badge beside the title): **Established** means a published source confirms
   the effect; **Measured** means it was observed during the crawl; **Reasonable proxy**
   means industry consensus; **Heuristic** means TalkingToad's own judgement. It then says
   when the check is wrong in each direction and what a plausible-but-wrong result looks
   like. Read this before acting on a finding you find surprising.
6. **How to fix** — the concrete action, naming the WordPress control where that is where
   you will do it.

The PDF report prints the same explanation under each finding, so a printed copy teaches
the same way the screen does. The writing rules are in `docs/explanation-style-guide.md`.

### Severity Colours

After the 2026-07 severity recalibration, most issues now surface as **Info** — only page-fatal problems (such as `noindex` on a page you want indexed, or redirect loops) remain **Critical**. **Broken links** are now scored as **minor** (low impact) rather than critical: they're worth fixing, but they rarely sink your search visibility on their own.

- 🔴 **Critical** — Fix these first; they directly harm your search visibility (reserved for page-fatal problems)
- 🟡 **Warning** — Should be fixed; will improve your results
- 🔵 **Info** — Worth knowing; low urgency. Each Info badge also shows its tier — **Key**, **Notable** or **Low** — so you can tell a "fix this soon" notice from a polish item at a glance.

### Page Priority queue

The **Page Priority** panel ranks the crawled pages so you know which ones to work on first. When you're done reviewing the ranked list, click **Hide** to collapse it and clear the table; re-opening the panel re-ranks the pages honestly from the current crawl. (The button used to read "Refresh" but only re-displayed the same crawl's numbers without re-scanning — "Hide" makes what it does clear.)

### Page Audit — seeing what is wrong, and checking your fix

Click **Inspect →** on any page to open the **Page Audit** panel: every finding for
that one page, with the tools to act on it.

**Which items are the problem.** A finding like *"25 external links open in a new
tab without rel=noopener"* names the page but not the links. Expand **Details** on
any finding and TalkingToad lists the actual offending items — the links by anchor
text and address, the images without alt text, the schema fields that do not match
the page. When it is showing part of a longer list it says so ("Showing 10 of 25")
rather than letting a short list look complete.

For findings where the page itself is the problem — a missing title, no `H1` —
Details says exactly that, so an empty list is never mistaken for "nothing wrong".

**Get full details** re-reads the page as it is right now and shows everything the
check recorded, instead of what was stored during the crawl. Nothing is saved: it
is a look, not a re-scan. Useful when you are part-way through fixing a page and
want to see what is still there.

**Re-check this page** (the ↻ button) re-fetches the page and runs the checks
again, so you can confirm a fix without re-crawling the whole site. It then tells
you what it found:

- **No longer found** — the finding is gone. This is the confirmation you wanted.
- **Still present** — the check ran and the problem is still there.
- **Newly found** — fixing one thing revealed another.
- **Not re-checked** — some checks compare your page against the *rest* of the
  site (duplicate titles, orphan pages, sitemap membership). A single-page
  re-check cannot evaluate those, so it leaves them exactly as they were and
  names them. They are not passes, and they are not failures — they are unread.
  Run a full crawl to have them checked.

If the page cannot be read — a 403 from bot protection, or a 429 because you have
been re-checking quickly — the panel says so and changes nothing. It will never
mark a finding fixed because it failed to look at the page.

> **Tip:** to work through a list of fixes and tick them off as you confirm each
> one, use the **Fix Focus** checklist and its per-page **Verify page** button
> instead. Same underlying check; it keeps the running list for you.

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
