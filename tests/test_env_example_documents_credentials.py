"""Every credential the code reads must be documented in .env.example.

Purpose: a credential that nothing documents is a feature that silently does
         nothing. `TT_PSI_API_KEY` is the case in point — without it the Core Web
         Vitals section quietly degrades to lab-only, and a reader with no
         pointer has no way to know that is why.
Tests:   this file

There was no guard here before. Adding one immediately found two undocumented
credentials — `GSC_OAUTH_CLIENT_SECRET` and `AI_CREDS_ENCRYPTION_KEY` — one of
which is set in the maintainer's real .env, so the gap was live rather than
theoretical.

Scoped to credentials on purpose. Numeric tuning knobs (`TT_OCCURRENCE_STEP`,
`TT_EVIDENCE_ROW_CAP`, and the rest) are documented in docs/thresholds.md, where
they belong; requiring all of them here would fill the file with noise and the
guard would be turned off.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"

# A credential is anything whose name says it is a secret or an identity.
_CREDENTIAL = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|CLIENT_ID")
_ENV_READ = re.compile(
    r"""os\.(?:getenv|environ\.get)\(\s*["']([A-Z][A-Z0-9_]*)["']"""
)

# Names that match the pattern but are not credentials.
_NOT_A_CREDENTIAL = frozenset({
    "API_KEY_READ_HEADER",
})


def _credentials_read_by_api() -> set[str]:
    names: set[str] = set()
    for path in (PROJECT_ROOT / "api").rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        names.update(_ENV_READ.findall(path.read_text()))
    return {
        n for n in names
        if _CREDENTIAL.search(n) and n not in _NOT_A_CREDENTIAL
    }


def test_env_example_exists():
    assert ENV_EXAMPLE.exists(), ".env.example is how a new deployment learns what to set"


@pytest.mark.parametrize("name", sorted(_credentials_read_by_api()))
def test_every_credential_is_documented(name):
    """Fails with the variable's name, so the fix is obvious: add it to
    .env.example with a line saying what breaks without it."""
    text = ENV_EXAMPLE.read_text()
    assert name in text, (
        f"{name} is read by api/ but is absent from .env.example. A credential "
        f"nothing documents is a feature that silently does nothing — add it, "
        f"with a note on what degrades when it is unset."
    )


def test_the_guard_actually_finds_credentials():
    """A guard that matches nothing passes forever. Pin that it sees the real set."""
    found = _credentials_read_by_api()
    assert len(found) >= 6, f"the scan found only {found} — the pattern has drifted"
    assert "TT_PSI_API_KEY" in found
    assert "AUTH_TOKEN" in found


def test_documented_credentials_are_blank_or_commented():
    """.env.example must never carry a real value. It is committed."""
    offenders = []
    for line in ENV_EXAMPLE.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        if _CREDENTIAL.search(name) and value.strip():
            offenders.append(name)
    assert not offenders, f"real-looking values in the committed example: {offenders}"
