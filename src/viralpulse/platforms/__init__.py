"""Platform crawler registry."""

from .twitter import TwitterCrawler
from .reddit import RedditCrawler
from .tiktok import TikTokCrawler
from .instagram import InstagramCrawler
from .linkedin import LinkedInCrawler
from .youtube import YouTubeCrawler
from .base import PlatformCrawler, RawPost

CRAWLERS = {
    "reddit": RedditCrawler,
    "tiktok": TikTokCrawler,
    "instagram": InstagramCrawler,
    "youtube": YouTubeCrawler,
    # Twitter and LinkedIn disabled — ScrapeCreators lacks search endpoints for these.
    # Re-enable when endpoints become available or alternative APIs are integrated.
    # "twitter": TwitterCrawler,
    # "linkedin": LinkedInCrawler,
}

ALL_PLATFORMS = list(CRAWLERS.keys())

__all__ = [
    "CRAWLERS", "ALL_PLATFORMS", "PlatformCrawler", "RawPost",
    "TwitterCrawler", "RedditCrawler", "TikTokCrawler",
    "InstagramCrawler", "LinkedInCrawler", "YouTubeCrawler",
]
