#!/usr/bin/env bash
# talkingtoad.sh — TalkingToad dev runner
# Usage: ./talkingtoad.sh <command> [options]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/venv"
PYTHON="$VENV/bin/python3"

# ── Colours ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}${BOLD}▶ $*${RESET}"; }
success() { echo -e "${GREEN}✔ $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠ $*${RESET}"; }
error()   { echo -e "${RED}✖ $*${RESET}" >&2; exit 1; }

# ── Helpers ────────────────────────────────────────────────────────────────

require_venv() {
  if [[ ! -x "$PYTHON" ]]; then
    warn "Virtual environment not found. Run:  ./talkingtoad.sh setup"
    exit 1
  fi
}

# ── Commands ───────────────────────────────────────────────────────────────

cmd_help() {
  echo -e "${BOLD}TalkingToad — Nonprofit SEO Crawler${RESET}"
  echo ""
  echo -e "${BOLD}Usage:${RESET}  ./talkingtoad.sh <command> [options]"
  echo ""
  echo -e "${BOLD}Commands:${RESET}"
  echo "  setup                  Create virtualenv and install dependencies"
  echo "  test [pytest-args]     Run the test suite"
  echo "  server                 Start the API backend (port 8000)"
  echo "  frontend               Start the React frontend dev server (port 5173)"
  echo "  crawl <url>            Crawl a website and print issues (CLI, no server needed)"
  echo "    --max-pages N          Stop after N pages  (default: 20)"
  echo "    --delay-ms N           Crawl delay in ms   (default: 500)"
  echo "  robots <url>           Fetch and show robots.txt for a domain"
  echo "  sitemap <url>          Discover and show sitemap URLs for a domain"
  echo "  normalise <url>        Show the normalised form of a URL"
  echo ""
  echo -e "${BOLD}Examples:${RESET}"
  echo "  ./talkingtoad.sh setup"
  echo "  ./talkingtoad.sh test"
  echo "  ./talkingtoad.sh server             # terminal 1"
  echo "  ./talkingtoad.sh frontend           # terminal 2, then open http://localhost:5173"
  echo "  ./talkingtoad.sh crawl https://livingsystems.ca"
  echo "  ./talkingtoad.sh crawl https://livingsystems.ca --max-pages 50"
  echo "  ./talkingtoad.sh robots https://livingsystems.ca"
  echo "  ./talkingtoad.sh sitemap https://livingsystems.ca"
  echo "  ./talkingtoad.sh normalise 'https://Example.COM/about/?utm_source=google#section'"
}

cmd_setup() {
  info "Setting up TalkingToad..."

  if [[ ! -x "$VENV/bin/python3" ]]; then
    python3 -m venv "$VENV"
    success "Virtualenv created"
  else
    success "Virtualenv already exists"
  fi

  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r requirements.txt respx
  success "Dependencies installed"
  echo ""
  echo -e "Run your first crawl:  ${BOLD}./talkingtoad.sh crawl https://livingsystems.ca${RESET}"
}

cmd_test() {
  require_venv
  info "Running test suite..."
  "$VENV/bin/pytest" tests/ "$@"
}

cmd_crawl() {
  require_venv
  local url=""
  local max_pages=20
  local delay_ms=500

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max-pages) max_pages="$2"; shift 2 ;;
      --delay-ms)  delay_ms="$2";  shift 2 ;;
      http*) url="$1"; shift ;;
      *) error "Unknown option: $1" ;;
    esac
  done

  [[ -z "$url" ]] && error "Usage: ./talkingtoad.sh crawl <url> [--max-pages N] [--delay-ms N]"

  info "Crawling: $url  (max $max_pages pages, ${delay_ms}ms delay)"
  echo ""

  "$PYTHON" - "$url" "$max_pages" "$delay_ms" <<'PYEOF'
import asyncio, sys
from api.crawler.engine import run_crawl, CrawlSettings

url, max_pages, delay_ms = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])

SEVERITY_COLOUR = {"critical": "\033[0;31m", "warning": "\033[1;33m", "info": "\033[0;36m"}
RESET = "\033[0m"
BOLD  = "\033[1m"

async def main():
    settings = CrawlSettings(max_pages=max_pages, crawl_delay_ms=delay_ms)

    def on_progress(p):
        total = p["pages_total"]
        bar   = f"{p['pages_crawled']}/{total}" if total else str(p["pages_crawled"])
        print(f"  [{bar}] {p['current_url']}", flush=True)

    result = await run_crawl("cli-crawl", url, settings, on_progress=on_progress)

    print()
    print(f"{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}Pages crawled:{RESET}  {result.pages_crawled}")
    print(f"{BOLD}Issues found: {RESET}  {len(result.issues)}")

    if not result.issues:
        print("\n\033[0;32m✔ No issues found!\033[0m")
        return

    # Group by severity for summary
    by_sev = {"critical": [], "warning": [], "info": []}
    for i in result.issues:
        by_sev.get(i.severity, by_sev["info"]).append(i)

    print()
    for sev in ("critical", "warning", "info"):
        issues = by_sev[sev]
        if not issues:
            continue
        col = SEVERITY_COLOUR[sev]
        print(f"{col}{BOLD}{sev.upper()} ({len(issues)}){RESET}")
        for i in issues:
            page = i.page_url or "(job-level)"
            print(f"  {col}●{RESET} {i.code:30}  {page}")
        print()

