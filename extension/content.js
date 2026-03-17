function extractMetadata() {
  const hostname = window.location.hostname.replace('www.', '');
  const extractors = {
    'x.com': extractTwitter,
    'twitter.com': extractTwitter,
    'reddit.com': extractReddit,
    'tiktok.com': extractTikTok,
    'instagram.com': extractInstagram,
    'youtube.com': extractYouTube,
    'linkedin.com': extractLinkedIn,
  };
  const extractor = extractors[hostname];
  if (extractor) {
    try { return extractor(); } catch (e) { console.log('ViralPulse: platform extractor failed, using generic', e); }
  }
  return extractGeneric();
}

function extractTwitter() {
  const article = document.querySelector('article');
  if (!article) return extractGeneric();
  const author = article.querySelector('[data-testid="User-Name"] a')?.textContent || '';
  const content = article.querySelector('[data-testid="tweetText"]')?.textContent || '';
  return { author, content, engagement: {}, hashtags: extractHashtags(content) };
}

function extractReddit() {
  const title = document.querySelector('[data-testid="post-title"], h1')?.textContent || '';
  const body = document.querySelector('[slot="text-body"], .usertext-body')?.textContent || '';
  const author = document.querySelector('[data-testid="post_author_link"], .author')?.textContent || '';
  return { author, content: title + '\n' + body, engagement: {}, hashtags: [] };
}

function extractTikTok() {
  const author = document.querySelector('[data-e2e="browse-username"], .author-uniqueId')?.textContent || '';
  const content = document.querySelector('[data-e2e="browse-video-desc"], .video-meta-title')?.textContent || '';
  return { author, content, engagement: {}, hashtags: extractHashtags(content) };
}

function extractInstagram() {
  const author = document.querySelector('header a')?.textContent || '';
  const content = document.querySelector('h1, [data-testid="post-comment-root"] span')?.textContent || '';
  return { author, content, engagement: {}, hashtags: extractHashtags(content) };
}

function extractYouTube() {
  const title = document.querySelector('h1.ytd-watch-metadata, h1.title')?.textContent || '';
  const channel = document.querySelector('#channel-name a, .ytd-channel-name a')?.textContent || '';
  const desc = document.querySelector('#description-inner, .ytd-text-inline-expander')?.textContent || '';
  return { author: channel, content: title + '\n' + desc.slice(0, 1000), engagement: {}, hashtags: extractHashtags(desc) };
}

function extractLinkedIn() {
  const author = document.querySelector('.feed-shared-actor__name, .update-components-actor__name')?.textContent || '';
  const content = document.querySelector('.feed-shared-text, .update-components-text')?.textContent || '';
  return { author, content, engagement: {}, hashtags: extractHashtags(content) };
}

function extractGeneric() {
  const ogTitle = document.querySelector('meta[property="og:title"]')?.content || '';
  const ogDesc = document.querySelector('meta[property="og:description"]')?.content || '';
  const author = document.querySelector('meta[name="author"]')?.content
    || document.querySelector('[rel="author"], .author, .byline')?.textContent || '';
  const articleText = document.querySelector('article, main, [role="main"]')?.innerText?.slice(0, 3000) || '';
  const content = ogTitle + (ogDesc ? '\n' + ogDesc : '') + (articleText ? '\n' + articleText : '') || document.title;
  return { author, content, engagement: {}, hashtags: extractHashtags(content) };
}

function extractHashtags(text) {
  const matches = text.match(/#(\w+)/g) || [];
  return matches.map(h => h.slice(1));
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'EXTRACT_METADATA') {
    sendResponse(extractMetadata());
  }
  return true;
});
