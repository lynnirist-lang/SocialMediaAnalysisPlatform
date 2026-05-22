from fastapi import APIRouter, Query, HTTPException
import pandas as pd
import numpy as np
from backend.models.schemas import Response, UserProfile
from backend.services.data_loader import DataLoader

router = APIRouter()

def get_data_loader():
    """获取全局 DataLoader 实例"""
    from backend.api.main import data_loader
    return data_loader


def normalize_series(series):
    """标准化系列到 0-1 区间"""
    min_val, max_val = series.min(), series.max()
    if max_val == min_val:
        return pd.Series([0.5] * len(series))
    return (series - min_val) / (max_val - min_val)


def assign_user_role(df, row):
    """
    基于多维度特征分配用户角色
    结合：粉丝数、网络中心性、爆发力、原创度
    """
    # 标准化各维度
    fans_norm = normalize_series(df['fans_count'].fillna(0)) if 'fans_count' in df.columns else pd.Series(
        [0.5] * len(df))
    pagerank_norm = normalize_series(df['pagerank_score'].fillna(0)) if 'pagerank_score' in df.columns else pd.Series(
        [0.5] * len(df))
    burst_norm = normalize_series(df['burst_power'].fillna(0)) if 'burst_power' in df.columns else pd.Series(
        [0.5] * len(df))
    originality_norm = normalize_series(
        df['originality_score'].fillna(0.5)) if 'originality_score' in df.columns else pd.Series([0.5] * len(df))

    # 综合影响力得分（加权）
    influence_score = (
            0.3 * fans_norm +
            0.3 * pagerank_norm +
            0.25 * burst_norm +
            0.15 * originality_norm
    )

    # 获取当前用户的标准化值
    idx = row.name
    fans_val = fans_norm.iloc[idx] if idx < len(fans_norm) else 0.5
    pagerank_val = pagerank_norm.iloc[idx] if idx < len(pagerank_norm) else 0.5
    burst_val = burst_norm.iloc[idx] if idx < len(burst_norm) else 0.5
    originality_val = originality_norm.iloc[idx] if idx < len(originality_norm) else 0.5
    influence_val = influence_score.iloc[idx] if idx < len(influence_score) else 0.5

    # 分层角色判定
    if fans_val > 0.7 and influence_val > 0.6:
        return '核心传播者'
    elif pagerank_val > 0.6 and influence_val > 0.5:
        return '意见领袖'
    elif burst_val > 0.5 or (originality_val > 0.7 and influence_val > 0.4):
        return '活跃参与者'
    elif any([fans_val > 0.5, pagerank_val > 0.5, burst_val > 0.5]):
        return '潜力用户'
    else:
        return '普通用户'


@router.get("/stats", response_model=Response)
async def get_user_stats():
    """获取用户画像统计摘要"""
    data_loader = get_data_loader()
    df = data_loader.load_user_stats()
    if df.empty:
        return Response(code=200, data={
            "avg_pagerank": 0,
            "network_density": 0,
            "core_nodes": 0,
            "propagation_levels": 0
        })

    # 计算统计指标
    avg_pagerank = df['pagerank_score'].mean() if 'pagerank_score' in df.columns else 0
    core_nodes = len(
        df[df['pagerank_score'] > df['pagerank_score'].quantile(0.9)]) if 'pagerank_score' in df.columns else 0

    # 估算网络密度（简化：边数/最大可能边数）
    total_users = len(df)
    active_users = df[df['total_actions'] > 1] if 'total_actions' in df.columns else df
    network_density = min(len(active_users) / total_users * 0.15, 1.0) if total_users > 0 else 0

    # 估算传播层级（基于响应速度分布）
    if 'response_speed' in df.columns:
        propagation_levels = int(df['response_speed'].quantile(0.75) / 6) + 1
    else:
        propagation_levels = 4

    return Response(code=200, data={
        "avg_pagerank": round(avg_pagerank, 4),
        "network_density": round(network_density, 2),
        "core_nodes": core_nodes,
        "propagation_levels": propagation_levels
    })


