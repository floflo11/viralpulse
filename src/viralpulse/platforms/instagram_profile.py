"""Instagram profile crawler via ScrapeCreators user/reels endpoint."""

import re
import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import RawPost


class InstagramProfileCrawler:
    """Fetch recent reels from a specific Instagram handle."""

    PLATFORM = "instagram"
    BASE_URL = "https://api.scrapecreators.com/v1/instagram"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    def fetch_user_posts(self, handle: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/user/reels",
            params={"handle": handle},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", data.get("reels", []))[:max_results]

        posts = []
        for item in items:
            media = item.get("media", item)
            caption_obj = media.get("caption", {})
            text = caption_obj.get("text", "") if isinstance(caption_obj, dict) else str(caption_obj or "")
            code = media.get("code", media.get("shortcode", ""))
            media_id = str(media.get("id", media.get("pk", "")))
            user = media.get("user", media.get("owner", {}))
            username = user.get("username", handle)

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=media_id,
                url=f"https://www.instagram.com/reel/{code}/" if code else "",
                author=f"@{username}",
                author_url=f"https://www.instagram.com/{username}/",
                title=None,
                content=text[:2000],
                media_url=None,
                published_at=self._parse_date(media),
                likes=media.get("like_count", 0),
                comments=media.get("comment_count", 0),
                shares=0,
                views=media.get("play_count", media.get("video_play_count", 0)),
                hashtags=re.findall(r'#(\w+)', text),
                raw_data=item,
            ))
        return posts

    def _parse_date(self, media: Dict[str, Any]) -> Optional[str]:
        ts = media.get("taken_at")
        if ts:
            try:
                return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
            except (ValueError, TypeError, OSError):
                pass
        return None
