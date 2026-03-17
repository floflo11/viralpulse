"""Crawl orchestrator — fetches posts across all platforms for a topic."""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from viralpulse.config import settings
from viralpulse.platforms import CRAWLERS, ALL_PLATFORMS
from viralpulse.platforms.base import RawPost
from viralpulse.query import extract_core_subject
from viralpulse.scoring import compute_relevance, compute_velocity, normalize_engagement, compute_composite
from viralpulse.db import get_conn

logger = logging.getLogger("viralpulse.crawler")


def crawl_topic(
    topic: str,
    api_key: str = None,
    platforms: List[str] = None,
    max_results: int = 20,
) -> List[RawPost]:
    """Crawl all platforms for a topic. Returns collected RawPosts."""
    key = api_key or settings.scrapecreators_api_key
    target_platforms = platforms or ALL_PLATFORMS
    query = extract_core_subject(topic)
    all_posts = []

    for platform_name in target_platforms:
        crawler_cls = CRAWLERS.get(platform_name)
        if not crawler_cls:
            logger.warning(f"Unknown platform: {platform_name}")
            continue

        try:
            crawler = crawler_cls(api_key=key)
            posts = crawler.search(query, max_results=max_results)
            all_posts.extend(posts)
            logger.info(f"[{platform_name}] Found {len(posts)} posts for '{query}'")
        except Exception as e:
            logger.error(f"[{platform_name}] Error: {e}")

    return all_posts


def store_crawl_results(
    topic_id: str,
    posts: List[RawPost],
    topic_name: str,
    db_url: str = None,
):
    """Store crawled posts in the database with scoring."""
    conn = get_conn(db_url)
    now = datetime.now(timezone.utc).isoformat()

    new_count = 0
    updated_count = 0

    for post in posts:
        if not post.url:
            continue

        existing = conn.execute(
            "SELECT id FROM posts WHERE url = %s", (post.url,)
        ).fetchone()

        if existing:
            post_id = existing["id"]
            updated_count += 1
        else:
            row = conn.execute(
                """INSERT INTO posts (topic_id, platform, platform_id, url, author, author_url,
                   title, content, media_url, published_at, fetched_at, raw_data)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (topic_id, post.platform, post.platform_id, post.url,
                 post.author, post.author_url, post.title, post.content,
                 post.media_url, post.published_at, now,
                 json.dumps(post.raw_data, default=str)),
            ).fetchone()
            post_id = row["id"]
            new_count += 1

        # Add engagement snapshot
        conn.execute(
            """INSERT INTO engagement (post_id, snapshot_at, likes, comments, shares, views, platform_score)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (post_id, now, post.likes, post.comments, post.shares, post.views, post.platform_score),
        )

    conn.commit()

    # Recompute scores for all posts in this topic
    _recompute_scores(topic_id, topic_name, conn)
    conn.commit()
    conn.close()

    return {"new": new_count, "updated": updated_count}


def _recompute_scores(topic_id: str, topic_name: str, conn):
    """Recompute relevance, engagement, velocity, composite for all posts in a topic."""
    posts = conn.execute(
        """SELECT p.id, p.content, p.title, p.published_at,
                  e.likes, e.comments, e.shares, e.views
           FROM posts p
           LEFT JOIN LATERAL (
               SELECT * FROM engagement WHERE post_id = p.id ORDER BY snapshot_at DESC LIMIT 1
           ) e ON true
           WHERE p.topic_id = %s""",
        (topic_id,),
    ).fetchall()

    if not posts:
        return

    now = datetime.now(timezone.utc)

    relevances = []
    velocities = []
    engagement_totals = []

    for p in posts:
        text = f"{p.get('title') or ''} {p.get('content') or ''}"
        rel = compute_relevance(topic_name, text)
        relevances.append(rel)

        total_engagement = (p.get("likes") or 0) + (p.get("comments") or 0) + (p.get("shares") or 0)
        engagement_totals.append(float(total_engagement))

        hours_old = 24.0
        if p.get("published_at"):
            try:
                pub = datetime.fromisoformat(str(p["published_at"]))
                hours_old = max((now - pub).total_seconds() / 3600, 0.1)
            except (ValueError, TypeError):
                pass
        velocities.append(compute_velocity(total_engagement, hours_old))

    norm_engagement = normalize_engagement(engagement_totals)
    norm_velocity = normalize_engagement(velocities)

    for i, p in enumerate(posts):
        composite = compute_composite(relevances[i], norm_engagement[i], norm_velocity[i])
        conn.execute(
            """INSERT INTO scores (post_id, relevance, engagement_normalized, velocity, composite)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (post_id) DO UPDATE SET
                   relevance = EXCLUDED.relevance,
                   engagement_normalized = EXCLUDED.engagement_normalized,
                   velocity = EXCLUDED.velocity,
                   composite = EXCLUDED.composite""",
            (p["id"], relevances[i], norm_engagement[i], norm_velocity[i], composite),
        )


def run_full_crawl(db_url: str = None, api_key: str = None):
    """Crawl all enabled topics across all platforms."""
    conn = get_conn(db_url)
    topics = conn.execute("SELECT id, name FROM topics WHERE enabled = TRUE").fetchall()
    conn.close()

    results = []
    for topic in topics:
        logger.info(f"Crawling topic: {topic['name']}")
        posts = crawl_topic(topic["name"], api_key=api_key)
        counts = store_crawl_results(str(topic["id"]), posts, topic["name"], db_url=db_url)
        results.append({"topic": topic["name"], **counts})
        logger.info(f"  -> {counts['new']} new, {counts['updated']} updated")

    return results
