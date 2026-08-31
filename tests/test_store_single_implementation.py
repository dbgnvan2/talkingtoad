"""One persistence contract, one implementation.

Class this guards (Cycle 3, bug-class elimination):
    The repo carried two hand-maintained job stores and a Protocol describing a
    third shape. Only SQLite ever executed -- get_job_store() returns Redis only
    when both UPSTASH_REDIS_REST_* vars are set, and the owner never configured
    Upstash. The unexecuted implementation had drifted in every way it could:
    10 public methods missing (including get_exempt_anchor_url_set, called
    unconditionally in run_crawl_task), 10 CrawlJob fields write-only, 14 of 40
    CrawledPage fields never serialised, two list methods stubbed to []. Its
    tests drove an AsyncMock, which returns a Mock for any attribute, so a
    missing method was indistinguishable from a working one (P6).

    Deleting the second implementation removes the drift class outright. These
    tests keep it removed, and -- more importantly -- make the resurrection
    path loud rather than silent.

Spec: docs/pending/2026-08-31_remove-redis-backend.md
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
API = REPO / "api"


def _py_files():
    return [p for p in API.rglob("*.py")]


class TestNoSecondImplementation:
    def test_the_module_is_gone(self):
        assert not (API / "services" / "redis_store.py").exists()

    def test_no_redis_implementation_remains(self):
        """No import or code reference to the deleted store survives in api/.

        Parsed as AST rather than grepped, so a docstring or an error message
        naming the module (job_store.py tells you where to restore it from) is
        not mistaken for a live reference. A substring check would force that
        prose out of the codebase for no benefit.
        """
        offenders = []
        for path in _py_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and "redis_store" in (node.module or ""):
                    offenders.append(f"{path.relative_to(REPO)}:{node.lineno} imports redis_store")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if "redis_store" in alias.name:
                            offenders.append(f"{path.relative_to(REPO)}:{node.lineno} imports {alias.name}")
                elif isinstance(node, ast.Name) and node.id == "RedisJobStore":
                    offenders.append(f"{path.relative_to(REPO)}:{node.lineno} references RedisJobStore")
                elif isinstance(node, ast.Attribute) and node.attr == "RedisJobStore":
                    offenders.append(f"{path.relative_to(REPO)}:{node.lineno} references RedisJobStore")
        assert not offenders, "Deleted Redis store still referenced:\n" + "\n".join(offenders)

    def test_store_annotations_name_one_implementation(self):
        """No `SQLiteJobStore | RedisJobStore` union survives."""
        offenders = [
            str(p.relative_to(REPO))
            for p in _py_files()
            if "| RedisJobStore" in p.read_text(encoding="utf-8")
        ]
        assert not offenders, f"Union annotations remain in: {offenders}"

    def test_upstash_dependency_is_gone(self):
        req = (REPO / "requirements.txt").read_text(encoding="utf-8")
        assert "upstash" not in req.lower(), (
            "upstash-redis is still pinned; the code that used it was deleted."
        )

    def test_unused_jobstore_protocol_is_gone(self):
        """The Protocol was never used as an annotation and had drifted to 46
        methods against SQLiteJobStore's 60 -- a third description of one
        contract, binding nothing."""
        base = (REPO / "api" / "services" / "job_store_base.py").read_text(encoding="utf-8")
        assert "class JobStore(Protocol)" not in base


class TestResurrectionIsLoud:
    """The deletion's real risk is not the missing code -- it is a deployment
    configured for Redis that silently starts on SQLite, serves 200s, and writes
    customer data to a local file nobody backs up. These pin that it cannot.
    """

    def _factory(self):
        from api.services.job_store import get_job_store
        return get_job_store

    def test_upstash_env_raises_rather_than_falling_back(self, monkeypatch):
        monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://fake.upstash.io")
        monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "token")
        with pytest.raises(RuntimeError, match="Redis job store was removed"):
            self._factory()()

    @pytest.mark.parametrize(
        "var",
        ["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"],
    )
    def test_adversarial_partial_upstash_config_also_raises(self, monkeypatch, var):
        """The likelier operator mistake: exactly one var set.

        The old factory required BOTH and silently ignored a half-configured
        deployment -- it fell through to SQLite with no signal. A guard that
        only caught the fully-configured case would leave the quieter, more
        probable failure intact.
        """
        monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
        monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
        monkeypatch.setenv(var, "set")
        with pytest.raises(RuntimeError, match="Redis job store was removed"):
            self._factory()()

    def test_clean_env_still_returns_the_sqlite_store(self, monkeypatch, tmp_path):
        """Guards the guard: the raise must be conditional, not unconditional.

        Without this, a factory that raised on every call would satisfy both
        tests above while breaking the entire app.
        """
        monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
        monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'x.db'}")
        from api.services.sqlite_store import SQLiteJobStore
        assert isinstance(self._factory()(), SQLiteJobStore)
