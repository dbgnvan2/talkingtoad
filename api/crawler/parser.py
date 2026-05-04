"""
HTML page parser for the TalkingToad crawler.

Extracts all Phase 1 and Phase 2 fields from a fetched page (spec §5.2, §3.1.2–3.1.6).
"""

import json
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from api.crawler.fetcher import FetchResult
from api.crawler.normaliser import is_same_domain

logger = logging.getLogger(__name__)


@dataclass
class ParsedLink:
    """A hyperlink found on a crawled page."""

    url: str
    text: str | None
    is_internal: bool


@dataclass
class ParsedPage:
    """All extracted fields for a single crawled page (spec §5.2)."""

    # Identity
    url: str                          # normalised URL that was fetched
    final_url: str                    # after any redirects
    status_code: int
    response_size_bytes: int

    # Metadata
    title: str | None
    meta_description: str | None
    og_title: str | None
    og_description: str | None
    og_image: str | None
    twitter_card: str | None
    canonical_url: str | None         # None if tag absent

    # Headings
    h1_tags: list[str]
    headings_outline: list[dict]      # [{"level": 1, "text": "..."}, ...]

    # Crawlability
    is_indexable: bool
    robots_directive: str | None      # raw value from meta or X-Robots-Tag header

    # Links
    links: list[ParsedLink]

    # Favicon (homepage only — None for all other pages)
    has_favicon: bool | None

    # Phase 2 fields (collected now, surfaced in Phase 2 UI)
    has_viewport_meta: bool
    schema_types: list[str]
    external_script_count: int
    external_stylesheet_count: int

    # v1.5 extension fields
    word_count: int | None = None
    crawl_depth: int | None = None
    pagination_next: str | None = None
    pagination_prev: str | None = None
    amphtml_url: str | None = None
    meta_refresh_url: str | None = None

    # Security signals (pre-computed during parse to avoid re-parsing HTML in issue_checker)
    mixed_content_count: int = 0         # HTTP resources on an HTTPS page
    unsafe_cross_origin_count: int = 0   # target=_blank without noopener/noreferrer
    has_hsts: bool | None = None         # None = HTTP page; True/False = HTTPS page

    # v1.5 bug-fix / new check fields
    img_missing_alt_count: int = 0       # <img> tags missing or empty alt attribute
    img_missing_alt_srcs: list = None   # list[str] of src URLs for images missing alt
    image_urls: list = None              # list[str] of image src URLs (for broken image checks)
    empty_anchor_count: int = 0          # <a> tags with no visible text
    empty_anchor_hrefs: list = None      # list[str] of the offending hrefs
    internal_nofollow_count: int = 0     # internal links with rel="nofollow"

    # v1.6 new fields
    robots_source: str = "meta"          # "header" | "meta" — where the directive came from
    lang_attr: str | None = None         # value of <html lang="..."> attribute
    redirect_url: str | None = None      # if page redirects, the target URL

    # v1.7 AI-Readiness fields
    text_to_html_ratio: float | None = None
    code_breakdown: dict | None = None  # KB breakdown: text, script, style, svg, markup
    has_json_ld: bool = False
    pdf_metadata: dict | None = None

    # v2.0 Schema Typing fields
    schema_blocks: list[dict] | None = None  # list of full JSON-LD objects (not just type names)

    # v1.9.2 Staleness detection
    last_modified: str | None = None  # Last-Modified header value (set by engine)

    # v1.9 Image Intelligence fields
    image_data: list = None  # list[dict] - comprehensive image data for ImageInfo

    # v2.1 GEO Analyzer fields
    is_spa_shell: bool = False           # raw HTML is a JS app shell with near-zero text
    author_detected: bool = False        # rel=author / itemprop=author / byline class found
    date_published: str | None = None    # datePublished from JSON-LD or <meta>
    date_modified: str | None = None     # dateModified from JSON-LD
    code_block_count: int = 0            # <pre> + <code> elements
    table_count: int = 0                 # <table> elements
    structured_element_count: int = 0    # <ul>+<ol>+<table>+<dl>+<pre>+<code>
    first_150_words: str | None = None   # first 200 words of visible body text (name kept for back-compat)
    blockquote_count: int = 0            # <blockquote> elements

    # Tier 1 GEO heuristic counts (spec §4.3–4.6) — pre-computed in parser
    vague_opener_count: int = 0          # H2/H3 sections starting with vague demonstrative
    cross_reference_count: int = 0       # backward-reference phrases ("as mentioned above" etc.)
    long_paragraph_count: int = 0        # <p> tags exceeding 150 words
    query_coverage_weak: bool = False    # H1 tokens under-represented in intro or H2 headings


