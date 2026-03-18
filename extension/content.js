// ViralPulse Content Script — Smart Extraction + Confirmation Card
// v2.0 — Structured data extraction, auto-expand, image capture

if (window.__vpInjected) { /* already loaded */ } else {
window.__vpInjected = true;

// ==========================================
// STYLES
// ==========================================

const vpStyle = document.createElement('style');
vpStyle.textContent = `
  .vp-save-btn {
    display: inline-flex; align-items: center; gap: 4px;
    background: none; border: none; cursor: pointer;
    color: #71767b; font-size: 13px; padding: 4px 8px;
    border-radius: 20px; transition: all 0.15s;
    font-family: -apple-system, system-ui, sans-serif;
    white-space: nowrap;
  }
  .vp-save-btn:hover { color: #dc2626; background: rgba(220,38,38,0.08); }
  .vp-save-btn.saved { color: #16a34a !important; }
  .vp-save-btn.saving { color: #78716c !important; pointer-events: none; }

  .vp-toast {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    z-index: 2147483647; padding: 12px 20px; border-radius: 10px;
    font: 500 14px -apple-system, system-ui, sans-serif;
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    animation: vpFadeUp 0.2s ease;
    color: #fff;
  }
  .vp-toast.success { background: #16a34a; }
  .vp-toast.error { background: #dc2626; }
  @keyframes vpFadeUp { from { opacity:0; transform:translateX(-50%) translateY(10px); } to { opacity:1; transform:translateX(-50%) translateY(0); } }

  #vp-confirm {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    z-index: 2147483647; background: #fff; border-radius: 14px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.04);
    padding: 16px; width: 400px; max-width: calc(100vw - 40px);
    font-family: -apple-system, system-ui, sans-serif;
    animation: vpFadeUp 0.2s ease;
  }
  .vp-tag {
    font-size: 11px; padding: 3px 9px; border-radius: 16px;
    border: 1px solid #e7e5e4; background: #fff; color: #57534e;
    cursor: pointer; user-select: none; display: inline-block;
  }
  .vp-tag:hover { border-color: #d6d3d1; background: #fafaf9; }
  .vp-tag.on { background: #1c1917; color: #fff; border-color: #1c1917; }
`;
document.head.appendChild(vpStyle);

// ==========================================
// ICON
// ==========================================

const VP_ICON = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>';

// ==========================================
// HELPERS
// ==========================================

function extractHashtags(text) {
  return (text.match(/#(\w+)/g) || []).map(h => h.slice(1));
}

function fmtNum(n) {
  if (!n) return '0';
  n = Number(n);
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

function showToast(msg, type) {
  document.querySelector('.vp-toast')?.remove();
  const t = document.createElement('div');
  t.className = `vp-toast ${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2500);
}

const hostname = window.location.hostname.replace('www.', '');

function platformLabel() {
  const map = { 'x.com':'X', 'twitter.com':'X', 'reddit.com':'Reddit', 'linkedin.com':'LinkedIn', 'youtube.com':'YouTube', 'tiktok.com':'TikTok', 'instagram.com':'Instagram' };
  return map[hostname] || 'Web';
}

// ==========================================
// PLATFORM EXTRACTORS
// ==========================================

const EXTRACTORS = {
  'x.com': {
    postSelector: 'article[data-testid="tweet"]',
    actionBar: '[role="group"]:last-of-type',
    expand(post) {
      const btn = post.querySelector('[data-testid="tweet-text-show-more-link"]');
      if (btn) { btn.click(); return true; }
      // Also try generic "Show more" spans
      for (const el of post.querySelectorAll('span[role="link"], div[role="link"]')) {
        if (/show more/i.test(el.textContent)) { el.click(); return true; }
      }
      return false;
    },
    extract(post) {
      const author = post.querySelector('[data-testid="User-Name"] a')?.textContent?.trim() || '';
      const content = post.querySelector('[data-testid="tweetText"]')?.textContent || '';
      const images = [...post.querySelectorAll('[data-testid="tweetPhoto"] img')]
        .map(img => img.src).filter(s => s && s.startsWith('http') && !s.includes('emoji'));
      const video = post.querySelector('video');
      const videoThumbnail = video?.poster || post.querySelector('[data-testid="videoPlayer"] img')?.src || null;
      const videoUrl = video ? window.location.href : null;
      const link = post.querySelector('a[href*="/status/"]');
      const url = link ? 'https://x.com' + new URL(link.href).pathname : window.location.href;
      // Engagement from aria-labels
      const engagement = {};
      post.querySelectorAll('[role="group"] button[aria-label]').forEach(btn => {
        const label = btn.getAttribute('aria-label') || '';
        const m = label.match(/([\d,]+)\s*(repl|like|repost|view|bookmark)/i);
        if (m) {
          const num = parseInt(m[1].replace(/,/g, ''));
          const t = m[2].toLowerCase();
          if (t.startsWith('repl')) engagement.comments = num;
          else if (t.startsWith('like')) engagement.likes = num;
          else if (t.startsWith('repost')) engagement.shares = num;
          else if (t.startsWith('view')) engagement.views = num;
        }
      });
      return { author, content, engagement, hashtags: extractHashtags(content), images, videoThumbnail, videoUrl, url };
    },
  },

  'reddit.com': {
    postSelector: 'shreddit-post, .Post, [data-testid="post-container"], article',
    actionBar: 'shreddit-post-overflow-menu, .flat-list.buttons, [slot="credit-bar"]',
    expand(post) {
      for (const btn of post.querySelectorAll('button, [role="button"]')) {
        if (btn.offsetHeight > 0 && /\bmore\b/i.test(btn.textContent)) { btn.click(); return true; }
      }
      return false;
    },
    extract(post) {
      const title = post.querySelector('[data-testid="post-title"], h1, h3, [slot="title"]')?.textContent?.trim() || '';
      const body = post.querySelector('[slot="text-body"], .usertext-body, [data-testid="post-content"]')?.textContent?.trim() || '';
      const author = post.querySelector('[data-testid="post_author_link"], .author, [slot="authorName"]')?.textContent?.trim() || '';
      const images = [...post.querySelectorAll('img')].filter(img => {
        const w = img.naturalWidth || img.width; return w > 100 && !/avatar|icon|emoji/i.test(img.src);
      }).map(img => img.src);
      const link = post.querySelector('a[href*="/comments/"]');
      const url = link ? link.href : window.location.href;
      const scoreEl = post.querySelector('[data-testid="post-score"], .score, [score]');
      const likes = scoreEl ? parseInt((scoreEl.textContent || scoreEl.getAttribute('score') || '0').replace(/[^0-9-]/g, '')) || 0 : 0;
      return { author, content: title + (body ? '\n' + body : ''), engagement: { likes }, hashtags: [], images, videoThumbnail: null, videoUrl: null, url };
    },
  },

  'linkedin.com': {
    postSelector: '.feed-shared-update-v2, .occludable-update, div[data-urn], div[data-id], [data-chameleon-result-urn], .scaffold-finite-scroll__content > div > div',
    actionBar: '.feed-shared-social-actions, .social-details-social-counts, .feed-shared-update-v2__control-menu, .social-details-social-activity',
    expand(post) {
      const btn = post.querySelector('.feed-shared-inline-show-more-text, button[aria-expanded="false"], span.lt-line-clamp__more');
      if (btn) { btn.click(); return true; }
      for (const el of post.querySelectorAll('button, span')) {
        if (/see more|\.\.\.more/i.test(el.textContent?.trim()) && el.offsetHeight > 0) { el.click(); return true; }
      }
      return false;
    },
    extract(post) {
      const author = post.querySelector('.feed-shared-actor__name, .update-components-actor__name, a[data-tracking-control-name*="actor"]')?.textContent?.trim() || '';
      const content = post.querySelector('.feed-shared-text, .update-components-text, .break-words')?.textContent?.trim() || '';
      const images = [...post.querySelectorAll('.feed-shared-image img, .update-components-image img, img[data-delayed-url]')]
        .map(img => img.src || img.getAttribute('data-delayed-url')).filter(Boolean);
      const video = post.querySelector('video');
      return { author, content, engagement: {}, hashtags: extractHashtags(content), images, videoThumbnail: video?.poster || null, videoUrl: null, url: window.location.href };
    },
  },

  'youtube.com': {
    postSelector: '#primary-inner, ytd-rich-item-renderer, ytd-video-renderer',
    actionBar: '#top-level-buttons-computed, ytd-menu-renderer, #info',
    expand(post) {
      const btn = document.querySelector('#expand, tp-yt-paper-button#more, [aria-label="Show more"]');
      if (btn) { btn.click(); return true; }
      return false;
    },
    extract() {
      const title = document.querySelector('h1.ytd-watch-metadata, #video-title')?.textContent?.trim() || '';
      const channel = document.querySelector('#channel-name a')?.textContent?.trim() || '';
      const desc = document.querySelector('#description-inner, .ytd-text-inline-expander')?.textContent?.slice(0, 2000)?.trim() || '';
      const ogImage = document.querySelector('meta[property="og:image"]')?.content || '';
      const viewsText = document.querySelector('#info-strings yt-formatted-string, .view-count')?.textContent || '';
      const views = parseInt(viewsText.replace(/[^0-9]/g, '') || '0');
      return { author: channel, content: title + '\n' + desc, engagement: { views }, hashtags: extractHashtags(desc), images: [], videoThumbnail: ogImage, videoUrl: window.location.href, url: window.location.href };
    },
  },

  'tiktok.com': {
    postSelector: '[data-e2e="recommend-list-item-container"], .video-feed-item',
    actionBar: '[data-e2e="video-action-bar"]',
    expand() { return false; },
    extract() {
      const author = document.querySelector('[data-e2e="browse-username"]')?.textContent?.trim() || '';
      const content = document.querySelector('[data-e2e="browse-video-desc"]')?.textContent || '';
      const video = document.querySelector('video');
      return { author, content, engagement: {}, hashtags: extractHashtags(content), images: [], videoThumbnail: video?.poster || null, videoUrl: window.location.href, url: window.location.href };
    },
  },

  'instagram.com': {
    postSelector: 'article',
    actionBar: 'section',
    expand(post) {
      for (const btn of post.querySelectorAll('button')) {
        if (/more/i.test(btn.textContent) && btn.offsetHeight > 0) { btn.click(); return true; }
      }
      return false;
    },
    extract(post) {
      const author = post.querySelector('header a')?.textContent?.trim() || '';
      const content = post.querySelector('h1, span[dir="auto"]')?.textContent || '';
      const images = [...post.querySelectorAll('img[srcset], img[sizes]')]
        .filter(img => (img.naturalWidth || img.width) > 100).map(img => img.src);
      const video = post.querySelector('video');
      return { author, content, engagement: {}, hashtags: extractHashtags(content), images, videoThumbnail: video?.poster || null, videoUrl: null, url: window.location.href };
    },
  },
};

  'moltbook.com': {
    postSelector: '[data-post-id], .post-card, article',
    actionBar: '.post-actions, .post-footer, footer',
    expand() { return false; },
    extract(post) {
      const author = post.querySelector('.agent-name, .author, [data-agent]')?.textContent?.trim() || '';
      const content = post.querySelector('.post-content, .post-body, p')?.textContent || '';
      const images = [...post.querySelectorAll('img')].filter(img => (img.naturalWidth || img.width) > 100 && !/avatar|icon/i.test(img.src)).map(img => img.src);
      const postLink = post.querySelector('a[href*="/post/"]');
      const url = postLink ? postLink.href : window.location.href;
      return { author, content, engagement: {}, hashtags: extractHashtags(content), images, videoThumbnail: null, videoUrl: null, url };
    },
  },

EXTRACTORS['twitter.com'] = EXTRACTORS['x.com'];

const ext = EXTRACTORS[hostname] || null;

// ==========================================
// BUTTON INJECTION
// ==========================================

function createVPButton(postEl) {
  const btn = document.createElement('button');
  btn.className = 'vp-save-btn';
  btn.setAttribute('data-vp', 'true');
  btn.innerHTML = `${VP_ICON}<span class="vp-label">Save</span>`;
  btn.title = 'Save to ViralPulse';
  btn._vpPostEl = postEl;
  btn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); handleSaveClick(btn, postEl); });
  return btn;
}

function injectButtons() {
  if (!ext) return;
  document.querySelectorAll(ext.postSelector).forEach(post => {
    if (post.querySelector('[data-vp]')) return;
    const bar = post.querySelector(ext.actionBar);
    if (bar) bar.appendChild(createVPButton(post));
  });
}

// ==========================================
// FLOATING FALLBACK BUTTON
// ==========================================

function injectFloatingButton() {
  if (document.getElementById('vp-fab')) return;
  const fab = document.createElement('button');
  fab.id = 'vp-fab';
  fab.className = 'vp-save-btn';
  fab.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:2147483640;background:#fff;border:1px solid #e7e5e4;box-shadow:0 4px 16px rgba(0,0,0,0.12);padding:12px 18px;border-radius:12px;font-size:14px;font-weight:500;';
  fab.innerHTML = `${VP_ICON} <span class="vp-label">Save this page</span>`;
  fab._vpPostEl = document.body;
  fab.addEventListener('click', (e) => {
    e.preventDefault();
    // For LinkedIn, try to find the focused/visible post first
    const visiblePost = document.querySelector('.feed-shared-update-v2, .occludable-update, div[data-urn], div[data-id]');
    handleSaveClick(fab, visiblePost || document.body);
  });
  document.body.appendChild(fab);
}

// ==========================================
// SAVE FLOW
// ==========================================

async function handleSaveClick(btn, postEl) {
  console.log('[VP] Save clicked');
  try {
  const result = await chrome.storage.sync.get('apiKey');
  console.log('[VP] API key result:', result);
  const apiKey = result.apiKey;
  if (!apiKey) { showToast('Set your API key in the ViralPulse extension popup', 'error'); return; }

  const label = btn.querySelector('.vp-label');
  const currentExt = ext;
  console.log('[VP] Extractor:', currentExt ? 'found' : 'null', 'hostname:', hostname);

  // Step 1: Auto-expand
  label.textContent = 'Expanding...';
  let expanded = false;
  if (currentExt) {
    try { expanded = currentExt.expand(postEl); } catch(e) { console.log('VP expand failed:', e); }
  }
  if (expanded) await new Promise(r => setTimeout(r, 600));

  // Step 2: Extract structured data
  label.textContent = 'Extracting...';
  let data;
  if (currentExt) {
    try { data = currentExt.extract(postEl); } catch(e) { console.log('VP extract failed:', e); data = null; }
  }
  if (!data) {
    // Generic fallback
    data = {
      author: document.querySelector('meta[name="author"]')?.content || '',
      content: (document.querySelector('meta[property="og:description"]')?.content || '') + '\n' + (document.querySelector('article, main')?.innerText?.slice(0, 2000) || document.title),
      engagement: {}, hashtags: [], images: [], videoThumbnail: null, videoUrl: null, url: window.location.href,
    };
  }

  // Step 3: Fetch images as base64
  label.textContent = 'Capturing media...';
  const images_base64 = [];
  for (const imgUrl of (data.images || []).slice(0, 5)) {
    try {
      const resp = await fetch(imgUrl);
      const blob = await resp.blob();
      if (blob.size > 100) { // skip tiny/broken images
        images_base64.push(await blobToBase64(blob));
      }
    } catch(e) { /* skip failed images */ }
  }

  let video_thumbnail_base64 = null;
  if (data.videoThumbnail) {
    try {
      const resp = await fetch(data.videoThumbnail);
      const blob = await resp.blob();
      if (blob.size > 100) video_thumbnail_base64 = await blobToBase64(blob);
    } catch(e) { /* skip */ }
  }

  data.images_base64 = images_base64;
  data.video_thumbnail_base64 = video_thumbnail_base64;

  label.textContent = 'Save';

  // Step 4: Show confirmation card
  console.log('[VP] Showing confirm card with data:', { author: data.author, contentLen: data.content?.length, images: data.images?.length });
  showConfirmCard(data, btn);

  } catch(err) {
    console.error('[VP] handleSaveClick error:', err);
    showToast('Error: ' + err.message, 'error');
    const label = btn?.querySelector('.vp-label');
    if (label) label.textContent = 'Save';
  }
}

// ==========================================
// CONFIRMATION CARD
// ==========================================

function showConfirmCard(data, btn) {
  document.getElementById('vp-confirm')?.remove();

  const imgThumb = data.images?.[0] || data.videoThumbnail || '';
  const thumbHtml = imgThumb ? `<img src="${imgThumb}" style="width:52px;height:52px;border-radius:6px;object-fit:cover;flex-shrink:0;" onerror="this.style.display='none'">` : '';

  const engParts = [];
  if (data.engagement?.views) engParts.push('&#x25B6; ' + fmtNum(data.engagement.views));
  if (data.engagement?.likes) engParts.push('&#x2764; ' + fmtNum(data.engagement.likes));
  if (data.engagement?.comments) engParts.push('&#x1F4AC; ' + fmtNum(data.engagement.comments));
  if (data.engagement?.shares) engParts.push('&#x21A9; ' + fmtNum(data.engagement.shares));

  const preview = (data.content || '').slice(0, 140) + ((data.content || '').length > 140 ? '...' : '');
  const mediaCount = (data.images_base64?.length || 0) + (data.video_thumbnail_base64 ? 1 : 0);
  const wordCount = (data.content || '').split(/\s+/).filter(Boolean).length;

  const card = document.createElement('div');
  card.id = 'vp-confirm';
  card.innerHTML = `
    <div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:10px;">
      ${thumbHtml}
      <div style="flex:1;min-width:0;">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
          <span style="font-size:11px;font-weight:600;padding:2px 7px;border-radius:4px;background:#f5f5f4;color:#57534e;">${platformLabel()}</span>
          <span style="font-size:12px;color:#57534e;font-weight:500;">${data.author || 'Unknown'}</span>
        </div>
        <div style="font-size:11px;color:#a8a29e;margin-bottom:4px;">${wordCount} words${mediaCount > 0 ? ' · ' + mediaCount + ' media' : ''}${engParts.length ? ' · ' + engParts.join(' ') : ''}</div>
        <div style="font-size:13px;color:#44403c;line-height:1.4;max-height:40px;overflow:hidden;">${preview}</div>
      </div>
    </div>
    <div id="vp-note-area" style="display:none;margin-bottom:10px;">
      <textarea id="vp-note-input" style="width:100%;border:1px solid #e7e5e4;border-radius:8px;padding:8px;font-size:13px;font-family:inherit;resize:none;height:36px;" placeholder="Why is this worth saving?"></textarea>
      <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:6px;">
        <span class="vp-tag" data-t="hook">Hook</span><span class="vp-tag" data-t="format">Format</span>
        <span class="vp-tag" data-t="competitor">Competitor</span><span class="vp-tag" data-t="tone">Tone</span>
        <span class="vp-tag" data-t="cta">CTA</span><span class="vp-tag" data-t="visual">Visual</span>
      </div>
    </div>
    <div style="display:flex;gap:8px;">
      <button id="vp-btn-save" style="flex:1;padding:9px;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;background:#1c1917;color:#fff;">Looks good</button>
      <button id="vp-btn-note" style="padding:9px 12px;border:1px solid #e7e5e4;border-radius:8px;font-size:12px;cursor:pointer;background:#fff;color:#57534e;">Add note</button>
      <button id="vp-btn-retry" style="padding:9px 12px;border:1px solid #e7e5e4;border-radius:8px;font-size:12px;cursor:pointer;background:#fff;color:#57534e;">Retry</button>
    </div>
  `;
  document.body.appendChild(card);

  // Tags
  card.querySelectorAll('.vp-tag').forEach(t => t.addEventListener('click', () => t.classList.toggle('on')));

  // Add note toggle
  card.querySelector('#vp-btn-note').addEventListener('click', () => {
    const area = card.querySelector('#vp-note-area');
    area.style.display = area.style.display === 'none' ? 'block' : 'none';
    if (area.style.display === 'block') card.querySelector('#vp-note-input').focus();
  });

  // Retry
  card.querySelector('#vp-btn-retry').addEventListener('click', () => {
    card.remove();
    if (btn._vpPostEl) handleSaveClick(btn, btn._vpPostEl);
  });

  // Save
  card.querySelector('#vp-btn-save').addEventListener('click', () => {
    const note = card.querySelector('#vp-note-input')?.value?.trim() || '';
    const tags = [...card.querySelectorAll('.vp-tag.on')].map(t => t.dataset.t);
    const fullNote = [note, ...tags.map(t => '#' + t)].filter(Boolean).join(' ');
    card.remove();
    doSave(btn, data, fullNote);
  });

  // Enter to save
  card.querySelector('#vp-note-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); card.querySelector('#vp-btn-save').click(); }
  });

  // ESC / click outside to dismiss
  const dismiss = (e) => {
    if (e.key === 'Escape' || (e.type === 'click' && !card.contains(e.target) && e.target !== btn)) {
      card.remove();
      document.removeEventListener('keydown', dismiss);
      setTimeout(() => document.removeEventListener('click', dismiss), 0);
    }
  };
  setTimeout(() => { document.addEventListener('keydown', dismiss); document.addEventListener('click', dismiss); }, 200);
}

// ==========================================
// SAVE TO API
// ==========================================

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

    if (result?.error) throw new Error(result.error);

    btn.classList.remove('saving');
    btn.classList.add('saved');
    label.textContent = 'Saved!';
    showToast('Saved to your library', 'success');
    setTimeout(() => { label.textContent = 'Saved'; }, 3000);
  } catch(e) {
    btn.classList.remove('saving');
    label.textContent = 'Save';
    showToast('Save failed: ' + e.message, 'error');
  }
}

// ==========================================
// OBSERVER + INIT
// ==========================================

function startObserver() {
  console.log('[VP] Starting observer on', hostname);
  injectButtons();

  // Always show floating button on LinkedIn (selectors are unreliable)
  // For other sites, show as fallback if no buttons injected after 3s
  const alwaysFloat = hostname === 'linkedin.com';
  setTimeout(() => {
    if (alwaysFloat || !document.querySelector('[data-vp]')) {
      console.log('[VP] Showing floating button');
      injectFloatingButton();
    }
  }, alwaysFloat ? 1000 : 3000);

  new MutationObserver(() => injectButtons()).observe(document.body, { childList: true, subtree: true });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startObserver);
} else {
  startObserver();
}

// ==========================================
// MESSAGE HANDLERS
// ==========================================

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'ACTIVATE_SELECTOR') { injectButtons(); sendResponse({ ok: true }); }
  else if (msg.type === 'EXTRACT_METADATA') {
    sendResponse({ author: '', content: document.title, engagement: {}, hashtags: [] });
  }
  return true;
});

} // end __vpInjected guard
