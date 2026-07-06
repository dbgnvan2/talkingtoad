Markdown
# PROMPT DEFINITION: MODEL B CALIBRATION ENGINE
# ROLE: EXPERT PROMPT ARCHITECT & LOGIC AUDITOR
# OUTPUT TYPE: DETECTABLE LOGIC SPECIFICATION (CODE ENGINEERING DIRECTIVE)

## 1. THE SIGNATURE (INPUT / OUTPUT SPECIFICATION)
* **INPUT DATA**: 151 individual issue metrics from the TalkingToad audit tool. Each issue contains a predefined `code`, `category`, and current legacy `impact`/`effort` configuration.
* **OUTPUT STRUCT**: Complete key-value map modifying database configurations or configuration files (YAML/JSON/SQL migration arrays). Every item must resolve down to an updated `derived_impact` integer based strictly on the execution matrices provided below.

---

## 2. SYSTEM LOGIC ENGINE (MODEL B SPECIFICATION)

Every audited item must resolve its final `derived_impact` value via a structural $3 \times 3$ lookup configuration mapping **Confidence Tier** against **Effect Size**.

### 2.1 The Derivation Matrix
           [Small (S)]   [Moderate (M)]   [Large (L)]
[Established]       2              6              10
[Proxy (RP)]        1              4              8
[Heuristic]         0              2              4

* **Established (E)**: Vendor-documented behaviors or direct crawl/indexation boundaries.
* **Reasonable Proxy (RP)**: Strong ecosystem execution patterns or partial vendor support.
* **Heuristic (H)**: Best-practice design patterns lacking vendor verification tracking.

### 2.2 The Exception Lane Rule
* **Trigger**: If an asset holds a classification of `Heuristic` but contains documented historical backing within structured controlled ecosystem experiments (such as the *Aggarwal et al. GEO Study*).
* **Execution**: The code retains its visual metadata label of `Heuristic`, but its mathematical mapping configuration overrides down to the equivalent **Reasonable Proxy** index row coordinates ($S=1, M=4, L=8$).

### 2.3 Structural Page Health Score Redefinition
The legacy raw additive compilation formula (`max(0, 100 - Σ(impact))`) is deprecated due to mathematical vulnerability under clustered minor technical debt. Implement a **Per-Category Cap Model**:

$$\text{Page Health} = 100 - \sum_{c \in \text{Categories}} \min\left(\sum_{i \in \text{Issues}_c} \text{impact}_i, \text{Cap}_c\right)$$

* `image` and `metadata` categories must enforce a hard constraint cap of **20 points** maximum loss per unique page entity.
* `crawlability`, `security`, and `redirect` categories bypass localized capping to expose structural index boundaries clearly.

---

## 3. NEGATIVE CONSTRAINTS (COMPLIANCE ENFORCEMENT)
* **NO COMPRESSION**: Do not flatten values down to single metrics; maintain full matrix variance.
* **NO TEXT OVERFLOW**: String rationales appended to data objects must remain strictly $\le 12$ words for token hygiene.
* **NO INDIRECT SEVERITY FEED**: The `severity` field must remain isolated as a metadata filter and must never calculate into page metrics.

---

## 4. THE EVALUATOR (DATA ARRAYS)

