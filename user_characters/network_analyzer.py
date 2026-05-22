import pandas as pd
import networkx as nx
from typing import Dict, Tuple


class NetworkAnalyzer:
    """社交网络分析器"""

    @staticmethod
    def build_graph(df_posts: pd.DataFrame, df_comments: pd.DataFrame) -> nx.DiGraph:
        """
        构建用户交互有向图
        :param df_posts: 过滤后的帖子数据
        :param df_comments: 过滤后的评论数据
        :return: NetworkX 有向图
        """
        G = nx.DiGraph()

        # 添加所有用户作为节点
        all_users = set(df_posts['user_id'].astype(str).unique()) | \
                    set(df_comments['user_id'].astype(str).unique())
        G.add_nodes_from(all_users)

        # 基于回复关系添加边
        for _, row in df_comments.iterrows():
            reply_user = str(row['user_id'])
            note_id = row['note_id']

            # 找到原帖作者
            original_post = df_posts[df_posts['note_id'] == note_id]
            if not original_post.empty:
                original_user = str(original_post.iloc[0]['user_id'])

                # 自己不回复自己
                if reply_user != original_user:
                    if G.has_edge(reply_user, original_user):
                        G[reply_user][original_user]['weight'] += 1
                    else:
                        G.add_edge(reply_user, original_user, weight=1)

        return G

    @staticmethod
    def calculate_pagerank(G: nx.DiGraph) -> Dict[str, float]:
        """计算 PageRank 值"""
        try:
            return nx.pagerank(G, weight='weight', max_iter=100)
        except:
            return {node: 0.0 for node in G.nodes()}

    @staticmethod
    def calculate_betweenness(G: nx.DiGraph) -> Dict[str, float]:
        """计算介数中心性（支持大规模采样加速）"""
        if G.number_of_nodes() > 1000:
            # 大规模图使用采样
            return nx.betweenness_centrality_subset(
                G,
                sources=list(G.nodes())[:100],
                targets=list(G.nodes())[100:200],
                weight='weight'
            )
        else:
            return nx.betweenness_centrality(G, weight='weight')

    @staticmethod
    def calculate_degree_metrics(G: nx.DiGraph) -> Tuple[Dict, Dict]:
        """计算入度和出度（带权重）"""
        return dict(G.in_degree(weight='weight')), dict(G.out_degree(weight='weight'))

    def analyze(self, df_posts: pd.DataFrame, df_comments: pd.DataFrame) -> pd.DataFrame:
        """
        执行完整网络分析
        :return: 包含网络特征的 DataFrame
        """
        print("🕸️ [6/9] 构建用户交互网络...")
        G = self.build_graph(df_posts, df_comments)
        print(f"   ✅ 网络构建完成：{G.number_of_nodes()} 个节点，{G.number_of_edges()} 条边")

        print("📊 [7/9] 计算网络结构特征...")
        pagerank = self.calculate_pagerank(G)
        betweenness = self.calculate_betweenness(G)
        in_degree, out_degree = self.calculate_degree_metrics(G)

        network_df = pd.DataFrame({
            'user_id': list(G.nodes()),
            'pagerank_score': [pagerank.get(u, 0) for u in G.nodes()],
            'betweenness_score': [betweenness.get(u, 0) for u in G.nodes()],
            'in_degree_weighted': [in_degree.get(u, 0) for u in G.nodes()],
            'out_degree_weighted': [out_degree.get(u, 0) for u in G.nodes()]
        })

        print(
            f"   ✅ PageRank 范围：[{network_df['pagerank_score'].min():.6f}, {network_df['pagerank_score'].max():.6f}]")
        print(
            f"   ✅ 介数中心性范围：[{network_df['betweenness_score'].min():.6f}, {network_df['betweenness_score'].max():.6f}]")

        return network_df
