# Spec: Non-production link check for TalkingToad

## Goal
Add a crawl check that flags links (and referenced resources) pointing at
**non-production destinations**: staging/dev/test sites, hosting-provider staging
domains, bare or reserved IP addresses, and off-domain hosts not on an allow-list.
For each flagged link, derive the intended production URL and report whether that
target actually resolves.

## Why this matters (don't skip — it shapes the design)
Staging/test links leak into production constantly: a page built on a staging copy
keeps absolute links to the staging host. Those links get crawled and indexed
(duplicate content, and sometimes the staging site outranks the live one), expose
unfinished content, and break for real users. Bare/reserved-IP links are simply
broken. This is a standard technical-SEO / GEO audit item the crawler should catch
on every run.

Real case this is modeled on (use it as the reference test): the site
`livingsystems.ca` had three podcast pages linking to
`https://staging2.daveg24.sg-host.com/...` (a SiteGround staging site), and its
homepage had a link to `http://0.0.58.241/` (a reserved IP). A blind
"swap the domain" fix would have corrected some links and 404'd others — which is
exactly why this check also verifies whether the production target resolves.

## Step 0 — read the codebase first
Before writing code, read TalkingToad's crawler and issue-reporting code. Match its
existing patterns: how it stores crawled pages/links, the shape of the findings it
already emits, its config format, its HTTP client (reuse it, with timeout/retry),
and its test conventions. Integrate this check into the existing crawl and report
pipeline — do not build a second crawler.

## Functional spec

### 1. What to scan
For every crawled page, extract every URL reference and resolve it to an absolute
URL against the page's own URL:
- Links: `<a href>`.
- Resources: `<img src>` + `srcset`, `<script src>`, `<link href>` (stylesheets,
  canonical, hreflang, preload), `<iframe src>`, `<source>`, `<video/audio src>`,
  `<form action>`.
- Meta URLs: `rel=canonical`, `rel=alternate hreflang`, `og:url`, `og:image`.
Skip non-HTTP schemes (`mailto:`, `tel:`, `javascript:`, `data:`, `#fragment`).
Report `<a>` leaks as the primary finding; resource/meta leaks under the same issue
type with an element label. (A leaked `canonical`/`og:url` is arguably worse — it
tells search engines the staging URL is the canonical one.)

### 2. Classify each URL's HOST (the core rule)
Parse the URL, take the **hostname**, and classify by matching on hostname LABELS
(split on `.`), never on the raw full-URL string. Flag if any rule hits:

- **reserved_or_private_ip** — IP in a non-routable range: `0.0.0.0/8`, `10/8`,
  `127/8`, `169.254/16`, `172.16/12`, `192.168/16`, `100.64/10`, `::1`, `fc00::/7`,
  `fe80::/10`.  → severity **high**
- **bare_ip** — any other IP literal as the host (a public IP as a link target is
  almost always non-canonical or broken).  → **high**
- **localhost** — host is `localhost` or ends `.localhost`.  → **high**
- **provider_staging_domain** — host ends in a known hosting staging/temp domain.
  Default list (config): `sg-host.com`, `wpengine.com`, `wpenginepowered.com`,
  `wpcomstaging.com`, `pantheonsite.io`, `kinsta.cloud`, `kinsta.dev`,
  `cloudwaysapps.com`, `flywheelsites.com`, `flywheelstaging.com`, `myftpupload.com`,
  `temporary.link`, `dream.press`, `azurewebsites.net`, `run.app`, `netlify.app`,
  `vercel.app`, `pages.dev`, `ondigitalocean.app`, `herokuapp.com`.  → **high**
- **staging_label** — any hostname label matches a staging token. Default tokens
  (config): `staging`, `stage`, `stg`, `dev`, `develop`, `development`, `test`,
  `tst`, `uat`, `qa`, `preview`, `demo`, `sandbox`, `beta`, `wip`. Match a label
  that EQUALS a token or is `token` + digits (`staging2`, `dev3`) — so
  `developer.mozilla.org` (label `developer`) is NOT flagged by `dev`.
  → **high** for staging/stg/uat/preview/dev/test; **medium** for beta/demo.
- **off_domain_not_allowlisted** — host is not one of the site's `canonical_domains`
  and not on `allowlist_hosts`.  → **low / "review"**, and OFF by default
  (`flag_off_domain: false`) — normal sites have many legitimate external links; make
  it opt-in for a strict outbound audit.

Never flag the site's own `canonical_domains`. Resolve protocol-relative (`//host/…`)
and relative URLs against the page URL before classifying.

### 3. Companion check — does the production target resolve?
For each finding classified as an intended-internal leak (staging/provider/localhost/
IP — not `off_domain`), derive the production URL by replacing the host with the
site's primary canonical domain and keeping the path/query. HTTP-check it
(config `check_live_target`, default on):
- HEAD, fall back to GET; follow redirects (cap the chain); timeout + one retry;
  reuse TalkingToad's hardened HTTP client; cache by URL; rate-limit.
