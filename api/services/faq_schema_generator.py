"""FAQPage JSON-LD generator (generate-and-advise).

Purpose: Build schema.org FAQPage structured data from FAQ Q&A pairs extracted
         from a page's RAW HTML, for the user to paste into their SEO plugin.
Spec:    docs/pending/2026-07-04_faq-schema-generator.md
Tests:   tests/test_faq_schema_generator.py

Safety / rules:
- **NO WordPress writes.** This module only produces text to copy/export. It
  never calls the WP API (CLAUDE.md WP-safety rule).
- **Never fabricate.** Only answers actually present in the HTML
  (>= _MIN_ANSWER_CHARS) are included. If fewer than _MIN_PAIRS usable pairs
  remain (e.g. answers are JS-injected on click), it REFUSES rather than emit a
  hollow shell or invent text.
- **Defence in depth (P14).** Any HTML/script fragment in a value is stripped to
  plain text before it reaches the JSON-LD.
"""

from __future__ import annotations

import json
import re

_MIN_ANSWER_CHARS = 40   # mirrors FAQ_ANSWERS_NOT_IN_HTML gate (docs/thresholds.md)
_MIN_PAIRS = 2           # a FAQPage with a single Q&A isn't worth marking up


def _plain(text: str) -> str:
    """Strip any tags and collapse whitespace so no markup/script reaches the
    JSON-LD. Answers arrive tag-free from the parser's text extraction; this is
    belt-and-braces."""
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    return " ".join(no_tags.split())


def generate_faqpage_schema(faq_blocks: list[dict] | None) -> dict:
    """Build a FAQPage JSON-LD document from parser ``faq_blocks``.

    Args:
        faq_blocks: list of ``{"question", "answer", "answer_char_count", ...}``
            as produced by ``parser._extract_faq_blocks``.

    Returns an envelope::

        {"jsonld": str | None, "question_count": int,
         "refused": bool, "reason": str | None}

    ``question_count`` is the number of usable pairs (answer present in HTML).
    On refusal ``jsonld`` is None and ``reason`` explains why — never a shell.
    """
    blocks = faq_blocks or []
    usable = [
        b for b in blocks
        if (b.get("question") or "").strip()
        and (b.get("answer") or "").strip()
        and b.get("answer_char_count", len((b.get("answer") or "").strip())) >= _MIN_ANSWER_CHARS
    ]

    if len(usable) < _MIN_PAIRS:
        total = len(blocks)
        if total == 0:
            reason = "No FAQ questions were found on this page."
        else:
            reason = (
                f"Only {len(usable)} of {total} FAQ answers are present in the page's HTML. "
                "The rest appear only after a JavaScript click, so they can't be turned into "
                "schema without inventing text. Make the answer text visible in the HTML source "
                "first (see FAQ_ANSWERS_NOT_IN_HTML), then regenerate."
            )
        return {"jsonld": None, "question_count": len(usable), "refused": True, "reason": reason}

    main_entity = [
        {
            "@type": "Question",
            "name": _plain(b["question"]),
            "acceptedAnswer": {"@type": "Answer", "text": _plain(b["answer"])},
        }
        for b in usable
    ]
    doc = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": main_entity,
    }
    return {
        "jsonld": json.dumps(doc, ensure_ascii=False, indent=2),
        "question_count": len(usable),
        "refused": False,
        "reason": None,
    }
