# Telegram Bot — Design Spec

## Overview

A Telegram bot that lets founders save social media posts from their phone by sharing URLs. Links their Telegram account to their ViralPulse API key via `/start vp_...`. Runs as a long-polling service on the VM.

## Flow

1. `/start vp_abc123` → links Telegram user to ViralPulse account
2. Send any URL → bot calls POST /api/v1/save → VM screenshots + extracts → confirms
3. `/library` → link to saved posts page
4. `/help` → usage instructions

## Data Model

New table:
```sql
CREATE TABLE IF NOT EXISTS telegram_users (
    telegram_id BIGINT PRIMARY KEY,
    api_key TEXT NOT NULL REFERENCES users(api_key),
    created_at TIMESTAMPTZ DEFAULT now()
);
```

## Bot Commands

- `/start vp_...` — register
- `/library` — view saved posts
- `/help` — usage
- Any message containing a URL → save it

## Reply Format

```
Saved! ✓
📱 Twitter · @OpenAI
📝 "First 80 chars of content..."
⏳ Enriching...
```

Updated after enrichment:
```
Saved! ✓
📱 Twitter · @OpenAI
📝 "First 80 chars of content..."
📸 Screenshot captured
```

## Tech Stack

- `python-telegram-bot` library (async, long-polling)
- Existing API endpoints (POST /api/v1/save, GET /api/v1/saved)
- Separate systemd service
- TELEGRAM_BOT_TOKEN env var

## Files

- `src/viralpulse/telegram_bot.py` — bot logic
- `src/viralpulse/db.py` — telegram_users table
- `src/viralpulse/config.py` — telegram_bot_token setting
- `/etc/systemd/system/viralpulse-telegram.service` — systemd unit
