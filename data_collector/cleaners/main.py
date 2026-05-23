"""
微博数据预处理主程序
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import (
    STOPWORDS_PATH,
    USER_DICT_PATH,
    MEDIA_CRAWLER_DATA_DIR,
    CLEANED_DATA_DIR,
    GeneratedFiles
)

from data_collector.cleaners.weibo_preprocessor import WeiboPreprocessor
from data_collector.cleaners.weibo_data_loader import WeiboDataLoader

import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


def prepare_sentiment_analysis_data():
    """清洗帖子和评论数据，输出带日期的 CSV"""
    output_dir = str(CLEANED_DATA_DIR)
    os.makedirs(output_dir, exist_ok=True)

    preprocessor = WeiboPreprocessor(
        stopwords_file_path=str(STOPWORDS_PATH),
        user_dict_path=str(USER_DICT_PATH)
    )
    data_loader = WeiboDataLoader(data_dir=str(MEDIA_CRAWLER_DATA_DIR))

    print("=" * 60)
    print("情感分析数据准备")
    print("=" * 60)

    print("\n清洗帖子数据...")
    df_posts_raw = data_loader.load_posts()
    df_posts_cleaned = preprocessor.process_dataframe(
        df_posts_raw,
        text_column='content',
        filter_ads=True,
        author_column='nickname',
        deduplicate=True,
        dedup_method='semantic'
    )
    posts_output_path = str(GeneratedFiles.get_posts_cleaned_path())
    df_posts_cleaned.to_csv(posts_output_path, index=False, encoding='utf-8-sig')
    print(f"帖子清洗完成：{len(df_posts_cleaned)} 条 -> {posts_output_path}")

    print("\n清洗评论数据...")
    df_comments_raw = data_loader.load_comments()
    df_comments_cleaned = preprocessor.process_dataframe(df_comments_raw, text_column='content')
    comments_output_path = str(GeneratedFiles.get_comments_cleaned_path())
    df_comments_cleaned.to_csv(comments_output_path, index=False, encoding='utf-8-sig')
    print(f"评论清洗完成：{len(df_comments_cleaned)} 条 -> {comments_output_path}")

    print("\n" + "=" * 60)
    print("完成！")
    print("=" * 60)
    return df_posts_cleaned, df_comments_cleaned


if __name__ == "__main__":
    prepare_sentiment_analysis_data()
