"""X/Twitter crawler via ScrapeCreators."""

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PlatformCrawler, RawPost


class TwitterCrawler(PlatformCrawler):
    PLATFORM = "twitter"
    BASE_URL = "https://api.scrapecreators.com/v1/twitter"

    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/search/tweets",
            params={"query": query, "sort_by": "relevance"},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_items = data.get("tweets") or data.get("data") or data.get("results") or []
        raw_items = raw_items[:max_results]

        posts = []
        for raw in raw_items:
            tweet_id = str(raw.get("id") or raw.get("tweet_id") or raw.get("id_str") or "")
            text = raw.get("full_text") or raw.get("text") or ""
            user = raw.get("user") or raw.get("author") or {}
            screen_name = user.get("screen_name") or user.get("username") or ""

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=tweet_id,
                url=f"https://x.com/{screen_name}/status/{tweet_id}" if screen_name and tweet_id else "",
                author=f"@{screen_name}" if screen_name else "",
                author_url=f"https://x.com/{screen_name}" if screen_name else None,
                title=None,
                content=text,
                media_url=None,
                published_at=self._parse_date(raw),
                likes=raw.get("favorite_count") or raw.get("likes") or 0,
                comments=raw.get("reply_count") or raw.get("replies") or 0,
                shares=raw.get("retweet_count") or raw.get("reposts") or 0,
                views=raw.get("views_count") or raw.get("views") or 0,
                raw_data=raw,
            ))
        return posts

    def _parse_date(self, item: Dict[str, Any]) -> Optional[str]:
        created_at = item.get("created_at")
        if created_at and isinstance(created_at, str):
            try:
                dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                return dt.isoformat()
            except (ValueError, TypeError):
                pass
        ts = item.get("timestamp") or item.get("created_at_timestamp")
        if ts:
            try:
                return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
            except (ValueError, TypeError, OSError):
                pass
        return None
