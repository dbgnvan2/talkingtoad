"""TT_ALLOW_LOCAL_TARGETS admits loopback for the E2E, and nothing else, nowhere in production.

Spec:  docs/pending/2026-09-02_phase3-happy-path.md#R3.1
Tests: this file
"""
from __future__ import annotations

import pytest

import api.crawler.fetcher as fetcher


@pytest.fixture(autouse=True)
def _clear_cache():
    fetcher._SSRF_CACHE.clear()
    yield
    fetcher._SSRF_CACHE.clear()


def test_loopback_is_denied_by_default(monkeypatch):
    monkeypatch.delenv("TT_ALLOW_LOCAL_TARGETS", raising=False)
    assert fetcher.is_ssrf_safe("http://127.0.0.1:8765/") is False
    assert fetcher.is_ssrf_safe("http://localhost:8765/") is False


def test_flag_admits_loopback_only(monkeypatch):
    monkeypatch.setenv("TT_ALLOW_LOCAL_TARGETS", "1")
    for m, _ in PRODUCTION_MARKERS:
        monkeypatch.delenv(m, raising=False)
    assert fetcher.is_ssrf_safe("http://127.0.0.1:8765/") is True
    assert fetcher.is_ssrf_safe("http://localhost:8765/") is True
    assert fetcher.is_ssrf_safe("http://0.0.0.0/") is False
    # Never the private ranges: the flag is for the fixture server, not the LAN.
    assert fetcher.is_ssrf_safe("http://10.0.0.5/") is False
    assert fetcher.is_ssrf_safe("http://192.168.1.1/") is False
    assert fetcher.is_ssrf_safe("http://169.254.169.254/") is False


from api.env import PRODUCTION_MARKERS


@pytest.mark.parametrize("marker,value", [(n, v or "anything") for n, v in PRODUCTION_MARKERS])
def test_flag_is_inert_in_production(monkeypatch, marker, value):
    """Every marker the app itself honours, from the one shared definition."""
    monkeypatch.setenv("TT_ALLOW_LOCAL_TARGETS", "1")
    monkeypatch.setenv(marker, value)
    assert fetcher.is_ssrf_safe("http://127.0.0.1:8765/") is False
