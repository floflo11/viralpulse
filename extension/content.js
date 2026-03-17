// ViralPulse Content Script — Post Selection + Metadata Extraction

let selectorActive = false;
let overlay = null;
let highlightBox = null;
let savePanel = null;
let selectedElement = null;

// Platform-specific post container selectors
const POST_SELECTORS = {
  'x.com': 'article[data-testid="tweet"], article',
  'twitter.com': 'article[data-testid="tweet"], article',
  'reddit.com': 'shreddit-post, .Post, [data-testid="post-container"], .thing.link',
  'tiktok.com': '[data-e2e="recommend-list-item-container"], .video-feed-item, [class*="DivItemContainer"]',
  'instagram.com': 'article, [role="presentation"]',
  'youtube.com': 'ytd-rich-item-renderer, ytd-video-renderer, #primary-inner',
  'linkedin.com': '.feed-shared-update-v2, .occludable-update, [data-urn]',
};

const GENERIC_SELECTORS = 'article, [role="article"], .post, .entry, .card, main > div > div, .content-body';

function getPostSelectors() {
  const hostname = window.location.hostname.replace('www.', '');
  return POST_SELECTORS[hostname] || GENERIC_SELECTORS;
}

function findClosestPost(el) {
  const selectors = getPostSelectors();
  let current = el;
  for (let i = 0; i < 15; i++) {
    if (!current || current === document.body || current === document.documentElement) break;
    try { if (current.matches && current.matches(selectors)) return current; } catch(e) {}
    current = current.parentElement;
  }
  // Fallback: reasonable block ancestor
  current = el;
  for (let i = 0; i < 10; i++) {
    if (!current || current === document.body) break;
    const rect = current.getBoundingClientRect();
    if (rect.height > 80 && rect.height < window.innerHeight * 0.85 && rect.width > 200) return current;
    current = current.parentElement;
  }
  return el;
}

