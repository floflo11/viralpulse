from unittest.mock import patch, MagicMock
from viralpulse.crawler import crawl_topic
from viralpulse.platforms.base import RawPost


def _fake_post(platform: str, idx: int) -> RawPost:
    return RawPost(
        platform=platform,
        platform_id=f"{platform}-{idx}",
        url=f"https://example.com/{platform}/{idx}",
        author=f"@user{idx}",
        author_url=None,
        title=f"Post {idx}",
        content=f"Content about AI tools {idx}",
        media_url=None,
        published_at="2026-03-12T14:30:00+00:00",
        likes=100 * idx,
        comments=10 * idx,
    )


@patch("viralpulse.crawler.CRAWLERS")
def test_crawl_topic_collects_from_all_platforms(mock_crawlers):
    mock_twitter = MagicMock()
    mock_twitter.return_value.search.return_value = [_fake_post("twitter", 1)]
    mock_reddit = MagicMock()
    mock_reddit.return_value.search.return_value = [_fake_post("reddit", 1)]

    mock_crawlers.get.side_effect = lambda k: {"twitter": mock_twitter, "reddit": mock_reddit}.get(k)

    results = crawl_topic("AI tools", api_key="test", platforms=["twitter", "reddit"])
    assert len(results) == 2
    platforms = {r.platform for r in results}
    assert "twitter" in platforms
    assert "reddit" in platforms


@patch("viralpulse.crawler.CRAWLERS")
def test_crawl_topic_handles_platform_error(mock_crawlers):
    mock_twitter = MagicMock()
    mock_twitter.return_value.search.side_effect = Exception("API error")
    mock_reddit = MagicMock()
    mock_reddit.return_value.search.return_value = [_fake_post("reddit", 1)]

    mock_crawlers.get.side_effect = lambda k: {"twitter": mock_twitter, "reddit": mock_reddit}.get(k)

    results = crawl_topic("AI tools", api_key="test", platforms=["twitter", "reddit"])
    assert len(results) == 1
    assert results[0].platform == "reddit"
