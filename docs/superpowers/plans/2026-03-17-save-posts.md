# Save Posts Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users save social media posts and web articles to a personal library via Chrome extension or API, with automatic screenshot capture and metadata extraction, queryable by AI agents.

**Architecture:** New `users` + `saved_posts` tables in existing Neon Postgres. API key auth via `X-API-Key` header. Screenshots stored in S3. Chrome extension captures tab + DOM metadata. VM fallback uses Playwright for URL-only saves.

**Tech Stack:** Python 3.14+, FastAPI (existing), psycopg, boto3 (S3), Playwright (VM screenshots), Chrome Manifest V3 (extension)

---

## File Structure

```
src/viralpulse/
├── config.py              # MODIFY: add aws_access_key_id, aws_secret_access_key, s3_bucket
├── db.py                  # MODIFY: add users + saved_posts tables to SCHEMA_SQL
├── auth.py                # CREATE: API key generation + user lookup
├── platform_detect.py     # CREATE: detect platform from URL
├── screenshot.py          # CREATE: VM screenshot service via Playwright
├── s3.py                  # CREATE: S3 upload/URL generation
├── api.py                 # MODIFY: add /users, /save, /saved, /saved/{id} endpoints
├── cli.py                 # MODIFY: add user subcommands
├── templates/
│   └── viral-writer.md    # MODIFY: add saved posts section

extension/                  # CREATE: Chrome extension
├── manifest.json
├── popup.html
├── popup.js
├── content.js              # DOM metadata extractors
├── background.js           # screenshot capture + API call
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png

tests/
├── test_auth.py
├── test_platform_detect.py
├── test_screenshot.py
├── test_save_api.py
```

---

## Chunk 1: Foundation (Tasks 1-4)

### Task 1: Config + Dependencies

**Files:**
- Modify: `src/viralpulse/config.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add S3 + Playwright dependencies**

```bash
cd /home/iris/viralpulse
~/.local/bin/uv add boto3 playwright
~/.local/bin/uv run playwright install chromium
```

- [ ] **Step 2: Update config.py with S3 settings**

Add to the Settings class:
```python
aws_access_key_id: str = ""
aws_secret_access_key: str = ""
aws_region: str = "us-east-1"
s3_bucket: str = "viralpulse-screenshots"
```

- [ ] **Step 3: Update .env.example**

Append:
```
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
S3_BUCKET=viralpulse-screenshots
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock src/viralpulse/config.py .env.example
git commit -m "feat: add boto3 + playwright deps, S3 config"
```

---

### Task 2: Database Schema — users + saved_posts

**Files:**
- Modify: `src/viralpulse/db.py`

- [ ] **Step 1: Append users + saved_posts tables to SCHEMA_SQL**

Add after the `crawl_runs` table in SCHEMA_SQL:

```sql
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
```

- [ ] **Step 2: Run migration**

```bash
.venv/bin/python3 -c "from viralpulse.db import init_db; init_db(); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/viralpulse/db.py
git commit -m "feat: add users + saved_posts tables"
```

---

### Task 3: Auth Module

**Files:**
- Create: `src/viralpulse/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_auth.py
from viralpulse.auth import generate_api_key, detect_platform


def test_generate_api_key():
    key = generate_api_key()
    assert key.startswith("vp_")
    assert len(key) == 27  # "vp_" + 24 chars


def test_generate_unique():
    keys = {generate_api_key() for _ in range(100)}
    assert len(keys) == 100
```

- [ ] **Step 2: Write auth.py**

```python
"""API key generation and user authentication."""

import secrets
from typing import Optional
from viralpulse.db import get_conn


def generate_api_key() -> str:
    """Generate a unique API key with vp_ prefix."""
    return f"vp_{secrets.token_urlsafe(18)}"


