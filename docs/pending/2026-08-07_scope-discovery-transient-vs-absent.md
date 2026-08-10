---
feature: Distinguish transient/unreachable from definitive absence in content-type scope discovery
status: pending
date: 2026-08-07
author: Claude Code (for Dave)
supersedes: none
touches:
  - api/crawler/content_discovery.py
  - api/crawler/sitemap.py
  - api/routers/crawl.py   # doc-only (payload shape)
  - frontend/src/pages/Home.jsx
  - frontend/src/api.js     # doc-only (comment)
tests:
  - tests/test_content_discovery.py
  - tests/test_discover_scope_integration.py
  - frontend/src/pages/__tests__/Home.scope.test.jsx
patterns: [P1, P2, P6]
---

# Micro-spec — Scope discovery must not report a transient probe failure as a definitive "no WordPress REST API"

## SD1 — Problem (bug)

`discover_scope()` in [`api/crawler/content_discovery.py`](../../api/crawler/content_discovery.py)
collapses a **transient probe failure** (network error, timeout, 5xx after
retries) into the same outcome as a **genuine absence** of the WordPress REST
API / typed sitemap. This is failure-patterns **P1** (transient recorded as a
permanent negative) and **P2** (silent drop with no signal a retry would help).

Concrete chain:

1. `_get_json` (≈L76–107) retries transient errors then returns `None`. Its own
   docstring warns: *"None therefore means 'no usable JSON after retries' — the
   caller must not assume it means 'the collection ended'"*.
2. `_probe_wp_rest` (≈L128–134) collapses that `None` into `return False` — a
   network blip is now indistinguishable from a 404 on `/wp-json/`.
3. The Tier-3 exit (≈L320–331) emits: *"This site doesn't expose a WordPress
   REST API or a typed sitemap, so content-type scoping isn't available — a
   full-site crawl will run."* — the **same message** whether the site genuinely
   lacks REST or the probe just couldn't reach it.

**Observed live:** a network issue made a known WordPress site (livingsystems.ca)
show the definitive "no REST API" message, silently stripping the content-type
scoping option with no signal that a retry would fix it.

The **sitemap tier** has the identical conflation: `_fetch_and_resolve` (≈L276–288)
returns `None` on both `httpx.RequestError` (transient) and a non-200 (definitive),
so `SitemapResult.found=False` cannot tell "site reachable, no typed sitemap" from
"couldn't reach the site".

## SD2 — Desired behaviour

Distinguish two failure modes and surface them differently:

- **Transient / unreachable (retryable):** the probe could not reach the site
  (network error, timeout, or 5xx after retries). We do **not** know whether REST
  or a typed sitemap exists. Emit a distinct, retryable result. The user sees a
  message like *"Couldn't reach the site to check for content-type scoping. This
  is usually temporary — try again."* with a **Try again** affordance.
- **Definitive absence:** the site **was reached** (HTTP responses received) and
  genuinely exposes neither a usable WordPress REST API nor a typed sitemap. Keep
  the current message unchanged.

### SD2.1 — Reachability classification (low level)

Introduce a three-way outcome for a probe fetch, replacing the boolean the probe
currently derives from `_get_json`:

| Outcome | Meaning | Trigger |
|---|---|---|
| `ok` | got parsed JSON | HTTP 200 + valid JSON body |
| `absent` | reached, but no usable JSON | reachable HTTP response that is non-200 (e.g. 404/401/403) **or** 200 with an unparseable/ wrong-shaped body |
| `unreachable` | transient, retryable | `httpx.RequestError` (connect/read/timeout) after retries, **or** 5xx after retries |

Rationale: a 5xx *is* an HTTP response, but per **P1** it is retryable, so it is
grouped with `unreachable`. A 404/403 is a definitive answer from a reachable
server, so it is `absent`.

`_get_json`'s existing `tuple | None` contract is preserved for the pagination /
collection callers (`_rest_types`, `_rest_count`, `_rest_categories`,
`_rest_collection_urls`) — those already handle `None` correctly via the
`X-WP-TotalPages` end-of-data signal and must not change. The new three-way
outcome is used only where reachability must be distinguished (the REST probe,
and the sitemap tier).

### SD2.2 — REST probe

`_probe_wp_rest` returns one of `"rest"` (is a WP REST root), `"absent"`
(reachable, not WP REST), or `"unreachable"` (transient) — not a bare `bool`.
The value of a WP REST root is unchanged (`dict` with `routes`/`namespaces`/`name`).

`resolve_scope_urls` also calls `_probe_wp_rest`; it treats anything other than
`"rest"` as "fall through to sitemap tier" (unchanged behaviour — resolution runs
after the user already chose types from a successful discovery, so its retry story
is out of scope here). Only the boolean check site changes from `if await
_probe_wp_rest(...)` to `if await _probe_wp_rest(...) == "rest"`.

### SD2.3 — Sitemap tier reachability

Add a `reachable: bool` attribute to `SitemapResult` (default `True` for
backward-compatible construction). In `fetch_sitemap_recursive`, `reachable` is
`True` if **any** candidate fetch produced a definitive HTTP answer (a status
`< 500`), and `False` if **every** candidate either raised `httpx.RequestError`
or returned a 5xx. When `found=True`, `reachable` is always `True`.

`fetch_sitemap` (the non-recursive variant) sets the same attribute for
consistency; only the recursive variant is consumed by scope discovery.

### SD2.4 — `discover_scope` decision

After the positive tiers fail to produce types, the definitive-vs-transient
decision is:

