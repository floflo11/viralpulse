from viralpulse.platform_detect import detect_platform


def test_twitter():
    assert detect_platform("https://x.com/OpenAI/status/123") == "twitter"
    assert detect_platform("https://twitter.com/user/status/456") == "twitter"


def test_reddit():
    assert detect_platform("https://www.reddit.com/r/tech/comments/abc") == "reddit"


def test_tiktok():
    assert detect_platform("https://www.tiktok.com/@user/video/123") == "tiktok"


def test_instagram():
    assert detect_platform("https://www.instagram.com/reel/ABC/") == "instagram"


def test_youtube():
    assert detect_platform("https://www.youtube.com/watch?v=abc") == "youtube"
    assert detect_platform("https://youtu.be/abc") == "youtube"


def test_linkedin():
    assert detect_platform("https://www.linkedin.com/posts/user-123") == "linkedin"


def test_generic():
    assert detect_platform("https://techcrunch.com/2026/03/article") == "web"
    assert detect_platform("https://substack.com/p/something") == "web"
