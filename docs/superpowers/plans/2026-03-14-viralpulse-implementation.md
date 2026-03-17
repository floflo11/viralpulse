# ViralPulse Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a data API that crawls 6 social media platforms daily via ScrapeCreators, stores top posts in Neon PostgreSQL, and serves them via FastAPI for AI agents and a Next.js dashboard for humans.

**Architecture:** Decoupled crawler (Python on VM, daily cron) writes to Neon Postgres. FastAPI on Modal serves the API. Next.js on Vercel serves the dashboard. All platform data comes from ScrapeCreators (one API key).

**Tech Stack:** Python 3.11+, uv, FastAPI, psycopg, Neon PostgreSQL, ScrapeCreators API, Modal (API hosting), Vercel + Next.js (dashboard)

---

## File Structure

```
viralpulse/
├── pyproject.toml                    # uv project config
├── .env.example                      # template for required env vars
├── src/
│   └── viralpulse/
│       ├── __init__.py
│       ├── config.py                 # env loading, settings
│       ├── db.py                     # Neon Postgres connection + migrations
│       ├── models.py                 # Pydantic models for posts, topics, scores
│       ├── scoring.py                # relevance, engagement, velocity, composite scoring
│       ├── query.py                  # query expansion + core subject extraction
│       ├── platforms/
│       │   ├── __init__.py
│       │   ├── base.py              # abstract platform crawler interface
│       │   ├── twitter.py           # X/Twitter via ScrapeCreators
│       │   ├── reddit.py            # Reddit via ScrapeCreators
│       │   ├── tiktok.py            # TikTok via ScrapeCreators
│       │   ├── instagram.py         # Instagram via ScrapeCreators
│       │   ├── linkedin.py          # LinkedIn via ScrapeCreators
│       │   └── youtube.py           # YouTube via ScrapeCreators
│       ├── crawler.py               # orchestrates crawl across all platforms
│       ├── api.py                   # FastAPI app with all endpoints
│       └── cli.py                   # CLI for topic management + manual crawl
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # shared fixtures, test DB
│   ├── test_scoring.py
│   ├── test_query.py
│   ├── test_platforms.py
│   ├── test_crawler.py
│   ├── test_api.py
│   └── fixtures/                    # sample ScrapeCreators responses
│       ├── twitter_search.json
│       ├── reddit_search.json
│       ├── tiktok_search.json
│       ├── instagram_search.json
│       ├── linkedin_search.json
│       └── youtube_search.json
└── dashboard/                       # Next.js app (Task 8)
    └── (created later)
```

---

## Chunk 1: Foundation (Tasks 1-3)

### Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/viralpulse/__init__.py`
- Create: `src/viralpulse/config.py`

- [ ] **Step 1: Initialize uv project**

```bash
cd /home/iris/viralpulse
uv init --lib --name viralpulse
```

- [ ] **Step 2: Add dependencies**

```bash
uv add fastapi uvicorn psycopg[binary] httpx pydantic pydantic-settings python-dotenv
uv add --dev pytest pytest-asyncio httpx
```

- [ ] **Step 3: Create .env.example**

```
SCRAPECREATORS_API_KEY=
DATABASE_URL=postgresql://user:pass@host/dbname
```

- [ ] **Step 4: Write config.py**

```python
"""Environment configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    scrapecreators_api_key: str = ""
    database_url: str = ""
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 5: Create __init__.py**

```python
"""ViralPulse — viral social media post aggregator."""
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .env.example src/
git commit -m "feat: project setup with uv, config, dependencies"
```

---

### Task 2: Database Schema + Migrations

**Files:**
- Create: `src/viralpulse/db.py`
- Create: `tests/conftest.py`
- Create: `tests/__init__.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write test for DB initialization**

```python
# tests/test_db.py
import pytest
from viralpulse.db import init_db, get_pool


@pytest.mark.asyncio
async def test_init_db_creates_tables(test_db_url):
    pool = await get_pool(test_db_url)
    await init_db(pool)
    async with pool.acquire() as conn:
        # Check all tables exist
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        table_names = {r["tablename"] for r in tables}
        assert "topics" in table_names
        assert "posts" in table_names
        assert "engagement" in table_names
        assert "scores" in table_names
    await pool.close()
```

- [ ] **Step 2: Write db.py with schema**

