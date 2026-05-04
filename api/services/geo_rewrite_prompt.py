"""
GEO Rewrite Prompt Generator.

Reverse-engineers what a 90+ GEO score requires and produces a structured
LLM prompt instructing a writing LLM to rewrite a page to meet those thresholds.

Also provides execute_rewrite_best_of_n() for best-of-5 rewrite execution.

Spec: docs/implementation_plan_geo_rewrite_prompt_2026-05-03.md#Phase-C
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page-type detection
# ---------------------------------------------------------------------------

_ARTICLE_SCHEMAS = frozenset({"BlogPosting", "Article", "NewsArticle"})
_TECHNICAL_SCHEMAS = frozenset({"TechArticle", "HowTo"})
_ARTICLE_URL_SEGS = ("/blog/", "/post/", "/article/", "/news/", "/stories/")
_TECHNICAL_URL_SEGS = ("/how-to/", "/guide/", "/tutorial/", "/setup/")
_FAQ_RE = re.compile(r"\bfrequently\s+asked\s+questions?\b|\bfaq\b", re.I)
_COMPARISON_RE = re.compile(
    r"\b(vs\.?|versus|compared to|difference between|comparison of)\b", re.I
)


def _detect_page_type(
    url: str,
    schema_types: list[str],
    headings: list[dict],
) -> str:
    """
    Infer content type for page-type-conditional rubric instructions.

    Returns one of: "article" | "technical" | "faq" | "comparison" | "general"
    """
    heading_texts = " ".join(h.get("text", "") for h in headings)

    if any(t in schema_types for t in _ARTICLE_SCHEMAS) or any(
        seg in url for seg in _ARTICLE_URL_SEGS
    ):
        return "article"
    if any(t in schema_types for t in _TECHNICAL_SCHEMAS) or any(
        seg in url for seg in _TECHNICAL_URL_SEGS
    ):
        return "technical"
    if _FAQ_RE.search(heading_texts) or sum(
        1
        for h in headings
        if re.match(
            r"^(what|how|why|when|where|who|which|can|do|does|is|are)\b.*\?$",
            h.get("text", "").strip(),
            re.I,
        )
    ) >= 3:
        return "faq"
    if _COMPARISON_RE.search(heading_texts):
        return "comparison"
    return "general"


# ---------------------------------------------------------------------------
# Rubric builder — translates 90-path into prompt instructions
# ---------------------------------------------------------------------------

def _build_rubric_section(path_result: dict, page_type: str) -> str:
    """
    Produce the rubric section (d) of the prompt from the 90-path result.

    Mandatory checks get HIGH PRIORITY labels; high-value and low-value
    get appropriately scoped labels. Weak checks are noted as unreliable.
    Infeasible checks get infrastructure-note instructions instead of content fixes.
    """
    lines: list[str] = []
    current_score = path_result.get("current_score", 0.0)
    target = path_result.get("target", 0.90)

    lines.append(
        f"Current GEO score: {current_score:.0%}  |  Target: {target:.0%}\n"
    )

    def _add_checks(bucket: list[dict], priority: str) -> None:
        if not bucket:
            return
        lines.append(f"\n### {priority} CHANGES\n")
        for entry in bucket:
            code = entry["code"]
            label = entry["label"]
            gain = entry["gain"]
            fixable = entry["can_fix_without_fabrication"]
            is_weak = entry.get("is_weak_check", False)

            prefix = f"[{code}]"
            if is_weak:
                prefix += " ⚠️ UNRELIABLE CHECK — apply only if clearly applicable"
            if not fixable:
                prefix += " 🔧 REQUIRES ENGINEERING (flag in output, do not fabricate)"

            lines.append(f"**{label}** {prefix}")
            lines.append(f"Score gain if fixed: +{gain:.0%}")

            # Fetch the rubric_instruction from GEO_CHECKS
            from api.services.geo_scoring_map import GEO_CHECKS
            instruction = next(
                (c["rubric_instruction"] for c in GEO_CHECKS if c["code"] == code),
                "Apply best judgement based on the check label.",
            )
            lines.append(instruction)
            lines.append("")

    _add_checks(path_result.get("mandatory", []), "MANDATORY")
    _add_checks(path_result.get("high_value", []), "HIGH VALUE")
    _add_checks(path_result.get("low_value", []), "LOW VALUE")

    if not (
        path_result.get("mandatory")
        or path_result.get("high_value")
        or path_result.get("low_value")
    ):
        lines.append(
            "No failing GEO checks detected. The page already meets the 90% threshold. "
            "Rewrite to improve clarity and answer-signal density without changing structure."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt generator — 9 sections
# ---------------------------------------------------------------------------

def generate_rewrite_prompt(
    report: dict,
    page_type: str,
    url: str = "",
) -> dict:
    """
    Generate a structured rewrite prompt from a GEOReport dict.

    Args:
        report:    GEOReport.to_dict() output with 'findings', 'overall_score', etc.
        page_type: Output of _detect_page_type() — article | technical | faq | comparison | general
        url:       The page URL (used for context only).

    Returns dict with keys:
        system_prompt: str — the complete system prompt for the rewriting LLM
        current_score: float
        target_score: float
        mandatory_count: int
        fixable_count: int
        page_type: str
    """
    from api.services.geo_scoring_map import compute_90_path

    findings = report.get("findings", [])
    current_score = report.get("overall_score", 1.0)
    path = compute_90_path(findings, target=0.90)

    mandatory_count = len(path.get("mandatory", []))
    fixable_count = sum(
        1
        for bucket in (path["mandatory"], path["high_value"], path["low_value"])
        for entry in bucket
        if entry.get("can_fix_without_fabrication")
    )

    rubric = _build_rubric_section(path, page_type)

    prompt = f"""\
