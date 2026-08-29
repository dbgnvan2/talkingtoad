# Micro-spec E5: Check what the Organization schema *says*, not just that it exists

Date: 2026-08-29
Status: **proposal — awaiting approval**
Area: `api/crawler/checkers/cross_page.py`, `api/crawler/checkers/registry.py`,
new `api/config/entity_values.json`, `frontend/src/data/issueHelp.js`, `docs/issue-codes.md`
New codes: `ENTITY_NAP_INCOMPLETE`, `ENTITY_VALUE_PLACEHOLDER`, `ENTITY_HOURS_DEFAULT`,
`ENTITY_FIELD_EMPTY`

## Problem (verified against the live homepage, 2026-08-29)

`SCHEMA_ORG_MISSING` (`checkers/metadata.py:39`) checks only that the homepage *has* an
Organization or LocalBusiness node. Nothing checks whether the values in it are true,
complete, or non-default. `ENTITY_NAME_INCONSISTENT` compares names across pages; it does not
look inside the node.

`ParsedPage.schema_blocks` already carries the full JSON-LD objects, so this needs no new
fetching and no new parsing — only checks that read what is already collected.

Live `@graph` from `https://livingsystems.ca/` on 2026-08-29:

```jsonc
{ "@type": "WebSite",
  "description": "site logo" },                       // ← placeholder leaked into schema

{ "@type": ["Organization", "Place"],
  "legalName": "Living systems counselling and Training society",  // ← inconsistent case
  "description": "…sliding fee plan for afforadble counselling…",  // ← typo, published
  "telephone": [],                                    // ← present but empty
  "openingHoursSpecification": [{ "dayOfWeek": ["Sunday","Monday","Tuesday","Wednesday",
      "Thursday","Friday","Saturday"], "opens": "09:00", "closes": "17:00" }],  // ← Yoast default
  // no address / PostalAddress node at all, on a node typed as Place
}
```

Semrush reported "100% markup health" on this. It is structurally valid and factually wrong:
a `Place` with no address, a phone that renders as an empty array, and seven-day 09:00–17:00
hours that a counselling nonprofit almost certainly does not keep — published to Google as
fact. This was the strongest section of the external audit and TalkingToad has no equivalent.

## Change

Four site-scoped checks in `cross_page.py`, emitted once at the homepage (or the shallowest
page carrying an Organization/LocalBusiness node), added to `_SITE_SCOPED_CODES` so they
deduct once site-wide (`registry.py:610`).

### E5.1 — `ENTITY_NAP_INCOMPLETE`

For a node typed `Organization`, `LocalBusiness`, `Place` or any subtype: report which of the
expected identity fields are absent. Required set differs by type and lives in config:
`Place`/`LocalBusiness` require `address` (with `streetAddress`, `addressLocality`,
`addressRegion`, `postalCode`, `addressCountry`), `telephone`, `email`; plain `Organization`
requires `url`, `logo`, and one contact route. `extra` lists exactly which fields are missing,
so the finding is actionable without a second lookup.

Guard against a false positive: a site with a genuine `sameAs`-only presence and no premises
should not be told to invent an address. The check reports **missing fields for the declared
type** — the fix is either "fill it in" or "stop declaring `Place`", and the recommendation
says both.

### E5.2 — `ENTITY_VALUE_PLACEHOLDER`

A field whose value matches a known placeholder or template default. Patterns in
`api/config/entity_values.json` (rule 9 — this is editorial content):

```json
{
  "placeholder_values": ["site logo", "logo", "your business name", "example",
                         "lorem ipsum", "description goes here", "site description",
                         "just another wordpress site", "n/a", "tbd", "-"],
  "placeholder_fields": ["description", "name", "legalName", "alternateName", "slogan"],
  "default_hours": {"days": 7, "opens": "09:00", "closes": "17:00"},
  "min_description_words": 5
}
```

Matching is case-insensitive on the trimmed value. `"site logo"` as a `WebSite.description`
is caught by exact match; a description under `min_description_words` is caught as too-short
to be real.

### E5.3 — `ENTITY_HOURS_DEFAULT`

`openingHoursSpecification` covering all seven days with identical `opens`/`closes` equal to
the configured default pair. Recommendation: verify the real hours or suppress the property —
never publish a default as a fact. Severity is the highest of the four, because unlike a
missing field this actively asserts something false to a search engine.

### E5.4 — `ENTITY_FIELD_EMPTY`

A field that is **present but empty** — `[]`, `""`, `{}`, `null`. This is distinct from
`ENTITY_NAP_INCOMPLETE` (absent) and is the more diagnostic finding: an empty `telephone: []`
means someone opened the field and did not fill it, so the fix is a settings edit, not a
decision. Same class as P14 — an empty value flowing through as if it were content.

### E5.5 — Registry and parity obligations