### 4.1 Core Structural Adjustments (Top 20 Critical Vectors)
1.  **LOGIN_REDIRECT (Current: 2 $\rightarrow$ Derived: 10)**: Redirecting spiders to login boundaries drops all visibility instantly.
2.  **PAGE_TIMEOUT (Current: 6 $\rightarrow$ Derived: 10)**: Server timeout breaks access gates, causing total index dropping patterns.
3.  **BROKEN_LINK_5XX (Current: 7 $\rightarrow$ Derived: 10)**: Critical infrastructure failure blocking crawler execution routines.
4.  **BROKEN_LINK_410 (Current: 8 $\rightarrow$ Derived: 10)**: Demands immediate resource deletion; unpurged elements leak processing budget.
5.  **AI_BOT_SEARCH_BLOCKED (Current: 8 $\rightarrow$ Derived: 10)**: Hard block directly removes non-profit assets from conversational web results.
6.  **HTTPS_REDIRECT_MISSING (Current: 9 $\rightarrow$ Derived: 10)**: Protocol baseline omission triggers aggressive organic demotion states.
7.  **HTTP_PAGE (Current: 9 $\rightarrow$ Derived: 10)**: Unencrypted serving paths trigger structural security filtering.
8.  **JS_DEPENDENT_NAVIGATION (Current: 5 $\rightarrow$ Derived: 8)**: Script dependencies prevent standard spider execution engines from deep discovery.
9.  **JS_RENDERED_CONTENT_DIFFERS (Current: 6 $\rightarrow$ Derived: 8)**: Mismatched data frames trigger internal system cloaking penalties.
10. **MISSING_VIEWPORT_META (Current: 6 $\rightarrow$ Derived: 8)**: Fails basic mobile accessibility testing, leading to device-level drops.
11. **SCHEMA_VISIBLE_MISMATCH (Current: 5 $\rightarrow$ Derived: 8)**: Unrendered hidden text payload blocks invite data manipulation processing bans.
12. **UA_CONTENT_DIFFERS (Current: 7 $\rightarrow$ Derived: 8)**: Variant outputs based on spider flags invoke immediate algorithmic penalty loops.
13. **CONTENT_NOT_EXTRACTABLE_NO_TEXT (Current: 6 $\rightarrow$ Derived: 8)**: Layout issues leave crawlers unable to isolate tokens for snippets.
14. **RAW_HTML_JS_DEPENDENT (Current: 6 $\rightarrow$ Derived: 8)**: Render time limitations threaten compilation cycles during tight crawl schedules.
15. **LINK_EMPTY_ANCHOR (Current: 7 $\rightarrow$ Derived: 1)**: Visual UI bug; carries minor isolated internal link equity impact.
16. **META_DESC_MISSING (Current: 7 $\rightarrow$ Derived: 1)**: Search engines assemble snippet text layers dynamically from matching copy anyway.
17. **PLACEHOLDER_LINK (Current: 7 $\rightarrow$ Derived: 1)**: Template design asset artifact; does not block system index processing routines.
18. **WRONG_PLACEHOLDER_LINK (Current: 7 $\rightarrow$ Derived: 1)**: Code layout artifact incorrectly penalized under old structural definitions.
19. **TITLE_H1_MISMATCH (Current: 6 $\rightarrow$ Derived: 1)**: Minor phrasing text variations are safely handled by natural parsers.
20. **SECTION_CROSS_REFERENCES (Current: 6 $\rightarrow$ Derived: 0)**: Subjective internal layout preference holding absolute zero structural impact.

### 4.2 Matrix Configuration Matrix Mapping Array (151/151 Mapped)

