from pydantic import BaseModel
from typing import List, Optional,Any
from datetime import date


# 通用响应模型
class Response(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


# 数据看板
class DashboardSummary(BaseModel):
    total_posts: int
    total_users: int
    avg_sentiment: float
    date_range: dict


class TrendData(BaseModel):
    dates: List[str]
    post_counts: List[int]
    sentiment_scores: List[float]


class WordCloudItem(BaseModel):
    name: str
    value: int


class PostItem(BaseModel):
    content: str
    score: float
    date: str



# 用户画像
class UserProfile(BaseModel):
    user_id: str
    post_count: int
    reply_count: int
    total_actions: int
    total_likes_received: int
    fans_count: Optional[float]
    pagerank_score: float
    betweenness_score: float
    in_degree_weighted: int
    out_degree_weighted: int
    burst_power: float
    response_speed: float
    active_duration: float
    originality_score: float
    sentiment_intensity: float
    user_role: Optional[str]