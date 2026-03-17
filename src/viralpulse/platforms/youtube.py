"""YouTube crawler via ScrapeCreators."""

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PlatformCrawler, RawPost


class YouTubeCrawler(PlatformCrawler):
    PLATFORM = "youtube"
    BASE_URL = "https://api.scrapecreators.com/v1/youtube"

    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/search",
            params={"query": query},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_items = data.get("videos") or data.get("data") or data.get("results") or []
        raw_items = raw_items[:max_results]

        posts = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            video_id = str(raw.get("id") or raw.get("video_id") or "")
            title = raw.get("title", "")
            description = raw.get("description", "")
            channel = raw.get("channel") or raw.get("author") or {}
            if isinstance(channel, str):
                channel_name = channel
                channel_url = ""
            else:
                channel_name = channel.get("name") or channel.get("title", "")
                channel_url = channel.get("url", "")

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}" if video_id else raw.get("url", ""),
                author=channel_name,
                author_url=channel_url or None,
                title=title,
                content=description[:2000],
                media_url=raw.get("thumbnail") or (f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None),
                published_at=self._parse_date(raw),
                likes=raw.get("likes") or raw.get("like_count", 0),
                comments=raw.get("comments") or raw.get("comment_count", 0),
                shares=0,
                views=raw.get("views") or raw.get("view_count", 0),
                raw_data=raw,
            ))
        return posts

    def _parse_date(self, item: Dict[str, Any]) -> Optional[str]:
        for key in ("published_at", "upload_date", "date", "created_at"):
            val = item.get(key)
            if not val:
                continue
            if isinstance(val, str):
                try:
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    return dt.isoformat()
                except (ValueError, TypeError):
                    pass
        return None
