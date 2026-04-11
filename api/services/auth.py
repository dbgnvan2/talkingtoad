"""
Bearer token authentication for the TalkingToad API (spec §2.9, §6.5).

Token is set via the AUTH_TOKEN environment variable.
When AUTH_TOKEN is not configured, all requests are allowed (useful in local dev).
"""

import os

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """FastAPI dependency — raises 401 if the bearer token is missing or wrong."""
    expected = os.getenv("AUTH_TOKEN", "")
    if not expected:
        # No token configured — dev mode, allow all
        return

    if credentials is None or credentials.credentials != expected:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Missing or invalid Authorization bearer token.",
                    "http_status": 401,
                }
            },
        )
