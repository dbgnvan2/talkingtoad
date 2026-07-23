# Golden Fixture Site

A controlled local website of deliberately-broken pages with **known ground
truth**, used to verify the crawler end-to-end. Driven by
[`tests/test_golden_site.py`](../test_golden_site.py); design rationale in
[`docs/golden-fixture-plan.md`](../../docs/golden-fixture-plan.md).

**What it proves:** running the *real* crawl engine against it surfaces the issue
codes each page was built to demonstrate (false negatives / regressions fail the
test), and targeted false-positive guards hold. It exercises the whole pipeline —
fetch → parse → check → cross-page → score → aggregate — which per-checker unit
tests can't. Current run: **~58 distinct issue codes** across 45 crawled pages.

## Files

| File | Purpose |
|---|---|
| `build_pages.py` | Generates the `.html` fixtures into `pages/`. Source-of-truth for what each page intends to trigger. |
| `pages/` | The served HTML (committed; regenerate with `build_pages.py`). |
| `server.py` | Stdlib HTTP server: serves `pages/`, plus redirects / status codes / headers / `robots.txt` / `sitemap.xml` / a missing `llms.txt`. |

## Run it

```bash
# regenerate the pages (optional — they're committed)
python tests/golden_site/build_pages.py

# the end-to-end detection test
pytest tests/test_golden_site.py -q

# serve it to browse by hand (prints the localhost URL)
python tests/golden_site/server.py
```

## Hosting / SSRF note

The app's SSRF guard **blocks `localhost`/`127.0.0.1`**, so:

- **In the test**, the harness monkeypatches `is_ssrf_safe` to allow the loopback
  fixture host. That's the supported path.
- **To crawl it through the real app UI**, localhost won't pass the guard — expose
  it publicly first (`ngrok http <port>` / `cloudflared`, or deploy the static
  `pages/` folder to Netlify/GitHub Pages).

Two codes fire as **environment artifacts of local http hosting** (not bugs, not
asserted): `HTTP_PAGE` (served over http) and `WRONG_PLACEHOLDER_LINK` (internal
links resolve to `127.0.0.1`, which the app correctly treats as a
localhost/wrong-domain placeholder on a real site).

## Not covered here (need other harnesses)

Broken **external** links (need an external host), TLS-only security codes
(`MIXED_CONTENT`, `MISSING_HSTS`, `HTTPS_REDIRECT_MISSING`, `WWW_CANONICALIZATION`),
image-byte codes (need real image assets), JS-render-diff codes (need the headless
renderer), PDF codes, and WP-fix / AI-LLM / GSC codes (need those integrations).
See the coverage table in `docs/golden-fixture-plan.md`.
