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
    original_content: str | None = None,
) -> dict:
    """
    Generate a structured rewrite prompt from a GEOReport dict.

    Args:
        report:           GEOReport.to_dict() with 'findings', 'overall_score', etc.
        page_type:        Output of _detect_page_type().
        url:              Page URL (context only).
        original_content: Raw page text — used to build §(k) PRESERVATION FLOOR.
                          When provided, the prompt gains page-specific preservation
                          rules derived from the actual elements found in the content.

    Returns dict with keys:
        system_prompt, current_score, target_score, mandatory_count, fixable_count,
        page_type, preservation_floor (dict | None)
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

    # Build page-specific preservation floor from original content (RP2)
    preservation_floor: dict | None = None
    preservation_section = ""
    if original_content:
        preservation_floor = _extract_preservation_floor(original_content)
        preservation_section = _build_preservation_floor_section(preservation_floor)

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

## (b.5) PRIORITY ORDER

Apply changes in this strict order — earlier steps unlock the most GEO score gain:

1. **INTRO ANSWER** — Does the page answer its core question in the first 100–200 words?
   Every other improvement is worth less if AI models see narrative warm-up before the answer.

2. **QUERY COVERAGE** — Do the intro + H2 headings together cover the key user queries?
   Each H2 section should address at least one distinct user question within its body.

3. **SECTION INDEPENDENCE** — Can each H2 section stand alone?
   A reader arriving directly at an H2 must not need prior sections to understand it.

4. **STRUCTURAL CLARITY** — Are headings specific? Are paragraphs under 150 words?
   Vague headings and wall-of-text paragraphs fragment AI retrieval.

---

## (b.6) REQUIRED PAGE STRUCTURE

Follow this template when structuring the output:

```
H1: [Clear topic — preserve existing H1 text]

INTRO (100–200 words): Direct answer to the page's core question. No preamble.
  → First sentence states what the page teaches, concretely.
  → Covers the 1–2 most fundamental queries.

H2: [First major aspect — specific, not vague]
  Body: Introduce the concept here; do NOT reference the intro.
        Place statistics, quotes, examples inside this section.
        Answers 1+ key queries naturally within the body.

H2: [Second major aspect]
  Body: Self-contained. Brief one-sentence recap of the central concept is fine.
        Do NOT cluster all evidence here; spread across sections.

H2: [Further aspects as needed …]
```

Do NOT move all statistics or citations into one section.

---

## (c) OUTPUT CONTRACT

Return **only** the rewritten content in Markdown, with no preamble, no explanation,
and no summary of changes. Do not add a "Here is the rewritten version:" header.

**Intro requirements:**
- The intro must directly answer the page's core question within the first 100–200 words.
- Do NOT begin with a narrative warm-up: "In this guide we will…", "Many organisations face…",
  "Understanding X is critical…", "Before we dive in…" — these defer the answer.
- The first sentence should state *what the page teaches*, concretely.
- Phrases like "we will cover", "this article explains", or "let's explore" are banned in the intro.

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
   do not remove any of the following from the original:
   - FAQ Q&A pairs (preserve all of them)
   - Code blocks (preserve verbatim)
   - Tables, especially comparison tables (preserve with same rows and columns)
   - Named example lists (lists with specific tool or product names)
   - Outbound citation links (preserve target URLs and anchor text)
   - Specific statistics, numeric claims, or named sources that appeared in the
     original (preserve verbatim — do not round, summarise, or remove)
   Generic descriptions ("memory tools") must never replace specific names
   ("Supabase", "Claude Desktop", "GitHub").

6. **Do not fabricate author names or publication dates.** Use placeholder
   patterns: `[AUTHOR NAME]`, `[PUBLICATION DATE]`, `[LAST UPDATED DATE]`.

7. **Do not add advertising, product recommendations, or promotional content.**

8. **Do not summarise the article at the end** unless the original had a summary section.

9. **Do not introduce specific numbers** (durations such as "45 minutes", percentages,
   survey results, user counts, year ranges) that did not appear in the original text.
   Use `[STATISTIC NEEDED: describe figure type]` as a placeholder instead.

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
- Do not pad content with meaningless bullet lists. Every list item must state a
  specific fact, name, or step — not a vague description.
- Do not start every list item with the same grammatical structure (e.g., all gerunds)
- Do not add a "Summary" or "Key Takeaways" section unless the original had one
- Do not use passive constructions for more than 20% of sentences
- Do not make every sentence roughly the same length — vary between short punchy
  sentences and longer explanatory ones

**Backward cross-reference phrases — STRICTLY PROHIBITED:**
These phrases prevent AI models from extracting standalone answers from sections.
Replace each with the actual concept name.

| Prohibited | Replace with |
|---|---|
| "this approach" / "this method" | the actual approach name |
| "as mentioned above" / "as noted above" | re-state the concept directly |
| "as discussed above" / "as discussed earlier" | re-state the concept directly |
| "the above method" / "the method described above" | the actual method name |
| "see above" / "see the previous section" | re-state the concept directly |
| "the aforementioned" | the actual concept name |
| "as previously stated" / "as we saw" / "as we covered" | re-state directly |
| "the process described" / "the technique described" | the actual process name |

**Section independence rule:**
Each H2 section must be readable without any prior sections.
A one-sentence recap of the central concept at the start of a section is encouraged.
Never use a backward reference where a direct re-statement works.

**Required style rules:**
- Preserve contractions if the original used them (don't, it's, we're)
- Vary sentence length deliberately — mix short sentences with longer ones
- Lead with the concrete before the abstract (example before principle)
- Prefer active verbs over nominalised verbs ("we measure" not "we perform measurement of")
- Use specific numbers and named entities wherever the original justifies them

---

## (j) QUERY DISTRIBUTION

The key queries listed in the rubric must be distributed across the page — do NOT
answer all of them in the intro.

- **Intro:** Answer the 1–2 most fundamental "what is / why" queries only.
- **Each H2 section:** Address at least one query naturally within the section body,
  where the content supports it.
- **FAQ sections:** If the original page has a FAQ section, **preserve it and expand
  it if needed**. Do NOT fold FAQ content into prose sections — the Q&A format is
  the strongest AI-retrievable structure on the page. Each Q&A pair should stand
  alone as a complete exchange (question + concise answer of 1–4 sentences).
- If a query is specific to a technical step or comparison, answer it in the
  section covering that step — not in the intro.
"""

    # Append §(k) PRESERVATION FLOOR when original content was provided (RP2)
    if preservation_section:
        prompt = prompt + preservation_section

    return {
        "system_prompt": prompt,
        "current_score": current_score,
        "target_score": 0.90,
        "mandatory_count": mandatory_count,
        "fixable_count": fixable_count,
        "page_type": page_type,
        "findings_count": len(findings),
        "preservation_floor": preservation_floor,
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

# ---------------------------------------------------------------------------
# Score blending weights for stream_rewrite_variants (Fix 6 / §7)
# ---------------------------------------------------------------------------
# ⚠️  These weights are PROVISIONAL and NOT empirically validated.
# Future work will measure correlation between projected_score and the actual
# recrawl GEO score across a corpus of rewrites, then tune the blend.  Until
# that validation exists, treat any score change of <5 points as within the
# margin of weighting uncertainty.  See:
#   docs/implementation_plan_geo_validation.md (planned, not yet written)
_QUERY_COVERAGE_WEIGHT: float = 0.8
_CONTENT_QUALITY_WEIGHT: float = 0.2
assert abs(_QUERY_COVERAGE_WEIGHT + _CONTENT_QUALITY_WEIGHT - 1.0) < 1e-9, (
    "Score blend weights must sum to 1.0"
)

# ---------------------------------------------------------------------------
# Preservation floor extraction (RP1)
# ---------------------------------------------------------------------------

# Question line: ≤130 chars, ends with ?, starts with a heading OR starts with
# a recognised question word. The "preceded by blank line" constraint is enforced
# in code (not regex) so we can inspect the surrounding lines.
_FAQ_QUESTION_WORDS_RE = re.compile(
    r"^(?:#+\s+|[*_]{1,2})?(?:Q\d*[:.]\s*)?"
    r"(?:What|How|Why|When|Where|Who|Can|Does|Is|Are|Will|Should|Do|"
    r"Which|Have|Has|Was|Were|Would|Could|May|Might|Must)\b",
    re.I,
)
_BULLET_LINE_RE = re.compile(r"^[-*+]\s+")
_NUMBERED_LINE_RE = re.compile(r"^\d+[.)]\s+")

# Proper-noun words that should not count as list-naming even though they are
# capitalized mid-item (common English title-case function words).
_COMMON_MID_CAPS: frozenset[str] = frozenset({
    "The", "It", "This", "In", "Is", "To", "A", "An", "And", "Or", "But",
    "For", "With", "From", "By", "At", "Of", "On", "That", "Which", "Be",
    "Has", "Have", "Had", "Was", "Were", "Not", "If", "When", "Where", "How",
})

# Numbers that warrant capture: integers ≥2, decimals, percentages, durations
_NUMBER_RE = re.compile(
    r"(?<!\w)"
    r"(?:\d{1,3}(?:,\d{3})*(?:\.\d+)?%"   # percentage: 99.9%, 73%
    r"|\d+(?:\.\d+)?\s*(?:second|minute|hour|day|week|month|year)s?"  # duration
    r"|\d{4,}"                               # 4+ digit integers (years, IDs)
    r"|\d+\.\d+"                             # decimals
    r"|[1-9]\d{1,2})"                        # integers 2–999
    r"(?!\w)",
    re.I,
)

# ---------------------------------------------------------------------------
# Named-entity extraction (Fix 4 / §5)
# ---------------------------------------------------------------------------
# Replaces the bare capitalisation heuristic in _item_has_named_reference.
# Strategy:
#   1. Backtick-wrapped identifiers: `pgvector`, `npm install`
#   2. Multi-word title-case phrases of 2-4 words: "Claude Desktop"
#   3. Single capitalised words (or camelCase) appearing >= 2 times
#   4. Allowlisted technical/product terms (case-insensitive)

_TECHNICAL_TERM_ALLOWLIST: frozenset[str] = frozenset({
    # protocols / formats / file types
    "npm", "pip", "git", "bash", "curl", "json", "sql", "api", "mcp",
    "css", "html", "xml", "yaml", "toml", "ssh", "tls", "https", "http",
    "oauth", "jwt", "uuid", "regex", "graphql", "rpc", "grpc", "rest",
    "rss", "atom", "csv", "pdf", "svg", "png", "jpg", "webp",
    # databases / stores
    "pgvector", "postgres", "postgresql", "mysql", "sqlite", "redis",
    "mongodb", "elasticsearch", "supabase", "firebase",
    # AI / LLM ecosystem
    "openai", "anthropic", "openbrain", "claude", "chatgpt", "gemini",
    "gpt", "llm", "rag", "ai", "ml", "mem0", "memgpt", "langchain",
    # product / platform names
    "notion", "github", "gitlab", "bitbucket", "linear", "slack", "zoom",
    "jira", "asana", "trello", "stripe", "twilio",
    # frontend / runtime
    "react", "vue", "angular", "svelte", "nextjs", "nuxt", "remix",
    "node", "deno", "bun", "rust", "python", "typescript", "javascript",
    "playwright", "puppeteer", "vite", "webpack",
    # general acronyms used as identifiers
    "ssr", "csr", "spa", "dom", "ide", "cli", "gui", "url", "uri",
    "seo", "geo",
})

# Words that capitalisation alone shouldn't promote to entity status.
_EMPHASIS_STOP_WORDS: frozenset[str] = frozenset({
    "Important", "Required", "Recommended", "Optional",
    "Note", "Notes", "Warning", "Tip", "Caution", "Critical", "Danger",
    "TODO", "FIXME", "Step", "Steps", "Setup", "Install", "Installation",
    "Configuration", "Why", "How", "What", "Who", "When", "Where", "Which",
    "Yes", "No", "True", "False", "OK", "Done", "Pass", "Fail",
    "First", "Second", "Third", "Next", "Then", "Finally",
    "The", "This", "That", "These", "Those",
})

_BACKTICK_ID_RE = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_/.-]*)`")
_SINGLE_CAP_WORD_RE = re.compile(r"\b[A-Z][a-zA-Z0-9]+\b")
# Multi-word phrase: 2-4 capitalised tokens; each token may be hyphenated/apostrophe'd
_MULTIWORD_TITLE_RE = re.compile(
    r"\b(?:[A-Z][a-zA-Z0-9]+(?:[-'][A-Za-z0-9]+)*)"
    r"(?:\s+(?:[A-Z][a-zA-Z0-9]+(?:[-'][A-Za-z0-9]+)*)){1,3}"
    r"\b"
)


def _extract_named_entities_from_text(text: str) -> frozenset[str]:
    """Extract candidate named entities from page text (Fix 4 / §5.2 / §5.3).

    Returns a frozenset combining four detection strategies (see docstring above
    the regex constants).  Allowlisted terms are normalised to lowercase; other
    forms preserve the source casing.

    The extractor is conservative — false negatives (missing a real entity) are
    recoverable; false positives cause cascading wrong feedback to the
    rewriting LLM.
    """
    entities: set[str] = set()

    # Strategy 1 — backtick identifiers, case-preserving
    for m in _BACKTICK_ID_RE.finditer(text):
        ident = m.group(1)
        if len(ident) >= 2:
            entities.add(ident)

    # Strategy 4 — allowlisted technical terms (case-insensitive)
    text_lower = text.lower()
    for term in _TECHNICAL_TERM_ALLOWLIST:
        if re.search(rf"\b{re.escape(term)}\b", text_lower):
            entities.add(term)

    # Strategy 2 — multi-word title-case phrases (skip if first word is stop word)
    for m in _MULTIWORD_TITLE_RE.finditer(text):
        phrase = m.group(0).strip()
        words = phrase.split()
        if not words or words[0] in _EMPHASIS_STOP_WORDS:
            continue
        # Drop phrases where ALL words are common stop words (rare but safe)
        if all(w in _EMPHASIS_STOP_WORDS for w in words):
            continue
        entities.add(phrase)

    # Strategy 3 — single capitalised words appearing >= 2 times
    counter: dict[str, int] = {}
    for m in _SINGLE_CAP_WORD_RE.finditer(text):
        w = m.group(0)
        if w in _EMPHASIS_STOP_WORDS:
            continue
        counter[w] = counter.get(w, 0) + 1
    for w, count in counter.items():
        if count >= 2:
            entities.add(w)

    return frozenset(entities)


def _item_references_known_entity(
    item_line: str, known_entities: frozenset[str]
) -> bool:
    """Return True if the bullet item mentions any entity in `known_entities`.

    Allowlisted technical names match case-insensitively; multi-word phrases
    and proper nouns from Strategies 2/3 match as substrings (case-sensitive
    for proper nouns, case-insensitive for the pre-lowered allowlist).
    """
    if not known_entities:
        return False
    # Strip bullet/number marker
    content = re.sub(r"^[-*+]\s+|^\d+[.)]\s+", "", item_line, count=1).strip()
    lowered = content.lower()
    for entity in known_entities:
        if entity in _TECHNICAL_TERM_ALLOWLIST:
            # Case-insensitive word-boundary match for allowlisted terms
            if re.search(rf"\b{re.escape(entity)}\b", lowered):
                return True
        else:
            # Case-preserving substring match for proper nouns / multi-word phrases
            if entity in content:
                return True
    return False


def _count_faq_pairs(text: str) -> int:
    """Count Q&A pairs: a question line followed within 5 lines by a non-question answer.

    Stricter rule (Fix 7.1 / §8.1 + CR_ADJ_4): heading-style questions only count
    if there are ≥2 such questions in the document AND each one starts with a
    recognised question word.  A single rhetorical heading like
    "## Why use OpenBrain?" in an article does NOT establish FAQ format.
    Inline-style questions (question-word lines preceded by a blank line) are
    counted independently.

    Heading-questions are also required to start with a question word
    (CR_ADJ_4) — `## Migration v2 → v3?` is rhetorical, not a Q&A heading.
    """
    lines = text.splitlines()
    heading_pairs: list[int] = []  # indices of confirmed heading-question pairs
    inline_pairs: list[int] = []   # indices of confirmed inline-question pairs
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        # Strip heading and bold markers to get the raw text
        stripped = re.sub(r"^#+\s*|[*_]{1,2}", "", line).strip()
        is_short = len(line) <= 130
        is_question_word = bool(_FAQ_QUESTION_WORDS_RE.match(line.lstrip()))
        is_heading = line.lstrip().startswith("#")
        ends_with_q = stripped.rstrip("*_ \t").endswith("?")
        preceded_by_blank = (i == 0) or (not lines[i - 1].strip())

        # Heading-style: requires question word AND ends with ? AND short
        # (CR_ADJ_4 narrows the previous "is_heading or ..." condition).
        is_heading_question = (
            is_heading and is_question_word and ends_with_q and is_short
        )
        # Inline-style: question word at start of line, preceded by blank, ends with ?
        is_inline_question = (
            (not is_heading) and is_question_word and preceded_by_blank
            and ends_with_q and is_short
        )

        if is_heading_question or is_inline_question:
            # Look for an answer within the next 5 non-blank lines
            j = i + 1
            non_blank_seen = 0
            found_answer_at = -1
            while j < len(lines) and non_blank_seen < 5:
                nl = lines[j].strip()
                if nl:
                    non_blank_seen += 1
                    nl_stripped = re.sub(r"^#+\s*|[*_]{1,2}", "", nl).strip()
                    # Answer: non-blank line that isn't itself a question
                    if not nl_stripped.endswith("?"):
                        found_answer_at = j
                        break
                j += 1
            if found_answer_at >= 0:
                if is_heading_question:
                    heading_pairs.append(i)
                else:
                    inline_pairs.append(i)
                i = found_answer_at + 1  # advance past the answer
                continue
        i += 1

    # Stricter rule: a single heading-question is rhetorical, not FAQ format.
    # Drop heading-pairs entirely if fewer than 2 were detected.
    if len(heading_pairs) < 2:
        heading_pairs = []

    return len(heading_pairs) + len(inline_pairs)


def _item_has_named_reference(item_line: str) -> bool:
    """Return True if a list item line contains a proper noun or quoted string."""
    # Remove bullet/number marker and leading markup
    content = re.sub(r"^[-*+]|\d+[.)]\s*", "", item_line, count=1).strip()
    content = re.sub(r"^[*_]{1,2}", "", content).strip()

    # Quoted strings in backticks or straight quotes count immediately
    if re.search(r"[`\"][^\"`]{2,40}[`\"]", content):
        return True

    # Proper noun: capitalised word ≥2 chars beyond the first word of the item
    words = content.split()
    for idx, word in enumerate(words):
        w = re.sub(r"[^\w\-]", "", word)
        if not w or len(w) < 2:
            continue
        if idx > 0 and w[0].isupper() and w not in _COMMON_MID_CAPS:
            return True
    return False


def _count_named_lists(
    text: str,
    known_entities: frozenset[str] | None = None,
) -> int:
    """Count bullet list blocks where ≥2 items reference named entities.

    Backwards-compatible: when `known_entities` is None or empty, falls back
    to the legacy capitalisation heuristic via _item_has_named_reference.
    When provided, uses _item_references_known_entity which compares against
    the entity set extracted from the original page (Fix 4 / §5.2).
    """
    lines = text.splitlines()
    named_list_count = 0
    i = 0
    while i < len(lines):
        if _BULLET_LINE_RE.match(lines[i]) or _NUMBERED_LINE_RE.match(lines[i]):
            # Collect consecutive list lines (allow continuation indent)
            block_lines = []
            while i < len(lines) and (
                _BULLET_LINE_RE.match(lines[i])
                or _NUMBERED_LINE_RE.match(lines[i])
                or (block_lines and lines[i].startswith("  ") and lines[i].strip())
            ):
                if _BULLET_LINE_RE.match(lines[i]) or _NUMBERED_LINE_RE.match(lines[i]):
                    block_lines.append(lines[i])
                i += 1
            if known_entities:
                named_items = sum(
                    1 for ln in block_lines
                    if _item_references_known_entity(ln, known_entities)
                )
            else:
                named_items = sum(
                    1 for ln in block_lines if _item_has_named_reference(ln)
                )
            if named_items >= 2:
                named_list_count += 1
        else:
            i += 1
    return named_list_count


def _count_tables(text: str) -> int:
    """Count distinct Markdown table blocks (requires at least one separator row |---|)."""
    # Find all runs of pipe-table lines; only count blocks that have a separator row
    table_count = 0
    in_table = False
    has_separator = False
    for line in text.splitlines():
        if re.match(r"^\|.+\|$", line.rstrip()):
            in_table = True
            if re.match(r"^\|[\s|:\-]+\|$", line.rstrip()):
                has_separator = True
        else:
            if in_table and has_separator:
                table_count += 1
            in_table = False
            has_separator = False
    if in_table and has_separator:
        table_count += 1
    return table_count


def _extract_specific_numbers(text: str) -> frozenset[str]:
    """Extract all specific numeric values from text (integers, decimals, percentages, durations)."""
    return frozenset(m.group(0).strip() for m in _NUMBER_RE.finditer(text))


def _extract_preservation_floor(text: str) -> dict:
    """
    Scan original page content for high-value extractable elements.

    Purpose: identify what must be preserved in every rewrite variant.
    Spec:    docs/implementation_plan_geo_rewrite_preservation_2026-05-04.md#RP1
    Tests:   tests/test_geo_rewrite_prompt.py::TestPreservationFloor

    Returns dict with:
      faq_pair_count, named_list_count, code_block_count, table_count,
      outbound_link_count, original_number_set
    """
    # Strip code blocks before most checks (code contains numbers, links, etc. that
    # aren't part of the prose content and could inflate counts).
    text_no_code = _MD_CODE_RE.sub("", text)

    # Extract named entities first so the named-list count can use them
    # (Fix 4 / §5.2.5–§5.2.6).  Entities are extracted from text WITH code
    # blocks so backtick-wrapped identifiers are captured.
    named_entities = _extract_named_entities_from_text(text)

    return {
        "faq_pair_count":      _count_faq_pairs(text_no_code),
        "named_list_count":    _count_named_lists(text_no_code, named_entities),
        "code_block_count":    len(_MD_CODE_RE.findall(text)),
        "table_count":         _count_tables(text_no_code),
        "outbound_link_count": len(_MD_LINK_RE.findall(text_no_code)),
        # CR_ADJ_5: scan numbers from FULL text (including code blocks) so a
        # rewrite that preserves a benchmark like ```45 minutes``` verbatim
        # doesn't trip the hallucination guard for "45 minutes" not being in
        # the original number set.
        "original_number_set": _extract_specific_numbers(text),
        "named_entities":      named_entities,
    }


def _build_preservation_floor_section(floor: dict) -> str:
    """
    Build the §(k) PRESERVATION FLOOR prompt section from extracted floor data.

    Returns an empty string when no notable elements were found (avoids
    injecting an empty section into the prompt).
    """
    items: list[str] = []

    if floor["faq_pair_count"] >= 2:
        n = floor["faq_pair_count"]
        min_required = max(2, int(n * 0.7))
        items.append(
            f"- **FAQ / Q&A section:** The original contains **{n} Q&A pairs**. "
            f"The rewrite must preserve at least {min_required} of them in Q&A format. "
            f"⛔ FAILURE CONDITION: Fewer than {min_required} Q&A pairs is a failing rewrite. "
            f"Do NOT fold FAQ content into prose — the Q&A structure is the highest-value "
            f"AI-retrievable format on the page."
        )

    if floor["code_block_count"] >= 1:
        n = floor["code_block_count"]
        items.append(
            f"- **Code blocks:** The original contains **{n} code block(s)**. "
            f"Every code block must appear in the rewrite unchanged (syntax and content). "
            f"⛔ FAILURE CONDITION: Removing any code block is a failing rewrite."
        )

    if floor["table_count"] >= 1:
        n = floor["table_count"]
        items.append(
            f"- **Tables:** The original contains **{n} Markdown table(s)**. "
            f"Each table must appear in the rewrite with the same rows and columns. "
            f"A comparison table naming competing products or platforms must survive intact. "
            f"⛔ FAILURE CONDITION: Removing any table is a failing rewrite."
        )

    if floor["outbound_link_count"] >= 1:
        n = floor["outbound_link_count"]
        items.append(
            f"- **Outbound citation links:** The original contains **{n} external link(s)**. "
            f"Every `[text](https://...)` link must appear in the rewrite. "
            f"If a link cannot be preserved verbatim, replace it with "
            f"`[SOURCE NEEDED: describe source type]` inline. "
            f"⛔ FAILURE CONDITION: Reducing outbound links to 0 when the original had {n} is a failing rewrite."
        )

    if floor["named_list_count"] >= 1:
        n = floor["named_list_count"]
        items.append(
            f"- **Named bullet list(s):** The original contains **{n} list(s)** with specific "
            f"tool, product, or platform names. The specific names (e.g. ChatGPT, Supabase, "
            f"GitHub, MCP) must be preserved — do NOT replace them with generic terms like "
            f"'memory tools' or 'storage options'. "
            f"⛔ FAILURE CONDITION: Converting named lists to generic prose is a failing rewrite."
        )

    if not items:
        return ""

    header = (
        "\n## (k) PRESERVATION FLOOR — PAGE-SPECIFIC REQUIREMENTS\n\n"
        "⚠️ This section is derived from the **actual content of the original page** and "
        "takes **highest priority** over any conflicting style guidance above.\n\n"
        "The following elements were detected in the original and **MUST be preserved or "
        "improved** in every rewrite. Removing or genericising any of them is a "
        "FAILURE CONDITION — the variant will be scored 0 on the preservation check.\n\n"
    )
    return header + "\n".join(items) + "\n"


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

    # first_200_words: preserve original punctuation (including "%" and ".") so that
    # stat-detection and answer-signal regexes work correctly.  Split on whitespace
    # (not word boundaries) so "27.6%" and "according to" patterns survive.
    _tokens = no_code.split()
    first_150 = " ".join(_tokens[:200])
    first_600 = " ".join(_tokens[:600])

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
    # NOTE (Fix 7.4 / §8.4): list_count is capped at 1 because the only consumer
    # of structured_element_count today is issue_checker._run_geo_checks at
    # api/crawler/issue_checker.py:1923 which checks `structured_element_count
    # == 0` only.  If issue_checker ever changes to threshold on counts (e.g.
    # requires >=2 structured elements), REMOVE THIS CAP and count actually,
    # otherwise this silently undercounts and pages will fail incorrectly.
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
        "first_200_words": first_150,
        "first_600_words": first_600,
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

# Fabricated outbound link detection (Fix 7.5 / §8.5).
# An LLM-hallucinated citation often points at example.com, placeholder domains,
# or contains words like "fabricated", "made-up", "todo", "fixme".  These are
# treated as placeholders (partial credit), not real citations (full pass).
_FABRICATED_LINK_RE = re.compile(
    r"https?://"
    r"(?:"
    r"example\.(?:com|org|net|io|app)"            # placeholder TLDs
    r"|placeholder\.[a-z]+"                       # any placeholder.*
    r"|[^/\s)]*(?:fabricated|made-up|todo|fixme|example|placeholder)[^/\s)]*"
    r")",
    re.I,
)


def _is_real_external_link(url: str) -> bool:
    """Return False if the URL looks like an LLM-hallucinated citation."""
    return not _FABRICATED_LINK_RE.search(url)

# GEO NOTES section delimiter (Fix 7.3 / §8.3) — matches the documented format only.
# Required structure:
#   \n---\n
#   GEO NOTES\n
#   - [TAG ...] notes-line(s)\n   ← at least one bracket-tag bullet
# This prevents accidental truncation when the body coincidentally contains
# the tokens "GEO NOTES" as a heading.  CR_ADJ_3 extends with leading-whitespace
# tolerance for the bullet markers (LLMs sometimes indent them).
_GEO_NOTES_SPLIT_RE = re.compile(
    r"\n---\s*\n"
    r"GEO NOTES\s*\n"
    r"(?:\s*-\s+\[[A-Z][^\]]*\][^\n]*\n?)+"
    r"\s*$",
    re.S | re.I,
)


def _split_body_and_notes(text: str) -> tuple[str, str]:
    """Split rewrite text into (body, geo_notes). geo_notes may be empty string."""
    m = _GEO_NOTES_SPLIT_RE.search(text)
    if m:
        return text[: m.start()], m.group(0)
    return text, ""


def _verify_geo_notes_placeholders(body: str, notes: str) -> list[str]:
    """
    Return a list of placeholder types that the LLM claimed to have added in GEO NOTES
    but which do not actually appear in the body text.

    Example: if GEO NOTES says "[CITATION NEEDED] added at: Introduction…" but the
    body has no [CITATION NEEDED] text, "CITATION NEEDED / LINK" is returned.

    This catches the failure mode where the LLM describes what it intended to add
    rather than inserting the placeholder inline.
    """
    if not notes:
        return []
    missing: list[str] = []
    checks = [
        (_PLACEHOLDER_CITATION_RE, "CITATION NEEDED / LINK"),
        (_PLACEHOLDER_STAT_RE, "STATISTIC"),
        (_PLACEHOLDER_QUOTE_RE, "QUOTE NEEDED"),
    ]
    for pattern, label in checks:
        if pattern.search(notes) and not pattern.search(body):
            missing.append(label)
    return missing


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


_REGRESSION_CHECK_WEIGHT = 2  # same weight as Mechanistic checks


def _check_preservation_regression(
    original_features: dict,
    rewrite_text: str,
) -> list[str]:
    """
    Detect which high-value elements from the original were removed in the rewrite.

    Purpose: regression-aware scoring so a rewrite that strips the FAQ, tables, or
             code blocks cannot score higher than one that preserves them.
    Spec:    docs/implementation_plan_geo_rewrite_preservation_2026-05-04.md#RP4
    Tests:   tests/test_geo_rewrite_prompt.py::TestPreservationFloor

    Returns a list of violation codes (empty = no regression).
    """
    body, _ = _split_body_and_notes(rewrite_text)
    rewrite_floor = _extract_preservation_floor(body)
    violations: list[str] = []

    # FAQ regression: original had ≥2 pairs; rewrite drops below 70% of original
    orig_faq = original_features.get("faq_pair_count", 0)
    if orig_faq >= 2:
        min_required = max(2, int(orig_faq * 0.7))
        if rewrite_floor["faq_pair_count"] < min_required:
            violations.append("FAQ_REMOVED")

    # Code block regression: original had ≥1; rewrite has 0
    if original_features.get("code_block_count", 0) >= 1:
        if rewrite_floor["code_block_count"] == 0:
            violations.append("CODE_BLOCK_REMOVED")

    # Table regression: original had ≥1; rewrite has 0
    if original_features.get("table_count", 0) >= 1:
        if rewrite_floor["table_count"] == 0:
            violations.append("TABLE_REMOVED")

    # Outbound link regression: original had ≥2; rewrite has 0
    if original_features.get("outbound_link_count", 0) >= 2:
        if rewrite_floor["outbound_link_count"] == 0:
            violations.append("OUTBOUND_LINK_REMOVED")

    # Named list genericised (legacy): original had ≥1 named list; rewrite has 0
    if original_features.get("named_list_count", 0) >= 1:
        if rewrite_floor["named_list_count"] == 0:
            violations.append("NAMED_LIST_GENERICISED")

    # Named entities lost (Fix 4 / §5.2.7): original had named entities;
    # rewrite preserves <70% of them.  Case-insensitive comparison so a
    # rewrite that lowercases "Supabase" → "supabase" still counts as preserved.
    orig_entities = original_features.get("named_entities", frozenset())
    if orig_entities:
        rewrite_entities = _extract_named_entities_from_text(rewrite_text)
        orig_lower = {e.lower() for e in orig_entities}
        rewrite_lower = {e.lower() for e in rewrite_entities}
        preserved = orig_lower & rewrite_lower
        if len(preserved) < 0.7 * len(orig_lower):
            violations.append("NAMED_ENTITIES_LOST")

    return violations


# ---------------------------------------------------------------------------
# Page-type-conditional structural check (Fix 3 / §4)
# ---------------------------------------------------------------------------

def _has_numbered_list_with_min_items(text: str, min_items: int) -> bool:
    """Return True if any numbered-list block has ≥ min_items consecutive items.

    A numbered-list block is a run of consecutive lines matching _NUMBERED_LINE_RE
    (e.g. `1. step`).  Continuation indents and blank lines reset the run.
    """
    lines = text.splitlines()
    longest = 0
    current = 0
    for line in lines:
        if _NUMBERED_LINE_RE.match(line):
            current += 1
            longest = max(longest, current)
        elif line.strip() == "":
            # blank line breaks the run only if the next non-blank line isn't a list
            # — for simplicity we reset on any blank
            current = 0
        else:
            current = 0
    return longest >= min_items


def _table_has_min_rows(text: str, min_rows: int) -> bool:
    """Return True if any markdown table has ≥ min_rows DATA rows (excluding header
    and separator rows).

    A markdown table is a run of pipe-delimited lines.  The first row is the header,
    the second row is the `|---|---|` separator, the rest are data rows.
    """
    in_table = False
    has_separator = False
    data_rows = 0
    longest_data_rows = 0
    for line in text.splitlines():
        is_pipe_row = bool(re.match(r"^\|.+\|$", line.rstrip()))
        is_separator = bool(re.match(r"^\|[\s|:\-]+\|$", line.rstrip()))
        if is_pipe_row:
            in_table = True
            if is_separator:
                has_separator = True
            elif has_separator:
                data_rows += 1
        else:
            if in_table:
                longest_data_rows = max(longest_data_rows, data_rows)
            in_table = False
            has_separator = False
            data_rows = 0
    if in_table:
        longest_data_rows = max(longest_data_rows, data_rows)
    return longest_data_rows >= min_rows


def _structural_check_passes(body: str, page_type: str) -> bool:
    """Page-type-conditional structural sufficiency check (Fix 3 / §4.2).

    technical:  code block OR numbered list with ≥3 steps
    comparison: table with ≥2 data rows OR ≥1 named list
    faq:        ≥3 detected Q&A pairs
    article:    any list, table, or code block (legacy behaviour)
    general:    same as article (legacy behaviour)
    """
    if page_type == "technical":
        has_code = bool(_MD_CODE_RE.search(body))
        has_step_list = _has_numbered_list_with_min_items(body, 3)
        return has_code or has_step_list
    if page_type == "comparison":
        has_table = _table_has_min_rows(body, 2)
        has_named_list = _count_named_lists(body) >= 1
        return has_table or has_named_list
    if page_type == "faq":
        return _count_faq_pairs(body) >= 3
    # article / general / unknown → any structured element
    return (
        bool(_MD_UL_RE.search(body))
        or bool(_MD_OL_RE.search(body))
        or bool(_MD_TABLE_RE.search(body))
        or bool(_MD_CODE_RE.search(body))
    )


def _content_score(
    url: str,
    content: str,
    page_type: str = "general",
    original_features: dict | None = None,
) -> tuple[int, float, list[str], dict]:
    """
    Score rewrite content on 5 GEO content signals + optional preservation regression.

    Returns (fail_count, score 0-1, list_of_failing_check_codes, placeholder_inventory).

    placeholder_inventory keys:
        partial_pass_checks: list[str]  — checks passing only via placeholders (half credit)
        placeholder_counts: dict[str, int]  — counts by type (citation/quote/stat)
        placeholder_density: float  — placeholders per 100 body words

    Uses a fixed denominator (weight=13) so baseline and all variant scores
    are directly comparable.  When original_features is provided, up to 5
    preservation regression checks are added (weight=2 each), growing the
    denominator accordingly.

    Placeholder credit (Fix 2 / §3):
      - Real evidence (e.g. real outbound link, real number, real attribution)
        → check passes fully.
      - Only placeholders ([CITATION NEEDED], [STATISTIC: ...], [QUOTE NEEDED: ...])
        → check passes at 0.5 credit (partial-pass).  fail_weight += weight × 0.5.
      - Neither → check fails fully.
      - Cap rule (§3.5): at most 2 of the 3 placeholder-eligible checks may
        partial-pass; if all three would partial-pass, the alphabetically-first
        check (EXTERNAL_CITATIONS_LOW) is demoted to a full fail.  Tie-break
        is alphabetical because all three weights are equal (3); this is
        documented and tested by CR3_5.
      - Fabricated outbound links (per _FABRICATED_LINK_RE) are treated as
        placeholders, not real citations.

    GEO NOTES are stripped before scoring so that placeholder descriptions in
    the notes section cannot inflate the score.
    """
    body, _notes = _split_body_and_notes(content)
    tokens = body.split()
    word_count = len(tokens)
    first_150 = " ".join(tokens[:150])

    fails: set[str] = set()
    partial_passes: set[str] = set()

    # ── Check 1 — Statistics ────────────────────────────────────────────────
    # Real: number-with-unit found by _STAT_RE_FULL.
    # Placeholder: [STATISTIC: ...] in body.
    if word_count >= 500:
        has_real_stat = bool(_STAT_RE_FULL.search(body))
        has_placeholder_stat = bool(_PLACEHOLDER_STAT_RE.search(body))
        if has_real_stat:
            pass  # full pass
        elif has_placeholder_stat:
            partial_passes.add("STATISTICS_COUNT_LOW")
        else:
            fails.add("STATISTICS_COUNT_LOW")

    # ── Check 2 — External citations ────────────────────────────────────────
    # Real: markdown link to a non-fabricated URL.
    # Placeholder: [CITATION NEEDED] OR markdown link to a fabricated URL.
    if word_count >= 500:
        real_links = [
            m for m in _MD_LINK_RE.finditer(body)
            if _is_real_external_link(m.group(2))
        ]
        fabricated_links = [
            m for m in _MD_LINK_RE.finditer(body)
            if not _is_real_external_link(m.group(2))
        ]
        has_real_citation = bool(real_links)
        has_placeholder_citation = (
            bool(_PLACEHOLDER_CITATION_RE.search(body))
            or bool(fabricated_links)
        )
        if has_real_citation:
            pass  # full pass
        elif has_placeholder_citation:
            partial_passes.add("EXTERNAL_CITATIONS_LOW")
        else:
            fails.add("EXTERNAL_CITATIONS_LOW")

    # ── Check 3 — Quotations/attribution ────────────────────────────────────
    # Real: blockquote OR attribution phrase.
    # Placeholder: [QUOTE NEEDED: ...].
    if word_count >= 500:
        has_real_quote = (
            bool(_MD_BLOCKQUOTE_RE.search(body))
            or bool(_ATTRIBUTION_RE_FULL.search(body))
        )
        has_placeholder_quote = bool(_PLACEHOLDER_QUOTE_RE.search(body))
        if has_real_quote:
            pass
        elif has_placeholder_quote:
            partial_passes.add("QUOTATIONS_MISSING")
        else:
            fails.add("QUOTATIONS_MISSING")

    # ── Cap rule (§3.5): at most 2 partial-passes ───────────────────────────
    # All three placeholder-eligible checks have weight 3.  Alphabetical tie-
    # break (documented in docstring + plan §4 risk) — EXTERNAL_CITATIONS_LOW
    # demotes first.
    while len(partial_passes) > 2:
        # Demote the alphabetically-first remaining partial-pass to a full fail
        demote = sorted(partial_passes)[0]
        partial_passes.remove(demote)
        fails.add(demote)

    # ── Check 4 — Answer signal in first 150 words ──────────────────────────
    # Binary check; not placeholder-eligible.
    if word_count >= 200:
        try:
            from api.crawler.issue_checker import _has_answer_signal  # type: ignore
            if not _has_answer_signal(first_150):
                fails.add("FIRST_VIEWPORT_NO_ANSWER")
        except Exception:
            pass  # skip check if import fails

    # ── Check 5 — Structured elements (page-type-conditional, Fix 3 / §4) ───
    # Binary check; not placeholder-eligible.  Dispatched per page_type:
    #   technical:  code block OR numbered list ≥3 steps
    #   comparison: table ≥2 data rows OR named list
    #   faq:        ≥3 Q&A pairs
    #   article/general: any list/table/code block (legacy behaviour)
    if word_count >= 500:
        if not _structural_check_passes(body, page_type):
            fails.add("STRUCTURED_ELEMENTS_LOW")

    # ── Score computation ───────────────────────────────────────────────────
    # Full failures contribute their full weight; partial passes contribute
    # half their weight.  Denominator stays fixed at 13 so scores are
    # comparable across variants.
    fail_weight = sum(_CONTENT_SCORE_WEIGHT.get(c, 0) for c in fails)
    fail_weight += sum(_CONTENT_SCORE_WEIGHT.get(c, 0) * 0.5 for c in partial_passes)
    total_weight = _CONTENT_SCORE_TOTAL_WEIGHT

    # Preservation regression checks (RP4.3) — each adds to denominator whether or not it fails
    if original_features:
        regression_violations = _check_preservation_regression(original_features, content)
        # Count how many regression checks were applicable (to set denominator correctly)
        applicable_checks = 0
        if original_features.get("faq_pair_count", 0) >= 2:
            applicable_checks += 1
        if original_features.get("code_block_count", 0) >= 1:
            applicable_checks += 1
        if original_features.get("table_count", 0) >= 1:
            applicable_checks += 1
        if original_features.get("outbound_link_count", 0) >= 2:
            applicable_checks += 1
        if original_features.get("named_list_count", 0) >= 1:
            applicable_checks += 1
        if original_features.get("named_entities"):
            applicable_checks += 1  # Fix 4 / §5.2.7
        total_weight += applicable_checks * _REGRESSION_CHECK_WEIGHT
        fail_weight += len(regression_violations) * _REGRESSION_CHECK_WEIGHT
        fails.update(regression_violations)

    score = round(1.0 - fail_weight / total_weight, 4) if total_weight > 0 else 1.0

    # ── Placeholder inventory (Fix 2 / §3.3) ────────────────────────────────
    placeholder_counts = {
        "citation": len(_PLACEHOLDER_CITATION_RE.findall(body)),
        "stat": len(_PLACEHOLDER_STAT_RE.findall(body)),
        "quote": len(_PLACEHOLDER_QUOTE_RE.findall(body)),
    }
    total_placeholders = sum(placeholder_counts.values())
    placeholder_density = (
        round(total_placeholders / (word_count / 100.0), 4)
        if word_count > 0 else 0.0
    )
    placeholder_inventory = {
        "partial_pass_checks": sorted(partial_passes),
        "placeholder_counts": placeholder_counts,
        "placeholder_density": placeholder_density,
    }

    return len(fails), score, sorted(fails), placeholder_inventory



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

# Numbered-output verdict line: `1: Yes`, `2. Partial`, `3) No`, etc.
# Tolerates leading whitespace, several common separators, and trailing text.
_VERDICT_LINE_RE = re.compile(
    r"^\s*(\d+)\s*[:.\-)]\s*(yes|partial|no)\b",
    re.I,
)


def parse_verdict_response(response: str, queries: list[str]) -> list[dict]:
    """Parse an LLM verdict response into per-query results (Fix 5 / §6).

    The LLM is instructed to emit lines of the form ``N: <verdict>``.  This
    parser is robust to:
      - extra whitespace / prefixes
      - out-of-order line numbers
      - missing query numbers (sets parse_failure=True, defaults to "Partial")

    Default-on-missing is "Partial" (not "No") because silent "No" defaults
    bias scores downward when the LLM misformats output, falsely indicating
    knowledge gaps.
    """
    verdicts: dict[int, str] = {}
    canonicalise = {"yes": "Yes", "partial": "Partial", "no": "No"}
    for line in response.splitlines():
        m = _VERDICT_LINE_RE.match(line)
        if m:
            n = int(m.group(1))
            verdicts[n] = canonicalise[m.group(2).lower()]

    per_query: list[dict] = []
    for idx, q in enumerate(queries, start=1):
        answered = verdicts.get(idx)
        if answered is None:
            per_query.append({"query": q, "answered": "Partial", "parse_failure": True})
        else:
            per_query.append({"query": q, "answered": answered, "parse_failure": False})
    return per_query


async def _score_rewrite_query_match(
    rewrite_text: str,
    original_query_table: list[dict],
    model: str,
    provider: str,
) -> tuple[float, list[dict]]:
    """
    Re-evaluate how well the rewrite text answers the original page's AI queries.

    Uses the same queries from the cached GEO report (not re-generating them),
    then asks the LLM to score each query Yes/Partial/No using the numbered
    output format (Fix 5 / §6).

    Returns (score, per_query_results) where:
      - score: 0.0–1.0 matching QUERY_MATCH_SCORE formula
      - per_query_results: list of {query, answered, parse_failure} dicts
    """
    from api.services.geo_analyzer import _call_ai  # type: ignore

    queries = [q.get("query", "").strip() for q in original_query_table if q.get("query")]
    if not queries:
        return 0.0, []

    q_block = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(queries))

    # For long rewrites use head + tail so the intro and conclusion are both visible.
    # Budget: 6000 chars total = 4000 head + 2000 tail (avoids duplicating short texts).
    _HEAD = 4000
    _TAIL = 2000
    if len(rewrite_text) <= _HEAD + _TAIL:
        text_sample = rewrite_text
    else:
        text_sample = rewrite_text[:_HEAD] + "\n…\n" + rewrite_text[-_TAIL:]

    prompt = (
        f"You are scoring how well a web page answers user questions.\n\n"
        f"PAGE TEXT:\n{text_sample}\n\n"
        f"QUESTIONS:\n{q_block}\n\n"
        f"For each question, output a single line in the EXACT format:\n"
        f"  N: <Yes|Partial|No>\n"
        f"where N is the question number. Output one line per question, "
        f"in question order. No other text, no commentary.\n\n"
        f"Example output for 3 questions:\n"
        f"  1: Yes\n"
        f"  2: Partial\n"
        f"  3: No\n"
    )
    try:
        response = await _call_ai(prompt, model, provider)
        per_query = parse_verdict_response(response, queries)
        # Log per-query parse failures (helps diagnose silent regressions)
        n_parse_fail = sum(1 for r in per_query if r.get("parse_failure"))
        if n_parse_fail:
            logger.warning(
                "query_match_parse_failure",
                extra={
                    "n_queries": len(queries),
                    "n_parse_failure": n_parse_fail,
                },
            )
        # Score: Yes=1, Partial=0.5, No=0.  parse_failure rows count as
        # Partial under §6.3's bias-toward-recoverable-default rule.
        answered = sum(1 for r in per_query if r["answered"] == "Yes")
        partial = sum(1 for r in per_query if r["answered"] == "Partial")
        total = len(queries)
        score = (answered + 0.5 * partial) / total if total else 0.0
        return round(score, 4), per_query
    except Exception as e:
        logger.warning("query_match_rescore_failed", extra={"error": str(e)})
        return 0.0, []


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
# Per-check fix instructions for the improvement prompt
# ---------------------------------------------------------------------------

_CONTENT_FIX_INSTRUCTIONS: dict[str, str] = {
    "EXTERNAL_CITATIONS_LOW": (
        "**EXTERNAL_CITATIONS_LOW** — No citation or markdown link found in the body text.\n"
        "Fix: Add at least one `[text](https://url)` markdown link to a source ONLY if that "
        "source already appeared in the original. Otherwise embed "
        "`[CITATION NEEDED: describe the source type]` INLINE in the body — at the point in "
        "the paragraph where the citation belongs.\n"
        "✅ DO: _This approach reduces latency [CITATION NEEDED: peer-reviewed benchmark study]._\n"
        "❌ DO NOT: _This approach reduces latency 40% according to a Stanford study._\n"
        "  (The '40%' figure and 'Stanford study' attribution were not in the original — "
        "this is fabrication.)\n"
        "⚠️  Listing it in GEO NOTES does NOT count. It must appear in the body paragraph."
    ),
    "STATISTICS_COUNT_LOW": (
        "**STATISTICS_COUNT_LOW** — No specific number with a unit found in the body text.\n"
        "Fix: Add at least one concrete figure (percentage, time, count, size) ONLY if it "
        "appeared in the original. Otherwise embed `[STATISTIC: describe what data is needed]` "
        "INLINE in the body at the relevant point.\n"
        "✅ DO: _Setup time varies by infrastructure choice [STATISTIC: typical setup duration]._\n"
        "❌ DO NOT: _Setup typically takes under 45 minutes [STATISTIC: median setup time]._\n"
        "  (The number '45 minutes' was not in the original — this is fabrication.)\n"
        "⚠️  Listing it in GEO NOTES does NOT count. It must appear in the body paragraph."
    ),
    "QUOTATIONS_MISSING": (
        "**QUOTATIONS_MISSING** — No attribution phrase or blockquote found in the body.\n"
        "Fix (choose one): Add an attribution that already appeared in the original, OR add a "
        "Markdown blockquote (> text) preserving original wording, OR embed "
        "`[QUOTE NEEDED: speaker and context]` INLINE at the relevant point.\n"
        "✅ DO: _Per the project's official documentation, [QUOTE NEEDED: capability claim from "
        "primary source]._\n"
        "❌ DO NOT: _According to the Supabase documentation, pgvector supports cosine similarity._\n"
        "  (Both the 'Supabase' attribution and the 'cosine similarity' technical claim were "
        "not in the original — this is fabrication.)\n"
        "⚠️  Listing it in GEO NOTES does NOT count. It must appear in the body paragraph."
    ),
    "STRUCTURED_ELEMENTS_LOW": (
        "**STRUCTURED_ELEMENTS_LOW** — No Markdown list, table, or code block found.\n"
        "Fix: Convert existing prose into structured form. Bulleted/numbered lists for steps, "
        "tables for comparisons, code blocks for syntax. Use only content that already exists "
        "in the page — do NOT invent items just to fill a table.\n"
        "✅ DO: _Convert the setup paragraph into a numbered list with one step per line._\n"
        "❌ DO NOT: _Invent a comparison table listing competing platforms not mentioned in "
        "the original (e.g. 'OpenBrain vs MemGPT vs Mem0' according to a 2024 benchmark)._\n"
        "  (Adding fabricated structural elements is worse than the missing structure itself.)"
    ),
    "STRUCTURED_ELEMENTS_LOW_TECHNICAL": (
        "**STRUCTURED_ELEMENTS_LOW** (technical page) — No code block AND no numbered "
        "procedure with ≥3 steps was found.\n"
        "Fix: Add a code block showing actual configuration, syntax, or commands "
        "(e.g. MCP config JSON, shell setup commands) that already appear in the original. "
        "If no code is justified, convert the setup section to a numbered list with at "
        "least 3 steps.\n"
        "✅ DO: _Format the existing 5-step setup section as a numbered list._\n"
        "❌ DO NOT: _Invent code samples or commands that did not appear in the original page._"
    ),
    "STRUCTURED_ELEMENTS_LOW_COMPARISON": (
        "**STRUCTURED_ELEMENTS_LOW** (comparison page) — No comparison table with ≥2 "
        "data rows AND no named-list contrasting at least two options was found.\n"
        "Fix: Add a Markdown table with rows for each compared item (already named in the "
        "original) and columns for each compared dimension. Tables are the most extractable "
        "format for 'X vs Y' queries.\n"
        "✅ DO: _Add a 3-row table comparing the alternatives that the original page already "
        "names, using the dimensions discussed in the prose._\n"
        "❌ DO NOT: _Invent rows for products not mentioned in the original._"
    ),
    "STRUCTURED_ELEMENTS_LOW_FAQ": (
        "**STRUCTURED_ELEMENTS_LOW** (FAQ page) — Fewer than 3 Q&A pairs detected.\n"
        "Fix: Restore or split existing content into at least 3 Q&A pairs. Each pair is a "
        "question heading or question-word line followed by a 1–4 sentence answer.\n"
        "✅ DO: _Split the existing FAQ section into ≥3 distinct question/answer pairs._\n"
        "❌ DO NOT: _Invent Q&A pairs to hit the threshold — restore them from the original instead._"
    ),
    "FIRST_VIEWPORT_NO_ANSWER": (
        "**FIRST_VIEWPORT_NO_ANSWER** — The first 100–200 words do not contain a direct answer.\n"
        "Fix: Rewrite the intro so the first sentence states what the subject IS, concretely. "
        "Use only facts that appear in the original.\n"
        "✅ DO: _OpenBrain is a personal AI memory database that stores your context in a "
        "database you control._\n"
        "❌ DO NOT: _OpenBrain is the leading personal AI memory database, adopted by millions "
        "of users according to recent benchmarks._\n"
        "  ('Leading' and 'millions of users according to recent benchmarks' are unsupported "
        "superlatives — this is fabrication.)\n"
        "Do NOT start with 'In this guide…', 'Many users face…', or 'Let's explore…'."
    ),
}


# ---------------------------------------------------------------------------
# Improvement-mode prompt builder
# ---------------------------------------------------------------------------

_REGRESSION_FIX_INSTRUCTIONS: dict[str, str] = {
    "FAQ_REMOVED": (
        "### RESTORE FAQ / Q&A SECTION\n"
        "The previous draft removed the FAQ section. This is a FAILURE CONDITION.\n"
        "- Find the FAQ questions from the original and restore them as a dedicated "
        "section with the Q&A format: **Question?** followed by a 1–4 sentence answer.\n"
        "- Do NOT convert Q&A content into prose paragraphs.\n"
    ),
    "CODE_BLOCK_REMOVED": (
        "### RESTORE CODE BLOCK(S)\n"
        "The previous draft removed one or more code blocks. This is a FAILURE CONDITION.\n"
        "- Restore every code block from the original verbatim (language and content).\n"
        "- If you cannot locate the exact code, add a `[CODE EXAMPLE: describe what it shows]` "
        "placeholder at the relevant location.\n"
    ),
    "TABLE_REMOVED": (
        "### RESTORE TABLE(S)\n"
        "The previous draft removed one or more Markdown tables. This is a FAILURE CONDITION.\n"
        "- Restore every table from the original with the same rows and columns.\n"
        "- Comparison tables (naming competing products or platforms) are especially important "
        "for AI retrieval — they must appear intact.\n"
    ),
    "OUTBOUND_LINK_REMOVED": (
        "### RESTORE OUTBOUND CITATION LINKS\n"
        "The previous draft removed all external links. This is a FAILURE CONDITION.\n"
        "- Restore every `[text](https://...)` link from the original.\n"
        "- If a link cannot be verified, use `[SOURCE NEEDED: describe source type]` inline.\n"
    ),
    "NAMED_LIST_GENERICISED": (
        "### RESTORE NAMED LISTS\n"
        "The previous draft replaced specific tool/platform names with generic descriptions. "
        "This is a FAILURE CONDITION.\n"
        "- Restore the actual product/tool/platform names (e.g. 'Supabase', 'Claude Desktop', "
        "'ChatGPT Memory') — do NOT replace them with 'memory tools' or similar.\n"
    ),
}


_PAGE_TYPE_FIX_SUFFIX = {
    "technical": "_TECHNICAL",
    "comparison": "_COMPARISON",
    "faq": "_FAQ",
}


def _resolve_fix_instruction(code: str, page_type: str) -> str | None:
    """Look up the fix instruction for `code`, preferring page-type-specific
    variants (e.g. STRUCTURED_ELEMENTS_LOW_TECHNICAL) before the generic key.

    Returns None if neither key exists in _CONTENT_FIX_INSTRUCTIONS.
    """
    suffix = _PAGE_TYPE_FIX_SUFFIX.get(page_type)
    if suffix:
        specific = f"{code}{suffix}"
        if specific in _CONTENT_FIX_INSTRUCTIONS:
            return _CONTENT_FIX_INSTRUCTIONS[specific]
    return _CONTENT_FIX_INSTRUCTIONS.get(code)


def _build_improvement_prompt(
    original_system_prompt: str,
    attempt_num: int,
    total: int,
    failing_checks: list[str] | None = None,
    current_score: float = 0.0,
    placeholder_issues: list[str] | None = None,
    regression_violations: list[str] | None = None,
    page_type: str = "general",
) -> str:
    """
    Wrap the original system prompt with targeted improvement-mode framing.

    Tries 2+ receive the current best draft as input.  When failing_checks are
    provided (from _content_score), the prompt gives specific per-check instructions
    rather than a generic checklist — and explicitly warns about GEO NOTES placeholders
    and regression violations from the previous try.

    page_type lets the fix-instruction lookup choose page-type-specific variants
    (e.g. STRUCTURED_ELEMENTS_LOW_TECHNICAL for technical pages).
    """
    failing = failing_checks or []
    ph_issues = placeholder_issues or []
    regressions = regression_violations or []

    # Build targeted fix section (with page-type-specific dispatch per Fix 3 / §4.3)
    if failing:
        fix_lines = ["## FAILING CONTENT CHECKS — FIX THESE FIRST\n"]
        fix_lines.append(
            "These specific checks are failing and suppressing the score. "
            "Each one has an exact fix described below.\n"
        )
        for code in failing:
            instruction = _resolve_fix_instruction(code, page_type)
            if instruction:
                fix_lines.append(instruction)
                fix_lines.append("")
        targeted_fixes = "\n".join(fix_lines)
    else:
        targeted_fixes = (
            "## ALL CONTENT CHECKS PASSING\n\n"
            "Focus on query coverage and backward cross-references only."
        )

    # Build regression warning when previous try stripped high-value elements
    if regressions:
        reg_fix_lines = [
            "\n## ⛔ REGRESSIONS TO FIX — PREVIOUS ATTEMPT REMOVED REQUIRED ELEMENTS\n",
            "The previous attempt stripped content that MUST be preserved. "
            "Fix ALL of the following before addressing any other checks:\n",
        ]
        for code in regressions:
            if code in _REGRESSION_FIX_INSTRUCTIONS:
                reg_fix_lines.append(_REGRESSION_FIX_INSTRUCTIONS[code])
        regression_warning = "\n".join(reg_fix_lines)
    else:
        regression_warning = ""

    # Build inline-embedding warning when the LLM made the describe-not-embed mistake
    if ph_issues:
        ph_warning = (
            f"\n## ⚠️  CRITICAL MISTAKE IN PREVIOUS ATTEMPT\n\n"
            f"The previous attempt described these placeholders in GEO NOTES "
            f"instead of embedding them in the body text: **{', '.join(ph_issues)}**\n\n"
            f"GEO NOTES are a reporting section only — they do NOT count toward the score.\n"
            f"The placeholder MUST appear inline at the point in the paragraph where the "
            f"evidence belongs. See the fix instructions above for the correct format.\n"
        )
    else:
        ph_warning = ""

    score_pct = f"{current_score:.0%}" if current_score > 0 else "unknown"

    prefix = f"""\
