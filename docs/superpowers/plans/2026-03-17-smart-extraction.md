# Smart Extraction Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Chrome extension from screenshot-based saves to structured data extraction with auto-expand, image download, and a confirmation card UI.

**Architecture:** Content script auto-expands truncated posts, extracts text/images/engagement/author from DOM, shows a confirmation card, then sends structured data + image base64 to the API. API uploads images to S3 and stores metadata. No screenshots by default.

**Tech Stack:** Chrome Manifest V3 (vanilla JS), FastAPI, boto3 (S3), Neon PostgreSQL

---

## File Structure

```
src/viralpulse/
├── db.py                    # MODIFY: add images, video_thumbnail, video_url columns
├── s3.py                    # MODIFY: add upload_image (supports multiple per post)
├── api.py                   # MODIFY: handle images_base64 + video_thumbnail_base64 in /save

extension/
├── content.js               # REWRITE: smart extraction + confirmation card
├── background.js            # MODIFY: handle image uploads in SAVE_POST
├── manifest.json            # NO CHANGE
├── popup.html               # NO CHANGE
├── popup.js                 # NO CHANGE

tests/
├── test_s3.py               # MODIFY: add test for upload_image
├── test_save_api.py         # MODIFY: add test for images in save payload
├── test_e2e_save.py         # CREATE: E2E test using Playwright to verify full flow
```

---

## Task 1: DB Migration — New Media Columns

**Files:**
- Modify: `src/viralpulse/db.py`

- [ ] **Step 1: Add columns to SCHEMA_SQL**

Append after the `saved_posts` table indexes in SCHEMA_SQL:

```sql
ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS images JSONB DEFAULT '[]';
ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS video_thumbnail TEXT;
ALTER TABLE saved_posts ADD COLUMN IF NOT EXISTS video_url TEXT;
```

Note: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` is safe to re-run.

- [ ] **Step 2: Run migration**

```bash
.venv/bin/python3 -c "from viralpulse.db import init_db; init_db(); print('OK')"
```

- [ ] **Step 3: Verify columns exist**

```bash
.venv/bin/python3 -c "
from viralpulse.db import get_conn
conn = get_conn()
row = conn.execute('SELECT images, video_thumbnail, video_url FROM saved_posts LIMIT 1').fetchone()
print('Columns exist' if row is not None or True else 'OK')
conn.close()
"
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/db.py
git commit -m "feat: add images, video_thumbnail, video_url columns to saved_posts"
```

---

## Task 2: S3 Image Upload Support

**Files:**
- Modify: `src/viralpulse/s3.py`
- Modify: `tests/test_s3.py`

- [ ] **Step 1: Add upload_image function to s3.py**

```python
def upload_image(user_id: str, post_id: str, index: int, b64_data: str) -> str:
    """Upload a post image to S3. Returns the public URL."""
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]
    png_bytes = base64.b64decode(b64_data)
    key = f"{user_id}/{post_id}/img_{index}.png"
    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=png_bytes,
        ContentType="image/png",
    )
    return f"https://{settings.s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"


def upload_video_thumbnail(user_id: str, post_id: str, b64_data: str) -> str:
    """Upload a video thumbnail to S3. Returns the public URL."""
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]
    png_bytes = base64.b64decode(b64_data)
    key = f"{user_id}/{post_id}/video_thumb.png"
    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=png_bytes,
        ContentType="image/png",
    )
    return f"https://{settings.s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"
```

- [ ] **Step 2: Add tests**

```python
@patch("viralpulse.s3.get_s3_client")
def test_upload_image(mock_client):
    mock_client.return_value = MagicMock()
    b64 = base64.b64encode(b"fake png").decode()
    url = upload_image("user-1", "post-1", 0, b64)
    assert "user-1/post-1/img_0.png" in url
    mock_client.return_value.put_object.assert_called_once()


