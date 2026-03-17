"""FastAPI application — serves viral post data to AI agents and dashboards."""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse

from viralpulse.auth import generate_api_key, get_user_by_key
from viralpulse.config import settings
from viralpulse.db import get_conn, init_db
from viralpulse.platform_detect import detect_platform
from viralpulse.models import (
    PostResponse, PostsListResponse, Engagement, Scores,
    Topic, PlatformStatus,
)
from viralpulse.platforms import ALL_PLATFORMS

TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(
    title="ViralPulse API",
    description="Top viral social media posts for any topic. Built for AI agents.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SORT_COLUMNS = {
    "composite": "s.composite",
    "engagement": "s.engagement_normalized",
    "velocity": "s.velocity",
    "relevance": "s.relevance",
    "recent": "p.published_at",
}


def _get_user(x_api_key: str = Header(None)):
    """Extract user from X-API-Key header."""
    if not x_api_key:
        raise HTTPException(401, "Missing X-API-Key header")
    user = get_user_by_key(x_api_key)
    if not user:
        raise HTTPException(403, "Invalid API key")
    return user


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def root():
    """Landing page with search, skill download, and topic dashboard."""
    if not settings.database_url:
        return RedirectResponse("/docs")

    try:
        conn = get_conn()
        topics = conn.execute(
            """SELECT t.name, t.updated_at,
                      COUNT(p.id) as post_count,
                      COUNT(DISTINCT p.platform) as platform_count,
                      array_agg(DISTINCT p.platform) as platforms
               FROM topics t LEFT JOIN posts p ON p.topic_id = t.id
               WHERE t.enabled = TRUE
               GROUP BY t.id ORDER BY COUNT(p.id) DESC"""
        ).fetchall()
        total_posts = conn.execute("SELECT COUNT(*) as c FROM posts").fetchone()["c"]
        conn.close()
    except Exception:
        topics = []
        total_posts = 0

    platform_svgs = {
        "reddit": '<svg width="16" height="16" viewBox="0 0 24 24" fill="#FF4500"><path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/></svg>',
        "tiktok": '<svg width="16" height="16" viewBox="0 0 24 24" fill="#000"><path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.28 0 .54.04.79.1v-3.5a6.37 6.37 0 0 0-.79-.05A6.34 6.34 0 0 0 3.15 15a6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.34-6.34V8.8a8.26 8.26 0 0 0 4.85 1.56V6.89a4.84 4.84 0 0 1-1.09-.2z"/></svg>',
        "instagram": '<svg width="16" height="16" viewBox="0 0 24 24" fill="#E1306C"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z"/></svg>',
        "youtube": '<svg width="16" height="16" viewBox="0 0 24 24" fill="#FF0000"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>',
    }
    all_plats = ["reddit", "tiktok", "instagram", "youtube"]

    topic_rows = ""
    for t in topics:
        name = t["name"]
        count = t["post_count"]
        encoded = name.replace(" ", "+")
        active_platforms = set(t["platforms"]) if t["platforms"] and t["platforms"][0] else set()

        icons = ""
        for p in all_plats:
            svg = platform_svgs.get(p, "")
            opacity = "1" if p in active_platforms else "0.15"
            icons += f'<span title="{p}" style="opacity:{opacity};display:inline-flex;">{svg}</span>'

        updated = ""
        if t["updated_at"]:
            try:
                dt = datetime.fromisoformat(str(t["updated_at"]).replace(" ", "T").split("+")[0])
                hours = (datetime.now(timezone.utc).replace(tzinfo=None) - dt).total_seconds() / 3600
                updated = f"{hours:.0f}h ago" if hours < 24 else f"{hours/24:.0f}d ago"
            except Exception:
                updated = "recently"

        topic_rows += f"""
          <tr>
            <td><a href="/view/posts?topic={encoded}&limit=20" class="topic-link">{name}</a></td>
            <td><span class="count-badge">{count}</span></td>
            <td><div style="display:flex;gap:6px;align-items:center;">{icons}</div></td>
            <td style="color:var(--text-muted);font-size:13px;">{updated}</td>
            <td>
              <a href="/view/posts?topic={encoded}&sort=engagement&limit=20" class="view-btn">View</a>
            </td>
          </tr>"""

    if not topic_rows:
        topic_rows = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:32px;">No topics yet. Search above to add one.</td></tr>'

    api_host = f"https://api.aithatjustworks.com"

    html = (TEMPLATES_DIR / "landing.html").read_text()
    html = html.replace("{{TOPIC_ROWS}}", topic_rows)
    html = html.replace("{{TOTAL_POSTS}}", str(total_posts))
    html = html.replace("{{TOPIC_COUNT}}", str(len(topics)))
    html = html.replace("{{API_HOST}}", api_host)
    return html


@app.get("/skill/viral-writer.md", include_in_schema=False)
def get_skill():
    """Serve the viral-writer agent skill file."""
    from fastapi.responses import PlainTextResponse
    api_host = "https://api.aithatjustworks.com"
    content = (TEMPLATES_DIR / "viral-writer.md").read_text()
    content = content.replace("{{API_HOST}}", api_host)
    return PlainTextResponse(content, media_type="text/markdown")