@router.get("/network", response_model=Response)
async def get_user_network(top_n: int = 50):
    """获取用户网络图数据（节点+边）"""
    data_loader = get_data_loader()
    df = data_loader.load_user_stats()
    if df.empty:
        return Response(code=200, data={"nodes": [], "links": []})

    df_sorted = df.nlargest(top_n, 'pagerank_score') if 'pagerank_score' in df.columns else df.head(top_n)

    nodes = []
    for _, row in df_sorted.iterrows():
        role = row.get('user_role', assign_user_role(df, row))

        nickname = row.get('nickname')
        if pd.isna(nickname) or not nickname or str(nickname).lower() == 'nan':
            nickname = str(row['user_id'])
        nickname = str(nickname)[:12]

        fans_count = row.get('fans_count')
        if pd.isna(fans_count):
            fans_count = 0

        pagerank = row.get('pagerank_score', 0)
        if pd.isna(pagerank):
            pagerank = 0

        nodes.append({
            "id": str(row['user_id']),
            "name": nickname,
            "value": float(fans_count),
            "symbolSize": min(max(float(pagerank) * 1000, 10), 50),
            "category": role
        })

    links = []
    node_ids = set(n['id'] for n in nodes)

    if 'betweenness_score' in df.columns:
        for i, row1 in df_sorted.iterrows():
            for j, row2 in df_sorted.iterrows():
                if i >= j:
                    continue
                if row1.get('pagerank_score', 0) > 0.001 and row2.get('pagerank_score', 0) > 0.001:
                    links.append({
                        "source": str(row1['user_id']),
                        "target": str(row2['user_id']),
                        "value": 1
                    })

    return Response(code=200, data={
        "nodes": nodes,
        "links": links[:200]
    })


@router.get("/role-distribution", response_model=Response)
async def get_role_distribution():
    """获取用户角色分布统计"""
    data_loader = get_data_loader()
    df = data_loader.load_user_stats()
    if df.empty:
        return Response(code=200, data=[])

    # 添加角色标签
    if 'user_role' not in df.columns:
        df['user_role'] = df.apply(lambda row: assign_user_role(df, row), axis=1)

    # 统计各角色数量
    role_counts = df['user_role'].value_counts().reset_index()
    role_counts.columns = ['name', 'value']

    return Response(code=200, data=role_counts.to_dict('records'))


@router.get("/list", response_model=Response)
async def get_user_list(page_size: int = 10, page: int = 1):
    data_loader = get_data_loader()
    df = data_loader.load_user_stats()
    if df.empty:
        return Response(code=200, data={"users": [], "total": 0})

    # 添加角色映射（多维度综合评分）
    if 'user_role' not in df.columns:
        df['user_role'] = df.apply(lambda row: assign_user_role(df, row), axis=1)

    # 分页
    total = len(df)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    df_page = df.iloc[start_idx:end_idx]

    return Response(code=200, data={
        "users": df_page.to_dict('records'),
        "total": total,
        "page": page,
        "page_size": page_size
    })


@router.get("/{user_id}", response_model=Response)
async def get_user_detail(user_id: str):
    """获取单个用户详情"""
    try:
        data_loader = get_data_loader()
        df = data_loader.load_user_stats()
        user_row = df[df['user_id'] == user_id]

        if user_row.empty:
            return Response(code=404, message="用户不存在")

        user_data = user_row.to_dict('records')[0]

        # 动态计算角色（与列表页保持一致）
        if 'user_role' not in user_data:
            # 重新加载完整 DataFrame 用于标准化
            df_full = data_loader.load_user_stats()

            # 找到当前用户在 DataFrame 中的索引
            user_idx = df_full[df_full['user_id'] == user_id].index[0]

            # 创建临时行对象（带 name 属性以兼容 assign_user_role）
            temp_row = df_full.loc[user_idx].copy()
            temp_row.name = user_idx

            user_data['user_role'] = assign_user_role(df_full, temp_row)

        return Response(
            code=200,
            data=user_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
