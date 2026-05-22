from pathlib import Path

import pandas as pd
import os
import re
from datetime import timedelta
from typing import List, Optional, Dict, Any
from config.config import (
    POSTS_CLEANED_PATH,
    COMMENTS_CLEANED_PATH,
    CREATORS_01_PATH,
    USER_CHARACTERS_OUTPUT_PATH, GeneratedFiles, DynamicFileManager
)

class UserFeatureExtractor:
    """
    用户特征提取器：
    融合行为数据 (Posts/Comments) 与 用户画像 (Creators)，
    基于 BERTopic 关键词进行话题过滤，生成宽表特征。
    """

    def __init__(self, config: Dict[str, str]):
        """
        初始化配置
        :param config: 包含文件路径和参数的字典
        """
        self.config = config
        self.df_posts = None
        self.df_comments = None
        self.df_users_raw = None
        self.df_topics = None
        self.keywords = []
        self.result_df = None

        # 新增：用于存储粉丝数映射字典 {user_id: fans_count}
        self.user_profile_map = {}

        # 默认参数
        self.window_hours_buffer = 2

    def load_data(self) -> bool:
        """加载所有 CSV 文件"""
        print("📂 [1/7] 正在加载数据文件...")
        try:
            files = {
                'posts': self.config['POSTS_FILE'],
                'comments': self.config['COMMENTS_FILE'],
                'topics': self.config['TOPICS_FILE']
            }

            for key, path in files.items():
                if not os.path.exists(path):
                    raise FileNotFoundError(f"文件不存在：{path}")

                # 尝试不同编码
                try:
                    df = pd.read_csv(path, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    try:
                        df = pd.read_csv(path, encoding='gbk')
                    except:
                        df = pd.read_csv(path, encoding='latin-1')

                setattr(self, f'df_{key}', df)
                print(f"   ✅ 加载 {key}: {len(df)} 行")

                # 单独加载用户画像表 - 优先使用环境变量,否则使用配置
                creators_files_str = os.environ.get('CREATORS_FILES', '')

                if creators_files_str:
                    # 从环境变量读取(由scheduler传递)
                    creators_files = [Path(f.strip()) for f in creators_files_str.split(';') if f.strip()]
                    print(f"   📥 使用环境变量指定的创作者文件: {len(creators_files)} 个")
                else:
                    # 从配置文件读取(独立运行时)
                    creators_files = self.config.get('USERS_FILES', [])

                if creators_files:
                    self.df_users_raw = pd.DataFrame()

                    for creators_file in creators_files:
                        file_path = str(creators_file) if isinstance(creators_file, type(Path())) else creators_file

                        if os.path.exists(file_path):
                            try:
                                df_user = pd.read_csv(file_path, encoding='utf-8-sig')
                                self.df_users_raw = pd.concat([self.df_users_raw, df_user], ignore_index=True)
                                print(f"   ✅ 加载创作者文件：{os.path.basename(file_path)} ({len(df_user)} 行)")
                            except Exception as e:
                                print(f"   ⚠️ 加载 {file_path} 失败：{e}")

                    if len(self.df_users_raw) > 0:
                        print(f"   ✅ 合并后用户画像表总数：{len(self.df_users_raw)} 行")
                    else:
                        print("   ⚠️ 未找到任何创作者文件，粉丝数将全部为空")
                else:
                    self.df_users_raw = pd.DataFrame()
                    print("   ⚠️ 未配置创作者文件，粉丝数将全部为空")
            return True
        except Exception as e:
            print(f"❌ 数据加载失败：{e}")
            return False

    def build_user_profile_map(self):
        """
        【关键步骤】从主页爬取的数据中提取 {user_id: fans_count} 映射表
        不合并行为记录，仅提取静态属性用于后续补充
        """
        if self.df_users_raw is None or self.df_users_raw.empty:
            print("   ℹ️ 跳过粉丝映射构建 (无用户数据)")
            return

        print("🗺️ [2/7] 构建用户粉丝映射表...")
        u_cols = self.df_users_raw.columns

        # 智能识别列名
        uid_col = 'user_id' if 'user_id' in u_cols else u_cols[0]

        # 修复：精确匹配粉丝数列名（增加对 'fans' 的支持）
        fans_col = None
        for col in u_cols:
            if col.lower() in ['fans', 'fans_count', 'follower', 'followers']:
                fans_col = col
                break

        # 如果没找到，尝试第二列（通常是 nickname）
        if not fans_col:
            fans_col = u_cols[1] if len(u_cols) > 1 else u_cols[0]
            print(f"   ⚠️ 未找到标准粉丝列，使用第 2 列：{fans_col}")

        nickname_col = None
        for col in u_cols:
            if col.lower() in ['nickname', 'nick_name', 'name', 'user_name', 'username']:
                nickname_col = col
                break

        print(f"   识别到 ID 列：{uid_col}, 粉丝列：{fans_col}, 昵称列：{nickname_col}")

        # 构建包含昵称和粉丝数的临时DataFrame
        cols_to_keep = [uid_col, fans_col]
        if nickname_col:
            cols_to_keep.append(nickname_col)

        temp_df = self.df_users_raw[cols_to_keep].copy()
        temp_df = temp_df.dropna(subset=[uid_col])

        # 统一 ID 为字符串
        temp_df[uid_col] = temp_df[uid_col].astype(str)

        # 处理粉丝数：转为数值，处理带"万""亿"的单位
        def convert_fans(value):
            if pd.isna(value):
                return 0
            if isinstance(value, (int, float)):
                return float(value)

            # 字符串处理
            value_str = str(value).strip().lower()
            if not value_str:
                return 0

            # 处理带单位的情况
            multiplier = 1
            if '万' in value_str:
                multiplier = 10000
                value_str = value_str.replace('万', '')
            elif '亿' in value_str:
                multiplier = 100000000
                value_str = value_str.replace('亿', '')

            try:
                return float(value_str) * multiplier
            except ValueError:
                return 0

        temp_df[fans_col] = temp_df[fans_col].apply(convert_fans)

        # 构建字典：如果有重复 user_id (同一个人多条历史帖)，取最大粉丝数
        self.user_profile_map = temp_df.groupby(uid_col)[fans_col].max().to_dict()

        if nickname_col:
            self.user_nickname_map = temp_df.groupby(uid_col)[nickname_col].last().to_dict()
            print(f"   ✅ 昵称映射表构建完成：{len(self.user_nickname_map)} 个唯一用户")
        else:
            self.user_nickname_map = {}
            print(f"   ⚠️ 未找到昵称列，昵称为空")

        print(f"   ✅ 映射表构建完成：{len(self.user_profile_map)} 个唯一用户")
        print(
            f"   📊 粉丝数统计：min={min(self.user_profile_map.values()):.0f}, max={max(self.user_profile_map.values()):.0f}")

    def preprocess_time(self) -> None:
        """统一时间戳格式并确定 STRICT 分析窗口"""
        print("⏰ [3/7] 正在处理时间序列并锁定事件窗口...")

        # 转换时间戳
        self.df_posts['create_time_dt'] = pd.to_datetime(self.df_posts['create_time'], unit='s', errors='coerce')
        self.df_comments['create_time_dt'] = pd.to_datetime(self.df_comments['create_time'], unit='s', errors='coerce')

        # 移除转换失败的行
        self.df_posts = self.df_posts.dropna(subset=['create_time_dt'])
        self.df_comments = self.df_comments.dropna(subset=['create_time_dt'])

        if self.df_posts.empty:
            raise ValueError("帖子数据时间为空或格式错误")

        # 【核心逻辑】自动检测数据最密集的连续2天
        from collections import Counter

        # 统计每天的帖子数
        date_counts = Counter()
        for dt in self.df_posts['create_time_dt']:
            date_key = dt.strftime('%Y-%m-%d')
            date_counts[date_key] += 1

        sorted_dates = sorted(date_counts.keys())

        selected_start = None
        selected_end = None
        max_count = 0

        # 找到帖子最多的连续2天
        for i in range(len(sorted_dates) - 1):
            day1 = sorted_dates[i]
            day2 = sorted_dates[i + 1]

            # 检查是否连续
            d1 = pd.to_datetime(day1)
            d2 = pd.to_datetime(day2)
            if (d2 - d1).days == 1:
                total = date_counts[day1] + date_counts[day2]
                if total > max_count:
                    max_count = total
                    selected_start = pd.to_datetime(f'{day1} 00:00:00')
                    selected_end = pd.to_datetime(f'{day2} 23:59:59')

        if not selected_start or max_count < 10:
            print(f"   ⚠️ 警告：未找到数据密集的连续时间段。")
            print(f"   💡  fallback: 将使用数据的最小/最大时间作为窗口 (可能包含历史脏数据)")
            min_t = self.df_posts['create_time_dt'].min()
            max_t = self.df_posts['create_time_dt'].max()
            selected_start = min_t - timedelta(hours=self.window_hours_buffer)
            selected_end = max_t + timedelta(hours=self.window_hours_buffer)
        else:
            print(
                f"   🎯 自动检测到事件窗口：{selected_start.strftime('%Y-%m-%d')} 至 {selected_end.strftime('%Y-%m-%d')} (共{max_count}条帖子)")

        self.event_start = selected_start
        self.event_end = selected_end

        # === 新增：计算事件持续时间（小时）===
        self.event_duration_hours = (self.event_end - self.event_start).total_seconds() / 3600

        print(f"   ✂️ 严格事件窗口设定：{self.event_start} 至 {self.event_end} (共{self.event_duration_hours:.1f}小时)")

    def extract_keywords(self) -> bool:
        """从 BERTopic 文件中提取关键词列表"""
        print("🔑 [4/7] 正在解析 BERTopic 关键词...")

        df = self.df_topics
        target_col = None
        keywords_candidates = ['keywords', 'keyword', 'topic_keywords', 'representation', 'topic_name']

        for col in df.columns:
            if any(k in col.lower() for k in keywords_candidates):
                target_col = col
                break

        if not target_col:
            target_col = df.columns[0]
            print(f"   ⚠️ 未找到明确关键词列，默认使用第一列: {target_col}")
        else:
            print(f"   ✅ 识别到关键词列: {target_col}")

        raw_list = df[target_col].dropna().astype(str).tolist()
        cleaned_keywords = set()
        split_pattern = r'[,\;\n\t]+'

        for item in raw_list:
            parts = re.split(split_pattern, item)
            for p in parts:
                p = p.strip().strip('#').strip('"').strip("'")
                if len(p) > 1:
                    cleaned_keywords.add(p)

        self.keywords = list(cleaned_keywords)
        print(f"   🎯 提取有效关键词数量: {len(self.keywords)}")
        if len(self.keywords) > 0:
            print(f"   💡 关键词样例: {self.keywords[:5]}")

        return len(self.keywords) > 0

    def filter_topic_data(self) -> None:
        """
        【核心修改】基于 STRICT 时间窗口 + 关键词过滤数据
        先切时间，再匹配关键词，彻底杜绝历史旧帖干扰
        """
        print("🔍 [5/7] 正在执行严格过滤 (时间优先)...")

        if not self.keywords:
            raise ValueError("关键词列表为空，无法过滤")

        # 1. 【第一步】强制时间切片 (只保留 3.03-3.04 的数据)
        # 这一步直接丢弃了从“主页爬取”数据中带来的几年前旧帖
        mask_time_posts = (self.df_posts['create_time_dt'] >= self.event_start) & \
                          (self.df_posts['create_time_dt'] <= self.event_end)

        posts_event = self.df_posts[mask_time_posts].copy()

        mask_time_comments = (self.df_comments['create_time_dt'] >= self.event_start) & \
                             (self.df_comments['create_time_dt'] <= self.event_end)
        comments_event = self.df_comments[mask_time_comments].copy()

        print(f"   ⏳ 时间切片后 -> 帖子: {len(posts_event)}, 评论: {len(comments_event)}")

        if posts_event.empty and comments_event.empty:
            raise ValueError("事件窗口内无任何数据！请检查时间戳或年份。")

        # 2. 【第二步】在时间切片后的数据中进行关键词匹配
        posts_event['content_str'] = posts_event['content'].fillna('').astype(str)

        escaped_kws = [re.escape(k) for k in self.keywords]
        pattern = '|'.join(escaped_kws)

        mask_keyword = posts_event['content_str'].str.contains(pattern, case=False, na=False, regex=True)
        self.df_posts_filt = posts_event[mask_keyword].copy()

        print(f"   🔑 关键词匹配后有效帖子: {len(self.df_posts_filt)}")

        if self.df_posts_filt.empty:
            print("   ❌ 致命错误：时间窗口内没有匹配到任何关键词的帖子！")
            print("   [调试] 时间窗口内前 3 条帖子内容:")
            print(posts_event['content_str'].head(3).to_string())
            print("   [调试] 当前关键词:", self.keywords[:5])
            raise ValueError("话题过滤结果为空")

        # 3. 关联评论 (只关联那些被选中的 Note ID，且评论本身也在时间窗口内)
        target_note_ids = self.df_posts_filt['note_id'].unique()
        self.df_comments_filt = comments_event[
            comments_event['note_id'].isin(target_note_ids)
        ].copy()

        print(f"   💬 关联到的有效评论数: {len(self.df_comments_filt)}")

    def aggregate_features(self) -> None:
        """聚合用户行为特征并补充粉丝数据"""
        print("📊 [6/7] 正在聚合用户特征...")

        # 标准化发帖行为
        p_act = self.df_posts_filt[['user_id', 'create_time_dt']].copy()
        p_act['action_type'] = 'post'
        p_act['like_received'] = self.df_posts_filt['liked_count'].fillna(0)

        # 标准化评论行为
        c_act = self.df_comments_filt[['user_id', 'create_time_dt']].copy()
        c_act['action_type'] = 'reply'
        c_act['like_received'] = self.df_comments_filt['comment_like_count'].fillna(0)

        # 合并
        df_all = pd.concat([p_act, c_act], ignore_index=True)

        # 统一 user_id 类型为字符串
        df_all['user_id'] = df_all['user_id'].astype(str)

        # 定义聚合规则 - 使用命名列方式
        df_stats = df_all.groupby('user_id').agg(
            post_count=('action_type', lambda x: (x == 'post').sum()),
            reply_count=('action_type', lambda x: (x == 'reply').sum()),
            total_actions=('action_type', 'count'),
            first_action_time=('create_time_dt', 'min'),
            last_action_time=('create_time_dt', 'max'),
            total_likes_received=('like_received', 'sum')
        ).reset_index()

        print(f"   👥 独立用户数：{len(df_stats)}")

        # 【关键融合】通过 map 补充粉丝数
        print("   🔗 正在通过映射表补充粉丝数据...")
        df_stats['fans_count'] = df_stats['user_id'].map(self.user_profile_map)

        if hasattr(self, 'user_nickname_map') and self.user_nickname_map:
            df_stats['nickname'] = df_stats['user_id'].map(self.user_nickname_map)
            matched_nicknames = df_stats['nickname'].notna().sum()
            print(
                f"   ✅ 成功匹配昵称：{matched_nicknames}/{len(df_stats)} ({matched_nicknames / len(df_stats) * 100:.1f}%)")
        else:
            df_stats['nickname'] = None
            print(f"   ⚠️ 昵称映射表为空，昵称为空")

        # 统计匹配情况
        matched_count = df_stats['fans_count'].notna().sum()
        total_count = len(df_stats)
        print(f"   ✅ 成功匹配粉丝数：{matched_count}/{total_count} ({matched_count / total_count * 100:.1f}%)")
        print(f"   ℹ️ 剩余 {total_count - matched_count} 用户粉丝数为 NaN (来源：纯关键词爬取，无主页数据)")

        # 计算时间差 (小时) - 相对于事件开始时间
        df_stats['delta_t_hours'] = (
                                            df_stats['first_action_time'] - self.event_start
                                    ).dt.total_seconds() / 3600

        # 整理列顺序
        final_cols = [
            'user_id','nickname', 'fans_count',
            'post_count', 'reply_count', 'total_actions',
            'total_likes_received',
            'first_action_time', 'last_action_time', 'delta_t_hours'
        ]
        self.result_df = df_stats[final_cols]

    def save_results(self) -> str:
        """保存结果到 CSV"""
        print("💾 [7/7] 正在保存结果...")
        output_path = self.config['OUTPUT_FILE']

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # 保持原有编码 utf-8-sig
        self.result_df.to_csv(output_path, index=False, encoding='utf-8-sig')

        print(f"   ✅ 成功保存至: {output_path}")
        print("\n📈 数据概览:")
        print(self.result_df.describe())
        print("\n💡 提示：fans_count 为 NaN 表示该用户数据来源于关键词爬取，未找到对应主页粉丝信息。")

        return output_path

    def run(self) -> Optional[pd.DataFrame]:
        """执行完整流程"""
        print("=" * 50)
        print("🚀 启动用户特征提取流程 (混合数据源优化版)")
        print("=" * 50)

        try:
            if not self.load_data():
                return None

            self.build_user_profile_map()
            self.preprocess_time()

            if not self.extract_keywords():
                return None

            self.filter_topic_data()
            self.aggregate_features()
            path = self.save_results()

            print("=" * 50)
            print("✅ 流程全部完成！数据已严格限制在事件时间内。")
            print("=" * 50)
            return self.result_df

        except Exception as e:
            print(f"\n❌ 流程中断: {e}")
            import traceback
            traceback.print_exc()
            return None



# ================= 主程序入口 =================
if __name__ == "__main__":
    # 使用动态文件管理器获取最新文件
    latest_posts = DynamicFileManager.get_latest_posts_cleaned()
    latest_comments = DynamicFileManager.get_latest_comments_cleaned()
    all_creators = DynamicFileManager.get_all_creators_files()
    latest_topics = DynamicFileManager.get_latest_bertopic_topics()  # 修复：使用正确的方法名

    # 检查文件是否存在
    if not all([latest_posts, latest_comments, latest_topics]):
        print("❌ 错误：找不到必要的输入文件")
        print(f"   posts_cleaned: {latest_posts}")
        print(f"   comments_cleaned: {latest_comments}")
        print(f"   bertopic_topics: {latest_topics}")
        exit(1)

    # 配置字典 - 使用动态路径
    CONFIG = {
        'POSTS_FILE': str(latest_posts),
        'COMMENTS_FILE': str(latest_comments),
        'USERS_FILES': all_creators,  # 传入文件列表
        'TOPICS_FILE': str(latest_topics),
        'OUTPUT_FILE': str(GeneratedFiles.get_user_stats_path())  # 输出带日期的新文件
    }

    # 实例化并运行
    extractor = UserFeatureExtractor(CONFIG)
    df_result = extractor.run()

    if df_result is not None and not df_result.empty:
        print(f"\n🎉 最终生成 {len(df_result)} 条用户记录。")
        print(f"💾 文件已保存至：{CONFIG['OUTPUT_FILE']}")
    else:
        print("\n⚠️ 未生成有效数据，请检查上述日志。")