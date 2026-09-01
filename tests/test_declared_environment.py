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
        violations = []
        for req in _requirements():
            inst = _installed(req)
            if inst is None:
                continue  # reported by the test above
            if not req.specifier.contains(inst, prereleases=True):
                violations.append(f"  {req.name}: pinned {req.specifier}, installed {inst}")
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
    @pytest.mark.parametrize(
        "spec",
        ["fastapi==0.0.1", "pytest<1.0"],
    )
    def test_adversarial_a_violated_pin_is_detected(self, spec):
        """An impossible pin must be reported. Without this the comparison
        could be inverted, or `contains()` misused, and the suite would stay
        green over any amount of drift."""
        req = Requirement(spec)
        inst = _installed(req)
        assert inst is not None, "package not installed; test cannot discriminate"
        assert not req.specifier.contains(inst, prereleases=True), (
            f"{spec} unexpectedly matched installed {inst} — the version "
            "comparison is not discriminating"
        )

    def test_adversarial_a_satisfied_pin_is_not_reported(self):
        """The inverse: the check must not flag a pin that genuinely holds, or
        it would be permanently red and get deleted."""
        inst = version("fastapi")
        req = Requirement(f"fastapi=={inst}")
        assert req.specifier.contains(inst, prereleases=True)
