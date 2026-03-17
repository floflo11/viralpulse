# Smart Extraction — Design Spec

## Overview

Upgrade the Chrome extension save flow from screenshot-based to structured data extraction. When a founder clicks Save on a post, the extension auto-expands truncated text, extracts full content + metadata + engagement numbers, downloads images to S3, and shows a confirmation card before saving.

## User Flow

1. Founder sees a post worth saving on X/Reddit/LinkedIn/YouTube/etc.
2. Clicks the "Save" button (injected next to native like/share buttons)
3. Extension auto-clicks "See more" if post is truncated, waits for expansion
4. Extracts: full text, author, permalink, engagement numbers, images, video thumbnail
5. Shows confirmation card at bottom: text preview, first image thumbnail, author, engagement, note field + tags
6. Founder clicks "Looks good" → images upload to S3 in background → toast "Saved!"
7. Or clicks "Retry" to re-extract if expansion didn't complete

## Per-Platform Expand + Extract

### X/Twitter
- **Expand:** click `[data-testid="tweet-text-show-more-link"]` or span containing "Show more"
- **Text:** `[data-testid="tweetText"]`
- **Images:** `[data-testid="tweetPhoto"] img` src attribute
- **Video:** `video[poster]` attribute or `[data-testid="videoPlayer"] img`
- **Engagement:** parse action bar (likes, retweets, replies, views)
- **URL:** `a[href*="/status/"]` → construct permalink

### Reddit
- **Expand:** click button containing "more" within post body
- **Text:** post title `[data-testid="post-title"]` + body `[slot="text-body"]`
- **Images:** `img` within post (filter size > 100px to skip icons)
- **Engagement:** `[data-testid="post-score"]` for upvotes, comments count
- **URL:** `a[href*="/comments/"]`

### LinkedIn
- **Expand:** click `.feed-shared-inline-show-more-text` or button with "see more"
- **Text:** `.feed-shared-text` or `.update-components-text`
- **Images:** `.feed-shared-image img` or `[data-urn] img`
- **Engagement:** reactions + comments from `.social-details-social-counts`
- **URL:** `a[href*="/feed/update/"]`

### YouTube
- **Expand:** click `#expand` or "...more" in description
- **Text:** title `h1.ytd-watch-metadata` + description `#description-inner`
- **Thumbnail:** `og:image` meta or `/vi/{id}/maxresdefault.jpg`
- **Engagement:** likes, views from info bar
- **URL:** `window.location.href`

### TikTok
- **Text:** `[data-e2e="browse-video-desc"]`
- **Video thumbnail:** video poster attribute
- **Engagement:** likes, comments, shares from action bar
- **URL:** `window.location.href`

### Instagram
- **Text:** caption from `h1` or `span[dir="auto"]`
- **Images:** article img tags
- **Engagement:** likes, comments from section buttons
- **URL:** `window.location.href`

### Generic (any other site)
- **No expand needed**
- **Text:** `og:title` + `og:description` + `<article>` body text
- **Images:** `og:image` meta tag or first large img in article
- **Author:** `meta[name="author"]`
- **URL:** `window.location.href`

## Confirmation Card UI

Floating card at bottom center of screen:

```
┌──────────────────────────────────────────────┐
│ [Platform badge] @author                     │
│                                              │
│ "First two lines of extracted text appear    │
│  here as a preview..."                       │
│                                              │
│ [image thumb]  ♥ 23.6K  💬 450  ↗ 3.3K     │
│                                              │
│ [note field - collapsed, click to expand]    │
│                                              │
│  [✓ Looks good]           [↻ Retry]         │
└──────────────────────────────────────────────┘
```

- Appears after extraction completes (~300ms)
- Note field + tag pills hidden by default, expandable with "Add note ▸" link
- "Looks good" triggers S3 upload + API save
- "Retry" re-runs expand + extract
- Auto-dismisses 3s after "Looks good"
- ESC or click outside dismisses without saving

## Data Model Changes

Add columns to existing `saved_posts` table:

```sql
ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS images JSONB DEFAULT '[]';
ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS video_thumbnail TEXT;
ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS video_url TEXT;
```

- `images` — array of S3 URLs for downloaded post images (max 5)
- `video_thumbnail` — S3 URL for video poster/thumbnail
- `video_url` — original video URL (not downloaded, too large)
- `engagement` — already exists as JSONB, now populated from DOM extraction
- `screenshot_url` — kept for backward compat, no longer captured by default

## Image Storage

- Same S3 bucket: `viralpulse-screenshots`
- Key pattern: `{user_id}/{post_id}/img_{n}.png` for images
- Key pattern: `{user_id}/{post_id}/video_thumb.png` for video thumbnails
- Max 5 images per post
- Images fetched client-side, sent as base64 to API alongside metadata
- API uploads to S3, stores URLs in `images` JSONB array

## API Changes

`POST /api/v1/save` body updated:

```json
{
  "url": "https://x.com/...",
  "metadata": {
    "author": "@OpenAI",
    "content": "Full expanded text...",
    "engagement": {"likes": 23600, "comments": 450},
    "hashtags": ["AI"],
    "images_base64": ["data:image/png;base64,..."],
    "video_thumbnail_base64": "data:image/png;base64,...",
    "video_url": "https://x.com/video/..."
  },
  "user_note": "great hook #hook",
  "screenshot_base64": null
}
```

API handles:
1. Store text metadata immediately
2. Upload each image from base64 to S3
3. Upload video thumbnail to S3
4. Update `saved_posts` row with S3 URLs

## Build Order

1. DB migration — add `images`, `video_thumbnail`, `video_url` columns
2. API update — handle `images_base64` and `video_thumbnail_base64` in save endpoint
3. Content script rewrite — per-platform expand + extract + image capture
4. Confirmation card UI
5. Update `/view/saved` to display images inline
6. Test on X, Reddit, LinkedIn

## Tech Stack

- Chrome extension content script (vanilla JS)
- Existing FastAPI + S3 + Neon Postgres
- No new dependencies
