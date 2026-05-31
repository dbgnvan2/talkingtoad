---
status: pending
proposed: 2026-05-31
author: Architect (GA4 cycle, TalkingToad session)
type: feature
source: PLAN-V3.0-UNIFIED.md Workstream GA → GA4 (Gemini "Authoritative Entity Schema Factory", 3.4)
---

# GA4 — Authoritative Entity Schema Factory

## Goal
Generate a nested, Schema.org-compliant JSON-LD block
(`Organization → Service → FAQPage`) that links the organisation to its
authoritative entity via `sameAs` (a Wikipedia/Wikidata URL) — for the user to
copy/paste. **Generate-and-suggest only. Deterministic — no LLM.**

## Locked decisions (consistent with GA3)
- **Generate-and-suggest only.** No WordPress write, no domain mutation.
- **Deterministic.** Pure construction from `GeoConfig`. No AIRouter, no network.
- **No outbound fetch.** `entity_wikipedia_url` is embedded as a string, never
  fetched → **no SSRF surface**.
- **Auth required** (lives under the `require_auth` `geo.py` router).

## GeoConfig change (verified round-trip)
Add one field to `api/models/geo_config.py`:
```python
entity_wikipedia_url: str = ""   # authoritative-entity URL for sameAs (Wikipedia/Wikidata)
```
- `to_dict()` is `asdict(self)` and `from_dict()` is `cls(**data)` with `""`
  default → the field round-trips automatically; **older stored configs without the
  key still load** (default applies). No migration script needed.
- The **GEO settings save path** (`POST /api/geo/settings` in `api/routers/geo.py`)
  must accept and persist the new field. Confirm the settings handler passes it
  through to `GeoConfig`/`from_dict` (it builds the config from the request body).
- `is_configured()` / `validate()` must **not** start requiring this field — it is
  optional (blank is valid; just omits `sameAs`).

## Signature
```python
# api/services/geo_schema_factory.py  (NEW)
def build_entity_schema(geo_config: GeoConfig) -> dict:
    """Return a nested Organization JSON-LD dict:
        Organization (name, sameAs?) -> hasOfferCatalog -> Service[] (from
        topic_entities, areaServed = primary_location) -> FAQPage (mainEntity).
    Deterministic; no I/O. `sameAs` is included only when
    entity_wikipedia_url is non-blank.
    """
```

### Structure (target shape — exact property nesting at developer's discretion, but these are required)
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "<org_name>",
  "sameAs": ["<entity_wikipedia_url>"],          // OMITTED entirely when blank
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "Services",
    "itemListElement": [
      {"@type": "Service", "name": "<topic_entity>", "areaServed": "<primary_location>"}
    ]
  },
  "subjectOf": { "@type": "FAQPage", "mainEntity": [ /* Question[] */ ] }
}
```
- **Reuse opportunity:** the `FAQPage` portion can call GA3's
  `api.services.geo_faq._build_faq_block(...)` (template questions) so the two GEO
  Authority features share one FAQ builder. Optional but encouraged.

## Files to add / modify
| File | Change |
|---|---|
| `api/models/geo_config.py` | add `entity_wikipedia_url: str = ""` |
| `api/services/geo_schema_factory.py` | **NEW** — `build_entity_schema()` |
| `api/routers/geo.py` | **NEW endpoint** `POST /api/geo/entity-schema` (router already `require_auth`) |
| `api/routers/geo.py` (settings save) | ensure `entity_wikipedia_url` persists on `POST /api/geo/settings` |
| `frontend/src/components/GeoSettings.jsx` *(or GeoSettingsModal.jsx)* | add an `entity_wikipedia_url` input |
| `frontend/src/components/GEOReportPanel.jsx` | **NEW card** "Entity Schema": Generate button + JSON-LD copy box (text, not `dangerouslySetInnerHTML`); loading/error states; V4 explainer |
| `frontend/src/api.js` | client fn for the endpoint |
| `docs/api.md` | document `POST /api/geo/entity-schema` |

## Endpoint contract
`POST /api/geo/entity-schema`  (auth required — geo.py router dependency)

Request: `{ "domain": str }`
Response 200:
```json
{ "jsonld": "<pretty-printed JSON-LD string>",
  "schema": { ...the dict... },
  "valid": true,
  "warnings": ["entity_wikipedia_url not set — sameAs omitted", ...] }
