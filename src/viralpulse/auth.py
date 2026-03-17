"""API key generation and user authentication."""

import secrets
from typing import Optional
from viralpulse.db import get_conn


def generate_api_key() -> str:
    """Generate a unique API key with vp_ prefix."""
    return f"vp_{secrets.token_urlsafe(18)}"


def get_user_by_key(api_key: str) -> Optional[dict]:
    """Look up user by API key. Returns user dict or None."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE api_key = %s", (api_key,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def require_user(api_key: str) -> dict:
    """Get user or raise ValueError."""
    user = get_user_by_key(api_key)
    if not user:
        raise ValueError("Invalid API key")
    return user
