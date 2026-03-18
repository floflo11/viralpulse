"""API key generation and user authentication."""

import random
from typing import Optional
from viralpulse.db import get_conn

# Wormhole-style word lists — easy to type, easy to remember
ADJECTIVES = [
    "swift", "bold", "calm", "deep", "fast", "gold", "keen", "pure", "warm", "wise",
    "blue", "cool", "dark", "free", "glad", "high", "iron", "just", "kind", "live",
    "mild", "open", "rare", "safe", "true", "vast", "wild", "zen", "epic", "fair",
    "pink", "red", "mint", "jade", "ruby", "sage", "onyx", "coal", "ice", "sun",
    "dawn", "dusk", "moon", "star", "rain", "snow", "wind", "fire", "wave", "leaf",
]

NOUNS = [
    "tiger", "eagle", "whale", "fox", "hawk", "lion", "wolf", "bear", "deer", "dove",
    "oak", "pine", "fern", "moss", "vine", "palm", "reed", "lily", "rose", "iris",
    "river", "ocean", "storm", "cloud", "flame", "stone", "steel", "glass", "pearl", "coral",
    "piano", "cello", "drum", "flute", "harp", "bell", "song", "echo", "pulse", "beat",
    "atlas", "spark", "orbit", "prism", "nexus", "forge", "vault", "tower", "bridge", "arrow",
]


def generate_api_key() -> str:
    """Generate a memorable API key like '42-swift-tiger'."""
    num = random.randint(1, 99)
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    return f"{num}_{adj}_{noun}"


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