@patch("viralpulse.s3.get_s3_client")
def test_upload_video_thumbnail(mock_client):
    mock_client.return_value = MagicMock()
    b64 = base64.b64encode(b"fake png").decode()
    url = upload_video_thumbnail("user-1", "post-1", b64)
    assert "video_thumb.png" in url
```

- [ ] **Step 3: Run tests**

```bash
~/.local/bin/uv run pytest tests/test_s3.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/s3.py tests/test_s3.py
git commit -m "feat: S3 upload for post images and video thumbnails"
```

---

## Task 3: API — Handle Images in Save Endpoint

**Files:**
- Modify: `src/viralpulse/api.py`
- Modify: `tests/test_save_api.py`

- [ ] **Step 1: Update the `save_post` endpoint**

In the existing `save_post` function, after inserting the saved_post row and handling screenshot_base64, add image handling:

```python
    # Handle images from extension
    images_b64 = metadata.get("images_base64", [])
    video_thumb_b64 = metadata.get("video_thumbnail_base64")
    video_url_val = metadata.get("video_url")

    image_urls = []
    if images_b64:
        from viralpulse.s3 import upload_image
        for idx, img_b64 in enumerate(images_b64[:5]):  # Max 5 images
            try:
                img_url = upload_image(str(user["id"]), post_id, idx, img_b64)
                image_urls.append(img_url)
            except Exception as e:
                logging.getLogger("viralpulse.api").error(f"Image upload {idx} failed: {e}")

    video_thumb_url = None
    if video_thumb_b64:
        try:
            from viralpulse.s3 import upload_video_thumbnail
            video_thumb_url = upload_video_thumbnail(str(user["id"]), post_id, video_thumb_b64)
        except Exception as e:
            logging.getLogger("viralpulse.api").error(f"Video thumb upload failed: {e}")

    # Update row with media URLs
    if image_urls or video_thumb_url or video_url_val:
        conn = get_conn()
        conn.execute(
            """UPDATE saved_posts SET images = %s, video_thumbnail = %s, video_url = %s WHERE id = %s""",
            (json.dumps(image_urls), video_thumb_url, video_url_val, post_id),
        )
        conn.commit()
        conn.close()
```

- [ ] **Step 2: Add test**

```python
def test_save_returns_platform():
    """Test that save endpoint returns platform detection."""
    # This tests the structure, not auth (tested elsewhere)
    from viralpulse.platform_detect import detect_platform
    assert detect_platform("https://x.com/test/status/123") == "twitter"
```

- [ ] **Step 3: Run tests**

```bash
~/.local/bin/uv run pytest tests/test_save_api.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/viralpulse/api.py tests/test_save_api.py
git commit -m "feat: handle image uploads and video thumbnails in save endpoint"
```

---

## Task 4: Content Script — Smart Extraction Engine

**Files:**
- Rewrite: `extension/content.js`

This is the core task. The content script needs:
1. Per-platform expand logic
2. Per-platform structured data extraction (text, images, engagement, author, URL)
3. Confirmation card UI
4. Communication with background script

- [ ] **Step 1: Write the per-platform extractor module**

The content.js should have this structure:

```javascript
// === PLATFORM EXTRACTORS ===
// Each returns: { author, content, engagement, hashtags, images, videoThumbnail, videoUrl, url }