@app.get("/api/v1/crawl-and-view", include_in_schema=False)
def crawl_and_view(topic: str = Query(...)):
    """Crawl a topic on the fly and redirect to the view page."""
    import logging
    logger = logging.getLogger("viralpulse.api")

    if not settings.database_url or not settings.scrapecreators_api_key:
        return RedirectResponse(f"/view/posts?topic={topic.replace(' ', '+')}&limit=20")

    conn = get_conn()
    # Create topic if not exists
    row = conn.execute(
        """INSERT INTO topics (name, search_queries) VALUES (%s, %s)
           ON CONFLICT (name) DO UPDATE SET updated_at = now()
           RETURNING id, name""",
        (topic, json.dumps([topic])),
    ).fetchone()
    conn.commit()
    conn.close()

    # Run crawl
    try:
        from viralpulse.crawler import crawl_topic, store_crawl_results
        posts = crawl_topic(topic)
        if posts:
            store_crawl_results(str(row["id"]), posts, row["name"])
            logger.info(f"On-demand crawl for '{topic}': {len(posts)} posts")
    except Exception as e:
        logger.error(f"On-demand crawl failed for '{topic}': {e}")

    return RedirectResponse(f"/view/posts?topic={topic.replace(' ', '+')}&limit=20")


@app.on_event("startup")
def startup():
    if settings.database_url:
        init_db()


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/platforms")
def list_platforms():
    platforms = []
    for name in ALL_PLATFORMS:
        platforms.append(PlatformStatus(name=name, enabled=True).model_dump())
    return {"platforms": platforms}


@app.get("/api/v1/topics")
def list_topics():
    if not settings.database_url:
        return {"topics": []}
    conn = get_conn()
    rows = conn.execute("SELECT * FROM topics ORDER BY name").fetchall()
    conn.close()
    return {"topics": [dict(r) for r in rows]}


@app.post("/api/v1/topics")
def create_topic(name: str, search_queries: str = ""):
    if not settings.database_url:
        raise HTTPException(500, "No database configured")
    conn = get_conn()
    queries = [q.strip() for q in search_queries.split(",") if q.strip()] if search_queries else [name]
    row = conn.execute(
        """INSERT INTO topics (name, search_queries) VALUES (%s, %s)
           ON CONFLICT (name) DO UPDATE SET search_queries = EXCLUDED.search_queries, updated_at = now()
           RETURNING *""",
        (name, json.dumps(queries)),
    ).fetchone()
    conn.commit()
    conn.close()
    return dict(row)


