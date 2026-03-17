const API_BASE = 'https://api.aithatjustworks.com';

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'SAVE_POST') {
    handleSave(msg).then(sendResponse).catch(e => sendResponse({ error: e.message }));
    return true;
  }
});

async function handleSave({ metadata, userNote, tabId }) {
  const { apiKey } = await chrome.storage.sync.get('apiKey');
  if (!apiKey) throw new Error('No API key set. Open extension settings.');

  const dataUrl = await chrome.tabs.captureVisibleTab(null, { format: 'png' });
  const tab = await chrome.tabs.get(tabId);

  const resp = await fetch(`${API_BASE}/api/v1/save`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify({
      url: tab.url,
      screenshot_base64: dataUrl,
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
