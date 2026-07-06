---
status: draft-review + claude-overlay
proposed: 2026-07-02
authors: Hermes Agent (original) + Claude Opus 4.8 (overlay)
type: review
scope: AI-readiness core — ai_readiness + AI Bot Access + Schema Typing + Content Extractability + Citations (part 4 of 5)
---

# Scoring Weight Review — Part 4: AI-Readiness Core
### (with Claude assessment blocks interleaved)

> Hermes's original text is unchanged. After each code, a block marked **◆ CLAUDE — Confidence: …** gives an independent second opinion. This part contains two of the review's most consequential corrections — `AI_BOT_USER_FETCH_BLOCKED` and `LLMS_TXT_MISSING` — both verified against current (early-2026) vendor documentation.

---

## General Observation

A pattern emerges in this section: **several codes with "Heuristic" confidence are weighted higher than codes with "Reasonable proxy" or even "Established" confidence.** The confidence labels were introduced precisely to track certainty, but the impact scores don't follow them. Heuristic checks should generally have lower impact scores to reflect that we're guessing.

> **◆ CLAUDE — Confidence: Medium**
> Agree with the observation and the general direction. One refinement (expanded in the overview): confidence and effect-size are separate axes. A single-study heuristic with a *measured* effect (the GEO/Aggarwal statistics/citations findings) shouldn't be capped at the same ceiling as a pure guess with no evidence. Prefer two fields — `confidence` × `effect_size` — over one mechanical cap.

---

## AI-Readiness Checks

### LLMS_TXT_MISSING — (6, 1) → 58 (Heuristic)

**Assessment:** Impact 6 is TOO HIGH. `/llms.txt` is an emerging convention (proposed by AnswerThePublic's founder as a way to guide LLM crawlers). No major AI engine (Google, OpenAI, Anthropic, Perplexity) has confirmed using it. It's a "Heuristic" confidence check — industry consensus only. Impact 6 is tied with CANONICAL_MISSING (a well-established SEO requirement). This should be impact 3 at most.

**Recommendation:** LOWER impact from 6 to 3. (3, 1) → 28

> **◆ CLAUDE — Confidence: High**
> **Agree with lowering, but two facts in the rationale are wrong** (verified against 2026 sources):
> 1. **Attribution:** llms.txt was proposed by **Jeremy Howard of Answer.AI / fast.ai** (Sept 3, 2024), not "AnswerThePublic's founder." (Answer.AI and AnswerThePublic are unrelated companies — easy conflation, but worth fixing in a tool that cites its reasoning.)
> 2. **"No major engine confirmed":** As of 2026, Google explicitly *declined* to support it (Illyes; Mueller likened it to the keywords meta tag) and OpenAI points to robots.txt — but **Anthropic and Perplexity have signaled/confirmed support**, and IDE agents (Cursor, Claude Code, Copilot) fetch it routinely.
>
> Net: the *score* is right (low), but for the correct reason — **no measurable AI-citation lift and negligible fetch volume from the search/answer bots as of 2026**, not "nobody uses it." I'd set (2–3, 1). Practical note for Living Systems: shipping one is a cheap, low-yield forward bet — it costs half a day and does no harm, but it is not a citation lever. Don't let this check imply otherwise.

---

### LLMS_TXT_INVALID — (4, 2) → 36 (Heuristic)

**Assessment:** Impact 4 is too high for a heuristic check that follows from the same uncertain premise. Having an invalid llms.txt is less harmful than missing it entirely. Impact 2 is more appropriate.

**Recommendation:** LOWER impact from 4 to 2. (2, 2) → 16

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (2, 2). If the file does almost nothing when valid, an invalid one does almost nothing worse. The only real cost is that an agent that *does* read it (an IDE tool) gets a malformed map. Low impact is right.

---

### SEMANTIC_DENSITY_LOW — (5, 3) → 44 (Heuristic)

**Assessment:** Impact 5 is TOO HIGH. This checks text-to-HTML ratio (<10%). On a typical nonprofit WordPress site with bloated themes, this will flag nearly every page. The threshold is arbitrary and the SEO/AI impact is indirect at best. This is a Heuristic check — impact 3 is more honest. Effort 3 (template/theme work) is appropriate.

**Recommendation:** LOWER impact from 5 to 3. (3, 3) → 24

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 3). Text-to-HTML ratio is a genuinely poor metric on any page-builder site — Elementor emits enormous nested-div markup, so a content-rich page can score "low density" purely from wrapper bloat. It measures theme verbosity, not content quality. I'd consider deprecating it in favor of a direct extractable-word-count check (which you already have via CONTENT_THIN). If kept, 3 is the ceiling.