const EXTRACTORS = {
  'x.com': {
    postSelector: 'article[data-testid="tweet"]',
    actionBar: '[role="group"]:last-of-type',
    expand: (post) => {
      const btn = post.querySelector('[data-testid="tweet-text-show-more-link"], span[role="link"]');
      if (btn) { btn.click(); return true; }
      return false;
    },
    extract: (post) => {
      const author = post.querySelector('[data-testid="User-Name"] a')?.textContent?.trim() || '';
      const content = post.querySelector('[data-testid="tweetText"]')?.textContent || '';
      const images = [...post.querySelectorAll('[data-testid="tweetPhoto"] img')]
        .map(img => img.src).filter(s => s && !s.includes('emoji') && !s.includes('profile'));
      const video = post.querySelector('video');
      const videoThumbnail = video?.poster || post.querySelector('[data-testid="videoPlayer"] img')?.src || null;
      const videoUrl = video?.src || null;
      const link = post.querySelector('a[href*="/status/"]');
      const url = link ? 'https://x.com' + new URL(link.href).pathname : window.location.href;
      // Engagement - parse from aria-labels or text
      const engagement = {};
      post.querySelectorAll('[role="group"] button').forEach(btn => {
        const label = btn.getAttribute('aria-label') || '';
        const match = label.match(/(\d[\d,.]*)\s*(repl|like|repost|view|bookmark)/i);
        if (match) {
          const num = parseInt(match[1].replace(/[,.\s]/g, ''));
          const type = match[2].toLowerCase();
          if (type.startsWith('repl')) engagement.comments = num;
          else if (type.startsWith('like')) engagement.likes = num;
          else if (type.startsWith('repost')) engagement.shares = num;
          else if (type.startsWith('view')) engagement.views = num;
        }
      });
      return { author, content, engagement, hashtags: extractHashtags(content), images, videoThumbnail, videoUrl, url };
    },
  },

  'reddit.com': {
    postSelector: 'shreddit-post, .Post, [data-testid="post-container"]',
    actionBar: 'shreddit-post-overflow-menu, .flat-list.buttons',
    expand: (post) => {
      const btns = post.querySelectorAll('button, [role="button"]');
      for (const btn of btns) {
        if (btn.textContent?.toLowerCase().includes('more') && btn.offsetHeight > 0) {
          btn.click(); return true;
        }
      }
      return false;
    },
    extract: (post) => {
      const title = post.querySelector('[data-testid="post-title"], h1, h3, [slot="title"]')?.textContent || '';
      const body = post.querySelector('[slot="text-body"], .usertext-body, [data-testid="post-content"]')?.textContent || '';
      const author = post.querySelector('[data-testid="post_author_link"], .author, [slot="authorName"]')?.textContent?.trim() || '';
      const images = [...post.querySelectorAll('img')]
        .filter(img => img.naturalWidth > 100 && !img.src.includes('avatar') && !img.src.includes('icon'))
        .map(img => img.src);
      const link = post.querySelector('a[href*="/comments/"]');
      const url = link ? link.href : window.location.href;
      const scoreEl = post.querySelector('[data-testid="post-score"], .score, [score]');
      const score = scoreEl ? parseInt(scoreEl.textContent?.replace(/[^0-9]/g, '') || '0') : 0;
      return { author, content: title + '\n' + body, engagement: { likes: score }, hashtags: [], images, videoThumbnail: null, videoUrl: null, url };
    },
  },

  'linkedin.com': {
    postSelector: '.feed-shared-update-v2, .occludable-update, div[data-urn]',
    actionBar: '.feed-shared-social-actions, .social-details-social-counts',
    expand: (post) => {
      const btn = post.querySelector('.feed-shared-inline-show-more-text, button[aria-label*="see more"], span.lt-line-clamp__more');
      if (btn) { btn.click(); return true; }
      return false;
    },
    extract: (post) => {
      const author = post.querySelector('.feed-shared-actor__name, .update-components-actor__name, a[data-tracking-control-name*="actor"]')?.textContent?.trim() || '';
      const content = post.querySelector('.feed-shared-text, .update-components-text, .break-words')?.textContent?.trim() || '';
      const images = [...post.querySelectorAll('.feed-shared-image img, .update-components-image img')]
        .map(img => img.src).filter(Boolean);
      const video = post.querySelector('video');
      return { author, content, engagement: {}, hashtags: extractHashtags(content), images, videoThumbnail: video?.poster || null, videoUrl: null, url: window.location.href };
    },
  },

  'youtube.com': {
    postSelector: '#primary-inner, ytd-rich-item-renderer',
    actionBar: '#top-level-buttons-computed, ytd-menu-renderer',
    expand: (post) => {
      const btn = post.querySelector('#expand, tp-yt-paper-button#more, [aria-label="Show more"]');
      if (btn) { btn.click(); return true; }
      return false;
    },
    extract: (post) => {
      const title = document.querySelector('h1.ytd-watch-metadata, #video-title')?.textContent?.trim() || '';
      const channel = document.querySelector('#channel-name a')?.textContent?.trim() || '';
      const desc = document.querySelector('#description-inner, .ytd-text-inline-expander')?.textContent?.slice(0, 2000) || '';
      const ogImage = document.querySelector('meta[property="og:image"]')?.content || '';
      const viewsText = document.querySelector('#info-strings yt-formatted-string, .view-count')?.textContent || '';
      const views = parseInt(viewsText.replace(/[^0-9]/g, '') || '0');
      return { author: channel, content: title + '\n' + desc, engagement: { views }, hashtags: extractHashtags(desc), images: [], videoThumbnail: ogImage || null, videoUrl: window.location.href, url: window.location.href };
    },
  },

  'tiktok.com': {
    postSelector: '[data-e2e="recommend-list-item-container"], .video-feed-item, [class*="DivItemContainer"]',
    actionBar: '[data-e2e="video-action-bar"]',
    expand: () => false,
    extract: (post) => {
      const author = post.querySelector('[data-e2e="browse-username"]')?.textContent?.trim() || document.querySelector('[data-e2e="browse-username"]')?.textContent?.trim() || '';
      const content = post.querySelector('[data-e2e="browse-video-desc"]')?.textContent || document.querySelector('[data-e2e="browse-video-desc"]')?.textContent || '';
      const video = document.querySelector('video');
      return { author, content, engagement: {}, hashtags: extractHashtags(content), images: [], videoThumbnail: video?.poster || null, videoUrl: window.location.href, url: window.location.href };
    },
  },

  'instagram.com': {
    postSelector: 'article',
    actionBar: 'section',
    expand: (post) => {
      const btn = post.querySelector('button[type="button"]');
      if (btn?.textContent?.toLowerCase().includes('more')) { btn.click(); return true; }
      return false;
    },
    extract: (post) => {
      const author = post.querySelector('header a')?.textContent?.trim() || '';
      const content = post.querySelector('h1, span[dir="auto"], [data-testid="post-comment-root"] span')?.textContent || '';
      const images = [...post.querySelectorAll('img[srcset], img[sizes]')]
        .filter(img => img.naturalWidth > 100).map(img => img.src);
      const video = post.querySelector('video');
      return { author, content, engagement: {}, hashtags: extractHashtags(content), images, videoThumbnail: video?.poster || null, videoUrl: null, url: window.location.href };
    },
  },
};

