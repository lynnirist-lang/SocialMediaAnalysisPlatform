"""
项目配置中心 - 统一管理所有路径和参数
"""
from pathlib import Path
import os
from datetime import datetime, timedelta
import glob
import re

# ==================== 自动加载 .env 文件 ====================
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=False)
except ImportError:
    pass

# ==================== 项目根目录 ====================
PROJECT_ROOT = Path(__file__).parent.parent  # 指向 SocialMediaAnalysis 根目录

# ==================== 主要目录 ====================
DATA_COLLECTOR_DIR = PROJECT_ROOT / "data_collector"
WORDS_DIR = PROJECT_ROOT / "words"
USER_CHARACTERS_DIR = PROJECT_ROOT / "user_characters"

# ==================== 分析模型相关 ====================
ANALYSIS_DIR = DATA_COLLECTOR_DIR / "analysis"
BERTOPIC_MODEL_DIR = ANALYSIS_DIR / "my_local_model"

# ==================== 数据文件路径 ====================
# 清洗后的数据
CLEANED_DATA_DIR = WORDS_DIR / "cleaned_data"
POSTS_CLEANED_PATH = CLEANED_DATA_DIR / "posts_cleaned.csv"
COMMENTS_CLEANED_PATH = CLEANED_DATA_DIR / "comments_cleaned.csv"

# 情感分析数据
SENTIMENT_DATA_DIR = WORDS_DIR / "sentiment_data"
POSTS_MODEL_PATH = SENTIMENT_DATA_DIR / "posts_model.csv"
SENTIMENT_MODEL_PATH = SENTIMENT_DATA_DIR / "sentiment_model.csv"

# 作者/创作者数据
AUTHOR_DIR = WORDS_DIR / "author"
CREATORS_01_PATH = AUTHOR_DIR / "creators_01.csv"
CREATORS_02_PATH = AUTHOR_DIR / "creators_02.csv"
CREATORS_03_PATH = AUTHOR_DIR / "creators_03.csv"

# 评论用户数据文件模式
COMMENT_USERS_PATTERN = 'search_comment_users_*.csv'

# 分析结果数据
ANALYSIS_DATA_DIR = WORDS_DIR / "analysis_data"

# 用户特征结果（按日期动态生成，使用 GeneratedFiles.get_user_stats_path()）
USER_CHARACTERS_DATA_DIR = WORDS_DIR / "user_characters"

# ==================== 资源文件 ====================
STOPWORDS_PATH = WORDS_DIR / "stopwords_hit.txt"
USER_DICT_PATH = WORDS_DIR / "user_dict.txt"

# ==================== 模型相关路径 ====================
# 预训练模型

FINE_TUNED_MODEL_DIR = DATA_COLLECTOR_DIR / "fine_tuned_model_final"
FINAL_MODEL_DIR = DATA_COLLECTOR_DIR / "fine_tuned_model_final"

# 微调输出
RESULTS_FINETUNE_DIR = DATA_COLLECTOR_DIR / "results_finetune"

# ==================== 外部数据源 (MediaCrawler) ====================
MEDIA_CRAWLER_DATA_DIR = Path(
    os.getenv("MEDIA_CRAWLER_DATA_DIR", r"E:\MyProjects\MediaCrawler\data\weibo\csv")
)

# ==================== SQLite 数据库 ====================
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "social_media.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
USE_DATABASE = os.getenv("USE_DATABASE", "true").lower() in ("1", "true", "yes")
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "false").lower() in ("1", "true", "yes")

# ==================== JWT 认证 ====================
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "social-media-analysis-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7)))

# ==================== 缓存目录 ====================
CACHE_DIR = PROJECT_ROOT / "cache"
TRANSFORMERS_CACHE_DIR = CACHE_DIR / "transformers"
HF_HOME_DIR = CACHE_DIR / "huggingface"


# ==================== 环境变量配置 ====================
def setup_environment():
    """设置环境变量"""
    os.environ['TRANSFORMERS_CACHE'] = str(TRANSFORMERS_CACHE_DIR)
    os.environ['HF_HOME'] = str(HF_HOME_DIR)


