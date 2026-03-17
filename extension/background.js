const API_BASE = 'https://api.aithatjustworks.com';

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'SAVE_POST') {
    handleSave(msg, sender).then(sendResponse).catch(e => sendResponse({ error: e.message }));
    return true;
  }
});

async function handleSave({ metadata, userNote, tabId, url }, sender) {
  const { apiKey } = await chrome.storage.sync.get('apiKey');
  if (!apiKey) throw new Error('No API key set. Open the extension popup to set it.');

  // Use the sender tab if available (content script), otherwise use provided tabId
  const actualTabId = sender?.tab?.id || tabId;

  // Capture visible tab screenshot
  let screenshot_base64 = null;
  try {
    screenshot_base64 = await chrome.tabs.captureVisibleTab(null, { format: 'png' });
  } catch (e) {
    console.log('Screenshot capture failed:', e);
  }

  // Get URL from the tab if not provided
  if (!url && actualTabId) {
    const tab = await chrome.tabs.get(actualTabId);
    url = tab.url;
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