function injectStyles() {
  const style = document.createElement('style');
  style.id = 'vp-styles';
  style.textContent = `
    #vp-overlay { position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.25); z-index:2147483640; cursor:crosshair; transition:background 0.2s; }
    #vp-highlight { position:fixed; z-index:2147483641; border:2.5px solid #2563eb; border-radius:8px; background:rgba(37,99,235,0.04); pointer-events:none; transition:all 0.08s ease; box-shadow:0 0 0 4px rgba(37,99,235,0.08); display:none; }
    #vp-hint { position:fixed; top:20px; left:50%; transform:translateX(-50%); z-index:2147483642; background:#1c1917; color:#fff; padding:10px 24px; border-radius:10px; font:500 14px -apple-system,system-ui,sans-serif; box-shadow:0 4px 20px rgba(0,0,0,0.25); display:flex; align-items:center; gap:12px; }
    #vp-hint kbd { background:rgba(255,255,255,0.15); padding:2px 8px; border-radius:4px; font-size:12px; }
    #vp-save-panel { position:fixed; right:20px; top:50%; transform:translateY(-50%); z-index:2147483643; background:#fff; border-radius:14px; box-shadow:0 8px 40px rgba(0,0,0,0.12),0 0 0 1px rgba(0,0,0,0.04); width:340px; overflow:hidden; font-family:-apple-system,system-ui,sans-serif; animation:vpSlideIn 0.2s ease; }
    @keyframes vpSlideIn { from { opacity:0; transform:translateY(-50%) translateX(20px); } to { opacity:1; transform:translateY(-50%) translateX(0); } }
    #vp-save-panel .body { padding:16px; }
    #vp-save-panel .meta { display:flex; align-items:center; gap:8px; margin-bottom:10px; }
    #vp-save-panel .pbadge { font-size:11px; font-weight:600; padding:3px 8px; border-radius:5px; }
    #vp-save-panel .author { font-size:13px; color:#57534e; font-weight:500; }
    #vp-save-panel .preview-text { font-size:12px; color:#78716c; line-height:1.5; margin-bottom:12px; max-height:48px; overflow:hidden; }
    #vp-save-panel .note-input { width:100%; border:1px solid #e7e5e4; border-radius:8px; padding:8px 10px; font-size:13px; font-family:inherit; resize:none; height:44px; margin-bottom:10px; }
    #vp-save-panel .note-input:focus { outline:none; border-color:#2563eb; }
    #vp-save-panel .tags { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:14px; }
    #vp-save-panel .tag { font-size:11px; padding:4px 10px; border-radius:20px; border:1px solid #e7e5e4; background:#fff; color:#57534e; cursor:pointer; transition:all 0.1s; user-select:none; }
    #vp-save-panel .tag:hover { border-color:#d6d3d1; background:#fafaf9; }
    #vp-save-panel .tag.on { background:#1c1917; color:#fff; border-color:#1c1917; }
    #vp-save-panel .sbtn { width:100%; padding:10px; border:none; border-radius:8px; font-size:14px; font-weight:600; cursor:pointer; background:#1c1917; color:#fff; transition:all 0.15s; }
    #vp-save-panel .sbtn:hover { background:#292524; }
    #vp-save-panel .sbtn:disabled { opacity:0.5; cursor:not-allowed; }
    #vp-save-panel .cancel { display:block; text-align:center; margin-top:8px; font-size:12px; color:#a8a29e; cursor:pointer; border:none; background:none; width:100%; }
    #vp-save-panel .cancel:hover { color:#57534e; }
    #vp-save-panel .prog { height:3px; background:#e7e5e4; border-radius:2px; margin-bottom:10px; overflow:hidden; display:none; }
    #vp-save-panel .prog.on { display:block; }
    #vp-save-panel .prog-bar { height:100%; background:#2563eb; width:0%; animation:vpProg 1.5s ease-in-out infinite; border-radius:2px; }
    @keyframes vpProg { 0%{width:5%} 50%{width:75%} 100%{width:95%} }
    #vp-success { padding:28px 16px; text-align:center; }
    #vp-success .chk { width:48px; height:48px; margin:0 auto 12px; background:#dcfce7; border-radius:50%; display:flex; align-items:center; justify-content:center; animation:vpPop 0.3s ease; }
    @keyframes vpPop { 0%{transform:scale(0)} 60%{transform:scale(1.2)} 100%{transform:scale(1)} }
  `;
  document.head.appendChild(style);
}

function activateSelector() {
  if (selectorActive) return;
  selectorActive = true;
  injectStyles();

  overlay = document.createElement('div');
  overlay.id = 'vp-overlay';
  document.body.appendChild(overlay);

  highlightBox = document.createElement('div');
  highlightBox.id = 'vp-highlight';
  document.body.appendChild(highlightBox);

  const hint = document.createElement('div');
  hint.id = 'vp-hint';
  hint.innerHTML = 'Click on the post you want to save <kbd>ESC</kbd>';
  document.body.appendChild(hint);

  overlay.addEventListener('mousemove', onHover);
  overlay.addEventListener('click', onSelect);
  document.addEventListener('keydown', onEsc);
}

function deactivateSelector() {
  selectorActive = false;
  ['vp-overlay','vp-highlight','vp-hint','vp-save-panel','vp-styles'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.remove();
  });
  overlay = null; highlightBox = null; savePanel = null; selectedElement = null;
  document.removeEventListener('keydown', onEsc);
}

function onEsc(e) { if (e.key === 'Escape') deactivateSelector(); }

function onHover(e) {
  if (!selectorActive || !highlightBox) return;
  overlay.style.pointerEvents = 'none';
  const el = document.elementFromPoint(e.clientX, e.clientY);
  overlay.style.pointerEvents = 'auto';
  if (!el || el === document.body || el === document.documentElement) { highlightBox.style.display = 'none'; return; }
  const post = findClosestPost(el);
  if (!post) { highlightBox.style.display = 'none'; return; }
  const rect = post.getBoundingClientRect();
  highlightBox.style.display = 'block';
  highlightBox.style.top = rect.top + 'px';
  highlightBox.style.left = rect.left + 'px';
  highlightBox.style.width = rect.width + 'px';
  highlightBox.style.height = rect.height + 'px';
  selectedElement = post;
}

