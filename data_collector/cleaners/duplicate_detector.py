"""
重复内容检测器
提供基于哈希和语义的文本去重功能
"""

import re
import hashlib
import pandas as pd
from difflib import SequenceMatcher
from typing import Optional, List


class DuplicateDetector:
    """重复内容检测器"""

    def __init__(self, similarity_threshold=0.85):
        self.similarity_threshold = similarity_threshold
        self.seen_texts = []
        self.seen_hashes = set()

    def normalize_for_dedup(self, text):
        """为去重做规范化"""
        if not isinstance(text, str):
            return ""
        text = text.lower()
        text = re.sub(r'\s+', '', text)    # 移除所有空白字符
        text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
        return text

    def compute_hash(self, text):
        """计算文本哈希"""
        if not text:
            return None
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def is_duplicate_simple(self, text):
        """简单去重：基于完全匹配"""
        if not text:
            return False
        norm_text = self.normalize_for_dedup(text)
        text_hash = self.compute_hash(norm_text)
        if text_hash in self.seen_hashes:
            return True
        self.seen_hashes.add(text_hash)
        return False

    def is_duplicate_semantic(self, text):
        """语义去重：基于文本相似度"""
        if not text:
            return False
        norm_text = self.normalize_for_dedup(text)
        for seen in self.seen_texts:
            similarity = SequenceMatcher(None, norm_text, seen).ratio()
            if similarity > self.similarity_threshold:
                return True
        self.seen_texts.append(norm_text)
        return False

    def deduplicate_dataframe(self, df, text_column='cleaned_content',
                              method='semantic'):
        """对 DataFrame 去重"""
        self.seen_hashes = set()
        self.seen_texts = []

        keep_mask = []  # 使用布尔掩码而不是索引列表，记录每行是否保留
        duplicate_count = 0

        print(f"\n🔍 开始去重 (方法：{method})...")

        # 重置索引以确保连续性
        df_reset = df.reset_index(drop=True)

        for idx in range(len(df_reset)):
            text = df_reset.iloc[idx][text_column]

            if pd.isna(text) or not isinstance(text, str):
                keep_mask.append(True)
                continue

            if method == 'simple':
                is_dup = self.is_duplicate_simple(text)
            else:
                is_dup = self.is_duplicate_semantic(text)

            if is_dup:
                keep_mask.append(False)  # 标记为删除
                duplicate_count += 1
            else:
                keep_mask.append(True)   # 标记为保留

        # 使用布尔索引筛选
        df_result = df_reset.copy()
        df_result['is_duplicate'] = [not keep for keep in keep_mask]

        result_df = df_result[keep_mask].reset_index(drop=True)

        original_len = len(df_reset)
        kept_len = len(result_df)

        print(f"  去重前：{original_len} 条")
        print(f"  保留：{kept_len} 条")
        print(f"  重复：{duplicate_count} 条 ({duplicate_count / original_len * 100:.1f}%)")

        return result_df
