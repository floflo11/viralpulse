const saveBtn = document.getElementById('saveBtn');
const noteEl = document.getElementById('note');
const statusEl = document.getElementById('status');
const apiKeyInput = document.getElementById('apiKeyInput');
const pageInfo = document.getElementById('pageInfo');
const progress = document.getElementById('progress');
const mainPanel = document.getElementById('mainPanel');
const successPanel = document.getElementById('successPanel');
const savedPlatform = document.getElementById('savedPlatform');
const savedNote = document.getElementById('savedNote');
const savedCount = document.getElementById('savedCount');

// Show current page URL
chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
  if (tab) {
    pageInfo.textContent = tab.url;
  }
});

// Load saved API key
chrome.storage.sync.get('apiKey', ({ apiKey }) => {
  if (apiKey) {
    apiKeyInput.value = apiKey;
    apiKeyInput.parentElement.style.display = 'none';
    // Show saved count
    fetchSavedCount(apiKey);
  }
});

// Save API key on change
apiKeyInput.addEventListener('change', () => {
  const key = apiKeyInput.value.trim();
  if (key) {
    chrome.storage.sync.set({ apiKey: key });
    statusEl.textContent = 'API key saved!';
    statusEl.className = 'status';
    statusEl.style.color = '#16a34a';
    setTimeout(() => { statusEl.textContent = ''; }, 2000);
  }
});

async function fetchSavedCount(apiKey) {
  try {
    const resp = await fetch('https://api.aithatjustworks.com/api/v1/saved?limit=1', {
      headers: { 'X-API-Key': apiKey },
    });
    if (resp.ok) {
      const data = await resp.json();
      savedCount.innerHTML = `${data.count} posts saved &middot; <a href="https://api.aithatjustworks.com/api/v1/saved" target="_blank">View library</a>`;
    }
  } catch (e) { /* silent */ }
}

saveBtn.addEventListener('click', async () => {
  const { apiKey } = await chrome.storage.sync.get('apiKey');
  if (!apiKey) {
    statusEl.textContent = 'Enter your API key below first';
    statusEl.className = 'status error';
    apiKeyInput.parentElement.style.display = 'block';
    apiKeyInput.focus();
    return;
  }

  // UI: saving state
  saveBtn.disabled = true;
  saveBtn.textContent = 'Capturing screenshot...';
  saveBtn.className = 'save-btn saving';
  progress.classList.add('show');
  statusEl.textContent = '';

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Try to inject + extract metadata
    saveBtn.textContent = 'Extracting content...';
    let metadata = {};
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js'],
      });
      await new Promise(r => setTimeout(r, 300));
      metadata = await chrome.tabs.sendMessage(tab.id, { type: 'EXTRACT_METADATA' });
    } catch (e) {
      console.log('Content extraction failed, saving URL + screenshot only:', e);
      metadata = { author: '', content: '', engagement: {}, hashtags: [] };
    }

    // Capture + upload
    saveBtn.textContent = 'Uploading...';
    const result = await chrome.runtime.sendMessage({
      type: 'SAVE_POST',
      metadata,
      userNote: noteEl.value.trim() || null,
      tabId: tab.id,
    });

    if (result.error) throw new Error(result.error);

    // Success!
    progress.classList.remove('show');
    mainPanel.style.display = 'none';
    successPanel.classList.add('show');
    savedPlatform.textContent = result.platform || 'web';
    if (noteEl.value.trim()) {
      savedNote.textContent = '"' + noteEl.value.trim() + '"';
    }

    // Update count
    fetchSavedCount(apiKey);

    // Auto-close after 2.5s
    setTimeout(() => window.close(), 2500);

  } catch (e) {
    progress.classList.remove('show');
    statusEl.textContent = e.message;
    statusEl.className = 'status error';
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save to Library';
    saveBtn.className = 'save-btn';
  }
});