def parse_page(
    result: FetchResult,
    base_url: str,
    *,
    is_homepage: bool = False,
) -> ParsedPage:
    """Parse *result* and return a :class:`ParsedPage`.

    Args:
        result: The fetch result containing HTML and headers.
        base_url: The crawl root URL — used for classifying internal vs external links.
        is_homepage: True if *result.url* is the crawl's start URL.
    """
    page_url = result.final_url or result.url
    size_bytes = len(result.html.encode("utf-8")) if result.html else 0

    if not result.html:
        # Non-HTML response or failed fetch — return a minimal record
        return ParsedPage(
            url=result.url,
            final_url=result.final_url,
            status_code=result.status_code,
            response_size_bytes=size_bytes,
            title=None,
            meta_description=None,
            og_title=None,
            og_description=None,
            og_image=None,
            twitter_card=None,
            canonical_url=None,
            h1_tags=[],
            headings_outline=[],
            is_indexable=True,
            robots_directive=None,
            robots_source="meta",
            links=[],
            has_favicon=None,
            has_viewport_meta=False,
            schema_types=[],
            external_script_count=0,
            external_stylesheet_count=0,
            img_missing_alt_count=0,
            image_urls=[],
            empty_anchor_count=0,
            internal_nofollow_count=0,
            lang_attr=None,
        )

    soup = BeautifulSoup(result.html, "lxml")

    is_indexable, robots_directive, robots_source = _parse_robots_signals(soup, result.headers)

    # Calculate text-to-html ratio and code breakdown
    text_to_html_ratio = None
    _code_breakdown = None
    if result.html:
        visible_text = soup.get_text()
        if result.response_size_bytes > 0:
            text_to_html_ratio = len(visible_text) / result.response_size_bytes
            # Calculate what's taking up the space
            script_bytes = sum(len(str(s)) for s in soup.find_all("script"))
            style_bytes = sum(len(str(s)) for s in soup.find_all("style"))
            svg_bytes = sum(len(str(s)) for s in soup.find_all("svg"))
            html_total = result.response_size_bytes
            text_bytes = len(visible_text.encode("utf-8", errors="replace"))
            markup_bytes = html_total - script_bytes - style_bytes - svg_bytes - text_bytes
            _code_breakdown = {
                "html_total_kb": round(html_total / 1024, 1),
                "text_kb": round(max(0, text_bytes) / 1024, 1),
                "script_kb": round(script_bytes / 1024, 1),
                "style_kb": round(style_bytes / 1024, 1),
                "svg_kb": round(svg_bytes / 1024, 1),
                "markup_kb": round(max(0, markup_bytes) / 1024, 1),
            }

    # PDF metadata
    pdf_metadata = None
    if "pdf" in result.content_type and result.content:
        pdf_metadata = _extract_pdf_metadata(result.content)

    return ParsedPage(
        url=result.url,
        final_url=result.final_url,
        status_code=result.status_code,
        response_size_bytes=size_bytes,
        title=_extract_title(soup),
        meta_description=_extract_meta(soup, "description"),
        og_title=_extract_og(soup, "og:title"),
        og_description=_extract_og(soup, "og:description"),
        og_image=_extract_og(soup, "og:image"),
        twitter_card=_extract_meta(soup, "twitter:card"),
        canonical_url=_extract_canonical(soup, page_url),
        h1_tags=_extract_h1s(soup),
        headings_outline=_extract_headings_outline(soup),
        is_indexable=is_indexable,
        robots_directive=robots_directive,
        robots_source=robots_source,
        links=_extract_links(soup, page_url, base_url),
        has_favicon=_check_favicon(soup) if is_homepage else None,
        has_viewport_meta=_has_viewport_meta(soup),
        schema_types=_extract_schema_types(soup),
        schema_blocks=_extract_schema_blocks(soup),
        external_script_count=_count_external_scripts(soup, page_url),
        external_stylesheet_count=_count_external_stylesheets(soup, page_url),
        word_count=_count_words(soup),
        pagination_next=_extract_link_rel(soup, "next"),
        pagination_prev=_extract_link_rel(soup, "prev"),
        amphtml_url=_extract_link_rel(soup, "amphtml"),
        meta_refresh_url=_extract_meta_refresh_url(soup),
        mixed_content_count=_count_mixed_content(soup, page_url),
        unsafe_cross_origin_count=_count_unsafe_cross_origin(soup, page_url),
        has_hsts=_check_hsts(result.headers, page_url),
        img_missing_alt_count=_count_img_missing_alt(soup),
        img_missing_alt_srcs=_find_img_missing_alt_srcs(soup, page_url),
        image_urls=_extract_image_urls(soup, page_url),
        empty_anchor_count=_count_empty_anchors(soup),
        empty_anchor_hrefs=_find_empty_anchors(soup, page_url),
        internal_nofollow_count=_count_internal_nofollow(soup, page_url, base_url),
        lang_attr=_extract_lang(soup),
        # v1.7 AI-Readiness fields
        text_to_html_ratio=text_to_html_ratio,
        code_breakdown=_code_breakdown,
        has_json_ld=_has_json_ld_script(soup),
        pdf_metadata=pdf_metadata,
        # v1.9 Image Intelligence
        image_data=_extract_image_data(soup, page_url),
        # v2.1 GEO Analyzer fields
        is_spa_shell=_detect_spa_shell(soup),
        author_detected=_detect_author(soup),
        date_published=_extract_date_published(soup),
        date_modified=_extract_date_modified(soup),
        code_block_count=_count_code_blocks(soup),
        table_count=len(soup.find_all("table")),
        structured_element_count=_count_structured_elements(soup),
        first_150_words=_extract_first_n_words(soup, 200),
        blockquote_count=len(soup.find_all("blockquote")),
        # Tier 1 GEO heuristics (spec §4.3–4.6)
        vague_opener_count=_count_vague_openers(soup),
        cross_reference_count=_count_cross_references(soup),
        long_paragraph_count=_count_long_paragraphs(soup),
        query_coverage_weak=_check_query_coverage_weak(soup),
    )