# ==================== 辅助函数 ====================
def get_date_string(separator: str = '') -> str:
    """
    生成日期字符串

    Args:
        separator: 日期分隔符，默认为空字符串，可以是 '-' 或其他

    Returns:
        格式化后的日期字符串
    """
    if separator:
        return datetime.now().strftime(f"%Y{separator}%m{separator}%d")
    return datetime.now().strftime("%Y%m%d")


def find_latest_file(directory: Path, pattern: str) -> Path | None:
    """
    在目录中查找匹配模式的最新文件（按日期排序）

    Args:
        directory: 搜索目录
        pattern: 文件名模式，如 'posts_cleaned_*.csv'

    Returns:
        最新的文件路径，如果没有找到则返回 None
    """
    if not directory.exists():
        return None

    # 查找所有匹配的文件
    matches = list(directory.glob(pattern))

    if not matches:
        return None

    # 从文件名中提取日期并排序
    def extract_date(filepath: Path) -> datetime:
        match = re.search(r'(\d{8})', filepath.name)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y%m%d')
            except ValueError:
                pass
        return datetime.min

    # 按日期降序排列，返回最新的
    matches.sort(key=extract_date, reverse=True)
    return matches[0]


def find_all_dated_files(directory: Path, pattern: str) -> list[Path]:
    """
    查找目录下所有匹配模式的带日期文件

    Args:
        directory: 搜索目录
        pattern: 文件名模式，如 'creators_*.csv'

    Returns:
        文件路径列表（按日期降序）
    """
    if not directory.exists():
        return []

    matches = list(directory.glob(pattern))

    # 按日期排序
    def extract_date(filepath: Path) -> datetime:
        match = re.search(r'(\d{8})', filepath.name)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y%m%d')
            except ValueError:
                pass
        return datetime.min

    matches.sort(key=extract_date, reverse=True)
    return matches