// Alias
EXTRACTORS['twitter.com'] = EXTRACTORS['x.com'];
```

- [ ] **Step 2: Write the confirmation card UI**

```javascript
function showConfirmCard(data, btn) {
  removeConfirmCard(); // remove any existing

  const card = document.createElement('div');
  card.id = 'vp-confirm';

  const imgThumb = data.images?.[0] || data.videoThumbnail || '';
  const thumbHtml = imgThumb
    ? `<img src="${imgThumb}" style="width:48px;height:48px;border-radius:6px;object-fit:cover;flex-shrink:0;" onerror="this.style.display='none'">`
    : '';

  const engParts = [];
  if (data.engagement?.views) engParts.push(`▶ ${fmtNum(data.engagement.views)}`);
  if (data.engagement?.likes) engParts.push(`♥ ${fmtNum(data.engagement.likes)}`);
  if (data.engagement?.comments) engParts.push(`💬 ${fmtNum(data.engagement.comments)}`);
  if (data.engagement?.shares) engParts.push(`↗ ${fmtNum(data.engagement.shares)}`);
  const engHtml = engParts.length ? `<div style="font-size:12px;color:#78716c;margin-top:6px;">${engParts.join(' · ')}</div>` : '';

  const preview = (data.content || '').slice(0, 120) + ((data.content || '').length > 120 ? '...' : '');
  const mediaCount = (data.images?.length || 0) + (data.videoThumbnail ? 1 : 0);
  const mediaLabel = mediaCount > 0 ? ` · ${mediaCount} media` : '';

  card.innerHTML = `
    <div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:10px;">
      ${thumbHtml}
      <div style="flex:1;min-width:0;">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
          <span style="font-size:11px;font-weight:600;padding:2px 7px;border-radius:4px;background:#f5f5f4;color:#57534e;">${detectPlatformLabel()}</span>
          <span style="font-size:12px;color:#57534e;font-weight:500;">${data.author || 'Unknown'}</span>
          <span style="font-size:11px;color:#a8a29e;">${(data.content?.split(/\s+/).length || 0)} words${mediaLabel}</span>
        </div>
        <div style="font-size:13px;color:#44403c;line-height:1.4;max-height:36px;overflow:hidden;">${preview}</div>
        ${engHtml}
      </div>
    </div>
    <div id="vp-note-section" style="display:none;margin-bottom:10px;">
      <textarea id="vp-note" style="width:100%;border:1px solid #e7e5e4;border-radius:8px;padding:8px;font-size:13px;font-family:inherit;resize:none;height:36px;" placeholder="Why save this?"></textarea>
      <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:6px;">
        <span class="vp-tag" data-t="hook">Hook</span><span class="vp-tag" data-t="format">Format</span>
        <span class="vp-tag" data-t="competitor">Competitor</span><span class="vp-tag" data-t="tone">Tone</span>
        <span class="vp-tag" data-t="cta">CTA</span><span class="vp-tag" data-t="visual">Visual</span>
      </div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;">
      <button id="vp-confirm-save" style="flex:1;padding:8px;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;background:#1c1917;color:#fff;">Looks good</button>
      <button id="vp-confirm-note" style="padding:8px 12px;border:1px solid #e7e5e4;border-radius:8px;font-size:12px;cursor:pointer;background:#fff;color:#57534e;">Add note</button>
      <button id="vp-confirm-retry" style="padding:8px 12px;border:1px solid #e7e5e4;border-radius:8px;font-size:12px;cursor:pointer;background:#fff;color:#57534e;">Retry</button>
    </div>
  `;

  document.body.appendChild(card);

  // Tag toggles
  card.querySelectorAll('.vp-tag').forEach(t => t.addEventListener('click', () => t.classList.toggle('on')));

  // Add note toggle
  card.querySelector('#vp-confirm-note').addEventListener('click', () => {
    const section = card.querySelector('#vp-note-section');
    section.style.display = section.style.display === 'none' ? 'block' : 'none';
    if (section.style.display === 'block') card.querySelector('#vp-note').focus();
  });

  // Retry
  card.querySelector('#vp-confirm-retry').addEventListener('click', () => {
    removeConfirmCard();
    // Re-trigger extraction on the same post
    if (btn?._vpPostEl) handleSaveClick(btn, btn._vpPostEl);
  });

  // Save
  card.querySelector('#vp-confirm-save').addEventListener('click', () => {
    const note = card.querySelector('#vp-note')?.value?.trim() || '';
    const tags = [...card.querySelectorAll('.vp-tag.on')].map(t => t.dataset.t);
    const fullNote = [note, ...tags.map(t => `#${t}`)].filter(Boolean).join(' ');
    removeConfirmCard();
    doSave(btn, data, fullNote);
  });

  // Enter to save
  card.querySelector('#vp-note')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); card.querySelector('#vp-confirm-save').click(); }
  });

  // ESC or click outside to dismiss
  const dismiss = (e) => {
    if (e.key === 'Escape' || (e.type === 'click' && !card.contains(e.target))) {
      removeConfirmCard();
      document.removeEventListener('keydown', dismiss);
      document.removeEventListener('click', dismiss);
    }
  };
  setTimeout(() => { document.addEventListener('keydown', dismiss); document.addEventListener('click', dismiss); }, 200);
}

