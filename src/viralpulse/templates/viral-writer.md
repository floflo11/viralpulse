---
name: viral-writer
description: Write viral social media posts by studying real top-performing content from Freedom API
---

# Viral Writer Skill

Write social media posts with the highest chance of going viral by studying what's actually performing right now.

## How It Works

1. Fetch the top viral posts for the user's topic from Freedom
2. Analyze what makes them perform — hooks, format, length, hashtags, engagement patterns
3. Generate new content that follows the winning patterns

## API

**Base URL:** `{{API_HOST}}/api/v1`

**Get top viral posts for a topic:**
```
GET /api/v1/posts?topic={topic}&sort=engagement&limit=20
```

**Filter by platform:**
```
GET /api/v1/posts?topic={topic}&platform=tiktok&sort=engagement&limit=20
```

Platforms: `reddit`, `tiktok`, `instagram`, `youtube`
Sort options: `composite` (balanced), `engagement` (most likes/views), `velocity` (fastest growing), `recent` (newest)

## Instructions

When the user asks you to write a viral post, tweet, caption, or any social media content:

### Step 1: Fetch viral examples

Call the Freedom API to get the top 20 posts for the user's topic, sorted by engagement:

```bash
curl "{{API_HOST}}/api/v1/posts?topic=TOPIC&sort=engagement&limit=20"
```

If the user specifies a platform (e.g. "write a viral TikTok caption"), filter by platform:

```bash
curl "{{API_HOST}}/api/v1/posts?topic=TOPIC&platform=tiktok&sort=engagement&limit=20"
```

### Step 2: Analyze the patterns

Study the top posts and identify:

- **Hooks** — How do the top posts open? What grabs attention in the first line?
- **Format** — Short vs long? Lists? Questions? Stories? Thread-style?
- **Tone** — Casual, authoritative, controversial, educational, humorous?
- **Hashtags** — Which hashtags appear in the highest-performing posts?
- **Engagement triggers** — What drives comments? (Questions, hot takes, "what do you think?")
- **Content type** — Tutorial, opinion, news, personal story, comparison?
- **Length** — What's the sweet spot for this topic and platform?
- **Timing patterns** — Are the top posts from certain days/times?

### Step 3: Generate the post

Write the content following the patterns you identified. For each post:

1. Lead with the strongest hook pattern you observed
2. Match the format and length of top performers
3. Use proven hashtags from the viral examples
4. Include an engagement trigger (question, CTA, or hot take)
5. Match the tone that resonates in this niche

### Step 4: Explain your reasoning

Tell the user:
- Which viral posts inspired your approach
- What specific patterns you're leveraging
- The engagement data behind your choices (e.g. "Posts with this hook format averaged 50K views")

## Example

**User:** "Write me a viral TikTok caption about AI video editing"

**You:**
1. Fetch: `GET /api/v1/posts?topic=AI+video+editing&platform=tiktok&sort=engagement&limit=20`
2. Analyze: Top posts use "This AI tool..." hooks, short punchy sentences, 3-5 hashtags, and end with a CTA
3. Generate the caption following those patterns
4. Explain: "Based on 20 viral TikToks about AI video editing (top post: 516K views, 33K likes), I used the 'This [tool] just changed everything' hook which appears in 4 of the top 10 posts..."

## Using the user's saved posts

If the user provides a Freedom API key, also fetch their personal collection:

```
GET /api/v1/saved?query={topic}&limit=20
Header: X-API-Key: {user's key}
```

These are posts the user personally curated as examples of great content.
Weight these higher than trending data — the user saved them because they
represent the style, format, or voice they want to emulate.

Combine both sources:
1. `GET /api/v1/posts?topic=...&limit=20` — what's trending (public data, no auth needed)
2. `GET /api/v1/saved?query=...&limit=20` — what the user has been collecting (requires API key)

The user's saved posts include `screenshot_url` — if using Claude vision,
you can analyze the visual format and layout of the original posts.

The `limit` parameter is configurable: use `limit=5` for a quick scan or `limit=100` for deep research.

## Notes

- The API returns real engagement numbers (views, likes, comments, shares) — use these to back up your choices
- Data is refreshed daily — patterns reflect what's working RIGHT NOW
- If a topic has no data yet, the search will crawl it live (takes ~30 seconds)
- Public trending data (`/api/v1/posts`) requires no API key
- Saved posts (`/api/v1/saved`) require the user's `X-API-Key` header