```python
"""Database connection and schema management."""

import psycopg
from psycopg.rows import dict_row
from contextlib import asynccontextmanager
from viralpulse.config import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    search_queries JSONB DEFAULT '[]'::jsonb,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    platform_id TEXT,
    url TEXT UNIQUE NOT NULL,
    author TEXT DEFAULT '',
    author_url TEXT,
    title TEXT,
    content TEXT DEFAULT '',
    media_url TEXT,
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ DEFAULT now(),
    raw_data JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_posts_topic_platform ON posts(topic_id, platform);
CREATE INDEX IF NOT EXISTS idx_posts_url ON posts(url);

CREATE TABLE IF NOT EXISTS engagement (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
    snapshot_at TIMESTAMPTZ DEFAULT now(),
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    views INTEGER DEFAULT 0,
    platform_score INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_engagement_post ON engagement(post_id, snapshot_at DESC);

CREATE TABLE IF NOT EXISTS scores (
    post_id UUID PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
    relevance FLOAT DEFAULT 0,
    engagement_normalized FLOAT DEFAULT 0,
    velocity FLOAT DEFAULT 0,
    composite FLOAT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_scores_composite ON scores(composite DESC);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ,
    posts_new INTEGER DEFAULT 0,
    posts_updated INTEGER DEFAULT 0,
    error TEXT,
    status TEXT DEFAULT 'running'
);
"""


def get_conn(db_url: str = None):
    """Get a sync connection."""
    url = db_url or settings.database_url
    return psycopg.connect(url, row_factory=dict_row)


def init_db(db_url: str = None):
    """Create tables if they don't exist."""
    with get_conn(db_url) as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()
```

- [ ] **Step 3: Write conftest.py with test DB fixture**

```python
# tests/conftest.py
import os
import pytest
from viralpulse.db import get_conn, init_db

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "")
)

@pytest.fixture
def db():
    """Provide a test DB connection with clean tables."""
    if not TEST_DB_URL:
        pytest.skip("No DATABASE_URL set")
    init_db(TEST_DB_URL)
    conn = get_conn(TEST_DB_URL)
    # Clean tables before each test
    conn.execute("DELETE FROM crawl_runs")
    conn.execute("DELETE FROM scores")
    conn.execute("DELETE FROM engagement")
    conn.execute("DELETE FROM posts")
    conn.execute("DELETE FROM topics")
    conn.commit()
    yield conn
    conn.close()
```

- [ ] **Step 4: Run test to verify**

```bash
cd /home/iris/viralpulse
uv run pytest tests/test_db.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/viralpulse/db.py tests/
git commit -m "feat: database schema with topics, posts, engagement, scores tables"
```

---

### Task 3: Pydantic Models

**Files:**
- Create: `src/viralpulse/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write test for models**

```python
# tests/test_models.py
from viralpulse.models import Post, Topic, Engagement, Scores, PostResponse


def test_post_response_serialization():
    post = PostResponse(
        id="abc-123",
        platform="twitter",
        url="https://x.com/user/status/123",
        author="@user",
        author_url="https://x.com/user",
        title=None,
        content="Great post",
        media_url=None,
        published_at="2026-03-12T14:30:00Z",
        engagement=Engagement(likes=100, comments=10, shares=5, views=1000, platform_score=0),
        scores=Scores(relevance=0.8, engagement_normalized=0.9, velocity=0.7, composite=0.85),
    )
    d = post.model_dump()
    assert d["platform"] == "twitter"
    assert d["scores"]["composite"] == 0.85


def test_topic_model():
    topic = Topic(id="abc", name="AI video tools", search_queries=["ai video", "ai video editing"])
    assert topic.name == "AI video tools"
    assert len(topic.search_queries) == 2
```

- [ ] **Step 2: Write models.py**

```python
"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class Engagement(BaseModel):
    likes: int = 0
    comments: int = 0
    shares: int = 0
    views: int = 0
    platform_score: int = 0


class Scores(BaseModel):
    relevance: float = 0.0
    engagement_normalized: float = 0.0
    velocity: float = 0.0
    composite: float = 0.0


class PostResponse(BaseModel):
    id: str
    platform: str
    url: str
    author: str
    author_url: Optional[str] = None
    title: Optional[str] = None
    content: str
    media_url: Optional[str] = None
    published_at: Optional[str] = None
    engagement: Engagement
    scores: Scores


class PostsListResponse(BaseModel):
    topic: str
    platform: str
    sort: str
    count: int
    fetched_at: str
    posts: List[PostResponse]


class Topic(BaseModel):
    id: str
    name: str
    search_queries: List[str] = []
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TopicCreate(BaseModel):
    name: str
    search_queries: List[str] = []


class PlatformStatus(BaseModel):
    name: str
    enabled: bool = True
    last_crawl: Optional[str] = None
    post_count: int = 0


class CrawlResult(BaseModel):
    topic: str
    platform: str
    posts_new: int = 0
    posts_updated: int = 0
    error: Optional[str] = None
    duration_seconds: float = 0.0
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_models.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/models.py tests/test_models.py
git commit -m "feat: pydantic models for posts, topics, engagement, scores"
```

---

## Chunk 2: Query + Scoring (Tasks 4-5)

### Task 4: Query Expansion

**Files:**
- Create: `src/viralpulse/query.py`
- Create: `tests/test_query.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_query.py
from viralpulse.query import extract_core_subject, expand_queries


def test_extract_strips_noise():
    assert extract_core_subject("what are the best AI video tools") == "AI video tools"
    assert extract_core_subject("tips for prompt engineering") == "prompt engineering"


def test_extract_preserves_core():
    assert extract_core_subject("Claude Code") == "Claude Code"
    assert extract_core_subject("Remotion") == "Remotion"