## IMPROVEMENT MODE — ATTEMPT {attempt_num} OF {total}

You are improving an existing GEO rewrite draft. The current draft scores **{score_pct}**.
Do NOT rewrite from scratch. Work additively — add what is missing, preserve what is working.
{regression_warning}{ph_warning}
## PRESERVATION CONSTRAINT — READ FIRST

The current draft scores {score_pct}. Some content is already answering the key user queries
and contributing to that score. **Do not remove, shorten, or rephrase any sentence that
directly answers a user question.** If you are unsure whether removing something will hurt
the score, keep it.

Work additively:
- Add inline elements (citations, statistics, lists) where they are missing
- Fix backward cross-references by replacing the pronoun with the actual concept name
- Strengthen sections that do not address a key query — ADD content, do not restructure

{targeted_fixes}

## SECONDARY CHECKLIST (after content checks are fixed)

1. **Backward cross-references** — Replace "as mentioned above", "this approach",
   "the aforementioned", "as we saw" with the actual concept name.
2. **Query coverage** — Each H2 section should address at least one key query.
   Strengthen any section that does not — by ADDING a sentence, not restructuring.
3. **Paragraph length** — Break paragraphs over 150 words into two focused paragraphs.

---
{original_system_prompt}"""
    return prefix


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

    # Extract preservation floor from original content so regression checks can
    # penalise variants that strip FAQ sections, code blocks, tables, etc.
    original_features = rewrite_prompt_result.get("preservation_floor")
    if original_features is None and page_content:
        original_features = _extract_preservation_floor(page_content)

    # Evolutionary rewrite state: after each try, use the best result so far
    # as the base content for the next try (Phase 4).
    current_best_text: str = ""
    current_best_score: float = -1.0
    current_best_failing: list[str] = []        # failing content checks of best variant
    current_best_ph_issues: list[str] = []      # placeholder issues of best variant
    current_best_regressions: list[str] = []    # regression violations of best variant
    baseline_score: float = 0.0  # score of try 1, used in improvement report

    # Knowledge ceiling tracking: per-variant per-query results
    # Structure: list indexed by variant, each entry is list[{query, answered}]
    all_per_query_results: list[list[dict]] = []

    for i in range(n):
        # Try 1 rewrites from original; subsequent tries improve the best result
        content_to_use = page_content if i == 0 or not current_best_text else current_best_text
        prompt_to_use = (
            system_prompt
            if i == 0
            else _build_improvement_prompt(
                system_prompt,
                attempt_num=i + 1,
                total=n,
                failing_checks=current_best_failing,
                current_score=current_best_score,
                placeholder_issues=current_best_ph_issues,
                regression_violations=current_best_regressions,
                page_type=page_type,
            )
        )

        result = await _generate_one_rewrite(content_to_use, prompt_to_use, model, provider, i)

        failing_checks: list[str] = []
        regressions: list[str] = []
        per_query_results: list[dict] = []
        placeholder_inventory: dict = {
            "partial_pass_checks": [],
            "placeholder_counts": {"citation": 0, "stat": 0, "quote": 0},
            "placeholder_density": 0.0,
        }
        if result.get("text"):
            issues, c_score, failing_checks, placeholder_inventory = _content_score(
                url, result["text"], page_type, original_features=original_features
            )
            # Extract regression violations separately for SSE reporting
            if original_features:
                regressions = _check_preservation_regression(original_features, result["text"])
            if query_table:
                new_qm_score, per_query_results = await _score_rewrite_query_match(
                    result["text"], query_table, model, provider
                )
                query_projected = _project_score_from_findings(findings_for_projection, new_qm_score)
                # Blend: query coverage + content quality (weights are provisional;
                # see _QUERY_COVERAGE_WEIGHT docstring).
                projected_score = round(
                    _QUERY_COVERAGE_WEIGHT * query_projected
                    + _CONTENT_QUALITY_WEIGHT * c_score,
                    4,
                )
            else:
                projected_score = c_score
        else:
            issues, c_score, projected_score = 999, 0.0, 0.0
        all_per_query_results.append(per_query_results)

        # Verify that placeholders mentioned in GEO NOTES were actually embedded in body
        placeholder_issues: list[str] = []
        if result.get("text"):
            body_text, notes_text = _split_body_and_notes(result["text"])
            placeholder_issues = _verify_geo_notes_placeholders(body_text, notes_text)
            if placeholder_issues:
                logger.warning(
                    "geo_rewrite_placeholder_not_embedded",
                    extra={"variant": i, "missing": placeholder_issues},
                )
            if regressions:
                logger.warning(
                    "geo_rewrite_preservation_regression",
                    extra={"variant": i, "violations": regressions},
                )

        result["issues"] = issues
        result["projected_score"] = projected_score
        result["placeholder_issues"] = placeholder_issues
        result["regressions"] = regressions
        result["placeholder_inventory"] = placeholder_inventory
        variants.append(result)

        # Record baseline from first try; update evolutionary best
        if i == 0:
            baseline_score = projected_score
        if result.get("text") and projected_score > current_best_score:
            current_best_score = projected_score
            current_best_text = result["text"]
            current_best_failing = failing_checks
            current_best_ph_issues = placeholder_issues
            current_best_regressions = regressions

        event = {
            "type": "variant",
            "index": i,
            "issues": issues,
            "projected_score": projected_score,
            "placeholder_issues": placeholder_issues,
            "placeholder_inventory": placeholder_inventory,
            "regressions": regressions,
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

    # Knowledge ceiling: find queries that scored "No" in every variant that had results.
    # A query at the knowledge ceiling cannot be answered by rewriting — it needs new content.
    #
    # Fix 5 / §6.3: a query with ANY parse-failure verdict is excluded from the
    # ceiling — we don't know what the LLM actually said.  Better to under-report
    # ceilings than to mark a query as a knowledge gap on the basis of a
    # malformed LLM response.
    knowledge_gaps: list[str] = []
    if all_per_query_results and query_table:
        all_queries = [q.get("query", "") for q in query_table if q.get("query")]
        for q_text in all_queries:
            # Collect this query's per-variant rows (full dict, not just verdict)
            verdict_rows = [
                r
                for per_query in all_per_query_results
                for r in per_query
                if r["query"] == q_text
            ]
            if not verdict_rows:
                continue
            any_parse_failure = any(r.get("parse_failure") for r in verdict_rows)
            all_no = all(r["answered"] == "No" for r in verdict_rows)
            if all_no and not any_parse_failure:
                knowledge_gaps.append(q_text)

    done_event = {
        "type": "done",
        "winner_index": winner_index,
        "winner_issues": winner.get("issues", 999),
        "winner_projected_score": winner.get("projected_score", 0.0),
        "winner_text": winner.get("text", ""),
        "knowledge_gaps": knowledge_gaps,
        "scoring_metadata": {
            "query_coverage_weight": _QUERY_COVERAGE_WEIGHT,
            "content_quality_weight": _CONTENT_QUALITY_WEIGHT,
            "weighting_validated": False,
        },
        "winner_placeholder_inventory": winner.get("placeholder_inventory", {
            "partial_pass_checks": [],
            "placeholder_counts": {"citation": 0, "stat": 0, "quote": 0},
            "placeholder_density": 0.0,
        }),
        "variants": [
            {
                "index": v["index"],
                "issues": v.get("issues", 999),
                "projected_score": v.get("projected_score", 0.0),
                "placeholder_issues": v.get("placeholder_issues", []),
                "placeholder_inventory": v.get("placeholder_inventory", {}),
                "regressions": v.get("regressions", []),
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
