"""Optional Bearer-token authentication.

Mirrors the mechanism used by faster-whisper-server: when ``settings.api_key`` is
unset the dependency is a no-op (the API stays open, matching prior behavior);
when set, protected endpoints require ``Authorization: Bearer <api_key>`` — the
OpenAI client convention. Comparison is constant-time.
"""

import secrets
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

auth_scheme = HTTPBearer(auto_error=False)


def require_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme),
) -> None:
    if not settings.api_key:
        return

    if credentials is None or not secrets.compare_digest(
        credentials.credentials, settings.api_key
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