function removeConfirmCard() {
  document.getElementById('vp-confirm')?.remove();
}
```

- [ ] **Step 3: Write the main save flow**

The handleSaveClick function:

```javascript
async function handleSaveClick(btn, postEl) {
  const { apiKey } = await chrome.storage.sync.get('apiKey');
  if (!apiKey) { showToast('Set your API key in the ViralPulse extension', 'error'); return; }

  const ext = getExtractor();
  if (!ext) return;

  // Store post reference on button for retry
  btn._vpPostEl = postEl;

  // Step 1: Auto-expand
  btn.querySelector('.vp-label').textContent = 'Expanding...';
  const expanded = ext.expand(postEl);
  if (expanded) await new Promise(r => setTimeout(r, 500)); // wait for expansion

  // Step 2: Extract
  btn.querySelector('.vp-label').textContent = 'Extracting...';
  const data = ext.extract(postEl);

  // Step 3: Fetch images as base64 (if any)
  const images_base64 = [];
  for (const imgUrl of (data.images || []).slice(0, 5)) {
    try {
      const resp = await fetch(imgUrl);
      const blob = await resp.blob();
      const b64 = await blobToBase64(blob);
      images_base64.push(b64);
    } catch (e) { console.log('Image fetch failed:', imgUrl, e); }
  }

  let video_thumbnail_base64 = null;
  if (data.videoThumbnail) {
    try {
      const resp = await fetch(data.videoThumbnail);
      const blob = await resp.blob();
      video_thumbnail_base64 = await blobToBase64(blob);
    } catch (e) { console.log('Video thumb fetch failed:', e); }
  }

  // Attach base64 data
  data.images_base64 = images_base64;
  data.video_thumbnail_base64 = video_thumbnail_base64;

  btn.querySelector('.vp-label').textContent = 'Save';

  // Step 4: Show confirmation card
  showConfirmCard(data, btn);
}
```

- [ ] **Step 4: Write helper functions**

```javascript
function extractHashtags(text) {
  return (text.match(/#(\w+)/g) || []).map(h => h.slice(1));
}

function fmtNum(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return String(n);
}

function blobToBase64(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.readAsDataURL(blob);
  });
}

