# TalkingToad Scoring & Checker Audit — Prompt for Claude Code

> **How to use:** Place this file in the repo (suggested: `docs/review/`) together with the 11 companion documents listed below, then start Claude Code at the repo root and give it this instruction:
>
> *"Read docs/review/CLAUDE_CODE_AUDIT_PROMPT.md and execute it."*

---

## Role and goal

You are auditing the issue-scoring and checker system of TalkingToad, a Python/FastAPI technical SEO + AI-GEO auditing tool (~151 issue codes in `api/crawler/checkers/registry.py`). Two prior reviews exist, done **without repo access** for the checker implementations. Your job is the review that was not possible before: verify everything against the actual code, adjudicate the disagreements between the two prior reviewers, and produce a final, evidence-based scoring change plan plus code-quality fixes.

The owner's priorities, in order: factual correctness, minimal assumptions, explicit uncertainty. Do not soften findings. Do not agree with either prior reviewer out of deference — both made errors that were later caught.

## Companion documents (place in `docs/review/`)

Original review (author: "Hermes Agent") — treat as **claims to verify**, not ground truth:
- `2026-07-02_scoring-review-part1-metadata-headings.md`
- `2026-07-02_scoring-review-part2-links-crawlability.md`
- `2026-07-02_scoring-review-part3-security-url-images.md`
- `2026-07-02_scoring-review-part4-ai-readiness-core.md`
- `2026-07-02_scoring-review-part5-geo-freshness-agent.md`

Second review (author: "Claude", chat-based, saw only `registry.py`) — same status, **claims to verify**:
- `2026-07-02_scoring-review-part0-overview_CLAUDE.md` (read this first — it contains the cross-cutting corrections, the schema-redundancy finding, and §6 registry-verification results)
- `2026-07-02_scoring-review-part1-…_CLAUDE.md` through `part5-…_CLAUDE.md` (Hermes text + interleaved "◆ CLAUDE" blocks with per-item verdicts and confidence tags)

Known facts already established (verified against vendor documentation and `registry.py`; re-verify only if you find contradicting evidence in code):
1. All 151 `_ISSUE_SCORING` values match the documents; the module docstring's counts (131/49) are stale (actual 151/62).
2. `PARAS_TOO_LONG` in Hermes Part 5 is a phantom — the registry has only `PARA_TOO_LONG`.
3. `GEO_SUMMARY_BURIED` (7,3) originated from translating a "penalty=20" prompt instruction (see "Cycle GG" comment), not evidence.
4. `make_issue`'s docstring claims unknown codes get zeroes, but `spec = _CATALOGUE[code]` raises `KeyError` first.
5. `fixability` and `effort` contradict each other on ~67/151 codes (details in part0 §6).
6. Web-verified as of early 2026: Anthropic's bots (incl. Claude-User) honor robots.txt; OpenAI says robots.txt "may not apply" to ChatGPT-User; Perplexity-User and Google user-proxy fetchers generally ignore it. llms.txt: proposed by Jeremy Howard (Answer.AI), Google declined support, Anthropic/Perplexity signaled support, no measured citation lift. Google 301/302 both pass PageRank. FAQ rich results restricted to gov/health sites since 2023. HowTo rich results deprecated 2023. `rel=noopener` implied for `target="_blank"` in modern browsers.

## Ground rules

1. **Every claim you make must cite `file:line`.** If you assert a checker behaves some way, quote the relevant code.
2. **Tag every judgment High / Medium / Low confidence**, and separate "verified in code" from "inferred" from "external-knowledge" claims.
3. **Report before patch.** Phases 1–4 produce a report. Do not modify scoring values until the owner approves the change plan. Phase 5 code-quality fixes (docstrings, dead code, the `KeyError` bug) may be implemented directly as a separate, clearly-labeled commit/diff, each with a test.
4. Where Hermes and Claude disagree, adjudicate with code and evidence; do not split the difference. The known disagreement list is in part0 §4 plus: `REDIRECT_302` (Hermes keep 5 / Claude 3), `AI_BOT_USER_FETCH_BLOCKED` (Hermes 2 / Claude 4), `STATISTICS_COUNT_LOW` and `QUOTATIONS_MISSING` (Hermes 4 / Claude 5), `OG_IMAGE_MISSING` (Hermes 2 / Claude 3), `TITLE_H1_MISMATCH` (Hermes 6 / Claude 5), `FAQ_SCHEMA_MISSING` (Hermes 3 / Claude 2), `AUTHOR_BYLINE_MISSING` and `CONTACT_INFO_NOT_IN_HTML` (page-type-conditional proposals), `MISSING_HSTS`, `AMPHTML_BROKEN`, `H1_MISSING` floor.
5. If web search is available to you, re-verify any fast-moving vendor claim you rely on (AI bot user-agent strings and robots.txt compliance especially). If it is not available, mark those items "as of early 2026, unverified today."
6. Do not assume the prior reviews are complete. If you find checks, thresholds, or scoring-relevant code paths neither review mentions, report them.

