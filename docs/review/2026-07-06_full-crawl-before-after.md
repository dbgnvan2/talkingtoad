---
status: validation report (V3 — before/after HealthScore)
date: 2026-07-06
site: https://livingsystems.ca
page_cap: 120
scoring_path: compute_impact_health / compute_page_health (shipped, capped+suppressed)
baseline: OLD_ISSUE_SCORING = `cur` column of docs/pending/OLD/2026-07-03_r3-FINAL-calibration.md §4
---

# V3 — Full-crawl before/after HealthScore (livingsystems.ca)

Every page scored under BOTH the current `_ISSUE_SCORING` and the reconstructed pre-R3 `OLD_ISSUE_SCORING` (the `cur` column), via the SAME `compute_page_health` path (cluster suppression + per-category cap + page-fatal bypass). Numbers below are from a real crawl.

## Headline

| Metric | Value |
|---|---|
| Pages scored | 119 |
| Page cap (max_pages) | 120 |
| Issues found | 955 |
| **Site Health — OLD (pre-R3)** | **72** |
| **Site Health — NEW (current)** | **88** |
| **Site Health delta (new − old)** | **+16** |
| Site Health — OLD (mean of isolated pages) | 72 |
| Site Health — NEW (mean of isolated pages) | 88 |

## Severity-mix shift (per issue occurrence)

| Severity | OLD | NEW |
|---|---|---|
| critical | 0 | 0 |
| warning | 477 | 165 |
| info | 478 | 790 |

## Per-page health deltas (sorted by rise)