# ---------------------------------------------------------------------------
# Private extraction helpers
# ---------------------------------------------------------------------------

def _extract_title(soup: BeautifulSoup) -> str | None:
    tag = soup.find("title")
    if not tag:
        return None
    text = tag.get_text(strip=True)
    return text if text else None


def _extract_meta(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    if not tag:
        return None
    content = tag.get("content", "")
    return content.strip() if content.strip() else None


def _extract_og(soup: BeautifulSoup, property_name: str) -> str | None:
    tag = soup.find("meta", property=property_name)
    if not tag:
        return None
    content = tag.get("content", "")
    return content.strip() if content.strip() else None


def _extract_canonical(soup: BeautifulSoup, page_url: str) -> str | None:
    tag = soup.find("link", rel=lambda r: r and "canonical" in r)
    if not tag:
        return None
    href = tag.get("href", "").strip()
    if not href:
        return None
    # Resolve relative canonical URLs
    return urljoin(page_url, href)


def _extract_h1s(soup: BeautifulSoup) -> list[str]:
    return [h.get_text(strip=True) for h in soup.find_all("h1")]


def _extract_headings_outline(soup: BeautifulSoup) -> list[dict]:
    outline = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        level = int(tag.name[1])
        classes = " ".join(tag.get("class", []))
        entry: dict = {"level": level, "text": tag.get_text(strip=True)}
        if classes:
            entry["classes"] = classes
        outline.append(entry)
    return outline


def _parse_robots_signals(
    soup: BeautifulSoup, headers: dict[str, str]
) -> tuple[bool, str | None, str]:
    """Return (is_indexable, robots_directive, robots_source) from meta tags and headers.

    robots_source is ``"header"`` when the directive came from an X-Robots-Tag HTTP
    response header, and ``"meta"`` when it came from a ``<meta name="robots">`` tag.
    """
    directive: str | None = None
    source: str = "meta"

    # Check X-Robots-Tag header first
    x_robots = headers.get("x-robots-tag", "")
    if x_robots:
        directive = x_robots
        source = "header"
        if "noindex" in x_robots.lower():
            return False, directive, source

    # Check meta robots tag
    meta_robots = soup.find("meta", attrs={"name": lambda n: n and n.lower() == "robots"})
    if meta_robots:
        content = meta_robots.get("content", "").strip()
        if content:
            directive = content
            source = "meta"
            if "noindex" in content.lower():
                return False, directive, source

    return True, directive, source


def _extract_links(
    soup: BeautifulSoup, page_url: str, base_url: str
) -> list[ParsedLink]:
    links: list[ParsedLink] = []
    seen: set[str] = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue

        # Resolve relative URLs
        try:
            absolute = urljoin(page_url, href)
        except Exception:
            continue

        # Normalise for deduplication only — store original absolute for the link record
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue

        # Deduplicate within this page
        if absolute in seen:
            continue
        seen.add(absolute)

        internal = is_same_domain(absolute, base_url)
        text = tag.get_text(strip=True) or None
        links.append(ParsedLink(url=absolute, text=text, is_internal=internal))

    return links


def _check_favicon(soup: BeautifulSoup) -> bool:
    """Return True if a favicon link element is found (homepage only)."""
    for tag in soup.find_all("link"):
        rel = tag.get("rel", [])
        if isinstance(rel, str):
            rel = [rel]
        rel_lower = [r.lower() for r in rel]
        if "icon" in rel_lower or "shortcut icon" in rel_lower:
            return True
    return False


def _has_viewport_meta(soup: BeautifulSoup) -> bool:
    tag = soup.find("meta", attrs={"name": lambda n: n and n.lower() == "viewport"})
    return tag is not None


def _extract_schema_types(soup: BeautifulSoup) -> list[str]:
    """Extract @type values from JSON-LD scripts and microdata itemtype attributes."""
    types: list[str] = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                _collect_schema_types(data, types)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        _collect_schema_types(item, types)
        except (json.JSONDecodeError, TypeError):
            pass

    # Microdata
    for tag in soup.find_all(attrs={"itemtype": True}):
        itemtype = tag["itemtype"]
        # e.g. "https://schema.org/Organization" → "Organization"
        schema_type = itemtype.rstrip("/").rsplit("/", 1)[-1]
        if schema_type:
            types.append(schema_type)

    return list(dict.fromkeys(types))  # deduplicate, preserve order


def _collect_schema_types(data: dict, types: list[str]) -> None:
    t = data.get("@type")
    if isinstance(t, str) and t:
        types.append(t)
    elif isinstance(t, list):
        types.extend(v for v in t if isinstance(v, str) and v)
    # Yoast (and other plugins) wrap all types in a @graph array
    graph = data.get("@graph")
    if isinstance(graph, list):
        for node in graph:
            if isinstance(node, dict):
                _collect_schema_types(node, types)


def _extract_schema_blocks(soup: BeautifulSoup) -> list[dict] | None:
    """Extract full JSON-LD schema objects (for Phase 2.0 schema typing validation)."""
    blocks = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            # Flatten @graph arrays into top-level blocks
            if isinstance(data, dict):
                graph = data.get("@graph")
                if isinstance(graph, list):
                    blocks.extend(g for g in graph if isinstance(g, dict))
                else:
                    blocks.append(data)
            elif isinstance(data, list):
                blocks.extend(item for item in data if isinstance(item, dict))
        except (json.JSONDecodeError, TypeError):
            pass

    return blocks if blocks else None


def _count_external_scripts(soup: BeautifulSoup, page_url: str) -> int:
    count = 0
    for tag in soup.find_all("script", src=True):
        src = tag["src"].strip()
        if src and not src.startswith(("javascript:", "data:")):
            absolute = urljoin(page_url, src)
            if not is_same_domain(absolute, page_url):
                count += 1
    return count


def _count_external_stylesheets(soup: BeautifulSoup, page_url: str) -> int:
    count = 0
    for tag in soup.find_all("link", rel=True):
        rel = tag.get("rel", [])
        if isinstance(rel, str):
            rel = [rel]
        if "stylesheet" not in [r.lower() for r in rel]:
            continue
        href = tag.get("href", "").strip()
        if href:
            absolute = urljoin(page_url, href)
            if not is_same_domain(absolute, page_url):
                count += 1
    return count


_EXCLUDED_TAGS = {"nav", "header", "footer", "aside", "script", "style"}


def _count_words(soup: BeautifulSoup) -> int:
    """Count visible body words, excluding navigation/chrome elements (spec §E5)."""
    body = soup.find("body")
    if not body:
        return 0
    # Deep copy to avoid decompose() corrupting the original soup tree
    import copy
    body_copy = copy.deepcopy(body)
    for tag in body_copy.find_all(_EXCLUDED_TAGS):
        tag.decompose()
    text = body_copy.get_text(separator=" ")
    return len(text.split())


def _extract_link_rel(soup: BeautifulSoup, rel_value: str) -> str | None:
    """Return the href of the first <link rel="..."> matching *rel_value*, or None."""
    tag = soup.find("link", rel=lambda r: r and rel_value in (r if isinstance(r, list) else [r]))
    if not tag:
        return None
    return tag.get("href", "").strip() or None


def _extract_meta_refresh_url(soup: BeautifulSoup) -> str | None:
    """Return the redirect URL from a meta refresh tag, or None if absent/reload-only."""
    tag = soup.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "refresh"})
    if not tag:
        return None
    content = tag.get("content", "")
    # content may be "0; url=/new-page" or just "30" (page reload)
    lower = content.lower()
    if "url=" not in lower:
        return None
    # Extract everything after url=
    idx = lower.index("url=") + 4
    return content[idx:].strip() or None


