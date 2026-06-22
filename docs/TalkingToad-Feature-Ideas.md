**TalkingToad — Product Roadmap Ideas**

*GEO/AEO opportunities · the agent-readiness opportunity · Screaming
Frog coverage gaps · ideas for a great product*

Prepared June 2026 · Assessed against TalkingToad v2.6.0 (142 shipped
issue codes)

A note before the list: you have already shipped a surprising amount of
the on-page GEO playbook. To stay useful, this separates what you
already cover from what is genuinely new, and flags where an idea pushes
TalkingToad beyond its current on-site-crawler scope (a strategic
decision, not just an engineering one).

Colour key: **green = already shipped** · **red = new build** · **amber
= partial / extend**

**The big opportunity: agent-readiness**

Search is shifting from people reading blue links to AI agents reading,
citing, and increasingly acting on websites. Two things follow. First,
the audit market is widening from 'is my site good for Google?' to 'can
AI find, trust, quote, and operate my site?' Second — and this is your
wedge — almost every tool in this space only diagnoses. You already fix,
on WordPress, in plain English, for the exact audience (nonprofits and
small businesses) that has no SEO team and no developer to act on a
report.

> **The product nobody else is offering:** audit a site's
> agent-readiness (any platform) → explain it for non-experts → fix it
> in WordPress (inject schema, add the missing H1, write alt text,
> repair dead CTAs) → verify the fix and monitor over time → prove the
> business impact. Screaming Frog audits but never touches the site;
> generic GEO tools advise but don't fix; agencies charge thousands. The
> find-and-fix loop you already have, pointed at agent-readiness, is a
> defensible category of one.

*Everything below is organised to serve that thesis: Part 1 covers the
content/measurement ideas from the GEO webinar; Part 2 is the
agent-readiness build-out; Part 3 is the technical-SEO checks worth
borrowing from Screaming Frog; Part 4 is additional ideas to round out a
great product.*

**Part 1 — Ideas from the GEO/AEO webinar**

