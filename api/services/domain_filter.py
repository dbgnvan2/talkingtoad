"""Per-domain issue-code filter — normalisation and read-time application.

What this is, and deliberately is not:

  - It hides findings from the RESULTS LISTS. The checks still run and every
    finding is still stored, so a filter is reversible with no re-crawl.
  - It does NOT touch the health score. `suppressed_issue_codes` is the
    mechanism that changes scoring, deliberately, and lives in its own table
    for exactly that reason. LEARNINGS records that suppressing ORPHAN_PAGE
    *raised* the score — coverage fell and the grade improved — and flags that
    as the wrong direction. A per-domain filter is a much easier lever to pull,
    so it must not be able to move a grade at all.
  - It always reports what it removed. 123 of the 170 catalogue codes are
    `info`, so the severity rule hides roughly 72% of findings; a response that
    just came back shorter would read as a cleaner site, which is the
    suppressed-check-renders-as-clean failure this repo has fixed three times
    (P31/P24).

Spec: docs/functional-specification.md (F1)
Tests: tests/test_domain_issue_filter.py
"""

from __future__ import annotations

from urllib.parse import urlparse

# A rule is {"issue_code": str|None, "severity": str|None} with exactly one set.
Rule = dict


def normalise_filter_domain(value: str) -> str:
    """Reduce any spelling of a site to one comparable key.

    Accepts a bare host or a full URL. Lowercases, drops the port, drops a
    leading `www.`, and strips credentials. Without this, `example.com` and
    `https://WWW.Example.COM:443/` would each address a different rule set and
    an operator who set a filter would watch nothing happen.
    """
    v = (value or "").strip()
    if not v:
        return ""
    if "//" in v:
        v = urlparse(v).netloc or v
    else:
        # `example.com/path` with no scheme — urlparse would call it all a path
        v = v.split("/", 1)[0]
    v = v.split("@")[-1]          # strip any credentials
    v = v.split(":", 1)[0]        # strip the port
    v = v.lower().strip(".")
    if v.startswith("www."):
        v = v[4:]
    return v


def _rule_sets(rules: list[Rule]) -> tuple[set[str], set[str]]:
    """Split rules into (codes, severities). One place, so the dict and model
    callers below cannot drift into filtering different things — the screen and
    the exported report have to describe the same site."""
    return (
        {r["issue_code"] for r in rules if r.get("issue_code")},
        {r["severity"] for r in rules if r.get("severity")},
    )


def _partition(items, rules, get_code, get_sev):
    """Shared engine. Returns (kept, report)."""
    if not rules:
        return list(items), {"hidden": 0, "by_rule": {}}
    codes, severities = _rule_sets(rules)
    kept, by_rule = [], {}
    for item in items:
        code, sev = get_code(item), get_sev(item)
        if code in codes:
            by_rule[code] = by_rule.get(code, 0) + 1
        elif sev in severities:
            key = f"severity:{sev}"
            by_rule[key] = by_rule.get(key, 0) + 1
        else:
            kept.append(item)
    return kept, {"hidden": len(list(items)) - len(kept), "by_rule": by_rule}


def apply_domain_filter(issues: list[dict], rules: list[Rule]) -> tuple[list[dict], dict]:
    """Filter issue DICTS (the API response path).

    A rule naming a code that no longer exists is INERT, not a wildcard. The
    API rejects unknown codes, but a row left behind by a deleted catalogue
    entry must never start hiding real findings.
    """
    return _partition(issues, rules,
                      lambda i: i.get("issue_code"), lambda i: i.get("severity"))


def filter_issue_models(issues, rules: list[Rule]):
    """Filter Issue MODELS (the export path).

    Same engine as apply_domain_filter, deliberately: the owner asked for "a
    report of what shows on the screen — not something different", and two
    copies of the matching logic is exactly how the two would come to differ.
    """
    return _partition(issues, rules,
                      lambda i: i.issue_code, lambda i: i.severity)


def filter_caveat_note(report: dict | None) -> str | None:
    """One sentence for a report that is a FILTERED view, or None.

    Provenance, not content. A PDF is the artefact that leaves the building,
    and its reader is usually not the operator who set the filter — a report
    that silently omits most findings while looking complete is the failure
    worth guarding. Returns None when nothing was hidden, so an unfiltered
    report does not acquire a caveat nobody reads.
    """
    if not report or not report.get("hidden"):
        return None
    parts = []
    for rule, count in sorted(report.get("by_rule", {}).items()):
        label = f"all {rule[9:]}-level findings" if rule.startswith("severity:") else rule
        parts.append(f"{label} ({count})")
    # ASCII only: this string is rendered into the PDF, which is Latin-1
    # (CLAUDE.md, Reporting). An em dash here raised UnicodeEncodeError and
    # took the whole export to a 500 — caught by asserting on the artefact
    # rather than on the call.
    return (
        f"Filtered view - {report['hidden']} finding"
        f"{'' if report['hidden'] == 1 else 's'} hidden for "
        f"{report.get('domain', 'this site')}: {', '.join(parts)}. "
        "They were detected and still count toward the health score; this "
        "report shows the filtered list only."
    )