_MIXED_CONTENT_TAGS = {
    "img": "src",
    "script": "src",
    "iframe": "src",
}


def _count_mixed_content(soup: BeautifulSoup, page_url: str) -> int:
    """Count HTTP resources on an HTTPS page (mixed content)."""
    if not page_url.startswith("https://"):
        return 0
    count = 0
    for tag_name, attr in _MIXED_CONTENT_TAGS.items():
        for tag in soup.find_all(tag_name):
            val = tag.get(attr, "")
            if val.startswith("http://"):
                count += 1
    # Stylesheets via <link rel="stylesheet">
    for tag in soup.find_all("link"):
        rel = tag.get("rel", [])
        if isinstance(rel, str):
            rel = [rel]
        if "stylesheet" in [r.lower() for r in rel]:
            href = tag.get("href", "")
            if href.startswith("http://"):
                count += 1
    return count


def _count_unsafe_cross_origin(soup: BeautifulSoup, page_url: str) -> int:
    """Count external target=_blank links missing noopener/noreferrer."""
    count = 0
    for tag in soup.find_all("a", href=True):
        target = tag.get("target", "")
        if target.lower() != "_blank":
            continue
        href = tag.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        try:
            absolute = urljoin(page_url, href)
        except Exception:
            continue
        if is_same_domain(absolute, page_url):
            continue  # internal link — not a cross-origin concern
        rel_val = tag.get("rel", [])
        if isinstance(rel_val, str):
            rel_val = rel_val.split()
        rel_lower = [r.lower() for r in rel_val]
        if "noopener" not in rel_lower and "noreferrer" not in rel_lower:
            count += 1
    return count