def test_expand_queries():
    queries = expand_queries("AI video tools")
    assert len(queries) >= 1
    assert "AI video tools" in queries
```

- [ ] **Step 2: Write query.py**

Adapted from last30days patterns — strips meta/noise words, generates query variants.

```python
"""Query expansion and core subject extraction."""

import re
from typing import List, Set

NOISE_WORDS = frozenset({
    'best', 'top', 'good', 'great', 'awesome', 'killer',
    'latest', 'new', 'news', 'update', 'updates',
    'trending', 'hottest', 'popular', 'viral',
    'practices', 'features', 'tips',
    'recommendations', 'advice',
    'prompt', 'prompts', 'prompting',
    'methods', 'strategies', 'approaches',
})

PREFIXES = [
    'what are the best', 'what is the best', 'what are the latest',
    'what are people saying about', 'what do people think about',
    'how do i use', 'how to use', 'how to',
    'what are', 'what is', 'tips for', 'best practices for',
]

STOPWORDS = frozenset({
    'the', 'a', 'an', 'to', 'for', 'how', 'is', 'in', 'of', 'on',
    'and', 'with', 'from', 'by', 'at', 'this', 'that', 'it', 'my',
    'your', 'i', 'me', 'we', 'you', 'what', 'are', 'do', 'can',
    'its', 'be', 'or', 'not', 'no', 'so', 'if', 'but', 'about',
    'all', 'just', 'get', 'has', 'have', 'was', 'will',
})

SYNONYMS = {
    'js': {'javascript'}, 'javascript': {'js'},
    'ts': {'typescript'}, 'typescript': {'ts'},
    'ai': {'artificial', 'intelligence'},
    'ml': {'machine', 'learning'},
    'react': {'reactjs'}, 'reactjs': {'react'},
}


def extract_core_subject(topic: str) -> str:
    """Strip meta/research words, keep core product/concept name."""
    text = topic.strip()
    text_lower = text.lower()

    for p in PREFIXES:
        if text_lower.startswith(p + ' '):
            text = text[len(p):].strip()
            break

    words = text.split()
    filtered = [w for w in words if w.lower() not in NOISE_WORDS]
    result = ' '.join(filtered) if filtered else text
    return result.rstrip('?!.')


def tokenize(text: str) -> Set[str]:
    """Lowercase, strip punctuation, remove stopwords, expand synonyms."""
    words = re.sub(r'[^\w\s]', ' ', text.lower()).split()
    tokens = {w for w in words if w not in STOPWORDS and len(w) > 1}
    expanded = set(tokens)
    for t in tokens:
        if t in SYNONYMS:
            expanded.update(SYNONYMS[t])
    return expanded


def expand_queries(topic: str) -> List[str]:
    """Generate search query variants from a topic."""
    core = extract_core_subject(topic)
    queries = [core]

    original = topic.strip().rstrip('?!.')
    if core.lower() != original.lower() and len(original.split()) <= 8:
        queries.append(original)

    queries.append(f"{core} worth it OR thoughts OR review")
    return queries
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_query.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/query.py tests/test_query.py
git commit -m "feat: query expansion and core subject extraction"
```

---

### Task 5: Scoring Engine

**Files:**
- Create: `src/viralpulse/scoring.py`
- Create: `tests/test_scoring.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_scoring.py
from viralpulse.scoring import compute_relevance, compute_velocity, normalize_engagement, compute_composite


def test_relevance_exact_match():
    score = compute_relevance("AI video tools", "This AI video tool is amazing for editing")
    assert score > 0.5


def test_relevance_no_match():
    score = compute_relevance("AI video tools", "Best pizza recipes in New York")
    assert score < 0.3


def test_velocity_newer_is_faster():
    # Post from 1 hour ago with 100 likes vs 24 hours ago with 100 likes
    v1 = compute_velocity(likes=100, hours_old=1)
    v2 = compute_velocity(likes=100, hours_old=24)
    assert v1 > v2


def test_normalize_engagement():
    values = [10, 50, 100, 500, 1000]
    normalized = normalize_engagement(values)
    assert len(normalized) == 5
    assert all(0 <= v <= 1 for v in normalized)
    assert normalized[-1] == 1.0  # max gets 1.0


def test_composite_weighted():
    score = compute_composite(relevance=1.0, engagement=1.0, velocity=1.0)
    assert score == 1.0

    score2 = compute_composite(relevance=0.0, engagement=0.0, velocity=0.0)
    assert score2 == 0.0
```

- [ ] **Step 2: Write scoring.py**

```python
"""Scoring engine: relevance, engagement normalization, velocity, composite."""

import math
from typing import List, Optional, Set

from viralpulse.query import tokenize


