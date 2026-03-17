const apiKeyInput = document.getElementById('apiKeyInput');
const statusEl = document.getElementById('status');
const savedCountEl = document.getElementById('savedCount');
const libraryLink = document.getElementById('libraryLink');
const injectBtn = document.getElementById('injectBtn');

// Load API key
chrome.storage.sync.get('apiKey', ({ apiKey }) => {
  if (apiKey) {
    apiKeyInput.value = apiKey;
    apiKeyInput.parentElement.style.display = 'none';
    libraryLink.href = `https://api.aithatjustworks.com/view/saved?key=${apiKey}`;
    fetchSavedCount(apiKey);
  }
});

// Save API key
apiKeyInput.addEventListener('change', () => {
  const key = apiKeyInput.value.trim();
  if (key) {
    chrome.storage.sync.set({ apiKey: key });
    libraryLink.href = `https://api.aithatjustworks.com/view/saved?key=${key}`;
    statusEl.textContent = 'Key saved!';
    statusEl.style.color = '#16a34a';
    fetchSavedCount(key);
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
      savedCountEl.textContent = `${data.count} posts saved`;
    }
  } catch (e) { savedCountEl.textContent = ''; }
}

// Manual inject button — forces content script onto current page
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