def _check_hsts(headers: dict[str, str], page_url: str) -> bool | None:
    """Return True/False for HTTPS pages (HSTS present/absent), None for HTTP pages."""
    if not page_url.startswith("https://"):
        return None
    return "strict-transport-security" in {k.lower() for k in headers}


def _count_img_missing_alt(soup: BeautifulSoup) -> int:
    """Count <img> tags that are missing or have empty/blank alt attributes.

    Both missing alt and empty alt="" are flagged — every meaningful image
    should have descriptive alt text for accessibility and SEO.
    """
    count = 0
    for tag in soup.find_all("img"):
        alt = tag.get("alt")
        # Flag if alt is missing (None) or empty/whitespace-only
        if alt is None or (isinstance(alt, str) and not alt.strip()):
            count += 1
    return count


def _find_img_missing_alt_srcs(soup: BeautifulSoup, page_url: str = "") -> list[str]:
    """Return absolute src URLs of <img> tags that are missing or have empty alt attributes."""
    from urllib.parse import urljoin
    srcs = []
    for tag in soup.find_all("img", src=True):
        alt = tag.get("alt")
        # Flag if alt is missing (None) or empty/whitespace-only
        if alt is None or (isinstance(alt, str) and not alt.strip()):
            src = tag["src"].strip()
            if src and not src.startswith("data:"):
                srcs.append(urljoin(page_url, src) if page_url else src)
    return srcs


def _extract_image_urls(soup: BeautifulSoup, page_url: str) -> list[str]:
    """Return absolute URLs of all <img src> attributes on the page (for broken-image checks)."""
    urls: list[str] = []
    for tag in soup.find_all("img", src=True):
        src = tag["src"].strip()
        if not src or src.startswith("data:"):
            continue
        try:
            absolute = urljoin(page_url, src)
        except Exception:
            continue
        parsed = urlparse(absolute)
        if parsed.scheme in ("http", "https"):
            urls.append(absolute)
    return urls


def _count_empty_anchors(soup: BeautifulSoup) -> int:
    """Count <a href> tags whose visible text (and alt text of any child img) is empty."""
    anchors = _find_empty_anchors(soup)
    # Only count those without an aria-label as truly empty
    return sum(1 for a in anchors if not a.get("aria_label"))


def _find_empty_anchors(soup: BeautifulSoup, page_url: str = "") -> list[dict]:
    """Return info about <a> tags with no visible anchor text or img alt text.

    Each entry is a dict with:
      - href: absolute URL of the link
      - aria_label: aria-label value if present, else None
      - has_children: bool — True if the <a> contains child elements (icons, SVGs, etc.)

    Links with a non-empty aria-label are still included (so the user can see
    them and decide), but flagged so the UI can display them differently.

    Relative hrefs are resolved to absolute URLs using *page_url*.
    """
    found: list[dict] = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue
        # Check visible text
        if tag.get_text(strip=True):
            continue
        # Allow img-only links with an alt attribute as valid
        child_imgs = tag.find_all("img")
        if child_imgs and any(img.get("alt", "").strip() for img in child_imgs):
            continue
        # Resolve relative hrefs to absolute URLs
        absolute = urljoin(page_url, href) if page_url else href
        aria_label = (tag.get("aria-label") or "").strip() or None
        has_children = len(tag.find_all()) > 0
        found.append({
            "href": absolute,
            "aria_label": aria_label,
            "has_children": has_children,
        })
    return found