# GEO CONTENT REWRITE INSTRUCTIONS

## (a) ROLE

You are an expert content strategist specialising in Generative Engine Optimisation (GEO).
You rewrite web content so that large language models can accurately retrieve, cite, and
quote it in AI-powered search results.

You have access to a detailed scoring rubric derived from the page's actual GEO audit.
Your output will be scored by the same rubric — write to satisfy the checks, not to pad
the content.

---

## (b) INPUT CONTRACT

You will receive:
1. **Page content** — the original text of the page to rewrite (Markdown or plain text).
2. **Page type** — `{page_type}` — determines which conditional checks apply.
3. **Page URL** — `{url or "(not provided)"}` — for context only; do not include in output.

The page content is provided immediately after these instructions, delimited by:
```
===BEGIN_CONTENT===
...original content...
===END_CONTENT===
```

---

## (c) OUTPUT CONTRACT

Return **only** the rewritten content in Markdown, with no preamble, no explanation,
and no summary of changes. Do not add a "Here is the rewritten version:" header.

Do NOT shorten the content unless a section is purely promotional. Preserve all
headings at the same nesting level. Preserve all factual claims.

At the very end of the rewrite (after the last paragraph), append a brief
**GEO NOTES** section listing any placeholders you added, in this format:

```
---
GEO NOTES
- [CITATION NEEDED] added at: <brief location description>
- [AUTHOR NAME] placeholder added near title
```

Omit the GEO NOTES section if you added no placeholders.

---

## (d) THE RUBRIC

{rubric}

---

## (e) HARD PROHIBITIONS

1. **Do not fabricate statistics.** If a statistic is needed, write
   `[STATISTIC: describe what kind of figure is needed here]` as a placeholder.

2. **Do not fabricate citations.** Write `[CITATION NEEDED: describe source type]`
   to mark where a real citation should go.

3. **Do not invent quotes.** Write `[QUOTE NEEDED: describe speaker/context]`
   if attribution would help but no real quote is available.

4. **Do not add new factual claims** not implied by the original text.

5. **Do not delete factual content.** You may restructure and rephrase, but
   do not remove substantive information.

6. **Do not fabricate author names or publication dates.** Use placeholder
   patterns: `[AUTHOR NAME]`, `[PUBLICATION DATE]`, `[LAST UPDATED DATE]`.

7. **Do not add advertising, product recommendations, or promotional content.**

8. **Do not summarise the article at the end** unless the original had a summary section.

---

## (f) PRESERVATION CONSTRAINTS

1. **Keep the author's register.** If the original uses first-person ("we", "I"),
   maintain that. If formal third-person, maintain that.

