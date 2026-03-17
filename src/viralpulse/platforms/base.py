"""Abstract base for platform crawlers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RawPost:
    """Normalized post from any platform."""
    platform: str
    platform_id: str
    url: str
    author: str
    author_url: Optional[str]
    title: Optional[str]
    content: str
    media_url: Optional[str]
    published_at: Optional[str]  # ISO 8601
    likes: int = 0
    comments: int = 0
    shares: int = 0
    views: int = 0
    platform_score: int = 0
    hashtags: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)


class PlatformCrawler(ABC):
    """Abstract base for platform crawlers. All use ScrapeCreators."""

    PLATFORM: str = ""
    BASE_URL: str = "https://api.scrapecreators.com"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
        }

    @abstractmethod
    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        """Search platform for posts matching query."""
        ...
