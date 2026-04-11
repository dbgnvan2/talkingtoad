"""
robots.txt fetching and parsing for the TalkingToad crawler.

Implements the rules from spec §3.1.5 and §3.1.7 (Sitemap: directives).
"""

import logging
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

# The user-agent name sent in crawl requests — must match what the fetcher uses
CRAWLER_AGENT = "NonprofitCrawler"

# Timeout for fetching robots.txt (seconds)
_FETCH_TIMEOUT = 5.0


class RobotsData:
    """Parsed result of a robots.txt fetch.

    Attributes:
        allowed (bool | None): None when robots.txt was unreachable (allow all).
        crawl_delay (float | None): Crawl-delay value in seconds, if present.
        sitemap_urls (list[str]): Sitemap URLs declared via ``Sitemap:`` directives.
        raw_text (str | None): The raw robots.txt body, for debugging.
    """

    def __init__(
        self,
        parser: RobotFileParser | None,
        crawl_delay: float | None,
        sitemap_urls: list[str],
        raw_text: str | None,
    ) -> None:
        self._parser = parser
        self.crawl_delay = crawl_delay
        self.sitemap_urls: list[str] = sitemap_urls
        self.raw_text = raw_text

    def is_allowed(self, url: str) -> bool:
        """Return True if the crawler is allowed to fetch *url*.

        When robots.txt was unreachable, all URLs are considered allowed
        (spec §3.1.5 — handle missing robots.txt gracefully).
        """
        if self._parser is None:
            return True
        return self._parser.can_fetch(CRAWLER_AGENT, url)


async def fetch_robots(base_url: str, client: httpx.AsyncClient) -> RobotsData:
    """Fetch and parse robots.txt for the domain of *base_url*.

    Args:
        base_url: Any URL on the target site — only scheme+host are used.
        client: An already-configured ``httpx.AsyncClient``.

    Returns:
        A :class:`RobotsData` instance. If robots.txt is unreachable or
        returns a non-200 status, a permissive instance is returned and a
        warning is logged.
    """
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        response = await client.get(robots_url, timeout=_FETCH_TIMEOUT, follow_redirects=True)
    except httpx.RequestError as exc:
        logger.warning(
            "robots_txt_fetch_failed",
            extra={"robots_url": robots_url, "error": str(exc)},
        )
        return RobotsData(parser=None, crawl_delay=None, sitemap_urls=[], raw_text=None)

    if response.status_code != 200:
        logger.warning(
            "robots_txt_not_found",
            extra={"robots_url": robots_url, "status_code": response.status_code},
        )
        return RobotsData(parser=None, crawl_delay=None, sitemap_urls=[], raw_text=None)

    raw_text = response.text
    parser, crawl_delay, sitemap_urls = _parse_robots(robots_url, raw_text)

    logger.info(
        "robots_txt_fetched",
        extra={
            "robots_url": robots_url,
            "sitemap_count": len(sitemap_urls),
            "crawl_delay": crawl_delay,
        },
    )

    return RobotsData(
        parser=parser,
        crawl_delay=crawl_delay,
        sitemap_urls=sitemap_urls,
        raw_text=raw_text,
    )


def _parse_robots(
    robots_url: str, text: str
) -> tuple[RobotFileParser, float | None, list[str]]:
    """Parse *text* as robots.txt content.

    Returns ``(parser, crawl_delay, sitemap_urls)``.
    """
    parser = RobotFileParser(robots_url)
    parser.parse(text.splitlines())

    crawl_delay: float | None = None
    sitemap_urls: list[str] = []

    # RobotFileParser doesn't expose Crawl-delay or Sitemap: directives
    # through its public API, so we parse those manually.
    current_agents: list[str] = []
    in_relevant_section = False

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            current_agents = []
            in_relevant_section = False
            continue

        if ":" not in stripped:
            continue

        field, _, value = stripped.partition(":")
        field = field.strip().lower()
        value = value.strip()

        if field == "user-agent":
            agent = value.lower()
            current_agents.append(agent)
            in_relevant_section = agent in (CRAWLER_AGENT.lower(), "*")
        elif field == "sitemap":
            if value:
                # Resolve relative sitemap URLs against the robots.txt URL
                sitemap_urls.append(urljoin(robots_url, value))
        elif field == "crawl-delay" and in_relevant_section:
            try:
                delay = float(value)
                # Use the most specific agent's value (NonprofitCrawler > *)
                if crawl_delay is None or CRAWLER_AGENT.lower() in current_agents:
                    crawl_delay = delay
            except ValueError:
                pass

    return parser, crawl_delay, sitemap_urls
