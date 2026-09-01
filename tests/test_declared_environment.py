"""What is declared and what is installed must be the same thing.

Class this guards (Cycle 5, bug-class elimination):
    requirements.txt and the working venv are two descriptions of one contract,
    and nothing compared them. 14 of 18 pins were violated. That is not
    cosmetic: under the pinned fastapi~=0.115.0, `from __future__ import
    annotations` makes `background_tasks: BackgroundTasks` an unresolvable
    string, so FastAPI treats it as a required query parameter and
    POST /api/crawl/start returns 422 -- the core endpoint, broken in the
    configuration that ships, while every local test passed.

    The pins are now the versions the code demonstrably works against, and this
    file keeps the two in step: upgrading a package without updating the pin
    turns the suite red on the developer's own machine.

Spec: docs/pending/2026-08-31_dependency-realignment-and-ci.md
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest
from packaging.requirements import Requirement

REPO = Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO / "requirements.txt"


def _requirements() -> list[Requirement]:
    out = []
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(Requirement(line))
    return out


def _installed(req: Requirement) -> str | None:
    try:
        return version(req.name)
    except PackageNotFoundError:
        return None


def _violations(reqs: list[Requirement]) -> list[str]:
    """The comparison under test. Extracted so the adversarial cases below
    exercise THIS function rather than re-deriving it.

    The previous adversarial tests built their own Requirement and called
    `.specifier.contains()` inline, so they asserted only that `packaging`
    works — neutralising the real comparison left them green, which is exactly
    the failure their own docstring described.
    """
    out = []
    for req in reqs:
        inst = _installed(req)
        if inst is None:
            continue  # reported separately
        if not req.specifier.contains(inst, prereleases=True):
            out.append(f"  {req.name}: pinned {req.specifier}, installed {inst}")
    return out


class TestDeclaredMatchesInstalled:
    def test_every_requirement_is_installed(self):
        """Guards the guard: the version check below can only compare packages
        it can find. Without this, a rename or a typo in requirements.txt would
        make the comparison silently skip that line and stay green."""
        missing = [r.name for r in _requirements() if _installed(r) is None]
        assert not missing, (
            f"declared in requirements.txt but not installed: {missing}. "
            "The version check cannot compare what it cannot find."
        )

    def test_installed_versions_satisfy_requirements(self):
        """The environment the tests run in must be the one requirements.txt
        describes — otherwise a green suite says nothing about what ships."""
        violations = _violations(_requirements())
        assert not violations, (
            "Installed versions do not satisfy requirements.txt. The Docker "
            "image installs the pinned set, so these tests are not exercising "
            "what ships:\n" + "\n".join(violations)
            + "\n\nEither update the pin to the version you are developing "
              "against, or install the pinned version."
        )

    def test_the_requirements_file_was_actually_read(self):
        """A parse that yields nothing would make both tests above vacuous."""
        reqs = _requirements()
        assert len(reqs) >= 15, f"only parsed {len(reqs)} requirements — parser is likely broken"
        assert any(r.name == "fastapi" for r in reqs)


class TestTheCheckCanFail:
    """These drive the real `_violations`, so neutralising it turns them red."""

    @pytest.mark.parametrize("spec", ["fastapi==0.0.1", "pytest<1.0"])
    def test_adversarial_a_violated_pin_is_reported(self, spec):
        assert _violations([Requirement(spec)]), (
            f"{spec} is impossible for the installed version, and the "
            "comparison did not report it"
        )

    def test_adversarial_a_satisfied_pin_is_not_reported(self):
        """The inverse: a pin that genuinely holds must not be flagged, or the
        check would be permanently red and get deleted."""
        assert _violations([Requirement(f"fastapi=={version('fastapi')}")]) == []

    def test_adversarial_an_uninstallable_name_is_not_silently_a_violation(self):
        """A package that cannot be found is reported by
        test_every_requirement_is_installed, not swallowed here as a pass."""
        assert _violations([Requirement("definitely-not-a-real-package>=1")]) == []
