"""Platform crawler registry."""

from .twitter import TwitterCrawler
from .reddit import RedditCrawler
from .tiktok import TikTokCrawler
from .instagram import InstagramCrawler
from .linkedin import LinkedInCrawler
from .youtube import YouTubeCrawler
from .base import PlatformCrawler, RawPost

CRAWLERS = {
    "twitter": TwitterCrawler,
    "reddit": RedditCrawler,
    "tiktok": TikTokCrawler,
    "instagram": InstagramCrawler,
    "linkedin": LinkedInCrawler,
    "youtube": YouTubeCrawler,
}

ALL_PLATFORMS = list(CRAWLERS.keys())

__all__ = [
    "CRAWLERS", "ALL_PLATFORMS", "PlatformCrawler", "RawPost",
    "TwitterCrawler", "RedditCrawler", "TikTokCrawler",
    "InstagramCrawler", "LinkedInCrawler", "YouTubeCrawler",
]
