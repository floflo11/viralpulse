"""Reddit crawler via ScrapeCreators."""

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PlatformCrawler, RawPost


class RedditCrawler(PlatformCrawler):
    PLATFORM = "reddit"
    BASE_URL = "https://api.scrapecreators.com/v1/reddit"

    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/search",
            params={"query": query, "sort": "relevance", "timeframe": "month"},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_items = data.get("posts") or data.get("data") or []
        raw_items = raw_items[:max_results]

        posts = []
        for raw in raw_items:
            permalink = raw.get("permalink", "")
            url = f"https://www.reddit.com{permalink}" if permalink else ""
            author = raw.get("author", "")

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=raw.get("id", ""),
                url=url,
                author=author,
                author_url=f"https://www.reddit.com/user/{author}" if author else None,
                title=raw.get("title", ""),
                content=raw.get("selftext", "")[:2000],
                media_url=raw.get("thumbnail") if raw.get("thumbnail", "").startswith("http") else None,
                published_at=self._parse_date(raw.get("created_utc")),
                likes=raw.get("ups") or raw.get("score", 0),
                comments=raw.get("num_comments", 0),
                shares=0,
                views=0,
                platform_score=raw.get("score", 0),
                raw_data=raw,
            ))
        return posts

    def _parse_date(self, created_utc) -> Optional[str]:
        if not created_utc:
            return None
        try:
            return datetime.fromtimestamp(float(created_utc), tz=timezone.utc).isoformat()
        except (ValueError, TypeError, OSError):
            return None