@app.get("/api/v1/posts", response_model=PostsListResponse)
def get_posts(
    topic: str = Query(..., description="Topic name to search for"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    sort: str = Query("composite", description="Sort by: composite, engagement, velocity, relevance, recent"),
    limit: int = Query(20, ge=1, le=100),
    days: int = Query(30, ge=1, le=365),
):
    if not settings.database_url:
        return PostsListResponse(
            topic=topic, platform=platform or "all", sort=sort,
            count=0, fetched_at=datetime.now(timezone.utc).isoformat(), posts=[],
        )

    sort_col = SORT_COLUMNS.get(sort, "s.composite")
    sort_dir = "DESC NULLS LAST"

    conn = get_conn()

    query_sql = f"""SELECT p.*, s.relevance, s.engagement_normalized, s.velocity, s.composite,
                  e.likes, e.comments, e.shares, e.views, e.platform_score
           FROM posts p
           JOIN topics t ON t.id = p.topic_id
           LEFT JOIN scores s ON s.post_id = p.id
           LEFT JOIN LATERAL (
               SELECT * FROM engagement WHERE post_id = p.id ORDER BY snapshot_at DESC LIMIT 1
           ) e ON true
           WHERE t.name = %s
             AND p.fetched_at > now() - make_interval(days => %s)"""

    params = [topic, days]

    if platform:
        query_sql += " AND p.platform = %s"
        params.append(platform)

    query_sql += f" ORDER BY {sort_col} {sort_dir} LIMIT %s"
    params.append(limit)

    rows = conn.execute(query_sql, params).fetchall()
    conn.close()

    posts = []
    for r in rows:
        posts.append(PostResponse(
            id=str(r["id"]),
            platform=r["platform"],
            url=r["url"],
            author=r["author"] or "",
            author_url=r.get("author_url"),
            title=r.get("title"),
            content=r.get("content", ""),
            media_url=r.get("media_url"),
            published_at=str(r["published_at"]) if r.get("published_at") else None,
            engagement=Engagement(
                likes=r.get("likes") or 0,
                comments=r.get("comments") or 0,
                shares=r.get("shares") or 0,
                views=r.get("views") or 0,
                platform_score=r.get("platform_score") or 0,
            ),
            scores=Scores(
                relevance=r.get("relevance") or 0,
                engagement_normalized=r.get("engagement_normalized") or 0,
                velocity=r.get("velocity") or 0,
                composite=r.get("composite") or 0,
            ),
        ))

    return PostsListResponse(
        topic=topic,
        platform=platform or "all",
        sort=sort,
        count=len(posts),
        fetched_at=datetime.now(timezone.utc).isoformat(),
        posts=posts,
    )


PLATFORM_ICONS = {
    "reddit": ("Reddit", "#FF4500", "reddit.com"),
    "tiktok": ("TikTok", "#00f2ea", "tiktok.com"),
    "instagram": ("Instagram", "#E1306C", "instagram.com"),
    "youtube": ("YouTube", "#FF0000", "youtube.com"),
    "twitter": ("X/Twitter", "#1DA1F2", "x.com"),
    "linkedin": ("LinkedIn", "#0A66C2", "linkedin.com"),
}


def _fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


_tiktok_thumb_cache: dict = {}


def _get_tiktok_thumbnail(url: str) -> str:
    """Fetch TikTok thumbnail via free oEmbed API. Cached in memory."""
    if url in _tiktok_thumb_cache:
        return _tiktok_thumb_cache[url]
    try:
        import httpx
        resp = httpx.get(f"https://www.tiktok.com/oembed?url={url}", timeout=5)
        if resp.status_code == 200:
            thumb = resp.json().get("thumbnail_url", "")
            _tiktok_thumb_cache[url] = thumb
            return thumb
    except Exception:
        pass
    _tiktok_thumb_cache[url] = ""
    return ""


def _get_thumbnail(post_id: str, platform: str, url: str, media_url: str) -> str:
    """Extract best thumbnail URL for a post. Only return URLs that actually work publicly."""
    # YouTube thumbnails always work
    if platform == "youtube" and "watch?v=" in url:
        vid = url.split("watch?v=")[1].split("&")[0]
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    # TikTok via oEmbed (free, no auth, publicly accessible)
    if platform == "tiktok" and "tiktok.com" in url:
        return _get_tiktok_thumbnail(url)
    # Reddit: i.redd.it images are public, preview.redd.it can expire
    if platform == "reddit":
        # Check media_url first (set by crawler from thumbnail field)
        if media_url and "i.redd.it" in media_url:
            return media_url
        # Check raw_data for direct image links
        try:
            conn = get_conn()
            row = conn.execute(
                """SELECT raw_data->>'url_overridden_by_dest' as dest,
                          raw_data->>'thumbnail' as thumb,
                          raw_data->>'post_hint' as hint
                   FROM posts WHERE id = %s""",
                (post_id,),
            ).fetchone()
            conn.close()
            if row and row.get("hint") == "image":
                dest = row.get("dest", "")
                if dest and ("i.redd.it" in dest or "i.imgur.com" in dest):
                    return dest
        except Exception:
            pass
    return ""


def _get_embed_html(platform: str, url: str) -> str:
    """Generate embed HTML for video/content platforms."""
    if platform == "youtube" and "watch?v=" in url:
        vid = url.split("watch?v=")[1].split("&")[0]
        return f'<iframe width="100%" height="315" src="https://www.youtube.com/embed/{vid}" frameborder="0" allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture" allowfullscreen style="border-radius:8px;"></iframe>'
    # TikTok: use thumbnail image instead of embed widget (faster, more reliable)
    if platform == "tiktok" and "tiktok.com" in url:
        thumb = _get_tiktok_thumbnail(url)
        if thumb:
            return f'<a href="{url}" target="_blank" style="display:block;position:relative;"><img src="{thumb}" style="width:100%;max-height:400px;object-fit:cover;border-radius:8px;" loading="lazy"><div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:56px;height:56px;background:rgba(0,0,0,0.6);border-radius:50%;display:flex;align-items:center;justify-content:center;"><svg width="24" height="24" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg></div></a>'
        return ""
    if platform == "instagram" and "/reel/" in url:
        shortcode = url.split("/reel/")[1].strip("/").split("/")[0].split("?")[0]
        return f'<iframe src="https://www.instagram.com/reel/{shortcode}/embed/" width="100%" height="480" frameborder="0" scrolling="no" allowtransparency="true" style="border-radius:8px;background:#000;"></iframe>'
    if platform == "reddit" and "reddit.com" in url:
        return f'<a href="{url}" target="_blank" style="display:block;background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:14px 16px;text-decoration:none;color:#d1d5db;font-size:13px;"><span style="color:#FF4500;font-weight:600;">r/</span> Open on Reddit &#x2197;</a>'
    return ""


@app.get("/view/posts", include_in_schema=False, response_class=HTMLResponse)
def view_posts(
    topic: str = Query(...),
    platform: Optional[str] = Query(None),
    sort: str = Query("composite"),
    limit: int = Query(20, ge=1, le=100),
    days: int = Query(30, ge=1, le=365),
):
    """HTML view of posts — human-readable card layout with media."""
    result = get_posts(topic=topic, platform=platform, sort=sort, limit=limit, days=days)

    sort_options = ""
    for s in ["composite", "engagement", "velocity", "relevance", "recent"]:
        cls = "pill active" if s == sort else "pill"
        encoded_topic = topic.replace(" ", "+")
        plat_param = f"&platform={platform}" if platform else ""
        sort_options += f'<a href="/view/posts?topic={encoded_topic}{plat_param}&sort={s}&limit={limit}" class="{cls}">{s}</a> '

    platform_filters = f'<a href="/view/posts?topic={topic.replace(" ", "+")}&sort={sort}&limit={limit}" class="pill{"  active" if not platform else ""}">All</a> '
    for p in ALL_PLATFORMS:
        cls = "pill active" if p == platform else "pill"
        label, color, _ = PLATFORM_ICONS.get(p, (p, "#888", ""))
        platform_filters += f'<a href="/view/posts?topic={topic.replace(" ", "+")}&platform={p}&sort={sort}&limit={limit}" class="{cls}">{label}</a> '

    has_tiktok = False
    cards = ""
    for i, post in enumerate(result.posts):
        p_label, p_color, p_domain = PLATFORM_ICONS.get(post.platform, (post.platform, "#888", ""))
        score_pct = int(post.scores.composite * 100)
        score_bar_color = "#4ade80" if score_pct >= 70 else "#facc15" if score_pct >= 40 else "#f87171"

        content_preview = (post.content or "")[:280]
        if len(post.content or "") > 280:
            content_preview += "..."

        title_html = f'<div style="font-weight:600;font-size:15px;margin-bottom:6px;color:#1c1917;">{post.title}</div>' if post.title else ""

        engagement_pills = ""
        if post.engagement.views:
            engagement_pills += f'<span style="background:#1a1a2e;padding:4px 10px;border-radius:20px;font-size:12px;">&#x25B6; {_fmt_num(post.engagement.views)}</span>'
        if post.engagement.likes:
            engagement_pills += f'<span style="background:#1a1a2e;padding:4px 10px;border-radius:20px;font-size:12px;">&#x2764; {_fmt_num(post.engagement.likes)}</span>'
        if post.engagement.comments:
            engagement_pills += f'<span style="background:#1a1a2e;padding:4px 10px;border-radius:20px;font-size:12px;">&#x1F4AC; {_fmt_num(post.engagement.comments)}</span>'
        if post.engagement.shares:
            engagement_pills += f'<span style="background:#1a1a2e;padding:4px 10px;border-radius:20px;font-size:12px;">&#x21A9; {_fmt_num(post.engagement.shares)}</span>'

        pub_date = ""
        if post.published_at:
            try:
                dt = datetime.fromisoformat(str(post.published_at).replace(" ", "T").split("+")[0])
                pub_date = dt.strftime("%b %d, %Y")
            except Exception:
                pub_date = str(post.published_at)[:10]

        # Media: thumbnail or embed
        thumb = _get_thumbnail(post.id, post.platform, post.url, post.media_url)
        embed = _get_embed_html(post.platform, post.url)
        if post.platform == "tiktok":
            has_tiktok = True

        media_html = ""
        if thumb:
            # Thumbnail available — show image (with play button for video platforms)
            if post.platform in ("tiktok", "youtube"):
                media_html = f'<a href="{post.url}" target="_blank" style="display:block;position:relative;margin-bottom:12px;"><img src="{thumb}" style="width:100%;max-height:400px;object-fit:cover;border-radius:8px;" loading="lazy" onerror="this.parentElement.style.display=\'none\'"><div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:56px;height:56px;background:rgba(0,0,0,0.55);border-radius:50%;display:flex;align-items:center;justify-content:center;"><svg width="22" height="22" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg></div></a>'
            else:
                media_html = f'<a href="{post.url}" target="_blank" style="display:block;margin-bottom:12px;"><img src="{thumb}" alt="" style="width:100%;max-height:400px;object-fit:cover;border-radius:8px;" loading="lazy" onerror="this.parentElement.style.display=\'none\'"></a>'
        elif embed:
            media_html = f'<div style="margin-bottom:12px;">{embed}</div>'

        # Compute engagement rate if we have views
        eng_rate = ""
        if post.engagement.views and post.engagement.views > 0:
            rate = (post.engagement.likes + post.engagement.comments + post.engagement.shares) / post.engagement.views * 100
            eng_rate = f"{rate:.2f}%"

        # Hours since published
        age_str = ""
        if post.published_at:
            try:
                pub_dt = datetime.fromisoformat(str(post.published_at).replace(" ", "T").split("+")[0])
                hours = (datetime.now(timezone.utc).replace(tzinfo=None) - pub_dt).total_seconds() / 3600
                if hours < 24:
                    age_str = f"{hours:.0f}h ago"
                else:
                    age_str = f"{hours / 24:.1f}d ago"
            except Exception:
                pass

        # Build metrics — real numbers only, no abstract scores
        total_eng = post.engagement.likes + post.engagement.comments + post.engagement.shares

        def _metric(value: str, label: str, color: str = "#1c1917"):
            return f'<div style="text-align:center;min-width:70px;"><div style="color:{color};font-size:18px;font-weight:700;font-family:\'IBM Plex Mono\',monospace;">{value}</div><div style="color:#a8a29e;font-size:11px;margin-top:2px;">{label}</div></div>'

        metrics = ""
        if post.engagement.views:
            metrics += _metric(_fmt_num(post.engagement.views), "Views")
        if post.engagement.likes:
            metrics += _metric(_fmt_num(post.engagement.likes), "Likes", "#dc2626")
        if post.engagement.comments:
            metrics += _metric(_fmt_num(post.engagement.comments), "Comments", "#2563eb")
        if post.engagement.shares:
            metrics += _metric(_fmt_num(post.engagement.shares), "Shares", "#7c3aed")
        if eng_rate:
            metrics += _metric(eng_rate, "Eng. Rate", "#d97706")
        if age_str:
            metrics += _metric(age_str, "Posted")

        metrics_html = f'''
          <div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:space-around;margin-top:14px;padding:14px 12px;background:#fafaf9;border:1px solid #e7e5e4;border-radius:8px;">
            {metrics}
          </div>''' if metrics else ""

        cards += f"""
        <div style="background:#fff;border:1px solid #e7e5e4;border-radius:10px;padding:20px;margin-bottom:16px;transition:box-shadow 0.2s,border-color 0.2s;" onmouseover="this.style.boxShadow='0 4px 16px rgba(0,0,0,0.06)';this.style.borderColor='#d6d3d1'" onmouseout="this.style.boxShadow='none';this.style.borderColor='#e7e5e4'">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <span style="background:{p_color}15;color:{p_color};padding:4px 10px;border-radius:6px;font-size:12px;font-weight:600;">{p_label}</span>
              <a href="{post.author_url or '#'}" target="_blank" style="color:#57534e;font-size:13px;text-decoration:none;font-weight:500;">{post.author}</a>
              <span style="color:#a8a29e;font-size:12px;">{pub_date}</span>
              <span style="color:#d6d3d1;font-size:11px;font-family:'IBM Plex Mono',monospace;">#{i + 1}</span>
            </div>
            <a href="{post.url}" target="_blank" style="color:#2563eb;font-size:12px;text-decoration:none;white-space:nowrap;font-weight:500;">View &rarr;</a>
          </div>
          {title_html}
          {media_html}
          <p style="color:#44403c;font-size:14px;line-height:1.65;margin-bottom:0;">{content_preview}</p>
          {metrics_html}
        </div>"""

    json_url = f"/api/v1/posts?topic={topic.replace(' ', '+')}"
    if platform:
        json_url += f"&platform={platform}"
    json_url += f"&sort={sort}&limit={limit}"

    return f"""<!DOCTYPE html>
<html>
<head>
  <title>{topic} — ViralPulse</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Outfit:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#fafaf9; color:#1c1917; font-family:'Outfit',system-ui,sans-serif; padding:32px 20px; -webkit-font-smoothing:antialiased; }}
    .container {{ max-width:900px; margin:0 auto; }}
    a {{ color:#2563eb; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .pill {{ display:inline-block; padding:6px 14px; border-radius:8px; font-size:13px; text-decoration:none; border:1px solid #e7e5e4; transition:all 0.12s; font-weight:500; }}
    .pill:hover {{ border-color:#d6d3d1; background:#f5f5f4; text-decoration:none; }}
    .pill.active {{ background:#1c1917; color:#fff; border-color:#1c1917; }}
    .pill.active:hover {{ background:#292524; }}
  </style>
</head>
<body>
  <div class="container">
    <div style="margin-bottom:32px;">
      <a href="/" style="color:#a8a29e;font-size:13px;text-decoration:none;">&larr; Back</a>
      <h1 style="font-family:'Instrument Serif',Georgia,serif;font-size:2.2em;font-weight:400;margin-top:8px;">{topic}</h1>
      <p style="color:#78716c;font-size:14px;margin-top:6px;">{result.count} posts &middot; sorted by <strong>{sort}</strong> &middot; <a href="{json_url}" style="font-size:13px;">JSON</a></p>
    </div>

    <div style="margin-bottom:14px;">
      <div style="margin-bottom:8px;color:#a8a29e;font-size:11px;font-family:'IBM Plex Mono',monospace;text-transform:uppercase;letter-spacing:1px;">Platform</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;">{platform_filters}</div>
    </div>
    <div style="margin-bottom:28px;">
      <div style="margin-bottom:8px;color:#a8a29e;font-size:11px;font-family:'IBM Plex Mono',monospace;text-transform:uppercase;letter-spacing:1px;">Sort by</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;">{sort_options}</div>
    </div>

    {cards if cards else '<p style="color:#a8a29e;padding:48px 0;text-align:center;">No posts found for this query.</p>'}
  </div>
</body>
</html>"""


@app.get("/api/v1/profiles")
def list_profiles():
    if not settings.database_url:
        return {"profiles": []}
    conn = get_conn()
    rows = conn.execute(
        """SELECT pr.*, COUNT(p.id) as post_count
           FROM profiles pr
           LEFT JOIN posts p ON p.author ILIKE '%%' || pr.handle || '%%' AND p.platform = pr.platform
           GROUP BY pr.id ORDER BY pr.handle"""
    ).fetchall()
    conn.close()
    return {"profiles": [dict(r) for r in rows]}


@app.post("/api/v1/profiles")
def add_profile(platform: str = Query(...), handle: str = Query(...)):
    if not settings.database_url:
        raise HTTPException(500, "No database configured")
    conn = get_conn()
    row = conn.execute(
        """INSERT INTO profiles (platform, handle) VALUES (%s, %s)
           ON CONFLICT (platform, handle) DO UPDATE SET updated_at = now()
           RETURNING *""",
        (platform, handle.lstrip("@")),
    ).fetchone()
    conn.commit()
    conn.close()
    return dict(row)


@app.get("/api/v1/profiles/{handle}/posts")
def get_profile_posts(handle: str, platform: str = Query(None), limit: int = Query(20, ge=1, le=100)):
    if not settings.database_url:
        return {"handle": handle, "posts": []}
    conn = get_conn()
    query = "SELECT p.*, e.likes, e.comments, e.shares, e.views FROM posts p LEFT JOIN LATERAL (SELECT * FROM engagement WHERE post_id = p.id ORDER BY snapshot_at DESC LIMIT 1) e ON true WHERE p.author ILIKE %s"
    params = [f"%{handle}%"]
    if platform:
        query += " AND p.platform = %s"
        params.append(platform)
    query += " ORDER BY e.likes DESC NULLS LAST LIMIT %s"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"handle": handle, "count": len(rows), "posts": [dict(r) for r in rows]}


