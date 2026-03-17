"""FastAPI application — serves viral post data to AI agents and dashboards."""

import json
from datetime import datetime, timezone
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
    """Landing page with example queries."""
    if not settings.database_url:
        return RedirectResponse("/docs")

    # Get available topics from DB
    try:
        conn = get_conn()
        topics = conn.execute(
            """SELECT t.name, COUNT(p.id) as post_count
               FROM topics t LEFT JOIN posts p ON p.topic_id = t.id
               WHERE t.enabled = TRUE
               GROUP BY t.id ORDER BY t.name"""
        ).fetchall()
        conn.close()
    except Exception:
        topics = []

    topic_cards = ""
    for t in topics:
        name = t["name"]
        count = t["post_count"]
        encoded = name.replace(" ", "+")
        topic_cards += f"""
        <div style="background:#1a1a2e;border:1px solid #16213e;border-radius:12px;padding:20px;margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <h3 style="margin:0;color:#e94560;">{name}</h3>
            <span style="color:#888;font-size:13px;">{count} posts</span>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;">
            <a href="/view/posts?topic={encoded}&limit=5" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">Top 5 (all platforms)</a>
            <a href="/view/posts?topic={encoded}&platform=tiktok&sort=engagement&limit=5" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">TikTok by engagement</a>
            <a href="/view/posts?topic={encoded}&platform=reddit&sort=composite&limit=5" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">Reddit top composite</a>
            <a href="/view/posts?topic={encoded}&platform=youtube&limit=5" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">YouTube top 5</a>
            <a href="/view/posts?topic={encoded}&sort=velocity&limit=10" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">Fastest rising (velocity)</a>
            <a href="/view/posts?topic={encoded}&sort=recent&limit=10" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">Most recent</a>
          </div>
        </div>"""

    if not topic_cards:
        topic_cards = '<p style="color:#888;">No topics yet. Add one via <code>POST /api/v1/topics</code> or the CLI.</p>'

    return f"""<!DOCTYPE html>
<html>
<head>
  <title>ViralPulse API</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#0a0a1a; color:#e2e2e2; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; padding:40px 20px; }}
    .container {{ max-width:800px; margin:0 auto; }}
    a {{ color:#e94560; }}
    a:hover {{ opacity:0.8; }}
    code {{ background:#1a1a2e; padding:2px 6px; border-radius:4px; font-size:13px; }}
    pre {{ background:#1a1a2e; padding:16px; border-radius:8px; overflow-x:auto; font-size:13px; line-height:1.5; }}
  </style>
</head>
<body>
  <div class="container">
    <h1 style="font-size:2.2em;margin-bottom:4px;">ViralPulse API</h1>
    <p style="color:#888;margin-bottom:30px;">Top viral social media posts for any topic. Built for AI agents.</p>

    <h2 style="margin-bottom:16px;color:#e94560;">Try it now</h2>
    {topic_cards}

    <h2 style="margin-top:36px;margin-bottom:16px;color:#e94560;">For AI Agents</h2>
    <pre>curl "{settings.api_host if settings.api_host != '0.0.0.0' else 'http://localhost'}:8000/api/v1/posts?topic=AI+video+tools&limit=20"</pre>

    <h2 style="margin-top:36px;margin-bottom:16px;color:#e94560;">Endpoints</h2>
    <div style="background:#1a1a2e;border-radius:12px;padding:20px;line-height:2;">
      <code>GET /api/v1/posts?topic=...&platform=...&sort=...&limit=...&days=...</code><br>
      <code>GET /api/v1/posts/{{post_id}}</code><br>
      <code>GET /api/v1/topics</code><br>
      <code>POST /api/v1/topics?name=...</code><br>
      <code>GET /api/v1/platforms</code><br>
      <code>GET /api/v1/health</code><br>
    </div>

    <h2 style="margin-top:36px;margin-bottom:16px;color:#e94560;">Sort options</h2>
    <div style="background:#1a1a2e;border-radius:12px;padding:20px;line-height:2;font-size:14px;">
      <code>composite</code> — weighted blend of relevance + engagement + velocity (default)<br>
      <code>engagement</code> — highest likes + comments + shares<br>
      <code>velocity</code> — fastest growing relative to post age<br>
      <code>relevance</code> — best keyword match<br>
      <code>recent</code> — newest first
    </div>

    <p style="margin-top:36px;color:#555;font-size:13px;">
      <a href="/docs">Swagger docs</a> &middot;
      Platforms: Reddit, TikTok, Instagram, YouTube &middot;
      Refreshed daily
    </p>
  </div>
</body>
</html>"""


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


def _get_thumbnail(post_id: str, platform: str, url: str, media_url: str) -> str:
    """Extract best thumbnail URL for a post. Only return URLs that won't hit login walls."""
    # YouTube thumbnails always work publicly
    if platform == "youtube" and "watch?v=" in url:
        vid = url.split("watch?v=")[1].split("&")[0]
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    # Reddit/Instagram/TikTok CDN thumbnails often expire or require auth — skip them
    return ""


