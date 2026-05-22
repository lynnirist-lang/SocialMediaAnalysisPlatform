"""业务数据 ORM：帖子、评论、用户画像统计"""
from sqlalchemy import Column, Float, Integer, String, Text, UniqueConstraint

from backend.database import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(64), index=True)
    create_time = Column(String(32))
    create_date_time = Column(String(64), index=True)
    content = Column(Text)
    cleaned_content = Column(Text)
    nickname = Column(String(128))
    sentiment = Column(String(16))
    confidence = Column(Float)
    topic = Column(Integer)
    source_date = Column(String(16), index=True)
    data_json = Column(Text)


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(String(64), index=True)
    user_id = Column(String(64), index=True)
    create_time = Column(String(32))
    create_date_time = Column(String(64), index=True)
    content = Column(Text)
    cleaned_content = Column(Text)
    nickname = Column(String(128))
    sentiment = Column(String(16))
    confidence = Column(Float)
    source_date = Column(String(16), index=True)
    data_json = Column(Text)


class UserStats(Base):
    __tablename__ = "user_stats"
    __table_args__ = (UniqueConstraint("user_id", "stats_date", name="uq_user_stats_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)
    stats_date = Column(String(16), nullable=False, index=True)
    nickname = Column(String(128))
    post_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    total_actions = Column(Integer, default=0)
    total_likes_received = Column(Integer, default=0)
    fans_count = Column(Float)
    pagerank_score = Column(Float)
    betweenness_score = Column(Float)
    in_degree_weighted = Column(Integer)
    out_degree_weighted = Column(Integer)
    burst_power = Column(Float)
    response_speed = Column(Float)
    active_duration = Column(Float)
    originality_score = Column(Float)
    sentiment_intensity = Column(Float)
    data_json = Column(Text)
