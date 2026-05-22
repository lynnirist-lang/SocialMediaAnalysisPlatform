"""
微博数据加载器
提供加载帖子、评论、创作者数据的功能
"""

import os
import glob
import re
import pandas as pd
from typing import Optional, List


class WeiboDataLoader:
    """微博数据加载器"""

    def __init__(self, data_dir: str = None):
        """
        初始化数据加载器

        Args:
            data_dir: 默认数据目录
        """
        self.data_dir = data_dir
        self.encoding = 'utf-8-sig'

    def load_posts(self,
                   file_path: Optional[str] = None,
                   date: Optional[str] = None,
                   pattern: str = '*_contents_*.csv') -> pd.DataFrame:
        """
        加载帖子数据（支持 search_contents 和 creator_contents）

        Args:
            file_path: 单个文件路径（优先使用）
            date: 指定日期，如 '2026-03-02'
            pattern: 文件名匹配模式，默认 '*_contents_*.csv'

        Returns:
            合并后的帖子DataFrame
        """
        return self._load_data(
            file_path=file_path,
            date=date,
            pattern=pattern,
            data_type='posts'
        )

    def load_comments(self,
                      file_path: Optional[str] = None,
                      date: Optional[str] = None,
                      pattern: str = 'search_comments_*.csv') -> pd.DataFrame:
        """
        加载评论数据

        Args:
            file_path: 单个文件路径（优先使用）
            date: 指定日期，如 '2026-03-02'
            pattern: 文件名匹配模式，默认 'search_comments_*.csv'

        Returns:
            合并后的评论DataFrame
        """
        return self._load_data(
            file_path=file_path,
            date=date,
            pattern=pattern,
            data_type='comments'
        )

    def load_creators(self,
                      file_path: Optional[str] = None,
                      date: Optional[str] = None,
                      pattern: str = 'creator_creators_*.csv') -> pd.DataFrame:
        """
        加载创作者/用户数据

        Args:
            file_path: 单个文件路径（优先使用）
            date: 指定日期，如 '2026-03-02'
            pattern: 文件名匹配模式，默认 'creator_creators_*.csv'

        Returns:
            合并后的创作者DataFrame
        """
        return self._load_data(
            file_path=file_path,
            date=date,
            pattern=pattern,
            data_type='creators'
        )

    def _load_data(self,
                   file_path: Optional[str],
                   date: Optional[str],
                   pattern: str,
                   data_type: str) -> pd.DataFrame:
        """
        内部方法：加载数据
        """
        dfs = []

        # 1. 如果指定了具体文件
        if file_path:
            if os.path.exists(file_path):
                df = self._read_single_file(file_path)
                if df is not None:
                    dfs.append(df)
                    print(f"✅ 加载文件: {os.path.basename(file_path)}")
            else:
                print(f"❌ 文件不存在: {file_path}")

        # 2. 如果指定了日期
        elif date and self.data_dir:
            # 根据data_type确定可能的文件名
            possible_filenames = []

            if data_type == 'posts':
                # 帖子有两种可能
                possible_filenames = [
                    f"search_contents_{date}.csv",
                    f"creator_contents_{date}.csv"
                ]
            elif data_type == 'comments':
                # 评论只有一种
                possible_filenames = [f"search_comments_{date}.csv"]
            elif data_type == 'creators':
                # 创作者只有一种
                possible_filenames = [
                    f"search_creators_{date}.csv",
                    f"creator_creators_{date}.csv"
                ]

            loaded = False
            for filename in possible_filenames:
                file_path = os.path.join(self.data_dir, filename)
                if os.path.exists(file_path):
                    df = self._read_single_file(file_path)
                    if df is not None:
                        dfs.append(df)
                        print(f"✅ 加载文件: {filename}")
                        loaded = True
                        # 如果是帖子且找到了一个，是否继续找另一个？这里选择继续找
                        if data_type != 'posts':
                            break

            if not loaded:
                print(f"❌ 未找到日期 {date} 的 {data_type} 文件")

        # 3. 否则加载目录下所有匹配的文件
        elif self.data_dir:
            file_pattern = os.path.join(self.data_dir, pattern)
            files = sorted(glob.glob(file_pattern))

            if not files:
                print(f"⚠️ 在 {self.data_dir} 中没有找到匹配 {pattern} 的文件")
            else:
                print(f"📁 找到 {len(files)} 个 {data_type} 文件:")
                for file in files:
                    df = self._read_single_file(file)
                    if df is not None:
                        dfs.append(df)
                        print(f"  ✅ {os.path.basename(file)}")

        else:
            print("❌ 请指定 file_path、date 或初始化时设置 data_dir")
            return pd.DataFrame()

        # 合并所有DataFrame
        if dfs:
            result = pd.concat(dfs, ignore_index=True)
            print(f"\n📊 总计加载 {len(result)} 条 {data_type} 数据")
            return result
        else:
            print(f"⚠️ 没有加载到任何 {data_type} 数据")
            return pd.DataFrame()

    def _read_single_file(self, file_path: str) -> Optional[pd.DataFrame]:
        """读取单个CSV文件"""
        try:
            df = pd.read_csv(file_path, encoding=self.encoding)
            # 添加来源信息
            df['source_file'] = os.path.basename(file_path)

            # 根据文件名判断类型
            if 'search_contents' in file_path:
                df['data_type'] = 'search_post'
            elif 'creator_contents' in file_path:
                df['data_type'] = 'creator_post'
            elif 'search_comments' in file_path:
                df['data_type'] = 'search_comment'
            elif 'creator_creators' in file_path:
                df['data_type'] = 'creator_info'

            return df
        except Exception as e:
            print(f"❌ 读取失败 {os.path.basename(file_path)}: {e}")
            return None

    def get_available_dates(self, pattern: str = '*_*_*.csv') -> List[str]:
        """获取可用的日期列表"""
        if not self.data_dir:
            return []

        files = glob.glob(os.path.join(self.data_dir, pattern))
        dates = set()

        for file in files:
            basename = os.path.basename(file)
            # 匹配日期格式
            match = re.search(r'\d{4}-\d{2}-\d{2}', basename)
            if match:
                dates.add(match.group())

        return sorted(list(dates))

    def get_summary(self) -> dict:
        """获取数据目录的摘要信息"""
        summary = {}

        if not self.data_dir:
            return summary

        # 统计各种文件
        summary['search_posts'] = len(glob.glob(os.path.join(self.data_dir, 'search_contents_*.csv')))
        summary['creator_posts'] = len(glob.glob(os.path.join(self.data_dir, 'creator_contents_*.csv')))
        summary['search_comments'] = len(glob.glob(os.path.join(self.data_dir, 'search_comments_*.csv')))
        summary['creator_creators'] = len(glob.glob(os.path.join(self.data_dir, 'creator_creators_*.csv')))

        # 获取日期列表
        summary['all_dates'] = self.get_available_dates()

        return summary