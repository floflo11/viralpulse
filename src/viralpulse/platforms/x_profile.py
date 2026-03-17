"""X/Twitter profile crawler via ScrapeCreators user-tweets endpoint."""

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PlatformCrawler, RawPost


class XProfileCrawler:
    """Fetch recent tweets from a specific X handle."""

    PLATFORM = "twitter"
    BASE_URL = "https://api.scrapecreators.com/v1/twitter"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    def fetch_user_posts(self, handle: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/user-tweets",
            params={"handle": handle},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        tweets = data.get("tweets", data.get("data", []))[:max_results]

        posts = []
        for raw in tweets:
            legacy = raw.get("legacy", {})
            core = raw.get("core", {}).get("user_results", {}).get("result", {})
            user_legacy = core.get("legacy", {})
            screen_name = user_legacy.get("screen_name", handle)
            tweet_id = legacy.get("id_str", raw.get("rest_id", ""))
            text = legacy.get("full_text", "")
            views = raw.get("views", {}).get("count", 0)
            if isinstance(views, str):
                try:
                    views = int(views)
                except (ValueError, TypeError):
                    views = 0

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=tweet_id,
                url=f"https://x.com/{screen_name}/status/{tweet_id}" if tweet_id else "",
                author=f"@{screen_name}",
                author_url=f"https://x.com/{screen_name}",
                title=None,
                content=text,
                media_url=None,
                published_at=self._parse_date(legacy),
                likes=legacy.get("favorite_count", 0),
                comments=legacy.get("reply_count", 0),
                shares=legacy.get("retweet_count", 0),
                views=views,
                raw_data=raw,
            ))
        return posts

    def _parse_date(self, legacy: Dict[str, Any]) -> Optional[str]:
        created = legacy.get("created_at", "")
        if created:
            try:
                dt = datetime.strptime(created, "%a %b %d %H:%M:%S %z %Y")
                return dt.isoformat()
            except (ValueError, TypeError):
                pass
        return None
