"""
微博数据预处理器
提供文本清洗、分词、停用词过滤、广告检测等功能
"""

import re
import warnings
from pathlib import Path
from typing import Optional, List, Union
import pandas as pd
import numpy as np
import jieba
import jieba.analyse
from datetime import datetime

from data_collector.cleaners.duplicate_detector import DuplicateDetector

warnings.filterwarnings('ignore')


class WeiboPreprocessor:
    """微博数据预处理器"""

    def __init__(self,
                 stopwords_file_path=None,
                 user_dict_path=None):
        """
        初始化预处理器

        Args:
            stopwords_file_path: 停用词文件路径
            user_dict_path: 用户自定义词典文件路径（每行一个词）
        """
        self.stopword_file = stopwords_file_path
        self.stopwords = self._load_stopwords()

        # 加载自定义词典（如果提供）
        if user_dict_path:
            self._load_user_dict(user_dict_path)

        self.ad_pipeline = None  # 广告过滤器实例

    def _load_user_dict(self, user_dict_path: str) -> None:
        """
        加载用户自定义词典

        Args:
            user_dict_path: 词典文件路径
        """
        try:
            jieba.load_userdict(user_dict_path)
            print(f"✅ 已加载自定义词典: {user_dict_path}")
        except Exception as e:
            print(f"⚠️ 加载自定义词典失败: {e}，继续使用默认词典")

    def _load_stopwords(self) -> set:
        """加载停用词(从文件中读取)"""
        stopwords = set()

        # 基础停用词兜底
        base_stops = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都',
            '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会',
            '着', '没有', '看', '好', '自己', '这', '那', '吗', '啊', '呢',
            '把', '被', '让', '给', '跟', '与', '对', '并', '因此', '所以'
        }

        # 如果提供了停用词文件，尝试加载
        if self.stopword_file:
            file_path = Path(self.stopword_file)
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            word = line.strip()
                            if word and not word.startswith('#'):  # 跳过注释行
                                stopwords.add(word)
                    print(f"✅ 从文件加载了 {len(stopwords)} 个停用词")
                    return stopwords

                except Exception as e:
                    print(f"⚠️ 读取停用词文件出错：{e}，使用基础停用词")
            else:
                print(f"⚠️ 未找到停用词文件：{self.stopword_file}，使用基础停用词")

        # 使用基础停用词
        stopwords.update(base_stops)
        print(f"📚 使用基础停用词，共 {len(stopwords)} 个")
        return stopwords

    def filter_ads_hybrid(self, text, author=None):
        """混合广告过滤（规则）"""
        if not isinstance(text, str) or len(text) < 5:
            return False, "文本过短"

        # 白名单
        whitelist = {'人民日报', '央视新闻', '新华网', '人民网', '中国政府网'}
        if author and author in whitelist:
            return False, "白名单账号"

        # 规则快速过滤
        rule_keywords = [
            '加 V', '加 v', '微信', 'QQ', '淘宝', '京东', '拼多多',
            '优惠券', '特价', '代购', '代理', '兼职', '日结',
            '限时', '最后一天', '手慢无', '白菜价',
            # 新增：营销活动关键词
            '免单', '口令', '福利', '抽奖', '红包', '秒杀',
            '点击领取', '立即抢购', '扫码', '淘口令',
            # 新增：引流词汇
            '入口', '链接', '详情页', '下单', '购买', '优惠'
        ]

        for keyword in rule_keywords:
            if keyword in text:
                return True, f"规则命中：{keyword}"

        return False, ""

    def clean_text(self, text):
        """清洗文本"""
        if pd.isna(text) or not isinstance(text, str):
            return ""
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'#([^#]+)#', '', text)  # 话题标签有时是噪声来源，可考虑去除
        text = re.sub(r'@\S+', '', text)

        # 2. 【新增】去除软广告高频词（抽奖、领券等）
        marketing_words = r'(抽奖|详情戳|点击领|包邮|点赞|关注我|私信|代购|拼团)'
        text = re.sub(marketing_words, '', text)

        # 3. 【新增】去除无意义符号和过多的表情
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)

        return text

    def segment(self,
                text: str,
                use_keywords: bool = False,
                topK: int = 10,
                cut_all: bool = False,
                min_word_len: int = 2) -> List[str]:
        """
        分词

        Args:
            text: 清洗后的文本
            use_keywords: 是否使用关键词提取模式
            topK: 关键词数量
            cut_all: 是否使用全模式（默认False，精确模式）
            min_word_len: 最小词长度

        Returns:
            分词列表
        """
        if not text:
            return []

        try:
            if use_keywords:
                # 关键词提取模式
                words = jieba.analyse.extract_tags(text, topK=topK, withWeight=False)
            else:
                # 精确模式分词
                words = jieba.lcut(text, cut_all=cut_all)
                # 过滤停用词和短词
                words = [w for w in words
                         if w not in self.stopwords and len(w) >= min_word_len]

            return words

        except Exception as e:
            print(f"⚠️ 分词出错: {e}")
            return []

    def process_dataframe(self, df: pd.DataFrame, text_column: str = 'content',
                          filter_ads: bool = False,
                          author_column: str = None,
                          deduplicate: bool = False,
                          dedup_method: str = 'semantic') -> pd.DataFrame:
        """
        批量处理 DataFrame

        Args:
            df: 原始数据 DataFrame
            text_column: 文本列名
            filter_ads: 是否过滤广告
            author_column: 作者列名（用于白名单）
            deduplicate: 是否去重
            dedup_method: 去重方法

        Returns:
            处理后的 DataFrame
        """
        df = df.copy()

        # ========== 广告过滤 ==========
        if filter_ads:
            print("\n🚫 开始广告过滤...")

            keep_indices = []
            filter_reasons = []

            for idx, row in df.iterrows():
                text = row[text_column]
                author = row[author_column] if author_column else None

                should_filter, reason = self.filter_ads_hybrid(text, author)

                if not should_filter:
                    keep_indices.append(idx)
                filter_reasons.append(reason)

            df['ad_filter_reason'] = filter_reasons
            original_len = len(df)
            df = df.iloc[keep_indices].reset_index(drop=True)
            print(f"  广告过滤：保留了 {len(df)}/{original_len} 条 ({len(df) / original_len * 100:.1f}%)")

        # 清洗文本
        df['cleaned_content'] = df[text_column].apply(self.clean_text)

        # 过滤空内容
        original_len = len(df)
        df = df[df['cleaned_content'].str.len() > 0].copy()
        print(f"  过滤空内容：{original_len - len(df)} 条")

        # ========== 新增：过滤无意义内容 ==========
        print("\n🗑️ 过滤无意义内容...")
        meaningless_patterns = [
            '转发微博', '分享图片', '分享评论', '转', '转发',
            '恭喜', '加油', '世界和平', '元宵快乐', '新年快乐',
            '太棒了', '优秀', '厉害', '好牛', '震撼', '干得漂亮',
            '支持', '买了', '好看', '好美', '赞', '顶'
        ]

        # 过滤完全匹配的无意义短语
        mask_meaningless = ~df['cleaned_content'].isin(meaningless_patterns)

        # 过滤纯数字
        mask_not_pure_number = ~df['cleaned_content'].str.match(r'^\d+$')

        # 过滤长度<5 的短内容（可选，根据需要调整）
        mask_min_length = df['cleaned_content'].str.len() >= 5

        # 应用所有过滤条件
        original_len = len(df)
        df = df[mask_meaningless & mask_not_pure_number & mask_min_length].copy()
        filtered_count = original_len - len(df)
        print(f"  过滤无意义内容：{filtered_count} 条")

        # 添加过滤标记列
        df['is_meaningful'] = True
        # ====================================

        # # 分词
        # df['words'] = df['cleaned_content'].apply(self.segment)
        # df['words_str'] = df['words'].apply(lambda x: ' '.join(x))

        # ========== 去重 ==========
        if deduplicate:
            print("\n🔄 开始去重...")
            deduplicator = DuplicateDetector(similarity_threshold=0.85)
            df = deduplicator.deduplicate_dataframe(df, text_column='cleaned_content', method=dedup_method)

        print(f"\n✅ 处理完成，剩余 {len(df)} 条数据")
        return df

    def parse_timestamp(self, timestamp):
        """解析时间戳"""
        try:
            if pd.isna(timestamp):
                return None

            ts = int(timestamp)
            if ts > 1e12:  # 13位毫秒时间戳
                return datetime.fromtimestamp(ts / 1000)
            else:  # 10位秒时间戳
                return datetime.fromtimestamp(ts)
        except:
            return None
