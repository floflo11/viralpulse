"""VM screenshot service using Playwright headless browser."""

import logging
import re
from typing import Optional, Tuple
from playwright.sync_api import sync_playwright

logger = logging.getLogger("viralpulse.screenshot")


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
            page.wait_for_timeout(2000)

            # Scroll to load lazy content
            page.evaluate("window.scrollBy(0, 800)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)

            # Take screenshot
            screenshot = page.screenshot(full_page=False)

            # Extract metadata
            try:
                metadata["content"] = page.evaluate("""() => {
                    const og = document.querySelector('meta[property="og:description"]');
                    if (og) return og.content;
                    const article = document.querySelector('article, main, [role="main"]');
                    if (article) return article.innerText.slice(0, 3000);
                    return document.title;
                }""") or ""

                metadata["author"] = page.evaluate("""() => {
                    const author = document.querySelector('meta[name="author"]');
                    const byline = document.querySelector('[rel="author"], .author, .byline');
                    const og = document.querySelector('meta[property="og:site_name"]');
                    return author?.content || byline?.innerText || og?.content || '';
                }""") or ""

                title = page.title() or ""
                if title and not metadata["content"]:
                    metadata["content"] = title

                metadata["hashtags"] = re.findall(r'#(\w+)', metadata["content"])

            except Exception as e:
                logger.warning(f"Metadata extraction failed for {url}: {e}")

            browser.close()
            return screenshot, metadata

    except Exception as e:
        logger.error(f"Screenshot capture failed for {url}: {e}")
        return None, metadata