Each code needs `_CATALOGUE`, `_ISSUE_SCORING`, `_AI_READINESS_CONFIDENCE`, an
`issueHelp.js` entry and a regenerated `docs/issue-codes.md`; the existing parity tests fail
otherwise. Proposed calibration, following the `_CALIBRATION` tier convention:

| Code | Category | Severity | Confidence | Effect | Impact/Effort |
|---|---|---|---|---|---|
| `ENTITY_HOURS_DEFAULT` | `ai_readiness` | warning | Established | moderate | (4, 1) |
| `ENTITY_NAP_INCOMPLETE` | `ai_readiness` | warning | Established | moderate | (4, 2) |
| `ENTITY_FIELD_EMPTY` | `ai_readiness` | warning | Established | small | (3, 1) |
| `ENTITY_VALUE_PLACEHOLDER` | `ai_readiness` | warning | Reasonable proxy | small | (2, 1) |

All four are `fixability = "developer_needed"` — they are SEO-plugin settings, not content
edits, and TalkingToad must not attempt to write them (the WordPress-safety constraint).

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| E5.1a | `Place` node with no `address` → `ENTITY_NAP_INCOMPLETE`, `extra.missing_fields` names `address` | `tests/test_entity_values.py::test_e5_1a_place_without_address` |
| E5.1b | Complete `LocalBusiness` → no finding | `…::test_e5_1b_complete_nap_clean` |
| E5.1c | **Adversarial (P7):** a plain `Organization` with `sameAs` and no premises is not told to add a street address | `…::test_e5_1c_online_only_org_not_flagged_for_address` |
| E5.2a | `WebSite.description = "site logo"` → `ENTITY_VALUE_PLACEHOLDER` | `…::test_e5_2a_site_logo_description` |
| E5.2b | A real 30-word description → clean | `…::test_e5_2b_real_description_clean` |
| E5.2c | **Adversarial:** a genuine business legitimately named "Example Ltd." must not fire on `name` | `…::test_e5_2c_legitimate_name_containing_example` |
| E5.3a | 7×09:00–17:00 → `ENTITY_HOURS_DEFAULT` | `…::test_e5_3a_seven_day_default_hours` |
| E5.3b | 5 weekdays 09:00–17:00 → clean (a real schedule) | `…::test_e5_3b_weekday_hours_clean` |
| E5.3c | 7 days 08:00–20:00 → clean (7-day, but not the default pair) | `…::test_e5_3c_seven_day_non_default_clean` |
| E5.4a | `telephone: []` → `ENTITY_FIELD_EMPTY`, not `ENTITY_NAP_INCOMPLETE` | `…::test_e5_4a_empty_array_is_empty_not_missing` |
| E5.5a | **Real-artifact (P19/P20):** the saved livingsystems homepage fires exactly `ENTITY_HOURS_DEFAULT`, `ENTITY_VALUE_PLACEHOLDER`, `ENTITY_FIELD_EMPTY`, `ENTITY_NAP_INCOMPLETE` and nothing else | `…::test_e5_5a_real_homepage_expected_findings` |
| E5.5b | **Real-artifact negative:** a saved homepage from a correctly configured site fires none of the four | `…::test_e5_5b_clean_real_site_no_findings` |
| E5.5c | Catalogue ↔ issueHelp ↔ scoring ↔ confidence parity holds for all four | `tests/test_issue_codes_doc_in_sync.py` (existing, extended) |
| E5.5d | Each code is site-scoped: deducts once across a 272-page crawl | `tests/test_site_scope.py::test_e5_5d_entity_codes_deduct_once` |

Fix→test map (P10): **E5.5a and E5.5b first** — a real artifact on both sides. Per P20, a
checker calibrated only on hand-authored ideal examples is an under-exercised checker; the
negative case matters as much as the positive one.

## Fixtures

- `tests/fixtures/entity/livingsystems_home.html` — real, recorded 2026-08-29 (shared with E1).
- `tests/fixtures/entity/clean_localbusiness.html` — a real correctly-configured site, for
  the negative case. To be selected and recorded during implementation; if no suitable real
  page is available the test is marked `xfail` with a note rather than faked with a synthetic
  ideal (rule 1).

## Adjacent issues found, not fixed (rule 10)

- `SCHEMA_ORG_MISSING` fires only on the homepage. A site whose Organization node lives on
  `/about/` and not `/` would be flagged wrongly. Pre-existing; flagged, not changed.
- No check reconciles schema `telephone`/`address` against the phone and address in the
  **visible footer**. `SCHEMA_VISIBLE_MISMATCH` covers a different set of fields. This is a
  real gap and a natural follow-up, but it is a separate check and belongs in its own spec.

## Out of scope

Reading Yoast/plugin settings over the authenticated WordPress API to say *where* to fix it.
That crosses the "scan must never call the WP API" constraint in `engine.py` and needs its own
decision — see the deferred items in the umbrella plan.
