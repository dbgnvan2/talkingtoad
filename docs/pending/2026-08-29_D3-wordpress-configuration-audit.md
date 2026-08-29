# Micro-spec D3: WordPress configuration audit — opt-in, read-only, never in the crawl

Date: 2026-08-29
Status: **proposal — awaiting approval. Needs an architecture decision before implementation.**
Area: new `api/services/wp_audit.py`, new `api/routers/wp_audit.py`,
new `api/config/wp_plugin_advice.json`, report §7.8
Origin: D3 in the E-series umbrella plan.

## What this is worth

The external audit's most operationally useful page had nothing to do with
crawling. It was this:

> 22 plugins, 19 active · five updates pending including a Yoast Premium version
> mismatch · **Duplicator Pro active but no backups have ever been created, no
> schedules enabled and no recovery point exists** · Security Optimizer installed
> but inactive · Smush and Speed Optimizer both doing image compression · Site
> Health recommends removing inactive plugins and enabling a persistent object cache

"You have a backup plugin that has never taken a backup" is a finding a nonprofit
can act on today, and no amount of crawling will ever produce it.

## The architecture decision this needs first

`api/crawler/engine.py` carries an explicit, test-enforced constraint:

> *"The SCAN process must ONLY use data from HTML parsing and HTTP HEAD requests.
> The SCAN must NEVER call WordPress API"* — enforced by
> `tests/test_architecture_constraints.py`

That constraint is correct and D3 does not touch it. The proposal is a **separate,
user-triggered, post-scan step** with its own endpoint — the same shape as the Fix
Manager, which already authenticates to WordPress today.

**What needs your approval is the scope question, not the mechanism:** this makes
TalkingToad partly a WordPress configuration reviewer, not only an SEO crawler. It
only works on WordPress, only with admin credentials, and it is the one item in
the D set that widens what the product *is*. I think it is worth it — it is the
highest-value-per-line item of the four — but it is your call, and it is why this
spec is marked as needing a decision rather than just approval.

## D3.1 — Read-only, and structurally so

- Every call goes through the existing `WPClient` (`api/services/wp_client.py`),
  which already authenticates and is already used by the fix routers.
- **`GET` only.** A guard test asserts `api/services/wp_audit.py` contains no
  `post(`, `patch(`, `delete(` or `put(` call — the audit must be incapable of
  changing anything, not merely intended not to.
- Domain-validated via the existing `_validate_wp_domain_for_job(store, job_id)`,
  per the WordPress-safety constraint in `CLAUDE.md`.
- Credentials come from the existing `wp-credentials.json` path. No new secret.

Endpoints read (all authenticated, admin-capability gated by WordPress itself):

| Endpoint | Gives |
|---|---|
| `GET /wp/v2/plugins` | name, version, status, `update` availability |
| `GET /wp/v2/themes` | active/inactive themes |
| `GET /wp/v2/users/me?context=edit` | capability probe — verify access before anything else |
| `GET /wp-site-health/v1/tests/…` | core's own recommendations (object cache, opcode cache, inactive plugins) |

The capability probe runs **first**. If the credentials lack plugin-read
capability, the audit returns a clear "insufficient permissions" state rather than
a partial result — a half-audit presented as a whole one is the P2 shape.

## D3.2 — Findings, and the line between knowable and not

Two tiers, and the spec is explicit about which is which because that line is
where this feature could start inventing things.

**Tier 1 — derivable from the plugin/theme/site-health payload alone.** Safe,
deterministic, no per-plugin knowledge:

- Inactive plugins and themes still installed
- Pending updates, with the version delta
- A premium/free version mismatch of the same plugin family
- Site Health's own recommendations, passed through verbatim and attributed to
  WordPress rather than to TalkingToad
- **Overlapping responsibility** — two active plugins claiming the same job
  (image compression, lazy-loading, caching, SEO, sitemaps, schema, redirects).
  The overlap map is pure editorial content and lives in
  `api/config/wp_plugin_advice.json` (rule 9), keyed by plugin slug.