---

### DOCUMENT_PROPS_MISSING — (4, 2) → 36 (Reasonable proxy)

**Assessment:** Impact 4 is too high for a PDF-specific check. Missing Title/Subject metadata in PDFs affects AI citation labels but has zero SEO impact and only affects PDF content. Impact 2 is more appropriate for this niche check.

**Recommendation:** LOWER impact from 4 to 2. (2, 2) → 16

> **◆ CLAUDE — Confidence: Medium**
> Agree, (2, 2). Google *does* use PDF Title metadata for the search result title, so "zero SEO impact" slightly overstates — but it's a niche, low-volume signal. 2 is right. Relevant to your Bowen Theory PDF library, where consistent Title/Author props would modestly help both Google's PDF titles and AI citation labels.

---

### JSON_LD_MISSING — (7, 2) → 66 (Reasonable proxy)

**Assessment:** Impact 7 is well-calibrated. JSON-LD structured data is the primary way Google understands page content for rich results, and AI engines use schema heavily for entity extraction and citation. This is one of the most important AI-readiness signals. The "Reasonable proxy" label probably understates this — Google has confirmed schema's importance for rich results.

**Recommendation:** KEEP AS-IS (7, 2) — consider upgrading confidence to "Established"

> **◆ CLAUDE — Confidence: High**
> Agree, (7, 2), and agree with upgrading confidence to Established for the *rich-results* claim (Google's documentation is explicit). One precision point: schema is Established for **Google rich results and entity disambiguation**; its role in **AI-answer citation** specifically is Reasonable-proxy (correlational, not vendor-confirmed as a ranking lever). So a split label is most accurate: Established (rich results) + Reasonable proxy (AI citation). Score holds at 7 — this is one of the highest-value GEO checks in the system.

---

### CONVERSATIONAL_H2_MISSING — (4, 2) → 36 (Heuristic)

**Assessment:** Impact 4 is too high for a Heuristic check with no vendor confirmation. This flags H2s that don't start with conversational interrogatives (How, What, Why). There's no evidence this affects AI citation. It's an experiment, not a weightable signal. Impact 2 is appropriate.

**Recommendation:** LOWER impact from 4 to 2. (2, 2) → 16

> **◆ CLAUDE — Confidence: High**
> Agree, (2, 2), arguably (1, 2). This is the weakest kind of heuristic — a stylistic pattern with no evidence and high false-positive potential (a heading "Emotional cutoff in families" is perfectly extractable without a "What is…" prefix). Question-form headings can help match conversational queries, but *mandating* them is cargo-culting. Keep at the floor.

---

### BLOG_SECTIONS_MISSING — (5, 2) → 46 (Heuristic)

**Assessment:** Impact 5 is too high. This checks whether a blog/article page has sufficient heading structure for AI citation anchors. The concept is sound (headings do serve as citation anchors for AI engines), but the confidence is Heuristic and the threshold is arbitrary (fewer than 3 headings). Impact 3 is more realistic.

**Recommendation:** LOWER impact from 5 to 3. (3, 2) → 26

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 2). Heading structure genuinely helps AI chunking, so this isn't pure speculation — but the "<3 headings" threshold is crude and will misfire on legitimately short posts. Keep at 3; consider scaling the threshold to word count rather than a flat count.

---

## AI Bot Access Checks

### AI_BOT_SEARCH_BLOCKED — (8, 1) → 78 (Established)

**Assessment:** Impact 8 is correct. Blocking a major AI search bot (GPTBot, Google-Extended, ClaudeBot) in robots.txt has a confirmed, direct effect on whether your content appears in AI search results (ChatGPT, Gemini, Perplexity, etc.). The confidence label is "Established" — this is vendor-confirmed. Keep.

