from viralpulse.scoring import compute_relevance, compute_velocity, normalize_engagement, compute_composite


def test_relevance_exact_match():
    score = compute_relevance("AI video tools", "This AI video tool is amazing for editing")
    assert score > 0.5


def test_relevance_no_match():
    score = compute_relevance("AI video tools", "Best pizza recipes in New York")
    assert score < 0.3


def test_velocity_newer_is_faster():
    v1 = compute_velocity(likes=100, hours_old=1)
    v2 = compute_velocity(likes=100, hours_old=24)
    assert v1 > v2


def test_normalize_engagement():
    values = [10, 50, 100, 500, 1000]
    normalized = normalize_engagement(values)
    assert len(normalized) == 5
    assert all(0 <= v <= 1 for v in normalized)
    assert normalized[-1] == 1.0


def test_normalize_engagement_equal():
    values = [50, 50, 50]
    normalized = normalize_engagement(values)
    assert all(v == 0.5 for v in normalized)


def test_composite_weighted():
    score = compute_composite(relevance=1.0, engagement=1.0, velocity=1.0)
    assert score == 1.0

    score2 = compute_composite(relevance=0.0, engagement=0.0, velocity=0.0)
    assert score2 == 0.0
