"""JSON configuration files and their loader.

Editorial content — placeholder vocabularies, classification thresholds, owner
maps, card-class patterns — lives here as JSON rather than as Python literals
(global rule 9). The loader validates required keys at import time and raises,
so a malformed or truncated config fails loudly instead of silently defaulting
to behaviour nobody chose (P2).

Spec: docs/pending/2026-08-29_E0-umbrella-plan.md
Tests: tests/test_config_loader.py
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parent


class ConfigError(RuntimeError):
    """A config file is missing, unparseable, or missing a required key."""


@lru_cache(maxsize=None)
def load_config(name: str, *, required_keys: tuple[str, ...] = ()) -> dict[str, Any]:
    """Load ``api/config/<name>.json``, verifying it has *required_keys*.

    Cached: config is read once per process. Raises :class:`ConfigError` on a
    missing file, invalid JSON, or a missing required key — never returns a
    partial dict that a caller would have to guess about.
    """
    path = CONFIG_DIR / f"{name}.json"
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config file {path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"config file {path} must contain a JSON object")

    missing = [k for k in required_keys if k not in data]
    if missing:
        raise ConfigError(f"config file {path} is missing required keys: {missing}")
    return data