- Report `live_target_status`: `ok` (2xx), `redirect:<final_url>` (3xx, record final
  status too), or `broken:<code>` (4xx/5xx/timeout).
This is what distinguishes "safe to swap the domain" from "needs a different target."

### 4. Finding contract
One finding per (source_page, link_url), in TalkingToad's existing finding shape,
with these fields:
```
issue_type:  "non_production_link"
severity:    high | medium | low
source_page: <URL the link is on>
element:     "a" | "img" | "script" | "iframe" | "link[canonical]" | ...
anchor_text: <trimmed text, for <a>>
link_url:    <absolute resolved URL>
host:        <hostname>
reason:      reserved_or_private_ip | bare_ip | localhost |
             provider_staging_domain | staging_label | off_domain
suggested_production_url: <host swapped to canonical domain> | null
live_target_status:       ok | redirect:<final_url> | broken:<code> | not_checked
```
Group findings by source_page in the report; add a summary of counts by reason and
by severity. Report zero-per-rule explicitly so "0 found" is a stated result, not a
silent gap. Also emit a deduped "unique leaked URLs" list (the same leak often
repeats site-wide in a menu/footer).

### 5. Config (editorial lists live in config, not code)
```yaml
non_production_link_check:
  canonical_domains: ["example.com", "www.example.com"]
  staging_labels:    [staging, stg, dev, uat, preview, test, sandbox, qa, wip]
  provider_staging_domains: [sg-host.com, wpengine.com, wpcomstaging.com, pantheonsite.io, ...]
  allowlist_hosts:   [forms.gle, eventbrite.com, youtube.com, docs.google.com]
  check_live_target: true
  flag_off_domain:   false
  severity_overrides: { beta: medium, demo: medium }
```
Ship sensible defaults; the user edits the lists.

## Correctness requirements / edge cases
- Parse the host properly: ports, IPv6 in brackets, userinfo, uppercase, trailing
  dot. Classify on the host, never on the full-URL string.
- Label matching must not false-positive on legitimate hosts (`developer.*`,
  `devon.*`): require exact label or `token`+digits; the allowlist is the escape
  hatch.
- Resolve protocol-relative and relative URLs before classifying.
- The live-target check must be hardened: timeout, one retry, redirect cap, and it
  must never crash or hang the crawl — a failed check = `live_target_status:
  broken:timeout`, surfaced, not swallowed.
- Reuse the crawler's existing size/count limits; if anything is capped, log what
  was dropped (no silent truncation).

## Tests (write these first)
Unit — the host classifier (pure, no network), adversarial:
- `staging2.daveg24.sg-host.com` → provider_staging_domain (+ staging_label).
- `http://0.0.58.241/` → reserved_or_private_ip; `http://192.168.1.10/` → reserved;
  `http://34.120.0.1/` → bare_ip.
- `https://developer.mozilla.org/` → NOT flagged (label `developer` ≠ `dev`).
- `https://forms.gle/x` with allowlist → NOT flagged.
- `https://staging.example.com` → staging_label; `https://example.com` (canonical)
  → NOT flagged.
- protocol-relative `//staging.example.com/x` and relative `/x` resolve correctly.
Integration:
- Page HTML containing `href="https://staging2.daveg24.sg-host.com/bowen-theory/"`
  yields a finding: reason=provider_staging_domain,
  suggested_production_url=`https://<canonical>/bowen-theory/`, and (mocked HTTP)
  live_target_status reflecting a 301→/about/.
- A leaked `<link rel=canonical href="https://staging…">` → element=link[canonical],
  severity high.
- Live-target check with mocked HTTP for 200/301/404 → ok / redirect / broken.
- A clean page → no findings, and the summary states 0 explicitly.

## Acceptance criteria
- AC1: findings of `issue_type: non_production_link` are emitted into the existing
  report, grouped by page, with the field contract above.
- AC2: the classifier flags staging labels, provider staging domains, bare +
  reserved IPs, and localhost; and does NOT flag canonical domains, allowlisted
  hosts, or lookalike labels (developer/devon). Proven by the adversarial unit tests.
- AC3: for internal-leak findings, `suggested_production_url` is derived and
  `live_target_status` is reported (ok/redirect/broken), gated by config.
- AC4: every list (labels, provider domains, allowlist, canonical domains) comes
  from config, not code.
- AC5: the live-target HTTP check is hardened (timeout/retry/redirect cap) and a
  failure is surfaced, never crashes the crawl.
- AC6: all tests above pass, including the no-false-positive cases and the
  livingsystems worked example.

## Out of scope
- Fixing the links (report only).
- General broken-link (404) auditing of all links — this check only HTTP-tests the
  derived production target of a flagged leak; a full broken-link crawl is a
  separate feature.
