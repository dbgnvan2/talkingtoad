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

### Top 5 Priority Fixes

The summary tab shows your five highest-priority issues to fix first. Each issue has an **Impact** score (how badly it hurts SEO) and an **Effort** score (how hard it is to fix). The priority ranking combines both.

### Severity Colours

- 🔴 **Critical** — Fix these first; they directly harm your search visibility
- 🟡 **Warning** — Should be fixed; will improve your results
- 🔵 **Info** — Worth knowing; low urgency

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

### Supported SEO plugins

TalkingToad auto-detects whether you are using **Yoast SEO** or **Rank Math** and uses the correct fields for each.

---

## Exporting Results

Click **Export CSV** on any results tab to download the data as a spreadsheet. You can share this with your web developer or use it to track progress over time.

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

**The crawl found a broken link but it works in my browser — why?**
Some websites and social platforms (LinkedIn, Facebook, Instagram) block automated requests but work fine for real visitors. These are listed as 'Unverified' rather than broken. Click the link yourself to confirm it works.

**What is a canonical tag?**
A canonical tag tells search engines which URL is the preferred version of a page. It prevents duplicate content penalties when the same page is accessible via multiple URLs (e.g., with and without `www`, with tracking parameters, etc.).

**What is an orphan page?**
An orphan page is a page that no other page on your site links to. Search engines may not discover it reliably, and it receives no internal link value from the rest of your site.
