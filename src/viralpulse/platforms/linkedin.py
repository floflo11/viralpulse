"""LinkedIn crawler via ScrapeCreators."""

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PlatformCrawler, RawPost


class LinkedInCrawler(PlatformCrawler):
    PLATFORM = "linkedin"
    BASE_URL = "https://api.scrapecreators.com/v1/linkedin"

    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/search",
            params={"query": query},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_items = data.get("posts") or data.get("data") or data.get("results") or []
        raw_items = raw_items[:max_results]

        posts = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            post_id = str(raw.get("id") or raw.get("post_id") or raw.get("urn") or "")
            text = raw.get("text") or raw.get("commentary") or raw.get("content", "")
            author_name = raw.get("author_name") or raw.get("author", "")
            author_url = raw.get("author_url") or raw.get("author_profile_url", "")
            url = raw.get("url") or raw.get("post_url", "")

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=post_id,
                url=url,
                author=author_name,
                author_url=author_url or None,
                title=None,
                content=text[:2000],
                media_url=raw.get("image_url") or raw.get("media_url"),
                published_at=self._parse_date(raw),
                likes=raw.get("likes") or raw.get("num_likes", 0),
                comments=raw.get("comments") or raw.get("num_comments", 0),
                shares=raw.get("shares") or raw.get("num_shares", 0),
                views=raw.get("views") or raw.get("num_views", 0),
                raw_data=raw,
            ))
        return posts

    def _parse_date(self, item: Dict[str, Any]) -> Optional[str]:
        for key in ("created_at", "date", "published_at", "timestamp"):
            val = item.get(key)
            if not val:
                continue
            if isinstance(val, (int, float)):
                try:
                    return datetime.fromtimestamp(val, tz=timezone.utc).isoformat()
                except (ValueError, TypeError, OSError):
                    pass
            if isinstance(val, str):
                try:
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    return dt.isoformat()
                except (ValueError, TypeError):
                    pass
        return None
