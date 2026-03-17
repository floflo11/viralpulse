"""FastAPI application — serves viral post data to AI agents and dashboards."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse

from viralpulse.config import settings
from viralpulse.db import get_conn, init_db
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


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def root():
    """Landing page with search and topic cards."""
    if not settings.database_url:
        return RedirectResponse("/docs")

    try:
        conn = get_conn()
        topics = conn.execute(
            """SELECT t.name, COUNT(p.id) as post_count
               FROM topics t LEFT JOIN posts p ON p.topic_id = t.id
               WHERE t.enabled = TRUE
               GROUP BY t.id ORDER BY COUNT(p.id) DESC"""
        ).fetchall()
        conn.close()
    except Exception:
        topics = []

    topic_cards = ""
    for idx, t in enumerate(topics):
        name = t["name"]
        count = t["post_count"]
        encoded = name.replace(" ", "+")
        delay = f"animation-delay:{0.4 + idx * 0.08}s;"
        topic_cards += f"""
      <a href="/view/posts?topic={encoded}&limit=20" class="topic-card fade-in" style="{delay}">
        <div class="topic-name">{name}</div>
        <div class="topic-meta">
          <span class="topic-count">{count} posts</span>
          <span>Updated daily</span>
        </div>
        <div class="topic-links">
          <a href="/view/posts?topic={encoded}&sort=engagement&limit=20">Top engagement</a>
          <a href="/view/posts?topic={encoded}&sort=velocity&limit=20">Fastest rising</a>
          <a href="/view/posts?topic={encoded}&platform=tiktok&limit=20">TikTok</a>
          <a href="/view/posts?topic={encoded}&platform=reddit&limit=20">Reddit</a>
          <a href="/view/posts?topic={encoded}&platform=youtube&limit=20">YouTube</a>
        </div>
      </a>"""

    if not topic_cards:
        topic_cards = '<p style="color:var(--text-dim);grid-column:1/-1;">No topics yet. Search above to add one.</p>'

    html = (TEMPLATES_DIR / "landing.html").read_text()
    html = html.replace("{{TOPIC_CARDS}}", topic_cards)
    return html


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