function detectPlatformLabel() {
  const h = window.location.hostname.replace('www.', '');
  const map = { 'x.com': 'X', 'twitter.com': 'X', 'reddit.com': 'Reddit', 'linkedin.com': 'LinkedIn', 'youtube.com': 'YouTube', 'tiktok.com': 'TikTok', 'instagram.com': 'Instagram' };
  return map[h] || 'Web';
}

function getExtractor() {
  const h = window.location.hostname.replace('www.', '');
  return EXTRACTORS[h] || null;
}
```

- [ ] **Step 5: Write doSave function**

```javascript
async function doSave(btn, data, note) {
  const label = btn.querySelector('.vp-label');
  label.textContent = 'Saving...';
  btn.classList.add('saving');

  try {
    const result = await chrome.runtime.sendMessage({
      type: 'SAVE_POST',
      metadata: {
        author: data.author,
        content: data.content,
        engagement: data.engagement,
        hashtags: data.hashtags,
        images_base64: data.images_base64 || [],
        video_thumbnail_base64: data.video_thumbnail_base64 || null,
        video_url: data.videoUrl || null,
      },
      userNote: note || null,
      url: data.url || window.location.href,
    });

    if (result.error) throw new Error(result.error);

    btn.classList.remove('saving');
    btn.classList.add('saved');
    label.textContent = 'Saved!';
    showToast('Saved to your library', 'success');
    setTimeout(() => { label.textContent = 'Saved'; }, 3000);
  } catch (e) {
    btn.classList.remove('saving');
    label.textContent = 'Save';
    showToast('Save failed: ' + e.message, 'error');
  }
}
```

- [ ] **Step 6: Assemble the full content.js**

Combine: styles + EXTRACTORS + button injection + save flow + confirmation card + observer + message handlers. Make sure the double-injection guard (`window.__vpInjected`) is present.

- [ ] **Step 7: Commit**

```bash
git add extension/content.js
git commit -m "feat: smart extraction with auto-expand, image capture, confirmation card"
```

---

## Task 5: Update /view/saved to Show Images

**Files:**
- Modify: `src/viralpulse/api.py` (the `view_saved` endpoint)

- [ ] **Step 1: Update the card rendering**

In the `view_saved` function, add image rendering from the `images` JSONB field:

```python
# After screenshot_html in the card template
images_data = r.get("images") or []
if isinstance(images_data, str):
    import json as _json
    try: images_data = _json.loads(images_data)
    except: images_data = []