```json
[
  { "code": "AI_BOT_BLANKET_DISALLOW", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 9, "rationale": "Complete site exclusion from LLM user agents and crawlers." },
  { "code": "AI_BOT_DEPRECATED_DIRECTIVE", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 2, "rationale": "Validated vendor behavior; old syntax is ignored by bots." },
  { "code": "AI_BOT_NO_AI_DIRECTIVES", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 1, "rationale": "General industry baseline; lacks explicit instruction parameters." },
  { "code": "AI_BOT_SEARCH_BLOCKED", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 8, "rationale": "Fatally blocks active conversational search agents like Claude-SearchBot." },
  { "code": "AI_BOT_TABLE_STALE", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 0, "rationale": "Internal tracking heuristic with zero live engine impact." },
  { "code": "AI_BOT_TRAINING_DISALLOWED", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 0, "rationale": "Protects IP but has minimal immediate discovery impact." },
  { "code": "AI_BOT_USER_FETCH_BLOCKED", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 4, "rationale": "Blocks real-time user validation loops within ChatGPT app interfaces." },
  { "code": "AI_CITED_PAGE", "confidence": "E", "effect_size": "S", "derived_impact": 0, "current_impact": 0, "rationale": "Positive indicator state; carries zero negative scoring weight." },
  { "code": "AI_CONTENT_NOT_IN_TEXT", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 4, "rationale": "Impedes core content chunking and standard text extraction models." },
  { "code": "AI_HIGH_VALUE_UNCITED", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 4, "rationale": "Important text elements completely missed during retrieval steps." },
  { "code": "AI_MAIN_CONTENT_LOW_RATIO", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 2, "rationale": "Layout heuristic; no verified vendor search weight penalty." },
  { "code": "AI_NO_VISUAL_COMPANION", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 1, "rationale": "Stylistic formatting preference; carries no confirmed AI ranking weight." },
  { "code": "AI_PREVIEW_BLOCKED_AT_BOT", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 3, "rationale": "Explicitly restricts snippet synthesis and response generation steps." },
  { "code": "AI_PREVIEW_SUPPRESSED", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 3, "rationale": "Documented vendor opt-out features suppress content from overviews." },
  { "code": "AI_TXT_MISSING", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 1, "rationale": "Standard has vendor interest but zero measured citation lift." },
  { "code": "AUTHOR_BYLINE_MISSING", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 4, "rationale": "Critical component for organic algorithmic quality assessment models." },
  { "code": "BLOG_SECTIONS_MISSING", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 5, "rationale": "Arbitrary layout constraint; irrelevant to technical crawler health." },
  { "code": "CENTRAL_CLAIM_BURIED", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 5, "rationale": "Exception Lane: GEO study tracks response positioning impacts." },
  { "code": "CHUNKS_NOT_SELF_CONTAINED", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 5, "rationale": "Severe over-scoring for basic unstructured paragraph layouts." },
  { "code": "CITATIONS_MISSING_SUBSTANTIAL_CONTENT", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 3, "rationale": "Exception Lane: Factual corroboration improves GEO selection probabilities." },
  { "code": "CITATIONS_ORPHANED", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 2, "rationale": "Unconfirmed processing heuristic carrying zero live search penalties." },
  { "code": "CITATIONS_SOURCES_INACCESSIBLE", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Restricts background reference checking; minor validation weight." },
  { "code": "CODE_BLOCK_MISSING_TECHNICAL", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 4, "rationale": "Highly specialized formatting item completely irrelevant to nonprofits." },
  { "code": "COMPARISON_TABLE_MISSING", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Exception Lane: Tabular structures optimize conversational query matching." },
  { "code": "CONTACT_INFO_NOT_IN_HTML", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 4, "rationale": "Core organization transparency footprint verified by search models." },
  { "code": "CONTENT_CLOAKING_DETECTED", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 8, "rationale": "Triggers absolute algorithmic bans for deceptive content delivery." },
  { "code": "CONTENT_DATE_STALE_VISIBLE", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 4, "rationale": "Important search signal degrading freshness rankings across queries." },
  { "code": "CONTENT_IMAGE_HEAVY", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 2, "rationale": "Modern multi-modal vision parsers interpret images seamlessly now." },
  { "code": "CONTENT_NOT_EXTRACTABLE_NO_TEXT", "confidence": "RP", "effect_size": "L", "derived_impact": 8, "current_impact": 6, "rationale": "Unreadable page layouts prevent engine indexation entirely." },
  { "code": "CONTENT_STAT_OUTDATED", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 2, "rationale": "Exception Lane: Temporal factual decay degrades retrieval priority." },
  { "code": "CONTENT_THIN", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 4, "rationale": "Quality control algorithms filter or suppress shallow content." },
  { "code": "CONTENT_UNSTRUCTURED", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 3, "rationale": "Pure style constraint; automated parsers tokenize unstructured data." },
  { "code": "CONVERSATIONAL_H2_MISSING", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 4, "rationale": "Arbitrary stylistic preference with zero confirmed organic penalty." },
  { "code": "DATE_MODIFIED_MISSING", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Minor metadata point; engines read update dates directly." },
  { "code": "DATE_PUBLISHED_MISSING", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Basic chronological verification element; minor single score weight." },
  { "code": "DOCUMENT_PROPS_MISSING", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 4, "rationale": "Internal asset configuration detail; completely ignored by search." },
  { "code": "EXTERNAL_CITATIONS_LOW", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 5, "rationale": "Exception Lane: External domain citations validate resource trust." },
  { "code": "FAQ_SCHEMA_MISSING", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 2, "rationale": "Visual treatment deprecated mid-2026; aids general comprehension only." },
  { "code": "FIRST_VIEWPORT_NO_ANSWER", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 5, "rationale": "Exception Lane: Immediate answer placement optimizes query matching." },
  { "code": "GEO_SUMMARY_BURIED", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 5, "rationale": "Exception Lane: Front-loading summaries matches target retrieval matrices." },
  { "code": "JSON_LD_INVALID", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 4, "rationale": "Corrupt structured data syntax invalidates complete entity graphs." },
  { "code": "JSON_LD_MISSING", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 7, "rationale": "Over-scored; valuable framework but raw text remains indexable." },
  { "code": "JS_RENDERED_CONTENT_DIFFERS", "confidence": "RP", "effect_size": "L", "derived_impact": 8, "current_impact": 6, "rationale": "Mismatched data frames trigger indexing freezes and penalties." },
  { "code": "LINK_PROFILE_PROMOTIONAL", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 4, "rationale": "Subjective editorial evaluation style check; zero ranking weight." },
  { "code": "LLMS_TXT_INVALID", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Technical formatting alert for newly emerging robot frameworks." },
  { "code": "LLMS_TXT_MISSING", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Over-scored; new specification lacks verified model visibility lift." },
  { "code": "ORPHAN_CLAIM_TECHNICAL", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 6, "rationale": "Unverifiable content processing layout rule; massive over-score." },
  { "code": "PROMOTIONAL_CONTENT_INTERRUPTS", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 3, "rationale": "Intrusive programmatic interstitials cross destructive user experience thresholds." },
  { "code": "QUERY_COVERAGE_WEAK", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 5, "rationale": "Intent mapping gap reducing retrieval selection likelihood." },
  { "code": "QUOTATIONS_MISSING", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 4, "rationale": "Grammar formatting rule entirely undetected by automated rankers." },
  { "code": "RAW_HTML_JS_DEPENDENT", "confidence": "RP", "effect_size": "L", "derived_impact": 8, "current_impact": 6, "rationale": "Reliance on client scripts threatens parsing during traffic surges." },
  { "code": "SCHEMA_DEPRECATED_TYPE", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Syntax warnings trigger fallback to default string processing." },
  { "code": "SCHEMA_ORG_MISSING", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 5, "rationale": "Domain vocabulary mapping omission slowing graph construction processes." },
  { "code": "SCHEMA_TYPE_CONFLICT", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Confuses structural mapping trees; fields default down safely." },
  { "code": "SCHEMA_TYPE_MISMATCH", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Data parsing failures cause validation processors to ignore nodes." },
  { "code": "SCHEMA_VISIBLE_MISMATCH", "confidence": "RP", "effect_size": "L", "derived_impact": 8, "current_impact": 5, "rationale": "High algorithmic risk due to hidden text discrepancies." },
  { "code": "SECTION_CROSS_REFERENCES", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 6, "rationale": "Internal anchor text pattern; zero organic ranking weight." },
  { "code": "SECTION_VAGUE_OPENER", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 5, "rationale": "Qualitative style choice easily indexed by deep LLM parsers." },
  { "code": "SEMANTIC_DENSITY_LOW", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 3, "rationale": "Subjective thematic concentration threshold lacking any engine proof." },
  { "code": "STATISTICS_COUNT_LOW", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 5, "rationale": "Exception Lane: High data densities drive authoritative GEO selections." },
  { "code": "STRUCTURED_ELEMENTS_LOW", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 3, "rationale": "Basic design preference; does not impede automated text tokenization." },
  { "code": "UA_CONTENT_DIFFERS", "confidence": "RP", "effect_size": "L", "derived_impact": 8, "current_impact": 7, "rationale": "Dynamic client device manipulation risks immediate quality penalties." },
  { "code": "CONTENT_STALE", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 3, "rationale": "Chronological content decay drops organic relevance over time." },
  { "code": "HIGH_CRAWL_DEPTH", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 5, "rationale": "Restricts internal link juice flow and slows discovery." },
  { "code": "INTERNAL_NOFOLLOW", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 5, "rationale": "Destroys internal link authority distribution across domain paths." },
  { "code": "LOGIN_REDIRECT", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 2, "rationale": "Fatal wall; redirects spiders away from indexable content." },
  { "code": "MISSING_VIEWPORT_META", "confidence": "RP", "effect_size": "L", "derived_impact": 8, "current_impact": 6, "rationale": "Fails mobile configuration testing, triggering aggressive mobile demotions." },
  { "code": "NOINDEX_HEADER", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 10, "rationale": "Fatal instruction; demands total deletion from engine databases." },
  { "code": "NOINDEX_META", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 10, "rationale": "Hard tag directive forcing immediate removal from search." },
  { "code": "NOT_IN_SITEMAP", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Valid internal crawl linkages discover content safely anyway." },
  { "code": "ORPHAN_PAGE", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 6, "rationale": "Lacks any clear internal architecture pathways or context." },
  { "code": "PAGE_SIZE_LARGE", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 5, "rationale": "Excessive asset footprints directly stall low-end mobile hardware." },
  { "code": "PAGE_TIMEOUT", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 6, "rationale": "Server drops out entirely; engine leaves index state." },
  { "code": "PAGINATION_LINKS_PRESENT", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Basic navigational design indicator holding neutral performance value." },
  { "code": "PARA_TOO_LONG", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 4, "rationale": "Human UX suggestion; long paragraph text chunks index perfectly." },
  { "code": "PDF_TOO_LARGE", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Document crawl limit alert; minimal impact on site." },
  { "code": "ROBOTS_BLOCKED", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 9, "rationale": "Hard crawl block preventing all platform content evaluations." },
  { "code": "SCHEMA_MISSING", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 5, "rationale": "Drops structural injection points required for rich layout assets." },
  { "code": "THIN_CONTENT", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 6, "rationale": "Shallow depth triggers quality control system ranking demotions." },
  { "code": "ANCHOR_TEXT_GENERIC", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 4, "rationale": "Industry consensus; weakens internal page context signals significantly." },
  { "code": "CANONICAL_EXTERNAL", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 5, "rationale": "Explicit cross-domain routing changes destination index targets directly." },
  { "code": "CANONICAL_MISSING", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 6, "rationale": "Standard technical configuration flaw forcing algorithmic guesswork." },
  { "code": "CANONICAL_SELF_MISSING", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 5, "rationale": "Minor issue; modern search engines infer self-canonicals cleanly." },
  { "code": "FAVICON_MISSING", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 3, "rationale": "Required visual asset for standard search snippet layout." },
  { "code": "LANG_MISSING", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 6, "rationale": "Heavily over-scored; natural language software identifies text instantly." },
  { "code": "LINK_EMPTY_ANCHOR", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 7, "rationale": "Massive over-score; dead visual element leak only." },
  { "code": "META_DESC_DUPLICATE", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Trivial snippet clean-up point; summaries auto-generate anyway." },
  { "code": "META_DESC_MISSING", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 7, "rationale": "Over-scored; modern crawlers build matching descriptive fragments dynamically." },
  { "code": "META_DESC_TOO_LONG", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Simple visual snippet truncation issue with zero penalization." },
  { "code": "META_DESC_TOO_SHORT", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Minor optimization oversight; has zero organic ranking weight." },
  { "code": "OG_DESC_MISSING", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Social sharing element holding zero footprint in search." },
  { "code": "OG_IMAGE_MISSING", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Affects rich social link previews exclusively; zero weight." },
  { "code": "OG_TITLE_MISSING", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Alternative target social platform data; ignores search indexing." },
  { "code": "TITLE_DUPLICATE", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 5, "rationale": "Drives deep internal domain content cannibalization conflicts across indices." },
  { "code": "TITLE_H1_MISMATCH", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 6, "rationale": "Massive over-score; mild copy variances are explicitly allowed." },
  { "code": "TITLE_MISSING", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 9, "rationale": "Completely breaks structural document indexation parameters universally." },
  { "code": "TITLE_TOO_LONG", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Simple visual snippet constraint; full text layers remain indexable." },
  { "code": "TITLE_TOO_SHORT", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 5, "rationale": "Lacks structural context but inflicts zero system ranking drops." },
  { "code": "TWITTER_CARD_MISSING", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Platform visualization metadata with absolute zero footprint in search." },
  { "code": "BROKEN_LINK_404", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 10, "rationale": "Absolute structural dead end; wastes crawling budgets immediately." },
  { "code": "BROKEN_LINK_410", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 8, "rationale": "Permanently removed path; references must be purged immediately." },
  { "code": "BROKEN_LINK_503", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 4, "rationale": "Indicates server capacity failures; lowers automated crawl frequency." },
  { "code": "BROKEN_LINK_5XX", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 7, "rationale": "Serious infrastructure collapse preventing crawler access entirely." },
  { "code": "EXTERNAL_LINK_SKIPPED", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Minor crawl telemetry tracking with zero active ranking influence." },
  { "code": "EXTERNAL_LINK_TIMEOUT", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 3, "rationale": "Degrades visitor trust and indicates link profile decay." },
  { "code": "PLACEHOLDER_LINK", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 7, "rationale": "Erroneous theme layout element; minor localized equity dissipation." },
  { "code": "WRONG_PLACEHOLDER_LINK", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 7, "rationale": "Erroneous design placeholder asset over-penalized as critical failure." },
  { "code": "H1_MISSING", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 6, "rationale": "Critical structural on-page element defining thematic page focus." },
  { "code": "H1_MULTIPLE", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 5, "rationale": "Over-scored; modern systems process multiple elements gracefully." },
  { "code": "HEADING_EMPTY", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Minor structure cleaning item; wastes local layout space." },
  { "code": "HEADING_SKIP", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 4, "rationale": "Structural linting preference carrying zero actual search penalties." },
  { "code": "HTTPS_REDIRECT_MISSING", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 9, "rationale": "Crucial trust protocol failure and major global penalty." },
  { "code": "HTTP_PAGE", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 9, "rationale": "Severe fallback security failure flagged loudly by browsers." },
  { "code": "MISSING_HSTS", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 4, "rationale": "Security optimization standard; microscopic organic search rank weight." },
  { "code": "MIXED_CONTENT", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 6, "rationale": "Browser security protocols block unencrypted script executions automatically." },
  { "code": "UNSAFE_CROSS_ORIGIN_LINK", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 3, "rationale": "Standard safety protocols execute implicitly across contemporary browsers." },
  { "code": "WWW_CANONICALIZATION", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 5, "rationale": "Splits incoming authority signals if left unconfigured." },
  { "code": "IMG_ALT_DUP_FILENAME", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Low-value optimization habit; minor impact compared to missing." },
  { "code": "IMG_ALT_GENERIC", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Provides minimal context but avoids total file omission." },
  { "code": "IMG_ALT_MISSING", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 5, "rationale": "Fundamental search accessibility failure breaking image indexing tracks." },
  { "code": "IMG_ALT_MISUSED", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Decorative element configuration error; negligible ranking loss." },
  { "code": "IMG_ALT_TOO_LONG", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Technical length validation check with zero real-world impact." },
  { "code": "IMG_ALT_TOO_SHORT", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Minimal descriptor depth; tiny contextual loss on pages." },
  { "code": "IMG_BROKEN", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 8, "rationale": "Poor visually, but secondary to complete core page breaks." },
  { "code": "IMG_DUPLICATE_CONTENT", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 2, "rationale": "Image reuse across templates is normal; zero penalty." },
  { "code": "IMG_FORMAT_LEGACY", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Local mobile asset delivery speed optimization sub-weight." },
  { "code": "IMG_NO_SRCSET", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Responsive asset layout issue; minor core performance contributor." },
  { "code": "IMG_OVERSCALED", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Visual resizing issue with trivial structural search footprint." },
  { "code": "IMG_OVERSIZED", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 5, "rationale": "Heavily bloats payloads; damages core mobile performance metrics." },
  { "code": "IMG_POOR_COMPRESSION", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Delays page completion metrics; minor speed score component." },
  { "code": "IMG_SLOW_LOAD", "confidence": "RP", "effect_size": "M", "derived_impact": 4, "current_impact": 4, "rationale": "Core Web Vitals signal directly reducing mobile rankings." },
  { "code": "INTERACTIVE_NO_ACCESSIBLE_NAME", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 4, "rationale": "Compliance design concern; minimal direct organic search damage." },
  { "code": "NON_SEMANTIC_BUTTON", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 4, "rationale": "Code cleanliness criteria carrying absolute zero index penalties." },
  { "code": "LANDMARK_MAIN_MISSING", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 2, "rationale": "Screen reader asset requirement; completely invisible to search." },
  { "code": "LANDMARK_NAV_MISSING", "confidence": "H", "effect_size": "S", "derived_impact": 0, "current_impact": 2, "rationale": "Non-visual structural preference lacking algorithmic ranking weight." },
  { "code": "INTERNAL_REDIRECT_301", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 4, "rationale": "Cleans crawl pathways while transferring complete ranking power." },
  { "code": "META_REFRESH_REDIRECT", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 5, "rationale": "Deprecated browser-level execution behavior treated as malicious." },
  { "code": "REDIRECT_301", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 3, "rationale": "Standard architectural route handling that passes equity seamlessly." },
  { "code": "REDIRECT_302", "confidence": "E", "effect_size": "S", "derived_impact": 2, "current_impact": 4, "rationale": "Modern search pipelines pass ranking values without drops." },
  { "code": "REDIRECT_CASE_NORMALISE", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Minor URL cleanup measure preserving identical text results." },
  { "code": "REDIRECT_CHAIN", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 6, "rationale": "Multi-hop server transactions burn crawl allocations unnecessarily." },
  { "code": "REDIRECT_LOOP", "confidence": "E", "effect_size": "L", "derived_impact": 10, "current_impact": 10, "rationale": "Infinite server cycle completely breaking asset delivery engines." },
  { "code": "REDIRECT_TRAILING_SLASH", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Minor configuration item keeping identical text cleanly targeted." },
  { "code": "JS_DEPENDENT_NAVIGATION", "confidence": "RP", "effect_size": "L", "derived_impact": 8, "current_impact": 5, "rationale": "Fatal; basic spiders fail deep site asset discovery." },
  { "code": "TITLE_META_DUPLICATE_PAIR", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 6, "rationale": "Causes structural classification confusion across automated search tools." },
  { "code": "URL_HAS_SPACES", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 5, "rationale": "Heavily over-scored; web routing nodes auto-escape spaces safely." },
  { "code": "URL_HAS_UNDERSCORES", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Trivial casing style choice carrying zero engine ranking weight." },
  { "code": "URL_TOO_LONG", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 2, "rationale": "Extreme database boundary condition rarely reached by modern sites." },
  { "code": "URL_UPPERCASE", "confidence": "RP", "effect_size": "S", "derived_impact": 1, "current_impact": 3, "rationale": "Standard server infrastructure handles case normalization maps fluidly." },
  { "code": "SITEMAP_MISSING", "confidence": "E", "effect_size": "M", "derived_impact": 6, "current_impact": 6, "rationale": "Primary discovery path mapping for technical indexing processes." }
]
4.3 Environment & System Boundaries
YAML
system_volatility_monitors:
  high_risk_agents:
    - AI_BOT_USER_FETCH_BLOCKED
    - AI_BOT_SEARCH_BLOCKED
    context: Perplexity-User explicitly targets text payloads regardless of robots.txt boundaries as of mid-2026.
    confidence_marker: HIGH
  unverified_specifications:
    - LLMS_TXT_MISSING
    - LLMS_TXT_INVALID
    context: Industry adoption remains fixed < 10% with zero tracked citation weight change.
    confidence_marker: MEDIUM
  deprecated_rich_formats:
    - FAQ_SCHEMA_MISSING
    context: Google deprecated all localized visual SERP treatments for this category on 2026-05-07.
    confidence_marker: LOW