**Tier 2 — needs per-plugin internals, and is NOT in this spec.** "Duplicator is
active but has never taken a backup" requires reading Duplicator's own tables or
settings. There is no generic REST surface for it, and writing a bespoke probe per
plugin is an open-ended commitment. This spec deliberately stops at Tier 1 and
says so in the output: the report states what it checked and that plugin-internal
state (backup history, security-plugin configuration, cache warmth) was **not**
inspected. Declaring the boundary is the difference between a useful finding and
an implied guarantee.

## D3.3 — Output

- `POST /api/wp-audit/{job_id}` returns a structured report; persisted on the job
  so a re-export does not re-authenticate.
- Report §7.8 **WordPress Configuration** — rendered only when the audit was run,
  omitted and named in Caveats otherwise (E7.4). The Caveats "CMS and plugin
  configuration not checked" line becomes conditional on whether it ran.
- Results GUI: a panel beside the existing WP fix tools.
- **No new issue codes.** These are configuration observations, not crawl findings;
  putting them in `_CATALOGUE` would let them enter the health score, which would
  be wrong — a site's plugin hygiene is not a property of its pages.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| D3.1a | **The audit module cannot write.** No POST/PATCH/PUT/DELETE anywhere in it | `tests/test_architecture_constraints.py::test_d3_1a_wp_audit_is_read_only` |
| D3.1b | The crawl engine still never calls the WP API — existing guard unchanged | `tests/test_architecture_constraints.py` (existing, must stay green) |
| D3.1c | A domain mismatch returns 403 `DOMAIN_MISMATCH` before any WP call | `tests/test_wp_audit.py::test_d3_1c_domain_validated_first` |
| D3.1d | Insufficient capability → a clear error state, never a partial audit | `…::test_d3_1d_partial_access_is_not_a_partial_report` |
| D3.1e | No credentials file → 400 with a named code, no traceback to the client | `…::test_d3_1e_missing_credentials` |
| D3.2a | Inactive plugins and pending updates are reported with versions | `…::test_d3_2a_inactive_and_pending` |
| D3.2b | Two active image-compression plugins are reported as an overlap | `…::test_d3_2b_overlap_detected` |
| D3.2c | **Adversarial (P7):** two plugins in the same *category* that do not actually overlap (an SEO plugin and its own premium add-on) must NOT be flagged | `…::test_d3_2c_addon_of_the_same_family_is_not_an_overlap` |
| D3.2d | Every slug in the advice config exists as a real plugin slug format; the config fails loudly if malformed | `…::test_d3_2d_advice_config_valid` |
| D3.2e | Site Health recommendations are attributed to WordPress, not presented as TalkingToad findings | `…::test_d3_2e_site_health_attributed` |
| D3.2f | The report states that plugin-internal state was not inspected | `…::test_d3_2f_tier2_boundary_declared` |
| D3.3a | Audit not run → §7.8 omitted **and** named in Caveats | `tests/test_report_roadmap.py::test_d3_3a_wp_audit_omission_disclosed` |
| D3.3b | Audit run → the Caveats "CMS and plugin configuration" line reflects that | `…::test_d3_3b_caveats_tracks_whether_wp_audit_ran` |
| D3.3c | **Dirty-state (P8):** a re-export uses the stored result, no re-authentication | `tests/test_wp_audit.py::test_d3_3c_reexport_uses_stored_result` |
| D3.3d | No finding enters `_CATALOGUE` or affects any health score | `tests/test_scoring_paths_unified.py::test_d3_3d_wp_audit_does_not_touch_scoring` |

Fix→test map (P10): **D3.1a first.** This feature holds admin credentials to the
client's live site. "It is read-only" has to be a property the tests enforce, not
an intention the author had.

## Fixtures

Recorded real `/wp/v2/plugins` and Site Health responses from the staging site,
credentials scrubbed, checked in. Synthetic plugin payloads would not exercise the
version-string and update-object shapes WordPress actually emits (P19).

## Adjacent issues found, not fixed (rule 10)

- `wp_client.py` has no rate limiting. The audit is a handful of calls so it does
  not matter here, but the fix routers can issue many and share the client.
- `wp-credentials.json` is a single global credential set. A second client site
  would need the parked multi-tenant work — worth stating before this feature
  creates an expectation it can serve several sites.

## Out of scope

Changing anything in WordPress. Reading plugin-internal state (Tier 2 above).
Recommending specific plugin purchases.
