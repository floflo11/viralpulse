"""CLI for topic management and manual crawling."""

import argparse
import json
import logging
import sys
import time

from viralpulse.config import settings
from viralpulse.db import get_conn, init_db
from viralpulse.crawler import crawl_topic, store_crawl_results, run_full_crawl

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("viralpulse")


def cmd_topic_add(args):
    init_db()
    conn = get_conn()
    queries = [q.strip() for q in args.queries.split(",")] if args.queries else [args.name]
    row = conn.execute(
        """INSERT INTO topics (name, search_queries) VALUES (%s, %s)
           ON CONFLICT (name) DO UPDATE SET search_queries = EXCLUDED.search_queries, updated_at = now()
           RETURNING *""",
        (args.name, json.dumps(queries)),
    ).fetchone()
    conn.commit()
    conn.close()
    print(f"Added topic: {row['name']} (id: {row['id']})")


def cmd_topic_list(args):
    init_db()
    conn = get_conn()
    rows = conn.execute(
        """SELECT t.*, COUNT(p.id) as post_count
           FROM topics t LEFT JOIN posts p ON p.topic_id = t.id
           GROUP BY t.id ORDER BY t.name"""
    ).fetchall()
    conn.close()

    if not rows:
        print("No topics. Add one with: viralpulse topic add \"Your Topic\"")
        return

    print(f"{'Topic':<30} {'Posts':<8} {'Enabled':<8}")
    print("-" * 50)
    for r in rows:
        print(f"{r['name']:<30} {r['post_count']:<8} {'yes' if r['enabled'] else 'no':<8}")


def cmd_topic_remove(args):
    init_db()
    conn = get_conn()
    row = conn.execute("DELETE FROM topics WHERE name = %s RETURNING name", (args.name,)).fetchone()
    conn.commit()
    conn.close()
    if row:
        print(f"Removed topic: {row['name']}")
    else:
        print(f"Topic not found: {args.name}")


def cmd_crawl(args):
    init_db()
    if not settings.scrapecreators_api_key:
        print("Error: SCRAPECREATORS_API_KEY not set in .env")
        sys.exit(1)

    if args.topic:
        conn = get_conn()
        topic_row = conn.execute("SELECT id, name FROM topics WHERE name = %s", (args.topic,)).fetchone()
        conn.close()
        if not topic_row:
            print(f"Topic not found: {args.topic}")
            sys.exit(1)

        print(f"Crawling: {topic_row['name']}")
        start = time.time()
        posts = crawl_topic(topic_row["name"])
        counts = store_crawl_results(str(topic_row["id"]), posts, topic_row["name"])
        duration = time.time() - start
        print(f"Done in {duration:.1f}s — {counts['new']} new, {counts['updated']} updated")
    else:
        print("Crawling all enabled topics...")
        start = time.time()
        results = run_full_crawl()
        duration = time.time() - start
        for r in results:
            print(f"  {r['topic']}: {r['new']} new, {r['updated']} updated")
        print(f"\nDone in {duration:.1f}s")


def cmd_status(args):
    init_db()
    conn = get_conn()
    topic_count = conn.execute("SELECT COUNT(*) as c FROM topics WHERE enabled = TRUE").fetchone()["c"]
    post_count = conn.execute("SELECT COUNT(*) as c FROM posts").fetchone()["c"]
    conn.close()
    print(f"Topics: {topic_count}")
    print(f"Posts:  {post_count}")
    print(f"API key: {'set' if settings.scrapecreators_api_key else 'NOT SET'}")
    print(f"DB:      {'connected' if settings.database_url else 'NOT SET'}")


def cmd_profile_add(args):
    init_db()
    conn = get_conn()
    handle = args.handle.lstrip("@")
    row = conn.execute(
        """INSERT INTO profiles (platform, handle) VALUES (%s, %s)
           ON CONFLICT (platform, handle) DO UPDATE SET updated_at = now()
           RETURNING *""",
        (args.platform, handle),
    ).fetchone()
    conn.commit()
    conn.close()
    print(f"Tracking @{handle} on {args.platform}")


