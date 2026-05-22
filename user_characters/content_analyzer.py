import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List


class ContentAnalyzer:
    """内容语义分析器"""

    def __init__(self, max_features: int = 1000):
        """
        初始化分析器
        :param max_features: TF-IDF 最大特征数
        """
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=max_features,
            stop_words=None
        )

    def calculate_originality(self, texts: List[str]) -> np.ndarray:
        """
        计算原创度（基于 TF-IDF 余弦相似度）
        :param texts: 文本列表
        :return: 原创度分数数组（0-1，越高越原创）
        """
        if len(texts) < 2:
            return np.ones(len(texts)) * 0.5

        try:
            # 过滤空文本
            valid_texts = [t for t in texts if t and len(t.strip()) > 0]
            if len(valid_texts) < 2:
                return np.ones(len(texts)) * 0.5

            tfidf_matrix = self.tfidf_vectorizer.fit_transform(valid_texts)
            mean_vector = tfidf_matrix.mean(axis=0).A1
            similarities = cosine_similarity(tfidf_matrix, mean_vector.reshape(1, -1)).flatten()

            # 映射回原始长度
            result = np.ones(len(texts)) * 0.5
            valid_idx = [i for i, t in enumerate(texts) if t and len(t.strip()) > 0]
            for i, idx in enumerate(valid_idx):
                result[idx] = 1 - similarities[i]

            return result
        except Exception as e:
            print(f"   ⚠️ TF-IDF 计算失败：{e}")
            import traceback
            traceback.print_exc()
            return np.ones(len(texts)) * 0.5

    def calculate_sentiment_intensity(self, liked_counts: np.ndarray) -> np.ndarray:
        """
        计算情感强度（基于点赞数的离散度）
        :param liked_counts: 点赞数数组
        :return: 情感强度数组（0-1，越高越极端）
        """
        if len(liked_counts) == 0:
            return np.array([0.0])

        mean_likes = np.mean(liked_counts)
        std_likes = np.std(liked_counts) + 1e-6
        z_scores = np.abs((liked_counts - mean_likes) / std_likes)
        return np.clip(z_scores, 0, 1)

    def analyze(self, df_posts: pd.DataFrame, df_comments: pd.DataFrame = None) -> pd.DataFrame:
        """
        执行完整内容分析
        :param df_posts: 过滤后的帖子数据
        :param df_comments: 过滤后的评论数据（可选）
        :return: 包含内容特征的 DataFrame
        """
        print("📝 [9/9] 计算内容语义特征...")

        # 构建带用户ID的内容列表
        post_contents = df_posts['content'].fillna('').tolist()
        post_user_ids = df_posts['user_id'].astype(str).values

        all_contents = post_contents.copy()
        all_user_ids = post_user_ids.tolist()

        if df_comments is not None and not df_comments.empty and 'comment_content' in df_comments.columns:
            comment_contents = df_comments['comment_content'].fillna('').tolist()
            comment_user_ids = df_comments['user_id'].astype(str).values

            all_contents.extend(comment_contents)
            all_user_ids.extend(comment_user_ids.tolist())

        if len(all_contents) < 2:
            print("   ⚠️ 内容太少，跳过原创度计算")
            user_ids = set(df_posts['user_id'].astype(str).unique())
            if df_comments is not None:
                user_ids |= set(df_comments['user_id'].astype(str).unique())
            return pd.DataFrame({
                'user_id': list(user_ids),
                'originality_score': 1.0,
                'sentiment_intensity': 0.0
            })

        # 计算原创度（保持与 all_contents 一一对应）
        originality_scores = self.calculate_originality(all_contents)

        # 计算情感强度（帖子 + 评论）
        liked_counts = df_posts['liked_count'].fillna(0).values

        if df_comments is not None and 'comment_like_count' in df_comments.columns:
            comment_likes = df_comments['comment_like_count'].fillna(0).values
            all_likes = np.concatenate([liked_counts, comment_likes])
            sentiment_intensity = self.calculate_sentiment_intensity(all_likes)
        else:
            sentiment_intensity = self.calculate_sentiment_intensity(liked_counts)

        # 构建结果 DataFrame（基于用户ID而非位置切片）
        content_df = pd.DataFrame({
            'user_id': all_user_ids,
            'originality_score': originality_scores,
            'sentiment_intensity': np.concatenate([
                sentiment_intensity[:len(df_posts)],
                sentiment_intensity[len(df_posts):] if len(sentiment_intensity) > len(df_posts)
                else [0.5] * (len(all_contents) - len(df_posts))
            ])[:len(all_contents)]
        })

        # 按用户聚合
        content_df = content_df.groupby('user_id').agg({
            'originality_score': 'mean',
            'sentiment_intensity': 'mean'
        }).reset_index()

        print(
            f"   ✅ 原创度范围：[{content_df['originality_score'].min():.3f}, {content_df['originality_score'].max():.3f}]")
        print(
            f"   ✅ 情感强度范围：[{content_df['sentiment_intensity'].min():.3f}, {content_df['sentiment_intensity'].max():.3f}]")

        return content_df