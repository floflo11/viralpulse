"""Detect social media platform from URL."""

from urllib.parse import urlparse

PLATFORM_MAP = {
    "x.com": "twitter",
    "twitter.com": "twitter",
    "reddit.com": "reddit",
    "old.reddit.com": "reddit",
    "tiktok.com": "tiktok",
    "instagram.com": "instagram",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "linkedin.com": "linkedin",
    "moltbook.com": "moltbook",
}


def detect_platform(url: str) -> str:
    """Detect platform from URL hostname. Returns platform name or 'web'."""
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower().removeprefix("www.")
        return PLATFORM_MAP.get(hostname, "web")
    except Exception:
        return "web"
