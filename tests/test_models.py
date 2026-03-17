from viralpulse.models import PostResponse, Topic, Engagement, Scores


def test_post_response_serialization():
    post = PostResponse(
        id="abc-123",
        platform="twitter",
        url="https://x.com/user/status/123",
        author="@user",
        author_url="https://x.com/user",
        title=None,
        content="Great post",
        media_url=None,
        published_at="2026-03-12T14:30:00Z",
        engagement=Engagement(likes=100, comments=10, shares=5, views=1000, platform_score=0),
        scores=Scores(relevance=0.8, engagement_normalized=0.9, velocity=0.7, composite=0.85),
    )
    d = post.model_dump()
    assert d["platform"] == "twitter"
    assert d["scores"]["composite"] == 0.85


def test_topic_model():
    topic = Topic(id="abc", name="AI video tools", search_queries=["ai video", "ai video editing"])
    assert topic.name == "AI video tools"
    assert len(topic.search_queries) == 2
