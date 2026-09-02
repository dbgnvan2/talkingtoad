"""Environment detection shared by the app and the fetcher — one definition.

Phase 3 sweep (2026-09-02): `api.main._is_production` and the fetcher's
loopback-flag guard each listed the production markers by hand and had
already drifted (Render was missing from one). The fetcher must not import
the app, so the leaf lives here and both import it.
"""

from __future__ import annotations

import os

PRODUCTION_MARKERS = (
    ("VERCEL", "1"),
    ("RAILWAY_ENVIRONMENT", None),   # any value
    ("RENDER", "true"),
    ("ENV", "production"),
)


def is_production() -> bool:
    """True when any host-provider marker says this process is production."""
    for name, value in PRODUCTION_MARKERS:
        got = os.getenv(name, "")
        if value is None:
            if got:
                return True
        elif got.lower() == value:
            return True
    return False