**Where TalkingToad is already strong (don't rebuild)**

Your spec already ships much of the on-page retrieval-readiness layer
the webinar preaches. Know this so you don't re-invent it:

> **• Answer-first structure:** GEO\_SUMMARY\_BURIED,
> AI\_MAIN\_CONTENT\_LOW\_RATIO, CONVERSATIONAL\_H2\_MISSING.
> 
> **• Retrieval formatting:** FAQ generator, Entity Schema Factory,
> schema typing, SCHEMA\_VISIBLE\_MISMATCH.
> 
> **• Freshness / velocity:** CONTENT\_DATE\_STALE\_VISIBLE,
> CONTENT\_STAT\_OUTDATED, Refresh Triggers.
> 
> **• AI access & llms.txt:** AI bot reference table
> (GPTBot/ClaudeBot…), llms.txt validate + generate, AI preview
> controls.
> 
> **• Original-data signals:** STATISTICS\_COUNT\_LOW,
> QUOTATIONS\_MISSING, Content Quality Advisor + Rewriter.
> 
> **• Performance reality-check:** GSC integration + Authority Matrix
> (Vulnerable Stars / Hidden Gems), Performance Ledger.

*The webinar's 'retrieval readiness' layer is largely done. The gaps are
in its other two layers — off-site authority signals and
business-outcome measurement.*

**Genuinely new ideas worth considering**

**1. AI visibility & citation tracking across LLMs**

The webinar's biggest theme — \~80% of citations are off-site, and you
should audit where you (and competitors) are cited across ChatGPT,
Gemini, Perplexity, Grok, Meta AI and Copilot. You already have a
citation-ingestion endpoint and a parked SERP-discovery repo; this
activates them into a real feature: query a panel of LLMs for target
questions, record whether your domain is cited, surface competitor
citations you're missing. Highest impact, highest effort, and it moves
you off-site — a deliberate scope expansion.

**2. A business-outcome measurement layer (kill the vanity metrics)**

The webinar's loudest practical point: stop reporting
mentions/impressions; tie visibility to revenue. Your Authority Matrix
already correlates health with GSC clicks — extend it. Add GA4
conversion/revenue ingestion; segment AI-referral traffic by detecting
referrers (chatgpt.com, perplexity.ai, gemini.google.com, copilot,
claude.ai); track branded-search lift and conversion-rate-by-source.
This directly answers the 'so what?' question for your users and is a
natural extension of work you've started.

**3. Content-opportunity / gap audit for high-citation formats**

Detect whether the site even has the content types AI cites most —
comparison and 'X vs Y' pages, alternatives/listicles,
original-research/statistics pages, bottom-funnel buyer guides — and
flag the missing ones as opportunities, then offer to scaffold them with
your existing FAQ/entity generators.

**4. Author / E-E-A-T signal audit**

Expert authorship is named as heavily weighted. Check for a visible
author byline, Person schema with credentials, and sameAs links to
author profiles (LinkedIn, ORCID). Low effort, fully on-site,
complements your entity work.

**5. Off-site entity & reputation footprint (on-site proxy)**

You can't crawl Reddit, but you can audit the on-site evidence of an
off-site presence: Organization schema with sameAs links to key
third-party profiles (Wikipedia, LinkedIn, YouTube, G2/Trustpilot,
Crunchbase). Flag a thin sameAs footprint as a corroboration risk. A
fuller version (review-velocity, brand-mention tracking) needs off-site
integrations — note that as a scope decision.

**6. Conversion-readiness audit on key pages**

The webinar's 'AI-friendly conversion architecture' — fast pages, clear
CTAs, trust signals, interactive tools. A lightweight version checks for
a visible CTA, trust signals (reviews/testimonials/badges) and
page-speed/Core Web Vitals (Part 3). Turns your audit from 'is this page
retrievable?' into 'does this page convert the visitor AI sent?'

**Part 2 — Agent-readiness: the build-out**

This is the section to lean into. It splits cleanly into two audiences,
and you've built most of the first half already.

**Two audiences, two halves**

**Citation agents** (ChatGPT, Perplexity, Claude, Google AI Overviews)
crawl and quote your content. **Task-executing agents** browse and act
on a user's behalf — filling forms, clicking CTAs, navigating. Your 60
AI-readiness codes largely cover the citation half. The task-execution
half is new territory, and it's where the freshest checks live.

> **Productize it as an 'Agent-Readiness Score.'** You already compute a
> Health Score and 60 AI-readiness signals. Surface a second headline
> number — Agent-Readiness — built from the citation-side codes you have
> plus the task-side checks below. A named, shareable score is a
> marketing asset and a natural lead-magnet (a free 'Agent-Readiness
> Scan').

**New checks to add (task-execution half)**

**A. Semantic-HTML & interactive-element correctness**

The key insight from the agent-readiness research: agents read the
accessibility tree — the browser's roles/names/states view — the same
structure screen readers use. Add checks for div/span used as buttons or
links, missing \<main\>/\<nav\>/\<header\> landmarks, and interactive
elements (buttons, links, form fields) with no accessible name. You
don't check any of this today.

> **This reframes accessibility.** I previously ranked WCAG/axe-core
> auditing as medium-priority, do-it-for-ADA-reasons. The
> accessibility-tree insight gives it a second, stronger rationale — it
> is literally the channel agents use to parse you — so raise its
> priority. Accessibility compliance and agent-readiness are now largely
> the same work, which is an efficient story to tell users.

**B. Client-side-render risk detection (cheap fix for your biggest
gap)**

Most AI crawlers ignore client-side JavaScript. You crawl static HTML
and can't render — I'd previously said 'defer full JS rendering, big
lift.' But you don't need a renderer to detect the problem: flag pages
whose server HTML has very little extractable text but heavy
JS-framework markers (empty root div, bundled scripts, content loaded
via AJAX). The check warns 'AI crawlers may see almost nothing here.'
This is the highest-value new check because it partially closes your
biggest gap without the architectural cost of rendering.

**C. Dead / placeholder CTA & link detection**

Flag href="\#", javascript:void(0), and links to obvious placeholder
domains (example.com, a stray google.com). You already flag empty anchor
text (LINK\_EMPTY\_ANCHOR) but not dead-action links. Cheap to build,
and it matters specifically for task agents that try to navigate or act
— a CTA that goes nowhere fails the agent (and the human) immediately.

**D. Form readiness for task agents**

Agents that book, enquire or sign up need forms they can operate: inputs
with associated \<label\>s, sensible name/autocomplete attributes, and
clear submit buttons. Add a lightweight form-readiness check. This is
foundational for the booking/intake flows your nonprofit users care
about.

**E. FAQPage schema presence (verify, then sharpen)**

FAQPage JSON-LD is associated with materially higher AI-citation rates.
You have a FAQ generator and schema typing — confirm whether you
explicitly flag 'FAQ-style content present but no FAQPage schema,' and
if not, add that gap check (with an offer to generate the schema).

**A killer feature: 'See your site as an agent sees it'**

Render, side-by-side, what a citation agent actually extracts from a
page (the text-only / accessibility-tree view) versus what a human sees.
Nothing makes the problem visceral faster than showing an org that
ChatGPT sees an empty page where their beautiful hero section is. It's a
screenshot-grade demo, a sales hook, and a genuinely useful diagnostic —
and it pairs perfectly with check B above.

**Extend the fix-loop to agent-readiness (your moat)**

Auditing agent-readiness is table stakes; fixing it is the
differentiator, and much of it is within your existing WordPress write
mechanisms:

> **• Inject Organization / LocalBusiness / FAQPage / Person schema** —
> you already generate entity and FAQ JSON-LD; wire it to one-click
> insertion.
> 
> **• Add a missing H1, fix heading order** — you already apply heading
> fixes.
> 
> **• Write descriptive alt text** — you already do AI alt-text
> suggestion + image meta updates.
> 
> **• Repair dead CTAs / placeholder links** — extends your
> link-replacement fixer.
> 
> **• Add/curate llms.txt** — already shipped.

*The semantic-HTML and form fixes are harder (theme-dependent), so
audit-and-guide there rather than auto-fix. But the schema, heading,
alt-text and link fixes turn 'your site isn't agent-ready' into 'we made
your site agent-ready' — in one tool.*

**Part 3 — Technical checks worth borrowing from Screaming Frog**

Screaming Frog catalogues 300+ checks; you ship 142. Most of the ones
you lack are power-user niche. Below are the ones that matter for
WordPress-based small-business and nonprofit sites, prioritised by user
impact against build effort, excluding what you already cover.

**High priority — common, high-impact, mostly low effort**

|                                           |                                                                                                                                                 |                  |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| **Check**                                 | **Why it matters for your users**                                                                                                               | **Build effort** |
| **Image missing width/height attributes** | Top cause of layout shift (CLS) — hurts Core Web Vitals and UX. You flag oversized images but not missing dimensions.                           | **Low**          |
| **Soft 404 detection**                    | Pages returning HTTP 200 with 'not found' content. Common on WordPress; invisible to a status-code check.                                       | **Medium**       |
| **Canonical robustness suite**            | Multiple/conflicting canonicals, canonical to a non-indexable or relative URL, canonicalised pages. Frequent Yoast/Rank Math misconfigurations. | **Low**          |
| **Structured-data VALIDATION**            | You type schema but don't validate it against Schema.org / Google rich-result rules. Directly strengthens your GEO/agent story.                 | **Medium**       |
| **Pagination (rel=next/prev)**            | Archive/blog-heavy nonprofit sites paginate heavily; zero coverage today.                                                                       | **Medium**       |
| **Mobile usability (beyond viewport)**    | Illegible font size, tap-target size, content not sized to viewport. You only check viewport presence.                                          | **Medium**       |

**Medium priority — valuable, moderate effort**

|                                         |                                                                                                                                         |                  |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| **Check**                               | **Why it matters for your users**                                                                                                       | **Build effort** |
| **PageSpeed / Core Web Vitals**         | LCP, CLS, render-blocking, image delivery via the PageSpeed Insights API. Ties to the 'fast pages convert' point; SF integrates this.   | **Medium**       |
| **Readability + placeholder detection** | Flesch-style readability and Lorem-Ipsum/placeholder flags. 'Concise, retrievable' is core to GEO and agent-readiness.                  | **Medium**       |
| **Spelling & grammar**                  | Credibility/trust signal (SF does 25 languages). Could route through your existing AIRouter rather than a new engine.                   | **Medium**       |
| **Internal-link analysis depth**        | Pages with no internal outlinks, nofollow-only inlinks, an internal link score. Webinar stresses internal linking for bot crawlability. | **Medium**       |
| **hreflang auditing**                   | Return tags, language/region consistency. High value only for multilingual sites — lower for single-language nonprofits.                | **Medium**       |
| **Accessibility (WCAG / axe-core)**     | Now double-justified: ADA pressure AND agent-readiness (the accessibility tree). Integrate axe-core rather than hand-rolling.           | **High**         |

**Lower priority — easy wins or niche**

> **• Security header suite:** CSP, X-Content-Type-Options,
> X-Frame-Options, Referrer-Policy, insecure/HTTP forms. Cheap; modest
> value. (Low)
> 
> **• Title/description pixel-width:** Truncation by rendered pixels,
> not just character count. Minor refinement. (Low)
> 
> **• HTML validation & page-weight:** Missing/multiple head/body tags,
> document over 2 MB. Partly covered by your 300 KB page-size check.
> (Low)

**Deliberately skip**

Full JavaScript rendering (use the cheap detection in Part 2.B instead),
AMP deep validation, custom XPath/CSS extraction, log-file analysis, and
the WCAG-AAA long tail are high-effort, expert-facing, and off-strategy.

**Part 4 — Additional ideas for a great product**

Beyond individual checks, these round TalkingToad into a product orgs
return to — not a one-off scan.

**Continuous monitoring + alerts (not one-off audits)**

Scheduled re-crawls with email/Slack alerts when the score drops, a fix
regresses, a new broken link appears, or an AI crawler gets blocked.
This is the single biggest lever for retention and recurring value, and
the webinar's 'maintain velocity or competitors displace you' point
applies directly. You already have the Performance Ledger to build on;
Screaming Frog charges for scheduling — make it core.

**Competitor benchmarking**

Audit a competitor's public site and compare Health and Agent-Readiness
scores side by side. The webinar repeatedly stressed 'find where
competitors are cited and you aren't.' Your audit engine is already
CMS-agnostic on the read side, so this is mostly UI and framing — and
it's a strong sales and renewal hook.

**Make 'fix impact' a first-class story**

You apply a fix, re-scan, and update the Performance Ledger — but
surface it as a narrative: 'You fixed 12 issues; health 64 → 81; these 3
high-traffic pages improved.' A before/after view (Screaming Frog's
crawl-comparison, repurposed for non-experts) proves the tool's worth
every month.

**Lead with a free Agent-Readiness Scan**

A no-signup, single-URL 'how agent-ready is your site?' scan that
returns the score and top three fixes, then offers the full crawl +
one-click fixes. It's the natural top-of-funnel for the opportunity,
mirrors Screaming Frog's free-tier hook, and showcases your unique fix
capability.

**Separate the audit (any CMS) from the fix (WordPress)**

Your remediation is WordPress-only, but the audit is CMS-agnostic. Let
anyone scan any site for free; gate only the one-click fixes behind
WordPress. This widens the funnel dramatically without diluting the moat
— a Squarespace nonprofit can still get the audit, the report, and a
reason to migrate or hire help.

**Plain-language, board-ready Agent-Readiness report**

You already produce branded PDF/Excel reports. Add an Agent-Readiness
report framed for a non-technical board or funder: 'Here's how findable
and trustworthy your site is to AI, what we fixed, and what it means for
reach.' This is the artifact that justifies the tool to the people who
hold the budget.

**If I had to pick the top moves**

**1. Ship an Agent-Readiness Score + the four new agent checks (Part 2
A–D)** — names and owns the opportunity.

**2. Extend the fix-loop to schema/H1/alt/CTA** — turns 'audit' into
'fixed,' which nobody else does.

**3. Client-side-render detection + 'see your site as an agent'** —
cheap, visceral, closes your biggest gap.

**4. Continuous monitoring + competitor benchmarking** — converts
one-off scans into recurring value.

**5. Business-outcome measurement (Part 1.2) + structured-data
validation** — makes the whole thing defensible to a budget-holder.

> **Honest caveat on scope.** *The richest ideas here — off-site
> citation tracking, revenue measurement, competitor benchmarking,
> continuous monitoring — pull TalkingToad from an on-site WordPress
> auditor toward a broader agent-readiness platform. That is very likely
> the right direction given where search is heading, but it is a
> product-identity decision with real engineering and positioning
> weight. The on-page agent checks, the fix-loop extensions, and the
> Screaming Frog technical checks all fit inside what you already are.*

*Sources: NP Digital AEO/GEO webinar transcript; an agent-friendliness
advisory conversation (Google's April 2026 agent guide, llms.txt,
NLWeb/MCP/WebMCP, accessibility-tree behaviour) provided by the user;
Screaming Frog SEO Spider Issues library and product page (v24.1, June
2026); TalkingToad functional specification v2.6.0. 'Already shipped'
claims are taken from your functional spec's feature catalogue; where I
was unsure (e.g. FAQPage schema gap check) I flagged it to verify rather
than assert.*
