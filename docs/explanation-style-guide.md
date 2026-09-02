---
status: current
last_reviewed: 2026-09-02
---
# Explanation style guide — how every issue code teaches

TalkingToad's readers are nonprofit staff, not SEO professionals. A flagged code with a
one-line tooltip teaches nothing; a code with a short, honest explanation turns the tool
into a coach. This guide is the bar for every entry in `frontend/src/data/issueHelp.json`
(the single authored source; the Python copy the PDF reads is generated from it).

## The seven fields, in the order the reader meets them

| Field | What it answers | Length |
|---|---|---|
| `title` | The finding, as a headline a manager would repeat | ≤ 60 characters |
| `mission_impact` | The one sentence that says why a nonprofit should care, in their terms | one sentence |
| `definition` | What the check looked at and what it found, plainly | 1–3 sentences |
| `impact` | What is at stake and how the mechanism works, jargon defined inline | 2–4 sentences |
| `good_vs_bad` | `{ good, bad }` — one concrete passing example and one failing one | one sentence each |
| `how_it_can_mislead` | The honest caveat: the evidence tier, the false-positive and false-negative cases, and what a correct-looking-but-wrong result looks like | 2–4 sentences, begins with the tier |
| `fix` | The concrete action, named for WordPress where that is where the reader will do it | 1–3 sentences |
| `confidence` | `Established` · `Reasonable proxy` · `Heuristic` for AI-readiness codes (must equal the API's label); `Established` · `Measured` · `Heuristic` for all others, derived from the code's evidence basis | one word or phrase |

Every field is required. An entry missing one fails `tests/test_issue_help_completeness.py`.

## Rules

1. **Reading level.** A bright reader with no SEO background. Short sentences. If a term
   must appear (`canonical`, `noindex`, `schema`), define it in the same sentence the first
   time: "a canonical tag, which tells Google which copy of a page is the real one".
2. **Show, don't assert.** `good_vs_bad` is two concrete examples, not two adjectives. "Good:
   `<title>Grief Counselling in Vancouver — Living Systems</title>`. Bad: `<title>Home</title>`."
   Use the site's own vocabulary (counselling, programs, donate) rather than e-commerce.
3. **Begin the caveat with the tier.** `how_it_can_mislead` starts "Evidence tier: Heuristic."
   (or Established / Reasonable proxy / Measured), then says when the check is wrong in each
   direction and what a wrong-but-plausible result would look like. This is the trust-builder;
   a caveat that only says "may vary" is not done.
4. **Numbers come from the check.** A threshold quoted in an explanation (30–60 characters,
   70–160, 300 words, 200 KB) must be the one `docs/thresholds.md` records. Never round it to
   sound nicer. If the source behind the check does not publish the number, say so — the
   authority record's `threshold_note` is the sentence to use.
5. **No fear, no hype.** "Google may show a less useful headline" — not "you will lose all
   your traffic". Do not promise a ranking outcome the evidence basis does not support.
6. **The fix names the button.** "In WordPress, open the page, scroll to the Yoast / Rank
   Math box, and fill in *Meta description*." When the fix needs a developer, say so plainly.
7. **Tier vocabulary is fixed.** AI-readiness codes use the three labels the API emits.
   Every other code's `confidence` is derived from `authority.yaml`: a published source →
   `Established`; measured during the crawl → `Measured`; TalkingToad's own judgement →
   `Heuristic`. No other words (the older `Mechanistic` / `Empirical` / `Conventional` set is
   retired).
8. **One source.** `issueHelp.json` is authored; `api/services/issue_help_data.py` is
   generated from it by `scripts/generate_issue_help_py.py` and a sync test fails when
   they differ. Never edit the Python file.

## The gold-standard example

`GEO_SUMMARY_BURIED` (preserved in `PLAN-V4.0.md`): what it is, why it matters, what it
measures, a three-row good/bad table, a caveat that names the tier and the exact
correct-looking-but-wrong result the earlier version produced, and the fix. If a new entry
is not as clear as that one, it is not done.
