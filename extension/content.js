// ViralPulse Content Script — Native Share Button Injection

const VP_ICON = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>`;

// Inject styles once
const style = document.createElement('style');
style.textContent = `
  .vp-save-btn {
    display: inline-flex; align-items: center; gap: 4px;
    background: none; border: none; cursor: pointer;
    color: #71767b; font-size: 13px; padding: 4px 8px;
    border-radius: 20px; transition: all 0.15s;
    font-family: -apple-system, system-ui, sans-serif;
    white-space: nowrap; position: relative;
  }
  .vp-save-btn:hover { color: #dc2626; background: rgba(220,38,38,0.08); }
  .vp-save-btn.saved { color: #16a34a; }
  .vp-save-btn.saving { color: #78716c; pointer-events: none; }

  .vp-toast {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    z-index: 2147483647; background: #1c1917; color: #fff;
    padding: 12px 20px; border-radius: 10px;
    font: 14px -apple-system, system-ui, sans-serif;
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    display: flex; align-items: center; gap: 10px;
    animation: vpToastIn 0.2s ease;
  }
  .vp-toast.success { background: #16a34a; }
  .vp-toast.error { background: #dc2626; }
  @keyframes vpToastIn { from { opacity:0; transform:translateX(-50%) translateY(10px); } to { opacity:1; transform:translateX(-50%) translateY(0); } }

  .vp-quick-note {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    z-index: 2147483647; background: #fff; border-radius: 14px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.05);
    padding: 16px; width: 360px;
    font-family: -apple-system, system-ui, sans-serif;
    animation: vpToastIn 0.2s ease;
  }
  .vp-quick-note textarea {
    width: 100%; border: 1px solid #e7e5e4; border-radius: 8px;
    padding: 8px 10px; font-size: 13px; font-family: inherit;
    resize: none; height: 40px; margin-bottom: 8px;
  }
  .vp-quick-note textarea:focus { outline: none; border-color: #2563eb; }
  .vp-quick-note .tags { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px; }
  .vp-quick-note .tag {
    font-size: 11px; padding: 3px 9px; border-radius: 16px;
    border: 1px solid #e7e5e4; background: #fff; color: #57534e;
    cursor: pointer; user-select: none;
  }
  .vp-quick-note .tag:hover { border-color: #d6d3d1; }
  .vp-quick-note .tag.on { background: #1c1917; color: #fff; border-color: #1c1917; }
  .vp-quick-note .actions { display: flex; gap: 8px; }
  .vp-quick-note .actions button {
    flex: 1; padding: 8px; border: none; border-radius: 8px;
    font-size: 13px; font-weight: 600; cursor: pointer;
  }
  .vp-quick-note .save { background: #1c1917; color: #fff; }
  .vp-quick-note .save:hover { background: #292524; }
  .vp-quick-note .skip { background: #f5f5f4; color: #57534e; }
  .vp-quick-note .skip:hover { background: #e7e5e4; }
`;
document.head.appendChild(style);

// ==========================================
// PLATFORM-SPECIFIC BUTTON INJECTION
// ==========================================

const hostname = window.location.hostname.replace('www.', '');

const PLATFORM_CONFIG = {
  'x.com': {
    postSelector: 'article[data-testid="tweet"]',
    actionBar: '[role="group"]:last-of-type',
    getAuthor: (el) => el.querySelector('[data-testid="User-Name"] a')?.textContent || '',
    getContent: (el) => el.querySelector('[data-testid="tweetText"]')?.textContent || '',
    getUrl: (el) => {
      const link = el.querySelector('a[href*="/status/"]');
      return link ? 'https://x.com' + new URL(link.href).pathname : window.location.href;
    },
  },
  'twitter.com': null, // same as x.com, set below
  'reddit.com': {
    postSelector: 'shreddit-post, .Post, [data-testid="post-container"]',
    actionBar: 'shreddit-post-overflow-menu, .Post .PostHeader, [data-testid="post-container"] > div:last-child',
    getAuthor: (el) => el.querySelector('[data-testid="post_author_link"], .author')?.textContent || '',
    getContent: (el) => {
      const title = el.querySelector('[data-testid="post-title"], h1, h3')?.textContent || '';
      const body = el.querySelector('[slot="text-body"], .usertext-body')?.textContent || '';
      return title + '\n' + body;
    },
    getUrl: (el) => {
      const link = el.querySelector('a[href*="/comments/"]');
      return link ? link.href : window.location.href;
    },
  },
  'linkedin.com': {
    postSelector: '.feed-shared-update-v2, .occludable-update',
    actionBar: '.social-details-social-counts, .feed-shared-social-actions',
    getAuthor: (el) => el.querySelector('.feed-shared-actor__name, .update-components-actor__name')?.textContent?.trim() || '',
    getContent: (el) => el.querySelector('.feed-shared-text, .update-components-text')?.textContent || '',
    getUrl: (el) => {
      const link = el.querySelector('a[href*="/feed/update/"]');
      return link ? link.href : window.location.href;
    },
  },
  'youtube.com': {
    postSelector: '#primary-inner, ytd-rich-item-renderer',
    actionBar: '#top-level-buttons-computed, ytd-menu-renderer',
    getAuthor: (el) => el.querySelector('#channel-name a, .ytd-channel-name a')?.textContent?.trim() || '',
    getContent: (el) => {
      const title = el.querySelector('h1.ytd-watch-metadata, #video-title')?.textContent || '';
      return title;
    },
    getUrl: (el) => window.location.href,
  },
  'tiktok.com': {
    postSelector: '[data-e2e="recommend-list-item-container"], .video-feed-item',
    actionBar: '[data-e2e="video-action-bar"], .video-action-container',
    getAuthor: (el) => el.querySelector('[data-e2e="browse-username"]')?.textContent || '',
    getContent: (el) => el.querySelector('[data-e2e="browse-video-desc"]')?.textContent || '',
    getUrl: (el) => window.location.href,
  },
  'instagram.com': {
    postSelector: 'article',
    actionBar: 'section:has(button[type="button"])',
    getAuthor: (el) => el.querySelector('header a')?.textContent || '',
    getContent: (el) => el.querySelector('h1, span[dir="auto"]')?.textContent || '',
    getUrl: (el) => window.location.href,
  },
};

PLATFORM_CONFIG['twitter.com'] = PLATFORM_CONFIG['x.com'];

const config = PLATFORM_CONFIG[hostname];

// ==========================================
// INJECT BUTTONS
// ==========================================

function createVPButton(postEl) {
  const btn = document.createElement('button');
  btn.className = 'vp-save-btn';
  btn.setAttribute('data-vp', 'true');
  btn.innerHTML = `${VP_ICON}<span class="vp-label">Save</span>`;
  btn.title = 'Save to ViralPulse';

  btn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    handleSaveClick(btn, postEl);
  });

  return btn;
}

function injectButtons() {
  if (!config) return;

  const posts = document.querySelectorAll(config.postSelector);
  posts.forEach(post => {
    // Skip if already injected
    if (post.querySelector('[data-vp]')) return;

    // Find the action bar
    const actionBar = post.querySelector(config.actionBar);
    if (actionBar) {
      const btn = createVPButton(post);
      actionBar.appendChild(btn);
    }
  });
}

// ==========================================
// SAVE HANDLER
// ==========================================

let activeQuickNote = null;

function showToast(msg, type = '') {
  const existing = document.querySelector('.vp-toast');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.className = `vp-toast ${type}`;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2500);
}

async function handleSaveClick(btn, postEl) {
  // Check API key
  const { apiKey } = await chrome.storage.sync.get('apiKey');
  if (!apiKey) {
    showToast('Set your API key in the ViralPulse extension', 'error');
    return;
  }

  // Extract metadata
  const metadata = {
    author: config.getAuthor(postEl),
    content: config.getContent(postEl),
    engagement: {},
    hashtags: (config.getContent(postEl).match(/#(\w+)/g) || []).map(h => h.slice(1)),
  };
  const url = config.getUrl(postEl);

  // Show quick note panel
  showQuickNote(btn, postEl, metadata, url, apiKey);
}

function showQuickNote(btn, postEl, metadata, url, apiKey) {
  // Remove any existing note panel
  if (activeQuickNote) { activeQuickNote.remove(); activeQuickNote = null; }

  const panel = document.createElement('div');
  panel.className = 'vp-quick-note';
  panel.innerHTML = `
    <textarea placeholder="Why save this? (optional)" autofocus></textarea>
    <div class="tags">
      <span class="tag" data-t="hook">Hook</span>
      <span class="tag" data-t="format">Format</span>
      <span class="tag" data-t="competitor">Competitor</span>
      <span class="tag" data-t="tone">Tone</span>
      <span class="tag" data-t="cta">CTA</span>
      <span class="tag" data-t="visual">Visual</span>
    </div>
    <div class="actions">
      <button class="skip">Save without note</button>
      <button class="save">Save with note</button>
    </div>
  `;
  document.body.appendChild(panel);
  activeQuickNote = panel;

  // Focus textarea
  panel.querySelector('textarea').focus();

  // Tag toggles
  panel.querySelectorAll('.tag').forEach(t => t.addEventListener('click', () => t.classList.toggle('on')));

  // Close on click outside
  const closeHandler = (e) => {
    if (!panel.contains(e.target) && e.target !== btn) {
      panel.remove();
      activeQuickNote = null;
      document.removeEventListener('click', closeHandler);
    }
  };
  setTimeout(() => document.addEventListener('click', closeHandler), 100);

  // Save without note
  panel.querySelector('.skip').addEventListener('click', () => {
    panel.remove();
    activeQuickNote = null;
    document.removeEventListener('click', closeHandler);
    doSave(btn, metadata, url, apiKey, '');
  });

  // Save with note
  panel.querySelector('.save').addEventListener('click', () => {
    const note = panel.querySelector('textarea').value.trim();
    const tags = [...panel.querySelectorAll('.tag.on')].map(t => t.dataset.t);
    const fullNote = [note, ...tags.map(t => `#${t}`)].filter(Boolean).join(' ');
    panel.remove();
    activeQuickNote = null;
    document.removeEventListener('click', closeHandler);
    doSave(btn, metadata, url, apiKey, fullNote);
  });

  // Enter key saves
  panel.querySelector('textarea').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      panel.querySelector('.save').click();
    }
  });
}

async function doSave(btn, metadata, url, apiKey, note) {
  // Update button state
  const label = btn.querySelector('.vp-label');
  btn.classList.add('saving');
  label.textContent = 'Saving...';

  try {
    const result = await chrome.runtime.sendMessage({
      type: 'SAVE_POST',
      metadata,
      userNote: note || null,
      url,
    });

    if (result.error) throw new Error(result.error);

    // Success
    btn.classList.remove('saving');
    btn.classList.add('saved');
    label.textContent = 'Saved!';
    showToast('Saved to your library', 'success');

    // Reset after 3s
    setTimeout(() => {
      label.textContent = 'Saved';
      // Keep green to show it's been saved
    }, 3000);

  } catch (e) {
    btn.classList.remove('saving');
    label.textContent = 'Save';
    showToast('Save failed: ' + e.message, 'error');
  }
}

// ==========================================
// GENERIC FALLBACK (non-supported platforms)
// ==========================================

function injectFloatingButton() {
  // Skip if floating button already exists
  if (document.getElementById('vp-fab')) return;

  const fab = document.createElement('button');
  fab.id = 'vp-fab';
  fab.className = 'vp-save-btn';
  fab.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:2147483640;background:#fff;border:1px solid #e7e5e4;box-shadow:0 2px 12px rgba(0,0,0,0.1);padding:10px 16px;border-radius:12px;font-size:14px;';
  fab.innerHTML = `${VP_ICON} <span class="vp-label">Save to VP</span>`;
  fab.title = 'Save this page to ViralPulse';
  document.body.appendChild(fab);

  fab.addEventListener('click', async (e) => {
    e.preventDefault();
    const { apiKey } = await chrome.storage.sync.get('apiKey');
    if (!apiKey) { showToast('Set your API key in the ViralPulse extension', 'error'); return; }

    const metadata = {
      author: document.querySelector('meta[name="author"]')?.content || '',
      content: (document.querySelector('meta[property="og:description"]')?.content || '') + '\n' + (document.querySelector('article, main')?.innerText?.slice(0, 2000) || document.title),
      engagement: {},
      hashtags: [],
    };

    showQuickNote(fab, document.body, metadata, window.location.href, apiKey);
  });
}

// ==========================================
// OBSERVER — watch for new posts loading
// ==========================================

function startObserver() {
  // Initial injection attempt
  injectButtons();

  // If no buttons were injected after a delay, show floating button as fallback
  setTimeout(() => {
    const injected = document.querySelectorAll('[data-vp]');
    if (injected.length === 0) {
      injectFloatingButton();
    }
  }, 3000);

  const observer = new MutationObserver(() => {
    injectButtons();
  });

  observer.observe(document.body, { childList: true, subtree: true });
}

// Guard against double injection
if (!window.__vpInjected) {
  window.__vpInjected = true;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startObserver);
  } else {
    startObserver();
  }
}

// ==========================================
// MESSAGE HANDLERS (for popup/background)
// ==========================================

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'ACTIVATE_SELECTOR') {
    // Legacy support — just inject buttons if not already done
    injectButtons();
    sendResponse({ ok: true });
  } else if (msg.type === 'EXTRACT_METADATA') {
    const metadata = {
      author: document.querySelector('meta[name="author"]')?.content || '',
      content: document.querySelector('meta[property="og:description"]')?.content || document.title,
      engagement: {},
      hashtags: [],
    };
    sendResponse(metadata);
  }
  return true;
});
