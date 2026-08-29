# Real-artifact fixtures — lazy-loaded images (E1) and entity schema (E5)

These are **real saved HTTP responses**, not synthetic markup. Recorded 2026-08-29 from
livingsystems.ca, a WordPress site running Smush lazy-loading — the exact configuration the
E1 bug was invisible under.

| File | Source URL | `<img>` | missing/empty alt | `data-src` lazy |
|---|---|---|---|---|
| `livingsystems_emotional_pain.html` | `https://livingsystems.ca/emotional-pain-and-suffering/` | 9 | 8 | 9 |
| `livingsystems_home.html` | `https://livingsystems.ca/` | 11 | 10 | 11 |

`tests/fixtures/entity/livingsystems_home.html` is a copy of the homepage fixture, used by the
E5 entity-value checks for its `application/ld+json` graph.

## Trim applied

`<style>` elements and `<script>` elements were removed to cut the fixtures from ~180 KB to
~72 KB. **`<script type="application/ld+json">` was deliberately preserved** — E5 reads it.
No `<img>` tag, attribute, or body content was altered. Counts above were re-verified after
the trim and match the live pages.

## Why these exist

A synthetic fixture written as `<img src="https://example.com/a.jpg" alt="">` is exactly what
allowed E1 to ship: it uses the idealised shape rather than the one the producer actually
emits (P19). Do not replace these with hand-authored markup. If they need re-recording, fetch
the live pages again and update the counts in this table and in the tests.