def cmd_profile_list(args):
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM profiles ORDER BY platform, handle").fetchall()
    conn.close()
    if not rows:
        print("No profiles tracked. Add one: viralpulse profile add twitter OpenAI")
        return
    print(f"{'Platform':<12} {'Handle':<20} {'Enabled':<8}")
    print("-" * 42)
    for r in rows:
        print(f"{r['platform']:<12} @{r['handle']:<19} {'yes' if r['enabled'] else 'no':<8}")


def cmd_profile_crawl(args):
    init_db()
    handle = args.handle.lstrip("@")
    if not settings.scrapecreators_api_key:
        print("Error: SCRAPECREATORS_API_KEY not set")
        sys.exit(1)

    print(f"Crawling @{handle} on {args.platform}...")
    start = time.time()
    posts = []

    if args.platform == "twitter":
        from viralpulse.platforms.x_profile import XProfileCrawler
        crawler = XProfileCrawler(settings.scrapecreators_api_key)
        posts = crawler.fetch_user_posts(handle)
    elif args.platform == "instagram":
        from viralpulse.platforms.instagram_profile import InstagramProfileCrawler
        crawler = InstagramProfileCrawler(settings.scrapecreators_api_key)
        posts = crawler.fetch_user_posts(handle)

    if posts:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn = get_conn()
        new = 0
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
                new += 1
        conn.commit()
        conn.close()
        duration = time.time() - start
        print(f"Done in {duration:.1f}s — {new} new posts, {len(posts) - new} existing")
    else:
        print("No posts found")


def cmd_serve(args):
    import uvicorn
    uvicorn.run("viralpulse.api:app", host=args.host, port=args.port, reload=args.reload)


def main():
    parser = argparse.ArgumentParser(prog="viralpulse", description="ViralPulse — viral social media post aggregator")
    sub = parser.add_subparsers(dest="command")

    # topic subcommands
    topic_parser = sub.add_parser("topic", help="Manage topics")
    topic_sub = topic_parser.add_subparsers(dest="topic_command")

    add_p = topic_sub.add_parser("add", help="Add a topic")
    add_p.add_argument("name", help="Topic name")
    add_p.add_argument("--queries", default="", help="Comma-separated search queries")
    add_p.set_defaults(func=cmd_topic_add)

    list_p = topic_sub.add_parser("list", help="List topics")
    list_p.set_defaults(func=cmd_topic_list)

    rm_p = topic_sub.add_parser("remove", help="Remove a topic")
    rm_p.add_argument("name", help="Topic name")
    rm_p.set_defaults(func=cmd_topic_remove)

    # profile subcommands
    profile_parser = sub.add_parser("profile", help="Track profiles")
    profile_sub = profile_parser.add_subparsers(dest="profile_command")

    add_prof = profile_sub.add_parser("add", help="Track a profile")
    add_prof.add_argument("platform", choices=["twitter", "instagram"])
    add_prof.add_argument("handle", help="Username/handle")
    add_prof.set_defaults(func=cmd_profile_add)

    list_prof = profile_sub.add_parser("list", help="List tracked profiles")
    list_prof.set_defaults(func=cmd_profile_list)

    crawl_prof = profile_sub.add_parser("crawl", help="Crawl a profile")
    crawl_prof.add_argument("platform", choices=["twitter", "instagram"])
    crawl_prof.add_argument("handle")
    crawl_prof.set_defaults(func=cmd_profile_crawl)

    # crawl
    crawl_p = sub.add_parser("crawl", help="Run crawler")
    crawl_p.add_argument("--topic", help="Crawl specific topic (default: all)")
    crawl_p.set_defaults(func=cmd_crawl)

    # status
    status_p = sub.add_parser("status", help="Show status")
    status_p.set_defaults(func=cmd_status)

    # serve
    serve_p = sub.add_parser("serve", help="Start API server")
    serve_p.add_argument("--host", default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.add_argument("--reload", action="store_true")
    serve_p.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "topic" and not getattr(args, "topic_command", None):
        topic_parser.print_help()
        sys.exit(1)

    if args.command == "profile" and not getattr(args, "profile_command", None):
        profile_parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
