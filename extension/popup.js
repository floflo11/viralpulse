const apiKeyInput = document.getElementById('apiKeyInput');
const statusEl = document.getElementById('status');
const savedCountEl = document.getElementById('savedCount');
const libraryLink = document.getElementById('libraryLink');
const injectBtn = document.getElementById('injectBtn');

const API_BASE = 'https://api.getfreedom.app';

// Load API key — try sync first, fall back to local
async function loadApiKey() {
  try {
    const result = await chrome.storage.sync.get('apiKey');
    if (result?.apiKey) return result.apiKey;
  } catch (e) { /* sync not available */ }
  try {
    const result = await chrome.storage.local.get('apiKey');
    if (result?.apiKey) return result.apiKey;
  } catch (e) { /* local not available */ }
  return null;
}

async function saveApiKey(key) {
  try { await chrome.storage.sync.set({ apiKey: key }); } catch (e) { /* ignore */ }
  try { await chrome.storage.local.set({ apiKey: key }); } catch (e) { /* ignore */ }
}

// Init
loadApiKey().then(apiKey => {
  if (apiKey) {
    apiKeyInput.value = apiKey;
    apiKeyInput.parentElement.style.display = 'none';
    libraryLink.href = `${API_BASE}/view/saved?key=${apiKey}`;
    fetchSavedCount(apiKey);
  }
});

// Save API key
apiKeyInput.addEventListener('change', async () => {
  const key = apiKeyInput.value.trim();
  if (key) {
    await saveApiKey(key);
    libraryLink.href = `${API_BASE}/view/saved?key=${key}`;
    statusEl.textContent = 'Key saved!';
    statusEl.style.color = '#16a34a';
    fetchSavedCount(key);
    setTimeout(() => { statusEl.textContent = ''; }, 2000);
  }
});

async function fetchSavedCount(apiKey) {
  try {
    const resp = await fetch(`${API_BASE}/api/v1/saved?limit=1`, {
      headers: { 'X-API-Key': apiKey },
    });
    if (resp.ok) {
      const data = await resp.json();
      savedCountEl.textContent = `${data.count} posts saved`;
    }
  } catch (e) { savedCountEl.textContent = ''; }
}

// Manual inject button
injectBtn.addEventListener('click', async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content.js'],
    });
    injectBtn.textContent = 'Activated! Check the page.';
    injectBtn.style.background = '#16a34a';
    setTimeout(() => window.close(), 1500);
  } catch (e) {
    injectBtn.textContent = 'Cannot access this page';
    injectBtn.style.background = '#dc2626';
  }
});
