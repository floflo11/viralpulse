"""ViralPulse Telegram Bot — save posts by sharing URLs."""

import json
import logging
import re
from typing import Optional

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from viralpulse.config import settings
from viralpulse.db import get_conn, init_db
from viralpulse.platform_detect import detect_platform

logger = logging.getLogger("viralpulse.telegram")

API_BASE = "https://api.aithatjustworks.com"

URL_REGEX = re.compile(r'https?://\S+')


# ── DB helpers ──

def get_api_key(telegram_id: int) -> Optional[str]:
    """Get the API key linked to a Telegram user."""
    conn = get_conn()
    row = conn.execute(
        "SELECT api_key FROM telegram_users WHERE telegram_id = %s",
        (telegram_id,),
    ).fetchone()
    conn.close()
    return row["api_key"] if row else None


def link_user(telegram_id: int, api_key: str) -> bool:
    """Link a Telegram user to a ViralPulse API key. Returns True if key is valid."""
    # Verify key exists
    conn = get_conn()
    user = conn.execute("SELECT id FROM users WHERE api_key = %s", (api_key,)).fetchone()
    if not user:
        conn.close()
        return False

    conn.execute(
        """INSERT INTO telegram_users (telegram_id, api_key)
           VALUES (%s, %s)
           ON CONFLICT (telegram_id) DO UPDATE SET api_key = EXCLUDED.api_key""",
        (telegram_id, api_key),
    )
    conn.commit()
    conn.close()
    return True


# ── Handlers ──

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start vp_... command."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Welcome to Freedom!\n\n"
            "To connect, send your key:\n"
            "/start 42-swift-tiger\n\n"
            "Get your key at https://api.aithatjustworks.com"
        )
        return

    # Support both old (vp_...) and new (42-word-word) format
    api_key = " ".join(args)  # Handle spaces in case key was split
    if link_user(update.effective_user.id, api_key):
        await update.message.reply_text(
            "Connected! ✓\n\n"
            "Send me any URL to save it to your library.\n"
            "Just share a link from X, Reddit, LinkedIn, YouTube, TikTok, or any website."
        )
    else:
        await update.message.reply_text(
            "Invalid API key. Please check your key and try again.\n"
            "Get your key at https://api.aithatjustworks.com"
        )


async def cmd_library(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /library command."""
    api_key = get_api_key(update.effective_user.id)
    if not api_key:
        await update.message.reply_text("Not connected yet. Send /start vp_YOUR_API_KEY first.")
        return

    await update.message.reply_text(
        f"Your library:\nhttps://api.aithatjustworks.com/view/saved?key={api_key}"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "ViralPulse Bot\n\n"
        "Commands:\n"
        "/start vp_KEY — Connect your account\n"
        "/library — View your saved posts\n"
        "/help — Show this message\n\n"
        "Usage:\n"
        "Just send me any URL and I'll save it to your library.\n"
        "Your AI agent can then use these posts as references for creating viral content."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any message — look for URLs to save."""
    text = update.message.text or ""
    urls = URL_REGEX.findall(text)

    if not urls:
        await update.message.reply_text(
            "Send me a URL to save it. For example, share a tweet or Reddit post link."
        )
        return

    api_key = get_api_key(update.effective_user.id)
    if not api_key:
        await update.message.reply_text("Not connected yet. Send /start vp_YOUR_API_KEY first.")
        return

    for url in urls[:3]:  # Max 3 URLs per message
        platform = detect_platform(url)
        platform_labels = {
            "twitter": "X/Twitter", "reddit": "Reddit", "tiktok": "TikTok",
            "instagram": "Instagram", "youtube": "YouTube", "linkedin": "LinkedIn", "web": "Web",
        }
        plat_label = platform_labels.get(platform, "Web")

        # Send initial "saving" message
        msg = await update.message.reply_text(
            f"Saving...\n"
            f"📱 {plat_label}\n"
            f"🔗 {url[:60]}{'...' if len(url) > 60 else ''}\n"
            f"⏳ Extracting content..."
        )

        # Call the save API
        try:
            # Extract any note from the message (text before/after the URL)
            note_text = text.replace(url, "").strip()

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{API_BASE}/api/v1/save",
                    json={
                        "url": url,
                        "metadata": {"content": "", "author": ""},
                        "user_note": note_text if note_text else None,
                    },
                    headers={"X-API-Key": api_key},
                )

            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "pending")

                if status == "pending":
                    # VM will enrich in background
                    await msg.edit_text(
                        f"Saved! ✓\n"
                        f"📱 {plat_label}\n"
                        f"🔗 {url[:60]}{'...' if len(url) > 60 else ''}\n"
                        f"📸 Screenshot capturing in background...\n"
                        f"{('📝 Note: ' + note_text) if note_text else ''}"
                    )
                else:
                    await msg.edit_text(
                        f"Saved! ✓\n"
                        f"📱 {plat_label}\n"
                        f"🔗 {url[:60]}{'...' if len(url) > 60 else ''}\n"
                        f"✅ Content captured\n"
                        f"{('📝 Note: ' + note_text) if note_text else ''}"
                    )
            else:
                error = resp.json().get("detail", "Unknown error")
                await msg.edit_text(f"Failed to save: {error}")

        except Exception as e:
            logger.error(f"Save failed for {url}: {e}")
            await msg.edit_text(f"Failed to save: {str(e)[:100]}")


# ── Main ──

def run_bot():
    """Start the Telegram bot (blocking, long-polling)."""
    token = settings.telegram_bot_token
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return

    init_db()
    logger.info("Starting ViralPulse Telegram bot...")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("library", cmd_library))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_bot()
