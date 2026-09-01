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


def apply_domain_filter(
    issues: list[dict],
    rules: list[Rule],
) -> tuple[list[dict], dict]:
    """Return (kept_issues, report).

    `report` is `{"hidden": int, "by_rule": {rule_key: count}}` and is always
    returned, including when nothing was filtered — the caller attaches it to
    the response so a shorter list always arrives with an account of why.

    A rule naming a code that no longer exists is INERT, not a wildcard. The
    API rejects unknown codes, but a row left behind by a deleted catalogue
    entry must never start hiding real findings.
    """
    if not rules:
        return issues, {"hidden": 0, "by_rule": {}}

    codes = {r["issue_code"] for r in rules if r.get("issue_code")}
    severities = {r["severity"] for r in rules if r.get("severity")}

    kept: list[dict] = []
    by_rule: dict[str, int] = {}
    for issue in issues:
        code = issue.get("issue_code")
        sev = issue.get("severity")
        if code in codes:
            by_rule[code] = by_rule.get(code, 0) + 1
            continue
        if sev in severities:
            key = f"severity:{sev}"
            by_rule[key] = by_rule.get(key, 0) + 1
            continue
        kept.append(issue)

    return kept, {"hidden": len(issues) - len(kept), "by_rule": by_rule}
