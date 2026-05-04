"""
JS rendering comparison service for GEO analysis.

Spec: docs/implementation_plan_geo_analyzer_2026-05-03.md#GEO.1.3b/c/d

Three checks:
- GEO.1.3b: JS_RENDERED_CONTENT_DIFFERS — rendered adds >20% more tokens
- GEO.1.3c: CONTENT_CLOAKING_DETECTED — rendered changes topic (Jaccard keywords < 0.3)
- GEO.1.3d: UA_CONTENT_DIFFERS — GPTBot/ClaudeBot get >20% less content than rendered

Playwright is optional: if not installed all three checks are skipped.
"""

import asyncio
import logging
import math
import re
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

_UA_GPTBOT = "GPTBot/1.0"
_UA_CLAUDEBOT = "ClaudeBot/1.0"
_UA_GENERIC = (
    "Mozilla/5.0 (compatible; TalkingToadBot/2.1; "
    "+https://talkingtoad.com/bot)"
)

_PLAYWRIGHT_TIMEOUT_MS = 5000  # hard timeout for page load
_DIFF_THRESHOLD = 0.20         # >20% token difference triggers issue
_JACCARD_THRESHOLD = 0.30      # < 0.30 similarity triggers cloaking warning
_TOP_N_KEYWORDS = 10


@dataclass
class JSRenderResult:
    url: str
    raw_tokens: set[str] = field(default_factory=set)
    rendered_tokens: set[str] = field(default_factory=set)
    gptbot_tokens: set[str] = field(default_factory=set)
    claudebot_tokens: set[str] = field(default_factory=set)
    playwright_available: bool = False
    error: str | None = None

    # Computed results
    js_rendered_content_differs: bool = False
    content_cloaking_detected: bool = False
    ua_content_differs: bool = False

    # Metrics for the report
    rendered_token_count: int = 0
    raw_token_count: int = 0
    added_token_ratio: float = 0.0
    topic_jaccard: float = 1.0
    gptbot_token_count: int = 0
    claudebot_token_count: int = 0


def _tokenize(html_or_text: str, *, is_html: bool = True) -> set[str]:
    """Extract lower-cased word tokens from HTML or plain text."""
    if is_html:
        try:
            soup = BeautifulSoup(html_or_text, "lxml")
            for noise in soup.find_all(["script", "style", "nav", "footer"]):
                noise.decompose()
            text = soup.get_text(separator=" ", strip=True)
        except Exception:
            text = html_or_text
    else:
        text = html_or_text
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return set(words)


def _tfidf_top_keywords(tokens: set[str], n: int = _TOP_N_KEYWORDS) -> set[str]:
    """Return top-n keywords by frequency (IDF not available without corpus; use TF only)."""
    _STOP = frozenset({
        "the", "and", "for", "are", "but", "not", "you", "all", "can",
        "has", "had", "was", "with", "this", "that", "from", "they",
        "will", "been", "have", "their", "which", "when", "your", "what",
        "each", "more", "also", "than", "into", "its", "our", "out",
    })
    from collections import Counter
    # Convert set to list (we already deduped via set — re-tokenize for freq)
    freq = Counter(t for t in tokens if t not in _STOP and len(t) > 3)
    return {w for w, _ in freq.most_common(n)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


async def _fetch_raw(url: str, user_agent: str) -> str:
    """Fetch raw HTML with a specific user agent."""
    headers = {"User-Agent": user_agent}
    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers=headers,
    ) as client:
        resp = await client.get(url)
        return resp.text


async def _render_with_playwright(url: str) -> str | None:
    """Render the page with Playwright and return the HTML after JS execution."""
    if not HAS_PLAYWRIGHT:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await asyncio.wait_for(
                page.goto(url, wait_until="networkidle"),
                timeout=_PLAYWRIGHT_TIMEOUT_MS / 1000,
            )
            content = await page.content()
            await browser.close()
            return content
    except Exception as e:
        logger.warning("playwright_render_failed", extra={"url": url, "error": str(e)})
        return None


