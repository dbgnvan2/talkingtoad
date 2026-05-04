"""Page type inference for schema typing validation.

Infers page type (home, article, team_member, service, faq, contact, about, unknown)
from URL patterns, HTML signals, and schema hints. Used by schema_typing.py to
validate schema appropriateness.

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.4
Tests: tests/test_page_classifier.py
"""

import re
from urllib.parse import urlparse

from api.crawler.parser import ParsedPage


def infer_page_type(parsed_page: ParsedPage) -> str:
    """Infer page type from URL, headings, and schema hints.

    Purpose: Classify page into semantic type for schema validation
    Spec:    docs/specs/ai-readiness/v2-extended-module.md § 3.4
    Tests:   tests/test_page_classifier.py::test_infer_page_type_*

    Args:
        parsed_page: Parsed HTML page with title, headings, schema_blocks

    Returns:
        One of: 'home', 'article', 'team_member', 'service', 'faq',
                'contact', 'about', 'unknown'
    """
    # Step 1: URL path patterns (highest confidence)
    page_type = _infer_from_url(parsed_page.url)
    if page_type != "unknown":
        return page_type

    # Step 2: Schema hints (moderate confidence)
    page_type = _infer_from_schema(parsed_page)
    if page_type != "unknown":
        return page_type

    # Step 3: HTML structure signals (lower confidence)
    page_type = _infer_from_html_structure(parsed_page)
    if page_type != "unknown":
        return page_type

    return "unknown"


def _infer_from_url(url: str) -> str:
    """Infer page type from URL path patterns."""
    path = urlparse(url).path.lower()
    path = path.rstrip("/")

    # Home page: /, /index, /home
    if path in ("", "/", "/index", "/home", "/index.html", "/home.html"):
        return "home"

    # Team member: /team/*, /about/team/*, /staff/*, /author/*
    if re.match(r"^/(team|about/team|staff|author)/", path):
        return "team_member"

    # Service: /service*, /services/*, /solutions/*, /offerings/*
    if re.match(r"^/(services?|solutions|offerings|products?)/", path):
        return "service"

    # FAQ: /faq, /faqs, /help, /qa, /questions-and-answers
    if re.match(r"^/(faq|faqs|help|qa|q-and-a|questions-and-answers)/?$", path):
        return "faq"

    # Contact: /contact, /contact-us, /get-in-touch
    if re.match(r"^/(contact|contact-us|get-in-touch|reach-out)/?$", path):
        return "contact"

    # About: /about, /about-us, /our-story, /mission
    if re.match(r"^/(about|about-us|our-story|mission|vision|who-we-are)/?$", path):
        return "about"

    # Article: /blog/*, /article/*, /news/*, /post/*, /posts/*
    if re.match(r"^/(blog|article|articles|news|post|posts)/", path):
        return "article"

    return "unknown"


def _infer_from_schema(parsed_page: ParsedPage) -> str:
    """Infer page type from JSON-LD schema types."""
    if not parsed_page.schema_types:
        return "unknown"

    schema_types = {t.lower() for t in parsed_page.schema_types}

    # Explicit page type schemas
    if "homepage" in schema_types or "website" in schema_types:
        return "home"
    if "article" in schema_types or "newsarticle" in schema_types or "blogposting" in schema_types:
        return "article"
    if "person" in schema_types:
        return "team_member"
    if "service" in schema_types or "offer" in schema_types:
        return "service"
    if "faqpage" in schema_types:
        return "faq"
    if "contactpage" in schema_types:
        return "contact"
    if "aboutpage" in schema_types or "organization" in schema_types:
        return "about"

    return "unknown"


def _infer_from_html_structure(parsed_page: ParsedPage) -> str:
    """Infer page type from HTML structure signals."""
    # Home page signals: minimal text, logo, nav, CTA buttons
    h1_count = len(parsed_page.h1_tags)
    word_count = parsed_page.word_count or 0

    # Home pages typically short (< 500 words) with single H1
    if h1_count == 1 and word_count < 500:
        if parsed_page.og_title and "home" in parsed_page.og_title.lower():
            return "home"

    # Article signals: title + substantial text (>500 words)
    if h1_count == 1 and word_count >= 500:
        if parsed_page.meta_description:
            if any(p in parsed_page.meta_description.lower() for p in ["article", "blog", "read"]):
                return "article"

    return "unknown"
