"""Startup contract — every documented way to start the backend must work.

Class this guards (Cycle 1, bug-class elimination):
    "How to start the backend" is stated in four places — CLAUDE.md, the Railway
    deployment doc, the core-crawler spec, and the Dockerfile. Nothing bound them,
    so one copy drifted to `cd api && uvicorn main:app`, which cannot work:
    api/main.py uses absolute `api.` imports, so from inside api/ the repo root is
    not on sys.path and the import raises ModuleNotFoundError before the server
    binds. The owner hit HTTP 500 on every page — Vite's /api proxy returns 500,
    not a connection error, when nothing is listening on :8000.

Why these tests import rather than string-match:
    A test asserting `target == "api.main:app"` would stay green while the app is
    unstartable for a different reason (renamed module, broken import inside
    main.py). It would pin the string, not the property. So each documented target
    is imported in a subprocess from its documented working directory, which is the
    thing that actually has to hold. test_adversarial_* pins that distinction by
    asserting the wrong targets genuinely fail — a check that cannot fail proves
    nothing (P27).

Spec: docs/pending/2026-08-31_startup-command-contract.md
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# Every file that tells a human or an agent how to start the backend.
# A source that stops yielding commands is a failure, not a pass — see
# test_every_documented_source_still_yields_a_command.
_SOURCES = {
    "CLAUDE.md": REPO / "CLAUDE.md",
    "deployment-railway.md": REPO / "docs" / "deployment-railway.md",
    "core-crawler-spec": REPO / "docs" / "specs" / "core-crawler" / "v1.4-nonprofit-crawler.md",
    "Dockerfile": REPO / "Dockerfile",
}

# `uvicorn <module.path>:<attr>` — the `:` is what separates a real invocation from
# a dependency pin (`uvicorn[standard]>=0.29.0`) or an ASCII diagram (`| uvicorn |`).
_UVICORN = re.compile(r"uvicorn\s+([A-Za-z_][\w.]*:[A-Za-z_]\w*)")
# A `cd <dir> &&` prefix on the same line changes the working directory the
# command is documented to run from.
_CD_PREFIX = re.compile(r"cd\s+([\w./-]+)\s*&&")


def _documented_commands() -> list[tuple[str, str, str]]:
    """Return (source_label, cwd_relative_to_repo, uvicorn_target) for each command."""
    found: list[tuple[str, str, str]] = []
    for label, path in _SOURCES.items():
        if not path.exists():
            pytest.fail(f"Documented-startup source is missing: {path.relative_to(REPO)}")
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _UVICORN.search(line)
            if not m:
                continue
            cd = _CD_PREFIX.search(line[: m.start()])
            # The Dockerfile's WORKDIR /app is the repo root (the build COPYs the
            # repo into /app), so its commands run from the root like the rest.
            found.append((label, cd.group(1) if cd else ".", m.group(1)))
    return found


def _import_target(target: str, cwd: Path) -> subprocess.CompletedProcess:
    """Import the module half of `module:attr` from *cwd*, as uvicorn would."""
    module = target.split(":", 1)[0]
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


class TestStartupContract:
    def test_every_documented_source_still_yields_a_command(self):
        """Guards the guard: a renamed heading must not make this file vacuously green."""
        by_source: dict[str, int] = {}
        for label, _, _ in _documented_commands():
            by_source[label] = by_source.get(label, 0) + 1
        missing = sorted(set(_SOURCES) - set(by_source))
        assert not missing, (
            f"No uvicorn command found in {missing}. Either the docs changed shape "
            f"and this test is now blind, or the command was deleted. Found: {by_source}"
        )

    def test_documented_uvicorn_targets_are_importable(self):
        """The documented command must actually start the app, from its documented CWD."""
        failures = []
        for label, cwd_rel, target in _documented_commands():
            cwd = (REPO / cwd_rel).resolve()
            proc = _import_target(target, cwd)
            if proc.returncode != 0:
                last = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "?"
                failures.append(f"  {label}: `cd {cwd_rel} && uvicorn {target}` -> {last}")
        assert not failures, (
            "Documented start command(s) cannot import the app:\n"
            + "\n".join(failures)
            + "\n\nThe backend never binds, so Vite's /api proxy returns 500 on every call."
        )

    def test_all_docs_agree_on_one_start_command(self):
        """Four copies of one instruction must be one instruction."""
        cmds = _documented_commands()
        distinct = {(cwd, target) for _, cwd, target in cmds}
        assert len(distinct) == 1, (
            "Documented start commands disagree:\n"
            + "\n".join(f"  {label}: cd {cwd} && uvicorn {target}" for label, cwd, target in cmds)
        )


class TestTheCheckCanActuallyFail:
    """Adversarial — what would a correct-looking but wrong result look like?

    A green suite here must mean "the app starts", not "the regex found nothing"
    or "the string matched". These pin that the importability check discriminates.
    """

    def test_adversarial_bare_main_target_is_not_importable_from_root(self):
        """The exact drifted target must fail from the repo root."""
        proc = _import_target("main:app", REPO)
        assert proc.returncode != 0, (
            "`uvicorn main:app` imported from the repo root — the importability "
            "check is not discriminating, so the other tests prove nothing."
        )

    def test_adversarial_api_prefixed_target_is_not_importable_from_api_dir(self):
        """The real failure the owner hit: correct target, wrong working directory."""
        proc = _import_target("api.main:app", REPO / "api")
        assert proc.returncode != 0 and "No module named" in proc.stderr, (
            "`import api.main` succeeded from inside api/. If the layout now "
            "supports both working directories, this contract has changed and "
            "the spec needs revisiting."
        )