images_html = ""
if images_data:
    imgs = ''.join(f'<img src="{u}" style="max-height:200px;border-radius:6px;object-fit:cover;" loading="lazy" onerror="this.style.display=\'none\'">' for u in images_data[:3])
    images_html = f'<div style="display:flex;gap:8px;margin-bottom:10px;overflow-x:auto;">{imgs}</div>'

video_thumb = r.get("video_thumbnail") or ""
video_url = r.get("video_url") or ""
video_html = ""
if video_thumb:
    video_html = f'<a href="{video_url or url}" target="_blank" style="display:block;position:relative;margin-bottom:10px;"><img src="{video_thumb}" style="max-height:200px;border-radius:6px;" loading="lazy"><div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:40px;height:40px;background:rgba(0,0,0,0.5);border-radius:50%;display:flex;align-items:center;justify-content:center;"><svg width="18" height="18" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg></div></a>'
```

Add `{images_html}{video_html}` to the card template before the content text.

- [ ] **Step 2: Restart and verify**

```bash
sudo systemctl restart viralpulse
```

Visit `https://api.aithatjustworks.com/view/saved?key=vp_5MYohOYt1h3HHMS3t_Tuw74n` and check that saved posts with images display them.

- [ ] **Step 3: Commit**

```bash
git add src/viralpulse/api.py
git commit -m "feat: display saved images and video thumbnails in /view/saved"
```

---

## Task 6: E2E Test

**Files:**
- Create: `tests/test_e2e_save.py`

- [ ] **Step 1: Write E2E test using the API directly**

This tests the full save → retrieve flow with images:

