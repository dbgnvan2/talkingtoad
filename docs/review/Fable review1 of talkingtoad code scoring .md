Fable review1 of talkingtoad code scoring 

Architected comprehensive SEO scoring framework with confidence-effect matrix
Architected comprehensive SEO scoring framework with confidence-effect matrix
Executing as specified. Where a code's detection logic is ambiguous from its name alone, I've assigned deliberately and flagged it in the rationale and in section 4; those judgments carry Low confidence.

1. Methodology (~390 words)
Recommendation: Model B synthesis. Model A conflates two independent questions — is the effect real? and how big is it? — so a vendor-documented triviality (e.g., a deprecated bot token) could score higher than a measured-but-unconfirmed GEO effect. Model B's risk is false precision: effect sizes for Heuristic checks are themselves guesses, so multiplying two uncertain numbers manufactures authority. Mitigation: low caps on the Heuristic rows so guessed effect sizes can't inflate scores.

Derivation matrix (confidence × effect_size → impact):

small	moderate	large	fatal
Established	2	6	9	10
Reasonable proxy	2	4	7	—
Heuristic-measured	2	4	5	—
Heuristic	1	2	3	—
Effect-size scale: small = marginal, cosmetic, or indirect; moderate = measurable effect on ranking, extraction, or citation probability for a typical page; large = can substantially suppress the page on one or more engines; fatal = page effectively invisible or unreachable (Established only). none = informational observation, derived impact 0.

Exception lane = "Heuristic-measured": no vendor confirmation but ≥1 controlled study (Aggarwal et al. GEO methods; retrieval position-bias literature). Scored one row above plain Heuristic, capped at 5 — a single narrow study cannot justify Reasonable-proxy-large (7). Vendor-neutralized checks (e.g., noopener) drop to 0 regardless of matrix.

Severity: should NOT feed the score independently — impact already encodes it; adding severity double-counts. Derive severity from derived impact (critical ≥8, warning 3–7, info ≤2) for display consistency.

Page formula: the additive uncapped model has two defects: (a) correlated/overlapping codes stack one underlying defect multiple times; (b) accumulation of trivia can equal a fatal issue. Fixes: (1) count each code once per page; (2) cap total deduction per category at 30; (3) fatal gate — any impact-10 issue caps Page Health at 40. Under this, ten impact-4 issues in one category → 70; a noindexed page → ≤40. Criticals now dominate, as they should. Also merge the overlapping code families flagged in the table (schema trio, thin-content pair, answer-first trio, JS-rendering pair, placeholder pair, canonical pair).

