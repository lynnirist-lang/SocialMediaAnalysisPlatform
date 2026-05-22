import sys

import pandas as pd
import os
import numpy as np
from typing import Optional, Dict
from datetime import timedelta
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


from config.config import GeneratedFiles, DynamicFileManager
from user_characters.user_feature_extractor import UserFeatureExtractor
from user_characters.network_analyzer import NetworkAnalyzer
from user_characters.content_analyzer import ContentAnalyzer


class AdvancedUserFeatureExtractor(UserFeatureExtractor):
    """
    高级用户特征提取器 - 多维动态特征体系
    继承自 UserFeatureExtractor，扩展网络和内容的分析能力
    """

    def __init__(self, config: Dict[str, str]):
        super().__init__(config)

        # 新增参数
        self.decay_rate = 0.1  # 时间衰减率 λ

        # 初始化分析器
        self.network_analyzer = NetworkAnalyzer()
        self.content_analyzer = ContentAnalyzer(max_features=1000)

    def calculate_behavioral_features(self) -> pd.DataFrame:
        """
        计算动态行为特征
        :return: 包含行为特征的 DataFrame
        """
        print("⚡ [8/9] 计算动态行为特征...")

        # 合并发帖和评论
        p_act = self.df_posts_filt[['user_id', 'create_time_dt', 'liked_count']].copy()
        p_act['action_type'] = 'post'
        c_act = self.df_comments_filt[['user_id', 'create_time_dt', 'comment_like_count']].copy()
        c_act.rename(columns={'comment_like_count': 'liked_count'}, inplace=True)
        c_act['action_type'] = 'reply'

        df_all = pd.concat([p_act, c_act], ignore_index=True)
        df_all['user_id'] = df_all['user_id'].astype(str)
        df_all['hours_since_start'] = (df_all['create_time_dt'] - self.event_start).dt.total_seconds() / 3600

        # 爆发力指数（向量化计算时间衰减权重）
        df_all['decay_weight'] = np.exp(-self.decay_rate * df_all['hours_since_start'])
        df_all['weighted_interaction'] = df_all['liked_count'] * df_all['decay_weight']

        burst_df = df_all.groupby('user_id')['weighted_interaction'].sum().reset_index()
        burst_df.columns = ['user_id', 'burst_power']

        # 响应速度（向量化取最小值）
        first_action = df_all.groupby('user_id')['hours_since_start'].min().reset_index()
        first_action.columns = ['user_id', 'response_speed']

        # 持续活跃窗口（向量化计算最大值-最小值）
        active_span = df_all.groupby('user_id')['hours_since_start'].agg(['max', 'min']).reset_index()
        active_span['active_duration'] = active_span['max'] - active_span['min']
        active_span = active_span[['user_id', 'active_duration']]

        behavioral_df = burst_df.merge(first_action, on='user_id').merge(active_span, on='user_id')

        print(
            f"   ✅ 爆发力指数范围：[{behavioral_df['burst_power'].min():.2f}, {behavioral_df['burst_power'].max():.2f}]")
        print(
            f"   ✅ 响应速度范围：[{behavioral_df['response_speed'].min():.2f}, {behavioral_df['response_speed'].max():.2f}] 小时")

        return behavioral_df

    def aggregate_all_features(self, network_df: pd.DataFrame,
                               behavioral_df: pd.DataFrame,
                               content_df: pd.DataFrame) -> None:
        """
        聚合所有特征
        :param network_df: 网络特征 DataFrame
        :param behavioral_df: 行为特征 DataFrame
        :param content_df: 内容特征 DataFrame
        """
        print("🔗 正在融合多维特征...")

        # 基础统计特征
        p_act = self.df_posts_filt[['user_id', 'create_time_dt']].copy()
        p_act['action_type'] = 'post'
        p_act['like_received'] = self.df_posts_filt['liked_count'].fillna(0)

        c_act = self.df_comments_filt[['user_id', 'create_time_dt']].copy()
        c_act['action_type'] = 'reply'
        c_act['like_received'] = self.df_comments_filt['comment_like_count'].fillna(0)

        df_all = pd.concat([p_act, c_act], ignore_index=True)
        df_all['user_id'] = df_all['user_id'].astype(str)

        df_stats = df_all.groupby('user_id').agg(
            post_count=('action_type', lambda x: (x == 'post').sum()),
            reply_count=('action_type', lambda x: (x == 'reply').sum()),
            total_actions=('action_type', 'count'),
            total_likes_received=('like_received', 'sum')
        ).reset_index()

        # 补充粉丝数
        df_stats['fans_count'] = df_stats['user_id'].map(self.user_profile_map)

        if hasattr(self, 'user_nickname_map') and self.user_nickname_map:
            df_stats['nickname'] = df_stats['user_id'].map(self.user_nickname_map)
            matched_nicknames = df_stats['nickname'].notna().sum()
            print(
                f"   ✅ 成功匹配昵称：{matched_nicknames}/{len(df_stats)} ({matched_nicknames / len(df_stats) * 100:.1f}%)")
        else:
            df_stats['nickname'] = None
            print(f"   ⚠️ 昵称映射表为空，昵称为空")

        # 合并所有特征
        self.result_df = (
            df_stats
            .merge(network_df, on='user_id', how='left')
            .merge(behavioral_df, on='user_id', how='left')
            .merge(content_df, on='user_id', how='left')
        )

        # 填充 NaN 值
        fill_dict = {
            'pagerank_score': 0,
            'betweenness_score': 0,
            'in_degree_weighted': 0,
            'out_degree_weighted': 0,
            'burst_power': 0,
            'response_speed': self.event_duration_hours,
            'active_duration': 0,
            'originality_score': 0.5,
            'sentiment_intensity': 0.5
        }

        for col, val in fill_dict.items():
            if col in self.result_df.columns:
                self.result_df[col] = self.result_df[col].fillna(val)

        if 'nickname' not in self.result_df.columns:
            self.result_df.insert(1, 'nickname', None)

        matched_count = self.result_df['fans_count'].notna().sum()
        total_count = len(self.result_df)
        print(f"   ✅ 成功匹配粉丝数：{matched_count}/{total_count} ({matched_count / total_count * 100:.1f}%)")
        print(f"   👥 最终独立用户数：{len(self.result_df)}")

    def run(self) -> Optional[pd.DataFrame]:
        """执行完整流程"""
        print("=" * 60)
        print("🚀 启动高级用户特征提取流程（多维动态特征体系）")
        print("=" * 60)

        try:
            if not self.load_data():
                return None

            self.build_user_profile_map()
            self.preprocess_time()

            if not self.extract_keywords():
                return None

            self.filter_topic_data()

            # === 新增：调用各模块分析器 ===
            network_df = self.network_analyzer.analyze(self.df_posts_filt, self.df_comments_filt)
            behavioral_df = self.calculate_behavioral_features()
            content_df = self.content_analyzer.analyze(self.df_posts_filt, self.df_comments_filt)

            self.aggregate_all_features(network_df, behavioral_df, content_df)
            path = self.save_results()

            print("=" * 60)
            print("✅ 流程全部完成！已生成多维动态特征体系。")
            print("=" * 60)
            return self.result_df

        except Exception as e:
            print(f"\n❌ 流程中断：{e}")
            import traceback
            traceback.print_exc()
            return None