def _extract_lang(soup: BeautifulSoup) -> str | None:
    """Return the value of the <html lang="..."> attribute, or None if absent or empty."""
    html_tag = soup.find("html")
    if not html_tag:
        return None
    lang = html_tag.get("lang", "")
    return lang.strip() if lang.strip() else None


def _has_json_ld_script(soup: BeautifulSoup) -> bool:
    """Return True if the page contains a <script type="application/ld+json"> tag."""
    return soup.find("script", type="application/ld+json") is not None


def _extract_pdf_metadata(content: bytes) -> dict | None:
    """Extract Title and Subject from PDF binary content using pypdf."""
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        metadata = reader.metadata
        if not metadata:
            return None
        return {
            "title": metadata.title.strip() if metadata.title else None,
            "subject": metadata.subject.strip() if metadata.subject else None,
        }
    except Exception:
        return None


def _count_internal_nofollow(soup: BeautifulSoup, page_url: str, base_url: str) -> int:
    """Count internal links that carry rel="nofollow"."""
    count = 0
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue
        try:
            absolute = urljoin(page_url, href)
        except Exception:
            continue
        if not is_same_domain(absolute, base_url):
            continue  # only flag internal links
        rel_val = tag.get("rel", [])
        if isinstance(rel_val, str):
            rel_val = rel_val.split()
        if "nofollow" in [r.lower() for r in rel_val]:
            count += 1
    return count


# ---------------------------------------------------------------------------
# v1.9 Image Intelligence - Enhanced Image Extraction
# ---------------------------------------------------------------------------


def _extract_image_data(soup: BeautifulSoup, page_url: str) -> list[dict]:
    """Extract comprehensive image data from page for ImageInfo creation.

    Returns a list of dicts with all HTML-level metadata for each image.
    The engine will merge this with fetched data (dimensions, size, etc.).
    """
    images = []
    for tag in soup.find_all("img", src=True):
        src = tag["src"].strip()
        if not src or src.startswith("data:"):
            continue

        try:
            absolute_url = urljoin(page_url, src)
        except Exception:
            continue

        parsed = urlparse(absolute_url)
        if parsed.scheme not in ("http", "https"):
            continue

        # Extract filename from URL path
        filename = _extract_filename_from_url(absolute_url)

        img_data = {
            "url": absolute_url,
            "page_url": page_url,
            "alt": tag.get("alt"),  # None if missing, "" if empty
            "title": tag.get("title"),
            "filename": filename,
            "rendered_width": _parse_dimension(tag.get("width")),
            "rendered_height": _parse_dimension(tag.get("height")),
            "is_lazy_loaded": tag.get("loading", "").lower() == "lazy",
            "has_srcset": bool(tag.get("srcset")),
            "srcset_candidates": _parse_srcset(tag.get("srcset", ""), page_url),
            "is_decorative": _detect_decorative(tag),
            "surrounding_text": _extract_surrounding_text(tag, limit=300),
        }
        images.append(img_data)

    return images


def _detect_decorative(tag) -> bool:
    """Detect if image is decorative based on HTML attributes.

    An image is considered decorative if:
    - role="presentation"
    - aria-hidden="true"
    - alt="" (intentionally empty, not missing)
    - dimensions < 32px (likely spacer/icon)
    """
    # Explicit decorative markers
    if tag.get("role") == "presentation":
        return True
    if tag.get("aria-hidden") == "true":
        return True

    # Empty alt (intentionally decorative) - but NOT missing alt (None)
    alt = tag.get("alt")
    if alt is not None and isinstance(alt, str) and alt.strip() == "":
        return True

    # Tiny images (icons/spacers)
    try:
        w = int(tag.get("width", 999))
        h = int(tag.get("height", 999))
        if w < 32 and h < 32:
            return True
    except (ValueError, TypeError):
        pass

    return False


def _parse_srcset(srcset: str, page_url: str = "") -> list[str]:
    """Parse srcset attribute into list of absolute URLs.

    srcset format: "image1.jpg 1x, image2.jpg 2x" or "small.jpg 300w, large.jpg 800w"
    """
    if not srcset:
        return []

    candidates = []
    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue
        # First part before space is the URL
        url_part = part.split()[0] if part else ""
        if url_part:
            try:
                absolute = urljoin(page_url, url_part) if page_url else url_part
                candidates.append(absolute)
            except Exception:
                pass
    return candidates


