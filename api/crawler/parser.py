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

    return ParsedPage(
        url=result.url,
        final_url=result.final_url,
        status_code=result.status_code,
        response_size_bytes=size_bytes,
        title=_extract_title(soup),
        meta_description=_extract_meta(soup, "description"),
        og_title=_extract_og(soup, "og:title"),
        og_description=_extract_og(soup, "og:description"),
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
        outline.append({"level": level, "text": tag.get_text(strip=True)})
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
    """Count <img> tags that are completely missing an alt attribute.

    Images with alt="" are intentionally decorative and are NOT flagged —
    per HTML spec and our own recommendation, empty alt is the correct way
    to mark a decorative image.  Only a completely absent alt attribute
    indicates the author forgot to describe the image.
    """
    count = 0
    for tag in soup.find_all("img"):
        if tag.get("alt") is None:
            count += 1
    return count


def _find_img_missing_alt_srcs(soup: BeautifulSoup, page_url: str = "") -> list[str]:
    """Return absolute src URLs of <img> tags that are completely missing an alt attribute."""
    from urllib.parse import urljoin
    srcs = []
    for tag in soup.find_all("img", src=True):
        if tag.get("alt") is None:
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
    return len(_find_empty_anchors(soup))


def _find_empty_anchors(soup: BeautifulSoup, page_url: str = "") -> list[str]:
    """Return absolute URLs of <a> tags with no visible anchor text or img alt text.

    Relative hrefs (e.g. "/" or "/about") are resolved to absolute URLs using
    *page_url* so the stored values are always actionable.
    """
    found: list[str] = []
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
        found.append(absolute)
    return found


def _extract_lang(soup: BeautifulSoup) -> str | None:
    """Return the value of the <html lang="..."> attribute, or None if absent or empty."""
    html_tag = soup.find("html")
    if not html_tag:
        return None
    lang = html_tag.get("lang", "")
    return lang.strip() if lang.strip() else None


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