# ================= 主程序入口 =================
if __name__ == "__main__":
    # 获取最新文件
    latest_posts = DynamicFileManager.get_latest_posts_cleaned()
    latest_comments = DynamicFileManager.get_latest_comments_cleaned()
    all_creators = DynamicFileManager.get_all_creators_files()
    latest_topics = DynamicFileManager.get_latest_bertopic_topics()

    if not all([latest_posts, latest_comments, latest_topics]):
        print("❌ 错误：找不到必要的输入文件")
        exit(1)

    CONFIG = {
        'POSTS_FILE': str(latest_posts),
        'COMMENTS_FILE': str(latest_comments),
        'USERS_FILES': all_creators,
        'TOPICS_FILE': str(latest_topics),
        'OUTPUT_FILE': str(GeneratedFiles.get_user_stats_path())
    }

    extractor = AdvancedUserFeatureExtractor(CONFIG)
    df_result = extractor.run()

    if df_result is not None and not df_result.empty:
        print(f"\n🎉 最终生成 {len(df_result)} 条用户记录。")
        print(f"💾 文件已保存至：{CONFIG['OUTPUT_FILE']}")
        print("\n📊 特征维度说明:")
        print("   - 基础特征：post_count, reply_count, fans_count")
        print("   - 网络特征：pagerank_score, betweenness_score, in/out_degree")
        print("   - 行为特征：burst_power, response_speed, active_duration")
        print("   - 内容特征：originality_score, sentiment_intensity")
    else:
        print("\n⚠️ 未生成有效数据，请检查上述日志。")