async def run_js_render_checks(url: str) -> JSRenderResult:
    """
    Run GEO.1.3b/c/d checks for a URL.

    Returns JSRenderResult with computed flags and metrics.
    Gracefully degrades if Playwright is unavailable.
    """
    result = JSRenderResult(url=url, playwright_available=HAS_PLAYWRIGHT)

    if not HAS_PLAYWRIGHT:
        result.error = "Playwright not installed. Run: pip install playwright && playwright install chromium"
        return result

    try:
        # Fetch raw HTML with three user agents + Playwright concurrently
        raw_task = asyncio.create_task(_fetch_raw(url, _UA_GENERIC))
        gptbot_task = asyncio.create_task(_fetch_raw(url, _UA_GPTBOT))
        claudebot_task = asyncio.create_task(_fetch_raw(url, _UA_CLAUDEBOT))

        raw_html, gptbot_html, claudebot_html = await asyncio.gather(
            raw_task, gptbot_task, claudebot_task,
            return_exceptions=True,
        )

        rendered_html = await _render_with_playwright(url)

        # Tokenise — skip any fetch that errored
        if isinstance(raw_html, Exception):
            logger.warning("raw_fetch_failed", extra={"url": url, "error": str(raw_html)})
            raw_tokens: set[str] = set()
        else:
            raw_tokens = _tokenize(raw_html)

        if rendered_html:
            rendered_tokens = _tokenize(rendered_html)
        else:
            result.error = "Playwright render returned no content"
            return result

        if isinstance(gptbot_html, Exception):
            gptbot_tokens: set[str] = set()
        else:
            gptbot_tokens = _tokenize(gptbot_html)

        if isinstance(claudebot_html, Exception):
            claudebot_tokens: set[str] = set()
        else:
            claudebot_tokens = _tokenize(claudebot_html)

        result.raw_tokens = raw_tokens
        result.rendered_tokens = rendered_tokens
        result.gptbot_tokens = gptbot_tokens
        result.claudebot_tokens = claudebot_tokens

        # ── GEO.1.3b: JS_RENDERED_CONTENT_DIFFERS ────────────────────────
        added_tokens = rendered_tokens - raw_tokens
        rendered_size = len(rendered_tokens) or 1
        added_ratio = len(added_tokens) / rendered_size

        result.rendered_token_count = len(rendered_tokens)
        result.raw_token_count = len(raw_tokens)
        result.added_token_ratio = round(added_ratio, 3)

        if added_ratio > _DIFF_THRESHOLD:
            result.js_rendered_content_differs = True

            # ── GEO.1.3c: CONTENT_CLOAKING_DETECTED ──────────────────────
            # Compare top-N keywords of raw vs rendered
            raw_kw = _tfidf_top_keywords(raw_tokens)
            rendered_kw = _tfidf_top_keywords(rendered_tokens)
            jaccard = _jaccard(raw_kw, rendered_kw)
            result.topic_jaccard = round(jaccard, 3)

            if jaccard < _JACCARD_THRESHOLD:
                result.content_cloaking_detected = True

        # ── GEO.1.3d: UA_CONTENT_DIFFERS ─────────────────────────────────
        result.gptbot_token_count = len(gptbot_tokens)
        result.claudebot_token_count = len(claudebot_tokens)

        rendered_size = len(rendered_tokens) or 1
        gptbot_ratio = len(gptbot_tokens) / rendered_size
        claudebot_ratio = len(claudebot_tokens) / rendered_size

        # Flag if either AI UA gets >20% fewer tokens than the rendered page
        if gptbot_ratio < (1 - _DIFF_THRESHOLD) or claudebot_ratio < (1 - _DIFF_THRESHOLD):
            result.ua_content_differs = True

    except Exception as e:
        result.error = str(e)
        logger.exception("js_render_checks_failed", extra={"url": url})

    return result
