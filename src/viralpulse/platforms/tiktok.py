"""TikTok crawler via ScrapeCreators."""

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PlatformCrawler, RawPost


class TikTokCrawler(PlatformCrawler):
    PLATFORM = "tiktok"
    BASE_URL = "https://api.scrapecreators.com/v1/tiktok"

    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/search/keyword",
            params={"query": query, "sort_by": "relevance"},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_entries = data.get("search_item_list") or data.get("data") or []
        raw_items = []
        for entry in raw_entries:
            if isinstance(entry, dict):
                raw_items.append(entry.get("aweme_info", entry))
        raw_items = raw_items[:max_results]

        posts = []
        for raw in raw_items:
            video_id = str(raw.get("aweme_id", ""))
            text = raw.get("desc", "")
            stats = raw.get("statistics") or {}
            author_info = raw.get("author") or {}
            username = author_info.get("unique_id", "")
            share_url = raw.get("share_url", "").split("?")[0]
            url = share_url or (f"https://www.tiktok.com/@{username}/video/{video_id}" if username and video_id else "")

            text_extra = raw.get("text_extra") or []
            hashtags = [t.get("hashtag_name", "") for t in text_extra
                        if isinstance(t, dict) and t.get("hashtag_name")]

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=video_id,
                url=url,
                author=f"@{username}" if username else "",
                author_url=f"https://www.tiktok.com/@{username}" if username else None,
                title=None,
                content=text,
                media_url=None,
                published_at=self._parse_date(raw),
                likes=stats.get("digg_count", 0),
                comments=stats.get("comment_count", 0),
                shares=stats.get("share_count", 0),
                views=stats.get("play_count", 0),
                hashtags=hashtags,
                raw_data=raw,
            ))
        return posts

    def _parse_date(self, item: Dict[str, Any]) -> Optional[str]:
        ts = item.get("create_time")
        if ts:
            try:
                return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
            except (ValueError, TypeError, OSError):
                pass
        return None