asyncio.run(main())
PYEOF
}

cmd_robots() {
  require_venv
  local url="${1:-}"
  [[ -z "$url" ]] && error "Usage: ./talkingtoad.sh robots <url>"

  info "Fetching robots.txt for: $url"
  echo ""

  "$PYTHON" - "$url" <<'PYEOF'
import asyncio, sys
import httpx
from api.crawler.robots import fetch_robots

async def main():
    url = sys.argv[1]
    async with httpx.AsyncClient() as client:
        data = await fetch_robots(url, client)

    print(f"Crawl delay:  {data.crawl_delay if data.crawl_delay is not None else 'not specified'}")
    print(f"Sitemap URLs: {len(data.sitemap_urls)}")
    for s in data.sitemap_urls:
        print(f"  {s}")

    test_paths = ["/", "/about", "/wp-admin/", "/wp-login.php", "/login"]
    from urllib.parse import urlparse
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    print("\nAccess check:")
    for path in test_paths:
        allowed = data.is_allowed(base + path)
        status = "\033[0;32m✔ allowed\033[0m" if allowed else "\033[0;31m✖ blocked\033[0m"
        print(f"  {base + path:50}  {status}")

asyncio.run(main())
PYEOF
}

cmd_sitemap() {
  require_venv
  local url="${1:-}"
  [[ -z "$url" ]] && error "Usage: ./talkingtoad.sh sitemap <url>"

  info "Discovering sitemap for: $url"
  echo ""

  "$PYTHON" - "$url" <<'PYEOF'
import asyncio, sys
import httpx
from api.crawler.sitemap import fetch_sitemap_recursive

async def main():
    url = sys.argv[1]
    async with httpx.AsyncClient() as client:
        result = await fetch_sitemap_recursive(url, client)

    if not result.found:
        print("\033[1;33m⚠ No sitemap found\033[0m")
        return

    print(f"Source:  {result.source_url}")
    print(f"URLs:    {len(result.urls)}")
    print()
    for u in result.urls[:30]:
        print(f"  {u}")
    if len(result.urls) > 30:
        print(f"  ... and {len(result.urls) - 30} more")

asyncio.run(main())
PYEOF
}

cmd_server() {
  require_venv
  local log_level="info"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --debug|--log) log_level="debug"; shift ;;
      *) error "Unknown option: $1" ;;
    esac
  done

  info "Starting API server on http://localhost:8000"
  info "API docs at http://localhost:8000/docs"
  info "Log level: $log_level"
  info "Auth: ${AUTH_TOKEN:+enabled (AUTH_TOKEN is set)}${AUTH_TOKEN:-disabled (no AUTH_TOKEN — open access)}"
  echo ""
  RATE_LIMIT_ENABLED="false" \
    "$VENV/bin/uvicorn" api.main:app --reload --port 8000 --log-level "$log_level"
}

cmd_frontend() {
  local frontend_dir="$SCRIPT_DIR/frontend"
  if [[ ! -d "$frontend_dir/node_modules" ]]; then
    info "Installing frontend dependencies..."
    (cd "$frontend_dir" && npm install)
  fi
  info "Starting frontend dev server on http://localhost:5173"
  echo ""
  (cd "$frontend_dir" && npm run dev)
}

cmd_normalise() {
  require_venv
  local url="${1:-}"
  [[ -z "$url" ]] && error "Usage: ./talkingtoad.sh normalise <url>"

  "$PYTHON" - "$url" <<'PYEOF'
import sys
from api.crawler.normaliser import normalise_url, is_same_domain, is_admin_path

url = sys.argv[1]
try:
    norm = normalise_url(url)
    print(f"Normalised:   {norm}")
    print(f"Admin path:   {is_admin_path(url)}")
except ValueError as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}

# ── Dispatch ───────────────────────────────────────────────────────────────

COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
  setup)     cmd_setup "$@" ;;
  test)      cmd_test "$@" ;;
  server)    cmd_server "$@" ;;
  frontend)  cmd_frontend "$@" ;;
  crawl)     cmd_crawl "$@" ;;
  robots)    cmd_robots "$@" ;;
  sitemap)   cmd_sitemap "$@" ;;
  normalise|normalize) cmd_normalise "$@" ;;
  help|--help|-h) cmd_help ;;
  *) error "Unknown command: $COMMAND  (run ./talkingtoad.sh help)" ;;
esac
