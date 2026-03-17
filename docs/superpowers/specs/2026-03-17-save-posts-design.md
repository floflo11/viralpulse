# Save Posts — Design Spec

## Overview

Users save social media posts and web articles to their personal ViralPulse library via Chrome extension or API. Each saved post is captured as a screenshot + extracted text/metadata. AI agents query the library alongside trending data to write viral content informed by the user's personal curation.

## User Flow

**Chrome Extension (primary):**
1. User browses any webpage (tweet, Reddit post, TechCrunch article, etc.)
2. Clicks "Save to ViralPulse" extension button
3. Extension captures visible tab screenshot + scrapes DOM metadata
4. POSTs to API with user's API key
5. Instant confirmation — post is saved with full content

**API/Link Share (fallback):**
1. User sends URL via `POST /api/v1/save` (or later: WhatsApp/Slack bot)
2. API stores URL as `status: "pending"`
3. Background: VM opens URL in headless Playwright, takes screenshot, extracts text
4. Updates to `status: "enriched"` or `"failed"`

## Data Model

Added to existing Neon Postgres (same DB as ViralPulse core):

### users
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| api_key | text | unique, "vp_" + 24 random chars |
| name | text | |
| email | text | unique, nullable |
| created_at | timestamptz | |

### saved_posts
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK → users |
| url | text | original URL |
| platform | text | auto-detected (twitter, reddit, tiktok, instagram, youtube, linkedin, web) |
| author | text | extracted from DOM |
| content | text | visible text content |
| engagement | jsonb | {likes, comments, shares, views} — null for non-social pages |
| hashtags | jsonb | ["ai", "video"] |
| published_at | timestamptz | nullable |
| user_note | text | optional user annotation |
| screenshot_url | text | S3 URL |
| source | text | "extension" or "api" |
| status | text | "pending", "enriched", "failed" |
| created_at | timestamptz | |
| UNIQUE(user_id, url) | | no duplicate saves |

### Screenshots
Stored in S3 bucket `viralpulse-screenshots`, keyed by `{user_id}/{post_id}.png`.

## API Endpoints

### User Management

```
POST /api/v1/users
  Body: {name, email?}
  Returns: {id, api_key, name}
```

### Save Posts

```
POST /api/v1/save
  Header: X-API-Key: vp_abc123...
  Body: {
    url: "https://x.com/OpenAI/status/123",
    screenshot_base64?: "iVBOR...",        // from Chrome extension
    metadata?: {author, content, engagement, hashtags, published_at},
    user_note?: "great hook pattern"
  }
  Returns: {id, status: "enriched" | "pending"}
```

If `screenshot_base64` is provided (Chrome extension): store immediately, status = "enriched".
If no screenshot (raw URL): store as "pending", background VM captures screenshot + metadata.

### Retrieve Saved Posts

```
GET /api/v1/saved
  Header: X-API-Key: vp_abc123...
  Params: ?query=...&platform=...&limit=20
  Returns: {count, posts: [{id, url, platform, author, content, engagement, screenshot_url, user_note, created_at}]}
```

Query searches across: content, author, hashtags, user_note (full-text search).

### Delete Saved Post

```
DELETE /api/v1/saved/{post_id}
  Header: X-API-Key: vp_abc123...
```

## Auth

Simple API key in `X-API-Key` header. Lookup user from key. No sessions, no OAuth.

## Chrome Extension

**Manifest V3** with these components:

### Popup
- "Save to ViralPulse" button
- Optional note text field
- Settings: paste API key once (stored in `chrome.storage.sync`)
- Success/error feedback

### Content Script
Injected on all pages. Two types of extractors:

**Platform-specific** (structured engagement data):
- `x.com` / `twitter.com` — author, tweet text, likes, retweets, replies, views
- `reddit.com` — author, title, body, upvotes, comments
- `tiktok.com` — author, caption, likes, comments, shares, views
- `instagram.com` — author, caption, likes, comments, views
- `youtube.com` — channel, title, description, views, likes, comments
- `linkedin.com` — author, text, reactions, comments

**Generic** (any other webpage):
- `og:title`, `og:description`, `og:image` from meta tags
- `<meta name="author">` or byline detection
- `<article>` or `<main>` body text
- `<time>` elements for publish date
- Page title as fallback

### Background Service Worker
1. Content script sends extracted metadata
2. `chrome.tabs.captureVisibleTab()` → screenshot as base64 PNG
3. POSTs `{url, screenshot_base64, metadata, user_note}` to API
4. Returns success/failure to popup

## VM Screenshot Fallback

For URLs saved via API without a screenshot:

1. Background thread receives pending URL
2. Opens in Playwright headless Chromium (existing Xvfb + Playwright MCP on VM)
3. Waits for page load, scrolls to load lazy content
4. `page.screenshot(full_page=True)` → PNG
5. Extracts text from DOM (same extractors as Chrome ext)
6. Uploads screenshot to S3
7. Updates saved_post: status → "enriched", fills metadata fields

**Limitations:**
- Login-walled content captures the login page
- Some platforms block headless browsers
- 30 second timeout per URL, then status → "failed"

## Platform Detection

Auto-detect from URL hostname:
```
x.com, twitter.com → "twitter"
reddit.com → "reddit"
tiktok.com → "tiktok"
instagram.com → "instagram"
youtube.com, youtu.be → "youtube"
linkedin.com → "linkedin"
everything else → "web"
```

## Agent Skill Integration

Updated `viral-writer.md` adds a section:

```
If the user provides a ViralPulse API key, also fetch their saved posts:
GET /api/v1/saved?query={topic}&limit=20
Header: X-API-Key: {user's key}

These are posts the user personally curated. Weight them higher than
trending data — the user saved them because they represent the style,
format, or voice they want to emulate.
```

## Build Order

1. DB tables (users, saved_posts) + API endpoints (save, saved, delete, users)
2. S3 screenshot storage
3. VM fallback screenshot service (Playwright)
4. Chrome extension (popup, content scripts, background worker)
5. Updated agent skill file

## Tech Stack

- **DB:** Existing Neon Postgres (new tables)
- **Storage:** AWS S3 (viralpulse-screenshots bucket)
- **VM screenshots:** Playwright + Xvfb (already running on VM)
- **Chrome extension:** Manifest V3, vanilla JS
- **API:** Existing FastAPI app (new endpoints)
