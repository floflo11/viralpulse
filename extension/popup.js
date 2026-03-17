const saveBtn = document.getElementById('saveBtn');
const noteEl = document.getElementById('note');
const statusEl = document.getElementById('status');
const apiKeyInput = document.getElementById('apiKeyInput');

chrome.storage.sync.get('apiKey', ({ apiKey }) => {
  if (apiKey) {
    apiKeyInput.value = apiKey;
    apiKeyInput.parentElement.style.display = 'none';
  }
});

apiKeyInput.addEventListener('change', () => {
  const key = apiKeyInput.value.trim();
  if (key) {
    chrome.storage.sync.set({ apiKey: key });
    statusEl.textContent = 'API key saved';
    statusEl.className = 'status success';
  }
});

saveBtn.addEventListener('click', async () => {
  const { apiKey } = await chrome.storage.sync.get('apiKey');
  if (!apiKey) {
    statusEl.textContent = 'Please enter your API key first';
    statusEl.className = 'status error';
    apiKeyInput.parentElement.style.display = 'block';
    return;
  }

  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';
  statusEl.textContent = '';

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Try to inject content script if not already loaded
    let metadata = {};
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js'],
      });
      // Small delay for script to initialize
      await new Promise(r => setTimeout(r, 200));
      metadata = await chrome.tabs.sendMessage(tab.id, { type: 'EXTRACT_METADATA' });
    } catch (e) {
      console.log('Content script extraction failed, saving URL only:', e);
      metadata = { author: '', content: document.title || '', engagement: {}, hashtags: [] };
    }

    const result = await chrome.runtime.sendMessage({
      type: 'SAVE_POST',
      metadata,
      userNote: noteEl.value.trim() || null,
      tabId: tab.id,
    });

    if (result.error) throw new Error(result.error);

    statusEl.textContent = 'Saved! (' + result.platform + ')';
    statusEl.className = 'status success';
    saveBtn.textContent = 'Saved!';
    setTimeout(() => window.close(), 1500);
  } catch (e) {
    statusEl.textContent = e.message;
    statusEl.className = 'status error';
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save to Library';
  }
});