| Page | OLD | NEW | Δ |
|---|---|---|---|
| https://livingsystems.ca/news_posts | 43 | 80 | +37 |
| https://livingsystems.ca/s2e07-societal-emotional-process | 38 | 75 | +37 |
| https://livingsystems.ca/team_members/maybo-lui | 45 | 79 | +34 |
| https://livingsystems.ca/s2e09-differentiation-own-family | 35 | 69 | +34 |
| https://livingsystems.ca/s2e02-nuclear-family-emotional-system | 45 | 76 | +31 |
| https://livingsystems.ca/team_members/iryna-pauliukova | 48 | 79 | +31 |
| https://livingsystems.ca | 40 | 70 | +30 |
| https://livingsystems.ca/training_calendar | 45 | 75 | +30 |
| https://livingsystems.ca/team_members/lois-walker | 49 | 78 | +29 |
| https://livingsystems.ca/team_members/14528 | 44 | 73 | +29 |
| https://livingsystems.ca/team_members/lori-anne-boutin-crawford | 54 | 83 | +29 |
| https://livingsystems.ca/s1e00-pre-season | 45 | 74 | +29 |
| https://livingsystems.ca/s2e00-pre-season-eight-concepts | 44 | 73 | +29 |
| https://livingsystems.ca/conference/thinking-big-about-family-challenges | 54 | 82 | +28 |
| https://livingsystems.ca/team_members/dixie-vandersluys | 56 | 84 | +28 |
| https://livingsystems.ca/s2e05-sibling-position | 53 | 80 | +27 |
| https://livingsystems.ca/team_members/jennifer-hassard | 55 | 82 | +27 |
| https://livingsystems.ca/s2e04-multigenerational-transmission | 51 | 78 | +27 |
| https://livingsystems.ca/s1e04-relationship-patterns-conflict | 51 | 78 | +27 |
| https://livingsystems.ca/s2e01-inside-outside-positions | 43 | 69 | +26 |
| https://livingsystems.ca/theory-thought-hope | 54 | 80 | +26 |
| https://livingsystems.ca/s3-preseason-bowen-theory-relationships-lifespan | 46 | 72 | +26 |
| https://livingsystems.ca/counselling | 56 | 81 | +25 |
| https://livingsystems.ca/archive-listing | 62 | 87 | +25 |
| https://livingsystems.ca/bowen_systems_podcast | 59 | 84 | +25 |
| https://livingsystems.ca/bowen_family_systems_blog | 57 | 82 | +25 |
| https://livingsystems.ca/events/event1 | 59 | 83 | +24 |
| https://livingsystems.ca/reactivity-role-in-defining-self | 53 | 77 | +24 |
| https://livingsystems.ca/s1e10-differentiation-of-self-part-2 | 55 | 79 | +24 |
| https://livingsystems.ca/team-member-role/acc | 55 | 78 | +23 |
| https://livingsystems.ca/training/bowen-theory-intro-lunch-learn | 63 | 86 | +23 |
| https://livingsystems.ca/training_categories/clinicians | 57 | 80 | +23 |
| https://livingsystems.ca/presentation | 55 | 78 | +23 |
| https://livingsystems.ca/podcasts-by-season | 60 | 83 | +23 |
| https://livingsystems.ca/training/thinking-systems-in-congregations | 63 | 86 | +23 |
| https://livingsystems.ca/team_members/rebecca-van-der-hijde | 60 | 83 | +23 |
| https://livingsystems.ca/team-member-role/faculty | 55 | 78 | +23 |
| https://livingsystems.ca/presentation/the-anxious-field-therapist-self-awareness-and-client-agency-in-an-era-of-systemic-uncertainty | 59 | 82 | +23 |
| https://livingsystems.ca/events | 55 | 78 | +23 |
| https://livingsystems.ca/conference | 55 | 78 | +23 |
| https://livingsystems.ca/s1e01-systems-thinking | 61 | 83 | +22 |
| https://livingsystems.ca/s3-ep1-parents-kathleen-smith | 60 | 82 | +22 |
| https://livingsystems.ca/s4-ep3-artificial-intelligence-dr-patrick-stinson | 62 | 84 | +22 |
| https://livingsystems.ca/the-maturity-point | 60 | 82 | +22 |
| https://livingsystems.ca/newsletter-sign-up-form | 63 | 85 | +22 |
| https://livingsystems.ca/your-family-system-trajectory | 65 | 86 | +21 |
| https://livingsystems.ca/team-member-role/faculty-ministry | 58 | 79 | +21 |
| https://livingsystems.ca/team-member-role/faculty-special | 58 | 79 | +21 |
| https://livingsystems.ca/team-member-role/faculty-public | 58 | 79 | +21 |
| https://livingsystems.ca/banner-message | 58 | 79 | +21 |
| https://livingsystems.ca/crisis-resources | 59 | 80 | +21 |
| https://livingsystems.ca/banner-message/new-banner-2 | 61 | 82 | +21 |
| https://livingsystems.ca/ministry-training | 60 | 80 | +20 |
| https://livingsystems.ca/s4-ep6-religion-matt-steele | 66 | 86 | +20 |
| https://livingsystems.ca/training_categories/hold | 57 | 77 | +20 |
| https://livingsystems.ca/what-kind-of-help-is-helpful | 67 | 87 | +20 |
| https://livingsystems.ca/the-brain-on-love | 64 | 84 | +20 |
| https://livingsystems.ca/contact_us | 66 | 85 | +19 |
| https://livingsystems.ca/s1e06-triangles | 63 | 82 | +19 |
| https://livingsystems.ca/living_systems_faculty | 65 | 84 | +19 |
| https://livingsystems.ca/s3-special-family-life-cycle-monica-mcgoldrick | 67 | 86 | +19 |
| https://livingsystems.ca/s3-ep3-pets-kathleen-cotter-cauley | 65 | 84 | +19 |
| https://livingsystems.ca/s1e07-over-under-functioning | 63 | 82 | +19 |
| https://livingsystems.ca/s3-ep6-coworkers-jake-morrill | 71 | 88 | +17 |
| https://livingsystems.ca/s3-ep5-dating-joe-berger | 71 | 88 | +17 |
| https://livingsystems.ca/s3-ep13-empty-nest-john-bell | 71 | 88 | +17 |
| https://livingsystems.ca/s3-ep18-death-priscilla-friesen | 71 | 88 | +17 |
| https://livingsystems.ca/s3-ep11-step-families-kathleen-cotter-cauley | 71 | 88 | +17 |
| https://livingsystems.ca/s3-ep8-parenting-lauren-errington | 71 | 88 | +17 |
| https://livingsystems.ca/s3-ep15-retirement-kathleen-kerr | 71 | 88 | +17 |
| https://livingsystems.ca/s3-ep12-launching-erik-thompson | 71 | 88 | +17 |
| https://livingsystems.ca/training-2 | 71 | 87 | +16 |
| https://livingsystems.ca/team-member-role/clinical_counsellor | 62 | 78 | +16 |
| https://livingsystems.ca/team-member-role/practicum | 64 | 80 | +16 |
| https://livingsystems.ca/pessimism-is-irresponsible-2 | 77 | 92 | +15 |
| https://livingsystems.ca/wp-content/uploads/2025/01/S1tiny-EP8-Family-Diagram.png | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2026/04/CTA.jpg | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/02/S2-Ep10-DOS-and-Coaching.jpg | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/02/S2-Ep9-DOS-and-Family-.jpg | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/01/S1tiny-EP3-Anxiety-Galloway-scaled.jpg | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/01/S2E2-Amie-Post-smiles.png | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/01/S2-E3-Walter-Smith-Tiny.png | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/01/S1tiny-EP2-Togetherness-scaled.jpg | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/01/S1tiny-EP4-Relationship-Patterns-1-scaled.jpg | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/02/S2-E6-Emotional-Cutoff.jpg | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/01/S1tiny-EP5.png | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/02/S2-E7-Societal-Emotional-Process-scaled.jpg | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/01/S2-Ep-4-Multi-Gen-Process-Collier.jpg | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2026/04/Image-5.jpg | 92 | 96 | +4 |
| https://livingsystems.ca/wp-content/uploads/2025/01/successful-hiking-in-mountains-1.jpg | 95 | 98 | +3 |
| https://livingsystems.ca/wp-content/uploads/2026/05/AdobeStock_267667432.jpg | 95 | 96 | +1 |
| https://livingsystems.ca/wp-content/uploads/2026/07/S4-Ep10-Money-still.jpg | 97 | 98 | +1 |
| https://livingsystems.ca/wp-content/uploads/2026/06/S4-Ep9-Sexual-Diversity-screenshot.jpg | 97 | 98 | +1 |
| https://livingsystems.ca/wp-content/uploads/2026/05/Mark-Smith-President-of-Board.png | 97 | 98 | +1 |
| https://livingsystems.ca/wp-content/uploads/2026/06/S4-Ep7-Politics-still.jpg | 97 | 98 | +1 |
| https://livingsystems.ca/wp-content/uploads/2017/11/Triangles1-1.gif | 97 | 98 | +1 |
| https://livingsystems.ca/wp-content/uploads/2026/05/Public-Pathways.jpg | 97 | 98 | +1 |
| https://livingsystems.ca/wp-content/uploads/2026/05/bowen-1024x683.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-3-ep-10.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2025/04/child-has-to-choose-1.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-3-ep-07.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-3-ep-12.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-4-ep-03.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/06/wworied-woman-at-window-cropped.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-3-ep-14.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/06/main-in-chair-with-laptop-windows-1024x729.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-3-ep-06.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-4-ep-01.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-3-ep-00.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-3-ep-16.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/01/happy-relationships-1807617_640-1.jpg | 98 | 98 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/meditation5-275x300.png | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-4-ep-07.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-3-ep-08.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-3-ep-15.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2025/07/kid-helping-kid-1.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-3-ep-09.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-4-ep-06.jpg | 100 | 100 | +0 |
| https://livingsystems.ca/wp-content/uploads/2026/05/podcast-season-3-ep-19.jpg | 100 | 100 | +0 |