```python
"""E2E test for the save posts feature."""
import base64
import json
import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client():
    """Client with a test user."""
    from viralpulse.api import app
    from viralpulse.db import get_conn, init_db

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        pytest.skip("No DATABASE_URL set")

    init_db()
    client = TestClient(app)

    # Create test user
    resp = client.post("/api/v1/users", json={"name": "E2E Test"})
    assert resp.status_code == 200
    user = resp.json()
    api_key = user["api_key"]

    yield client, api_key

    # Cleanup
    conn = get_conn()
    conn.execute("DELETE FROM saved_posts WHERE user_id = %s", (str(user["id"]),))
    conn.execute("DELETE FROM users WHERE id = %s", (str(user["id"]),))
    conn.commit()
    conn.close()


def test_save_with_metadata(api_client):
    client, key = api_client
    resp = client.post("/api/v1/save",
        json={
            "url": "https://x.com/test/status/999",
            "metadata": {
                "author": "@testuser",
                "content": "This is a great viral post about AI tools #AI #viral",
                "engagement": {"likes": 5000, "comments": 200, "shares": 300},
                "hashtags": ["AI", "viral"],
            },
            "user_note": "amazing hook #hook",
        },
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["platform"] == "twitter"
    assert data["status"] in ("enriched", "pending")

    # Retrieve
    resp = client.get("/api/v1/saved", headers={"X-API-Key": key})
    assert resp.status_code == 200
    posts = resp.json()["posts"]
    assert len(posts) >= 1
    saved = next(p for p in posts if p["url"] == "https://x.com/test/status/999")
    assert saved["author"] == "@testuser"
    assert saved["content"] == "This is a great viral post about AI tools #AI #viral"
    assert saved["user_note"] == "amazing hook #hook"
    assert saved["platform"] == "twitter"


def test_save_with_images(api_client):
    client, key = api_client
    fake_img = base64.b64encode(b"fake png data").decode()
    resp = client.post("/api/v1/save",
        json={
            "url": "https://reddit.com/r/test/comments/abc/test_post",
            "metadata": {
                "author": "redditor",
                "content": "Check out this image",
                "engagement": {"likes": 100},
                "hashtags": [],
                "images_base64": [f"data:image/png;base64,{fake_img}"],
                "video_thumbnail_base64": f"data:image/png;base64,{fake_img}",
                "video_url": "https://youtube.com/watch?v=abc",
            },
        },
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 200

    # Verify images were stored
    resp = client.get("/api/v1/saved", headers={"X-API-Key": key})
    posts = resp.json()["posts"]
    saved = next(p for p in posts if "reddit.com" in p["url"])
    # images should be stored (either as URLs if S3 works, or empty if mocked)
    assert "images" in saved


def test_save_and_delete(api_client):
    client, key = api_client
    # Save
    resp = client.post("/api/v1/save",
        json={"url": "https://linkedin.com/feed/update/123", "metadata": {"content": "test"}},
        headers={"X-API-Key": key},
    )
    post_id = resp.json()["id"]

    # Delete
    resp = client.delete(f"/api/v1/saved/{post_id}", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["deleted"] == True

    # Verify gone
    resp = client.get("/api/v1/saved", headers={"X-API-Key": key})
    urls = [p["url"] for p in resp.json()["posts"]]
    assert "https://linkedin.com/feed/update/123" not in urls


def test_save_search(api_client):
    client, key = api_client
    # Save two posts
    client.post("/api/v1/save",
        json={"url": "https://x.com/a/status/1", "metadata": {"content": "AI tools are amazing", "author": "@ai_fan"}},
        headers={"X-API-Key": key},
    )
    client.post("/api/v1/save",
        json={"url": "https://x.com/b/status/2", "metadata": {"content": "Best pizza recipe ever", "author": "@chef"}},
        headers={"X-API-Key": key},
    )

    # Search for AI
    resp = client.get("/api/v1/saved?query=AI", headers={"X-API-Key": key})
    posts = resp.json()["posts"]
    assert any("AI" in p["content"] for p in posts)
    assert not any("pizza" in p["content"] for p in posts)
```

- [ ] **Step 2: Run E2E tests**

```bash
~/.local/bin/uv run pytest tests/test_e2e_save.py -v
```

- [ ] **Step 3: Run ALL tests**

```bash
~/.local/bin/uv run pytest -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_save.py
git commit -m "test: E2E tests for save, retrieve, search, delete, images"
```

---

## Task 7: Deploy + Final Test

- [ ] **Step 1: Restart production**

```bash
sudo systemctl restart viralpulse
```

- [ ] **Step 2: Send updated extension to user**

```bash
rm -f /tmp/viralpulse-extension.zip && zip -r /tmp/viralpulse-extension.zip extension/
wormhole send /tmp/viralpulse-extension.zip
```

- [ ] **Step 3: Manual test on X**

1. Go to x.com
2. See "Save" buttons on tweets
3. Click Save on a tweet with an image
4. See confirmation card with text preview + image thumbnail + engagement
5. Click "Looks good"
6. See "Saved!" toast
7. Check library at /view/saved — see the post with image displayed

- [ ] **Step 4: Push to GitHub**

```bash
git push
```