def _extract_surrounding_text(tag, limit: int = 300) -> str:
    """Extract text context around an image tag (±limit chars).

    Helps with semantic analysis of whether image relates to page content.
    Default limit increased to 300 for GEO analysis (v1.9geo).
    """
    texts = []

    # Previous siblings
    for sib in tag.previous_siblings:
        if hasattr(sib, "get_text"):
            text = sib.get_text(strip=True)
            if text:
                texts.insert(0, text)
        elif isinstance(sib, str) and sib.strip():
            texts.insert(0, sib.strip())
        if sum(len(t) for t in texts) > limit:
            break

    # Next siblings
    for sib in tag.next_siblings:
        if hasattr(sib, "get_text"):
            text = sib.get_text(strip=True)
            if text:
                texts.append(text)
        elif isinstance(sib, str) and sib.strip():
            texts.append(sib.strip())
        if sum(len(t) for t in texts) > limit * 2:
            break

    result = " ".join(texts)
    # Trim to limit * 2 (before + after)
    return result[: limit * 2] if len(result) > limit * 2 else result


def _parse_dimension(value) -> int | None:
    """Parse an HTML width/height attribute value to int.

    Handles: "100", "100px", 100 (int)
    Returns None for invalid/missing values.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        # Remove 'px' suffix if present
        clean = value.strip().lower().replace("px", "").strip()
        try:
            return int(clean)
        except ValueError:
            return None
    return None


def _extract_filename_from_url(url: str) -> str:
    """Extract filename from URL path.

    e.g. "https://example.com/images/photo.jpg?v=1" -> "photo.jpg"
    """
    try:
        parsed = urlparse(url)
        path = parsed.path
        if path:
            # Get the last segment of the path
            filename = path.rstrip("/").rsplit("/", 1)[-1]
            return filename
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# v2.1 GEO Analyzer helpers
# ---------------------------------------------------------------------------

import re as _re

_SPA_SHELL_IDS = {"root", "app", "__next", "__nuxt", "react-root", "vue-app"}
_SPA_SHELL_TAGS = {"app-root", "ng-view", "ion-app"}


def _detect_spa_shell(soup: BeautifulSoup) -> bool:
    """Return True if the page looks like a JS app-shell with minimal raw text."""
    for id_val in _SPA_SHELL_IDS:
        tag = soup.find(id=id_val)
        if tag:
            inner = tag.get_text(strip=True)
            if len(inner) < 50:
                return True
    for tag_name in _SPA_SHELL_TAGS:
        if soup.find(tag_name):
            return True
    return False


_AUTHOR_CLASSES = _re.compile(
    r"\b(author|byline|contributor|writer|posted-by|entry-author)\b", _re.I
)


def _detect_author(soup: BeautifulSoup) -> bool:
    """Return True if an author signal is present."""
    # rel=author link
    if soup.find("a", rel=lambda r: r and "author" in r):
        return True
    # itemprop=author
    if soup.find(attrs={"itemprop": "author"}):
        return True
    # JSON-LD author field
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and "author" in data:
                return True
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "author" in item:
                        return True
        except Exception:
            pass
    # meta name=author
    if soup.find("meta", attrs={"name": "author"}):
        return True
    # class-based byline
    for tag in soup.find_all(True, class_=True):
        classes = " ".join(tag.get("class", []))
        if _AUTHOR_CLASSES.search(classes):
            return True
    return False


def _extract_date_published(soup: BeautifulSoup) -> str | None:
    """Extract datePublished from JSON-LD or <meta> tags."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and "datePublished" in item:
                    return str(item["datePublished"])
        except Exception:
            pass
    for attr in ("article:published_time", "og:article:published_time",
                 "datePublished", "date"):
        tag = soup.find("meta", attrs={"property": attr}) or \
              soup.find("meta", attrs={"name": attr})
        if tag and tag.get("content"):
            return tag["content"]
    return None