## Top score-movers (|Δimpact| × occurrences)

| Code | old imp | new imp | Δimp | occurrences |
|---|---|---|---|---|
| UNSAFE_CROSS_ORIGIN_LINK | 3 | 0 | -3 | 76 |
| CONVERSATIONAL_H2_MISSING | 4 | 1 | -3 | 64 |
| SEMANTIC_DENSITY_LOW | 3 | 1 | -2 | 76 |
| REDIRECT_TRAILING_SLASH | 2 | 0 | -2 | 74 |
| ANCHOR_TEXT_GENERIC | 4 | 2 | -2 | 68 |
| H1_MISSING | 6 | 4 | -2 | 56 |
| META_DESC_MISSING | 7 | 2 | -5 | 22 |
| FIRST_VIEWPORT_NO_ANSWER | 5 | 2 | -3 | 30 |
| ORPHAN_PAGE | 6 | 4 | -2 | 39 |
| OG_IMAGE_MISSING | 3 | 1 | -2 | 39 |
| TITLE_TOO_SHORT | 5 | 1 | -4 | 18 |
| THIN_CONTENT | 6 | 4 | -2 | 29 |
| LANDMARK_MAIN_MISSING | 2 | 1 | -1 | 47 |
| IMG_OVERSIZED | 5 | 2 | -3 | 15 |
| OG_DESC_MISSING | 3 | 1 | -2 | 22 |
| BROKEN_LINK_503 | 4 | 1 | -3 | 14 |
| CITATIONS_SOURCES_INACCESSIBLE | 4 | 1 | -3 | 10 |
| CITATIONS_ORPHANED | 2 | 1 | -1 | 27 |
| META_DESC_TOO_LONG | 3 | 2 | -1 | 25 |
| TITLE_TOO_LONG | 4 | 2 | -2 | 12 |