```
Errors: `401` no auth · `422` unknown `domain` or empty `topic_entities` (clear
message) · `422` malformed body.

## Test plan (`tests/test_geo_schema_factory.py`)
**Schema validity (unit):**
- Output has `@context`, `@type == "Organization"`, a nested `OfferCatalog` with one
  `Service` per `topic_entity`, and a nested `FAQPage`.
- With `entity_wikipedia_url` set → `sameAs == ["<url>"]`.

**Adversarial:**
- **Blank `entity_wikipedia_url` → `sameAs` key is ABSENT** (never `"sameAs": ""`,
  never `"sameAs": [""]`, never `null`). Assert the key does not exist.
- Empty `topic_entities` → graceful minimal object or 422 at the endpoint (never a
  crash or malformed JSON).
- `org_name` blank → graceful (omit/placeholder), valid JSON.

**Serialization (unit):**
- `GeoConfig` round-trips `entity_wikipedia_url` through `to_dict()`/`from_dict()`.
- A stored dict **without** the key still loads (default `""`) — back-compat.

**Contract (`tests/test_geo_schema_integration.py`)** — written BEFORE the frontend:
- `POST /api/geo/entity-schema` 200 → `jsonld`, `schema`, `valid`.
- 401 without auth; 422 unknown domain; 422 empty topic_entities; 422 malformed body.
- Saving GeoConfig with `entity_wikipedia_url` via `POST /api/geo/settings` then
  generating → the URL appears in `sameAs` (end-to-end round-trip).

## Security check
- **SSRF:** No — `entity_wikipedia_url` embedded, never fetched. (If a future
  iteration validates the URL by fetching it, it MUST go through
  `api/crawler/fetcher.py:is_ssrf_safe()` first.)
- **Auth:** Yes — `/api/geo/*` router carries `require_auth`.
- **WordPress:** No — generate-and-suggest; no WP REST call; no domain-validation needed.
- **XSS:** No — JSON-LD returned as data, rendered as text in a copy box.

## Documentation impact
- `docs/api.md` — add `POST /api/geo/entity-schema`.
- No `_CATALOGUE` change (generator, not an issue code).
- `PLAN-V3.0-UNIFIED.md` — flip GA4 to ✅ when merged (closes Workstream GA).

## V4 explainer (apply the standard, as GA3 did)
- **What it is:** builds ready-to-paste JSON-LD that tells search and AI engines who
  your organisation is, what services it offers, and which authoritative entity
  (Wikipedia/Wikidata page) it corresponds to.
- **Why it's useful:** `sameAs` to an authoritative entity is a strong disambiguation
  signal — it helps AI engines confidently identify and cite your organisation.
- **Good vs bad:** linking to your real Wikipedia/Wikidata entity vs leaving it blank
  (no disambiguation) or pointing at an unrelated page (actively misleading).
- **How it can mislead:** schema must match what's visibly on your page and be truthful;
  claiming services or an identity you can't back up can hurt trust and eligibility.
- **How to use:** set your entity URL in GEO settings, generate, paste the JSON-LD into
  the page `<head>`.

## Acceptance criteria
1. `entity_wikipedia_url` added; round-trips; older configs still load; settings save
   persists it.
2. Output nests `Organization → Service → FAQPage`; `sameAs` present when URL set and
   **absent** when blank (adversarial test passes).
3. Endpoint contract tests (401/422/round-trip) pass **before** the frontend card.
4. No LLM, no WP write, no SSRF surface. Full suite green, 0 regressions.