Priority ordering: yes, effort should weigh more for non-technical owners. Proposed: priority_rank = derived_impact×10 − effort×8 (effort swings 40 vs impact's 100 — reorders within impact bands, never lifts trivia above criticals), plus a pinned "Quick wins" section: impact ≥4 AND effort ≤1.

changed = derived_impact ≠ current_impact. Tier relabels with unchanged impact are noted in rationale.

2. Full table (151 rows)
csv
code,recommended_confidence,recommended_effect_size,derived_impact,current_impact,changed,rationale
AI_BOT_BLANKET_DISALLOW,Established,large,9,9,no,Documented compliance; removes site from AI search
AI_BOT_DEPRECATED_DIRECTIVE,Established,small,2,2,no,Stale token; negligible effect
AI_BOT_NO_AI_DIRECTIVES,Heuristic,small,1,1,no,Default-allow suffices; relabel Heuristic
AI_BOT_SEARCH_BLOCKED,Established,large,9,8,yes,Citation-critical index bots; documented compliance
AI_BOT_TABLE_STALE,Heuristic,none,0,0,no,Tool maintenance flag; informational
AI_BOT_TRAINING_DISALLOWED,Established,none,0,0,no,Owner policy choice; informational
AI_BOT_USER_FETCH_BLOCKED,Established,moderate,6,4,yes,Live-fetch citations lost; only compliant vendors bite
AI_CITED_PAGE,Established,none,0,0,no,Positive observation; informational
AI_CONTENT_NOT_IN_TEXT,Reasonable proxy,moderate,4,4,no,Extractability consensus
AI_HIGH_VALUE_UNCITED,Reasonable proxy,none,0,4,yes,Outcome not defect; causes scored elsewhere
AI_MAIN_CONTENT_LOW_RATIO,Heuristic,moderate,2,2,no,Boilerplate-ratio heuristic
AI_NO_VISUAL_COMPANION,Heuristic,small,1,1,no,No citation evidence; relabel Heuristic
AI_PREVIEW_BLOCKED_AT_BOT,Established,moderate,6,3,yes,Snippet controls gate AI Overview eligibility
AI_PREVIEW_SUPPRESSED,Established,moderate,6,3,yes,Same documented snippet-control mechanism
AI_TXT_MISSING,Heuristic,small,1,1,no,Negligible adoption; no vendor support
AMPHTML_BROKEN,Reasonable proxy,small,2,4,yes,AMP legacy; minor crawl waste
ANCHOR_TEXT_GENERIC,Reasonable proxy,moderate,4,4,no,Anchor relevance consensus
AUTHOR_BYLINE_MISSING,Reasonable proxy,moderate,4,4,no,EEAT proxy
BLOG_SECTIONS_MISSING,Heuristic,moderate,2,5,yes,Best practice only; no vendor evidence
BROKEN_LINK_404,Reasonable proxy,moderate,4,10,yes,Google denies ranking factor; UX/crawl harm only
BROKEN_LINK_410,Reasonable proxy,moderate,4,8,yes,Same indirect harm as 404
BROKEN_LINK_503,Reasonable proxy,small,2,4,yes,Transient; retest before penalizing
BROKEN_LINK_5XX,Reasonable proxy,small,2,7,yes,Often transient; defect lives on target page
CANONICAL_EXTERNAL,Established,moderate,6,5,yes,Cedes indexing if unintended; verify intent
CANONICAL_MISSING,Reasonable proxy,moderate,4,6,yes,Canonical is a hint; Google self-selects
CANONICAL_SELF_MISSING,Reasonable proxy,small,2,5,yes,Overlaps CANONICAL_MISSING; merge
CENTRAL_CLAIM_BURIED,Heuristic-measured,moderate,4,5,yes,Answer position has measured retrieval support
CHUNKS_NOT_SELF_CONTAINED,Heuristic-measured,moderate,4,5,yes,Chunk retrieval documented; threshold heuristic
CITATIONS_MISSING_SUBSTANTIAL_CONTENT,Heuristic-measured,moderate,4,3,yes,Aggarwal measured cite-sources lift; narrow basis
CITATIONS_ORPHANED,Heuristic,small,1,2,yes,Formatting nit
CITATIONS_SOURCES_INACCESSIBLE,Heuristic,moderate,2,4,yes,Indirect trust signal only
CODE_BLOCK_MISSING_TECHNICAL,Heuristic,moderate,2,4,yes,Rarely applies to nonprofit content
COMPARISON_TABLE_MISSING,Heuristic,moderate,2,3,yes,Format preference; weak evidence
CONTACT_INFO_NOT_IN_HTML,Reasonable proxy,moderate,4,4,no,Local NAP consensus; relabel Reasonable proxy
CONTENT_CLOAKING_DETECTED,Established,large,9,8,yes,Documented spam policy; penalty exposure
CONTENT_DATE_STALE_VISIBLE,Reasonable proxy,moderate,4,4,no,Freshness query-dependent
CONTENT_IMAGE_HEAVY,Heuristic,moderate,2,2,no,Extractability heuristic
CONTENT_NOT_EXTRACTABLE_NO_TEXT,Established,large,9,6,yes,No machine-readable text defeats every engine
CONTENT_STALE,Reasonable proxy,small,2,3,yes,Evergreen pages unaffected; query-dependent
CONTENT_STAT_OUTDATED,Heuristic,moderate,2,2,no,Minor trust heuristic
CONTENT_THIN,Reasonable proxy,moderate,4,4,no,Duplicate of THIN_CONTENT; merge codes
CONTENT_UNSTRUCTURED,Heuristic,moderate,2,3,yes,Structure heuristic
CONVERSATIONAL_H2_MISSING,Heuristic,moderate,2,4,yes,Question headings unproven
DATE_MODIFIED_MISSING,Reasonable proxy,small,2,2,no,Single compensable signal
DATE_PUBLISHED_MISSING,Reasonable proxy,small,2,3,yes,Single compensable signal
DOCUMENT_PROPS_MISSING,Reasonable proxy,small,2,4,yes,Definition unclear; metadata minor; low confidence
EXTERNAL_CITATIONS_LOW,Heuristic-measured,moderate,4,5,yes,GEO study basis; narrow evidence
EXTERNAL_LINK_SKIPPED,Heuristic,none,0,2,yes,Crawl status note; informational
EXTERNAL_LINK_TIMEOUT,Heuristic,small,1,3,yes,Tool-side transient
FAQ_SCHEMA_MISSING,Established,small,2,2,no,Rich result removed 2026-05-07; comprehension residual only
FAVICON_MISSING,Established,small,2,3,yes,SERP cosmetic only
FIRST_VIEWPORT_NO_ANSWER,Heuristic,moderate,2,5,yes,Overlaps CENTRAL_CLAIM_BURIED; deduplicate
GEO_SUMMARY_BURIED,Heuristic,moderate,2,5,yes,Overlaps answer-position checks; deduplicate
H1_MISSING,Reasonable proxy,moderate,4,6,yes,Google tolerates; extraction and a11y value remains
H1_MULTIPLE,Established,small,2,5,yes,Google documented non-issue
HEADING_EMPTY,Reasonable proxy,small,2,4,yes,Markup noise; minor
HEADING_SKIP,Heuristic,moderate,2,4,yes,Google ignores order; a11y/chunking only
HIGH_CRAWL_DEPTH,Reasonable proxy,moderate,4,5,yes,Architecture consensus
HTTPS_REDIRECT_MISSING,Established,moderate,6,9,yes,Canonical split; HTTPS itself present
HTTP_PAGE,Established,large,9,9,no,Browser warnings; documented signal; donation trust
IMG_ALT_DUP_FILENAME,Reasonable proxy,small,2,3,yes,Poor alt quality; minor
IMG_ALT_GENERIC,Reasonable proxy,small,2,4,yes,Poor alt quality; minor
IMG_ALT_MISSING,Reasonable proxy,moderate,4,5,yes,Image search plus a11y plus AI description
IMG_ALT_MISUSED,Reasonable proxy,small,2,3,yes,Minor misuse
IMG_ALT_TOO_LONG,Heuristic,small,1,2,yes,Cosmetic
IMG_ALT_TOO_SHORT,Heuristic,small,1,3,yes,Cosmetic
IMG_BROKEN,Reasonable proxy,moderate,4,8,yes,UX and content loss; not ranking-critical
IMG_DUPLICATE_CONTENT,Heuristic,small,1,2,yes,Trivial
IMG_FORMAT_LEGACY,Reasonable proxy,small,2,2,no,CWV proxy; tiebreaker weight
IMG_NO_SRCSET,Reasonable proxy,small,2,2,no,Performance proxy
IMG_OVERSCALED,Reasonable proxy,small,2,4,yes,Wasted bytes; performance proxy
IMG_OVERSIZED,Reasonable proxy,moderate,4,5,yes,Common LCP driver on WordPress
IMG_POOR_COMPRESSION,Reasonable proxy,small,2,4,yes,Overlaps IMG_OVERSIZED; deduplicate
IMG_SLOW_LOAD,Reasonable proxy,moderate,4,4,no,Measured slowness
INTERACTIVE_NO_ACCESSIBLE_NAME,Heuristic,moderate,2,4,yes,A11y not ranking; keep advisory
INTERNAL_NOFOLLOW,Established,moderate,6,5,yes,Nofollow evaporates PageRank; documented
INTERNAL_REDIRECT_301,Established,small,2,4,yes,301 passes equity; crawl waste only
JSON_LD_INVALID,Reasonable proxy,moderate,4,4,no,Ignored markup equals missing schema
JSON_LD_MISSING,Reasonable proxy,moderate,4,7,yes,Overlaps schema codes; merge; moderate value
JS_DEPENDENT_NAVIGATION,Established,moderate,6,5,yes,Non-anchor links invisible to crawlers
JS_RENDERED_CONTENT_DIFFERS,Established,moderate,6,6,no,AI crawlers skip JS; relabel Established
LANDMARK_MAIN_MISSING,Reasonable proxy,small,2,2,no,Extraction aid
LANDMARK_NAV_MISSING,Reasonable proxy,small,2,2,no,Boilerplate identification aid
LANG_MISSING,Established,small,2,6,yes,Google ignores lang attribute; a11y only
LINK_EMPTY_ANCHOR,Reasonable proxy,small,2,7,yes,Lost anchor signal; not severe
LINK_PROFILE_PROMOTIONAL,Heuristic,moderate,2,4,yes,Style heuristic
LLMS_TXT_INVALID,Heuristic,small,1,2,yes,Unsupported file; validity moot
LLMS_TXT_MISSING,Heuristic,small,1,3,yes,No measured lift; Google declined support
LOGIN_REDIRECT,Established,small,2,2,no,Often intentional gating; verify intent
META_DESC_DUPLICATE,Established,small,2,4,yes,Google rewrites most descriptions
META_DESC_MISSING,Reasonable proxy,moderate,4,7,yes,CTR only; snippet auto-generated
META_DESC_TOO_LONG,Reasonable proxy,small,2,3,yes,Truncation cosmetic
META_DESC_TOO_SHORT,Reasonable proxy,small,2,4,yes,Minor
META_REFRESH_REDIRECT,Reasonable proxy,moderate,4,5,yes,Works but discouraged; slow
MISSING_HSTS,Reasonable proxy,small,2,4,yes,Security hardening; negligible SEO effect
MISSING_VIEWPORT_META,Established,moderate,6,6,no,Mobile-first indexing documented
MIXED_CONTENT,Established,moderate,6,6,no,Browser blocking documented
NOINDEX_HEADER,Established,fatal,10,10,no,Page-fatal if unintended; verify intent
NOINDEX_META,Established,fatal,10,10,no,Page-fatal if unintended; verify intent
NON_SEMANTIC_BUTTON,Heuristic,small,1,4,yes,A11y only; not crawl-relevant
NOT_IN_SITEMAP,Established,small,2,4,yes,Sitemap is a hint; links suffice
OG_DESC_MISSING,Reasonable proxy,small,2,3,yes,Social preview only
OG_IMAGE_MISSING,Reasonable proxy,small,2,3,yes,Social preview only
OG_TITLE_MISSING,Reasonable proxy,small,2,4,yes,Falls back to title tag
ORPHAN_CLAIM_TECHNICAL,Heuristic,moderate,2,6,yes,Definition unclear; heuristic; low confidence
ORPHAN_PAGE,Established,moderate,6,6,no,Discovery and equity documented
PAGE_SIZE_LARGE,Reasonable proxy,moderate,4,5,yes,Performance proxy
PAGE_TIMEOUT,Established,moderate,6,6,no,Escalate to large if persistent
PAGINATION_LINKS_PRESENT,Heuristic,small,1,2,yes,rel prev/next ignored since 2019
PARA_TOO_LONG,Heuristic,moderate,2,4,yes,Readability and chunking heuristic
PDF_TOO_LARGE,Heuristic,moderate,2,4,yes,Fetch cost heuristic
PLACEHOLDER_LINK,Reasonable proxy,small,2,7,yes,Dead href; UX not ranking
PROMOTIONAL_CONTENT_INTERRUPTS,Heuristic,moderate,2,3,yes,UX heuristic
QUERY_COVERAGE_WEAK,Heuristic,moderate,2,5,yes,Definition unclear; heuristic; low confidence
QUOTATIONS_MISSING,Heuristic-measured,moderate,4,4,no,Aggarwal measured quotation lift; narrow basis
RAW_HTML_JS_DEPENDENT,Established,moderate,6,6,no,AI crawlers skip JS; Google renders
REDIRECT_301,Reasonable proxy,small,2,3,yes,Normal plumbing; passes equity
REDIRECT_302,Established,small,2,4,yes,Passes PageRank; canonical ambiguity only
REDIRECT_CASE_NORMALISE,Heuristic,small,1,2,yes,Normalization working as intended
REDIRECT_CHAIN,Established,moderate,6,6,no,Hop limits documented; latency
REDIRECT_LOOP,Established,fatal,10,10,no,Page unreachable
REDIRECT_TRAILING_SLASH,Heuristic,small,1,2,yes,Normalization working as intended
ROBOTS_BLOCKED,Established,large,9,9,no,Uncrawlable; URL-only indexing
SCHEMA_DEPRECATED_TYPE,Established,small,2,2,no,Deprecations documented; markup harmless
SCHEMA_MISSING,Reasonable proxy,moderate,4,5,yes,Merge schema trio; one deduction
SCHEMA_ORG_MISSING,Reasonable proxy,moderate,4,5,yes,Merge schema trio; one deduction
SCHEMA_TYPE_CONFLICT,Reasonable proxy,small,2,3,yes,Entity confusion minor
SCHEMA_TYPE_MISMATCH,Reasonable proxy,moderate,4,4,no,Wrong type loses eligibility
SCHEMA_VISIBLE_MISMATCH,Established,moderate,6,5,yes,Documented spam-policy exposure
SECTION_CROSS_REFERENCES,Heuristic,moderate,2,6,yes,Overlaps chunk check; deduplicate
SECTION_VAGUE_OPENER,Heuristic,moderate,2,5,yes,Style heuristic
SEMANTIC_DENSITY_LOW,Heuristic,moderate,2,3,yes,Weak heuristic
SITEMAP_MISSING,Established,small,2,6,yes,Small linked sites rarely need one per Google
STATISTICS_COUNT_LOW,Heuristic-measured,moderate,4,5,yes,Aggarwal measured statistics lift; narrow basis
STRUCTURED_ELEMENTS_LOW,Heuristic,moderate,2,3,yes,Format heuristic
THIN_CONTENT,Reasonable proxy,moderate,4,6,yes,Duplicate of CONTENT_THIN; merge
TITLE_DUPLICATE,Established,moderate,6,5,yes,Unique titles documented
TITLE_H1_MISMATCH,Heuristic,small,1,6,yes,Google tolerates mismatch; rewrite risk only
TITLE_META_DUPLICATE_PAIR,Reasonable proxy,moderate,4,6,yes,Overlaps title/desc duplicate codes; deduplicate
TITLE_MISSING,Established,large,9,9,no,Documented ranking element
TITLE_TOO_LONG,Established,small,2,4,yes,Truncation and rewrite only
TITLE_TOO_SHORT,Reasonable proxy,small,2,5,yes,Wasted signal; minor
TWITTER_CARD_MISSING,Heuristic,small,1,3,yes,Falls back to OpenGraph
UA_CONTENT_DIFFERS,Reasonable proxy,large,7,7,no,Cloaking-adjacent; may be benign
UNSAFE_CROSS_ORIGIN_LINK,Established,none,0,3,yes,Browsers imply noopener since 2021; retire check
URL_HAS_SPACES,Reasonable proxy,small,2,5,yes,Encoded spaces handled fine
URL_HAS_UNDERSCORES,Established,small,2,2,no,Documented tiny joiner effect
URL_TOO_LONG,Heuristic,small,1,2,yes,No practical effect
URL_UPPERCASE,Reasonable proxy,small,2,3,yes,Duplicate risk minor
WRONG_PLACEHOLDER_LINK,Reasonable proxy,small,2,7,yes,Dead href; UX not ranking
WWW_CANONICALIZATION,Established,moderate,6,5,yes,Host split; canonical ambiguity
3. Top 20 most-consequential changes
BROKEN_LINK_404: 10 → 4 (High). Impact 10 puts a single broken outbound link on par with noindex. Google has repeatedly stated broken links are not a ranking factor; the real harms (UX, crawl waste, internal equity paths) are indirect and moderate.
TITLE_H1_MISMATCH: 6 → 1 (High). Google explicitly does not require title/H1 agreement; the only real consequence is possible title rewriting in SERPs. Current 6 penalizes a documented non-issue heavily.
LANG_MISSING: 6 → 2 (High). Google has stated it ignores the lang attribute and detects language itself. Residual value is accessibility and possibly non-Google consumers — small.
H1_MULTIPLE: 5 → 2 (High). Vendor-documented non-issue for ranking; HTML5-valid. Retained at 2 only for structure/extraction hygiene.
LINK_EMPTY_ANCHOR: 7 → 2 (Medium-High). An empty anchor loses one link's signal and is an accessibility issue; nothing supports near-critical weighting.
PLACEHOLDER_LINK & WRONG_PLACEHOLDER_LINK: 7 → 2 each (Medium). Dead hrefs are UX defects and crawl dead-ends, not ranking events. At 7, three placeholder links cost more than serving the page over HTTP would.
META_DESC_MISSING: 7 → 4 (High). Not a ranking factor (vendor-stated); Google auto-generates and rewrites the majority of descriptions anyway. CTR effect is real but moderate.
JSON_LD_MISSING: 7 → 4, plus merging the schema trio (Medium-High). JSON_LD_MISSING, SCHEMA_ORG_MISSING, and SCHEMA_MISSING describe the same absence; a schema-less page currently loses up to 17 points for one defect. One code at 4 is defensible; three stacked codes are not.
HTTPS_REDIRECT_MISSING: 9 → 6 (Medium). If HTTPS exists but HTTP doesn't redirect, the failure is canonicalization/duplication — serious but categorically less than serving pages over HTTP (which correctly stays 9).
CONTENT_NOT_EXTRACTABLE_NO_TEXT: 6 → 9 (Medium). A page with no machine-readable text is invisible to AI crawlers and severely degraded for Google. This is one of the few upward corrections and belongs near the fatal band.
AI_PREVIEW_BLOCKED_AT_BOT / AI_PREVIEW_SUPPRESSED: 3 → 6 each (Medium). Google documents that snippet controls govern AI Overview eligibility; suppressing previews now gates a major surface. Current 3 predates that reality. Confidence Medium because I inferred the checks' exact semantics from their names.
AI_BOT_SEARCH_BLOCKED: 8 → 9; AI_BOT_USER_FETCH_BLOCKED: 4 → 6 (Medium). Blocking AI search-index bots removes citation eligibility on compliant engines — matrix-large. User-fetch upgrade reflects growth of live retrieval, discounted because only compliant vendors (notably Anthropic) actually honor the block; Perplexity-User ignores it, ChatGPT-User may.
CONTENT_CLOAKING_DETECTED: 8 → 9, Reasonable proxy → Established (High). Cloaking is a documented Google spam-policy violation with manual-action exposure; it warrants Established-large.
IMG_BROKEN: 8 → 4 (Medium). Broken images are content/UX loss, not a near-critical ranking event.
BROKEN_LINK_410: 8 → 4; BROKEN_LINK_5XX: 7 → 2 (Medium-High). Same logic as #1; 5xx targets are frequently transient and the defect belongs to the target page, not the linking page.
SITEMAP_MISSING: 6 → 2 (Medium). Google documents that small, well-linked sites generally don't need a sitemap — and small nonprofit sites are exactly this tool's audience. Effort 2 (really 1 with any WP SEO plugin) keeps it surfaced as a quick win.
UNSAFE_CROSS_ORIGIN_LINK: 3 → 0, retire (High). Browsers have implied noopener on target="_blank" since ~2021; the vulnerability the check guards against is neutralized. Scoring neutralized issues erodes exactly the trust the tool is built for.
LLMS_TXT_MISSING: 3 → 1; LLMS_TXT_INVALID: 2 → 1 (High). No measured citation lift, ~5–10% adoption, Google declined support. Anything above 1 is indefensible on current evidence; revisit if a vendor confirms consumption.
GEO-heuristic deflation family: SECTION_CROSS_REFERENCES 6→2, ORPHAN_CLAIM_TECHNICAL 6→2, QUERY_COVERAGE_WEAK 5→2, BLOG_SECTIONS_MISSING 5→2, SECTION_VAGUE_OPENER 5→2, FIRST_VIEWPORT_NO_ANSWER 5→2, GEO_SUMMARY_BURIED 5→2, CONVERSATIONAL_H2_MISSING 4→2 (High on principle, Low-Medium on individual semantics). These unconfirmed heuristics currently outscore documented issues; collectively they could sink a well-built page's health by 40+ points on pure conjecture. The three answer-position checks additionally triple-count one concept — I kept CENTRAL_CLAIM_BURIED at 4 (measured exception lane) and demoted the overlapping two.
AI_HIGH_VALUE_UNCITED: 4 → 0 (Medium-High). Not being cited is an outcome, not a page defect; its causes (extractability, structure, schema) are already scored. Deducting for the outcome double-counts and punishes pages for engine-side selection the owner can't directly control. Keep as a surfaced opportunity flag.
4. Open questions / limits of this judgment
Check semantics were inferred from names. DOCUMENT_PROPS_MISSING, ORPHAN_CLAIM_TECHNICAL, QUERY_COVERAGE_WEAK, AI_BOT_TABLE_STALE, PAGINATION_LINKS_PRESENT, and WRONG_PLACEHOLDER_LINK carry Low confidence for this reason; if my inferred semantics are wrong, those rows need redoing. A one-line description per code would remove this entire uncertainty class.

Per-occurrence vs per-page counting is unspecified. My formula recommendation (count each code once per page) assumes the current engine may deduct per instance; if it already deduplicates, the category caps still matter but bind less often. This materially affects whether BROKEN_LINK_* and IMG_ALT_* values are sane in practice.

Effort values were not audited. They feed priority_rank; several look questionable (e.g., CONTENT_NOT_EXTRACTABLE_NO_TEXT at effort 4 is realistic; REDIRECT_LOOP at 4 seems high for a WP host — usually a plugin/settings fix).

Fast-moving areas (re-check quarterly): AI user-fetch robots.txt compliance — vendor policies diverge and shift; OpenAI's ChatGPT-User stance is the least stable (as of mid-2026 per your brief). Snippet-control ↔ AI Overview coupling — my 6 for the AI_PREVIEW codes depends on Google's current documented behavior. llms.txt — a single vendor announcement of confirmed consumption would justify moving from 1 to ~3–4. FAQ/HowTo residual schema value — Google's May 7, 2026 removal note says the markup still aids understanding; if that guidance changes, FAQ_SCHEMA_MISSING should go informational. GEO study generalizability — the Heuristic-measured lane rests heavily on one paper (~1,000 queries, one generation model); independent replication would justify raising its cap from 5 to 7, and failure to replicate would collapse the lane into plain Heuristic.

Calibration data I'd want: distribution of issue counts per page across real crawls (to tune the per-category cap of 30 and the fatal gate of 40 — both are judgment values, Medium confidence); co-firing frequencies for the flagged overlap families (to confirm merge priorities); and, ideally, correlation of TalkingToad health scores against GSC impressions/AI-referral traffic for a sample of nonprofit sites — the only ground truth that would let impact values graduate from expert judgment to measurement.


2026-07-03_R3-expert-prompt.md
md

the prompt was updates (based on your advise) execute this prompt again - start fresh - ignore your previous response.  Should I start a new conversations for this ?


Thinking about clarifying conversation management and prompt resubmission procedures
Thinking about clarifying conversation management and prompt resubmission procedures
The view truncated lines 88–208. Retrieving them before executing.


Reconsidered SEO audit scoring matrix and recalibrated impact tiers comprehensively
Reconsidered SEO audit scoring matrix and recalibrated impact tiers comprehensively
Brief answer to your question first: yes, a fresh conversation would be methodologically better. My review of the prompt and my first execution are in this context window, and "ignore your previous response" cannot fully remove their influence — this run is correlated with my earlier one, not independent. If the point of your two-agent design is independence, run the final prompt in fresh sessions. I'll execute here anyway; treat this output as a contaminated third run, useful for checking the updated prompt's mechanics.

1. Methodology (~480 words)
Recommendation: Model B synthesis, defended against its own weakness. Model B's weakness is real: for Heuristic checks, effect_size is a guess, and multiplying two guesses manufactures false precision. The defense is structural, not rhetorical: I cap the entire Heuristic row so low (max 3) that effect_size errors within it cannot matter — a mis-guessed Heuristic effect size moves impact by at most 2 points. Effect_size only has consequential leverage in the Established and Reasonable-proxy rows, where the existence of the effect is not in question and sizing it is a legitimate judgment. Model A is rejected because it cannot distinguish a vendor-documented triviality (deprecated bot token) from a vendor-documented catastrophe except by uncapped hand-setting below the ceiling — which is the inconsistency problem restated.

Derivation matrix (confidence × effect_size → impact):

small	moderate	large	fatal
Established	2	6	9	10
Reasonable proxy	2	4	7	—
Heuristic-measured (exception lane)	2	4	5	—
Heuristic	1	2	3	—
effect_size none → 0 (informational). Exception lane = Heuristic evidence plus ≥1 controlled study (Aggarwal et al. covers statistics, quotations, cite-sources, answer-position). Capped at 5: one narrow study cannot buy Reasonable-proxy-large (7).

10-tier: kept, redefined. 10 = page-fatal — the page is removed from or unreachable in search (NOINDEX_META, NOINDEX_HEADER, REDIRECT_LOOP). BROKEN_LINK_404 is expelled from this tier; a broken outbound link does not remove the source page from anything.

Interpretation of "large": gating across engines. Losing one AI engine's surface (e.g., one search bot disallowed) while Google and others remain = moderate, not large. This resolves what would otherwise be tier compression at the top.

Severity: should NOT feed the score. Impact already encodes severity; adding it double-counts one judgment. Current data proves severity is unreliable anyway (NOINDEX_META impact 10 carries severity "warning"; CANONICAL_SELF_MISSING is "info" at impact 5). Derive severity from derived impact: critical ≥8, warning 3–7, info ≤2.

Page formula: three defects. (1) The per-occurrence counting on BROKEN_LINK_/REDIRECT_ is the worst distortion — five 404s = −50, more damage than serving the page over HTTP. Fix: deduct each code once per page; display the occurrence count in the issue detail (the fix action — "review this page's links" — is one task regardless of count). (2) Overlap clusters stack one root cause 2–3× (section 3). Fix: suppression rules. (3) Trivia accumulation can equal a fatal issue. Fix: per-category deduction cap of 30, plus a fatal gate — any impact-10 issue caps Page Health at 40. Under this: ten impact-4 issues across categories ≥ 60; a noindexed page ≤ 40.

Priority ordering: yes, effort should weigh more. priority_rank = derived_impact×10 − effort×8 (effort swings 40 of impact's 100 — reorders within impact bands, never lifts trivia over criticals). Add a pinned "Quick wins" list (impact ≥4 AND effort ≤1) and a "verify intent" flag on NOINDEX_*, LOGIN_REDIRECT, CANONICAL_EXTERNAL, AI_BOT_TRAINING_DISALLOWED — for this audience, "confirm this is deliberate" is different advice from "fix this."

2. Full table (151 rows)
csv
code,current_confidence,recommended_confidence,recommended_effect_size,derived_impact,current_impact,impact_changed,confidence_changed,reviewer_confidence,rationale
AI_BOT_BLANKET_DISALLOW,Established,Established,large,9,9,no,no,H,Blocks all engines; site invisible
AI_BOT_DEPRECATED_DIRECTIVE,Established,Established,small,2,2,no,no,H,Stale token; cosmetic robots.txt hygiene
AI_BOT_NO_AI_DIRECTIVES,Reasonable proxy,Heuristic,small,1,1,no,yes,M,Default-allow suffices; no evidence explicit directives help
AI_BOT_SEARCH_BLOCKED,Established,Established,moderate,6,8,yes,no,M,Gates one engine's citations; Google unaffected
AI_BOT_TABLE_STALE,Heuristic,Heuristic,none,0,0,no,no,H,Informational by design; tool maintenance flag
AI_BOT_TRAINING_DISALLOWED,Established,Established,none,0,0,no,no,H,Informational by design; legitimate owner choice
AI_BOT_USER_FETCH_BLOCKED,Established,Established,small,2,4,yes,no,M,Narrow surface; only compliant vendors honor block
AI_CITED_PAGE,Established,Established,none,0,0,no,no,H,Informational by design; positive finding
AI_CONTENT_NOT_IN_TEXT,Reasonable proxy,Reasonable proxy,moderate,4,4,no,no,H,Non-text content invisible to extraction
AI_HIGH_VALUE_UNCITED,Reasonable proxy,Reasonable proxy,none,0,4,yes,no,M,Outcome not defect; causes scored elsewhere
AI_MAIN_CONTENT_LOW_RATIO,Heuristic,Heuristic,moderate,2,2,no,no,M,Boilerplate-ratio heuristic; plausible extraction effect
AI_NO_VISUAL_COMPANION,Reasonable proxy,Heuristic,small,1,1,no,yes,M,No citation evidence visuals required
AI_PREVIEW_BLOCKED_AT_BOT,Established,Established,moderate,6,3,yes,no,M,Header gates that crawler; documented mechanism
AI_PREVIEW_SUPPRESSED,Established,Established,moderate,6,3,yes,no,M,Snippet controls gate AI Overview eligibility
AI_TXT_MISSING,Heuristic,Heuristic,small,1,1,no,no,H,Near-zero adoption; no vendor support
AMPHTML_BROKEN,—,Reasonable proxy,small,2,4,yes,yes,M,AMP no longer required; crawl waste only
ANCHOR_TEXT_GENERIC,—,Reasonable proxy,moderate,4,4,no,yes,H,Anchor relevance consensus; a11y overlap
AUTHOR_BYLINE_MISSING,Reasonable proxy,Reasonable proxy,moderate,4,4,no,no,M,EEAT proxy; consensus not vendor-confirmed
BLOG_SECTIONS_MISSING,Heuristic,Heuristic,moderate,2,5,yes,no,M,Citation-anchor theory unproven
BROKEN_LINK_404,—,Reasonable proxy,moderate,4,10,yes,yes,H,Not a ranking factor per Google; UX harm
BROKEN_LINK_410,—,Reasonable proxy,moderate,4,8,yes,yes,H,Same indirect harm as 404
BROKEN_LINK_503,—,Reasonable proxy,small,2,4,yes,yes,H,Transient; retest before penalizing
BROKEN_LINK_5XX,—,Reasonable proxy,small,2,7,yes,yes,M,Often transient; defect belongs to target
CANONICAL_EXTERNAL,—,Established,moderate,6,5,yes,yes,M,Cedes indexing if unintended; verify intent
CANONICAL_MISSING,—,Reasonable proxy,moderate,4,6,yes,yes,H,Real duplication risk; canonical is a hint
CANONICAL_SELF_MISSING,—,Reasonable proxy,small,2,5,yes,yes,H,Advisory; Google self-selects canonical fine
CENTRAL_CLAIM_BURIED,Heuristic,Heuristic-measured,moderate,4,5,yes,yes,M,Answer-position measured in GEO study
CHUNKS_NOT_SELF_CONTAINED,Heuristic,Heuristic-measured,moderate,4,5,yes,yes,M,Chunk retrieval documented; threshold is guess
CITATIONS_MISSING_SUBSTANTIAL_CONTENT,Reasonable proxy,Heuristic-measured,moderate,4,3,yes,yes,M,One study measured cite-sources lift
CITATIONS_ORPHANED,Heuristic,Heuristic,small,1,2,yes,no,L,Formatting nit; semantics thin
CITATIONS_SOURCES_INACCESSIBLE,Heuristic,Heuristic,moderate,2,4,yes,no,M,Indirect trust signal only
CODE_BLOCK_MISSING_TECHNICAL,Heuristic,Heuristic,moderate,2,4,yes,no,M,Rarely applies to nonprofit content
COMPARISON_TABLE_MISSING,Heuristic,Heuristic,moderate,2,3,yes,no,L,Format preference; weak trigger heuristic
CONTACT_INFO_NOT_IN_HTML,Heuristic,Reasonable proxy,moderate,4,4,no,yes,M,Local NAP-in-HTML consensus is strong
CONTENT_CLOAKING_DETECTED,Reasonable proxy,Reasonable proxy,large,7,8,yes,no,M,Detection is proxy; real cloaking is penalty-grade
CONTENT_DATE_STALE_VISIBLE,Reasonable proxy,Reasonable proxy,moderate,4,4,no,no,M,Freshness query-dependent; AI engines prefer recent
CONTENT_IMAGE_HEAVY,Heuristic,Heuristic,moderate,2,2,no,no,M,Extraction heuristic
CONTENT_NOT_EXTRACTABLE_NO_TEXT,Reasonable proxy,Established,large,9,6,yes,yes,H,No text defeats every engine; documented
CONTENT_STALE,—,Heuristic,small,1,3,yes,yes,M,Evergreen pages unaffected; age alone weak
CONTENT_STAT_OUTDATED,Heuristic,Heuristic,small,1,2,yes,no,M,Year-mention heuristic; weak
CONTENT_THIN,Reasonable proxy,Reasonable proxy,moderate,4,4,no,no,H,Under-100-words real; cluster with THIN_CONTENT
CONTENT_UNSTRUCTURED,Heuristic,Heuristic,moderate,2,3,yes,no,M,Headings aid extraction; unproven magnitude
CONVERSATIONAL_H2_MISSING,Heuristic,Heuristic,small,1,4,yes,no,M,Interrogative headings unproven
DATE_MODIFIED_MISSING,Reasonable proxy,Reasonable proxy,small,2,2,no,no,H,Single compensable signal
DATE_PUBLISHED_MISSING,Reasonable proxy,Reasonable proxy,small,2,3,yes,no,H,Single compensable signal
DOCUMENT_PROPS_MISSING,Reasonable proxy,Reasonable proxy,small,2,4,yes,no,M,PDF metadata minor; title matters most
EXTERNAL_CITATIONS_LOW,Reasonable proxy,Heuristic-measured,moderate,4,5,yes,yes,M,GEO study basis; narrow evidence
EXTERNAL_LINK_SKIPPED,—,Heuristic,none,0,2,yes,yes,H,Crawl status note; not a defect
EXTERNAL_LINK_TIMEOUT,—,Heuristic,small,1,3,yes,yes,H,Tool-side transient; low signal
FAQ_SCHEMA_MISSING,Reasonable proxy,Established,small,2,2,no,yes,H,Rich result removed 2026-05-07; comprehension residual
FAVICON_MISSING,—,Established,small,2,3,yes,yes,H,SERP cosmetic only
FIRST_VIEWPORT_NO_ANSWER,Heuristic,Heuristic,moderate,2,5,yes,no,M,Overlaps CENTRAL_CLAIM_BURIED; suppress in cluster
GEO_SUMMARY_BURIED,Heuristic,Heuristic,moderate,2,5,yes,no,M,Section-level answer-first; unproven variant
H1_MISSING,—,Reasonable proxy,moderate,4,6,yes,yes,H,Google tolerant; extraction and a11y value
H1_MULTIPLE,—,Established,small,2,5,yes,yes,H,Google-documented non-issue
HEADING_EMPTY,—,Reasonable proxy,small,2,4,yes,yes,H,Markup noise; minor
HEADING_SKIP,—,Heuristic,moderate,2,4,yes,yes,H,Google ignores order; a11y and chunking only
HIGH_CRAWL_DEPTH,—,Reasonable proxy,moderate,4,5,yes,yes,M,Architecture consensus; matters less on small sites
HTTPS_REDIRECT_MISSING,—,Established,moderate,6,9,yes,yes,M,Canonical split; HTTPS itself exists
HTTP_PAGE,—,Established,large,9,9,no,yes,H,Browser warnings; documented signal; donor trust
IMG_ALT_DUP_FILENAME,—,Reasonable proxy,small,2,3,yes,yes,H,Poor alt quality; minor
IMG_ALT_GENERIC,—,Reasonable proxy,small,2,4,yes,yes,H,Poor alt quality; minor
IMG_ALT_MISSING,—,Reasonable proxy,moderate,4,5,yes,yes,H,Image search plus a11y plus AI description
IMG_ALT_MISUSED,—,Heuristic,small,1,3,yes,yes,M,Decorative alt text is trivial
IMG_ALT_TOO_LONG,—,Heuristic,small,1,2,yes,yes,H,Cosmetic threshold
IMG_ALT_TOO_SHORT,—,Heuristic,small,1,3,yes,yes,H,Cosmetic threshold
IMG_BROKEN,—,Reasonable proxy,moderate,4,8,yes,yes,H,Content and UX loss; not near-critical
IMG_DUPLICATE_CONTENT,—,Heuristic,small,1,2,yes,yes,M,Trivial; caching nuance only
IMG_FORMAT_LEGACY,—,Reasonable proxy,small,2,2,no,yes,H,CWV proxy; tiebreaker weight
IMG_NO_SRCSET,—,Reasonable proxy,small,2,2,no,yes,H,Performance proxy
IMG_OVERSCALED,—,Reasonable proxy,small,2,4,yes,yes,H,Wasted bandwidth; performance proxy
IMG_OVERSIZED,—,Reasonable proxy,moderate,4,5,yes,yes,H,Common WordPress LCP driver
IMG_POOR_COMPRESSION,—,Reasonable proxy,small,2,4,yes,yes,H,Overlaps IMG_OVERSIZED; suppress in cluster
IMG_SLOW_LOAD,—,Reasonable proxy,moderate,4,4,no,yes,H,Measured slowness; CWV-adjacent
INTERACTIVE_NO_ACCESSIBLE_NAME,—,Heuristic,moderate,2,4,yes,yes,M,A11y not ranking; keep advisory
INTERNAL_NOFOLLOW,—,Established,moderate,6,5,yes,yes,H,Nofollow evaporates PageRank; documented
INTERNAL_REDIRECT_301,—,Established,small,2,4,yes,yes,H,301 passes equity; crawl waste only
JSON_LD_INVALID,Reasonable proxy,Reasonable proxy,moderate,4,4,no,no,H,Invalid markup equals missing markup
JSON_LD_MISSING,Reasonable proxy,Reasonable proxy,moderate,4,7,yes,no,H,Merge with SCHEMA_MISSING; one deduction
JS_DEPENDENT_NAVIGATION,—,Established,moderate,6,5,yes,yes,H,Non-rendering bots cannot discover links
JS_RENDERED_CONTENT_DIFFERS,Reasonable proxy,Established,moderate,6,6,no,yes,M,AI bots skip JS; documented; AI Overviews exempt
LANDMARK_MAIN_MISSING,—,Reasonable proxy,small,2,2,no,yes,M,Main-content identification aid
LANDMARK_NAV_MISSING,—,Reasonable proxy,small,2,2,no,yes,M,Boilerplate identification aid
LANG_MISSING,—,Established,small,2,6,yes,yes,H,Google ignores lang attribute; a11y residual
LINK_EMPTY_ANCHOR,—,Reasonable proxy,small,2,7,yes,yes,H,One lost link signal; a11y issue
LINK_PROFILE_PROMOTIONAL,Heuristic,Heuristic,moderate,2,4,yes,no,M,Self-link ratio heuristic
LLMS_TXT_INVALID,Heuristic,Heuristic,small,1,2,yes,no,H,Unsupported file; validity moot
LLMS_TXT_MISSING,Heuristic,Heuristic,small,1,3,yes,no,H,No measured lift; Google declined
LOGIN_REDIRECT,—,Established,small,2,2,no,yes,H,Often intentional; verify intent
META_DESC_DUPLICATE,—,Established,small,2,4,yes,yes,H,Google rewrites most descriptions
META_DESC_MISSING,—,Reasonable proxy,moderate,4,7,yes,yes,H,CTR only; snippet auto-generated
META_DESC_TOO_LONG,—,Reasonable proxy,small,2,3,yes,yes,H,Truncation cosmetic
META_DESC_TOO_SHORT,—,Reasonable proxy,small,2,4,yes,yes,H,Minor; still functions
META_REFRESH_REDIRECT,—,Reasonable proxy,moderate,4,5,yes,yes,M,Works but discouraged; slow UX
MISSING_HSTS,—,Reasonable proxy,small,2,4,yes,yes,H,Security hardening; negligible SEO effect
MISSING_VIEWPORT_META,—,Established,moderate,6,6,no,yes,H,Mobile-first indexing documented
MIXED_CONTENT,—,Established,moderate,6,6,no,yes,H,Browser blocking documented
NOINDEX_HEADER,—,Established,fatal,10,10,no,yes,H,Page-fatal; verify intent first
NOINDEX_META,—,Established,fatal,10,10,no,yes,H,Page-fatal; verify intent first
NON_SEMANTIC_BUTTON,—,Heuristic,small,1,4,yes,yes,M,A11y only; not crawl-relevant
NOT_IN_SITEMAP,—,Established,small,2,4,yes,yes,H,Sitemap is a hint; links suffice
OG_DESC_MISSING,—,Reasonable proxy,small,2,3,yes,yes,H,Social preview only
OG_IMAGE_MISSING,—,Reasonable proxy,small,2,3,yes,yes,H,Social preview only
OG_TITLE_MISSING,—,Reasonable proxy,small,2,4,yes,yes,H,Falls back to title tag
ORPHAN_CLAIM_TECHNICAL,Heuristic,Heuristic-measured,moderate,4,6,yes,yes,M,Cite-sources measured; cluster with citation codes
ORPHAN_PAGE,—,Established,moderate,6,6,no,yes,H,Discovery and equity documented
PAGE_SIZE_LARGE,—,Reasonable proxy,moderate,4,5,yes,yes,M,Performance proxy; mobile-relevant
PAGE_TIMEOUT,—,Established,moderate,6,6,no,yes,H,Uncrawlable when persistent; retest transients
PAGINATION_LINKS_PRESENT,—,Established,none,0,2,yes,yes,H,rel prev/next ignored since 2019; harmless
PARA_TOO_LONG,—,Heuristic,moderate,2,4,yes,yes,M,Readability and chunking heuristic
PDF_TOO_LARGE,—,Heuristic,moderate,2,4,yes,yes,M,Fetch cost heuristic
PLACEHOLDER_LINK,—,Reasonable proxy,moderate,4,7,yes,yes,M,Dead CTA; UX-critical SEO-moderate
PROMOTIONAL_CONTENT_INTERRUPTS,Heuristic,Heuristic,small,1,3,yes,no,L,Style heuristic; classifier-dependent
QUERY_COVERAGE_WEAK,Heuristic,Heuristic,moderate,2,5,yes,no,M,Keyword-consistency heuristic
QUOTATIONS_MISSING,Heuristic,Heuristic-measured,moderate,4,4,no,yes,M,Quotation lift measured; narrow basis
RAW_HTML_JS_DEPENDENT,Reasonable proxy,Established,large,9,6,yes,yes,M,App shell gates non-rendering AI bots
REDIRECT_301,—,Established,small,2,3,yes,yes,H,Normal plumbing; passes equity
REDIRECT_302,—,Established,small,2,4,yes,yes,H,Passes PageRank; canonical ambiguity only
REDIRECT_CASE_NORMALISE,—,Heuristic,small,1,2,yes,yes,H,Server working as intended
REDIRECT_CHAIN,—,Established,moderate,6,6,no,yes,H,Hop limits and latency documented
REDIRECT_LOOP,—,Established,fatal,10,10,no,yes,H,Page unreachable
REDIRECT_TRAILING_SLASH,—,Heuristic,small,1,2,yes,yes,H,CMS working as intended
ROBOTS_BLOCKED,—,Established,large,9,9,no,yes,H,Uncrawlable; URL-only indexing remains
SCHEMA_DEPRECATED_TYPE,Reasonable proxy,Established,small,2,2,no,yes,H,Deprecations documented; markup harmless
SCHEMA_MISSING,—,Reasonable proxy,moderate,4,5,yes,yes,H,Merge with JSON_LD_MISSING; one deduction
SCHEMA_ORG_MISSING,Reasonable proxy,Reasonable proxy,moderate,4,5,yes,no,H,Homepage entity identification; knowledge panel input
SCHEMA_TYPE_CONFLICT,Reasonable proxy,Reasonable proxy,small,2,3,yes,no,M,Entity confusion minor
SCHEMA_TYPE_MISMATCH,Reasonable proxy,Reasonable proxy,moderate,4,4,no,no,M,Wrong type loses feature eligibility
SCHEMA_VISIBLE_MISMATCH,Established,Established,moderate,6,5,yes,no,H,Markup must match visible content; documented policy
SECTION_CROSS_REFERENCES,Heuristic,Heuristic,moderate,2,6,yes,no,M,One cause of non-self-contained chunks; cluster
SECTION_VAGUE_OPENER,Heuristic,Heuristic,moderate,2,5,yes,no,M,Style heuristic
SEMANTIC_DENSITY_LOW,Heuristic,Heuristic,small,1,3,yes,no,M,Text-to-HTML ratio weak proxy
SITEMAP_MISSING,—,Established,small,2,6,yes,yes,H,Small linked sites rarely need one
STATISTICS_COUNT_LOW,Heuristic,Heuristic-measured,moderate,4,5,yes,yes,M,Statistics lift measured; narrow basis
STRUCTURED_ELEMENTS_LOW,Heuristic,Heuristic,moderate,2,3,yes,no,M,Format heuristic
THIN_CONTENT,—,Reasonable proxy,moderate,4,6,yes,yes,H,Under-300-words; cluster with CONTENT_THIN
TITLE_DUPLICATE,—,Established,moderate,6,5,yes,yes,H,Unique titles documented guidance
TITLE_H1_MISMATCH,—,Heuristic,moderate,2,6,yes,yes,M,Google tolerates; rewrite risk only
TITLE_META_DUPLICATE_PAIR,—,Reasonable proxy,moderate,4,6,yes,yes,H,Always co-fires with children; suppress them
TITLE_MISSING,—,Established,large,9,9,no,yes,H,Documented ranking element absent
TITLE_TOO_LONG,—,Established,small,2,4,yes,yes,H,Truncation and rewrite only
TITLE_TOO_SHORT,—,Reasonable proxy,small,2,5,yes,yes,H,Wasted signal; minor
TWITTER_CARD_MISSING,—,Heuristic,small,1,3,yes,yes,H,Falls back to OpenGraph
UA_CONTENT_DIFFERS,Reasonable proxy,Reasonable proxy,large,7,7,no,no,M,AI bots served less; cloaking-adjacent
UNSAFE_CROSS_ORIGIN_LINK,—,Established,none,0,3,yes,yes,H,Browsers imply noopener since 2021; retire
URL_HAS_SPACES,—,Reasonable proxy,small,2,5,yes,yes,H,Encoded spaces handled fine; ugly only
URL_HAS_UNDERSCORES,—,Established,small,2,2,no,yes,H,Documented tiny word-joiner effect
URL_TOO_LONG,—,Heuristic,small,1,2,yes,yes,H,No practical effect at 200 chars
URL_UPPERCASE,—,Reasonable proxy,small,2,3,yes,yes,H,Duplicate-URL risk minor
WRONG_PLACEHOLDER_LINK,—,Reasonable proxy,moderate,4,7,yes,yes,M,Dead CTA to example domain; UX-critical
WWW_CANONICALIZATION,—,Established,moderate,6,5,yes,yes,H,Duplicate hosts; canonical ambiguity documented
3. Overlap clusters (task 6)
C1 — Schema absence: SCHEMA_MISSING + JSON_LD_MISSING (+ SCHEMA_ORG_MISSING on homepage). Any page with no structured data fires the first two (JSON-LD is the dominant format; only a microdata-only page separates them). A schema-less homepage fires all three: 16 points for one absence. Fix: merge SCHEMA_MISSING into JSON_LD_MISSING; keep SCHEMA_ORG_MISSING as the homepage-specific issue and suppress the generic code when it fires there.

C2 — Thin content: CONTENT_THIN (<100 words) ⊂ THIN_CONTENT (<300 words). Strict subset — every CONTENT_THIN page fires both, always. Fix: one graded parent (severe <100 / moderate 100–300), or suppress THIN_CONTENT when CONTENT_THIN fires.

C3 — Answer position: CENTRAL_CLAIM_BURIED (first 150 words) + FIRST_VIEWPORT_NO_ANSWER (first 200 words) + GEO_SUMMARY_BURIED. The first two have near-identical detection windows and co-fire on most pages lacking an early answer. Fix: CENTRAL_CLAIM_BURIED is the parent (it carries the measured-evidence lane); suppress FIRST_VIEWPORT_NO_ANSWER when it fires. GEO_SUMMARY_BURIED is section-scope, technically distinct — keep but demoted.

C4 — Uncited content: CITATIONS_MISSING_SUBSTANTIAL_CONTENT (200+w) + EXTERNAL_CITATIONS_LOW (500+w) + ORPHAN_CLAIM_TECHNICAL. A 500+ word page with no sourcing fires the first two by definition; a technical one fires all three (14 points, one root cause: "add sources"). Fix: graded parent by word count; ORPHAN_CLAIM_TECHNICAL suppressed when the parent fires on the same page.

C5 — Duplicate pair: TITLE_META_DUPLICATE_PAIR fires only when TITLE_DUPLICATE and META_DESC_DUPLICATE both fire — pure triple-count (currently 6+5+4 = 15). Fix: PAIR replaces its children, never adds.

C6 — JS rendering: RAW_HTML_JS_DEPENDENT (app shell) ⊃ JS_RENDERED_CONTENT_DIFFERS (>20% delta). A shell trivially exceeds the 20% delta; both fire. CONTENT_CLOAKING_DETECTED also compares rendered-vs-raw and can co-fire on JS-heavy pages. Fix: suppress DIFFERS when SHELL fires; require CLOAKING's topic-shift test to exclude pure volume deltas.

C7 — No-text pages: CONTENT_NOT_EXTRACTABLE_NO_TEXT drags CONTENT_THIN, THIN_CONTENT, CONTENT_UNSTRUCTURED, SEMANTIC_DENSITY_LOW, AI_MAIN_CONTENT_LOW_RATIO — a page with zero text satisfies every text-quantity/structure check simultaneously (potentially 20+ stacked points, one root cause). Fix: NO_TEXT suppresses all text-quantity/structure children.

C8 — Security host pair: HTTP_PAGE + HTTPS_REDIRECT_MISSING co-fire on every HTTP page of a non-redirecting site (18 points/page for one server config). Fix: HTTPS_REDIRECT_MISSING and WWW_CANONICALIZATION become site-level issues deducted once, not per page.

C9 — Robots blanket: AI_BOT_BLANKET_DISALLOW implies AI_BOT_SEARCH_BLOCKED, AI_BOT_USER_FETCH_BLOCKED, and per-page ROBOTS_BLOCKED on every page. If the tool fires all of these, one robots.txt line can floor the entire site several times over. Fix: BLANKET suppresses the specific bot codes; ROBOTS_BLOCKED per page is arguably correct (each page genuinely is blocked) but should be noted as a single root cause in reporting.

C10 — Redirect normalization: REDIRECT_CASE_NORMALISE / REDIRECT_TRAILING_SLASH vs INTERNAL_REDIRECT_301 — an internal link whose target 301s for a normalization reason can fire both the specific and generic code. Fix: specific suppresses generic per link.

4. Top 20 most-consequential changes
BROKEN_LINK_404: 10 → 4, plus per-page dedup (H). The compounded error — page-fatal impact × per-occurrence counting — means five broken links (−50) outweigh serving the page over HTTP. Google states broken outbound links are not a ranking factor; the harms are UX and crawl waste.
Per-occurrence counting rule change for all BROKEN_LINK_/REDIRECT_ codes (H). Deduct once per code per page with count displayed; the fix action is one task regardless of count. This is a bigger score-distribution change than any single impact value.
C5 suppression — TITLE_META_DUPLICATE_PAIR (H). Deterministic triple-count today; the same duplicated template costs 15 points where 4 is defensible.
LANG_MISSING: 6 → 2 (H). Google documents that it ignores the lang attribute and self-detects language. Residual value is accessibility.
TITLE_H1_MISMATCH: 6 → 2 (M). Google does not require agreement; the practical consequence is possible title rewriting. Six points penalizes a tolerated pattern.
Schema cluster (C1): merge, JSON_LD_MISSING 7 → 4 (H). A schema-less homepage currently loses up to 16 points for one absence whose individual value is moderate at best.
LINK_EMPTY_ANCHOR: 7 → 2 (H). One link's lost anchor signal plus an a11y defect; nothing supports near-critical weighting.
META_DESC_MISSING: 7 → 4 (H). Vendor-stated non-ranking-factor; Google rewrites most descriptions regardless. Real but moderate CTR effect.
CONTENT_NOT_EXTRACTABLE_NO_TEXT: 6 → 9, RP → Established (H). No machine-readable text defeats Google extraction and every non-rendering AI crawler — one of the few genuinely gating conditions, and currently scored below a missing meta description.
RAW_HTML_JS_DEPENDENT: 6 → 9, RP → Established (M). An app shell gates all non-rendering AI crawlers (OpenAI/Anthropic documented). Confidence M because Google and therefore AI Overviews still see rendered content — the gate is AI-side, not total.
AI_PREVIEW_BLOCKED_AT_BOT / AI_PREVIEW_SUPPRESSED: 3 → 6 (M). Snippet-control directives gate AI Overview eligibility per Google's documentation; current 3 (and severity "info") predates that coupling. Fast-moving — re-verify quarterly.
AI_BOT_SEARCH_BLOCKED: 8 → 6 (M). Blocking one engine's search bot removes one citation surface while Google and other engines are unaffected — moderate under a consistent "gating = across engines" rule, not near-critical.
HTTPS_REDIRECT_MISSING: 9 → 6, site-level once (C8) (M). The failure is canonicalization/duplication when HTTPS already exists — categorically less severe than HTTP_PAGE, and currently double-charged per page alongside it.
GEO-heuristic deflation family: SECTION_CROSS_REFERENCES 6→2, QUERY_COVERAGE_WEAK 5→2, BLOG_SECTIONS_MISSING 5→2, SECTION_VAGUE_OPENER 5→2, FIRST_VIEWPORT_NO_ANSWER 5→2, GEO_SUMMARY_BURIED 5→2, CONVERSATIONAL_H2_MISSING 4→1 (H on the principle, M–L on individual semantics). Unconfirmed style heuristics currently outscore documented issues; collectively they can sink a competent page by 30+ points on conjecture. The measured GEO effects survive at 4 via the exception lane; the unmeasured ones drop to the Heuristic band.
AI_HIGH_VALUE_UNCITED: 4 → 0 (M). Not being cited is an outcome, not a page defect; its causes are scored elsewhere. Deducting for it double-counts and penalizes engine-side selection the owner cannot control. Keep as an opportunity flag.
IMG_BROKEN: 8 → 4 (H). Content/UX loss, not a near-critical ranking event.
SITEMAP_MISSING: 6 → 2 (H). Google documents that small, well-linked sites generally don't need a sitemap — precisely this tool's 20–100-page audience. Low effort keeps it a quick win.
H1_MULTIPLE: 5 → 2 (H). Vendor-documented non-issue for ranking; HTML5-valid. Retained at 2 for structure hygiene only.
UNSAFE_CROSS_ORIGIN_LINK: 3 → 0, retire (H). Browsers have implied noopener on target="_blank" since ~2021; scoring a neutralized vulnerability erodes the tool's trustworthiness claim.
LLMS_TXT_MISSING 3 → 1 / LLMS_TXT_INVALID 2 → 1 (H). No measured citation lift, minority adoption, Google declined support. Above 1 is indefensible on current evidence; revisit if any vendor confirms consumption.
Also worth noting though outside the top 20: the current severity labels contradict the current impacts in at least four places (NOINDEX_META = warning at impact 10; AI_PREVIEW_* = info; CANONICAL_SELF_MISSING = info at impact 5; PLACEHOLDER_LINK = critical at UX-only harm). Deriving severity from impact eliminates the entire inconsistency class.

5. Open questions / limits of this judgment
This run is not independent. As stated above, my prior review and execution are in context; the derivation matrix is identical to my earlier one because I still endorse it, but a genuinely fresh session might have produced a different matrix or different tier boundaries. Weight accordingly when comparing against your second agent.

The "gating = across engines" interpretation of large is my choice, not the prompt's. Your effect_size anchor says "gate the page's indexing or AI-citation eligibility outright" without specifying scope. I read "outright" as across-engines; the other agent may read it per-engine, which would push AI_BOT_SEARCH_BLOCKED and the AI_PREVIEW codes to 9. This is the single most likely systematic divergence between reviewers — worth resolving in the prompt if you run it again.

Granularity cost of the matrix. Established has no cell yielding 4 or 5, so AI_BOT_USER_FETCH_BLOCKED lands at 2 when the honest value is "2–4 depending on how much you weight live-fetch citations." Reviewer_confidence M–L rows in the Established tier mostly reflect this quantization, not evidence uncertainty.

Effort values remain unaudited — outside the stated task, but they now carry 40 points of priority weight under my proposed formula. Several look off for a WordPress-with-page-builder audience (REDIRECT_LOOP effort 4 is high for what is usually a plugin/SSL-setting fix; CHUNKS_NOT_SELF_CONTAINED effort 4 is probably right).

Fast-moving dependencies to re-verify quarterly: (a) snippet-control ↔ AI Overview coupling — my 6 for both AI_PREVIEW codes depends on Google's current documented behavior; (b) AI user-fetch robots.txt compliance — OpenAI's ChatGPT-User stance is the least stable of the vendor facts; (c) llms.txt — a single vendor confirming consumption justifies 1 → 3; (d) FAQ schema residual value — if Google's "still aids understanding" language disappears from the documentation, FAQ_SCHEMA_MISSING should go informational; (e) the entire Heuristic-measured lane rests on one paper (~1,000 queries, one generation model) — independent replication would justify raising its cap from 5 toward 7; failed replication collapses it into plain Heuristic.

Calibration data I'd want before trusting these numbers as more than expert judgment: the empirical co-firing frequencies for clusters C1–C10 from real crawls (to confirm suppression priorities); the distribution of per-page issue counts (to tune the category cap of 30 and fatal gate of 40, both of which are judgment values, M confidence); and correlation of TalkingToad health scores against GSC impressions or AI-referral traffic across a sample of nonprofit sites — the only ground truth that would move any of this from calibrated opinion to measurement.

