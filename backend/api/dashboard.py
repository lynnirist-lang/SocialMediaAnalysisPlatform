from fastapi import APIRouter, Query, HTTPException
from datetime import date
import pandas as pd
from pathlib import Path
from backend.models.schemas import Response, DashboardSummary, TrendData, WordCloudItem
from backend.services.data_loader import DataLoader

router = APIRouter()

def get_data_loader():
    """获取全局 DataLoader 实例"""
    from backend.api.main import data_loader
    return data_loader



@router.get("/summary", response_model=Response)
async def get_dashboard_summary(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None)
):
    """获取数据看板顶部的三个统计指标"""
    data_loader = get_data_loader()
    df_posts = data_loader.load_posts()
    df_comments = data_loader.load_comments()

    total_posts = len(df_posts)
    total_users = df_posts['user_id'].nunique() if not df_posts.empty else 0
    total_comments = len(df_comments)

    if not df_posts.empty and 'sentiment_score' in df_posts.columns:
        avg_sentiment = float(df_posts['sentiment_score'].mean())
    elif not df_posts.empty and 'sentiment' in df_posts.columns:
        score_map = {'积极': 1, '中性': 0, '消极': -1}
        avg_sentiment = float(df_posts['sentiment'].map(score_map).mean())
    else:
        avg_sentiment = 0.0

    return Response(
        code=200,
        data={
            "total_posts": total_posts,
            "total_users": total_users,
            "total_comments": total_comments,
            "avg_sentiment": round(avg_sentiment, 2)
        }
    )


@router.get("/trend", response_model=Response)
async def get_post_trend():
    """获取趋势图数据：日期、发帖量、用户数"""
    data_loader = get_data_loader()
    df_posts = data_loader.load_posts()
    if df_posts.empty:
        return Response(code=200, data={"dates": [], "post_counts": [], "user_counts": []})

    # 处理日期格式
    df_posts['date'] = pd.to_datetime(df_posts['create_date_time']).dt.date

    # 按天聚合：计数（发帖量）和 唯一用户数
    trend_df = df_posts.groupby('date').agg(
        count=('content', 'count'),
        user_count=('user_id', 'nunique')
    ).reset_index().sort_values('date')

    return Response(
        code=200,
        data={
            "dates": trend_df['date'].astype(str).tolist(),
            "post_counts": trend_df['count'].tolist(),
            "user_counts": trend_df['user_count'].tolist()
        }
    )


@router.get("/wordcloud", response_model=Response)
async def get_wordcloud():
    """获取词云数据"""
    data_loader = get_data_loader()
    df = data_loader.load_bertopic_results()
    if df.empty:
        return Response(code=200, data=[])

    wordcloud_data = []
    # 核心修复：使用 CSV 中的 Representation 列（关键词列表格式）
    if 'Representation' in df.columns and 'Count' in df.columns:
        for _, row in df.iterrows():
            count = int(row.get('Count', 0))
            # 解析 ['词1', '词2'] 格式的字符串
            try:
                import ast
                keywords = ast.literal_eval(row['Representation'])
                for kw in keywords[:5]:  # 每个主题取前5个关键词
                    wordcloud_data.append({"name": kw, "value": count})
            except:
                continue

    # 去重并取前50
    seen = set()
    unique_data = []
    for item in wordcloud_data:
        if item['name'] not in seen:
            seen.add(item['name'])
            unique_data.append(item)
            if len(unique_data) >= 50:
                break

    return Response(code=200, data=unique_data)