def _extract_date_modified(soup: BeautifulSoup) -> str | None:
    """Extract dateModified from JSON-LD or <meta> tags."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and "dateModified" in item:
                    return str(item["dateModified"])
        except Exception:
            pass
    for attr in ("article:modified_time", "og:article:modified_time",
                 "dateModified", "last-modified"):
        tag = soup.find("meta", attrs={"property": attr}) or \
              soup.find("meta", attrs={"name": attr})
        if tag and tag.get("content"):
            return tag["content"]
    return None


def _count_code_blocks(soup: BeautifulSoup) -> int:
    """Count <pre> and top-level <code> elements (not nested inside <pre>)."""
    pres = soup.find_all("pre")
    codes = [c for c in soup.find_all("code") if not c.find_parent("pre")]
    return len(pres) + len(codes)


def _count_structured_elements(soup: BeautifulSoup) -> int:
    """Count <ul>, <ol>, <table>, <dl>, <pre>, <code> elements."""
    total = 0
    for tag in ("ul", "ol", "table", "dl", "pre"):
        total += len(soup.find_all(tag))
    codes = [c for c in soup.find_all("code") if not c.find_parent("pre")]
    total += len(codes)
    return total


def _extract_first_n_words(soup: BeautifulSoup, n: int) -> str | None:
    """Extract first *n* words from visible body text."""
    body = soup.find("body") or soup
    # Remove script, style, nav, header, footer noise
    for noise in body.find_all(["script", "style", "nav", "header", "footer", "aside"]):
        noise.decompose()
    text = body.get_text(separator=" ", strip=True)
    words = text.split()
    if not words:
        return None
    return " ".join(words[:n])


# ---------------------------------------------------------------------------
# Tier 1 GEO heuristic helpers (spec §4.3–4.6)
# ---------------------------------------------------------------------------

import re as _re

_VAGUE_OPENER_RE = _re.compile(
    r"^(This|The|It|That|These|Those)\s+"
    r"(method|approach|system|technique|process|way|solution|tool|"
    r"feature|strategy|framework|concept|model|type|option|above)\b",
    _re.I,
)
_VAGUE_PRONOUN_RE = _re.compile(r"^(It|These|Those)\s+\w", _re.I)

_CROSS_REF_RE = _re.compile(
    r"\b(as mentioned above|as discussed earlier|as noted above|"
    r"as described above|as stated above|as covered above|as shown above|"
    r"the above|see above|refer to the previous)\b",
    _re.I,
)

_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "into", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "not", "no", "if", "as",
    "so", "this", "that", "these", "those", "it", "its", "your", "our",
    "my", "their", "you", "we", "i", "he", "she", "they", "what", "how",
    "when", "where", "who", "which", "why",
})


def _count_vague_openers(soup: BeautifulSoup) -> int:
    """Count H2/H3 sections whose first paragraph opens with a vague reference."""
    count = 0
    for h in soup.find_all(["h2", "h3"]):
        for sib in h.next_siblings:
            name = getattr(sib, "name", None)
            if name in ("h2", "h3"):
                break
            if name in ("p", "div", "section"):
                text = sib.get_text(separator=" ", strip=True)
                if text and (_VAGUE_OPENER_RE.match(text) or _VAGUE_PRONOUN_RE.match(text)):
                    count += 1
                break
            raw = getattr(sib, "string", None)
            if raw and raw.strip():
                t = raw.strip()
                if _VAGUE_OPENER_RE.match(t) or _VAGUE_PRONOUN_RE.match(t):
                    count += 1
                break
    return count


def _count_cross_references(soup: BeautifulSoup) -> int:
    """Count backward-reference phrases in visible body text."""
    body = soup.find("body") or soup
    for noise in body.find_all(["script", "style", "nav", "header", "footer"]):
        noise.decompose()
    text = body.get_text(separator=" ")
    return len(_CROSS_REF_RE.findall(text))


def _count_long_paragraphs(soup: BeautifulSoup, threshold: int = 150) -> int:
    """Count <p> elements whose word count exceeds threshold."""
    count = 0
    for p in soup.find_all("p"):
        if len(p.get_text(separator=" ", strip=True).split()) > threshold:
            count += 1
    return count


def _check_query_coverage_weak(soup: BeautifulSoup) -> bool:
    """True if H1 significant tokens are under-represented in intro or H2/H3 headings."""
    h1 = soup.find("h1")
    if not h1:
        return False
    h1_text = h1.get_text(strip=True).lower()
    tokens = [
        w for w in _re.findall(r"[a-z]+", h1_text)
        if w not in _STOP_WORDS and len(w) >= 3
    ]
    if len(tokens) < 2:
        return False

    # Need first 200 words of body text
    body = soup.find("body") or soup
    for noise in body.find_all(["script", "style", "nav", "header", "footer", "aside"]):
        noise.decompose()
    intro = " ".join(body.get_text(separator=" ", strip=True).split()[:200]).lower()

    intro_hits = sum(1 for t in tokens if t in intro)
    if intro_hits / len(tokens) < 0.5:
        return True  # query terms absent from intro

    # Check if any H2/H3 heading covers ≥50% of tokens
    h2h3 = [h.get_text(strip=True).lower() for h in soup.find_all(["h2", "h3"])]
    if not h2h3:
        return False
    return not any(
        sum(1 for t in tokens if t in h) / len(tokens) >= 0.5
        for h in h2h3
    )
