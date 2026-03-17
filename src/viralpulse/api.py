"""FastAPI application — serves viral post data to AI agents and dashboards."""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

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
