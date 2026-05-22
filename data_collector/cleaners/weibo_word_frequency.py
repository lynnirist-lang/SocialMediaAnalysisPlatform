"""
微博词频统计器
提供词频统计、保存、可视化等功能
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
from typing import Optional, List
from data_collector.cleaners.weibo_preprocessor import WeiboPreprocessor
from data_collector.cleaners.weibo_data_loader import WeiboDataLoader

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


class WeiboWordFrequency:
    """微博词频统计类"""

    def __init__(self, preprocessor: WeiboPreprocessor, data_loader: WeiboDataLoader):
        """
        初始化词频统计器

        Args:
            preprocessor: 预处理器实例
            data_loader: 数据加载器实例
        """
        self.preprocessor = preprocessor
        self.data_loader = data_loader
        self.freq_results = {}  # 存储词频结果

    def compute_frequency(self,
                          texts: pd.Series,
                          name: str = 'default',
                          use_keywords: bool = False,
                          topN: int = 100) -> pd.DataFrame:
        """
        计算文本的词频

        Args:
            texts: 文本Series
            name: 数据集名称（用于标识）
            use_keywords: 是否使用关键词提取模式
            topN: 保留前N个词

        Returns:
            词频DataFrame
        """
        all_words = []

        print(f"📊 正在统计 {name} 的词频...")

        for text in texts:
            if pd.isna(text) or not isinstance(text, str):
                continue

            # 清洗文本
            cleaned = self.preprocessor.clean_text(text)

            # 分词
            words = self.preprocessor.segment(cleaned, use_keywords=use_keywords)

            all_words.extend(words)

        # 统计词频
        word_counter = Counter(all_words)

        # 将频次元组转成DataFrame
        df_freq = pd.DataFrame(word_counter.most_common(topN),
                               columns=['word', 'frequency'])

        # 添加占比列
        total_words = sum(word_counter.values())
        df_freq['percentage'] = (df_freq['frequency'] / total_words * 100).round(4)

        # 保存结果
        self.freq_results[name] = {
            'df': df_freq,
            'counter': word_counter,
            'total_words': total_words,
            'unique_words': len(word_counter)
        }

        print(f"✅ {name} 词频统计完成")
        print(f"   总词数: {total_words}")
        print(f"   唯一词数: {len(word_counter)}")

        return df_freq

    def compute_from_dataframe(self,
                               df: pd.DataFrame,
                               text_column: str = 'content',
                               name: str = 'dataset',
                               use_keywords: bool = False,
                               topN: int = 100) -> pd.DataFrame:
        """
        从DataFrame中计算词频

        Args:
            df: 数据DataFrame
            text_column: 文本列名
            name: 数据集名称
            use_keywords: 是否使用关键词提取
            topN: 保留前N个词

        Returns:
            词频DataFrame
        """
        if text_column not in df.columns:
            print(f"❌ 列 {text_column} 不存在")
            return pd.DataFrame()

        return self.compute_frequency(
            texts=df[text_column],
            name=name,
            use_keywords=use_keywords,
            topN=topN
        )

    def compute_posts_frequency(self,
                                date: Optional[str] = None,
                                source: str = 'all',
                                use_keywords: bool = False,
                                topN: int = 100) -> pd.DataFrame:
        """
        计算帖子词频

        Args:
            date: 指定日期
            source: 'search' 或 'creator' 或 'all'
            use_keywords: 是否使用关键词提取
            topN: 保留前N个词

        Returns:
            词频DataFrame
        """
        # 加载帖子数据
        if date:
            df = self.data_loader.load_posts(date=date)
            name = f"posts_{date}"
        else:
            df = self.data_loader.load_posts()
            name = "posts_all"

        if df.empty:
            print("❌ 没有加载到帖子数据")
            return pd.DataFrame()

        # 如果指定了source，进行过滤
        if source != 'all' and 'data_type' in df.columns:
            if source == 'search':
                df = df[df['data_type'] == 'search_post']
                name += "_search"
            elif source == 'creator':
                df = df[df['data_type'] == 'creator_post']
                name += "_creator"

        return self.compute_from_dataframe(
            df=df,
            text_column='content',
            name=name,
            use_keywords=use_keywords,
            topN=topN
        )

    def compute_comments_frequency(self,
                                   date: Optional[str] = None,
                                   use_keywords: bool = False,
                                   topN: int = 100) -> pd.DataFrame:
        """
        计算评论词频

        Args:
            date: 指定日期
            use_keywords: 是否使用关键词提取
            topN: 保留前N个词

        Returns:
            词频DataFrame
        """
        # 加载评论数据
        if date:
            df = self.data_loader.load_comments(date=date)
            name = f"comments_{date}"
        else:
            df = self.data_loader.load_comments()
            name = "comments_all"

        if df.empty:
            print("❌ 没有加载到评论数据")
            return pd.DataFrame()

        return self.compute_from_dataframe(
            df=df,
            text_column='content',
            name=name,
            use_keywords=use_keywords,
            topN=topN
        )

    def compute_creators_frequency(self,
                                   date: Optional[str] = None,
                                   use_keywords: bool = False,
                                   topN: int = 100) -> pd.DataFrame:
        """
        计算创作者描述词频

        Args:
            date: 指定日期
            use_keywords: 是否使用关键词提取
            topN: 保留前N个词

        Returns:
            词频DataFrame
        """
        # 加载创作者数据
        if date:
            df = self.data_loader.load_creators(date=date)
            name = f"creators_{date}"
        else:
            df = self.data_loader.load_creators()
            name = "creators_all"

        if df.empty:
            print("❌ 没有加载到创作者数据")
            return pd.DataFrame()

        # 如果有desc列，用desc；否则用nickname或其他
        text_column = 'desc' if 'desc' in df.columns else 'nickname'

        return self.compute_from_dataframe(
            df=df,
            text_column=text_column,
            name=name,
            use_keywords=use_keywords,
            topN=topN
        )

    def save_frequency_table(self,
                             name: str,
                             output_dir: str = 'E:\\pycharm\\code\\SocialMediaAnalysis\\words',
                             save_csv: bool = True,
                             save_excel: bool = False) -> str:
        """
        保存词频表

        Args:
            name: 数据集名称
            output_dir: 输出目录
            save_csv: 是否保存CSV
            save_excel: 是否保存Excel

        Returns:
            保存的文件路径
        """
        if name not in self.freq_results:
            print(f"❌ 没有找到 {name} 的词频结果")
            return ""

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        df = self.freq_results[name]['df']
        stats = self.freq_results[name]

        # 添加统计信息行
        df_with_stats = df.copy()
        stats_row = pd.DataFrame({
            'word': ['--- 统计信息 ---', f'总词数: {stats["total_words"]}',
                     f'唯一词数: {stats["unique_words"]}'],
            'frequency': ['', '', ''],
            'percentage': ['', '', '']
        })
        df_with_stats = pd.concat([stats_row, df_with_stats], ignore_index=True)

        # 保存文件
        if save_csv:
            csv_path = os.path.join(output_dir, f'{name}_frequency.csv')
            df_with_stats.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"✅ 词频表已保存: {csv_path}")

        if save_excel:
            excel_path = os.path.join(output_dir, f'{name}_frequency.xlsx')
            df_with_stats.to_excel(excel_path, index=False)
            print(f"✅ 词频表已保存: {excel_path}")

        return csv_path if save_csv else excel_path

    def save_all_frequency_tables(self, output_dir: str = 'E:\\pycharm\\code\\SocialMediaAnalysis\\words'):
        """保存所有词频表"""
        for name in self.freq_results:
            self.save_frequency_table(name, output_dir)

    def compare_frequency(self, names: List[str], topN: int = 10) -> pd.DataFrame:
        """
        对比多个数据集的词频

        Args:
            names: 数据集名称列表
            topN: 对比前N个词

        Returns:
            对比DataFrame
        """
        comparison = {}

        for name in names:
            if name in self.freq_results:
                df = self.freq_results[name]['df'].head(topN)
                comparison[name] = df['word'].tolist()

        return pd.DataFrame(comparison)

    def plot_top_words(self,
                       name: str,
                       topN: int = 20,
                       figsize: tuple = (12, 8),
                       title: str = None) -> None:
        """
        绘制词频柱状图

        Args:
            name: 数据集名称
            topN: 显示前N个词
            figsize: 图表大小
            title: 图表标题
        """
        if name not in self.freq_results:
            print(f"❌ 没有找到 {name} 的词频结果")
            return

        df = self.freq_results[name]['df'].head(topN)

        plt.figure(figsize=figsize)

        # 水平柱状图
        plt.barh(range(len(df)), df['frequency'][::-1])
        plt.yticks(range(len(df)), df['word'][::-1])

        plt.xlabel('频次')
        plt.title(title or f'{name} 高频词TOP{topN}')
        plt.tight_layout()
        plt.show()

    def get_summary(self) -> pd.DataFrame:
        """获取词频统计摘要"""
        summary = []

        for name, data in self.freq_results.items():
            summary.append({
                'dataset': name,
                'total_words': data['total_words'],
                'unique_words': data['unique_words'],
                'top_word': data['df'].iloc[0]['word'] if not data['df'].empty else '',
                'top_freq': data['df'].iloc[0]['frequency'] if not data['df'].empty else 0
            })

        return pd.DataFrame(summary)