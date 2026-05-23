import pandas as pd
from pathlib import Path
from datetime import datetime
import sys
import os
import re
import json
import hashlib

sys.path.insert(0, str(Path(__file__).parents[2]))
from config.config import (
    SENTIMENT_DATA_DIR,
    CLEANED_DATA_DIR,
    USER_CHARACTERS_DIR,
    USER_CHARACTERS_DATA_DIR,
    USE_DATABASE,
)

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class DataLoader:
    """统一数据加载服务（含三层热度感知缓存）"""

    def __init__(self, use_cache=True, cache_ttl=3600):
        self.base_dir = Path(__file__).parents[2]
        self.use_cache = use_cache and REDIS_AVAILABLE
        self.cache_ttl = cache_ttl

        if self.use_cache:
            try:
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=0,
                    decode_responses=True
                )
                self.redis_client.ping()
                print("[INFO] Redis 缓存已启用")
            except Exception as e:
                print(f"[WARNING] Redis 连接失败: {e}，降级为无缓存模式")
                self.use_cache = False
                self.redis_client = None
        else:
            self.redis_client = None

        self._db_available = None

        # 三层热度迁移管理器
        try:
            from backend.services.data_tier_manager import DataTierManager
            self.tier_manager = DataTierManager(
                redis_client=self.redis_client if self.use_cache else None
            )
        except Exception:
            self.tier_manager = None

    def _database_enabled(self) -> bool:
        """检测是否使用 SQLite（库表存在且有帖子数据）"""
        if not USE_DATABASE:
            return False
        if self._db_available is not None:
            return self._db_available
        try:
            from backend.database import SessionLocal, init_db
            from backend.models.db_models import Post

            init_db()
            with SessionLocal() as session:
                self._db_available = session.query(Post).count() > 0
        except Exception as e:
            print(f"[WARNING] 数据库不可用，回退 CSV: {e}")
            self._db_available = False
        return self._db_available

    def _posts_df_from_db(self, start_date=None, end_date=None) -> pd.DataFrame:
        from backend.database import SessionLocal
        from backend.models.db_models import Post
        from backend.services.db_sync import db_records_to_dataframe

        with SessionLocal() as session:
            rows = session.query(Post).all()
        df = db_records_to_dataframe([], rows)
        if df.empty:
            return df

        if 'note_id' in df.columns and 'sentiment' in df.columns:
            df['has_sentiment'] = df['sentiment'].notna()
            df = df.sort_values(['note_id', 'has_sentiment'], ascending=[True, False])
            df = df.drop_duplicates(subset='note_id', keep='first')
            df = df.drop(columns=['has_sentiment'], errors='ignore')

        if start_date and end_date and 'create_time' in df.columns:
            df['datetime'] = pd.to_datetime(df['create_time'], errors='coerce')
            mask = (df['datetime'].dt.date >= start_date) & (df['datetime'].dt.date <= end_date)
            df = df[mask]

        return df

    def _comments_df_from_db(self, start_date=None, end_date=None) -> pd.DataFrame:
        from backend.database import SessionLocal
        from backend.models.db_models import Comment
        from backend.services.db_sync import db_records_to_dataframe

        with SessionLocal() as session:
            rows = session.query(Comment).all()
        df = db_records_to_dataframe([], rows)
        if df.empty:
            return df

        if start_date and end_date and 'create_time' in df.columns:
            df['datetime'] = pd.to_datetime(df['create_time'], errors='coerce')
            mask = (df['datetime'].dt.date >= start_date) & (df['datetime'].dt.date <= end_date)
            df = df[mask]
        return df

    def _user_stats_df_from_db(self, start_date=None, end_date=None) -> pd.DataFrame:
        from backend.database import SessionLocal
        from backend.models.db_models import UserStats
        from backend.services.db_sync import db_records_to_dataframe

        with SessionLocal() as session:
            q = session.query(UserStats)
            if start_date and end_date and start_date == end_date:
                date_str = start_date.split(' ')[0] if ' ' in str(start_date) else str(start_date)
                q = q.filter(UserStats.stats_date == date_str)
                rows = q.all()
                if not rows:
                    return pd.DataFrame()
            else:
                rows = sorted(q.all(), key=lambda r: r.stats_date, reverse=True)
                if rows:
                    latest_date = rows[0].stats_date
                    rows = [r for r in rows if r.stats_date == latest_date]

        df = db_records_to_dataframe([], rows)
        if df.empty:
            return df

        if 'user_id' in df.columns:
            df['user_id'] = df['user_id'].astype(str).str.strip()
            df['user_id'] = df['user_id'].apply(lambda x: x[:-2] if x.endswith('.0') else x)
        return df

    def _generate_cache_key(self, prefix, **kwargs):
        """生成缓存键"""
        key_data = json.dumps(kwargs, sort_keys=True)
        hash_value = hashlib.md5(key_data.encode()).hexdigest()[:8]
        return f"{prefix}:{hash_value}"

    def _get_from_cache(self, key):
        """从缓存获取数据"""
        if not self.use_cache or not self.redis_client:
            return None
        try:
            data = self.redis_client.get(key)
            if data:
                print(f"[CACHE HIT] {key}")
                return json.loads(data)
        except Exception as e:
            print(f"[CACHE ERROR] 读取失败: {e}")
        return None

    def _set_to_cache(self, key, data, ttl: int | None = None):
        """将数据存入缓存；ttl 为 None 时使用默认 TTL；ttl=0 跳过缓存"""
        if not self.use_cache or not self.redis_client:
            return
        actual_ttl = ttl if ttl is not None else self.cache_ttl
        if actual_ttl <= 0:
            print(f"[CACHE SKIP] {key} (冷数据，不缓存)")
            return
        try:
            self.redis_client.setex(key, actual_ttl, json.dumps(data))
            print(f"[CACHE SET] {key} (TTL: {actual_ttl}s)")
        except Exception as e:
            print(f"[CACHE ERROR] 写入失败: {e}")

    def _tier_ttl(self, cache_key: str, data_date: str | None = None, importance: float = 0.5) -> int:
        """通过热度管理器获取动态 TTL；无管理器时退回默认 TTL"""
        if self.tier_manager is None:
            return self.cache_ttl
        self.tier_manager.record_access(cache_key)
        return self.tier_manager.get_dynamic_ttl(cache_key, data_date, importance)

    def _invalidate_cache_pattern(self, pattern):
        """清除匹配模式的缓存"""
        if not self.use_cache or not self.redis_client:
            return
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                print(f"[CACHE INVALIDATE] 清除 {len(keys)} 个缓存键")
        except Exception as e:
            print(f"[CACHE ERROR] 清除失败: {e}")

    def _load_sentiment_map(self, sentiment_file):
        """加载情感数据映射表"""
        if not sentiment_file or not sentiment_file.exists():
            return {}

        cache_key = self._generate_cache_key("sentiment", file=str(sentiment_file))
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            df = pd.read_csv(sentiment_file, encoding='utf-8-sig')
            if 'note_id' in df.columns and 'label' in df.columns:
                label_map = {0: '积极', 1: '消极', 2: '中性'}
                df['sentiment'] = df['label'].map(label_map)
                result = dict(zip(df['note_id'], df[['sentiment', '置信度']].values.tolist()))
                self._set_to_cache(cache_key, result)
                return result
        except Exception as e:
            print(f"加载情感数据失败 {sentiment_file}: {e}")

        return {}

    def load_posts(self, start_date=None, end_date=None):
        """加载所有帖子数据（包含情感标注）"""
        cache_key = self._generate_cache_key(
            "posts",
            start_date=str(start_date),
            end_date=str(end_date),
            source="db" if self._database_enabled() else "csv",
        )

        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        if self._database_enabled():
            df_all = self._posts_df_from_db(start_date, end_date)
            print(f"[DEBUG] 从数据库加载帖子: {len(df_all)} 条")
            date_hint = str(start_date) if start_date else None
            ttl = self._tier_ttl(cache_key, date_hint)
            self._set_to_cache(cache_key, df_all.to_dict('records'), ttl=ttl)
            return df_all

        all_files = list(CLEANED_DATA_DIR.glob('posts_cleaned_merged*.csv'))

        # 如果没有 merged 文件，再回退到普通 cleaned 文件
        if not all_files:
            all_files = list(CLEANED_DATA_DIR.glob('posts_cleaned_*.csv'))

        if not all_files:
            fixed_file = CLEANED_DATA_DIR / 'posts_cleaned.csv'
            if fixed_file.exists():
                all_files = [fixed_file]

        print(f"[DEBUG] 找到 {len(all_files)} 个帖子文件: {[f.name for f in all_files]}")

        merged_files = [f for f in all_files if 'merged' in f.name]
        regular_files = [f for f in all_files if 'merged' not in f.name]

        date_map = {}
        for f in merged_files:
            match = re.search(r'(\d{8})', f.name)
            if match:
                date_map[match.group(1)] = f

        for f in regular_files:
            match = re.search(r'(\d{8})', f.name)
            if match:
                date_str = match.group(1)
                if date_str not in date_map:
                    date_map[date_str] = f

        selected_files = sorted(date_map.values())
        print(f"[DEBUG] 去重后选择 {len(selected_files)} 个文件: {[f.name for f in selected_files]}")

        dfs = []
        for posts_file in selected_files:
            try:
                df = pd.read_csv(posts_file, encoding='utf-8-sig')
                print(f"[DEBUG] 加载 {posts_file.name}: {len(df)} 条")

                date_str = ''
                match = re.search(r'(\d{8})', posts_file.name)
                if match:
                    date_str = match.group(1)

                sentiment_file = SENTIMENT_DATA_DIR / f"posts_model_{date_str}.csv"
                sentiment_map = self._load_sentiment_map(sentiment_file)

                if sentiment_map and 'note_id' in df.columns:
                    sentiments = []
                    confidence_scores = []
                    matched = 0
                    for note_id in df['note_id']:
                        if note_id in sentiment_map:
                            sent, conf = sentiment_map[note_id]
                            sentiments.append(sent)
                            confidence_scores.append(conf)
                            matched += 1
                        else:
                            sentiments.append(None)
                            confidence_scores.append(None)

                    df['sentiment'] = sentiments
                    df['置信度'] = confidence_scores
                    print(f"[DEBUG]   情感匹配: {matched}/{len(df)}")

                dfs.append(df)
            except Exception as e:
                print(f"[ERROR] 加载文件 {posts_file} 失败: {e}")
                import traceback
                traceback.print_exc()

        if not dfs:
            print("[WARNING] 没有加载到任何帖子数据")
            return pd.DataFrame()

        df_all = pd.concat(dfs, ignore_index=True)
        print(f"[DEBUG] 合并后总计: {len(df_all)} 条帖子")
        if 'note_id' in df_all.columns and 'sentiment' in df_all.columns:
            # 标记有情感的记录
            df_all['has_sentiment'] = df_all['sentiment'].notna()

            # 按 note_id 和 has_sentiment 排序（True 在前）
            df_all = df_all.sort_values(['note_id', 'has_sentiment'], ascending=[True, False])

            # 按 note_id 去重，保留第一条（即有情感的）
            df_all = df_all.drop_duplicates(subset='note_id', keep='first')

            # 删除临时列
            df_all = df_all.drop(columns=['has_sentiment'])

            print(f"[DEBUG] 去重后: {len(df_all)} 条帖子（原始: {df_all.shape[0]}）")

        if start_date and end_date and 'create_time' in df_all.columns:
            df_all['datetime'] = pd.to_datetime(df_all['create_time'])
            mask = (df_all['datetime'].dt.date >= start_date) & \
                   (df_all['datetime'].dt.date <= end_date)
            df_all = df_all[mask]
            print(f"[DEBUG] 日期过滤后: {len(df_all)} 条")

        date_hint = str(start_date) if start_date else None
        ttl = self._tier_ttl(cache_key, date_hint)
        self._set_to_cache(cache_key, df_all.to_dict('records'), ttl=ttl)
        return df_all

    def load_comments(self, start_date=None, end_date=None):
        """加载所有评论数据（包含情感标注）"""
        cache_key = self._generate_cache_key(
            "comments",
            start_date=str(start_date),
            end_date=str(end_date),
            source="db" if self._database_enabled() else "csv",
        )

        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        if self._database_enabled():
            df_all = self._comments_df_from_db(start_date, end_date)
            print(f"[DEBUG] 从数据库加载评论: {len(df_all)} 条")
            date_hint = str(start_date) if start_date else None
            ttl = self._tier_ttl(cache_key, date_hint)
            self._set_to_cache(cache_key, df_all.to_dict('records'), ttl=ttl)
            return df_all

        all_files = list(CLEANED_DATA_DIR.glob('comments_cleaned_*.csv'))

        if not all_files:
            fixed_file = CLEANED_DATA_DIR / 'comments_cleaned.csv'
            if fixed_file.exists():
                all_files = [fixed_file]

        print(f"[DEBUG] 找到 {len(all_files)} 个评论文件")

        dfs = []
        for comments_file in sorted(all_files):
            try:
                df = pd.read_csv(comments_file, encoding='utf-8-sig')
                print(f"[DEBUG] 加载 {comments_file.name}: {len(df)} 条")

                date_str = ''
                match = re.search(r'(\d{8})', comments_file.name)
                if match:
                    date_str = match.group(1)

                sentiment_file = SENTIMENT_DATA_DIR / f"comments_model_{date_str}.csv"
                sentiment_map = self._load_sentiment_map(sentiment_file)

                if sentiment_map and 'note_id' in df.columns:
                    sentiments = []
                    confidence_scores = []
                    matched = 0
                    for note_id in df['note_id']:
                        if note_id in sentiment_map:
                            sent, conf = sentiment_map[note_id]
                            sentiments.append(sent)
                            confidence_scores.append(conf)
                            matched += 1
                        else:
                            sentiments.append(None)
                            confidence_scores.append(None)

                    df['sentiment'] = sentiments
                    df['置信度'] = confidence_scores
                    print(f"[DEBUG]   情感匹配: {matched}/{len(df)}")

                dfs.append(df)
            except Exception as e:
                print(f"[ERROR] 加载文件 {comments_file} 失败: {e}")

        if not dfs:
            print("[WARNING] 没有加载到任何评论数据")
            return pd.DataFrame()

        df_all = pd.concat(dfs, ignore_index=True)
        print(f"[DEBUG] 合并后总计: {len(df_all)} 条评论")

        if start_date and end_date and 'create_time' in df_all.columns:
            df_all['datetime'] = pd.to_datetime(df_all['create_time'])
            mask = (df_all['datetime'].dt.date >= start_date) & \
                   (df_all['datetime'].dt.date <= end_date)
            df_all = df_all[mask]
            print(f"[DEBUG] 日期过滤后: {len(df_all)} 条")

        date_hint = str(start_date) if start_date else None
        ttl = self._tier_ttl(cache_key, date_hint)
        self._set_to_cache(cache_key, df_all.to_dict('records'), ttl=ttl)
        return df_all

    def load_user_stats(self, start_date=None, end_date=None):
        """加载用户特征数据（支持按日期筛选）"""
        cache_key = self._generate_cache_key(
            "user_stats",
            start_date=str(start_date),
            end_date=str(end_date),
            source="db" if self._database_enabled() else "csv",
        )

        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        if self._database_enabled():
            df = self._user_stats_df_from_db(start_date, end_date)
            if not df.empty:
                df = self._enrich_user_nicknames(df)
                date_hint = str(start_date) if start_date else None
                # 用户画像重要性取 pagerank 均值作为 importance hint
                importance = float(df['pagerank_score'].mean()) if 'pagerank_score' in df.columns else 0.5
                ttl = self._tier_ttl(cache_key, date_hint, importance=min(importance * 200, 1.0))
                self._set_to_cache(cache_key, df.to_dict('records'), ttl=ttl)
                return df
            if start_date and end_date and start_date == end_date:
                return pd.DataFrame()

        target_file = None

        # ✅ 修改：如果指定了日期，只寻找精确匹配的文件
        if start_date and end_date and start_date == end_date:
            date_str = start_date.split(' ')[0] if ' ' in start_date else start_date
            target_file = USER_CHARACTERS_DATA_DIR / f"user_stats_{date_str}.csv"

            if not target_file.exists():
                print(f"[INFO] 未找到 {date_str} 的用户画像文件，将返回空数据")
                return pd.DataFrame()  # ✅ 找不到就直接返回空，不回退
        else:
            # 全量模式：加载最新的统计文件
            all_files = sorted(USER_CHARACTERS_DATA_DIR.glob('user_stats_*.csv'), reverse=True)
            if not all_files:
                return pd.DataFrame()
            target_file = all_files[0]

        if not target_file or not target_file.exists():
            return pd.DataFrame()

        df = pd.read_csv(target_file, encoding='utf-8-sig')
        print(f"[DEBUG] 加载用户画像: {target_file.name}")

        if 'user_id' in df.columns:
            df['user_id'] = df['user_id'].astype(str).str.strip()
            df['user_id'] = df['user_id'].apply(lambda x: x[:-2] if x.endswith('.0') else x)

        df = self._enrich_user_nicknames(df)
        date_hint = str(start_date) if start_date else None
        importance = float(df['pagerank_score'].mean()) if 'pagerank_score' in df.columns else 0.5
        ttl = self._tier_ttl(cache_key, date_hint, importance=min(importance * 200, 1.0))
        self._set_to_cache(cache_key, df.to_dict('records'), ttl=ttl)
        return df

    def _enrich_user_nicknames(self, df: pd.DataFrame) -> pd.DataFrame:
        """从帖子/评论数据补全用户昵称"""
        if df.empty or 'user_id' not in df.columns:
            return df

        all_nicknames = []
        base_path = Path(__file__).parents[2]

        def clean_uid(df_in):
            if 'user_id' not in df_in.columns:
                return df_in
            df_in['user_id'] = df_in['user_id'].astype(str).str.strip()
            df_in['user_id'] = df_in['user_id'].apply(lambda x: x[:-2] if x.endswith('.0') else x)
            return df_in

        if self._database_enabled():
            posts_df = self._posts_df_from_db()
            if not posts_df.empty and 'nickname' in posts_df.columns:
                all_nicknames.append(clean_uid(posts_df[['user_id', 'nickname']]))
        else:
            merged_files = sorted(base_path.glob('words/cleaned_data/posts_cleaned_merged_*.csv'))
            for f in merged_files:
                try:
                    df_n = pd.read_csv(f, encoding='utf-8-sig', usecols=['user_id', 'nickname'])
                    all_nicknames.append(clean_uid(df_n))
                except Exception:
                    pass

            comment_files = sorted(base_path.glob('words/cleaned_data/comments_cleaned_*.csv'))
            for f in comment_files:
                try:
                    df_n = pd.read_csv(f, encoding='utf-8-sig')
                    if 'user_id' in df_n.columns and 'nickname' in df_n.columns:
                        all_nicknames.append(clean_uid(df_n[['user_id', 'nickname']]))
                except Exception:
                    pass

        if all_nicknames:
            df_all_nicks = pd.concat(all_nicknames, ignore_index=True)
            df_all_nicks = df_all_nicks.dropna(subset=['nickname'])
            df_all_nicks = df_all_nicks[df_all_nicks['nickname'].str.len() > 0]
            nickname_map_df = df_all_nicks.drop_duplicates(subset=['user_id'], keep='last')
            df = pd.merge(df, nickname_map_df, on='user_id', how='left', suffixes=('', '_map'))
            if 'nickname_map' in df.columns:
                df['nickname'] = df['nickname'].fillna(df['nickname_map'])
                df = df.drop(columns=['nickname_map'])
        return df

    def load_bertopic_results(self):
        """加载 BERTopic 主题结果"""
        cache_key = self._generate_cache_key("bertopic")

        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        from config.config import DynamicFileManager
        latest_file = DynamicFileManager.get_latest_bertopic_topics()
        if latest_file and latest_file.exists():
            df = pd.read_csv(latest_file, encoding='utf-8-sig')
            result = df if not df.empty else pd.DataFrame()
            self._set_to_cache(cache_key, result.to_dict('records'))
            return result
        return pd.DataFrame()

    def invalidate_all_cache(self):
        """清除所有缓存（数据更新时调用）"""
        self._invalidate_cache_pattern("*")
        print("[INFO] 所有缓存已清除")
