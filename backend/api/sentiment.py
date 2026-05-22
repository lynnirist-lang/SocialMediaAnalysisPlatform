from datetime import datetime

from fastapi import APIRouter, Query, HTTPException
import pandas as pd
from backend.models.schemas import Response,PostItem
from backend.services.data_loader import DataLoader

router = APIRouter()

def get_data_loader():
    """获取全局 DataLoader 实例"""
    from backend.api.main import data_loader
    return data_loader




@router.get("/distribution", response_model=Response)
async def get_sentiment_distribution():
    """获取情感分布统计（饼图用）"""
    data_loader = get_data_loader()
    df_posts = data_loader.load_posts()
    if df_posts.empty:
        return Response(code=200, data={"positive": 0, "neutral": 0, "negative": 0})

    # 根据标签统计
    counts = df_posts['sentiment'].value_counts().to_dict()

    return Response(
        code=200,
        data={
            "positive": int(counts.get('积极', 0)),
            "neutral": int(counts.get('中性', 0)),
            "negative": int(counts.get('消极', 0))
        }
    )


@router.get("/trend", response_model=Response)
async def get_sentiment_trend():
    """获取情感得分随时间变化趋势"""
    data_loader = get_data_loader()
    df = data_loader.load_posts()
    if df.empty:
        return Response(code=200, data={"dates": [], "scores": []})

    # 处理日期
    df['date'] = pd.to_datetime(df['create_date_time']).dt.date

    # 计算每条微博的情感得分（结合标签和置信度）
    def calc_score(row):
        sentiment = row.get('sentiment', '中性')
        confidence = row.get('置信度', None)

        if confidence is None or pd.isna(confidence):
            confidence = 0.5

        confidence = float(confidence)

        if sentiment == '积极':
            return confidence
        elif sentiment == '消极':
            return -confidence
        else:
            return 0.0

    df['score'] = df.apply(calc_score, axis=1)

    # 按天聚合平均得分
    trend_df = df.groupby('date')['score'].mean().reset_index()
    trend_df = trend_df.sort_values('date')

    return Response(
        code=200,
        data={
            "dates": trend_df['date'].astype(str).tolist(),
            "scores": trend_df['score'].round(2).tolist()
        }
    )


@router.get("/heatmap", response_model=Response)
async def get_sentiment_heatmap():
    """获取情感活跃热力图：横轴小时(0-23)，纵轴星期(0-6)"""
    data_loader = get_data_loader()
    df = data_loader.load_posts()
    if df.empty:
        return Response(code=200, data=[])

    try:
        if 'create_date_time' in df.columns:
            df['parsed_time'] = pd.to_datetime(df['create_date_time'], errors='coerce')
        elif 'create_time' in df.columns:
            df['parsed_time'] = pd.to_datetime(df['create_time'], unit='s', errors='coerce')
        else:
            return Response(code=200, data=[], message="缺少时间字段")

        df = df.dropna(subset=['parsed_time'])

        if df.empty:
            return Response(code=200, data=[])

        df['hour'] = df['parsed_time'].dt.hour
        df['weekday'] = df['parsed_time'].dt.weekday

        heatmap_data = df.groupby(['hour', 'weekday']).size().reset_index(name='value')

        result = heatmap_data[['hour', 'weekday', 'value']].values.tolist()

        return Response(code=200, data=result)
    except Exception as e:
        import traceback
        print(f"[ERROR] 热力图数据处理失败: {e}")
        print(traceback.format_exc())
        return Response(code=500, data=[], message=f"数据处理失败: {str(e)}")


@router.get("/posts", response_model=Response)
async def get_sentiment_posts(page_size: int = 10):
    """获取带情感标签的博文，供底部表格使用"""
    data_loader = get_data_loader()
    df = data_loader.load_posts()
    latest_posts = df.sort_values('create_time', ascending=False).head(page_size)

    posts = []
    for _, row in latest_posts.iterrows():
        try:
            if 'create_date_time' in df.columns and pd.notna(row.get('create_date_time')):
                dt = pd.to_datetime(row['create_date_time'])
                create_time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                ts = float(row['create_time'])
                if ts > 1e12:
                    ts = ts / 1000
                dt = datetime.fromtimestamp(ts)
                create_time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"[ERROR] 时间转换失败: {e}, 原始值: {row.get('create_time')}")
            create_time_str = str(row.get('create_time', ''))

        sentiment_label = row.get('sentiment', '中性')
        confidence = row.get('置信度', None)

        if confidence is None:
            confidence = float(row.get('sentiment_score', 0.5))
        else:
            confidence = float(confidence)

        if sentiment_label == '积极':
            sentiment_score = confidence
        elif sentiment_label == '消极':
            sentiment_score = -confidence
        else:
            sentiment_score = 0.0

        posts.append({
            "create_time": create_time_str,
            "content": row['content'],
            "sentiment": sentiment_label,
            "sentiment_score": round(sentiment_score, 4),
            "note_id": str(row.get('note_id', ''))
        })

    return Response(code=200, data={"posts": posts})

