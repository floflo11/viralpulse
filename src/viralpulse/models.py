"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class Engagement(BaseModel):
    likes: int = 0
    comments: int = 0
    shares: int = 0
    views: int = 0
    platform_score: int = 0


class Scores(BaseModel):
    relevance: float = 0.0
    engagement_normalized: float = 0.0
    velocity: float = 0.0
    composite: float = 0.0


class PostResponse(BaseModel):
    id: str
    platform: str
    url: str
    author: str
    author_url: Optional[str] = None
    title: Optional[str] = None
    content: str
    media_url: Optional[str] = None
    published_at: Optional[str] = None
    engagement: Engagement
    scores: Scores


class PostsListResponse(BaseModel):
    topic: str
    platform: str
    sort: str
    count: int
    fetched_at: str
    posts: List[PostResponse]


class Topic(BaseModel):
    id: str
    name: str
    search_queries: List[str] = []
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TopicCreate(BaseModel):
    name: str
    search_queries: List[str] = []


class PlatformStatus(BaseModel):
    name: str
    enabled: bool = True
    last_crawl: Optional[str] = None
    post_count: int = 0


class CrawlResult(BaseModel):
    topic: str
    platform: str
    posts_new: int = 0
    posts_updated: int = 0
    error: Optional[str] = None
    duration_seconds: float = 0.0