def compute_relevance(query: str, text: str, hashtags: List[str] = None) -> float:
    """Bidirectional token overlap between query and text. Returns 0-1."""
    q_tokens = tokenize(query)
    combined = text
    if hashtags:
        combined = f"{text} {' '.join(hashtags)}"
    t_tokens = tokenize(combined)

    if not q_tokens:
        return 0.5

    overlap = len(q_tokens & t_tokens)
    ratio = overlap / len(q_tokens)
    return max(0.1, min(1.0, ratio))


def compute_velocity(likes: int = 0, hours_old: float = 1.0) -> float:
    """Engagement per hour. Higher = faster growing content."""
    hours = max(hours_old, 0.1)  # avoid division by zero
    return likes / hours


def normalize_engagement(values: List[float]) -> List[float]:
    """Percentile normalization: map values to 0-1 range."""
    if not values:
        return []
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return [0.5] * len(values)
    return [(v - min_v) / (max_v - min_v) for v in values]


def compute_composite(
    relevance: float,
    engagement: float,
    velocity: float,
    weights: tuple = (0.3, 0.4, 0.3),
) -> float:
    """Weighted composite score. Default: 30% relevance, 40% engagement, 30% velocity."""
    w_r, w_e, w_v = weights
    return round(w_r * relevance + w_e * engagement + w_v * velocity, 4)
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_scoring.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/scoring.py tests/test_scoring.py
git commit -m "feat: scoring engine with relevance, velocity, engagement normalization"
```

---

## Chunk 3: Platform Crawlers (Tasks 6-7)

### Task 6: Platform Crawlers — Base + All 6 Platforms

**Files:**
- Create: `src/viralpulse/platforms/__init__.py`
- Create: `src/viralpulse/platforms/base.py`
- Create: `src/viralpulse/platforms/twitter.py`
- Create: `src/viralpulse/platforms/reddit.py`
- Create: `src/viralpulse/platforms/tiktok.py`
- Create: `src/viralpulse/platforms/instagram.py`
- Create: `src/viralpulse/platforms/linkedin.py`
- Create: `src/viralpulse/platforms/youtube.py`
- Create: `tests/test_platforms.py`
- Create: `tests/fixtures/twitter_search.json`
- Create: `tests/fixtures/reddit_search.json`
- Create: `tests/fixtures/tiktok_search.json`
- Create: `tests/fixtures/instagram_search.json`
- Create: `tests/fixtures/linkedin_search.json`
- Create: `tests/fixtures/youtube_search.json`

- [ ] **Step 1: Write base.py — abstract crawler interface**

```python
"""Abstract base for platform crawlers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RawPost:
    """Normalized post from any platform."""
    platform: str
    platform_id: str
    url: str
    author: str
    author_url: Optional[str]
    title: Optional[str]
    content: str
    media_url: Optional[str]
    published_at: Optional[str]  # ISO 8601
    likes: int = 0
    comments: int = 0
    shares: int = 0
    views: int = 0
    platform_score: int = 0
    hashtags: List[str] = None
    raw_data: Dict[str, Any] = None

    def __post_init__(self):
        if self.hashtags is None:
            self.hashtags = []
        if self.raw_data is None:
            self.raw_data = {}


class PlatformCrawler(ABC):
    """Abstract base for platform crawlers. All use ScrapeCreators."""

    PLATFORM: str = ""
    BASE_URL: str = "https://api.scrapecreators.com"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
        }

    @abstractmethod
    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        """Search platform for posts matching query. Returns normalized RawPosts."""
        ...
```

- [ ] **Step 2: Write twitter.py**

ScrapeCreators endpoint: `GET /v1/twitter/search/tweets?query=...&sort_by=relevance`
Auth header: `x-api-key`
Response: `{"tweets": [...]}`

```python
"""X/Twitter crawler via ScrapeCreators."""

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PlatformCrawler, RawPost


class TwitterCrawler(PlatformCrawler):
    PLATFORM = "twitter"
    BASE_URL = "https://api.scrapecreators.com/v1/twitter"

    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/search/tweets",
            params={"query": query, "sort_by": "relevance"},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_items = data.get("tweets") or data.get("data") or data.get("results") or []
        raw_items = raw_items[:max_results]

        posts = []
        for raw in raw_items:
            tweet_id = str(raw.get("id") or raw.get("tweet_id") or raw.get("id_str") or "")
            text = raw.get("full_text") or raw.get("text") or ""
            user = raw.get("user") or raw.get("author") or {}
            screen_name = user.get("screen_name") or user.get("username") or ""

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=tweet_id,
                url=f"https://x.com/{screen_name}/status/{tweet_id}" if screen_name and tweet_id else "",
                author=f"@{screen_name}" if screen_name else "",
                author_url=f"https://x.com/{screen_name}" if screen_name else None,
                title=None,
                content=text,
                media_url=None,
                published_at=self._parse_date(raw),
                likes=raw.get("favorite_count") or raw.get("likes") or 0,
                comments=raw.get("reply_count") or raw.get("replies") or 0,
                shares=raw.get("retweet_count") or raw.get("reposts") or 0,
                views=raw.get("views_count") or raw.get("views") or 0,
                raw_data=raw,
            ))
        return posts

    def _parse_date(self, item: Dict[str, Any]) -> Optional[str]:
        created_at = item.get("created_at")
        if created_at and isinstance(created_at, str):
            try:
                dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                return dt.isoformat()
            except (ValueError, TypeError):
                pass
        ts = item.get("timestamp") or item.get("created_at_timestamp")
        if ts:
            try:
                return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
            except (ValueError, TypeError, OSError):
                pass
        return None
```

- [ ] **Step 3: Write reddit.py**

ScrapeCreators endpoint: `GET /v1/reddit/search?query=...&sort=relevance&timeframe=month`
Response: `{"posts": [...]}`

```python
"""Reddit crawler via ScrapeCreators."""

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PlatformCrawler, RawPost


class RedditCrawler(PlatformCrawler):
    PLATFORM = "reddit"
    BASE_URL = "https://api.scrapecreators.com/v1/reddit"

    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/search",
            params={"query": query, "sort": "relevance", "timeframe": "month"},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_items = data.get("posts") or data.get("data") or []
        raw_items = raw_items[:max_results]

        posts = []
        for raw in raw_items:
            permalink = raw.get("permalink", "")
            url = f"https://www.reddit.com{permalink}" if permalink else ""
            author = raw.get("author", "")

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=raw.get("id", ""),
                url=url,
                author=author,
                author_url=f"https://www.reddit.com/user/{author}" if author else None,
                title=raw.get("title", ""),
                content=raw.get("selftext", "")[:2000],
                media_url=raw.get("thumbnail") if raw.get("thumbnail", "").startswith("http") else None,
                published_at=self._parse_date(raw.get("created_utc")),
                likes=raw.get("ups") or raw.get("score", 0),
                comments=raw.get("num_comments", 0),
                shares=0,
                views=0,
                platform_score=raw.get("score", 0),
                raw_data=raw,
            ))
        return posts

    def _parse_date(self, created_utc) -> Optional[str]:
        if not created_utc:
            return None
        try:
            return datetime.fromtimestamp(float(created_utc), tz=timezone.utc).isoformat()
        except (ValueError, TypeError, OSError):
            return None
```

- [ ] **Step 4: Write tiktok.py**

ScrapeCreators endpoint: `GET /v1/tiktok/search/keyword?query=...&sort_by=relevance`
Response: `{"search_item_list": [{"aweme_info": {...}}]}`

```python
"""TikTok crawler via ScrapeCreators."""

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PlatformCrawler, RawPost


class TikTokCrawler(PlatformCrawler):
    PLATFORM = "tiktok"
    BASE_URL = "https://api.scrapecreators.com/v1/tiktok"

    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/search/keyword",
            params={"query": query, "sort_by": "relevance"},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_entries = data.get("search_item_list") or data.get("data") or []
        raw_items = []
        for entry in raw_entries:
            if isinstance(entry, dict):
                raw_items.append(entry.get("aweme_info", entry))
        raw_items = raw_items[:max_results]

        posts = []
        for raw in raw_items:
            video_id = str(raw.get("aweme_id", ""))
            text = raw.get("desc", "")
            stats = raw.get("statistics") or {}
            author_info = raw.get("author") or {}
            username = author_info.get("unique_id", "")
            share_url = raw.get("share_url", "").split("?")[0]
            url = share_url or (f"https://www.tiktok.com/@{username}/video/{video_id}" if username and video_id else "")

            text_extra = raw.get("text_extra") or []
            hashtags = [t.get("hashtag_name", "") for t in text_extra
                        if isinstance(t, dict) and t.get("hashtag_name")]

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=video_id,
                url=url,
                author=f"@{username}" if username else "",
                author_url=f"https://www.tiktok.com/@{username}" if username else None,
                title=None,
                content=text,
                media_url=None,
                published_at=self._parse_date(raw),
                likes=stats.get("digg_count", 0),
                comments=stats.get("comment_count", 0),
                shares=stats.get("share_count", 0),
                views=stats.get("play_count", 0),
                hashtags=hashtags,
                raw_data=raw,
            ))
        return posts

    def _parse_date(self, item: Dict[str, Any]) -> Optional[str]:
        ts = item.get("create_time")
        if ts:
            try:
                return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
            except (ValueError, TypeError, OSError):
                pass
        return None
```

- [ ] **Step 5: Write instagram.py**

ScrapeCreators endpoint: `GET /v1/instagram/reels/search?query=...`
Response: `{"reels": [...]}`

```python
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
```

- [ ] **Step 6: Write linkedin.py**

ScrapeCreators endpoint: `GET /v1/linkedin/search?query=...` (inferred from their platform list — same pattern as others)

```python
"""LinkedIn crawler via ScrapeCreators."""

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PlatformCrawler, RawPost


class LinkedInCrawler(PlatformCrawler):
    PLATFORM = "linkedin"
    BASE_URL = "https://api.scrapecreators.com/v1/linkedin"

    def search(self, query: str, max_results: int = 20) -> List[RawPost]:
        resp = httpx.get(
            f"{self.BASE_URL}/search",
            params={"query": query},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_items = data.get("posts") or data.get("data") or data.get("results") or []
        raw_items = raw_items[:max_results]

        posts = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            post_id = str(raw.get("id") or raw.get("post_id") or raw.get("urn") or "")
            text = raw.get("text") or raw.get("commentary") or raw.get("content", "")
            author_name = raw.get("author_name") or raw.get("author", "")
            author_url = raw.get("author_url") or raw.get("author_profile_url", "")
            url = raw.get("url") or raw.get("post_url", "")

            posts.append(RawPost(
                platform=self.PLATFORM,
                platform_id=post_id,
                url=url,
                author=author_name,
                author_url=author_url or None,
                title=None,
                content=text[:2000],
                media_url=raw.get("image_url") or raw.get("media_url"),
                published_at=self._parse_date(raw),
                likes=raw.get("likes") or raw.get("num_likes", 0),
                comments=raw.get("comments") or raw.get("num_comments", 0),
                shares=raw.get("shares") or raw.get("num_shares", 0),
                views=raw.get("views") or raw.get("num_views", 0),
                raw_data=raw,
            ))
        return posts

    def _parse_date(self, item: Dict[str, Any]) -> Optional[str]:
        for key in ("created_at", "date", "published_at", "timestamp"):
            val = item.get(key)
            if not val:
                continue
            if isinstance(val, (int, float)):
                try:
                    return datetime.fromtimestamp(val, tz=timezone.utc).isoformat()
                except (ValueError, TypeError, OSError):
                    pass
            if isinstance(val, str):
                try:
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    return dt.isoformat()
                except (ValueError, TypeError):
                    pass
        return None
```

- [ ] **Step 7: Write youtube.py**

ScrapeCreators endpoint: `GET /v1/youtube/search?query=...`

```python
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
```

- [ ] **Step 8: Write platforms/__init__.py — crawler registry**

```python
"""Platform crawler registry."""

from .twitter import TwitterCrawler
from .reddit import RedditCrawler
from .tiktok import TikTokCrawler
from .instagram import InstagramCrawler
from .linkedin import LinkedInCrawler
from .youtube import YouTubeCrawler
from .base import PlatformCrawler, RawPost

CRAWLERS = {
    "twitter": TwitterCrawler,
    "reddit": RedditCrawler,
    "tiktok": TikTokCrawler,
    "instagram": InstagramCrawler,
    "linkedin": LinkedInCrawler,
    "youtube": YouTubeCrawler,
}

ALL_PLATFORMS = list(CRAWLERS.keys())

__all__ = [
    "CRAWLERS", "ALL_PLATFORMS", "PlatformCrawler", "RawPost",
    "TwitterCrawler", "RedditCrawler", "TikTokCrawler",
    "InstagramCrawler", "LinkedInCrawler", "YouTubeCrawler",
]
```

- [ ] **Step 9: Create test fixtures from last30days samples**

Copy relevant fixture files from `/tmp/last30days-skill/fixtures/` and create minimal test fixtures for each platform.

- [ ] **Step 10: Write tests/test_platforms.py**

```python
# tests/test_platforms.py
import json
import pytest
from unittest.mock import patch, MagicMock
from viralpulse.platforms import CRAWLERS, ALL_PLATFORMS
from viralpulse.platforms.base import RawPost


def test_all_platforms_registered():
    assert set(ALL_PLATFORMS) == {"twitter", "reddit", "tiktok", "instagram", "linkedin", "youtube"}


def test_crawlers_have_search_method():
    for name, cls in CRAWLERS.items():
        crawler = cls(api_key="test")
        assert hasattr(crawler, "search")
        assert crawler.PLATFORM == name


def _mock_response(data: dict):
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


@patch("httpx.get")
def test_twitter_search_parses(mock_get):
    mock_get.return_value = _mock_response({
        "tweets": [{
            "id": "123",
            "full_text": "AI is amazing",
            "user": {"screen_name": "testuser"},
            "favorite_count": 100,
            "retweet_count": 50,
            "reply_count": 10,
            "created_at": "Wed Mar 12 14:30:00 +0000 2026",
        }]
    })
    crawler = CRAWLERS["twitter"](api_key="test")
    posts = crawler.search("AI")
    assert len(posts) == 1
    assert posts[0].platform == "twitter"
    assert posts[0].likes == 100
    assert posts[0].author == "@testuser"


@patch("httpx.get")
def test_reddit_search_parses(mock_get):
    mock_get.return_value = _mock_response({
        "posts": [{
            "id": "abc",
            "title": "AI discussion",
            "permalink": "/r/tech/comments/abc/ai_discussion/",
            "author": "redditor",
            "ups": 500,
            "num_comments": 42,
            "selftext": "Long text here",
            "created_utc": 1741785600,
        }]
    })
    crawler = CRAWLERS["reddit"](api_key="test")
    posts = crawler.search("AI")
    assert len(posts) == 1
    assert posts[0].platform == "reddit"
    assert posts[0].likes == 500
    assert "reddit.com" in posts[0].url


@patch("httpx.get")
def test_tiktok_search_parses(mock_get):
    mock_get.return_value = _mock_response({
        "search_item_list": [{"aweme_info": {
            "aweme_id": "789",
            "desc": "Cool AI video #ai #tech",
            "statistics": {"play_count": 50000, "digg_count": 3000, "comment_count": 100, "share_count": 200},
            "author": {"unique_id": "creator1"},
            "create_time": 1741785600,
        }}]
    })
    crawler = CRAWLERS["tiktok"](api_key="test")
    posts = crawler.search("AI")
    assert len(posts) == 1
    assert posts[0].views == 50000
    assert posts[0].likes == 3000
```

- [ ] **Step 11: Run tests**

```bash
uv run pytest tests/test_platforms.py -v
```

- [ ] **Step 12: Commit**

```bash
git add src/viralpulse/platforms/ tests/test_platforms.py
git commit -m "feat: platform crawlers for Twitter, Reddit, TikTok, Instagram, LinkedIn, YouTube"
```

---

### Task 7: Crawler Orchestrator

**Files:**
- Create: `src/viralpulse/crawler.py`
- Create: `tests/test_crawler.py`

- [ ] **Step 1: Write test**

```python
# tests/test_crawler.py
from unittest.mock import patch, MagicMock
from viralpulse.crawler import crawl_topic
from viralpulse.platforms.base import RawPost


def _fake_post(platform: str, idx: int) -> RawPost:
    return RawPost(
        platform=platform,
        platform_id=f"{platform}-{idx}",
        url=f"https://example.com/{platform}/{idx}",
        author=f"@user{idx}",
        author_url=None,
        title=f"Post {idx}",
        content=f"Content about AI tools {idx}",
        media_url=None,
        published_at="2026-03-12T14:30:00+00:00",
        likes=100 * idx,
        comments=10 * idx,
    )


@patch("viralpulse.crawler.CRAWLERS")
def test_crawl_topic_collects_from_all_platforms(mock_crawlers):
    mock_twitter = MagicMock()
    mock_twitter.return_value.search.return_value = [_fake_post("twitter", 1)]
    mock_reddit = MagicMock()
    mock_reddit.return_value.search.return_value = [_fake_post("reddit", 1)]

    mock_crawlers.items.return_value = [
        ("twitter", mock_twitter),
        ("reddit", mock_reddit),
    ]

    results = crawl_topic("AI tools", api_key="test", platforms=["twitter", "reddit"])
    assert len(results) == 2
    platforms = {r.platform for r in results}
    assert "twitter" in platforms
    assert "reddit" in platforms
```

- [ ] **Step 2: Write crawler.py**

```python
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

        # Check if post already exists
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

    # Compute raw scores
    relevances = []
    velocities = []
    engagement_totals = []

    for p in posts:
        text = f"{p.get('title') or ''} {p.get('content') or ''}"
        rel = compute_relevance(topic_name, text)
        relevances.append(rel)

        total_engagement = (p.get("likes") or 0) + (p.get("comments") or 0) + (p.get("shares") or 0)
        engagement_totals.append(float(total_engagement))

        hours_old = 24.0  # default
        if p.get("published_at"):
            try:
                pub = datetime.fromisoformat(str(p["published_at"]))
                hours_old = max((now - pub).total_seconds() / 3600, 0.1)
            except (ValueError, TypeError):
                pass
        velocities.append(compute_velocity(total_engagement, hours_old))

    # Normalize engagement and velocity
    norm_engagement = normalize_engagement(engagement_totals)
    norm_velocity = normalize_engagement(velocities)  # reuse normalizer

    # Write scores
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
        counts = store_crawl_results(topic["id"], posts, topic["name"], db_url=db_url)
        results.append({"topic": topic["name"], **counts})
        logger.info(f"  → {counts['new']} new, {counts['updated']} updated")

    return results
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_crawler.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/crawler.py tests/test_crawler.py
git commit -m "feat: crawler orchestrator with scoring and DB persistence"
```

---

## Chunk 4: API + CLI (Tasks 8-9)

### Task 8: FastAPI Application

**Files:**
- Create: `src/viralpulse/api.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write test**

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from viralpulse.api import app


client = TestClient(app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_platforms():
    resp = client.get("/api/v1/platforms")
    assert resp.status_code == 200
    platforms = resp.json()["platforms"]
    names = {p["name"] for p in platforms}
    assert "twitter" in names
    assert "reddit" in names


def test_posts_requires_topic():
    resp = client.get("/api/v1/posts")
    assert resp.status_code == 422  # missing required param


def test_topics_empty():
    resp = client.get("/api/v1/topics")
    assert resp.status_code == 200
```

- [ ] **Step 2: Write api.py**

```python
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


@app.get("/api/v1/posts")
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
    sort_dir = "DESC" if sort != "recent" else "DESC NULLS LAST"

    conn = get_conn()

    query_parts = [
        """SELECT p.*, s.relevance, s.engagement_normalized, s.velocity, s.composite,
                  e.likes, e.comments, e.shares, e.views, e.platform_score
           FROM posts p
           JOIN topics t ON t.id = p.topic_id
           LEFT JOIN scores s ON s.post_id = p.id
           LEFT JOIN LATERAL (
               SELECT * FROM engagement WHERE post_id = p.id ORDER BY snapshot_at DESC LIMIT 1
           ) e ON true
           WHERE t.name = %s
             AND p.fetched_at > now() - interval '%s days'"""
    ]
    params = [topic, days]

    if platform:
        query_parts.append("AND p.platform = %s")
        params.append(platform)

    query_parts.append(f"ORDER BY {sort_col} {sort_dir} NULLS LAST")
    query_parts.append("LIMIT %s")
    params.append(limit)

    rows = conn.execute(" ".join(query_parts), params).fetchall()
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
                likes=r.get("likes", 0),
                comments=r.get("comments", 0),
                shares=r.get("shares", 0),
                views=r.get("views", 0),
                platform_score=r.get("platform_score", 0),
            ),
            scores=Scores(
                relevance=r.get("relevance", 0),
                engagement_normalized=r.get("engagement_normalized", 0),
                velocity=r.get("velocity", 0),
                composite=r.get("composite", 0),
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
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_api.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/api.py tests/test_api.py
git commit -m "feat: FastAPI with /posts, /topics, /platforms, /health endpoints"
```

---

### Task 9: CLI

**Files:**
- Create: `src/viralpulse/cli.py`

- [ ] **Step 1: Write cli.py**

```python
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


def cmd_serve(args):
    import uvicorn
    uvicorn.run("viralpulse.api:app", host=args.host, port=args.port, reload=args.reload)


def main():
    parser = argparse.ArgumentParser(prog="viralpulse", description="ViralPulse — viral social media post aggregator")
    sub = parser.add_subparsers(dest="command")

    # topic add
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

    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add CLI entry point to pyproject.toml**

Add under `[project.scripts]`:
```toml
[project.scripts]
viralpulse = "viralpulse.cli:main"
```

- [ ] **Step 3: Test CLI manually**

```bash
uv run viralpulse --help
uv run viralpulse topic --help
uv run viralpulse status
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/cli.py pyproject.toml
git commit -m "feat: CLI with topic management, crawl, serve, status commands"
```

---

## Chunk 5: Deployment (Task 10)

### Task 10: Cron Setup + .env Configuration

**Files:**
- Create: `.env` (from `.env.example`, not committed)

- [ ] **Step 1: Create .env with real credentials**

```bash
cp .env.example .env
# Edit .env with actual SCRAPECREATORS_API_KEY and Neon DATABASE_URL
```

- [ ] **Step 2: Initialize database**

```bash
uv run python -c "from viralpulse.db import init_db; init_db(); print('DB initialized')"
```

- [ ] **Step 3: Add a test topic and run first crawl**

```bash
uv run viralpulse topic add "AI video tools"
uv run viralpulse crawl --topic "AI video tools"
```

- [ ] **Step 4: Start API server and verify**

```bash
uv run viralpulse serve &
curl http://localhost:8000/api/v1/health
curl "http://localhost:8000/api/v1/posts?topic=AI+video+tools"
```

- [ ] **Step 5: Set up daily cron**

```bash
crontab -e
# Add: 0 8 * * * cd /home/iris/viralpulse && /home/iris/.local/bin/uv run viralpulse crawl >> /home/iris/viralpulse/crawl.log 2>&1
```

- [ ] **Step 6: Add .env to .gitignore and commit**

```bash
echo ".env" >> .gitignore
echo "crawl.log" >> .gitignore
echo "__pycache__/" >> .gitignore
echo ".pytest_cache/" >> .gitignore
git add .gitignore
git commit -m "chore: add .gitignore for secrets and cache"
```

---

## Chunk 6: Dashboard (Task 11)

### Task 11: Next.js Dashboard

This task creates the cross-platform news dashboard. Defer until the API is working and has data.

**Files:**
- Create: `dashboard/` (Next.js app via `npx create-next-app`)

- [ ] **Step 1: Scaffold Next.js app**

```bash
cd /home/iris/viralpulse
npx create-next-app@latest dashboard --typescript --tailwind --app --no-src-dir --no-import-alias
```

- [ ] **Step 2: Build dashboard pages**

Pages needed:
- `/` — cross-platform feed with topic selector + platform filter chips + sort dropdown
- Card component showing: platform badge, author, content preview, engagement metrics, composite score

- [ ] **Step 3: Connect to API**

Use the FastAPI base URL as an env var (`NEXT_PUBLIC_API_URL`).

- [ ] **Step 4: Deploy to Vercel**

```bash
cd dashboard
vercel
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/
git commit -m "feat: Next.js dashboard with cross-platform news feed"
```
