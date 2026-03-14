# ViralPulse — Design Spec

## Overview

ViralPulse is a data API that provides the top 20 viral posts per social media platform for any tracked topic. AI agents consume the API to get real-world examples of high-performing content in a given domain, improving their ability to generate content with viral potential.

A secondary interface is a Next.js dashboard for humans to browse cross-platform trending content.

## Target Users

- **Primary:** AI agents/LLMs that need viral content examples as context for content generation
- **Secondary:** Humans browsing a cross-platform news/trends dashboard

## Platforms

1. X/Twitter
2. Reddit
3. TikTok
4. Instagram
5. LinkedIn
6. YouTube

All accessed via **ScrapeCreators API** (one key, all platforms). Cost: ~1 credit/request, $47/25K credits.

## Architecture

```
Daily Cron (VM: 5.161.65.234)
    │
    ▼
┌─────────────────┐      ┌──────────────────┐
│  Crawler         │─────▶│  Neon PostgreSQL  │
│  Python + cron   │      └────────┬─────────┘
│  ScrapeCreators  │               │
└─────────────────┘    ┌───────────┼───────────┐
                       ▼                       ▼
             ┌─────────────────┐     ┌─────────────────┐
             │  FastAPI (Modal) │     │  Next.js (Vercel)│
             │  JSON API        │     │  Dashboard       │
             └─────────────────┘     └─────────────────┘
                       ▲
                 AI Agents / LLMs
```

### Components

1. **Crawler** — Python script on VM, daily cron. Fetches top posts per topic per platform from ScrapeCreators, normalizes, scores, writes to Neon Postgres.
2. **Database** — Neon PostgreSQL. Topics, posts, engagement snapshots, precomputed scores.
3. **API** — FastAPI deployed on Modal. Stateless reads from Neon. No auth initially.
4. **Dashboard** — Next.js on Vercel. Reads from API. Cross-platform feed with topic/platform filters.

## Data Model

### topics
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| name | text | unique, e.g. "AI video tools" |
| search_queries | jsonb | expanded queries per platform |
| enabled | bool | default true |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### posts
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| topic_id | uuid | FK → topics |
| platform | text | twitter, reddit, tiktok, instagram, linkedin, youtube |
| platform_id | text | native post ID |
| url | text | unique |
| author | text | |
| author_url | text | nullable |
| title | text | nullable (Reddit/YouTube have titles) |
| content | text | post body / caption |
| media_url | text | nullable, thumbnail or video URL |
| published_at | timestamptz | |
| fetched_at | timestamptz | |
| raw_data | jsonb | full ScrapeCreators response |

### engagement
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| post_id | uuid | FK → posts |
| snapshot_at | timestamptz | when captured |
| likes | int | |
| comments | int | |
| shares | int | |
| views | int | |
| platform_score | int | Reddit score, etc. |

### scores
| Column | Type | Notes |
|--------|------|-------|
| post_id | uuid | FK → posts, unique |
| relevance | float | keyword match quality 0-1 |
| engagement_normalized | float | cross-platform comparable 0-1 |
| velocity | float | engagement relative to post age 0-1 |
| composite | float | weighted final score 0-1 |

**Deduplication:** On re-crawl, existing posts (matched by `url`) get a new engagement snapshot but are not duplicated. Scores are recalculated.

## Scoring Algorithm

Borrowed from last30days patterns:

- **Relevance (0-1):** Bidirectional token overlap between search query and post content, with synonym expansion and stopword removal.
- **Engagement normalized (0-1):** Per-platform percentile normalization. A post with 5K likes on X is compared to other X posts in the same topic, not to Reddit scores.
- **Velocity (0-1):** `engagement / hours_since_published`. Normalized across the result set. Catches rising content vs. old established posts.
- **Composite (0-1):** `0.3 * relevance + 0.4 * engagement_normalized + 0.3 * velocity`. Configurable weights.

## API Design

**Base:** Deployed on Modal.

### Endpoints

```
GET /api/v1/posts
  ?topic=ai+video+tools        (required)
  ?platform=twitter             (optional, omit = all platforms)
  ?sort=composite|engagement|velocity|relevance|recent  (default: composite)
  ?limit=20                     (default: 20, max: 100)
  ?days=30                      (default: 30)

GET /api/v1/posts/{post_id}     (single post + engagement history)
GET /api/v1/topics              (list tracked topics)
GET /api/v1/platforms           (platform list + health)
GET /api/v1/health              (service health)
```

### Response: GET /api/v1/posts

```json
{
  "topic": "ai video tools",
  "platform": "all",
  "sort": "composite",
  "count": 20,
  "fetched_at": "2026-03-14T08:00:00Z",
  "posts": [
    {
      "id": "...",
      "platform": "twitter",
      "url": "https://x.com/user/status/123",
      "author": "@creator",
      "author_url": "https://x.com/creator",
      "title": null,
      "content": "This AI video tool changed everything...",
      "media_url": "https://...",
      "published_at": "2026-03-12T14:30:00Z",
      "engagement": {
        "likes": 5200,
        "comments": 340,
        "shares": 890,
        "views": 125000
      },
      "scores": {
        "composite": 0.94,
        "relevance": 0.88,
        "engagement_normalized": 0.97,
        "velocity": 0.91
      }
    }
  ]
}
```

## Crawler Design

### Daily flow per topic:

1. For each enabled topic, for each platform:
   - Call ScrapeCreators search endpoint with topic's search queries
   - Parse response into normalized post objects
2. Deduplicate against existing posts (by URL)
3. For new posts: insert post + engagement snapshot + compute scores
4. For existing posts: add new engagement snapshot + recompute scores
5. Log run stats (new/updated counts, errors, duration)

### ScrapeCreators endpoints used:

- `GET /v1/twitter/search?query=...`
- `GET /v1/reddit/search?query=...`
- `GET /v1/tiktok/search?query=...`
- `GET /v1/instagram/search?query=...`
- `GET /v1/linkedin/search?query=...`
- `GET /v1/youtube/search?query=...`

### Error handling:

- Per-platform failures don't block other platforms
- Retry once on timeout/5xx
- Log errors, continue to next topic

## CLI for Topic Management

```bash
# Add a topic
python -m viralpulse.cli topic add "AI video tools"

# List topics
python -m viralpulse.cli topic list

# Remove a topic
python -m viralpulse.cli topic remove "AI video tools"

# Manual crawl (all topics)
python -m viralpulse.cli crawl

# Manual crawl (single topic)
python -m viralpulse.cli crawl --topic "AI video tools"

# Check ScrapeCreators credit balance
python -m viralpulse.cli status
```

## Dashboard (Next.js)

Cross-platform news feed:
- Filter by topic (dropdown)
- Filter by platform (toggle chips)
- Sort by composite / engagement / velocity / recent
- Card-based layout showing post content, author, engagement metrics, platform badge, score
- Auto-refreshes from API

## Tech Stack

- **Language:** Python 3.11+
- **Package manager:** uv
- **Crawler:** Python + cron on VM
- **DB:** Neon PostgreSQL (free tier to start)
- **API:** FastAPI on Modal
- **Dashboard:** Next.js on Vercel
- **Data source:** ScrapeCreators (one API key)

## Cost Estimate

- **ScrapeCreators:** 6 platforms × 1 credit × N topics × 1/day = 6N credits/day
  - 10 topics: 60 credits/day → $47 lasts ~416 days
  - 50 topics: 300 credits/day → $47 lasts ~83 days
- **Neon:** Free tier (0.5 GB storage, 190 compute hours/month)
- **Modal:** Free tier ($30/month credits)
- **Vercel:** Free tier (hobby)
