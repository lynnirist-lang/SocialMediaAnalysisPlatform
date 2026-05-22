"""
微博数据预处理和分析主程序
整合所有功能模块并执行数据分析流程
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import (
    STOPWORDS_PATH,
    USER_DICT_PATH,
    MEDIA_CRAWLER_DATA_DIR,
    CLEANED_DATA_DIR,
    GeneratedFiles
)

from weibo_preprocessor import WeiboPreprocessor
from weibo_data_loader import WeiboDataLoader
from weibo_word_frequency import WeiboWordFrequency

# 设置中文显示
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


def run_word_frequency_analysis():
    """运行词频统计分析"""

    # 1. 初始化各个类
    preprocessor = WeiboPreprocessor(
        stopwords_file_path=str(STOPWORDS_PATH),
        user_dict_path=str(USER_DICT_PATH)
    )

    data_loader = WeiboDataLoader(data_dir=r"E:\\MyProjects\\MediaCrawler\\data\\weibo\\csv")
    word_freq = WeiboWordFrequency(preprocessor, data_loader)

    print("=" * 60)
    print("📊 词频统计开始")
    print("=" * 60)

    # 2. 统计所有帖子的词频
    print("\n📝 统计帖子词频...")
    df_posts_freq = word_freq.compute_posts_frequency(use_keywords=False)

    # 3. 统计所有评论的词频
    print("\n💬 统计评论词频...")
    df_comments_freq = word_freq.compute_comments_frequency(use_keywords=False)

    # 4. 统计创作者信息的词频
    print("\n👤 统计创作者词频...")
    df_creators_freq = word_freq.compute_creators_frequency(use_keywords=False)

    # 5. 按日期统计（可选）
    print("\n📅 统计指定日期的词频...")
    df_posts_20260302 = word_freq.compute_posts_frequency(date='2026-03-02', use_keywords=False)

    print("\n" + "=" * 60)

    # 6. 查看摘要
    print("\n📋 词频统计摘要:")
    summary = word_freq.get_summary()
    print(summary)

    # 7. 显示前10个词
    print("\n📈 帖子高频词TOP10:")
    print(df_posts_freq.head(10))

    print("\n📈 评论高频词TOP10:")
    print(df_comments_freq.head(10))

    # 8. 保存所有词频表
    print("\n💾 保存词频表...")
    word_freq.save_all_frequency_tables()

    # 9. 绘制词频图
    print("\n🎨 绘制词频图...")
    word_freq.plot_top_words('posts_all', topN=15, title='帖子高频词TOP15')
    word_freq.plot_top_words('comments_all', topN=15, title='评论高频词TOP15')

    print("\n✅ 词频统计完成！")

    return word_freq


def prepare_sentiment_analysis_data():
    """准备情感分析数据"""

    # 创建保存目录
    output_dir = str(CLEANED_DATA_DIR)
    os.makedirs(output_dir, exist_ok=True)

    # 初始化
    preprocessor = WeiboPreprocessor(
        stopwords_file_path=str(STOPWORDS_PATH),
        user_dict_path=str(USER_DICT_PATH)
    )
    data_loader = WeiboDataLoader(data_dir=str(MEDIA_CRAWLER_DATA_DIR))

    print("=" * 60)
    print("情感分析数据准备")
    print("=" * 60)

    # 1. 清洗帖子数据 - 使用带日期的文件名
    print("\n📝 清洗帖子数据...")
    df_posts_raw = data_loader.load_posts()
    df_posts_cleaned = preprocessor.process_dataframe(
        df_posts_raw,
        text_column='content',
        filter_ads=True,  # 启用广告过滤
        author_column='nickname',  # 指定作者列（用于白名单）
        deduplicate=True,  # 启用去重
        dedup_method='semantic'  # 使用语义去重
    )

    # 使用带日期的输出文件名
    posts_output_path = str(GeneratedFiles.get_posts_cleaned_path())
    df_posts_cleaned.to_csv(posts_output_path, index=False, encoding='utf-8-sig')
    print(f"✅ 帖子清洗完成：{len(df_posts_cleaned)} 条")
    print(f"   📁 保存至：{posts_output_path}")
    print(f"   包含字段：{list(df_posts_cleaned.columns)}")

    # 2. 清洗评论数据 - 使用带日期的文件名
    print("\n💬 清洗评论数据...")
    df_comments_raw = data_loader.load_comments()
    df_comments_cleaned = preprocessor.process_dataframe(df_comments_raw, text_column='content')

    comments_output_path = str(GeneratedFiles.get_comments_cleaned_path())
    df_comments_cleaned.to_csv(comments_output_path, index=False, encoding='utf-8-sig')
    print(f"✅ 评论清洗完成：{len(df_comments_cleaned)} 条")
    print(f"   📁 保存至：{comments_output_path}")
    print(f"   包含字段：{list(df_comments_cleaned.columns)}")

    # 3. 词频统计
    print("\n📊 统计词频...")
    word_freq = WeiboWordFrequency(preprocessor, data_loader)
    word_freq.compute_posts_frequency(use_keywords=False)
    word_freq.compute_comments_frequency(use_keywords=False)
    word_freq.save_all_frequency_tables()
    print("✅ 词频统计已保存")

    print("\n" + "=" * 60)
    print("✅ 情感分析数据准备完成！")
    print(f"📁 数据位置：{output_dir}")
    print("📌 下次运行请使用 DynamicFileManager 获取最新文件")
    print("=" * 60)

    # 显示数据预览
    print("\n🔍 帖子数据预览（前 2 条）:")
    print(df_posts_cleaned[['content', 'cleaned_content', 'words']].head(2))

    print("\n🔍 评论数据预览（前 2 条）:")
    print(df_comments_cleaned[['content', 'cleaned_content', 'words']].head(2))

    return df_posts_cleaned, df_comments_cleaned


if __name__ == "__main__":

    print("\n" + "=" * 60)
    print("请选择要运行的功能:")
    print("1. 词频统计分析")
    print("2. 准备情感分析数据")
    print("=" * 60)

    # 默认运行词频统计
    # run_word_frequency_analysis()

    # 如果需要情感分析数据，取消下面的注释
    prepare_sentiment_analysis_data()