@app.get("/api/v1/crawl-profile", include_in_schema=False)
def crawl_profile(platform: str = Query(...), handle: str = Query(...)):
    """Crawl a profile on the fly and redirect to view."""
    import logging
    logger = logging.getLogger("viralpulse.api")

    if not settings.database_url or not settings.scrapecreators_api_key:
        return RedirectResponse(f"/api/v1/profiles/{handle}/posts?platform={platform}")

    handle = handle.lstrip("@")
    conn = get_conn()
    conn.execute(
        """INSERT INTO profiles (platform, handle) VALUES (%s, %s)
           ON CONFLICT (platform, handle) DO UPDATE SET updated_at = now()""",
        (platform, handle),
    )
    conn.commit()
    conn.close()

    try:
        posts = []
        if platform == "twitter":
            from viralpulse.platforms.x_profile import XProfileCrawler
            crawler = XProfileCrawler(settings.scrapecreators_api_key)
            posts = crawler.fetch_user_posts(handle)
        elif platform == "instagram":
            from viralpulse.platforms.instagram_profile import InstagramProfileCrawler
            crawler = InstagramProfileCrawler(settings.scrapecreators_api_key)
            posts = crawler.fetch_user_posts(handle)

        if posts:
            now = datetime.now(timezone.utc).isoformat()
            conn = get_conn()
            for post in posts:
                if not post.url:
                    continue
                existing = conn.execute("SELECT id FROM posts WHERE url = %s", (post.url,)).fetchone()
                if not existing:
                    conn.execute(
                        """INSERT INTO posts (topic_id, platform, platform_id, url, author, author_url,
                           title, content, media_url, published_at, fetched_at, raw_data)
                           VALUES (NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (post.platform, post.platform_id, post.url, post.author, post.author_url,
                         post.title, post.content, post.media_url, post.published_at, now,
                         json.dumps(post.raw_data, default=str)),
                    )
                    conn.execute(
                        """INSERT INTO engagement (post_id, snapshot_at, likes, comments, shares, views)
                           SELECT id, %s, %s, %s, %s, %s FROM posts WHERE url = %s""",
                        (now, post.likes, post.comments, post.shares, post.views, post.url),
                    )
            conn.commit()
            conn.close()
            logger.info(f"Profile crawl @{handle} on {platform}: {len(posts)} posts")
    except Exception as e:
        logger.error(f"Profile crawl failed @{handle}: {e}")

    return RedirectResponse(f"/view/profile?handle={handle}&platform={platform}")


@app.get("/view/saved", include_in_schema=False, response_class=HTMLResponse)
def view_saved(
    key: str = Query(..., description="API key"),
    query: str = Query(None),
    platform: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """HTML view of a user's saved posts library."""
    user = get_user_by_key(key)
    if not user:
        return HTMLResponse("<h1>Invalid API key</h1>", status_code=403)

    conn = get_conn()
    sql = "SELECT * FROM saved_posts WHERE user_id = %s"
    params = [str(user["id"])]
    if platform:
        sql += " AND platform = %s"
        params.append(platform)
    if query:
        sql += " AND (content ILIKE %s OR author ILIKE %s OR user_note ILIKE %s)"
        q = f"%{query}%"
        params.extend([q, q, q])
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    cards = ""
    for i, r in enumerate(rows):
        p = r.get("platform", "web")
        p_label, p_color, _ = PLATFORM_ICONS.get(p, (p, "#888", ""))
        content = (r.get("content") or "")[:200]
        if len(r.get("content") or "") > 200:
            content += "..."
        note = r.get("user_note") or ""
        ss = r.get("screenshot_url") or ""
        status = r.get("status", "pending")
        url = r.get("url", "")

        pub = ""
        if r.get("created_at"):
            try:
                dt = datetime.fromisoformat(str(r["created_at"]).replace(" ", "T").split("+")[0])
                pub = dt.strftime("%b %d, %Y %H:%M")
            except Exception:
                pass

        screenshot_html = ""
        if ss:
            screenshot_html = f'<a href="{ss}" target="_blank"><img src="{ss}" style="width:100%;max-height:300px;object-fit:cover;border-radius:8px;margin-bottom:10px;" loading="lazy" onerror="this.style.display=\'none\'"></a>'

        note_html = f'<div style="background:#fef3c7;border:1px solid #fde68a;border-radius:6px;padding:6px 10px;font-size:12px;color:#92400e;margin-bottom:8px;">Note: {note}</div>' if note else ""

        status_color = "#16a34a" if status == "enriched" else "#d97706" if status == "pending" else "#dc2626"

        cards += f"""
        <div style="background:#fff;border:1px solid #e7e5e4;border-radius:10px;padding:16px;margin-bottom:14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="background:{p_color}15;color:{p_color};padding:3px 8px;border-radius:5px;font-size:11px;font-weight:600;">{p_label}</span>
              <span style="color:#a8a29e;font-size:11px;">{pub}</span>
              <span style="width:6px;height:6px;border-radius:50%;background:{status_color};display:inline-block;" title="{status}"></span>
            </div>
            <a href="{url}" target="_blank" style="color:#2563eb;font-size:11px;text-decoration:none;font-weight:500;">Open &rarr;</a>
          </div>
          {note_html}
          {screenshot_html}
          <p style="color:#44403c;font-size:13px;line-height:1.5;">{content if content else '<span style=\"color:#a8a29e;\">No content extracted</span>'}</p>
          <div style="margin-top:6px;font-size:11px;color:#a8a29e;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{url}</div>
        </div>"""

    filter_pills = f'<a href="/view/saved?key={key}" style="padding:5px 12px;border-radius:20px;font-size:12px;text-decoration:none;{"background:#1c1917;color:#fff;" if not platform else "background:#fff;color:#57534e;border:1px solid #e7e5e4;"}">All</a> '
    for plat in ["twitter", "reddit", "tiktok", "instagram", "youtube", "linkedin", "web"]:
        active = "background:#1c1917;color:#fff;" if plat == platform else "background:#fff;color:#57534e;border:1px solid #e7e5e4;"
        label = PLATFORM_ICONS.get(plat, (plat, "#888", ""))[0]
        filter_pills += f'<a href="/view/saved?key={key}&platform={plat}" style="padding:5px 12px;border-radius:20px;font-size:12px;text-decoration:none;{active}">{label}</a> '

    return f"""<!DOCTYPE html>
<html>
<head>
  <title>My Library — ViralPulse</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Outfit:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#fafaf9; color:#1c1917; font-family:'Outfit',system-ui,sans-serif; padding:32px 20px; }}
    .container {{ max-width:800px; margin:0 auto; }}
  </style>
</head>
<body>
  <div class="container">
    <a href="/" style="color:#a8a29e;font-size:13px;text-decoration:none;">&larr; Back</a>
    <h1 style="font-family:'Instrument Serif',Georgia,serif;font-size:2em;font-weight:400;margin-top:8px;">My Library</h1>
    <p style="color:#78716c;font-size:14px;margin:6px 0 20px;">{len(rows)} saved posts &middot; {user['name']}</p>
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:24px;">{filter_pills}</div>
    {cards if cards else '<p style="color:#a8a29e;text-align:center;padding:48px 0;">No saved posts yet. Use the Chrome extension to save posts!</p>'}
  </div>
</body>
</html>"""


@app.get("/view/profile", include_in_schema=False, response_class=HTMLResponse)
def view_profile(
    handle: str = Query(...),
    platform: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """HTML view of a tracked profile's posts."""
    handle_clean = handle.lstrip("@")

    posts_data = []
    if settings.database_url:
        conn = get_conn()
        query = """SELECT p.*, e.likes, e.comments, e.shares, e.views
                   FROM posts p
                   LEFT JOIN LATERAL (
                       SELECT * FROM engagement WHERE post_id = p.id ORDER BY snapshot_at DESC LIMIT 1
                   ) e ON true
                   WHERE p.author ILIKE %s"""
        params = [f"%{handle_clean}%"]
        if platform:
            query += " AND p.platform = %s"
            params.append(platform)
        query += " ORDER BY e.likes DESC NULLS LAST LIMIT %s"
        params.append(limit)
        posts_data = conn.execute(query, params).fetchall()
        conn.close()

    cards = ""
    for i, r in enumerate(posts_data):
        p_label, p_color, _ = PLATFORM_ICONS.get(r["platform"], (r["platform"], "#888", ""))
        content_preview = (r.get("content") or "")[:280]
        if len(r.get("content") or "") > 280:
            content_preview += "..."

        title_html = f'<div style="font-weight:600;font-size:15px;margin-bottom:6px;color:#1c1917;">{r["title"]}</div>' if r.get("title") else ""

        pub_date = ""
        if r.get("published_at"):
            try:
                dt = datetime.fromisoformat(str(r["published_at"]).replace(" ", "T").split("+")[0])
                pub_date = dt.strftime("%b %d, %Y")
            except Exception:
                pub_date = str(r["published_at"])[:10]

        likes = r.get("likes") or 0
        comments = r.get("comments") or 0
        shares = r.get("shares") or 0
        views = r.get("views") or 0

        def _metric(value: str, label: str, color: str = "#1c1917"):
            return f'<div style="text-align:center;min-width:70px;"><div style="color:{color};font-size:18px;font-weight:700;font-family:\'IBM Plex Mono\',monospace;">{value}</div><div style="color:#a8a29e;font-size:11px;margin-top:2px;">{label}</div></div>'

        metrics = ""
        if views:
            metrics += _metric(_fmt_num(views), "Views")
        if likes:
            metrics += _metric(_fmt_num(likes), "Likes", "#dc2626")
        if comments:
            metrics += _metric(_fmt_num(comments), "Comments", "#2563eb")
        if shares:
            metrics += _metric(_fmt_num(shares), "Shares", "#7c3aed")

        metrics_html = f'''
          <div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:space-around;margin-top:14px;padding:14px 12px;background:#fafaf9;border:1px solid #e7e5e4;border-radius:8px;">
            {metrics}
          </div>''' if metrics else ""

        cards += f"""
        <div style="background:#fff;border:1px solid #e7e5e4;border-radius:10px;padding:20px;margin-bottom:16px;transition:box-shadow 0.2s,border-color 0.2s;" onmouseover="this.style.boxShadow='0 4px 16px rgba(0,0,0,0.06)';this.style.borderColor='#d6d3d1'" onmouseout="this.style.boxShadow='none';this.style.borderColor='#e7e5e4'">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <span style="background:{p_color}15;color:{p_color};padding:4px 10px;border-radius:6px;font-size:12px;font-weight:600;">{p_label}</span>
              <span style="color:#a8a29e;font-size:12px;">{pub_date}</span>
              <span style="color:#d6d3d1;font-size:11px;font-family:'IBM Plex Mono',monospace;">#{i + 1}</span>
            </div>
            <a href="{r['url']}" target="_blank" style="color:#2563eb;font-size:12px;text-decoration:none;white-space:nowrap;font-weight:500;">View &rarr;</a>
          </div>
          {title_html}
          <p style="color:#44403c;font-size:14px;line-height:1.65;margin-bottom:0;">{content_preview}</p>
          {metrics_html}
        </div>"""

    plat_label = f" on {platform}" if platform else ""

    return f"""<!DOCTYPE html>
<html>
<head>
  <title>@{handle_clean} — ViralPulse</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Outfit:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#fafaf9; color:#1c1917; font-family:'Outfit',system-ui,sans-serif; padding:32px 20px; -webkit-font-smoothing:antialiased; }}
    .container {{ max-width:900px; margin:0 auto; }}
    a {{ color:#2563eb; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
  </style>
</head>
<body>
  <div class="container">
    <div style="margin-bottom:32px;">
      <a href="/" style="color:#a8a29e;font-size:13px;text-decoration:none;">&larr; Back</a>
      <h1 style="font-family:'Instrument Serif',Georgia,serif;font-size:2.2em;font-weight:400;margin-top:8px;">@{handle_clean}</h1>
      <p style="color:#78716c;font-size:14px;margin-top:6px;">{len(posts_data)} posts{plat_label} &middot; sorted by likes &middot; <a href="/api/v1/profiles/{handle_clean}/posts{"?platform=" + platform if platform else ""}" style="font-size:13px;">JSON</a></p>
    </div>

    {cards if cards else '<p style="color:#a8a29e;padding:48px 0;text-align:center;">No posts found for this profile. <a href="/api/v1/crawl-profile?platform=' + (platform or 'twitter') + '&handle=' + handle_clean + '">Crawl now</a></p>'}
  </div>
</body>
</html>"""


@app.post("/api/v1/users")
def create_user(body: dict):
    if not settings.database_url:
        raise HTTPException(500, "No database configured")
    name = body.get("name", "")
    email = body.get("email")
    api_key = generate_api_key()
    conn = get_conn()
    row = conn.execute(
        "INSERT INTO users (api_key, name, email) VALUES (%s, %s, %s) RETURNING *",
        (api_key, name, email),
    ).fetchone()
    conn.commit()
    conn.close()
    return dict(row)


@app.post("/api/v1/save")
def save_post(body: dict, user: dict = Depends(_get_user)):
    if not settings.database_url:
        raise HTTPException(500, "No database configured")

    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(400, "url is required")

    platform = detect_platform(url)
    screenshot_b64 = body.get("screenshot_base64")
    metadata = body.get("metadata", {})
    user_note = body.get("user_note")
    source = "extension" if screenshot_b64 else "api"
    status = "enriched" if screenshot_b64 else "pending"

    conn = get_conn()
    row = conn.execute(
        """INSERT INTO saved_posts (user_id, url, platform, author, content, engagement, hashtags,
           published_at, user_note, source, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (user_id, url) DO UPDATE SET
               user_note = COALESCE(EXCLUDED.user_note, saved_posts.user_note),
               status = EXCLUDED.status
           RETURNING *""",
        (str(user["id"]), url, platform,
         metadata.get("author", ""), metadata.get("content", ""),
         json.dumps(metadata.get("engagement")) if metadata.get("engagement") else None,
         json.dumps(metadata.get("hashtags", [])),
         metadata.get("published_at"), user_note, source, status),
    ).fetchone()
    conn.commit()
    post_id = str(row["id"])
    conn.close()

    # Handle screenshot from extension
    if screenshot_b64:
        try:
            from viralpulse.s3 import upload_screenshot_base64
            screenshot_url = upload_screenshot_base64(str(user["id"]), post_id, screenshot_b64)
            conn = get_conn()
            conn.execute("UPDATE saved_posts SET screenshot_url = %s WHERE id = %s", (screenshot_url, post_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.getLogger("viralpulse.api").error(f"S3 upload failed: {e}")
    else:
        # Queue background VM screenshot
        def _bg_enrich():
            try:
                from viralpulse.screenshot import capture_screenshot_and_metadata
                from viralpulse.s3 import upload_screenshot
                ss_bytes, meta = capture_screenshot_and_metadata(url, platform)
                conn = get_conn()
                if ss_bytes:
                    s3_url = upload_screenshot(str(user["id"]), post_id, ss_bytes)
                    conn.execute(
                        """UPDATE saved_posts SET screenshot_url = %s, author = %s, content = %s,
                           hashtags = %s, status = 'enriched' WHERE id = %s""",
                        (s3_url, meta.get("author", ""), meta.get("content", ""),
                         json.dumps(meta.get("hashtags", [])), post_id),
                    )
                else:
                    conn.execute("UPDATE saved_posts SET status = 'failed' WHERE id = %s", (post_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                logging.getLogger("viralpulse.api").error(f"BG enrich failed: {e}")
                try:
                    c = get_conn()
                    c.execute("UPDATE saved_posts SET status = 'failed' WHERE id = %s", (post_id,))
                    c.commit()
                    c.close()
                except Exception:
                    pass
        threading.Thread(target=_bg_enrich, daemon=True).start()

    return {"id": post_id, "status": status, "platform": platform}


@app.get("/api/v1/saved")
def get_saved(
    query: str = Query(None),
    platform: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(_get_user),
):
    conn = get_conn()
    sql = "SELECT * FROM saved_posts WHERE user_id = %s"
    params = [str(user["id"])]

    if platform:
        sql += " AND platform = %s"
        params.append(platform)
    if query:
        sql += " AND (content ILIKE %s OR author ILIKE %s OR user_note ILIKE %s)"
        q = f"%{query}%"
        params.extend([q, q, q])

    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return {"count": len(rows), "posts": [dict(r) for r in rows]}


@app.delete("/api/v1/saved/{post_id}")
def delete_saved(post_id: str, user: dict = Depends(_get_user)):
    conn = get_conn()
    row = conn.execute(
        "DELETE FROM saved_posts WHERE id = %s AND user_id = %s RETURNING id",
        (post_id, str(user["id"])),
    ).fetchone()
    conn.commit()
    conn.close()
    if not row:
        raise HTTPException(404, "Post not found")
    try:
        from viralpulse.s3 import delete_screenshot
        delete_screenshot(str(user["id"]), post_id)
    except Exception:
        pass
    return {"deleted": True}


@app.get("/api/v1/posts/{post_id}")
def get_post(post_id: str):
    if not settings.database_url:
        raise HTTPException(404, "No database configured")
    conn = get_conn()
    post = conn.execute("SELECT * FROM posts WHERE id = %s", (post_id,)).fetchone()
    if not post:
        conn.close()
        raise HTTPException(404, "Post not found")

    engagement_history = conn.execute(
        "SELECT * FROM engagement WHERE post_id = %s ORDER BY snapshot_at DESC",
        (post_id,),
    ).fetchall()

    scores = conn.execute(
        "SELECT * FROM scores WHERE post_id = %s", (post_id,)
    ).fetchone()

    conn.close()
    return {
        "post": dict(post),
        "engagement_history": [dict(e) for e in engagement_history],
        "scores": dict(scores) if scores else None,
    }