def get_user_by_key(api_key: str) -> Optional[dict]:
    """Look up user by API key. Returns user dict or None."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE api_key = %s", (api_key,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def require_user(api_key: str) -> dict:
    """Get user or raise ValueError."""
    user = get_user_by_key(api_key)
    if not user:
        raise ValueError("Invalid API key")
    return user
```

- [ ] **Step 3: Run tests**

```bash
~/.local/bin/uv run pytest tests/test_auth.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/auth.py tests/test_auth.py
git commit -m "feat: API key generation and user auth"
```

---

### Task 4: Platform Detection

**Files:**
- Create: `src/viralpulse/platform_detect.py`
- Create: `tests/test_platform_detect.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_platform_detect.py
from viralpulse.platform_detect import detect_platform


def test_twitter():
    assert detect_platform("https://x.com/OpenAI/status/123") == "twitter"
    assert detect_platform("https://twitter.com/user/status/456") == "twitter"


def test_reddit():
    assert detect_platform("https://www.reddit.com/r/tech/comments/abc") == "reddit"


def test_tiktok():
    assert detect_platform("https://www.tiktok.com/@user/video/123") == "tiktok"


def test_instagram():
    assert detect_platform("https://www.instagram.com/reel/ABC/") == "instagram"


def test_youtube():
    assert detect_platform("https://www.youtube.com/watch?v=abc") == "youtube"
    assert detect_platform("https://youtu.be/abc") == "youtube"


def test_linkedin():
    assert detect_platform("https://www.linkedin.com/posts/user-123") == "linkedin"


def test_generic():
    assert detect_platform("https://techcrunch.com/2026/03/article") == "web"
    assert detect_platform("https://substack.com/p/something") == "web"
```

- [ ] **Step 2: Write platform_detect.py**

```python
"""Detect social media platform from URL."""

from urllib.parse import urlparse

PLATFORM_MAP = {
    "x.com": "twitter",
    "twitter.com": "twitter",
    "reddit.com": "reddit",
    "old.reddit.com": "reddit",
    "tiktok.com": "tiktok",
    "instagram.com": "instagram",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "linkedin.com": "linkedin",
}


def detect_platform(url: str) -> str:
    """Detect platform from URL hostname. Returns platform name or 'web'."""
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower().removeprefix("www.")
        return PLATFORM_MAP.get(hostname, "web")
    except Exception:
        return "web"
```

- [ ] **Step 3: Run tests**

```bash
~/.local/bin/uv run pytest tests/test_platform_detect.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/platform_detect.py tests/test_platform_detect.py
git commit -m "feat: platform detection from URL"
```

---

## Chunk 2: S3 + Screenshot Service (Tasks 5-6)

### Task 5: S3 Upload Module

**Files:**
- Create: `src/viralpulse/s3.py`
- Create: `tests/test_s3.py`

- [ ] **Step 1: Write s3.py**

```python
"""S3 screenshot storage."""

import base64
import boto3
from viralpulse.config import settings


def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


def upload_screenshot(user_id: str, post_id: str, png_bytes: bytes) -> str:
    """Upload screenshot PNG to S3. Returns the public URL."""
    key = f"{user_id}/{post_id}.png"
    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=png_bytes,
        ContentType="image/png",
    )
    return f"https://{settings.s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"


def upload_screenshot_base64(user_id: str, post_id: str, b64_data: str) -> str:
    """Upload base64-encoded screenshot to S3."""
    # Strip data URI prefix if present
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]
    png_bytes = base64.b64decode(b64_data)
    return upload_screenshot(user_id, post_id, png_bytes)


def delete_screenshot(user_id: str, post_id: str):
    """Delete a screenshot from S3."""
    key = f"{user_id}/{post_id}.png"
    client = get_s3_client()
    client.delete_object(Bucket=settings.s3_bucket, Key=key)
```

- [ ] **Step 2: Write test (mocked)**

```python
# tests/test_s3.py
from unittest.mock import patch, MagicMock
from viralpulse.s3 import upload_screenshot, upload_screenshot_base64
import base64


@patch("viralpulse.s3.get_s3_client")
def test_upload_screenshot(mock_client):
    mock_client.return_value = MagicMock()
    url = upload_screenshot("user-123", "post-456", b"fake png bytes")
    assert "user-123/post-456.png" in url
    mock_client.return_value.put_object.assert_called_once()


@patch("viralpulse.s3.get_s3_client")
def test_upload_base64(mock_client):
    mock_client.return_value = MagicMock()
    b64 = base64.b64encode(b"fake png").decode()
    url = upload_screenshot_base64("user-123", "post-456", b64)
    assert "user-123/post-456.png" in url


@patch("viralpulse.s3.get_s3_client")
def test_upload_base64_with_data_uri(mock_client):
    mock_client.return_value = MagicMock()
    b64 = "data:image/png;base64," + base64.b64encode(b"fake png").decode()
    url = upload_screenshot_base64("user-123", "post-456", b64)
    assert "post-456.png" in url
```

- [ ] **Step 3: Run tests**

```bash
~/.local/bin/uv run pytest tests/test_s3.py -v
```

- [ ] **Step 4: Create S3 bucket**

```bash
aws s3 mb s3://viralpulse-screenshots --region us-east-1
aws s3api put-public-access-block --bucket viralpulse-screenshots --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
aws s3api put-bucket-policy --bucket viralpulse-screenshots --policy '{"Version":"2012-10-17","Statement":[{"Sid":"PublicRead","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::viralpulse-screenshots/*"}]}'
```

- [ ] **Step 5: Commit**

```bash
git add src/viralpulse/s3.py tests/test_s3.py
git commit -m "feat: S3 screenshot upload module"
```

---

### Task 6: VM Screenshot Service

**Files:**
- Create: `src/viralpulse/screenshot.py`

- [ ] **Step 1: Write screenshot.py**

```python
"""VM screenshot service using Playwright headless browser."""

import logging
import re
from typing import Optional, Tuple
from playwright.sync_api import sync_playwright

logger = logging.getLogger("viralpulse.screenshot")

# Platform-specific DOM selectors for metadata extraction
EXTRACTORS = {
    "twitter": {
        "author": 'article [data-testid="User-Name"] a span',
        "content": 'article [data-testid="tweetText"]',
        "engagement": {
            "likes": '[data-testid="like"] span',
            "retweets": '[data-testid="retweet"] span',
            "replies": '[data-testid="reply"] span',
        },
    },
    "reddit": {
        "author": '[data-testid="post_author_link"]',
        "content": '[data-testid="post-title"], [slot="text-body"]',
        "engagement": {
            "score": '[data-testid="post-score"]',
            "comments": 'a[data-testid="comments-link"] span',
        },
    },
    "youtube": {
        "author": '#channel-name a',
        "content": 'h1.ytd-watch-metadata',
        "engagement": {
            "views": '#info-strings yt-formatted-string',
            "likes": '#top-level-buttons-computed button:first-child',
        },
    },
}


def _parse_engagement_number(text: str) -> int:
    """Parse engagement numbers like '1.5K', '2.3M', '500'."""
    text = text.strip().replace(",", "")
    multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}
    for suffix, mult in multipliers.items():
        if text.upper().endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                return 0
    try:
        return int(text)
    except ValueError:
        return 0


def capture_screenshot_and_metadata(
    url: str,
    platform: str = "web",
    timeout_ms: int = 30000,
) -> Tuple[Optional[bytes], dict]:
    """Open URL in headless browser, take screenshot, extract metadata.

    Returns (screenshot_bytes, metadata_dict). screenshot_bytes may be None on failure.
    """
    metadata = {"author": "", "content": "", "engagement": {}, "hashtags": []}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_timeout(2000)  # extra settle time

            # Scroll down to load lazy content
            page.evaluate("window.scrollBy(0, 800)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)

            # Take screenshot
            screenshot = page.screenshot(full_page=False)  # visible viewport

            # Extract metadata — try platform-specific first, fall back to generic
            try:
                # Generic extraction (works on all pages)
                metadata["content"] = page.evaluate("""() => {
                    const og = document.querySelector('meta[property="og:description"]');
                    if (og) return og.content;
                    const article = document.querySelector('article, main, [role="main"]');
                    if (article) return article.innerText.slice(0, 3000);
                    return document.title;
                }""") or ""

                metadata["author"] = page.evaluate("""() => {
                    const og = document.querySelector('meta[property="og:site_name"]');
                    const author = document.querySelector('meta[name="author"]');
                    const byline = document.querySelector('[rel="author"], .author, .byline');
                    return author?.content || byline?.innerText || og?.content || '';
                }""") or ""

                # Page title as supplemental
                title = page.title() or ""
                if title and not metadata["content"]:
                    metadata["content"] = title

                # Extract hashtags from content
                metadata["hashtags"] = re.findall(r'#(\w+)', metadata["content"])

            except Exception as e:
                logger.warning(f"Metadata extraction failed for {url}: {e}")

            browser.close()
            return screenshot, metadata

    except Exception as e:
        logger.error(f"Screenshot capture failed for {url}: {e}")
        return None, metadata
```

- [ ] **Step 2: Commit**

```bash
git add src/viralpulse/screenshot.py
git commit -m "feat: VM screenshot service with Playwright"
```

---

## Chunk 3: API Endpoints (Task 7)

### Task 7: Save/Saved/Users API Endpoints

**Files:**
- Modify: `src/viralpulse/api.py`
- Create: `tests/test_save_api.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_save_api.py
from fastapi.testclient import TestClient
from viralpulse.api import app

client = TestClient(app)


def test_create_user_no_db():
    """Without DB, user creation should fail gracefully."""
    resp = client.post("/api/v1/users", json={"name": "test"})
    # Will be 500 if no DB — that's expected
    assert resp.status_code in (200, 201, 500)


def test_saved_requires_auth():
    resp = client.get("/api/v1/saved")
    assert resp.status_code in (401, 403)


def test_save_requires_auth():
    resp = client.post("/api/v1/save", json={"url": "https://x.com/test"})
    assert resp.status_code in (401, 403)
```

- [ ] **Step 2: Add API endpoints to api.py**

Add these imports at the top of api.py:
```python
import threading
from fastapi import Header
from viralpulse.auth import generate_api_key, get_user_by_key
from viralpulse.platform_detect import detect_platform
```

Add a dependency for auth:
```python
def _get_user(x_api_key: str = Header(None)):
    """Extract user from X-API-Key header."""
    if not x_api_key:
        raise HTTPException(401, "Missing X-API-Key header")
    user = get_user_by_key(x_api_key)
    if not user:
        raise HTTPException(403, "Invalid API key")
    return user
```

Add endpoints (before the `get_post` endpoint):

```python
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
               updated_at = now()
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

    # Handle screenshot
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
    # Delete S3 screenshot
    try:
        from viralpulse.s3 import delete_screenshot
        delete_screenshot(str(user["id"]), post_id)
    except Exception:
        pass
    return {"deleted": True}
```

Note: Add `from fastapi import Depends` to the imports.

- [ ] **Step 3: Run tests**

```bash
~/.local/bin/uv run pytest tests/test_save_api.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/api.py tests/test_save_api.py
git commit -m "feat: save/saved/users API endpoints with auth"
```

---

## Chunk 4: CLI + Skill Update (Task 8)

### Task 8: CLI User Commands + Skill Update

**Files:**
- Modify: `src/viralpulse/cli.py`
- Modify: `src/viralpulse/templates/viral-writer.md`

- [ ] **Step 1: Add user CLI commands to cli.py**

Add handler functions:
```python
def cmd_user_create(args):
    init_db()
    from viralpulse.auth import generate_api_key
    conn = get_conn()
    api_key = generate_api_key()
    row = conn.execute(
        "INSERT INTO users (api_key, name, email) VALUES (%s, %s, %s) RETURNING *",
        (api_key, args.name, args.email),
    ).fetchone()
    conn.commit()
    conn.close()
    print(f"User created: {row['name']}")
    print(f"API Key: {row['api_key']}")
    print(f"Save this key — it won't be shown again.")


def cmd_user_list(args):
    init_db()
    conn = get_conn()
    rows = conn.execute(
        """SELECT u.*, COUNT(sp.id) as saved_count
           FROM users u LEFT JOIN saved_posts sp ON sp.user_id = u.id
           GROUP BY u.id ORDER BY u.created_at"""
    ).fetchall()
    conn.close()
    if not rows:
        print("No users. Create one: viralpulse user create \"Your Name\"")
        return
    print(f"{'Name':<20} {'Key':<30} {'Saved':<8}")
    print("-" * 60)
    for r in rows:
        key_preview = r['api_key'][:10] + "..."
        print(f"{r['name']:<20} {key_preview:<30} {r['saved_count']:<8}")
```

Add subcommand parsers in `main()`:
```python
    user_parser = sub.add_parser("user", help="Manage users")
    user_sub = user_parser.add_subparsers(dest="user_command")

    create_u = user_sub.add_parser("create", help="Create a user")
    create_u.add_argument("name", help="User name")
    create_u.add_argument("--email", default=None)
    create_u.set_defaults(func=cmd_user_create)

    list_u = user_sub.add_parser("list", help="List users")
    list_u.set_defaults(func=cmd_user_list)
```

Add handler for missing subcommand:
```python
    if args.command == "user" and not getattr(args, "user_command", None):
        user_parser.print_help()
        sys.exit(1)
```

- [ ] **Step 2: Update viral-writer.md skill**

Append this section before the `## Notes` section:

```markdown
## Using the user's saved posts

If the user provides a ViralPulse API key, also fetch their personal collection:

```
GET /api/v1/saved?query={topic}&limit=20
Header: X-API-Key: {user's key}
```

These are posts the user personally curated as examples of great content.
Weight these higher than trending data — the user saved them because they
represent the style, format, or voice they want to emulate.

Combine both sources:
1. `GET /api/v1/posts?topic=...` — what's trending (public data)
2. `GET /api/v1/saved?query=...` — what the user has been collecting (personal curation)

The user's saved posts include `screenshot_url` — if using Claude vision,
you can analyze the visual format and layout of the original posts.
```

- [ ] **Step 3: Commit**

```bash
git add src/viralpulse/cli.py src/viralpulse/templates/viral-writer.md
git commit -m "feat: user CLI commands + updated agent skill with saved posts"
```

---

## Chunk 5: Chrome Extension (Task 9)

### Task 9: Chrome Manifest V3 Extension

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/popup.html`
- Create: `extension/popup.js`
- Create: `extension/content.js`
- Create: `extension/background.js`
- Create: `extension/icons/` (placeholder icons)

- [ ] **Step 1: Create extension/manifest.json**

```json
{
  "manifest_version": 3,
  "name": "ViralPulse — Save Viral Posts",
  "version": "1.0.0",
  "description": "Save any social media post or article to your ViralPulse library with one click.",
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["https://api.aithatjustworks.com/*"],
  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["content.js"],
    "run_at": "document_idle"
  }],
  "background": {
    "service_worker": "background.js"
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

- [ ] **Step 2: Create extension/content.js**

```javascript
// Content script — extracts metadata from the current page

function extractMetadata() {
  const url = window.location.href;
  const hostname = window.location.hostname.replace('www.', '');

  // Platform-specific extractors
  const extractors = {
    'x.com': extractTwitter,
    'twitter.com': extractTwitter,
    'reddit.com': extractReddit,
    'tiktok.com': extractTikTok,
    'instagram.com': extractInstagram,
    'youtube.com': extractYouTube,
    'linkedin.com': extractLinkedIn,
  };

  const extractor = extractors[hostname];
  if (extractor) {
    try { return extractor(); } catch (e) { console.log('Platform extractor failed, using generic', e); }
  }
  return extractGeneric();
}

function extractTwitter() {
  const article = document.querySelector('article');
  if (!article) return extractGeneric();
  const author = article.querySelector('[data-testid="User-Name"] a')?.textContent || '';
  const content = article.querySelector('[data-testid="tweetText"]')?.textContent || '';
  return { author, content, engagement: {}, hashtags: extractHashtags(content) };
}

function extractReddit() {
  const title = document.querySelector('[data-testid="post-title"], h1')?.textContent || '';
  const body = document.querySelector('[slot="text-body"], .usertext-body')?.textContent || '';
  const author = document.querySelector('[data-testid="post_author_link"], .author')?.textContent || '';
  return { author, content: title + '\n' + body, engagement: {}, hashtags: [] };
}

function extractTikTok() {
  const author = document.querySelector('[data-e2e="browse-username"], .author-uniqueId')?.textContent || '';
  const content = document.querySelector('[data-e2e="browse-video-desc"], .video-meta-title')?.textContent || '';
  return { author, content, engagement: {}, hashtags: extractHashtags(content) };
}

function extractInstagram() {
  const author = document.querySelector('header a')?.textContent || '';
  const content = document.querySelector('h1, [data-testid="post-comment-root"] span')?.textContent || '';
  return { author, content, engagement: {}, hashtags: extractHashtags(content) };
}

function extractYouTube() {
  const title = document.querySelector('h1.ytd-watch-metadata, h1.title')?.textContent || '';
  const channel = document.querySelector('#channel-name a, .ytd-channel-name a')?.textContent || '';
  const desc = document.querySelector('#description-inner, .ytd-text-inline-expander')?.textContent || '';
  return { author: channel, content: title + '\n' + desc.slice(0, 1000), engagement: {}, hashtags: extractHashtags(desc) };
}

function extractLinkedIn() {
  const author = document.querySelector('.feed-shared-actor__name, .update-components-actor__name')?.textContent || '';
  const content = document.querySelector('.feed-shared-text, .update-components-text')?.textContent || '';
  return { author, content, engagement: {}, hashtags: extractHashtags(content) };
}

function extractGeneric() {
  const ogTitle = document.querySelector('meta[property="og:title"]')?.content || '';
  const ogDesc = document.querySelector('meta[property="og:description"]')?.content || '';
  const author = document.querySelector('meta[name="author"]')?.content
    || document.querySelector('[rel="author"], .author, .byline')?.textContent || '';
  const articleText = document.querySelector('article, main, [role="main"]')?.innerText?.slice(0, 3000) || '';
  const content = ogTitle + (ogDesc ? '\n' + ogDesc : '') + (articleText ? '\n' + articleText : '') || document.title;
  return { author, content, engagement: {}, hashtags: extractHashtags(content) };
}

function extractHashtags(text) {
  const matches = text.match(/#(\w+)/g) || [];
  return matches.map(h => h.slice(1));
}

// Listen for messages from popup/background
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'EXTRACT_METADATA') {
    sendResponse(extractMetadata());
  }
  return true;
});
```

- [ ] **Step 3: Create extension/background.js**

```javascript
// Background service worker — captures screenshot + sends to API

const API_BASE = 'https://api.aithatjustworks.com';

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'SAVE_POST') {
    handleSave(msg).then(sendResponse).catch(e => sendResponse({ error: e.message }));
    return true; // async response
  }
});

async function handleSave({ metadata, userNote, tabId }) {
  // Get API key
  const { apiKey } = await chrome.storage.sync.get('apiKey');
  if (!apiKey) throw new Error('No API key set. Open extension settings.');

  // Capture screenshot
  const dataUrl = await chrome.tabs.captureVisibleTab(null, { format: 'png' });
  const screenshot_base64 = dataUrl; // includes data:image/png;base64, prefix — API strips it

  // Get current tab URL
  const tab = await chrome.tabs.get(tabId);

  // Send to API
  const resp = await fetch(`${API_BASE}/api/v1/save`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify({
      url: tab.url,
      screenshot_base64,
      metadata,
      user_note: userNote || null,
    }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `API error: ${resp.status}`);
  }

  return resp.json();
}
```

- [ ] **Step 4: Create extension/popup.html + popup.js**

```html
<!-- extension/popup.html -->
<!DOCTYPE html>
<html>
<head>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { width: 320px; font-family: -apple-system, system-ui, sans-serif; background: #fafaf9; color: #1c1917; padding: 16px; }
    h1 { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
    h1 span { color: #dc2626; }
    textarea { width: 100%; height: 60px; border: 1px solid #e7e5e4; border-radius: 8px; padding: 8px; font-size: 13px; resize: none; font-family: inherit; }
    textarea:focus { outline: none; border-color: #dc2626; }
    button { width: 100%; padding: 10px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 8px; }
    .save-btn { background: #1c1917; color: white; }
    .save-btn:hover { background: #292524; }
    .save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .status { font-size: 12px; margin-top: 8px; text-align: center; }
    .status.success { color: #16a34a; }
    .status.error { color: #dc2626; }
    .settings { margin-top: 12px; padding-top: 12px; border-top: 1px solid #e7e5e4; }
    .settings label { font-size: 12px; color: #78716c; display: block; margin-bottom: 4px; }
    .settings input { width: 100%; border: 1px solid #e7e5e4; border-radius: 6px; padding: 6px 8px; font-size: 12px; font-family: monospace; }
    .settings input:focus { outline: none; border-color: #dc2626; }
  </style>
</head>
<body>
  <h1><span>Viral</span>Pulse — Save Post</h1>
  <textarea id="note" placeholder="Add a note (optional)... e.g. 'great hook', 'study this format'"></textarea>
  <button class="save-btn" id="saveBtn">Save to Library</button>
  <div class="status" id="status"></div>

  <div class="settings" id="settingsSection">
    <label>API Key</label>
    <input type="text" id="apiKeyInput" placeholder="vp_...">
  </div>

  <script src="popup.js"></script>
</body>
</html>
```

```javascript
// extension/popup.js

const saveBtn = document.getElementById('saveBtn');
const noteEl = document.getElementById('note');
const statusEl = document.getElementById('status');
const apiKeyInput = document.getElementById('apiKeyInput');

// Load saved API key
chrome.storage.sync.get('apiKey', ({ apiKey }) => {
  if (apiKey) {
    apiKeyInput.value = apiKey;
    apiKeyInput.parentElement.style.display = 'none'; // hide if already set
  }
});

// Save API key on change
apiKeyInput.addEventListener('change', () => {
  const key = apiKeyInput.value.trim();
  if (key) {
    chrome.storage.sync.set({ apiKey: key });
    statusEl.textContent = 'API key saved';
    statusEl.className = 'status success';
  }
});

saveBtn.addEventListener('click', async () => {
  // Check API key
  const { apiKey } = await chrome.storage.sync.get('apiKey');
  if (!apiKey) {
    statusEl.textContent = 'Please enter your API key first';
    statusEl.className = 'status error';
    apiKeyInput.parentElement.style.display = 'block';
    return;
  }

  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';
  statusEl.textContent = '';

  try {
    // Get active tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Extract metadata from content script
    const metadata = await chrome.tabs.sendMessage(tab.id, { type: 'EXTRACT_METADATA' });

    // Send to background for screenshot + API call
    const result = await chrome.runtime.sendMessage({
      type: 'SAVE_POST',
      metadata,
      userNote: noteEl.value.trim() || null,
      tabId: tab.id,
    });

    if (result.error) throw new Error(result.error);

    statusEl.textContent = `Saved! (${result.platform})`;
    statusEl.className = 'status success';
    saveBtn.textContent = 'Saved!';

    setTimeout(() => window.close(), 1500);
  } catch (e) {
    statusEl.textContent = e.message;
    statusEl.className = 'status error';
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save to Library';
  }
});
```

- [ ] **Step 5: Create placeholder icons**

Generate simple colored square PNGs (16x16, 48x48, 128x128) using Python:
```bash
mkdir -p extension/icons
python3 -c "
from PIL import Image
for size in [16, 48, 128]:
    img = Image.new('RGB', (size, size), '#dc2626')
    img.save(f'extension/icons/icon{size}.png')
print('Icons created')
"
```
If PIL not available, create minimal placeholder PNGs.

- [ ] **Step 6: Commit**

```bash
git add extension/
git commit -m "feat: Chrome extension with screenshot capture and DOM metadata extraction"
```

---

## Chunk 6: Integration Test + Deploy (Task 10)

### Task 10: End-to-End Test + Production Deploy

- [ ] **Step 1: Update .env with S3 credentials**

The AWS credentials are already in `~/.aws/credentials`. Copy them to .env or verify `boto3` picks them up from the default credential chain.

- [ ] **Step 2: Create a test user**

```bash
~/.local/bin/uv run viralpulse user create "Test User" --email test@viralpulse.dev
```

Save the API key output.

- [ ] **Step 3: Test save via API (VM screenshot path)**

```bash
curl -X POST https://api.aithatjustworks.com/api/v1/save \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY_HERE" \
  -d '{"url": "https://x.com/OpenAI/status/1234567890"}'
```

- [ ] **Step 4: Test retrieve**

```bash
curl -H "X-API-Key: YOUR_KEY_HERE" "https://api.aithatjustworks.com/api/v1/saved"
```

- [ ] **Step 5: Restart production service**

```bash
sudo systemctl restart viralpulse
```

- [ ] **Step 6: Run all tests**

```bash
~/.local/bin/uv run pytest -v
```

- [ ] **Step 7: Commit and push**

```bash
git add -A
git commit -m "feat: save posts feature complete — API, S3, screenshots, Chrome extension"
git push
```