2. **Keep the author's vocabulary.** Do not swap domain-specific terms for generic ones
   (e.g., do not replace "crawl budget" with "the amount of crawling done").

3. **Keep all heading levels.** An H2 stays an H2. An H3 stays an H3. Do not flatten
   the heading hierarchy.

4. **Keep the page's scope.** Do not add new topics not present in the original.

5. **Keep internal links.** Do not remove `[text](url)` links from the original.

---

## (g) UNCERTAINTY HANDLING

When the original content is ambiguous or missing required information:

| Missing element | Placeholder to use |
|---|---|
| Statistic | `[STATISTIC: type of data needed]` |
| Citation / source link | `[CITATION NEEDED: source type]` |
| Quote or attribution | `[QUOTE NEEDED: speaker/context]` |
| Author name | `[AUTHOR NAME]` |
| Publication date | `[PUBLICATION DATE]` |
| Last-updated date | `[LAST UPDATED DATE]` |
| Code example | `[CODE EXAMPLE: language and what it should show]` |
| Reference link URL | `[LINK: describe the type of authoritative source]` |

Placeholders must appear inline in the text at the point where the information
is needed, not collected at the end.

---

## (h) ITERATION INSTRUCTION

This is one attempt in a best-of-{_BEST_OF_N} batch. Each attempt is independently
scored against the GEO rubric. Focus on maximum rubric compliance rather than
stylistic elegance — the scorer rewards concrete signals (statistics, answer sentences,
code blocks, structured elements) over fluency.

If you reach the end of the content and realise you missed a mandatory check,
go back and add the required element rather than noting it in GEO NOTES.

---

## (i) STYLE CONSTRAINTS — ANTI-AI WRITING RULES

The rewrite MUST avoid the following patterns that mark content as AI-generated:

**Banned opening phrases (never start a sentence or section with):**
- "In today's world" / "In today's [adjective] landscape"
- "It is worth noting that" / "It is important to note that"
- "Let's dive in" / "Let's explore" / "Let's take a look at"
- "Delve into" / "Harness the power of" / "Unleash the potential"
- "Seamless" / "Cutting-edge" / "Game-changing" / "Transformative"
- "In conclusion" (unless the original had this)
- "To summarise" / "In summary" (unless the original had a summary section)
- "As an AI language model"

**Structural prohibitions:**
- No more than 2 bullet lists per 500 words (convert excess to prose)
- Do not start every list item with the same grammatical structure (e.g., all gerunds)
- Do not add a "Summary" or "Key Takeaways" section unless the original had one
- Do not use passive constructions for more than 20% of sentences
- Do not make every sentence roughly the same length — vary between short punchy
  sentences and longer explanatory ones