## Phase 1 — Verify the conditional claims (checker implementations)

Both prior reviews flagged detection-precision concerns they could not verify. For each, read the actual checker and state what the code does, whether the concern is real, and what fix (if any) is needed:

1. `LINK_EMPTY_ANCHOR` — does it check accessible name (`aria-label`, `aria-labelledby`, visually-hidden text, `img[alt]` inside the anchor), or visible text only? False-positive rate on icon links determines whether impact 6 or 4 is right.
2. `ORPHAN_PAGE` — is link discovery done on raw HTML only? Does the crawler execute or otherwise account for JS/query-driven listings (the JetEngine loop-grid case)? If raw-HTML-only, orphan findings on dynamic sites are unreliable and the check needs a caveat or a rendered-DOM pass.
3. `ROBOTS_BLOCKED` — does it exempt expected blocks (`/wp-admin/`, cart/search/param URLs)? Does it distinguish crawl-blocking from index-blocking anywhere in messaging?
4. `MIXED_CONTENT` — does it distinguish active (script/iframe — blocked by browsers) from passive (img/media — auto-upgraded) resources?
5. `IMG_SLOW_LOAD` / `IMG_OVERSIZED` / `IMG_OVERSCALED` / `IMG_POOR_COMPRESSION` — can they stack on one image? Is the LCP element identified and weighted differently?
6. `BROKEN_LINK_5XX` / `PAGE_TIMEOUT` / `EXTERNAL_LINK_TIMEOUT` — is there retry/persistence logic before firing, or single-observation?
7. `JS_RENDERED_CONTENT_DIFFERS` — is the >20% token delta computed on main content or total DOM? Total-DOM will fire on nearly every modern page.
8. `NOINDEX_META` / `AI_BOT_BLANKET_DISALLOW` — any staging-vs-production awareness? (Owner's real risk: staging directives surviving a SiteGround→production cutover.)
9. `TITLE_H1_MISMATCH` — inspect `_titles_mismatch` / `_sig_words` (registry.py ~1606–1640): how aggressive is the mismatch test? Does it fire on surface differences or genuine semantic divergence?
10. `SEMANTIC_DENSITY_LOW` vs `AI_MAIN_CONTENT_LOW_RATIO` — confirm both exist as separate computations; the Claude review recommends deprecating the former on page-builder markup. Verify what each measures.
11. `CONTENT_STAT_OUTDATED` / `CONTENT_DATE_STALE_VISIBLE` / `CONTENT_STALE` — is there page-type awareness (evergreen vs time-sensitive)?
12. `AI_BOT_*` checks — extract the actual user-agent table. Verify it distinguishes search bots (OAI-SearchBot, Claude-SearchBot, PerplexityBot, Google-Extended) from training bots (GPTBot, ClaudeBot, CCBot) from user-fetch agents (ChatGPT-User, Claude-User, Perplexity-User). Check `AI_BOT_SEARCH_BLOCKED` fires on search bots, not training bots. Check `AI_BOT_DEPRECATED_DIRECTIVE`'s deprecated-name list is current.

## Phase 2 — Stacking and aggregation analysis

1. Find how issues roll up to page and site scores (wherever `priority_rank`, severity counts, or grades are aggregated — likely outside registry.py). Document the formula.
2. Determine which of these clusters can multi-fire on a single page, and quantify the inflation under the aggregation formula:
   - Schema trio: `SCHEMA_MISSING`, `JSON_LD_MISSING`, `SCHEMA_ORG_MISSING` (+ `JSON_LD_INVALID` interaction)
   - Thin-content pair: `THIN_CONTENT`, `CONTENT_THIN`
   - Answer-first trio: `FIRST_VIEWPORT_NO_ANSWER`, `CENTRAL_CLAIM_BURIED`, `GEO_SUMMARY_BURIED`
   - Section-independence trio: `CHUNKS_NOT_SELF_CONTAINED`, `SECTION_VAGUE_OPENER`, `SECTION_CROSS_REFERENCES`
   - Duplicate-metadata stack: `TITLE_DUPLICATE` + `META_DESC_DUPLICATE` + `TITLE_META_DUPLICATE_PAIR`
   - Broken-reference overlap: `CITATIONS_SOURCES_INACCESSIBLE` vs `BROKEN_LINK_*`
   - Cloaking pair: `CONTENT_CLOAKING_DETECTED` vs `UA_CONTENT_DIFFERS`
   - Not-in-text cluster: `AI_CONTENT_NOT_IN_TEXT`, `CONTENT_NOT_EXTRACTABLE_NO_TEXT`, `CONTACT_INFO_NOT_IN_HTML`, `RAW_HTML_JS_DEPENDENT`
3. Propose suppression/precedence rules per cluster (parent code suppresses children, or merge into one graded check). State the behavior change each rule causes.

## Phase 3 — Scoring model design

1. Evaluate the two competing calibration schemes against the codebase as it actually exists:
   - Hermes: cap impact by confidence tier (Heuristic ≤3, Reasonable proxy ≤6, Established ≤9).
   - Claude: two axes — `confidence` × `effect_size` — with a documented exception for single-study-but-measured findings (the Aggarwal GEO checks).
   Recommend one (or a concrete synthesis) with implementation sketch. Note the formula quirk: lowering effort *raises* priority_rank, so "easier than we thought" promotes items — decide whether that is intended.
2. Reconcile `fixability` vs `effort`: propose a derivation rule (effort from fixability + scope) and list every code whose effort would change under it.
3. Decide `ORPHAN_PAGE` fixability (`developer_needed` is wrong per both reviews) and `BROKEN_LINK_5XX` (`wp_fixable` is wrong).

## Phase 4 — Final scoring change plan

Produce one table covering all 151 codes: `code | current (i,e) | Hermes proposed | Claude proposed | final recommendation (i,e) | severity change if any | confidence-label change if any | one-line rationale | adjudication note where the reviews disagreed`. Follow with the migration diff for `_ISSUE_SCORING` (and `_AI_READINESS_CONFIDENCE` / severity where changed) as a patch the owner can review before applying. Include: deletion of nothing without justification; deprecations (`SCHEMA_MISSING`, possibly `SEMANTIC_DENSITY_LOW`, possibly merging trios) listed separately with a compatibility note (what happens to historical audit data referencing removed codes).

## Phase 5 — Code-quality fixes (implement, separate from scoring)

1. Fix `make_issue` unknown-code handling (choose: `.get()` with a synthesized spec, or raise with a clear message — match the docstring to reality either way). Add a test.
2. Update stale docstring counts, or better, derive counts dynamically in the docstring's place / add a test asserting `len(_ISSUE_SCORING) == len(_CATALOGUE)` and that every scoring code has a catalogue entry and vice versa.
3. Add a test asserting every `ai_readiness`-category code has a confidence label (catches the gaps both reviews had to work around).
4. Tidy `_AI_READINESS_CONFIDENCE` section grouping (entries sitting under the wrong section comments).
5. Report (do not fix without approval) anything you find beyond this list: dead codes never emitted by any checker, checkers emitting codes absent from `_ISSUE_SCORING` (these currently get (0,0) silently — or crash, per the `KeyError` bug), threshold constants that contradict documentation.

## Deliverables

1. `docs/review/2026-07-XX_code-audit-report.md` — Phases 1–3 findings, every claim cited to file:line, every judgment confidence-tagged.
2. `docs/review/2026-07-XX_scoring-change-plan.md` — the Phase 4 table + patch.
3. A branch/diff with Phase 5 fixes and tests, each change separately explained.
4. A short list titled "What I could not verify and why" — required; do not omit it.
