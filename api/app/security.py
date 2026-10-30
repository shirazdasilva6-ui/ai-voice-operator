import hmac

from fastapi import Header, HTTPException

from .config import get_settings


def secret_matches(given: str | None, expected: str) -> bool:
    """Constant-time comparison: `!=` returns faster the earlier the strings differ, which leaks the secret byte by byte."""
    return bool(given) and hmac.compare_digest(given.encode(), expected.encode())


def require_dashboard_token(authorization: str | None = Header(default=None)) -> None:
    token = get_settings().dashboard_token
    if not token:
        return  # local demo mode; production_problems() refuses to start without one
    if not authorization or not secret_matches(authorization.removeprefix("Bearer "), token):
        raise HTTPException(401, "missing or invalid dashboard token")