**Required style rules:**
- Preserve contractions if the original used them (don't, it's, we're)
- Vary sentence length deliberately — mix short sentences with longer ones
- Lead with the concrete before the abstract (example before principle)
- Prefer active verbs over nominalised verbs ("we measure" not "we perform measurement of")
- Use specific numbers and named entities wherever the original justifies them
"""

    return {
        "system_prompt": prompt,
        "current_score": current_score,
        "target_score": 0.90,
        "mandatory_count": mandatory_count,
        "fixable_count": fixable_count,
        "page_type": page_type,
        "findings_count": len(findings),
    }


# ---------------------------------------------------------------------------
# Synthetic ParsedPage builder (for best-of-5 static scoring)
# ---------------------------------------------------------------------------

_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.M)
_MD_CODE_RE = re.compile(r"```[\s\S]*?```", re.M)
_MD_TABLE_RE = re.compile(r"^\|.+\|$", re.M)
_MD_UL_RE = re.compile(r"^[-*+]\s+", re.M)
_MD_OL_RE = re.compile(r"^\d+[.)]\s+", re.M)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_MD_BLOCKQUOTE_RE = re.compile(r"^>\s+.+", re.M)
_MD_AUTHOR_RE = re.compile(r"\bBy\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b|\bAuthor:\s*\S+")
_MD_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
)

# Kept at module level so _generate_one_rewrite can use it via import
_BEST_OF_N = 5


def _build_synthetic_parsed_page(
    url: str,
    markdown_content: str,
    page_type: str = "general",
):
    """
    Build a ParsedPage-compatible dict from rewritten markdown content.

    Used to run _run_geo_checks() on rewrite candidates without re-fetching URLs.
    Returns a dict with all GEO-relevant ParsedPage fields.
    """
    # Strip code blocks before counting words (code isn't "visible text")
    no_code = _MD_CODE_RE.sub(" ", markdown_content)

    # word_count: simple token count (consistent with issue_checker expectations)
    words = re.findall(r"\w+", no_code)
    word_count = len(words)

    # first_150_words: preserve original punctuation (including "%" and ".") so that
    # stat-detection and answer-signal regexes work correctly.  Split on whitespace
    # (not word boundaries) so "27.6%" and "according to" patterns survive.
    _tokens = no_code.split()
    first_150 = " ".join(_tokens[:150])

    # Headings
    headings_outline = [
        {"level": len(m.group(1)), "text": m.group(2).strip()}
        for m in _MD_HEADING_RE.finditer(markdown_content)
    ]

    # Code blocks
    code_block_count = len(_MD_CODE_RE.findall(markdown_content))

    # Tables
    table_rows = _MD_TABLE_RE.findall(markdown_content)
    table_count = 1 if len(table_rows) >= 2 else 0

    # Lists
    ul_count = len(_MD_UL_RE.findall(markdown_content))
    ol_count = len(_MD_OL_RE.findall(markdown_content))
    list_count = min(ul_count + ol_count, 1)  # at least one list = 1 structured element

    # Structured elements
    structured_element_count = list_count + table_count + min(code_block_count, 1)

    # External links
    links = []
    for m in _MD_LINK_RE.finditer(markdown_content):
        from api.crawler.parser import ParsedLink  # type: ignore[attr-defined]
        from urllib.parse import urlparse
        href = m.group(2)
        page_netloc = urlparse(url).netloc.lstrip("www.")
        link_netloc = urlparse(href).netloc.lstrip("www.")
        is_internal = link_netloc == page_netloc
        links.append(ParsedLink(url=href, text=m.group(1), is_internal=is_internal))

    # Blockquotes
    blockquote_count = len(_MD_BLOCKQUOTE_RE.findall(markdown_content))

    # Author / date signals
    author_detected = bool(_MD_AUTHOR_RE.search(markdown_content[:500]))
    date_match = _MD_DATE_RE.search(markdown_content[:500])
    date_published = date_match.group(0) if date_match else None

    # Page-type-derived schema_types (approximate)
    schema_map = {
        "article": ["Article"],
        "technical": ["TechArticle"],
        "faq": [],
        "comparison": [],
        "general": [],
    }
    schema_types = schema_map.get(page_type, [])

    return {
        # Core fields used by _run_geo_checks
        "url": url,
        "is_indexable": True,
        "is_spa_shell": False,
        "text_to_html_ratio": 0.5,  # markdown has no HTML overhead
        "word_count": word_count,
        "schema_types": schema_types,
        "schema_blocks": [],
        "headings_outline": headings_outline,
        "links": links,
        "first_150_words": first_150,
        "blockquote_count": blockquote_count,
        "author_detected": author_detected,
        "date_published": date_published,
        "date_modified": None,
        "code_block_count": code_block_count,
        "table_count": table_count,
        "structured_element_count": structured_element_count,
    }


# ---------------------------------------------------------------------------
# Content-compliance scoring (5 always-applicable GEO checks)
# ---------------------------------------------------------------------------
# Fixed denominator = 13 so baseline and all variants are on the same scale.
# Checks are implemented directly here (not via _run_static_geo_checks) so we
# can apply rewrite-friendly rules:
#   - [CITATION NEEDED] / [LINK: ...] placeholders count as external citations
#   - [QUOTE NEEDED] / [STATISTIC: N] placeholders count as their category
#   - Statistics are searched in the FULL text, not just the first 150 words
#   - Answer signal is still only checked in the first 150 words

_CONTENT_SCORE_WEIGHT = {
    "STATISTICS_COUNT_LOW": 3,      # Empirical
    "EXTERNAL_CITATIONS_LOW": 3,    # Empirical
    "QUOTATIONS_MISSING": 3,        # Empirical
    "FIRST_VIEWPORT_NO_ANSWER": 2,  # Mechanistic
    "STRUCTURED_ELEMENTS_LOW": 2,   # Mechanistic
}
_CONTENT_SCORE_TOTAL_WEIGHT = 13  # sum of above

# Regex for GEO placeholders inserted by the rewriting LLM
_PLACEHOLDER_CITATION_RE = re.compile(
    r"\[CITATION\s+NEEDED[^\]]*\]|\[LINK[^\]]*\]|\[SOURCE[^\]]*\]",
    re.I,
)
_PLACEHOLDER_QUOTE_RE = re.compile(r"\[QUOTE\s+NEEDED[^\]]*\]", re.I)
_PLACEHOLDER_STAT_RE = re.compile(r"\[STATISTIC[^\]]*\]", re.I)

# Stat regex (same pattern as issue_checker._STAT_RE)
_STAT_RE_FULL = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?\s*"
    r"(?:%|percent|kb|mb|gb|ms|seconds?|minutes?|hours?|days?|months?|years?"
    r"|users?|customers?|companies|organisations?|organizations?"
    r"|times?\s+faster|times?\s+more|\dx?\s+faster|\dx?\s+more"
    r"|Gbps|Mbps|fps|rpm|mph|km|mi|kg|lbs?"
    r"|million|billion|trillion|thousand|hundred)(?:\b|(?=\s|$))"
    r"|\b(?:19|20)\d{2}\b"
    r"|\b\d+\s+(?:of|out\s+of)\s+\d+\b",
    re.I,
)
_ATTRIBUTION_RE_FULL = re.compile(
    r'(?:according\s+to|says?|said|stated|noted|wrote|reports?|"[^"]{10,200}"\s*—)',
    re.I,
)


def _content_score(url: str, content: str, page_type: str = "general") -> tuple[int, float]:
    """
    Score rewrite content on 5 GEO content signals, returning (fail_count, score 0-1).

    Uses a fixed denominator (weight=13) so baseline and all variant scores
    are directly comparable.  Placeholder citations/quotes/stats from the
    rewriting LLM are counted as passes so the scoring rewards good rewrites
    that identify WHERE evidence should go, even if the editor must fill it in.
    """
    tokens = content.split()
    word_count = len(tokens)
    first_150 = " ".join(tokens[:150])

    fails: set[str] = set()

    # Check 1 — Statistics: search FULL text + placeholders
    if word_count >= 500:
        has_stat = (
            bool(_STAT_RE_FULL.search(content))
            or bool(_PLACEHOLDER_STAT_RE.search(content))
        )
        if not has_stat:
            fails.add("STATISTICS_COUNT_LOW")

    # Check 2 — External citations: markdown links OR [CITATION NEEDED] placeholders
    if word_count >= 500:
        has_citation = (
            bool(_MD_LINK_RE.search(content))         # [text](https://...)
            or bool(_PLACEHOLDER_CITATION_RE.search(content))  # [CITATION NEEDED...]
        )
        if not has_citation:
            fails.add("EXTERNAL_CITATIONS_LOW")

    # Check 3 — Quotations/attribution: full text + placeholders
    if word_count >= 500:
        has_quote = (
            bool(_MD_BLOCKQUOTE_RE.search(content))   # > blockquote
            or bool(_ATTRIBUTION_RE_FULL.search(content))  # "according to" etc.
            or bool(_PLACEHOLDER_QUOTE_RE.search(content))  # [QUOTE NEEDED...]
        )
        if not has_quote:
            fails.add("QUOTATIONS_MISSING")

    # Check 4 — Answer signal in first 150 words (intentionally strict: first viewport only)
    if word_count >= 200:
        try:
            from api.crawler.issue_checker import _has_answer_signal  # type: ignore
            if not _has_answer_signal(first_150):
                fails.add("FIRST_VIEWPORT_NO_ANSWER")
        except Exception:
            pass  # skip check if import fails

    # Check 5 — Structured elements: list items, tables, or code blocks anywhere
    if word_count >= 500:
        has_structure = (
            bool(_MD_UL_RE.search(content))
            or bool(_MD_OL_RE.search(content))
            or bool(_MD_TABLE_RE.search(content))
            or bool(_MD_CODE_RE.search(content))
        )
        if not has_structure:
            fails.add("STRUCTURED_ELEMENTS_LOW")

    fail_weight = sum(_CONTENT_SCORE_WEIGHT.get(c, 0) for c in fails)
    score = round(1.0 - fail_weight / _CONTENT_SCORE_TOTAL_WEIGHT, 4)
    return len(fails), score


def _project_score(
    original_findings: list[dict],
    url: str,
    markdown_content: str,
    page_type: str = "general",
) -> tuple[int, float]:
    """
    Project the content-compliance score for a rewrite variant.

    Scores are computed from the 5 content-measurable static GEO checks with a
    fixed denominator (weight=13).  This keeps both the baseline (original page)
    and each variant on the same scale, so improvement is meaningful.

    The original geo_report score (LLM-only) is intentionally excluded here:
    it cannot be cheaply re-run per variant, so mixing it with static checks
    produced a collapsed denominator (the bug: 79% → 10%).

    Returns (content_fail_count, projected_score).
    """
    return _content_score(url, markdown_content, page_type)


def _run_static_geo_checks(
    url: str,
    markdown_content: str,
    page_type: str = "general",
) -> list[str]:
    """Run _run_geo_checks on synthetic page, return list of fired issue codes."""
    from api.crawler.issue_checker import _run_geo_checks  # type: ignore[attr-defined]

    page_dict = _build_synthetic_parsed_page(url, markdown_content, page_type)

    class _SyntheticPage:
        def __init__(self, d: dict):
            for k, v in d.items():
                setattr(self, k, v)

    page = _SyntheticPage(page_dict)
    issues: list = []
    try:
        _run_geo_checks(page, url, issues)
    except Exception as e:
        logger.warning("geo_check_on_synthetic_page_failed", extra={"error": str(e)})
    return [getattr(i, "issue_code", getattr(i, "code", "")) for i in issues]


def _score_markdown(url: str, markdown_content: str, page_type: str = "general") -> int:
    """
    Score a markdown rewrite by counting how many static GEO issues fire.

    Lower is better — fewer issues = better candidate.
    """
    return len(_run_static_geo_checks(url, markdown_content, page_type))


# ---------------------------------------------------------------------------
# Query-match re-scoring for rewrite variants
# ---------------------------------------------------------------------------

async def _score_rewrite_query_match(
    rewrite_text: str,
    original_query_table: list[dict],
    model: str,
    provider: str,
) -> float:
    """
    Re-evaluate how well the rewrite text answers the original page's AI queries.

    Uses the same queries from the cached GEO report (not re-generating them),
    then asks the LLM to score each query Yes/Partial/No.

    Returns a 0.0–1.0 score matching the QUERY_MATCH_SCORE calculation:
        (answered + 0.5 × partial) / total_queries
    """
    from api.services.geo_analyzer import _call_ai  # type: ignore

    queries = [q.get("query", "").strip() for q in original_query_table if q.get("query")]
    if not queries:
        return 0.0

    q_block = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(queries))
    # Truncate rewrite to ~3000 chars to stay within token budget
    text_sample = rewrite_text[:3000]

    prompt = (
        f"You are scoring how well a web page answers user questions.\n\n"
        f"PAGE TEXT:\n{text_sample}\n\n"
        f"QUESTIONS:\n{q_block}\n\n"
        f"For each question respond with exactly one of: Yes / Partial / No\n"
        f"Output one answer per line, in question order. No other text."
    )
    try:
        response = await _call_ai(prompt, model, provider)
        lines = [ln.strip().lower() for ln in response.strip().splitlines() if ln.strip()]
        answered = sum(1 for ln in lines if ln.startswith("yes"))
        partial = sum(1 for ln in lines if ln.startswith("partial"))
        total = len(queries)
        score = (answered + 0.5 * partial) / total if total else 0.0
        return round(score, 4)
    except Exception as e:
        logger.warning("query_match_rescore_failed", extra={"error": str(e)})
        return 0.0


def _project_score_from_findings(
    original_findings: list[dict],
    new_query_match_score: float,
) -> float:
    """
    Re-compute the overall GEO score by replacing QUERY_MATCH_SCORE with
    the re-evaluated score for a rewrite variant.  All other findings
    (CHUNKS_NOT_SELF_CONTAINED, CENTRAL_CLAIM_BURIED, etc.) are kept unchanged.

    Returns projected_score (0.0–1.0).
    """
    from api.services.geo_scoring_map import compute_score_from_findings

    updated: list[dict] = []
    for f in original_findings:
        if f.get("code") == "QUERY_MATCH_SCORE":
            updated.append({
                **f,
                "score": new_query_match_score,
                "pass_fail": "pass" if new_query_match_score >= 0.70 else "fail",
            })
        else:
            updated.append(f)

    # If there was no QUERY_MATCH_SCORE in the original findings, add it
    if not any(f.get("code") == "QUERY_MATCH_SCORE" for f in original_findings):
        updated.append({
            "code": "QUERY_MATCH_SCORE",
            "evidence_tier": "Empirical",
            "pass_fail": "pass" if new_query_match_score >= 0.70 else "fail",
            "score": new_query_match_score,
        })

    return compute_score_from_findings(updated)


# ---------------------------------------------------------------------------
# Best-of-N rewrite executor
# ---------------------------------------------------------------------------

async def _generate_one_rewrite(
    page_content: str,
    system_prompt: str,
    model: str,
    provider: str,
    variant_index: int,
) -> dict:
    """Generate a single rewrite candidate and return with index."""
    from api.services.geo_analyzer import _call_ai

    full_prompt = (
        f"{system_prompt}\n\n"
        f"===BEGIN_CONTENT===\n{page_content}\n===END_CONTENT==="
    )
    try:
        text = await _call_ai(full_prompt, model, provider)
        return {"index": variant_index, "text": text, "error": None}
    except Exception as e:
        logger.warning("rewrite_variant_failed", extra={"index": variant_index, "error": str(e)})
        return {"index": variant_index, "text": "", "error": str(e)}


async def stream_rewrite_variants(
    page_content: str,
    rewrite_prompt_result: dict,
    model: str,
    provider: str,
    url: str = "",
    page_type: str = "general",
    n: int = _BEST_OF_N,
    original_findings: list[dict] | None = None,
    original_query_table: list[dict] | None = None,
):
    """
    AsyncGenerator that runs n rewrites sequentially, yielding one SSE event
    per completed variant and a final 'done' event with the winner.

    Projected score: 80% query coverage (same queries re-scored vs the rewrite)
    + 20% content quality (5 static checks: stats, citations, quotes, viewport
    answer, structure).  This makes the issues count affect the score so variants
    with the same query coverage but different issue counts are distinguishable.

    Yields JSON-encoded strings in SSE format: "data: {...}\\n\\n"
    """
    import json as _json

    system_prompt = rewrite_prompt_result["system_prompt"]
    geo_report_score = rewrite_prompt_result.get("current_score", 0.0)
    findings_for_projection = original_findings or []
    query_table = original_query_table or []

    variants: list[dict] = []

    for i in range(n):
        result = await _generate_one_rewrite(page_content, system_prompt, model, provider, i)

        if result.get("text"):
            issues, c_score = _content_score(url, result["text"], page_type)
            if query_table:
                new_qm_score = await _score_rewrite_query_match(
                    result["text"], query_table, model, provider
                )
                query_projected = _project_score_from_findings(findings_for_projection, new_qm_score)
                # Blend: 80% query coverage + 20% content quality so issue
                # count actually affects the projected score
                projected_score = round(0.8 * query_projected + 0.2 * c_score, 4)
            else:
                projected_score = c_score
        else:
            issues, projected_score = 999, 0.0

        result["issues"] = issues
        result["projected_score"] = projected_score
        variants.append(result)

        event = {
            "type": "variant",
            "index": i,
            "issues": issues,
            "projected_score": projected_score,
            "error": result.get("error"),
            "text": result.get("text", ""),
            "preview": (result["text"][:120] + "…") if result.get("text") else None,
            "completed": i + 1,
            "total": n,
        }
        yield f"data: {_json.dumps(event)}\n\n"

    # Pick winner — highest projected score, tie-break by fewest static issues
    successful = [v for v in variants if not v.get("error") and v.get("text")]
    winner = (
        max(successful, key=lambda v: (v["projected_score"], -v["issues"]))
        if successful else (variants[0] if variants else {})
    )
    winner_index = winner.get("index", 0)

    # Rank all variants by projected_score descending
    ranked = sorted(successful, key=lambda v: (v["projected_score"], -v["issues"]), reverse=True)
    for v in variants:
        v["rank"] = next((r + 1 for r, rv in enumerate(ranked) if rv["index"] == v["index"]), None)

    done_event = {
        "type": "done",
        "winner_index": winner_index,
        "winner_issues": winner.get("issues", 999),
        "winner_projected_score": winner.get("projected_score", 0.0),
        "winner_text": winner.get("text", ""),
        "variants": [
            {
                "index": v["index"],
                "issues": v.get("issues", 999),
                "projected_score": v.get("projected_score", 0.0),
                "rank": v.get("rank"),
                "error": v.get("error"),
                "text": v.get("text", ""),
                "preview": (v["text"][:120] + "…") if v.get("text") else None,
            }
            for v in variants
        ],
        "improvement": {
            "baseline_score": baseline_score,
            "winner_score": winner.get("projected_score", 0.0),
            "gain": round(winner.get("projected_score", 0.0) - baseline_score, 3),
            "geo_report_score": geo_report_score,
        },
    }
    yield f"data: {_json.dumps(done_event)}\n\n"


async def execute_rewrite_best_of_n(
    page_content: str,
    rewrite_prompt_result: dict,
    model: str,
    provider: str,
    url: str = "",
    page_type: str = "general",
    n: int = _BEST_OF_N,
) -> dict:
    """
    Generate n rewrite variants in parallel, score each with static GEO checks,
    and return the variant with the fewest issues (lowest score = best).

    Args:
        page_content:         Original page text to rewrite.
        rewrite_prompt_result: Return value of generate_rewrite_prompt().
        model:                 LLM model ID.
        provider:              "openai" | "gemini".
        url:                   Page URL (used for issue_checker domain checks).
        page_type:             Article | technical | faq | comparison | general.
        n:                     Number of variants to generate (default 5).

    Returns dict with:
        winner_text:     str — best rewrite text
        winner_index:    int — 0-based index of best variant
        winner_issues:   int — issue count of winner
        variants:        list[dict] — all variants with text, issues, rank
        improvement:     dict — comparison between original_score and projected_score
    """
    system_prompt = rewrite_prompt_result["system_prompt"]
    current_score = rewrite_prompt_result.get("current_score", 0.0)

    # Generate all variants in parallel
    tasks = [
        _generate_one_rewrite(page_content, system_prompt, model, provider, i)
        for i in range(n)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    variants = []
    for res in results:
        if isinstance(res, Exception):
            variants.append({"index": len(variants), "text": "", "error": str(res), "issues": 999})
        elif res.get("error"):
            variants.append({**res, "issues": 999})
        else:
            issue_count = _score_markdown(url, res["text"], page_type)
            variants.append({**res, "issues": issue_count})

    # Sort by issue count ascending (fewer = better)
    ranked = sorted(
        [v for v in variants if not v.get("error")],
        key=lambda v: v["issues"],
    )
    if not ranked:
        # All variants failed — fall back to first result's text if any
        fallback = next((v for v in variants if v.get("text")), variants[0] if variants else {})
        return {
            "winner_text": fallback.get("text", ""),
            "winner_index": fallback.get("index", 0),
            "winner_issues": fallback.get("issues", 999),
            "variants": variants,
            "improvement": {"original_score": current_score, "projected_issues": 999},
        }

    winner = ranked[0]
    for i, v in enumerate(variants):
        v["rank"] = next(
            (r + 1 for r, ranked_v in enumerate(ranked) if ranked_v["index"] == v["index"]),
            None,
        )

    return {
        "winner_text": winner["text"],
        "winner_index": winner["index"],
        "winner_issues": winner["issues"],
        "variants": variants,
        "improvement": {
            "original_score": current_score,
            "winner_issues": winner["issues"],
            "all_issue_counts": [v.get("issues", 999) for v in variants],
        },
    }
