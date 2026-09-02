# TalkingToad — Nonprofit SEO Crawler

Welcome to **TalkingToad**, a lightweight web-based SEO auditing and remediation tool specifically designed for nonprofit organisations. 

TalkingToad helps you identify technical SEO issues on your website and — for WordPress sites — allows you to apply fixes directly without writing any code.

## 🚀 Key Features

- **Async SEO Crawler:** Scans up to 500 pages for 170 SEO issue codes, using a recalibrated severity model where only page-fatal problems surface as Critical.
- **WordPress Fix Manager:** One-click fixes for page titles, meta descriptions, headings, and image alt text.
- **AI-Readiness Audit:** Checks how well your content is prepared for AI search engines (GEO optimization).
- **FAQ / GEO Schema Generator:** Generates ready-to-paste Schema.org FAQPage JSON-LD from a page's Q&A to improve AI/GEO visibility.
- **Image Intelligence:** Vision-AI powered image analysis and automatic optimization.
- **Search Console Integration:** Optional Google Search Console link (app-wide, one-time OAuth) blends real search performance into the priority ranking; a built-in Connections panel tests AI-provider and GSC connectivity.
- **Per-Site Issue Filter:** Hide issue codes — or every `info`-level finding — for one
  site, so the results show what that site's team actually acts on. Findings are hidden,
  never deleted, and the health score is deliberately unchanged so filtering cannot
  flatter a site. Exported reports match the screen and state that they are a filtered view.
- **Page Audit — named items and a real re-check:** Every finding lists the actual
  offending items (which links, which images, which schema fields), with a **Get full
  details** button that re-reads the page live and stores nothing. **Re-check this page**
  confirms a fix without re-crawling, and reports what it found — resolved, still
  present, newly found, or *not re-checked* for the checks that need a whole-site crawl.
  It never marks a finding fixed on the strength of a check it could not run.
- **Info detail:** Info notices are graded **Key / Notable / Low** from their impact, and a scan's
  *Info detail* setting (Advanced settings) chooses which tiers it shows **and counts toward the
  health score** — the level is printed under the score, excluded notices can be revealed, and
  exports and comparisons say what was left out.
- **Rescan:** Every finished scan on the home page has a **Rescan** button that re-runs it
  with the settings it was originally run with — page limit, analysis toggles, ignored
  headings, content-type scope, GSC priority file. Nothing to re-enter, and the score
  stays comparable to the previous run: a scan re-run under different settings shows a
  delta that is partly a change in what was measured, not in the site.
- **Professional Reporting:** Export results as tabbed Excel workbooks or professional PDF audits.

---

## 📖 User Help & Guides

If you are a user looking for help on how to use TalkingToad, please refer to our canonical guides:

- **[User Guide](docs/user-guide.md)** — The complete manual on running crawls, understanding results, and using the WordPress Fix Manager.
- **[Issue Catalogue](docs/issue-codes.md)** — A complete list of all SEO issues TalkingToad checks for, including their impact and how to fix them.
- **[Overview](docs/overview.md)** — A high-level introduction to the project goals and target audience.

---

## 🛠️ Developer Resources

If you are a developer looking to contribute or deploy TalkingToad:

- **[CLAUDE.md](CLAUDE.md)** — Start here! This is the machine-readable rulebook for working in this repo.
- **[Documentation Index](docs/README.md)** — The central hub for all technical documentation (Architecture, API, Security, Deployment).
- **[Functional Specification](docs/functional-specification.md)** — Detailed description of all observable behaviour and acceptance criteria.
- **[TODO.md](TODO.md)** — Current technical debt and upcoming tasks.

---

## 🚦 Project Status

- **Current Version:** 3.0.0 (Shipped)
- **Roadmap:** See [PLAN-V4.0.md](PLAN-V4.0.md) for future feature drafts.
- **Archive:** Historical planning documents can be found in the [archive/](archive/) directory.

---

**GitHub:** [https://github.com/dbgnvan2/talkingtoad](https://github.com/dbgnvan2/talkingtoad)  
**Last Updated:** 2026-09-01
