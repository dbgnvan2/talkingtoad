"""
GEO check inventory and scoring utilities for the rewrite prompt generator.

Mirrors the scoring logic in geo_analyzer._compute_scores() so the prompt
generator can compute actual score changes without hitting the LLM.

Spec: docs/implementation_plan_geo_rewrite_prompt_2026-05-03.md#Phase-A
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Tier weights — must stay in sync with geo_analyzer._compute_scores()
# ---------------------------------------------------------------------------

TIER_WEIGHTS: dict[str, int] = {
    "Empirical": 3,
    "Mechanistic": 2,
    "Conventional": 1,
}

# ---------------------------------------------------------------------------
# Check inventory
# ---------------------------------------------------------------------------
# Fields:
#   code                       issue code used in GEOFinding and Issue objects
#   label                      human-readable name
#   tier                       Empirical | Mechanistic | Conventional
#   tier_weight                derived from TIER_WEIGHTS
#   source                     "static" (issue_checker) | "llm" (geo_analyzer)
#   pass_condition             plain-english description of what "pass" requires
#   threshold_description      exact numeric/structural threshold
#   page_type_conditions       list of conditions (empty = applies to all pages)
#   fix_effort                 easy | medium | hard | infeasible
#   can_fix_without_fabrication whether a pure text rewrite can fix it
#   rubric_instruction         instruction injected into the rewrite prompt
#   weak_check_note            explanation when check has known reliability gaps

GEO_CHECKS: list[dict] = [
    # ── Empirical tier (weight 3) ────────────────────────────────────────────
    {
        "code": "STATISTICS_COUNT_LOW",
        "label": "No Numeric Statistics",
        "tier": "Empirical",
        "tier_weight": 3,
        "source": "static",
        "pass_condition": "At least 1 numeric statistic detected on the page",
        "threshold_description": "0 statistics found (numbers + unit/% pattern) in headings + first_150_words",
        "page_type_conditions": ["word_count >= 500"],
        "fix_effort": "medium",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "Add at least one specific numeric statistic or data point drawn from the "
            "existing content or from a real source you can reference. Do NOT invent "
            "figures. If the original text has no statistics, note this at the end of "
            "your rewrite."
        ),
        "weak_check_note": (
            "Regex scope is narrow (first_150_words + heading text only); statistics "
            "buried deep in body text are missed, causing false fires."
        ),
    },
    {
        "code": "EXTERNAL_CITATIONS_LOW",
        "label": "No External Citations",
        "tier": "Empirical",
        "tier_weight": 3,
        "source": "static",
        "pass_condition": "At least 1 outbound link to an external domain in page body",
        "threshold_description": "0 external body links detected; triggered on 500+ word pages",
        "page_type_conditions": ["word_count >= 500"],
        "fix_effort": "hard",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "The rewrite should signal WHERE a real citation could be placed by writing "
            "a sentence such as 'According to [Source Name], ...' — mark the placeholder "
            "with [CITATION NEEDED] so the human editor knows to insert the real link."
        ),
        "weak_check_note": None,
    },
    {
        "code": "QUOTATIONS_MISSING",
        "label": "No Quotations or Attribution",
        "tier": "Empirical",
        "tier_weight": 3,
        "source": "static",
        "pass_condition": "At least 1 blockquote OR attribution pattern (e.g. 'according to') present",
        "threshold_description": "blockquote_count + inline attribution patterns == 0; 500+ word pages",
        "page_type_conditions": ["word_count >= 500"],
        "fix_effort": "medium",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "Add at least one attributed quote or 'according to [authority]' phrase if the "
            "source material supports it. If no quote is available, add a sentence that "
            "references a named expert or organisation. Do NOT fabricate quotes."
        ),
        "weak_check_note": None,
    },
    {
        "code": "ORPHAN_CLAIM_TECHNICAL",
        "label": "Unsourced Technical Claims",
        "tier": "Empirical",
        "tier_weight": 3,
        "source": "static",
        "pass_condition": "Fewer than 3 unsourced factual claims, or ≥1 external link present",
        "threshold_description": "≥3 capability-verb sentences in first_150_words with 0 external links",
        "page_type_conditions": [
            "is_technical (TechArticle/HowTo schema or /how-to/|/guide/|/tutorial/ in URL)",
            "word_count >= 300",
        ],
        "fix_effort": "medium",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "For technical claims (sentences with verbs like 'supports', 'enables', "
            "'reduces'), add a citation marker [CITATION NEEDED] after each unsourced "
            "claim so the editor can add links. Do not invent sources."
        ),
        "weak_check_note": (
            "Stub implementation: only scans first_150_words with a narrow verb regex. "
            "Rarely fires in practice. Excluded from mandatory rubric section."
        ),
    },
    {
        "code": "QUERY_MATCH_SCORE",
        "label": "Query-Match Test",
        "tier": "Empirical",
        "tier_weight": 3,
        "source": "llm",
        "pass_condition": "score >= 0.70 (answered + 0.5 × partial) / total queries",
        "threshold_description": "LLM generates 7 queries; Yes=1.0, Partial=0.5, No=0.0; pass iff avg ≥ 0.70",
        "page_type_conditions": [],
        "fix_effort": "medium",
        "can_fix_without_fabrication": True,
        "rubric_instruction": (
            "The rewrite must directly answer the implicit questions a user would ask "
            "when landing on this page. Each major H2 section should open with a "
            "one-sentence direct answer before elaborating. Aim for the first 150 words "
            "to answer the primary question completely."
        ),
        "weak_check_note": None,
    },

    # ── Mechanistic tier (weight 2) ──────────────────────────────────────────
    {
        "code": "RAW_HTML_JS_DEPENDENT",
        "label": "JS-Only Content (SPA Shell)",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "static",
        "pass_condition": "is_spa_shell is False OR text_to_html_ratio >= 0.05",
        "threshold_description": "is_spa_shell=True AND text_to_html_ratio < 0.05",
        "page_type_conditions": [],
        "fix_effort": "infeasible",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "NOTE: This page renders content via JavaScript only, which AI crawlers "
            "cannot read. A content rewrite alone cannot fix this — the engineering team "
            "must add server-side rendering or a static HTML fallback. Flag this in your "
            "output as an infrastructure issue, not a content issue."
        ),
        "weak_check_note": None,
    },
    {
        "code": "JS_RENDERED_CONTENT_DIFFERS",
        "label": "JS-Gated Content",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "llm",
        "pass_condition": "Rendered token count is ≤ 120% of raw HTML token count",
        "threshold_description": "added_token_ratio > 0.20 (JS adds >20% new tokens)",
        "page_type_conditions": ["Playwright available"],
        "fix_effort": "infeasible",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "NOTE: Significant content is hidden behind JavaScript and invisible to AI "
            "crawlers. This requires engineering changes (SSR or pre-rendering). Flag "
            "as an infrastructure issue in your output."
        ),
        "weak_check_note": (
            "Requires Playwright; silently absent in most deployments. Cannot be fixed "
            "by content rewrite."
        ),
    },
    {
        "code": "CONTENT_CLOAKING_DETECTED",
        "label": "Possible Content Cloaking",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "llm",
        "pass_condition": "Topic Jaccard similarity (raw vs rendered) >= 0.30",
        "threshold_description": "topic_jaccard < 0.30 between raw HTML and JS-rendered content",
        "page_type_conditions": ["Playwright available"],
        "fix_effort": "infeasible",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "NOTE: Raw HTML and rendered page cover different topics. This is a server "
            "configuration issue. Flag as requiring engineering investigation."
        ),
        "weak_check_note": (
            "Requires Playwright; silently absent in most deployments. Cannot be fixed "
            "by content rewrite."
        ),
    },
    {
        "code": "UA_CONTENT_DIFFERS",
        "label": "AI Bot Content Stripping",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "llm",
        "pass_condition": "AI bot UA receives >= 80% of rendered token count",
        "threshold_description": "GPTBot or ClaudeBot token count < 80% of rendered count",
        "page_type_conditions": ["Playwright available"],
        "fix_effort": "infeasible",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "NOTE: AI crawlers (GPTBot, ClaudeBot) are receiving less content than "
            "normal users. This is a server-side bot detection or paywall issue. Flag "
            "as requiring engineering changes."
        ),
        "weak_check_note": (
            "Requires Playwright; silently absent in most deployments. Cannot be fixed "
            "by content rewrite."
        ),
    },
    {
        "code": "FIRST_VIEWPORT_NO_ANSWER",
        "label": "No Answer Signal in First 150 Words",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "static",
        "pass_condition": "first_150_words contains a definition, TL;DR, or 'is a' sentence",
        "threshold_description": (
            "No match for: tl;dr, in short, the short answer is, key takeaway, "
            "bottom line, '[Noun] is a/an [noun]', refers to, defined as"
        ),
        "page_type_conditions": ["word_count >= 200", "first_150_words available"],
        "fix_effort": "easy",
        "can_fix_without_fabrication": True,
        "rubric_instruction": (
            "The first 150 words MUST contain a direct definitional statement or "
            "answer signal. Lead with a sentence in the form '[Topic] is/refers to ...' "
            "or begin with 'TL;DR:' followed by a one-sentence summary. This is the "
            "highest-value change for AI citation."
        ),
        "weak_check_note": None,
    },
    {
        "code": "AUTHOR_BYLINE_MISSING",
        "label": "No Author Byline",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "static",
        "pass_condition": "page.author_detected is True",
        "threshold_description": "author_detected=False on article/blog pages",
        "page_type_conditions": [
            "is_article (BlogPosting/Article/NewsArticle schema or /blog/|/post/|/article/ in URL)"
        ],
        "fix_effort": "hard",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "Add an author attribution line. If the original author is known from the "
            "source text, include 'By [Author Name]' near the title. If unknown, add "
            "a placeholder: 'By [AUTHOR NAME — add byline here]'."
        ),
        "weak_check_note": None,
    },
    {
        "code": "DATE_PUBLISHED_MISSING",
        "label": "No Publication Date",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "static",
        "pass_condition": "datePublished in JSON-LD or og:article:published_time present",
        "threshold_description": "date_published field is None/empty on article pages",
        "page_type_conditions": [
            "is_article (BlogPosting/Article/NewsArticle schema or /blog/|/post/|/article/ in URL)"
        ],
        "fix_effort": "medium",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "If a publication date can be inferred from the content or context, add it "
            "as a visible date line near the title in the format 'Published: [Month DD, YYYY]'. "
            "Do not fabricate a date — use [PUBLICATION DATE] as a placeholder if unknown."
        ),
        "weak_check_note": None,
    },
    {
        "code": "DATE_MODIFIED_MISSING",
        "label": "No Last-Modified Date",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "static",
        "pass_condition": "dateModified in JSON-LD or og:article:modified_time present",
        "threshold_description": "date_modified field is None/empty on article pages",
        "page_type_conditions": [
            "is_article (BlogPosting/Article/NewsArticle schema or /blog/|/post/|/article/ in URL)"
        ],
        "fix_effort": "medium",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "Add a 'Last updated: [Month DD, YYYY]' line near the title if the update "
            "date can be determined. Use [LAST UPDATED DATE] as a placeholder if unknown."
        ),
        "weak_check_note": None,
    },
    {
        "code": "CODE_BLOCK_MISSING_TECHNICAL",
        "label": "No Code Examples on Technical Page",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "static",
        "pass_condition": "code_block_count > 0 OR page does not have numbered steps",
        "threshold_description": "has_numbered_steps=True AND code_block_count==0 on technical pages",
        "page_type_conditions": [
            "is_technical (TechArticle/HowTo schema or /how-to/|/guide/|/tutorial/ in URL)",
            "word_count >= 200",
        ],
        "fix_effort": "medium",
        "can_fix_without_fabrication": True,
        "rubric_instruction": (
            "For each numbered step that involves a command, configuration value, or "
            "code snippet, format it in a code block using triple backticks. If the "
            "original text describes code in prose ('run the install command'), extract "
            "it into a fenced code block. Do not invent commands."
        ),
        "weak_check_note": None,
    },
    {
        "code": "COMPARISON_TABLE_MISSING",
        "label": "Comparison Heading Without Table",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "static",
        "pass_condition": "table_count > 0 OR no comparison signal in headings",
        "threshold_description": "heading contains 'vs', 'versus', 'compared to', etc. AND table_count==0",
        "page_type_conditions": [],
        "fix_effort": "easy",
        "can_fix_without_fabrication": True,
        "rubric_instruction": (
            "If a heading contains a comparison signal (vs, versus, compared to), create "
            "a Markdown table below that heading listing the compared items with at least "
            "3 attributes per row. Extract data from the prose — do not invent attributes."
        ),
        "weak_check_note": None,
    },
    {
        "code": "CHUNKS_NOT_SELF_CONTAINED",
        "label": "Sections Lack Context",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "llm",
        "pass_condition": ">= 50% of H2/H3 sections are self-contained",
        "threshold_description": "LLM scores each section; ratio < 0.50 triggers finding",
        "page_type_conditions": [],
        "fix_effort": "medium",
        "can_fix_without_fabrication": True,
        "rubric_instruction": (
            "Each H2 and H3 section must be comprehensible without reading prior "
            "sections. At the start of each section, add a one-sentence anchor that "
            "restates the relevant context (e.g., 'When configuring X, the Y setting...'). "
            "Do not repeat entire explanations — one bridging sentence per section suffices."
        ),
        "weak_check_note": (
            "LLM threshold (< 50%) is high; many pages with 40-49% self-contained "
            "sections narrowly escape this check. Score instability across LLM runs."
        ),
    },
    {
        "code": "CENTRAL_CLAIM_BURIED",
        "label": "Main Point Buried",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "llm",
        "pass_condition": "LLM identifies central claim as appearing in first 150 words",
        "threshold_description": "appears_in_first_150_words=False from LLM analysis",
        "page_type_conditions": [],
        "fix_effort": "easy",
        "can_fix_without_fabrication": True,
        "rubric_instruction": (
            "Identify the page's central claim or key answer and ensure it appears "
            "within the first 150 words. Move or summarise the core takeaway to the "
            "opening paragraph. Do not bury the main point after introductory preamble."
        ),
        "weak_check_note": None,
    },
    {
        "code": "LINK_PROFILE_PROMOTIONAL",
        "label": "Mostly Promotional Outbound Links",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "static",
        "pass_condition": "promotional / external_body_total <= 0.80",
        "threshold_description": "promotional link ratio > 0.80 AND external_body_total > 0",
        "page_type_conditions": ["word_count >= 300", "has external links"],
        "fix_effort": "hard",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "If the page links predominantly to product/affiliate URLs, suggest replacing "
            "at least 2 promotional links with links to authoritative reference sources "
            "(research papers, government sites, industry reports). Mark suggestions as "
            "[REPLACE WITH REFERENCE LINK]."
        ),
        "weak_check_note": None,
    },
    {
        "code": "STRUCTURED_ELEMENTS_LOW",
        "label": "No Lists, Tables, or Code Blocks",
        "tier": "Mechanistic",
        "tier_weight": 2,
        "source": "static",
        "pass_condition": "structured_element_count > 0 on 500+ word pages",
        "threshold_description": "structured_element_count==0 AND word_count >= 500",
        "page_type_conditions": ["word_count >= 500"],
        "fix_effort": "easy",
        "can_fix_without_fabrication": True,
        "rubric_instruction": (
            "A 500+ word page with no lists, tables, or code blocks is harder for AI to "
            "chunk and cite. Add at least one of: a bulleted list summarising key points, "
            "a comparison table, or a numbered steps list. Extract these from the existing "
            "prose — do not add content that is not implied by the original."
        ),
        "weak_check_note": None,
    },

    # ── Conventional tier (weight 1) ─────────────────────────────────────────
    {
        "code": "JSON_LD_INVALID",
        "label": "Invalid JSON-LD Schema",
        "tier": "Conventional",
        "tier_weight": 1,
        "source": "static",
        "pass_condition": "All schema blocks have both @type and @context",
        "threshold_description": "At least 1 schema_block missing @type or @context",
        "page_type_conditions": ["has schema_blocks"],
        "fix_effort": "medium",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "Note: Invalid JSON-LD schema cannot be fixed by rewriting body content. "
            "Add a reminder at the end of the rewrite: "
            "'[DEV: Fix JSON-LD schema — add missing @type or @context to structured data]'."
        ),
        "weak_check_note": None,
    },
    {
        "code": "FAQ_SCHEMA_MISSING",
        "label": "FAQ Section Without FAQPage Schema",
        "tier": "Conventional",
        "tier_weight": 1,
        "source": "static",
        "pass_condition": "FAQPage in schema_types OR no FAQ heading AND < 3 question headings",
        "threshold_description": "FAQ heading or 3+ question H2s present, but no FAQPage schema",
        "page_type_conditions": [],
        "fix_effort": "medium",
        "can_fix_without_fabrication": False,
        "rubric_instruction": (
            "If the page has FAQ-style content (question headings or a FAQ section), "
            "add a reminder at the end of the rewrite: "
            "'[DEV: Add FAQPage JSON-LD schema to match the FAQ content in this page]'."
        ),
        "weak_check_note": None,
    },
    {
        "code": "PROMOTIONAL_CONTENT_INTERRUPTS",
        "label": "Promotional Content in Article",
        "tier": "Conventional",
        "tier_weight": 1,
        "source": "llm",
        "pass_condition": "Fewer than 2 mid-article sections classified as promotional",
        "threshold_description": "LLM classifies > 1 non-first/non-last sections as promotional",
        "page_type_conditions": [],
        "fix_effort": "medium",
        "can_fix_without_fabrication": True,
        "rubric_instruction": (
            "Remove or relocate CTA sections, sign-up prompts, and discount offers that "
            "interrupt the informational content. Move them to the end of the article or "
            "remove them entirely. Keep the article body focused on informational content."
        ),
        "weak_check_note": (
            "Only first 300 chars per section are sent to LLM, so promotional copy "
            "embedded mid-section is missed. High false-negative rate."
        ),
    },
]

# Checks with known reliability gaps — excluded from mandatory rubric instructions
WEAK_CHECKS: list[dict] = [c for c in GEO_CHECKS if c["weak_check_note"] is not None]
WEAK_CHECK_CODES: set[str] = {c["code"] for c in WEAK_CHECKS}


# ---------------------------------------------------------------------------
# Scoring helpers — mirror geo_analyzer._compute_scores()
# ---------------------------------------------------------------------------

def _effective_score(finding: dict) -> float:
    """Mirror geo_analyzer._compute_scores() score extraction."""
    pass_fail = finding.get("pass_fail", "fail")
    if pass_fail == "pass":
        return float(finding.get("score", 1.0))
    if pass_fail == "info":
        return 0.75
    return 0.0  # "fail"


def compute_score_from_findings(findings: list[dict]) -> float:
    """
    Compute overall GEO score from a list of finding dicts.

    Mirrors geo_analyzer._compute_scores() exactly.
    findings dicts must have: evidence_tier, pass_fail, score.
    Returns 1.0 when findings is empty (no failing checks = clean).
    """
    total_weight = 0.0
    weighted_score = 0.0
    for f in findings:
        w = TIER_WEIGHTS.get(f.get("evidence_tier", "Conventional"), 1)
        total_weight += w
        weighted_score += w * _effective_score(f)
    if total_weight > 0:
        return round(weighted_score / total_weight, 4)
    return 1.0


# ---------------------------------------------------------------------------
# 90-path calculator
# ---------------------------------------------------------------------------

def compute_90_path(
    current_findings: list[dict],
    target: float = 0.90,
) -> dict:
    """
    Classify currently failing GEO checks by their importance to reaching `target`.

    A check is **mandatory** if fixing everything else but this check still leaves
    overall_score < target (i.e. this check alone holds you below the target).
    Equivalently, s_c (effective score) < target.

    A check is **high_value** if fixing it alone would raise overall_score by >= 0.05.

    Returns dict with keys:
        current_score, target, mandatory, high_value, low_value
        Each bucket is a list of dicts: {code, label, tier, gain, score_if_fixed}.
    """
    current_score = compute_score_from_findings(current_findings)

    mandatory = []
    high_value = []
    low_value = []

    for i, finding in enumerate(current_findings):
        remaining = [f for j, f in enumerate(current_findings) if j != i]
        score_if_fixed = compute_score_from_findings(remaining)
        gain = round(score_if_fixed - current_score, 4)

        entry = {
            "code": finding.get("code", ""),
            "label": finding.get("label", finding.get("code", "")),
            "tier": finding.get("evidence_tier", ""),
            "tier_weight": TIER_WEIGHTS.get(finding.get("evidence_tier", ""), 1),
            "pass_fail": finding.get("pass_fail", "fail"),
            "current_score": _effective_score(finding),
            "gain": gain,
            "score_if_fixed": score_if_fixed,
            "can_fix_without_fabrication": _check_can_fix(finding.get("code", "")),
            "is_weak_check": finding.get("code", "") in WEAK_CHECK_CODES,
        }

        # Mandatory: even if all others fixed, this one alone blocks reaching target.
        # For fail checks, s_c = 0.0 < target (always mandatory).
        # For pass checks (QUERY_MATCH_SCORE), s_c = actual score.
        s_c = _effective_score(finding)
        if s_c < target:
            mandatory.append(entry)
        elif gain >= 0.05:
            high_value.append(entry)
        else:
            low_value.append(entry)

    _sort_by_gain = lambda lst: sorted(lst, key=lambda x: x["gain"], reverse=True)

    return {
        "current_score": current_score,
        "target": target,
        "mandatory": _sort_by_gain(mandatory),
        "high_value": _sort_by_gain(high_value),
        "low_value": _sort_by_gain(low_value),
    }


def _check_can_fix(code: str) -> bool:
    """Look up can_fix_without_fabrication for a given check code."""
    for c in GEO_CHECKS:
        if c["code"] == code:
            return c["can_fix_without_fabrication"]
    return True
