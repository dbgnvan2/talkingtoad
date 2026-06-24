# Agent-Readiness Checks — in plain English

> A friendly companion to the technical spec — now folded into the canonical
> `docs/functional-specification.md` §4.9 (Phase 1 shipped 2026-06-22).
> Same checks, no jargon — what each one is and what it helps with. Good for explaining the
> feature to a board, a client, or yourself.

## What "agent-readiness" means

Search is shifting from people clicking blue links to **AI assistants** (ChatGPT, Google's AI
answers, Perplexity, Claude) reading your site and answering on your behalf. "Agent-readiness"
is simply: **can AI find your site, understand it, trust it enough to quote it, and — if needed —
act on it?** There are two kinds of AI visitor:

- **Citation agents** — they read your pages and *quote* you in their answers. Most of the value today.
- **Task agents** — they *do things* on your site for a user (click a button, fill a form, book a session). Newer, but coming fast.

These checks add an **Agent-Readiness Score** (0–100) next to your existing Health Score, so you
can see at a glance how ready your site is for this new kind of visitor.

---

## Group A — Can AI even see your site?

If a site fails these, nothing else matters — the AI never gets in the door.

**AI crawler access.** Websites have a small file (`robots.txt`) that tells automated visitors
where they may go. Sometimes it accidentally blocks the AI crawlers by name (GPTBot, ClaudeBot,
PerplexityBot, Google-Extended), or the whole site is closed off. *Helps with:* making sure you
haven't quietly locked AI out of your site — the single most important thing to get right.

**Content that only appears with JavaScript.** Most AI crawlers read the "raw" page and don't run
the interactive scripts a browser does. If your main text only shows up after those scripts run,
the AI may see a nearly blank page. *Helps with:* catching the situation where your beautiful
homepage looks fine to you but reads as empty to AI — so you fix it before it costs you citations.

**Navigation that only appears with JavaScript.** Same idea, for your menus and links. If the AI
can't see your navigation, it can't discover the rest of your pages. *Helps with:* making sure AI
can travel through your whole site, not just the front door.

---

## Group B — Can AI understand and trust your page?

Once AI is in, these decide whether it can make sense of you — and whether it quotes you.

**Real buttons and links (not fake ones).** On the web, a button should be a real "button" and a
link a real "link" — not a styled box pretending to be one. AI (and screen readers) rely on those
real elements to know what's clickable. *Helps with:* making your page understandable to AI and
accessible to people using assistive technology — the same fix serves both.

**Page landmarks.** Pages can label their main content and navigation areas so software knows
"this is the main article, that's the menu." *Helps with:* helping AI focus on your actual content
instead of getting lost in headers and sidebars.

**Buttons and links that have a name.** An icon-only button (say, a bare magnifying glass) means
nothing to AI unless it has a hidden label. *Helps with:* making sure every clickable thing
announces what it does — again, good for AI and for accessibility.

**Organization information (schema).** "Schema" is a small, invisible block of facts that tells
search and AI engines who you are — your name, address, phone, founding date, charity status — in
a structured way they trust. *Helps with:* letting AI confidently identify and describe your
organization, instead of guessing.

**FAQ markup.** If you have a questions-and-answers section, marking it up as a proper FAQ makes it
far more likely to be pulled into an AI answer (this format gets cited notably more often).
*Helps with:* turning the Q&A you already wrote into content AI actually quotes.

**A visible date on articles.** AI favours content it can tell is current. A post with no visible
publish or update date looks undatable — and possibly stale. *Helps with:* signalling freshness so
your timely content isn't passed over.

**Contact details in text.** If your address, phone, or email lives only inside an image or a
script, AI can't read it. *Helps with:* making sure people (and AI) can actually find how to reach
you — critical for a counselling or service organization.

---

## Group C — Can AI (or a visitor) actually act?

These matter for task agents, but they're also plain-old broken-link problems that hurt every visitor.

**Dead placeholder buttons.** Sometimes a "Book Now" or "Contact" button is wired to go nowhere (a
placeholder that was never finished). A person clicks and nothing happens; an AI trying to act fails
instantly. *Helps with:* catching call-to-action buttons that quietly lead nowhere — embarrassing
on a live site and a dead end for anyone trying to take the next step.

**Links pointing to the wrong place.** Occasionally a link is left pointing at a placeholder like
`google.com` or `example.com` from when the page was being built. *Helps with:* finding links that
were never pointed at their real destination before they reach your visitors.

---

## The bottom line

Most of these overlap completely with **good accessibility and good SEO** — so there's no wasted
effort. Fixing them makes your site clearer to AI assistants, easier for people using screen
readers, and stronger in ordinary search, all at once. The Agent-Readiness Score rolls it up into
one number you can watch improve as you fix things.
