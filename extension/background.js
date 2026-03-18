const API_BASE = 'https://api.getfreedom.app';

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'GET_API_KEY') {
    getApiKey().then(key => sendResponse({ apiKey: key }));
    return true;
  }
  if (msg.type === 'SAVE_POST') {
    handleSave(msg, sender).then(sendResponse).catch(e => sendResponse({ error: e.message }));
    return true;
  }
});

async function getApiKey() {
  try {
    const result = await chrome.storage.sync.get('apiKey');
    if (result?.apiKey) return result.apiKey;
  } catch (e) { /* sync failed */ }
  try {
    const result = await chrome.storage.local.get('apiKey');
    if (result?.apiKey) return result.apiKey;
  } catch (e) { /* local failed */ }
  return null;
}

async function handleSave({ metadata, userNote, tabId, url }, sender) {
  const apiKey = await getApiKey();
  if (!apiKey) throw new Error('No API key set. Open the Freedom extension popup to set it.');

  // Get tab from sender (content script) or provided tabId
  const actualTabId = sender?.tab?.id || tabId;

  // Get URL from sender tab if not provided
  if (!url) {
    if (sender?.tab?.url) {
      url = sender.tab.url;
    } else if (actualTabId) {
      try {
        const tab = await chrome.tabs.get(actualTabId);
        url = tab.url;
      } catch (e) { /* ignore */ }
    }
  }

  // Capture visible tab screenshot
  let screenshot_base64 = null;
  try {
    const windowId = sender?.tab?.windowId || null;
    screenshot_base64 = await chrome.tabs.captureVisibleTab(windowId, { format: 'png' });
  } catch (e) {
    console.log('Screenshot capture failed:', e.message);
  }

  const resp = await fetch(`${API_BASE}/api/v1/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
    body: JSON.stringify({
      url,
      screenshot_base64,
      metadata,
      user_note: userNote || null,
    }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `API error: ${resp.status}`);
  }

  return resp.json();
}

// Keyboard shortcut support
chrome.commands?.onCommand?.addListener((command) => {
  if (command === 'activate-selector') {
    chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
      if (tab) {
        chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] })
          .then(() => chrome.tabs.sendMessage(tab.id, { type: 'ACTIVATE_SELECTOR' }))
          .catch(console.error);
      }
    });
  }
});
