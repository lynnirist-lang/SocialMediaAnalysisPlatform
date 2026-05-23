"""三层数据热度迁移管理器

层级定义：
  热层 (hot)  — Redis 缓存，TTL 7200s，高频近期数据
  温层 (warm) — Redis 缓存，TTL 3600s，中等频率或较新数据
  冷层 (cold) — 不缓存，仅 SQLite / CSV，低频历史数据

热度公式：
  heat = 0.5 * access_freq + 0.3 * recency + 0.2 * importance
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional


# ── 阈值 ──────────────────────────────────────────────────────────
HOT_SCORE = 0.65       # heat >= HOT_SCORE  → 热层
WARM_SCORE = 0.30      # heat >= WARM_SCORE → 温层（否则冷层）

HOT_TTL = 7200         # 2 小时
WARM_TTL = 3600        # 1 小时
COLD_TTL = 0           # 不缓存

RECENCY_HALF_LIFE_DAYS = 14   # 14 天后时效性衰减到 0.5
MAX_ACCESS_WINDOW_HOURS = 24  # 统计过去 24h 访问量
NORM_ACCESS_SATURATION = 50   # 50 次访问即视为访问频率 = 1.0


class DataTierManager:
    """基于访问频率 + 时效性 + 数据重要性的三层热度管理器"""

    TIERS = {
        'hot':  {'min_score': HOT_SCORE,  'ttl': HOT_TTL,  'label': '热层'},
        'warm': {'min_score': WARM_SCORE, 'ttl': WARM_TTL, 'label': '温层'},
        'cold': {'min_score': 0.0,        'ttl': COLD_TTL, 'label': '冷层'},
    }

    _ACCESS_PREFIX = 'access:'
    _HEAT_PREFIX   = 'heat:'

    def __init__(self, redis_client=None):
        self.redis = redis_client

    # ── 访问记录 ──────────────────────────────────────────────────

    def record_access(self, data_key: str) -> None:
        """每次数据被加载时调用，按小时滑动窗口计数"""
        if not self.redis:
            return
        try:
            hour_bucket = f"{self._ACCESS_PREFIX}{data_key}:{datetime.now().strftime('%Y%m%d%H')}"
            pipe = self.redis.pipeline()
            pipe.incr(hour_bucket)
            pipe.expire(hour_bucket, 86400)  # 桶 key 保留 24h
            pipe.execute()
        except Exception:
            pass

    def get_access_frequency(self, data_key: str) -> float:
        """返回过去 24h 的归一化访问频率 [0, 1]"""
        if not self.redis:
            return 0.0
        try:
            now = datetime.now()
            total = 0
            for h in range(MAX_ACCESS_WINDOW_HOURS):
                t = now - timedelta(hours=h)
                bucket = f"{self._ACCESS_PREFIX}{data_key}:{t.strftime('%Y%m%d%H')}"
                val = self.redis.get(bucket)
                if val:
                    total += int(val)
            return min(total / NORM_ACCESS_SATURATION, 1.0)
        except Exception:
            return 0.0

    # ── 热度计算 ──────────────────────────────────────────────────

    @staticmethod
    def _recency_score(data_date: Optional[str]) -> float:
        """基于半衰期的时效性得分 [0, 1]"""
        if not data_date:
            return 0.5
        try:
            date = datetime.strptime(str(data_date)[:10], '%Y-%m-%d')
            age_days = max((datetime.now() - date).days, 0)
            return math.exp(-age_days * math.log(2) / RECENCY_HALF_LIFE_DAYS)
        except Exception:
            return 0.5

    def calculate_heat_score(
        self,
        data_key: str,
        data_date: Optional[str] = None,
        importance: float = 0.5,
    ) -> float:
        """
        综合热度得分 [0, 1]
          data_key   : 标识数据集的字符串（与缓存 key 对应）
          data_date  : 数据所属日期（YYYY-MM-DD），用于时效性
          importance : 外部注入的重要性分值，如归一化 PageRank 均值
        """
        access = self.get_access_frequency(data_key)
        recency = self._recency_score(data_date)
        heat = 0.5 * access + 0.3 * recency + 0.2 * min(max(importance, 0.0), 1.0)
        score = round(min(heat, 1.0), 4)

        # 缓存热度得分本身，便于监控
        self._cache_heat_score(data_key, score)
        return score

    def _cache_heat_score(self, data_key: str, score: float) -> None:
        if not self.redis:
            return
        try:
            self.redis.setex(f"{self._HEAT_PREFIX}{data_key}", 3600, str(score))
        except Exception:
            pass

    # ── 层级判定 ──────────────────────────────────────────────────

    def get_tier(self, heat_score: float) -> str:
        if heat_score >= HOT_SCORE:
            return 'hot'
        if heat_score >= WARM_SCORE:
            return 'warm'
        return 'cold'

    def get_dynamic_ttl(
        self,
        data_key: str,
        data_date: Optional[str] = None,
        importance: float = 0.5,
    ) -> int:
        """根据热度动态计算 Redis TTL；冷数据返回 0（不缓存）"""
        heat = self.calculate_heat_score(data_key, data_date, importance)
        tier = self.get_tier(heat)
        return self.TIERS[tier]['ttl']

    def should_cache(
        self,
        data_key: str,
        data_date: Optional[str] = None,
        importance: float = 0.5,
    ) -> bool:
        return self.get_dynamic_ttl(data_key, data_date, importance) > 0

    # ── 监控与运维 ────────────────────────────────────────────────

    def get_tier_stats(self) -> dict:
        """扫描所有已缓存的热度分值，统计三层分布"""
        if not self.redis:
            return {'error': 'Redis 不可用', 'hot': 0, 'warm': 0, 'cold': 0}
        try:
            keys = self.redis.keys(f'{self._HEAT_PREFIX}*')
            stats: dict = {'hot': 0, 'warm': 0, 'cold': 0, 'total': len(keys)}
            for k in keys:
                val = self.redis.get(k)
                if val:
                    tier = self.get_tier(float(val))
                    stats[tier] += 1
            return stats
        except Exception as e:
            return {'error': str(e)}

    def migrate_cold_data(
        self,
        session,
        cutoff_days: int = 60,
        dry_run: bool = True,
    ) -> dict:
        """
        将冷数据从 SQLite 归档：
          - 找出 source_date 超过 cutoff_days 且近期访问极低的帖子
          - dry_run=True  只统计，不实际删除
          - dry_run=False 实际从 SQLite 中删除（数据已持久化在 CSV）

        返回统计信息。
        """
        from backend.models.db_models import Post, Comment

        result: dict = {'archived_posts': 0, 'archived_comments': 0, 'dry_run': dry_run}
        cutoff_str = (datetime.now() - timedelta(days=cutoff_days)).strftime('%Y%m%d')

        try:
            old_posts = (
                session.query(Post)
                .filter(Post.source_date <= cutoff_str)
                .all()
            )
            cold_post_ids = []
            for post in old_posts:
                key = f"post:{post.source_date}"
                freq = self.get_access_frequency(key)
                if freq < 0.02:   # 过去 24h 几乎没有访问
                    cold_post_ids.append(post.note_id)

            result['archived_posts'] = len(cold_post_ids)

            old_comments = (
                session.query(Comment)
                .filter(Comment.source_date <= cutoff_str)
                .all()
            )
            cold_comment_ids = []
            for comment in old_comments:
                key = f"comment:{comment.source_date}"
                freq = self.get_access_frequency(key)
                if freq < 0.02:
                    cold_comment_ids.append(comment.id)

            result['archived_comments'] = len(cold_comment_ids)

            if not dry_run:
                if cold_post_ids:
                    session.query(Post).filter(Post.note_id.in_(cold_post_ids)).delete(
                        synchronize_session=False
                    )
                if cold_comment_ids:
                    session.query(Comment).filter(Comment.id.in_(cold_comment_ids)).delete(
                        synchronize_session=False
                    )
                session.commit()
                result['committed'] = True

        except Exception as e:
            result['error'] = str(e)
            session.rollback()

        return result
