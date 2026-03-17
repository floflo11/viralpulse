"""Instagram crawler via ScrapeCreators."""

import re
import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PlatformCrawler, RawPost


class InstagramCrawler(PlatformCrawler):
    PLATFORM = "instagram"
    BASE_URL = "https://api.scrapecreators.com/v1/instagram"

    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/reels/search",
            params={"query": query},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_items = data.get("reels") or data.get("items") or data.get("data") or []
        raw_items = raw_items[:max_results]

        posts = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            shortcode = raw.get("shortcode") or raw.get("code", "")
            caption_obj = raw.get("caption", "")
            if isinstance(caption_obj, dict):
                text = caption_obj.get("text", "")
            elif isinstance(caption_obj, str):
                text = caption_obj
            else:
                text = raw.get("text", "")

            owner = raw.get("owner") or raw.get("user") or {}
            username = owner.get("username", "")
            hashtags = re.findall(r'#(\w+)', text)

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=str(raw.get("id") or raw.get("pk", "")),
                url=f"https://www.instagram.com/reel/{shortcode}/" if shortcode else "",
                author=f"@{username}" if username else "",
                author_url=f"https://www.instagram.com/{username}/" if username else None,
                title=None,
                content=text[:2000],
                media_url=None,
                published_at=self._parse_date(raw),
                likes=raw.get("like_count", 0),
                comments=raw.get("comment_count", 0),
                shares=0,
                views=raw.get("video_play_count") or raw.get("video_view_count") or 0,
                hashtags=hashtags,
                raw_data=raw,
            ))
        return posts

    def _parse_date(self, item: Dict[str, Any]) -> Optional[str]:
        ts = item.get("taken_at")
        if not ts:
            return None
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.isoformat()
            except (ValueError, TypeError):
                pass
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
        except (ValueError, TypeError, OSError):
            return None
