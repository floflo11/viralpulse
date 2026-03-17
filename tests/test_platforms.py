import pytest
from unittest.mock import patch, MagicMock
from viralpulse.platforms import CRAWLERS, ALL_PLATFORMS
from viralpulse.platforms.base import RawPost


def test_all_platforms_registered():
    assert set(ALL_PLATFORMS) == {"twitter", "reddit", "tiktok", "instagram", "linkedin", "youtube"}


def test_crawlers_have_search_method():
    for name, cls in CRAWLERS.items():
        crawler = cls(api_key="test")
        assert hasattr(crawler, "search")
        assert crawler.PLATFORM == name


def _mock_response(data: dict):
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


@patch("httpx.get")
def test_twitter_search_parses(mock_get):
    mock_get.return_value = _mock_response({
        "tweets": [{
            "id": "123",
            "full_text": "AI is amazing",
            "user": {"screen_name": "testuser"},
            "favorite_count": 100,
            "retweet_count": 50,
            "reply_count": 10,
            "created_at": "Wed Mar 12 14:30:00 +0000 2026",
        }]
    })
    crawler = CRAWLERS["twitter"](api_key="test")
    posts = crawler.search("AI")
    assert len(posts) == 1
    assert posts[0].platform == "twitter"
    assert posts[0].likes == 100
    assert posts[0].author == "@testuser"


@patch("httpx.get")
def test_reddit_search_parses(mock_get):
    mock_get.return_value = _mock_response({
        "posts": [{
            "id": "abc",
            "title": "AI discussion",
            "permalink": "/r/tech/comments/abc/ai_discussion/",
            "author": "redditor",
            "ups": 500,
            "num_comments": 42,
            "selftext": "Long text here",
            "created_utc": 1741785600,
        }]
    })
    crawler = CRAWLERS["reddit"](api_key="test")
    posts = crawler.search("AI")
    assert len(posts) == 1
    assert posts[0].platform == "reddit"
    assert posts[0].likes == 500
    assert "reddit.com" in posts[0].url


@patch("httpx.get")
def test_tiktok_search_parses(mock_get):
    mock_get.return_value = _mock_response({
        "search_item_list": [{"aweme_info": {
            "aweme_id": "789",
            "desc": "Cool AI video #ai #tech",
            "statistics": {"play_count": 50000, "digg_count": 3000, "comment_count": 100, "share_count": 200},
            "author": {"unique_id": "creator1"},
            "create_time": 1741785600,
        }}]
    })
    crawler = CRAWLERS["tiktok"](api_key="test")
    posts = crawler.search("AI")
    assert len(posts) == 1
    assert posts[0].views == 50000
    assert posts[0].likes == 3000


@patch("httpx.get")
def test_instagram_search_parses(mock_get):
    mock_get.return_value = _mock_response({
        "reels": [{
            "id": "456",
            "shortcode": "ABC123",
            "caption": {"text": "Amazing #ai content"},
            "owner": {"username": "instauser"},
            "like_count": 200,
            "comment_count": 30,
            "video_play_count": 10000,
            "taken_at": "2026-03-12T14:00:00.000Z",
        }]
    })
    crawler = CRAWLERS["instagram"](api_key="test")
    posts = crawler.search("AI")
    assert len(posts) == 1
    assert posts[0].platform == "instagram"
    assert posts[0].likes == 200
    assert "instagram.com/reel/ABC123" in posts[0].url
    assert "ai" in posts[0].hashtags


@patch("httpx.get")
def test_linkedin_search_parses(mock_get):
    mock_get.return_value = _mock_response({
        "posts": [{
            "id": "li-123",
            "text": "AI is transforming business",
            "author_name": "John Doe",
            "url": "https://linkedin.com/posts/123",
            "likes": 150,
            "comments": 20,
        }]
    })
    crawler = CRAWLERS["linkedin"](api_key="test")
    posts = crawler.search("AI")
    assert len(posts) == 1
    assert posts[0].platform == "linkedin"
    assert posts[0].likes == 150


@patch("httpx.get")
def test_youtube_search_parses(mock_get):
    mock_get.return_value = _mock_response({
        "videos": [{
            "id": "yt-abc",
            "title": "Best AI Tools 2026",
            "description": "A review of top AI tools",
            "channel": {"name": "TechReview", "url": "https://youtube.com/@techreview"},
            "views": 100000,
            "likes": 5000,
            "published_at": "2026-03-10T10:00:00Z",
        }]
    })
    crawler = CRAWLERS["youtube"](api_key="test")
    posts = crawler.search("AI tools")
    assert len(posts) == 1
    assert posts[0].platform == "youtube"
    assert posts[0].views == 100000
    assert posts[0].title == "Best AI Tools 2026"
