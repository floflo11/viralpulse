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
            <a href="/api/v1/posts?topic={encoded}&limit=5" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">Top 5 (all platforms)</a>
            <a href="/api/v1/posts?topic={encoded}&platform=tiktok&sort=engagement&limit=5" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">TikTok by engagement</a>
            <a href="/api/v1/posts?topic={encoded}&platform=reddit&sort=composite&limit=5" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">Reddit top composite</a>
            <a href="/api/v1/posts?topic={encoded}&platform=youtube&limit=5" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">YouTube top 5</a>
            <a href="/api/v1/posts?topic={encoded}&sort=velocity&limit=10" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">Fastest rising (velocity)</a>
            <a href="/api/v1/posts?topic={encoded}&sort=recent&limit=10" style="background:#0f3460;color:#e2e2e2;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;">Most recent</a>
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