**Recommendation:** KEEP AS-IS (8, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (8, 1), with a taxonomy correction that matters for accuracy: the bots that gate **AI search visibility** are the *search* crawlers — **OAI-SearchBot** (OpenAI), **Claude-SearchBot** (Anthropic), **PerplexityBot**, and **Google-Extended** (Gemini grounding/training). **GPTBot and ClaudeBot are *training* crawlers** — blocking them removes you from future model training, **not** from live AI search. OpenAI states plainly that sites opted out of OAI-SearchBot won't appear in ChatGPT search answers. So the check should key on the *search* user-agents; if it currently flags GPTBot/ClaudeBot as "search blocked," it's conflating training with search (that's the AI_BOT_TRAINING_DISALLOWED case below, correctly scored 0). Impact 8 is right for a genuine *search*-bot block.

---

### AI_BOT_TRAINING_DISALLOWED — (0, 1) → -2 (Established)

**Assessment:** Impact 0 is correct. This is intentionally a zero-impact observation. Blocking training bots doesn't affect AI search visibility. This is correctly an info-level, zero-impact check.

**Recommendation:** KEEP AS-IS (0, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (0, 1). Blocking training (GPTBot/ClaudeBot/CCBot/Google-Extended-for-training) is a legitimate IP choice with no search-visibility cost. Zero impact is exactly right — it's a values decision, not a defect. Good that the tool doesn't moralize it.

---

### AI_BOT_USER_FETCH_BLOCKED — (4, 1) → 38 (Established)

**Assessment:** Impact 4 is too high. This flag fires when a user-fetch bot (ChatGPT-User, Claude-User) is blocked in robots.txt — which has no effect because these bots don't honor robots.txt by design. The check itself tells the user their block is ineffective. Impact 2 is more appropriate (it's a misconfiguration, not a problem).

**Recommendation:** LOWER impact from 4 to 2. (2, 1) → 18

> **◆ CLAUDE — Confidence: High**
> **Disagree — the premise is factually wrong, and it inverts the conclusion.** Verified against current vendor docs (Feb–Apr 2026):
> - **Anthropic states all three of its bots — including Claude-User — honor robots.txt.** So blocking Claude-User in robots.txt **is effective**, and therefore blocking it **does** stop Claude from fetching your page when a user asks about you. That's a real visibility cost, not a no-op.
> - **OpenAI** takes a softer line: robots.txt "may not apply" to ChatGPT-User (ambiguous, not "ignored by design").
> - **Perplexity-User** and **Google's** user-proxy fetchers *do* generally ignore robots.txt.
>
> So compliance is **vendor-specific, not category-wide.** Hermes's "the block does nothing, so lower the impact" reasoning holds only for Perplexity/Google, and fails for Anthropic (and partly OpenAI). Because an accidental Claude-User/ChatGPT-User block genuinely removes you from user-initiated AI fetches for the compliant vendors, **keep impact at 4** (or 3 if you want to hedge for the non-compliant vendors). Do **not** drop to 2 on an "ineffective anyway" basis. If anything, this check should *warn that the block is working and costing visibility*, not that it's futile.

---

### AI_BOT_DEPRECATED_DIRECTIVE — (2, 1) → 18 (Established)

**Assessment:** Impact 2 is about right. Using old bot names (anthropic-ai, claude-web) means the rules don't apply to the current bots. Minor — confirmed fact but low impact. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (2, 1). Confirmed: `anthropic-ai` and `Claude-Web` are deprecated; current strings are ClaudeBot / Claude-User / Claude-SearchBot. A rule targeting the old names silently does nothing. There's a subtle sharper case worth a note: if someone *intended to block training* using `anthropic-ai` and it's now inert, their content may be getting trained on against their wishes — for a privacy-conscious org that's more than cosmetic. Score fine at 2; consider surfacing the "your intended block is inert" framing.

---

### AI_BOT_NO_AI_DIRECTIVES — (1, 1) → 8 (Reasonable proxy)

**Assessment:** Impact 1 is correct. Not having explicit AI bot rules doesn't harm anything — by default, they're allowed. This is an info-level observation. Keep.

**Recommendation:** KEEP AS-IS (1, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (1, 1). For a site that *wants* AI visibility (which Living Systems does), "no AI directives" = "allow all" = the desired state. Correctly near-zero, informational.

---

### AI_BOT_BLANKET_DISALLOW — (9, 1) → 88 (Established)

**Assessment:** Impact 9 is correct. `User-agent: * Disallow: /` blocks ALL bots, including Googlebot. This is catastrophic for a site's SEO and AI visibility. The only reason it's not 10 is that it's usually intentional (dev/staging). Keep.

**Recommendation:** KEEP AS-IS (9, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (9, 1). This is the single most dangerous robots.txt state and the classic migration accident — a `Disallow: /` shipped from staging to production. Directly relevant: your staging host (`daveg24.sg-host.com`) *should* carry a blanket disallow; the risk is it surviving the cutover to livingsystems.ca. The check should treat blanket-disallow on a staging domain as expected and on the production domain as critical. Correct score.

---

### AI_BOT_TABLE_STALE — (0, 1) → -2 (Heuristic)

**Assessment:** Impact 0 is correct. Internal documentation check only. Keep.

**Recommendation:** KEEP AS-IS (0, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (0, 1). Internal maintenance flag; no user-facing impact. Given how fast the bot landscape moves (Claude-SearchBot and the three-tier split were formalized in early 2026), a staleness reminder on your own bot table is genuinely useful — just correctly zero-scored.

---

## Schema Typing Checks

### SCHEMA_TYPE_MISMATCH — (4, 2) → 36 (Reasonable proxy)

**Assessment:** Impact 4 is reasonable. Using the wrong schema type (e.g., Product instead of Article) means Google's rich results may not apply and AI engines may misinterpret the content. This is a real quality signal. Keep.

**Recommendation:** KEEP AS-IS (4, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (4, 2). A wrong type is worse than no type because it actively misinforms. Relevant to your JetEngine CPTs: Team Member, Training, and Podcast Episode pages should carry appropriate types (Person, Course/Event, PodcastEpisode) — a mismatch there would mislead both Google and AI extractors about entity type. Score fine.

---

### SCHEMA_DEPRECATED_TYPE — (2, 1) → 18 (Reasonable proxy)

**Assessment:** Impact 2 is correct. Using deprecated schema types is a minor hygiene issue — they still work but may not be supported forever. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (2, 1), with a concrete example that raises the stakes slightly: Google **deprecated HowTo rich results (2023)** and **restricted FAQ rich results to authoritative government/health sites (2023)**. So markup that used to earn rich results now silently earns nothing. That's not harmful, but it means effort spent maintaining FAQ/HowTo schema for SERP features is wasted for most sites. Worth flagging as "no longer yields rich results," not just "deprecated type." Score fine.

---

### SCHEMA_TYPE_CONFLICT — (3, 2) → 26 (Reasonable proxy)

**Assessment:** Impact 3 is reasonable. Conflicting schema types (e.g., declaring both Product and Article on the same page) create ambiguity for parsers. Google may ignore the conflicting data. Keep.

**Recommendation:** KEEP AS-IS (3, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 2). Caveat: multiple types on one page are often *legitimate* (a WebPage containing an Organization and a BreadcrumbList, or an @graph with several linked entities). Only flag genuinely contradictory primary types, or this false-positives on well-built schema. Score fine.

---

### SCHEMA_VISIBLE_MISMATCH — (5, 2) → 46 (Established)

**Assessment:** Impact 5 is reasonable. Google's own guidelines state that schema values should match visible page content. Mismatch can trigger manual actions or rich result loss. "Established" confidence is correct. Keep.

**Recommendation:** KEEP AS-IS (5, 2)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (5, 2). This is genuinely Established — Google's structured-data guidelines explicitly require marked-up content to be visible to users, and violations can draw a manual action. Higher-confidence than most of this section; correctly weighted.

---

### AI_CONTENT_NOT_IN_TEXT — (4, 2) → 36 (Reasonable proxy)

**Assessment:** Impact 4 is reasonable. Critical content in images/video/embeds that AI systems can't read as text is a real barrier to AI extraction. Impact 4 is appropriate for a "Reasonable proxy" signal.

**Recommendation:** KEEP AS-IS (4, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (4, 2). Overlaps with AI_CONTENT_NOT_IN_TEXT / CONTENT_NOT_EXTRACTABLE / CONTACT_INFO_NOT_IN_HTML (Part 5) — several checks circle "important info trapped in non-text." Ensure they target distinct cases (body content vs whole-page vs contact block) rather than stacking. Directly relevant to you: text baked into hero images or Vimeo-only content is invisible to extractors. Score fine.

---

### AI_PREVIEW_SUPPRESSED — (3, 1) → 28 (Established)

**Assessment:** Impact 3 is reasonable. Suppressing search/AI previews (nosnippet) is a deliberate choice — this flag informs the user that their content won't appear in AI Overviews. Impact 3 is appropriate for info level.

**Recommendation:** KEEP AS-IS (3, 1)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (3, 1). Accurate: `nosnippet` / `max-snippet:0` do suppress the text Google can use in featured snippets and AI Overviews. Usually accidental when present, so surfacing it is useful. If unintended, the real impact is higher than 3 — consider making it conditional on whether the page otherwise wants visibility. Score defensible.

---

### AI_PREVIEW_BLOCKED_AT_BOT — (3, 1) → 28 (Established)

**Assessment:** Impact 3 is reasonable. Same as above — deliberate choice. Keep.

**Recommendation:** KEEP AS-IS (3, 1)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 1). Same logic as AI_PREVIEW_SUPPRESSED.

---

### AI_NO_VISUAL_COMPANION — (1, 1) → 8 (Reasonable proxy)

**Assessment:** Impact 1 is correct. Text pages without images are fine — adding images is a nice improvement but not a problem. Keep.

**Recommendation:** KEEP AS-IS (1, 1)

> **◆ CLAUDE — Confidence: High**
> Agree, (1, 1). A text-only page is not a defect. Correctly at the floor.

---

### AI_MAIN_CONTENT_LOW_RATIO — (2, 1) → 18 (Heuristic)

**Assessment:** Impact 2 is reasonable. Main content <40% of visible text is a usability/extraction concern, not a direct harm. Heuristic confidence, low impact — correct calibration.

**Recommendation:** KEEP AS-IS (2, 1)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (2, 1). This is a better-targeted version of SEMANTIC_DENSITY_LOW (main-content ratio is more meaningful than raw text-to-HTML). If you deprecate SEMANTIC_DENSITY_LOW, this is the check to keep. Score fine.

---

## Content Extractability

### CONTENT_NOT_EXTRACTABLE_NO_TEXT — (6, 4) → 52 (Reasonable proxy)

**Assessment:** Impact 6 is reasonable. A page with no visible text at all (images-only or JS-shell) is completely invisible to AI extractors. This is a significant barrier. However, effort 4 is too high — adding text to a page is a content-edit task, not "major dev work." Effort 2.

**Recommendation:** KEEP impact 6, LOWER effort from 4 to 2. (6, 2) → 56

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (6, 2), with a distinction: if the page is text-free because it's *image-only*, the fix is content (effort 2). If it's text-free because it's a *JS shell* (content renders client-side and isn't in raw HTML), the fix is SSR/pre-rendering — genuine dev work (effort 4). Same symptom, very different effort. If the check can tell these apart, split the effort; otherwise 2–3 is a fair blended estimate. This overlaps with RAW_HTML_JS_DEPENDENT (Part 5) — coordinate them.

---

### CONTENT_THIN — (4, 3) → 34 (Reasonable proxy)

**Assessment:** Impact 4 is reasonable for thin content (<100 words). Similar to the crawlability THIN_CONTENT check but at a stricter threshold and in the AI-readiness category. Effort 3 is too high — adding content is a wordpress-fixable content edit, effort 1-2.

**Recommendation:** KEEP impact 4, LOWER effort from 3 to 2. (4, 2) → 36

> **◆ CLAUDE — Confidence: Medium**
> Agree, (4, 2). Flag the overlap: this and THIN_CONTENT (Part 2) are the same concept at two thresholds (<100 vs the Part 2 threshold). Two codes for one condition risks double-firing on genuinely thin pages. Consider merging into one graded check. Score fine.

---

### CONTENT_UNSTRUCTURED — (3, 2) → 26 (Heuristic)

**Assessment:** Impact 3 is reasonable. No heading structure on a long page makes AI extraction harder. Heuristic confidence, moderate impact. Keep.

**Recommendation:** KEEP AS-IS (3, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 2). This is a well-motivated heuristic (flat wall-of-text is genuinely hard to chunk) and correctly scoped to *long* pages. Fine.

---

### CONTENT_IMAGE_HEAVY — (2, 3) → 14 (Heuristic)

**Assessment:** Impact 2 is reasonable. Image-heavy pages (more images than text sections) are harder for AI to extract, but this is a heuristic observation. Effort 3 is too high — adding text alongside images is content work, effort 1-2.

**Recommendation:** KEEP impact 2, LOWER effort from 3 to 2. (2, 2) → 16

> **◆ CLAUDE — Confidence: Medium**
> Agree, (2, 2). Low-stakes, and prone to false positives on legitimately visual pages (galleries, event photos). Correct at the low end.

---

## Citation & Attribution

### CITATIONS_MISSING_SUBSTANTIAL_CONTENT — (3, 2) → 26 (Reasonable proxy)

**Assessment:** Impact 3 is reasonable. Pages with 200+ words but no citations are harder for AI to verify and cite authoritatively. This is a content quality signal. Keep.

**Recommendation:** KEEP AS-IS (3, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 2), but note the domain fit: not every 200-word page needs citations (a service description, a bio). This should fire on *claim-bearing* content (research summaries, Bowen Theory explainers), not all substantial pages, or it'll nag pages that legitimately have nothing to cite. Score fine; targeting matters.

---

### CITATIONS_ORPHANED — (2, 1) → 18 (Heuristic)

**Assessment:** Impact 2 is reasonable. Citations without surrounding context are less useful, but this is a minor content quality concern. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (2, 1). Minor. Fine.

---

### CITATIONS_SOURCES_INACCESSIBLE — (4, 3) → 34 (Heuristic)

**Assessment:** Impact 4 is reasonable. Broken citation sources undermine the page's claims. For AI citation engines, a page citing broken sources is less quotable. However, effort 3 is too high — fixing a link is a trivial content-edit task, effort 1.

**Recommendation:** KEEP impact 4, LOWER effort from 3 to 1. (4, 1) → 38

> **◆ CLAUDE — Confidence: Medium**
> Agree, (4, 1). This is essentially BROKEN_LINK applied to citation/reference links — arguably it should inherit the broken-link detection rather than exist separately. If it's a distinct code, make sure a broken reference link isn't counted twice (once here, once as BROKEN_LINK_404). Score fine.

---

## Part 4 Summary — Claude deltas vs Hermes

| Code | Hermes proposed | Claude | Why |
|------|-----------------|--------|-----|
| **AI_BOT_USER_FETCH_BLOCKED** | (4, 1) → **2** | **keep 4** (or 3) | Premise false: Claude-User honors robots.txt; block is *effective* and costly, not a no-op |
| LLMS_TXT_MISSING | (3, 1) | (2–3, 1) | Agree low, but fix attribution (Jeremy Howard/Answer.AI) + "Anthropic/Perplexity signaled support" |
| SEMANTIC_DENSITY_LOW | (3, 3) | deprecate → use AI_MAIN_CONTENT_LOW_RATIO | Text-to-HTML ratio is meaningless on Elementor markup |
| AI_BOT_SEARCH_BLOCKED | keep (8, 1) | keep (8, 1) + fix taxonomy | Must key on *search* bots (OAI-SearchBot/Claude-SearchBot), not training bots (GPTBot/ClaudeBot) |
| JSON_LD_MISSING | keep (7, 2) | keep (7, 2), split confidence | Established for rich results; Reasonable-proxy for AI citation |

All other Part 4 items: **agree with Hermes.** Overlap/dedup flags logged for the thin-content pair, the "not-in-text" cluster, SEMANTIC_DENSITY vs MAIN_CONTENT_LOW_RATIO, and CITATIONS_SOURCES_INACCESSIBLE vs BROKEN_LINK.
