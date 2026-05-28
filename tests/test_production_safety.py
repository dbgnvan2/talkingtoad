"""Tests for v2.3 M0.8 production-safety checks.

The checks live in api.main._is_production and api.main._assert_production_safe.
They're invoked at module import — which makes them tricky to test because the
import runs once. We test the functions directly with environment monkeypatching
to verify each fail-closed branch works.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# _is_production() — environment detection
# ---------------------------------------------------------------------------


class TestIsProduction:
    @pytest.mark.parametrize("env_var,value", [
        ("VERCEL", "1"),
        ("RAILWAY_ENVIRONMENT", "production"),
        ("RAILWAY_ENVIRONMENT", "staging"),
        ("RENDER", "true"),
        ("ENV", "production"),
        ("ENV", "PRODUCTION"),  # case-insensitive
    ])
    def test_detects_production_marker(self, monkeypatch, env_var, value):
        """Each known production marker should be recognized."""
        # Clear all production markers first
        for var in ["VERCEL", "RAILWAY_ENVIRONMENT", "RENDER", "ENV"]:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv(env_var, value)

        from api.main import _is_production
        assert _is_production() is True

    def test_no_markers_means_dev(self, monkeypatch):
        for var in ["VERCEL", "RAILWAY_ENVIRONMENT", "RENDER", "ENV"]:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("ENV", "development")

        from api.main import _is_production
        assert _is_production() is False

    def test_vercel_other_value_not_production(self, monkeypatch):
        """Adversarial: VERCEL=0 must NOT trigger production mode."""
        for var in ["RAILWAY_ENVIRONMENT", "RENDER", "ENV"]:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("VERCEL", "0")

        from api.main import _is_production
        assert _is_production() is False


# ---------------------------------------------------------------------------
# _assert_production_safe() — fail-closed checks
# ---------------------------------------------------------------------------


class TestAssertProductionSafe:
    def test_dev_with_no_auth_token_passes_with_warning(self, monkeypatch, caplog):
        """Dev mode without AUTH_TOKEN logs a warning but does NOT crash."""
        for var in ["VERCEL", "RAILWAY_ENVIRONMENT", "RENDER", "ENV"]:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.delenv("AUTH_TOKEN", raising=False)

        from api.main import _assert_production_safe
        # Should not raise
        _assert_production_safe()

    def test_production_with_no_auth_token_refuses_to_start(self, monkeypatch):
        """Production environment + AUTH_TOKEN unset = RuntimeError."""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("AUTH_TOKEN", raising=False)
        # Make sure ALLOWED_ORIGINS isn't also tripping
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.com")

        from api.main import _assert_production_safe
        with pytest.raises(RuntimeError, match="P2 fail-closed"):
            _assert_production_safe()

    def test_production_with_empty_auth_token_refuses_to_start(self, monkeypatch):
        """Adversarial: AUTH_TOKEN set but empty string. Still fail."""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("AUTH_TOKEN", "")
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.com")

        from api.main import _assert_production_safe
        with pytest.raises(RuntimeError, match="P2 fail-closed"):
            _assert_production_safe()

    def test_production_with_wildcard_origins_refuses_to_start(self, monkeypatch):
        """ALLOWED_ORIGINS=* in production = RuntimeError (CSRF surface)."""
        monkeypatch.setenv("VERCEL", "1")
        monkeypatch.setenv("AUTH_TOKEN", "valid-token")
        monkeypatch.setenv("ALLOWED_ORIGINS", "*")

        from api.main import _assert_production_safe
        with pytest.raises(RuntimeError, match="P3 fail-closed"):
            _assert_production_safe()

    def test_production_with_wildcard_in_origin_list_refuses_to_start(self, monkeypatch):
        """Adversarial: comma-separated list containing *."""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("AUTH_TOKEN", "valid-token")
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.com, *, https://other.com")

        from api.main import _assert_production_safe
        with pytest.raises(RuntimeError, match="P3 fail-closed"):
            _assert_production_safe()

    def test_production_with_specific_origins_passes(self, monkeypatch):
        """Properly configured production: auth + specific origin = OK."""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("AUTH_TOKEN", "valid-token")
        monkeypatch.setenv(
            "ALLOWED_ORIGINS",
            "https://app.example.com,https://staging.example.com",
        )

        from api.main import _assert_production_safe
        # Should not raise
        _assert_production_safe()