```
definitive_none = (rest_outcome == "absent") AND sitemap.reachable
```

- If `definitive_none` → return the existing Tier-3 `"none"` payload unchanged.
- Otherwise (REST was `unreachable`, **or** the sitemap was unreachable) → return
  the new **transient** payload: we could not conclusively rule out scoping, so a
  retry may succeed.

This is deliberately conservative: a transient failure on *either* tier that
prevented a positive result yields a retryable outcome, because a transient REST
failure means REST-absence is unproven, and a transient sitemap failure means
typed-sitemap-absence is unproven.

### SD2.5 — Payload shape (additive, backward compatible)

`discover_scope` payloads gain one additive boolean field: **`retryable`**
(default `False`). The transient case sets:

```json
{
  "is_wordpress": false,
  "discovery_tier": "unreachable",
  "types": [],
  "categories": [],
  "category_scope_supported": false,
  "retryable": true,
  "notes": "Couldn't reach the site to check for content-type scoping. This is usually temporary — try again."
}
```

All existing payloads (`rest`, `sitemap`, `none`) gain `"retryable": false`. No
existing field changes type or meaning. `discovery_tier` gains one new value
`"unreachable"`; existing values are unchanged.

### SD2.6 — Frontend (Home scope flow)

[`frontend/src/pages/Home.jsx`](../../frontend/src/pages/Home.jsx) renders the
`types.length === 0` branch (≈L310) as a dead-end message today. Update it so
that when `scopeData.retryable` (equivalently `discovery_tier === 'unreachable'`)
is true, it renders the notes **plus a "Try again" button** wired to
`runDiscovery` (mirroring the existing `scopeError` branch at ≈L297). The
definitive `"none"` case (retryable false) keeps the current dead-end copy.
Update the `discoverScope` doc comment in `frontend/src/api.js` to list the new
`retryable` field.

## SD3 — Acceptance criteria → tests

Each criterion is verified by a specific automated test.

| ID | Criterion | Test |
|---|---|---|
| SD3.1 | REST probe timeout ⇒ `discover_scope` returns `discovery_tier == "unreachable"`, `retryable == True`, and the retryable notes (NOT the definitive "doesn't expose" copy). Sitemap also unreachable. | `tests/test_content_discovery.py::test_sd3_1_rest_probe_timeout_is_retryable_not_definitive` |
| SD3.2 | Site reachable, `/wp-json/` returns a valid non-WP **200** and the sitemap is reached with no typed index ⇒ `discovery_tier == "none"`, `retryable == False`, definitive notes unchanged. | `tests/test_content_discovery.py::test_sd3_2_reachable_non_wp_200_is_definitive_none` |
| SD3.3 | `/wp-json/` returns **404** (reachable) but the **sitemap fetch times out** ⇒ `discovery_tier == "unreachable"`, `retryable == True` (typed-sitemap absence unproven). | `tests/test_content_discovery.py::test_sd3_3_rest_404_but_sitemap_unreachable_is_retryable` |
| SD3.4 | `_probe_wp_rest` returns `"unreachable"` on `RequestError`/5xx-after-retries, `"absent"` on 404, `"rest"` on a WP REST root. | `tests/test_content_discovery.py::test_sd3_4_probe_wp_rest_three_way_outcome` |
| SD3.5 | `SitemapResult.reachable` is `False` when every candidate raises `RequestError`, `True` when a candidate returns a definitive (non-5xx) HTTP status, and `True` whenever `found`. | `tests/test_content_discovery.py::test_sd3_5_sitemap_reachable_flag` |
| SD3.6 | Existing `rest` / `sitemap` / `none` payloads all include `"retryable": false`; the WP-REST happy path is unaffected (regression guard). | `tests/test_content_discovery.py::test_sd3_6_positive_tiers_carry_retryable_false` |
| SD3.7 | `discover-scope` endpoint returns `retryable` in the JSON body and logs the tier (integration). | `tests/test_discover_scope_integration.py::test_sd3_7_endpoint_returns_retryable_field` |
| SD3.8 | Home renders a **Try again** button (wired to re-discovery) when the payload is `retryable`, and does **not** render it for the definitive `none` payload. | `frontend/src/pages/__tests__/Home.scope.test.jsx` — `sd3.8 retryable discovery shows Try again` and `sd3.8 definitive none shows no retry` |

### Adversarial / dirty-state coverage (explicit, per CLAUDE.md)

- **SD3.1 is the adversarial timeout test** the task requires: it simulates a
  probe timeout and asserts the *retryable* (not the definitive) message — the
  "looks like absence but is actually unreachable" input must not score as
  definitive.
- **SD3.2 is its mirror**: a valid non-WP **200** must yield the *definitive*
  message — proving the classifier isn't simply flipping everything to retryable.
- **SD3.3** guards the sitemap-tier conflation independently of REST.

## SD4 — Out of scope

- `resolve_scope_urls` retry UX (runs post-selection; its truncation notes
  already distinguish partial sets per P9/P1 and are unchanged here).
- Any change to pagination end-of-data detection (`X-WP-TotalPages`) or the
  `_MAX_REST_PAGES` cap.
- Auto-retry loops in the backend beyond the existing `_MAX_RETRIES` backoff; the
  retry is a user-driven affordance, not an automatic re-probe.

## SD5 — Thresholds / config

No new numeric thresholds. Reuses existing `_MAX_RETRIES` / `_RETRY_BACKOFF_S`
(REST) and `_FETCH_TIMEOUT` (sitemap). `docs/thresholds.md` needs no change.