def _get_embed_html(platform: str, url: str) -> str:
    """Generate embed HTML for video/content platforms."""
    if platform == "youtube" and "watch?v=" in url:
        vid = url.split("watch?v=")[1].split("&")[0]
        return f'<iframe width="100%" height="315" src="https://www.youtube.com/embed/{vid}" frameborder="0" allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture" allowfullscreen style="border-radius:8px;"></iframe>'
    if platform == "tiktok":
        return f'<blockquote class="tiktok-embed" cite="{url}" data-video-id="" style="max-width:100%;"><section></section></blockquote>'
    if platform == "instagram" and "/reel/" in url:
        shortcode = url.split("/reel/")[1].strip("/").split("/")[0].split("?")[0]
        return f'<iframe src="https://www.instagram.com/reel/{shortcode}/embed/" width="100%" height="480" frameborder="0" scrolling="no" allowtransparency="true" style="border-radius:8px;background:#000;"></iframe>'
    if platform == "reddit" and "reddit.com" in url:
        return f'<a href="{url}" target="_blank" style="display:block;background:#1a1a2e;border:1px solid #2d2d44;border-radius:8px;padding:14px 16px;text-decoration:none;color:#d1d5db;font-size:13px;margin-bottom:4px;"><span style="color:#FF4500;font-weight:600;">r/</span> Open on Reddit &#x2197;</a>'
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
        active = "background:#e94560;color:#fff;" if s == sort else "background:#1a1a2e;color:#aaa;"
        encoded_topic = topic.replace(" ", "+")
        plat_param = f"&platform={platform}" if platform else ""
        sort_options += f'<a href="/view/posts?topic={encoded_topic}{plat_param}&sort={s}&limit={limit}" style="{active}padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;border:1px solid #333;">{s}</a> '

    platform_filters = f'<a href="/view/posts?topic={topic.replace(" ", "+")}&sort={sort}&limit={limit}" style="{"background:#e94560;color:#fff;" if not platform else "background:#1a1a2e;color:#aaa;"}padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;border:1px solid #333;">All</a> '
    for p in ALL_PLATFORMS:
        active = "background:#e94560;color:#fff;" if p == platform else "background:#1a1a2e;color:#aaa;"
        label, color, _ = PLATFORM_ICONS.get(p, (p, "#888", ""))
        platform_filters += f'<a href="/view/posts?topic={topic.replace(" ", "+")}&platform={p}&sort={sort}&limit={limit}" style="{active}padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;border:1px solid #333;">{label}</a> '

    has_tiktok = False
    cards = ""
    for i, post in enumerate(result.posts):
        p_label, p_color, p_domain = PLATFORM_ICONS.get(post.platform, (post.platform, "#888", ""))
        score_pct = int(post.scores.composite * 100)
        score_bar_color = "#4ade80" if score_pct >= 70 else "#facc15" if score_pct >= 40 else "#f87171"

        content_preview = (post.content or "")[:280]
        if len(post.content or "") > 280:
            content_preview += "..."

        title_html = f'<div style="font-weight:600;font-size:15px;margin-bottom:6px;color:#fff;">{post.title}</div>' if post.title else ""

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
        if embed:
            media_html = f'<div style="margin-bottom:12px;">{embed}</div>'
        elif thumb:
            media_html = f'<a href="{post.url}" target="_blank"><img src="{thumb}" alt="" style="width:100%;max-height:360px;object-fit:cover;border-radius:8px;margin-bottom:12px;" loading="lazy" onerror="this.style.display=\'none\'"></a>'

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

        # Score bar helper
        def _score_bar(label, value, color, is_active=False):
            pct = int(value * 100)
            border = f"border:2px solid {color};" if is_active else "border:1px solid #1f2937;"
            glow = f"box-shadow:0 0 8px {color}44;" if is_active else ""
            return f'''<div style="flex:1;min-width:100px;background:#0d1117;border-radius:8px;padding:10px 12px;{border}{glow}">
              <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="color:#9ca3af;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;">{label}</span>
                <span style="color:{color};font-size:13px;font-weight:700;">{pct}</span>
              </div>
              <div style="height:4px;background:#1f2937;border-radius:2px;overflow:hidden;">
                <div style="width:{pct}%;height:100%;background:{color};border-radius:2px;"></div>
              </div>
            </div>'''

        rel_color = "#60a5fa"
        eng_color = "#a78bfa"
        vel_color = "#34d399"
        comp_color = score_bar_color

        scores_html = f'''
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;padding-top:12px;border-top:1px solid #1f2937;">
            {_score_bar("Composite", post.scores.composite, comp_color, sort == "composite")}
            {_score_bar("Relevance", post.scores.relevance, rel_color, sort == "relevance")}
            {_score_bar("Engagement", post.scores.engagement_normalized, eng_color, sort == "engagement")}
            {_score_bar("Velocity", post.scores.velocity, vel_color, sort == "velocity")}
          </div>'''

        # Raw engagement numbers grid
        eng_items = ""
        if post.engagement.views:
            eng_items += f'<div style="text-align:center;"><div style="color:#fff;font-size:16px;font-weight:700;">{_fmt_num(post.engagement.views)}</div><div style="color:#6b7280;font-size:11px;">Views</div></div>'
        if post.engagement.likes:
            eng_items += f'<div style="text-align:center;"><div style="color:#fff;font-size:16px;font-weight:700;">{_fmt_num(post.engagement.likes)}</div><div style="color:#6b7280;font-size:11px;">Likes</div></div>'
        if post.engagement.comments:
            eng_items += f'<div style="text-align:center;"><div style="color:#fff;font-size:16px;font-weight:700;">{_fmt_num(post.engagement.comments)}</div><div style="color:#6b7280;font-size:11px;">Comments</div></div>'
        if post.engagement.shares:
            eng_items += f'<div style="text-align:center;"><div style="color:#fff;font-size:16px;font-weight:700;">{_fmt_num(post.engagement.shares)}</div><div style="color:#6b7280;font-size:11px;">Shares</div></div>'
        if eng_rate:
            eng_items += f'<div style="text-align:center;"><div style="color:#fbbf24;font-size:16px;font-weight:700;">{eng_rate}</div><div style="color:#6b7280;font-size:11px;">Eng. Rate</div></div>'
        if age_str:
            eng_items += f'<div style="text-align:center;"><div style="color:#9ca3af;font-size:16px;font-weight:700;">{age_str}</div><div style="color:#6b7280;font-size:11px;">Posted</div></div>'

        metrics_html = f'''
          <div style="display:flex;gap:16px;flex-wrap:wrap;justify-content:space-around;margin-top:10px;padding:12px 8px;background:#0d1117;border-radius:8px;">
            {eng_items}
          </div>''' if eng_items else ""

        cards += f"""
        <div style="background:#111827;border:1px solid #1f2937;border-radius:12px;padding:20px;margin-bottom:20px;transition:border-color 0.2s;" onmouseover="this.style.borderColor='#374151'" onmouseout="this.style.borderColor='#1f2937'">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <span style="background:{p_color}22;color:{p_color};padding:4px 10px;border-radius:6px;font-size:12px;font-weight:600;">{p_label}</span>
              <a href="{post.author_url or '#'}" target="_blank" style="color:#9ca3af;font-size:13px;text-decoration:none;">{post.author}</a>
              <span style="color:#4b5563;font-size:12px;">{pub_date}</span>
              <span style="color:#4b5563;font-size:11px;">#{i + 1}</span>
            </div>
            <a href="{post.url}" target="_blank" style="color:#60a5fa;font-size:12px;text-decoration:none;white-space:nowrap;">View on {p_label} &#x2197;</a>
          </div>
          {title_html}
          {media_html}
          <p style="color:#d1d5db;font-size:14px;line-height:1.6;margin-bottom:0;">{content_preview}</p>
          {metrics_html}
          {scores_html}
        </div>"""

    tiktok_script = '<script async src="https://www.tiktok.com/embed.js"></script>' if has_tiktok else ""

    json_url = f"/api/v1/posts?topic={topic.replace(' ', '+')}"
    if platform:
        json_url += f"&platform={platform}"
    json_url += f"&sort={sort}&limit={limit}"

    return f"""<!DOCTYPE html>
<html>
<head>
  <title>{topic} — ViralPulse</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#0a0a1a; color:#e2e2e2; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; padding:32px 20px; }}
    .container {{ max-width:860px; margin:0 auto; }}
    a {{ color:#60a5fa; }}
  </style>
</head>
<body>
  <div class="container">
    <div style="margin-bottom:28px;">
      <a href="/" style="color:#6b7280;text-decoration:none;font-size:13px;">&larr; Back to topics</a>
      <h1 style="font-size:1.8em;margin-top:8px;">{topic}</h1>
      <p style="color:#6b7280;font-size:14px;margin-top:4px;">{result.count} posts &middot; sorted by {sort} &middot; <a href="{json_url}" style="font-size:13px;">JSON API</a></p>
    </div>

    <div style="margin-bottom:16px;">
      <div style="margin-bottom:8px;color:#9ca3af;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Platform</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;">{platform_filters}</div>
    </div>
    <div style="margin-bottom:24px;">
      <div style="margin-bottom:8px;color:#9ca3af;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Sort by</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;">{sort_options}</div>
    </div>

    {cards if cards else '<p style="color:#6b7280;padding:40px 0;text-align:center;">No posts found for this query.</p>'}
  </div>
  {tiktok_script}
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