function onSelect(e) {
  e.preventDefault();
  e.stopPropagation();
  if (!selectedElement) return;
  const el = selectedElement;
  const hint = document.getElementById('vp-hint');
  if (hint) hint.style.display = 'none';
  overlay.style.background = 'rgba(0,0,0,0.1)';
  overlay.removeEventListener('mousemove', onHover);
  overlay.removeEventListener('click', onSelect);
  overlay.style.pointerEvents = 'none';
  highlightBox.style.border = '2.5px solid #16a34a';
  highlightBox.style.boxShadow = '0 0 0 4px rgba(22,163,74,0.1)';
  showSavePanel(extractFromElement(el));
}

function extractFromElement(el) {
  const hostname = window.location.hostname.replace('www.', '');
  const text = el.innerText || '';
  let author = '', postUrl = window.location.href;
  if (hostname === 'x.com' || hostname === 'twitter.com') {
    author = el.querySelector('[data-testid="User-Name"] a')?.textContent || '';
    const link = el.querySelector('a[href*="/status/"]');
    if (link) postUrl = link.href;
  } else if (hostname === 'reddit.com') {
    author = el.querySelector('[data-testid="post_author_link"], .author')?.textContent || '';
    const link = el.querySelector('a[href*="/comments/"]');
    if (link) postUrl = link.href;
  } else if (hostname.includes('youtube.com')) {
    author = el.querySelector('#channel-name a, .ytd-channel-name a')?.textContent || '';
  } else if (hostname.includes('linkedin.com')) {
    author = el.querySelector('.feed-shared-actor__name, .update-components-actor__name')?.textContent || '';
  } else {
    author = document.querySelector('meta[name="author"]')?.content || '';
  }
  return { author: author.trim(), content: text.slice(0, 3000), engagement: {}, hashtags: (text.match(/#(\w+)/g) || []).map(h => h.slice(1)), url: postUrl };
}

function showSavePanel(metadata) {
  const platMap = {
    'x.com':{ bg:'#eef6ff', c:'#1c1917', l:'X' }, 'twitter.com':{ bg:'#eef6ff', c:'#1c1917', l:'X' },
    'reddit.com':{ bg:'#fff2f0', c:'#FF4500', l:'Reddit' }, 'tiktok.com':{ bg:'#f0fffe', c:'#000', l:'TikTok' },
    'instagram.com':{ bg:'#fef2f8', c:'#E1306C', l:'Instagram' }, 'youtube.com':{ bg:'#fef2f2', c:'#FF0000', l:'YouTube' },
    'linkedin.com':{ bg:'#eff6ff', c:'#0A66C2', l:'LinkedIn' },
  };
  const hostname = window.location.hostname.replace('www.', '');
  const p = platMap[hostname] || { bg:'#f5f5f4', c:'#57534e', l:'Web' };
  const preview = metadata.content.slice(0, 100) + (metadata.content.length > 100 ? '...' : '');

  savePanel = document.createElement('div');
  savePanel.id = 'vp-save-panel';
  savePanel.innerHTML = `
    <div class="body" id="vp-body">
      <div class="meta"><span class="pbadge" style="background:${p.bg};color:${p.c};">${p.l}</span><span class="author">${metadata.author || 'Unknown'}</span></div>
      <div class="preview-text">${preview}</div>
      <textarea class="note-input" id="vp-note" placeholder="Why is this worth saving? e.g. 'killer hook' 'study this format'"></textarea>
      <div class="tags" id="vp-tags">
        <span class="tag" data-t="hook">Hook</span><span class="tag" data-t="format">Format</span>
        <span class="tag" data-t="competitor">Competitor</span><span class="tag" data-t="tone">Tone</span>
        <span class="tag" data-t="cta">CTA</span><span class="tag" data-t="visual">Visual</span>
        <span class="tag" data-t="headline">Headline</span>
      </div>
      <div class="prog" id="vp-prog"><div class="prog-bar"></div></div>
      <button class="sbtn" id="vp-sbtn">Save to Library</button>
      <button class="cancel" id="vp-cancel">Cancel</button>
    </div>
    <div id="vp-success" style="display:none;">
      <div class="chk"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="3" stroke-linecap="round"><path d="M5 13l4 4L19 7"/></svg></div>
      <div style="font-size:15px;font-weight:600;color:#1c1917;">Saved!</div>
      <div style="font-size:12px;color:#78716c;margin-top:4px;">Your agent will reference this</div>
    </div>`;
  document.body.appendChild(savePanel);

  savePanel.querySelectorAll('.tag').forEach(t => t.addEventListener('click', () => t.classList.toggle('on')));
  document.getElementById('vp-cancel').addEventListener('click', deactivateSelector);
  document.getElementById('vp-sbtn').addEventListener('click', () => doSave(metadata));
}

async function elementToDataUrl(el) {
  // Capture the selected element as a full-size screenshot using canvas
  // This works for elements taller than the viewport
  try {
    const rect = el.getBoundingClientRect();
    const scrollTop = window.scrollY;
    const scrollLeft = window.scrollX;

    // Use a canvas to draw the element
    const canvas = document.createElement('canvas');
    const scale = window.devicePixelRatio || 1;
    // Cap at reasonable size (max 4000px tall)
    const maxH = Math.min(el.scrollHeight || rect.height, 4000);
    const w = Math.min(el.scrollWidth || rect.width, 1400);
    canvas.width = w * scale;
    canvas.height = maxH * scale;
    canvas.style.width = w + 'px';
    canvas.style.height = maxH + 'px';

    // Fallback: just request background to capture visible tab
    // (canvas rendering of arbitrary DOM is unreliable without html2canvas)
    return null;
  } catch (e) {
    return null;
  }
}

async function doSave(metadata) {
  const btn = document.getElementById('vp-sbtn');
  const prog = document.getElementById('vp-prog');
  const note = document.getElementById('vp-note').value.trim();
  const tags = [...document.querySelectorAll('#vp-tags .tag.on')].map(t => t.dataset.t);
  const fullNote = [note, ...tags.map(t => `#${t}`)].filter(Boolean).join(' ');

  btn.disabled = true; btn.textContent = 'Capturing...'; prog.classList.add('on');

  try {
    // Scroll the selected element into view before screenshot
    if (selectedElement) {
      selectedElement.scrollIntoView({ behavior: 'instant', block: 'start' });
      await new Promise(r => setTimeout(r, 300));
    }

    // Send to background — it will capture the visible tab
    // No chrome.tabs.query here (not available in content scripts)
    const result = await chrome.runtime.sendMessage({
      type: 'SAVE_POST',
      metadata: { author: metadata.author, content: metadata.content, engagement: metadata.engagement, hashtags: metadata.hashtags },
      userNote: fullNote || null,
      url: metadata.url || window.location.href,
    });
    if (result.error) throw new Error(result.error);

    prog.classList.remove('on');
    document.getElementById('vp-body').style.display = 'none';
    document.getElementById('vp-success').style.display = 'block';
    setTimeout(deactivateSelector, 2000);
  } catch (e) {
    prog.classList.remove('on');
    btn.disabled = false; btn.textContent = 'Save to Library';
    alert('Save failed: ' + e.message);
  }
}

// Listen for activation from popup or keyboard shortcut
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'ACTIVATE_SELECTOR') { activateSelector(); sendResponse({ ok: true }); }
  else if (msg.type === 'EXTRACT_METADATA') { sendResponse(extractFromElement(document.body)); }
  return true;
});
