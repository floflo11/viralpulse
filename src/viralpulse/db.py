"""Database connection and schema management."""

import psycopg
from psycopg.rows import dict_row
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

CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(platform, handle)
);

CREATE INDEX IF NOT EXISTS idx_profiles_platform ON profiles(platform, handle);

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

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key TEXT UNIQUE NOT NULL,
    name TEXT DEFAULT '',
    email TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);

CREATE TABLE IF NOT EXISTS saved_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    platform TEXT DEFAULT 'web',
    author TEXT DEFAULT '',
    content TEXT DEFAULT '',
    engagement JSONB,
    hashtags JSONB DEFAULT '[]'::jsonb,
    published_at TIMESTAMPTZ,
    user_note TEXT,
    screenshot_url TEXT,
    source TEXT DEFAULT 'api',
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, url)
);

CREATE INDEX IF NOT EXISTS idx_saved_posts_user ON saved_posts(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_saved_posts_platform ON saved_posts(user_id, platform);

ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS images JSONB DEFAULT '[]';
ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS video_thumbnail TEXT;
ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS video_url TEXT;

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    keywords JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id);

ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS telegram_users (
    telegram_id BIGINT PRIMARY KEY,
    api_key TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
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
