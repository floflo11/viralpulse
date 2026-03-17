"""Scoring engine: relevance, engagement normalization, velocity, composite."""

from typing import List

from viralpulse.query import tokenize


def compute_relevance(query: str, text: str, hashtags: List[str] = None) -> float:
    """Bidirectional token overlap between query and text. Returns 0-1."""
    q_tokens = tokenize(query)
    combined = text
    if hashtags:
        combined = f"{text} {' '.join(hashtags)}"
    t_tokens = tokenize(combined)

    if not q_tokens:
        return 0.5

    overlap = len(q_tokens & t_tokens)
    ratio = overlap / len(q_tokens)
    return max(0.1, min(1.0, ratio))


def compute_velocity(likes: int = 0, hours_old: float = 1.0) -> float:
    """Engagement per hour. Higher = faster growing content."""
    hours = max(hours_old, 0.1)
    return likes / hours


def normalize_engagement(values: List[float]) -> List[float]:
    """Percentile normalization: map values to 0-1 range."""
    if not values:
        return []
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return [0.5] * len(values)
    return [(v - min_v) / (max_v - min_v) for v in values]


def compute_composite(
    relevance: float,
    engagement: float,
    velocity: float,
    weights: tuple = (0.3, 0.4, 0.3),
) -> float:
    """Weighted composite score. Default: 30% relevance, 40% engagement, 30% velocity."""
    w_r, w_e, w_v = weights
    return round(w_r * relevance + w_e * engagement + w_v * velocity, 4)