## V2 — SCHEMA_VISIBLE_MISMATCH finding (CONFIRMED FALSE-POSITIVE, detector fixed)

Inspected the real pages where SCHEMA_VISIBLE_MISMATCH fired WITH JSON-LD present (R5.2 suppresses it when JSON_LD_MISSING co-fires). On every such page the fired field was `Person.name: "Dave Galloway"` — the site owner's byline, injected by the WP SEO plugin as an author `Person` node in the JSON-LD `@graph`, never present in the visible copy of an unrelated page (episode/blog/service pages). Two @id forms carry this same byline:

- `…/author/dave-galloway/#schema-author` — already suppressed by the pre-existing author-node guard.
- `…/#/schema/person/<hash>` — the sibling @graph identity node; this form SLIPPED the guard and fired site-wide.

**Verdict: theme/plugin artifact (false positive), NOT a true content mismatch.** Fix: extended `_is_author_publisher_node` in `api/services/schema_typing.py` to also recognise the `/schema/person/` graph-node @id form. Impact weight UNCHANGED (6) per V2.2 — the detector was fixed, not the score. A genuine SUBJECT Person (ordinary @id, name absent from copy) still fires (adversarial test `tests/test_schema_typing.py::test_visible_mismatch_no_fp_theme_schema`). The numbers above were generated AFTER the detector fix, so SCHEMA_VISIBLE_MISMATCH no longer appears among the score-movers.

## Method / caveats

- Live crawl of https://livingsystems.ca capped at max_pages=120. Both score columns computed from the SAME crawl's issue rows; only the per-code impact table differs (category, cluster suppression, cap, and page-fatal logic are identical between the two runs).
- OLD impacts are the pre-R3 live impacts (`cur`). Codes absent from the §4 table score old-impact 0 (they did not exist / were unscored pre-R3).
- Severity mix is counted per issue OCCURRENCE (not per unique code) so it reflects what a user saw on the dashboard.
