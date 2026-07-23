"""Local golden-fixture web server.

Serves a controlled site of deliberately-broken pages so the crawler can be run
end-to-end against known ground truth (see tests/test_golden_site.py and
docs/golden-fixture-plan.md). Stdlib only — no extra dependencies.

Handles the conditions a plain static server can't:
  * 301/302/redirect-chain/redirect-loop, 404/410/503/500 status routes
  * per-page response headers (X-Robots-Tag: noindex)
  * robots.txt (with AI-bot directives + a Disallow), sitemap.xml, missing llms.txt

The site is served over HTTP (so HTTP_PAGE is expected site-wide) on 127.0.0.1,
so the crawl harness must allow the loopback host past the SSRF guard.
"""

from __future__ import annotations

import http.server
import threading
from pathlib import Path

PAGES_DIR = Path(__file__).parent / "pages"

# path -> (status, extra_headers, location). Location set => redirect.
_ROUTES: dict[str, tuple[int, dict, str | None]] = {
    "/redirect-301": (301, {}, "/target.html"),
    "/redirect-302": (302, {}, "/target.html"),
    "/chain-a": (301, {}, "/chain-b"),
    "/chain-b": (301, {}, "/chain-c"),
    "/chain-c": (301, {}, "/target.html"),
    "/loop-a": (301, {}, "/loop-b"),
    "/loop-b": (301, {}, "/loop-a"),
    "/gone": (410, {}, None),
    "/unavailable": (503, {}, None),
    "/server-error": (500, {}, None),
    "/login": (200, {}, None),  # a page a login-redirect points at
    "/secret-area": (302, {}, "/login"),  # LOGIN_REDIRECT
}

# Pages served with extra response headers (path -> headers).
_HEADER_PAGES: dict[str, dict] = {
    "/noindex-header.html": {"X-Robots-Tag": "noindex"},
}

_ROBOTS_TXT = """User-agent: *
Disallow: /blocked/
Sitemap: http://{host}/sitemap.xml

User-agent: GPTBot
Disallow: /

User-agent: Google-Extended
Disallow: /
"""


def _sitemap_xml(host: str, paths: list[str]) -> str:
    urls = "".join(f"<url><loc>http://{host}{p}</loc></url>" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'


# Pages listed in the sitemap. Deliberately omits /orphan.html (→ NOT_IN_SITEMAP
# is avoided for listed pages; orphan is reachable via sitemap so it's crawled).
_SITEMAP_PATHS = ["/", "/orphan.html"]


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def _host(self) -> str:
        return self.headers.get("Host", f"127.0.0.1:{self.server.server_port}")

    def do_HEAD(self):
        self._respond(head_only=True)

    def do_GET(self):
        self._respond(head_only=False)

    def _respond(self, head_only: bool):
        path = self.path.split("?")[0].split("#")[0]

        # Special status/redirect routes
        if path in _ROUTES:
            status, headers, location = _ROUTES[path]
            self.send_response(status)
            if location:
                self.send_header("Location", location)
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            return

        if path == "/robots.txt":
            body = _ROBOTS_TXT.format(host=self._host()).encode()
            return self._send(200, body, "text/plain", head_only)

        if path == "/sitemap.xml":
            body = _sitemap_xml(self._host(), _SITEMAP_PATHS).encode()
            return self._send(200, body, "application/xml", head_only)

        if path == "/llms.txt":
            return self._send(404, b"not found", "text/plain", head_only)  # LLMS_TXT_MISSING

        # Static HTML from pages/
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        file = (PAGES_DIR / rel).resolve()
        try:
            file.relative_to(PAGES_DIR.resolve())
        except ValueError:
            return self._send(404, b"forbidden", "text/plain", head_only)
        if file.is_file():
            body = file.read_bytes()
            extra = _HEADER_PAGES.get(path, {})
            return self._send(200, body, "text/html; charset=utf-8", head_only, extra)
        return self._send(404, b"not found", "text/plain", head_only)

    def _send(self, status, body, ctype, head_only, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not head_only:
            self.wfile.write(body)


class GoldenSiteServer:
    """Context manager: starts the site on a free localhost port."""

    def __init__(self):
        self._httpd = None
        self._thread = None
        self.port = None

    def __enter__(self):
        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def __exit__(self, *exc):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()


if __name__ == "__main__":  # manual: python tests/golden_site/server.py
    with GoldenSiteServer() as s:
        print(f"Golden site at {s.base_url} (Ctrl-C to stop)")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