def ensure_dirs_exist():
    """确保所有必要的目录存在"""
    dirs = [
        DATA_DIR,
        CACHE_DIR,
        TRANSFORMERS_CACHE_DIR,
        HF_HOME_DIR,
        CLEANED_DATA_DIR,
        SENTIMENT_DATA_DIR,
        ANALYSIS_DATA_DIR,
        RESULTS_FINETUNE_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def get_path(key: str) -> Path | None:
    """
    通过键名获取路径（仅返回静态路径）

    Args:
        key: 路径键名

    Returns:
        对应的 Path 对象或 None
    """
    path_map = {
        'POSTS_CLEANED': POSTS_CLEANED_PATH,
        'COMMENTS_CLEANED': COMMENTS_CLEANED_PATH,
        'STOPWORDS': STOPWORDS_PATH,
        'USER_DICT': USER_DICT_PATH,
        'BERTOPIC_MODEL': BERTOPIC_MODEL_DIR,
        'FINE_TUNED_MODEL': FINE_TUNED_MODEL_DIR,
        'FINAL_MODEL': FINAL_MODEL_DIR,
        'CREATORS_01': CREATORS_01_PATH,
    }
    return path_map.get(key)




# ==================== 快速访问字典 ====================
PATHS = {
    'posts_cleaned': POSTS_CLEANED_PATH,
    'comments_cleaned': COMMENTS_CLEANED_PATH,
    'stopwords': STOPWORDS_PATH,
    'user_dict': USER_DICT_PATH,
    'bertopic_model': BERTOPIC_MODEL_DIR,
    'fine_tuned_model': FINE_TUNED_MODEL_DIR,
    'final_model': FINAL_MODEL_DIR,
    'creators_01': CREATORS_01_PATH,
    'creators_02': CREATORS_02_PATH,
    'creators_03': CREATORS_03_PATH,
    'media_crawler_data': MEDIA_CRAWLER_DATA_DIR,
}


# ==================== 生成文件路径 (带日期) ====================
class GeneratedFiles:
    """动态生成文件路径类 - 所有运行时生成的输出文件都使用此类"""

    @staticmethod
    def get_user_stats_path(separator: str = '-') -> Path:
        """
        用户统计文件输出

        Args:
            separator: 日期分隔符，默认 '-'

        Returns:
            文件路径
        """
        date_str = get_date_string(separator)
        return USER_CHARACTERS_DATA_DIR / f"user_stats_{date_str}.csv"


    @staticmethod
    def get_bertopic_topics_path() -> Path:
        """BERTopic 主题分析输出：bertopic_topics_YYYYMMDD.csv"""
        date_str = get_date_string()
        return ANALYSIS_DATA_DIR / f"bertopic_topics_{date_str}.csv"

    @staticmethod
    def get_posts_cleaned_path() -> Path:
        """清洗后帖子数据输出：posts_cleaned_YYYYMMDD.csv"""
        date_str = get_date_string()
        return CLEANED_DATA_DIR / f"posts_cleaned_{date_str}.csv"

    @staticmethod
    def get_comments_cleaned_path() -> Path:
        """清洗后评论数据输出：comments_cleaned_YYYYMMDD.csv"""
        date_str = get_date_string()
        return CLEANED_DATA_DIR / f"comments_cleaned_{date_str}.csv"

    @staticmethod
    def get_sentiment_analysis_path() -> Path:
        """情感分析结果输出：sentiment_analysis_YYYYMMDD.csv"""
        date_str = get_date_string()
        return SENTIMENT_DATA_DIR / f"sentiment_analysis_{date_str}.csv"

    @staticmethod
    def get_all_output_paths() -> dict:
        """获取所有输出文件的路径字典"""
        return {
            'user_stats': GeneratedFiles.get_user_stats_path(),
            'bertopic_topics': GeneratedFiles.get_bertopic_topics_path(),
            'posts_cleaned': GeneratedFiles.get_posts_cleaned_path(),
            'comments_cleaned': GeneratedFiles.get_comments_cleaned_path(),
            'sentiment_analysis': GeneratedFiles.get_sentiment_analysis_path(),
        }


# ==================== 动态文件管理器 ====================
class DynamicFileManager:
    """
    动态文件管理器 - 自动发现和管理带日期的文件

    使用示例：
    # 获取最新的清洗后帖子文件
    latest_posts = DynamicFileManager.get_latest_posts_cleaned()

    # 获取所有创作者文件
    all_creators = DynamicFileManager.get_all_creators_files()

    # 获取最近的评论文件（最近 7 天）
    recent_comments = DynamicFileManager.get_recent_comments_cleaned(days=7)
    """

    @staticmethod
    def get_latest_posts_cleaned() -> Path | None:
        """获取最新的清洗后帖子文件"""
        # 先查找带日期的文件，如果没有则返回固定名称的文件
        dated_file = find_latest_file(CLEANED_DATA_DIR, 'posts_cleaned_*.csv')
        if dated_file:
            return dated_file

        # 回退到固定名称
        fixed_file = CLEANED_DATA_DIR / 'posts_cleaned.csv'
        return fixed_file if fixed_file.exists() else None

    @staticmethod
    def get_latest_comments_cleaned() -> Path | None:
        """获取最新的清洗后评论文件"""
        # 先查找带日期的文件，如果没有则返回固定名称的文件
        dated_file = find_latest_file(CLEANED_DATA_DIR, 'comments_cleaned_*.csv')
        if dated_file:
            return dated_file

        # 回退到固定名称
        fixed_file = CLEANED_DATA_DIR / 'comments_cleaned.csv'
        return fixed_file if fixed_file.exists() else None

    @staticmethod
    def get_latest_bertopic_topics() -> Path | None:
        """获取最新的 BERTopic 主题分析文件"""
        # 先查找带日期的文件
        dated_file = find_latest_file(ANALYSIS_DATA_DIR, 'bertopic_topics_*.csv')
        if dated_file:
            return dated_file

        # 回退到固定名称
        fixed_file = ANALYSIS_DATA_DIR / 'bertopic_topics_fixed.csv'
        return fixed_file if fixed_file.exists() else None

    @staticmethod
    def get_latest_sentiment_data() -> Path | None:
        """获取最新的情感标注数据文件"""
        dated_file = find_latest_file(SENTIMENT_DATA_DIR, 'posts_model_*.csv')
        if dated_file:
            return dated_file
        fixed_file = SENTIMENT_DATA_DIR / 'posts_model.csv'
        return fixed_file if fixed_file.exists() else None

    @staticmethod
    def merge_sentiment_to_posts() -> Path | None:
        """
        合并情感数据和 Topic 到清洗后的数据
        生成格式：posts_cleaned_merged_YYYYMMDD.csv
        """
        try:
            import pandas as pd

            # 获取最新文件
            posts_file = DynamicFileManager.get_latest_posts_cleaned()
            sentiment_file = DynamicFileManager.get_latest_sentiment_data()
            bertopic_file = DynamicFileManager.get_latest_bertopic_topics()

            if not posts_file:
                return None

            # 提取日期
            match = re.search(r'(\d{8})', posts_file.name)
            date_str = match.group(1) if match else get_date_string()

            # 读取帖子数据
            df_posts = pd.read_csv(posts_file, encoding='utf-8-sig')

            # 1. 合并情感数据
            sentiment_file_path = SENTIMENT_DATA_DIR / f"posts_model_{date_str}.csv"
            if sentiment_file_path.exists():
                try:
                    df_sentiment = pd.read_csv(sentiment_file_path, encoding='utf-8-sig')
                    label_map = {0: '积极', 1: '消极', 2: '中性'}
                    df_sentiment['sentiment'] = df_sentiment['label'].map(label_map)

                    if 'note_id' in df_sentiment.columns and 'note_id' in df_posts.columns:
                        df_posts = df_posts.merge(
                            df_sentiment[['note_id', 'sentiment', '置信度']],
                            on='note_id',
                            how='left'
                        )
                    elif 'text' in df_sentiment.columns and 'cleaned_content' in df_posts.columns:
                        df_posts = df_posts.merge(
                            df_sentiment[['text', 'sentiment', '置信度']],
                            left_on='cleaned_content',
                            right_on='text',
                            how='left'
                        )
                        df_posts.drop(columns=['text'], inplace=True, errors='ignore')
                except Exception as e:
                    print(f"[WARNING] {date_str} 情感合并失败: {e}")

            # 2. 合并 Topic 数据
            if bertopic_file and bertopic_file.exists():
                try:
                    df_topics = pd.read_csv(bertopic_file, encoding='utf-8-sig')
                    if 'note_id' in df_topics.columns and 'Topic' in df_topics.columns:
                        topic_map = dict(zip(df_topics['note_id'], df_topics['Topic']))
                        df_posts['Topic'] = df_posts['note_id'].map(topic_map).fillna(-1).astype(int)
                        print(f"[DEBUG] Topic 映射成功，未分类: {(df_posts['Topic'] == -1).sum()}")
                    elif 'Topic' in df_posts.columns:
                        print("[DEBUG] 帖子文件已包含 Topic 列")
                    else:
                        df_posts['Topic'] = -1
                        print("[WARNING] BERTopic 结果缺少 note_id，所有帖子标记为未分类")
                except Exception as e:
                    print(f"[WARNING] 合并 Topic 数据失败: {e}")
                    if 'Topic' not in df_posts.columns:
                        df_posts['Topic'] = -1
            else:
                if 'Topic' not in df_posts.columns:
                    df_posts['Topic'] = -1
                    print("[WARNING] 无 BERTopic 结果，所有帖子标记为未分类")

            # 3. 生成带日期的合并文件
            output_file = CLEANED_DATA_DIR / f'posts_cleaned_merged_{date_str}.csv'
            df_posts.to_csv(output_file, index=False, encoding='utf-8-sig')
            print(f"✅ 已生成合并文件: {output_file}")
            print(f"   总记录数: {len(df_posts)}")
            print(f"   含情感: {df_posts['sentiment'].notna().sum()}")
            print(f"   含Topic: {(df_posts['Topic'] != -1).sum()}")

            return output_file

        except Exception as e:
            print(f"[ERROR] 生成合并文件失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def merge_all_posts_with_sentiment_and_topic() -> list[Path]:
        """
        合并所有日期帖子文件的情感和 Topic 数据
        生成格式：posts_cleaned_merged_YYYYMMDD.csv
        """
        try:
            import pandas as pd

            # 获取所有带日期的帖子文件
            all_posts_files = find_all_dated_files(CLEANED_DATA_DIR, 'posts_cleaned_*.csv')

            if not all_posts_files:
                print("[WARNING] 未找到任何帖子文件")
                return []

            generated_files = []

            for posts_file in all_posts_files:
                try:
                    # 提取日期
                    match = re.search(r'(\d{8})', posts_file.name)
                    if not match:
                        continue
                    date_str = match.group(1)

                    # 读取帖子数据
                    df_posts = pd.read_csv(posts_file, encoding='utf-8-sig')

                    # 1. 合并情感数据
                    sentiment_file = SENTIMENT_DATA_DIR / f"posts_model_{date_str}.csv"
                    if sentiment_file.exists():
                        try:
                            df_sentiment = pd.read_csv(sentiment_file, encoding='utf-8-sig')
                            label_map = {0: '积极', 1: '消极', 2: '中性'}
                            df_sentiment['sentiment'] = df_sentiment['label'].map(label_map)

                            if 'note_id' in df_sentiment.columns and 'note_id' in df_posts.columns:
                                df_posts = df_posts.merge(
                                    df_sentiment[['note_id', 'sentiment', '置信度']],
                                    on='note_id',
                                    how='left'
                                )
                            elif 'text' in df_sentiment.columns and 'cleaned_content' in df_posts.columns:
                                df_posts = df_posts.merge(
                                    df_sentiment[['text', 'sentiment', '置信度']],
                                    left_on='cleaned_content',
                                    right_on='text',
                                    how='left'
                                )
                                df_posts.drop(columns=['text'], inplace=True, errors='ignore')
                        except Exception as e:
                            print(f"[WARNING] {date_str} 情感合并失败: {e}")

                    # 2. 合并 Topic 数据（从 BERTopic 结果映射）
                    bertopic_file = DynamicFileManager.get_latest_bertopic_topics()
                    if bertopic_file and bertopic_file.exists():
                        try:
                            df_topics = pd.read_csv(bertopic_file, encoding='utf-8-sig')
                            if 'note_id' in df_topics.columns and 'Topic' in df_topics.columns:
                                topic_map = dict(zip(df_topics['note_id'], df_topics['Topic']))
                                df_posts['Topic'] = df_posts['note_id'].map(topic_map).fillna(-1).astype(int)
                            elif 'Topic' not in df_posts.columns:
                                df_posts['Topic'] = -1
                        except Exception as e:
                            print(f"[WARNING] {date_str} Topic 合并失败: {e}")
                            if 'Topic' not in df_posts.columns:
                                df_posts['Topic'] = -1
                    else:
                        if 'Topic' not in df_posts.columns:
                            df_posts['Topic'] = -1

                    # 3. 生成合并文件
                    output_file = CLEANED_DATA_DIR / f'posts_cleaned_merged_{date_str}.csv'
                    df_posts.to_csv(output_file, index=False, encoding='utf-8-sig')
                    generated_files.append(output_file)

                    print(f"✅ {date_str}: {len(df_posts)} 条, "
                          f"情感:{df_posts['sentiment'].notna().sum()}, "
                          f"Topic:{(df_posts['Topic'] != -1).sum()}")

                except Exception as e:
                    print(f"[ERROR] 处理 {posts_file.name} 失败: {e}")
                    continue

            print(f"\n✅ 共生成 {len(generated_files)} 个合并文件")
            return generated_files

        except Exception as e:
            print(f"[ERROR] 批量合并失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    def get_all_creators_files() -> list[Path]:
        """获取所有创作者文件（包括帖子用户和评论用户，按日期降序）"""
        # 获取帖子用户主页文件
        post_creators = find_all_dated_files(AUTHOR_DIR, 'creators_*.csv')

        # 获取评论用户主页文件
        comment_users = find_all_dated_files(AUTHOR_DIR, 'search_comment_users_*.csv')

        # 合并两类文件
        all_files = post_creators + comment_users
        print(f"   📂 找到 {len(post_creators)} 个帖子用户文件, {len(comment_users)} 个评论用户文件")

        return all_files
    @staticmethod
    def get_all_user_stats_files() -> list[Path]:
        """获取所有用户统计文件（按日期降序）"""
        return find_all_dated_files(USER_CHARACTERS_DATA_DIR, 'user_stats_*.csv')

    @staticmethod
    def get_all_bertopic_topics_files() -> list[Path]:
        """获取所有 BERTopic 主题分析文件（按日期降序）"""
        return find_all_dated_files(ANALYSIS_DATA_DIR, 'bertopic_topics_*.csv')

    @staticmethod
    def get_recent_posts_cleaned(days: int = 7) -> list[Path]:
        """
        获取最近 N 天的帖子文件

        Args:
            days: 天数，默认 7 天

        Returns:
            文件路径列表
        """
        cutoff_date = datetime.now() - timedelta(days=days)  # 修复 1: timedelta 计算错误
        files = find_all_dated_files(CLEANED_DATA_DIR, 'posts_cleaned_*.csv')  # 修复 2: 应该查找 posts 文件

        result = []
        for f in files:
            match = re.search(r'(\d{8})', f.name)
            if match:
                try:
                    file_date = datetime.strptime(match.group(1), '%Y%m%d')
                    if file_date >= cutoff_date:
                        result.append(f)
                except ValueError:
                    pass

        return result

    @staticmethod
    def get_all_output_files_summary() -> dict:
        """
        获取所有输出文件的摘要信息

        Returns:
            字典，包含每个类型文件的数量和最新文件路径
        """
        return {
            'posts_cleaned': {
                'count': len(find_all_dated_files(CLEANED_DATA_DIR, 'posts_cleaned_*.csv')),
                'latest': find_latest_file(CLEANED_DATA_DIR, 'posts_cleaned_*.csv')
            },
            'comments_cleaned': {
                'count': len(find_all_dated_files(CLEANED_DATA_DIR, 'comments_cleaned_*.csv')),
                'latest': find_latest_file(CLEANED_DATA_DIR, 'comments_cleaned_*.csv')
            },
            'creators': {
                'count': len(find_all_dated_files(AUTHOR_DIR, 'creators_*.csv')),
                'latest': find_latest_file(AUTHOR_DIR, 'creators_*.csv')
            },
            'user_stats': {
                'count': len(find_all_dated_files(USER_CHARACTERS_DATA_DIR, 'user_stats_*.csv')),
                'latest': find_latest_file(USER_CHARACTERS_DATA_DIR, 'user_stats_*.csv')
            },
            'bertopic_topics': {
                'count': len(find_all_dated_files(ANALYSIS_DATA_DIR, 'bertopic_topics_*.csv')),
                'latest': find_latest_file(ANALYSIS_DATA_DIR, 'bertopic_topics_*.csv')
            }
        }


# ==================== 快速访问字典（静态文件） ====================
STATIC_PATHS = {
    'stopwords': STOPWORDS_PATH,
    'user_dict': USER_DICT_PATH,
    'bertopic_model': BERTOPIC_MODEL_DIR,
    'fine_tuned_model': FINE_TUNED_MODEL_DIR,
    'final_model': FINAL_MODEL_DIR,
    'media_crawler_data': MEDIA_CRAWLER_DATA_DIR,
}