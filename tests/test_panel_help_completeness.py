"""P7.1 — every major panel explains itself, in the same five parts.

The app explains what `META_DESC_TOO_LONG` means in seven parts, for all 170
codes, and said nothing at all about the four tools that change a nonprofit's
site. Counted before the work:

    GEOReportPanel      2 explainers (toggle, copy inline in JSX)
    GSCInsightsPanel    1 explainer  (always on, copy in a V4_EXPLAINER object)
    FaqSchemaModal      0
    GeoSettingsModal    0
    ImageAnalysisPanel  0
    BatchOptimizePanel  0

Three copies of the five-label markup, in two forms. Four more would have made
seven, which is the shape the P5.2 gate flagged and the P6.1 gate caught twice
after it. The labels live once, in `PanelExplainer.jsx`; the copy lives once, in
`panelHelp.json`.

Mirrors tests/test_issue_help_completeness.py, including its best idea: a
substance check is only a guard if it has been proved able to reject something.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "frontend" / "src"
_HELP_JSON = _SRC / "data" / "panelHelp.json"
_EXPLAINER = _SRC / "components" / "PanelExplainer.jsx"

PANEL_HELP: dict = json.loads(_HELP_JSON.read_text())

_PARTS = ("what", "why", "goodVsBad", "misleading", "howToUse")

# The four the TODO names — the tools that change a nonprofit's site and
# explained nothing.
_MUST_BE_REGISTERED = {
    "faq-schema", "geo-settings", "image-analysis", "batch-optimise",
}


@pytest.mark.parametrize("panel_id", sorted(PANEL_HELP))
def test_every_registered_panel_has_all_five_parts(panel_id):
    """3.1 — a part that is present but empty is the same as missing."""
    entry = PANEL_HELP[panel_id]
    assert entry.get("title"), f"{panel_id} has no title"
    for part in _PARTS:
        assert entry.get(part), f"{panel_id} is missing '{part}'"
        assert len(entry[part].split()) >= 8, (
            f"{panel_id}.{part} is {len(entry[part].split())} words — too short to teach"
        )


def test_the_four_named_panels_are_registered():
    """3.2 — the item is about these four specifically."""
    missing = _MUST_BE_REGISTERED - set(PANEL_HELP)
    assert not missing, f"panels named by TODO P7.1 with no entry: {sorted(missing)}"


# ── Substance ───────────────────────────────────────────────────────────────
# A caveat has substance when it names a concrete way THAT TOOL is wrong or
# incomplete — not a general reminder to be careful. Copied from
# test_issue_help_completeness.caveat_has_substance, which exists because a
# generic caution reads like a disclosure and teaches nothing.

_VAPID = (
    "may vary", "always review", "use your judgement", "use your judgment",
    "for informational purposes", "no guarantee", "as with any tool",
    "results can differ", "please verify",
)


def misleading_has_substance(text: str) -> bool:
    lowered = text.lower()
    if any(phrase in lowered for phrase in _VAPID):
        return False
    if len(text.split()) < 15:
        return False
    # It must point at something specific: a number, a capitalised identifier, a
    # code-formatted term, or a named consequence.
    return bool(re.search(r"\d|`[^`]+`|[A-Z]{2,}", text))


@pytest.mark.parametrize("panel_id", sorted(PANEL_HELP))
def test_misleading_has_substance(panel_id):
    """3.3 — the field that makes an explainer honest rather than promotional."""
    assert misleading_has_substance(PANEL_HELP[panel_id]["misleading"]), (
        f"{panel_id}: 'misleading' is a general caution, not a concrete way this "
        f"tool misleads:\n  {PANEL_HELP[panel_id]['misleading']}"
    )


@pytest.mark.parametrize("text", [
    "Results may vary; always review the output before publishing.",
    "As with any tool, use your judgement.",
    "Please verify the results.",
    "It can be wrong.",
])
def test_the_adversarial_caveat_fails(text):
    """3.4 — the guard on the guard.

    A substance check nobody has proved CAN reject is a green light, not a
    test: `len(text) > 0` would pass 3.3 for all seven panels and read as rigour.
    """
    assert misleading_has_substance(text) is False, (
        f"the substance check accepted a vapid caveat: {text!r}"
    )


def test_misleading_is_not_a_restatement_of_what_it_is():
    """3.3b — the other way a caveat can be empty: describing the tool again.

    Rejects an entry whose caveat shares most of its vocabulary with `what`.
    """
    for panel_id, entry in PANEL_HELP.items():
        what = set(re.findall(r"[a-z]{5,}", entry["what"].lower()))
        mis = set(re.findall(r"[a-z]{5,}", entry["misleading"].lower()))
        if not mis:
            continue
        overlap = len(what & mis) / len(mis)
        assert overlap < 0.6, (
            f"{panel_id}: 'misleading' repeats 'what it is' ({overlap:.0%} shared "
            f"vocabulary) rather than naming a failure"
        )


# ── One home for the labels, one registry for the ids ───────────────────────


def test_no_panel_hand_writes_the_five_labels():
    """3.5 — the P13 guard, and the reason PanelExplainer exists.

    Three copies of this markup already existed in two forms. The way it reaches
    seven is the next author adding a panel and copying the JSX.
    """
    offenders = []
    for path in _SRC.rglob("*.jsx"):
        if path == _EXPLAINER or "__tests__" in path.parts:
            continue
        if re.search(r"<strong>\s*What it is:", path.read_text()):
            offenders.append(str(path.relative_to(_SRC)))
    assert not offenders, (
        f"these files spell the explainer labels themselves instead of using "
        f"PanelExplainer: {offenders}"
    )


def test_every_panel_that_renders_the_explainer_uses_a_registered_id():
    """3.6 — the failure a shared component introduces that inline copy did not.

    `<PanelExplainer id="batch-optimize" />` against a key spelled
    `batch-optimise` renders nothing, silently, and no completeness test over the
    data would notice.
    """
    used: dict[str, str] = {}
    for path in _SRC.rglob("*.jsx"):
        if path == _EXPLAINER or "__tests__" in path.parts:
            continue
        for m in re.finditer(r"<PanelExplainer[^>]*\bid=[\"']([^\"']+)[\"']", path.read_text()):
            used[m.group(1)] = str(path.relative_to(_SRC))
    assert used, "no panel renders PanelExplainer — the component is unused"
    unknown = {i: f for i, f in used.items() if i not in PANEL_HELP}
    assert not unknown, f"PanelExplainer ids with no entry in panelHelp.json: {unknown}"
    # And the reverse, added at the gate's request: an entry nothing renders is
    # copy nobody will ever read, and every test above would pass it. Both
    # directions or neither — a one-way set check is how a registry rots.
    orphaned = set(PANEL_HELP) - set(used)
    assert not orphaned, (
        f"panelHelp.json entries no panel renders: {sorted(orphaned)}"
    )


def test_the_labels_are_defined_once():
    """3.5b — and the component itself must carry all five."""
    text = _EXPLAINER.read_text()
    for label in ("What it is:", "Why it's useful:", "Good vs bad:",
                  "How it can mislead:", "How to use:"):
        assert label in text or label.replace("'", "&apos;") in text, (
            f"PanelExplainer does not render the label {label!r}"
        )
