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

    # Visible words — include all tokens so first_150_words preserves articles/prepositions
    # (answer-signal regex needs "is a/an", which breaks if single-char words are stripped)
    words = re.findall(r"\w+", no_code)
    word_count = len(words)
    first_150 = " ".join(words[:150])

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


def _score_markdown(url: str, markdown_content: str, page_type: str = "general") -> int:
    """
    Score a markdown rewrite by counting how many static GEO issues fire.

    Lower is better — fewer issues = better candidate.
    """
    from api.crawler.issue_checker import _run_geo_checks  # type: ignore[attr-defined]

    # Build a lightweight duck-typed page object
    page_dict = _build_synthetic_parsed_page(url, markdown_content, page_type)

    class _SyntheticPage:
        """Duck-typed ParsedPage for _run_geo_checks."""
        def __init__(self, d: dict):
            for k, v in d.items():
                setattr(self, k, v)

    page = _SyntheticPage(page_dict)
    issues: list = []
    try:
        _run_geo_checks(page, url, issues)
    except Exception as e:
        logger.warning("geo_check_on_synthetic_page_failed", extra={"error": str(e)})
    return len(issues)


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
