import ast
import json
import math
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
import pandas as pd
from backend.models.schemas import Response
from backend.services.data_loader import DataLoader
from functools import lru_cache

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DYNAMIC_TOPICS_FILE = Path(project_root) / "words" / "analysis_data" / "dynamic_topics.json"
_STOPWORDS_FILE = Path(project_root) / "words" / "stopwords_hit.txt"

# 加载停用词，用于修正 DTM 链名
_DTM_STOPWORDS: set = set()
try:
    with open(_STOPWORDS_FILE, encoding="utf-8") as _f:
        _DTM_STOPWORDS = {line.strip() for line in _f if line.strip()}
except Exception:
    pass


def _select_chain_name(chain: dict) -> str | None:
    """
    从链的关键词中选出第一个有意义的词作为链名。
    有意义 = 长度 > 1 且不在停用词表 且不是纯数字。
    返回 None 表示该链全为虚词噪声，应当过滤掉。
    """
    # 汇总所有关键词：全局 + 各时期
    all_kws: list[str] = list(chain.get("keywords", []))
    for pd_data in chain.get("periods", {}).values():
        all_kws.extend(pd_data.get("keywords", []))

    for kw in all_kws:
        kw = str(kw).strip()
        if len(kw) > 1 and not kw.isdigit() and kw not in _DTM_STOPWORDS:
            return kw
    return None  # 纯噪声链


router = APIRouter()
def get_data_loader():
    """获取全局 DataLoader 实例"""
    from backend.api.main import data_loader
    return data_loader

@router.get("/keywords", response_model=Response)
async def get_topic_keywords(top_n: int = 20):
    """获取热门关键词排行"""
    data_loader = get_data_loader()
    df_topics = data_loader.load_bertopic_results()

    if df_topics.empty:
        return Response(code=200, data=[])

    keywords_list = []
    for _, row in df_topics.iterrows():
        # 从 Representation 列提取关键词（字符串列表格式）
        representation = row.get('Representation', '')
        if pd.isna(representation) or not representation:
            continue

        try:
            keywords = ast.literal_eval(representation)
            if not isinstance(keywords, list):
                continue
        except:
            # 降级：按逗号分割
            keywords = str(representation).split(',')

        topic_name = row.get('topic_name', f"话题{row.get('Topic', '未知')}")
        count = int(row.get('Count', 0))

        for kw in keywords[:5]:  # 每个主题取前5个关键词
            if isinstance(kw, str) and kw.strip():
                keywords_list.append({
                    "word": kw.strip(),
                    "count": count,
                    "topic": topic_name
                })

    keywords_list.sort(key=lambda x: x['count'], reverse=True)

    return Response(code=200, data=keywords_list[:top_n])


@router.get("/clusters", response_model=Response)
async def get_topic_clusters():
    """优化后的聚类数据接口"""
    try:
        data_loader = get_data_loader()
        df_topics = data_loader.load_bertopic_results()

        if df_topics.empty:
            print("[WARNING] BERTopic 结果为空")
            return Response(code=200, data={"nodes": [], "links": [], "categories": []})

        required_cols = ['Topic', 'Count', 'Representation']
        missing_cols = [col for col in required_cols if col not in df_topics.columns]
        if missing_cols:
            print(f"[ERROR] BERTopic 数据缺少列: {missing_cols}")
            return Response(code=200, data={"nodes": [], "links": [], "categories": []})

        # 屏蔽 Topic -1 (离群值)，并取热度最高的 25 个话题
        df_filtered = df_topics[df_topics['Topic'] != -1].sort_values(by='Count', ascending=False).head(25)

        if df_filtered.empty:
            return Response(code=200, data={"nodes": [], "links": [], "categories": []})

        nodes = []
        keyword_sets = []

        for _, row in df_filtered.iterrows():
            try:
                kw_list = ast.literal_eval(row['Representation']) if isinstance(row['Representation'], str) else row[
                    'Representation']
            except Exception as e:
                print(f"[WARNING] 解析关键词失败: {e}")
                kw_list = str(row['Representation']).split(',')

            # 提取前 8 个关键词用于计算相似度
            clean_kws = set([str(k).strip() for k in kw_list if len(str(k).strip()) > 1][:8])
            keyword_sets.append(clean_kws)

            count = int(row['Count'])
            size = math.log(count + 1) * 12

            topic_name = row.get('topic_name', f"话题{row.get('Topic', '未知')}")

            nodes.append({
                "name": topic_name,
                "value": count,
                "symbolSize": round(size, 2),
                "category": 0,
                "draggable": True
            })

        links = []
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                set_i = keyword_sets[i]
                set_j = keyword_sets[j]

                if not set_i or not set_j:
                    continue

                intersection = set_i & set_j
                union = set_i | set_j

                similarity = len(intersection) / len(union) if union else 0

                if similarity >= 0.15:
                    links.append({
                        "source": nodes[i]['name'],
                        "target": nodes[j]['name'],
                        "value": round(similarity, 3),
                        "lineStyle": {
                            "width": 1 + similarity * 8,
                            "curveness": 0.1
                        }
                    })

        if nodes:
            counts = [n['value'] for n in nodes]
            q80 = sorted(counts)[int(len(counts) * 0.8)]
            q40 = sorted(counts)[int(len(counts) * 0.4)]

            for node in nodes:
                if node['value'] >= q80:
                    node['category'] = 0
                elif node['value'] >= q40:
                    node['category'] = 1
                else:
                    node['category'] = 2

        categories = [{"name": "核心热点"}, {"name": "重点关注"}, {"name": "一般话题"}]

        return Response(
            code=200,
            data={
                "nodes": nodes,
                "links": links,
                "categories": categories
            }
        )
    except Exception as e:
        import traceback
        error_msg = f"[ERROR] /api/topic/clusters 接口异常: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/details/{topic_id}")
async def get_topic_details(topic_id: int):
    data_loader = get_data_loader()
    df = data_loader.load_bertopic_results()
    topic_data = df[df['Topic'] == topic_id]

    if topic_data.empty:
        raise HTTPException(status_code=404, detail="Topic not found")

    return Response(code=200, data={
        "name": topic_data.iloc[0]['topic_name'],
        "keywords": ast.literal_eval(topic_data.iloc[0]['Representation']),
        "docs": ast.literal_eval(topic_data.iloc[0]['Representative_Docs'])[:5]  # 只给前5条
    })


@router.get("/evolution", response_model=Response)
async def get_topic_evolution(interval: str = "week", top_n: int = 6):
    """动态主题演化：按时间段统计各话题帖子数量，供 ThemeRiver 图使用"""
    try:
        data_loader = get_data_loader()
        df_posts = data_loader.load_posts()
        df_topics_meta = data_loader.load_bertopic_results()

        if df_posts.empty or 'Topic' not in df_posts.columns:
            return Response(code=200, data={"series": [], "legend": []})

        # 解析时间字段
        time_col = 'create_date_time' if 'create_date_time' in df_posts.columns else 'create_time'
        if time_col not in df_posts.columns:
            return Response(code=200, data={"series": [], "legend": []})

        df = df_posts.copy()
        df['dt'] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.dropna(subset=['dt'])
        df = df[df['Topic'] != -1]

        if df.empty:
            return Response(code=200, data={"series": [], "legend": []})

        # 话题名称映射
        topic_name_map: dict = {}
        if not df_topics_meta.empty and 'Topic' in df_topics_meta.columns:
            for _, row in df_topics_meta.iterrows():
                tid = row.get('Topic')
                name = row.get('topic_name', f'话题{tid}')
                if tid is not None and not (isinstance(tid, float) and math.isnan(tid)):
                    topic_name_map[int(tid)] = str(name)

        # 选出热度 top_n 个话题
        hot_topics = df['Topic'].value_counts().head(top_n).index.tolist()
        df = df[df['Topic'].isin(hot_topics)].copy()
        df['topic_name'] = df['Topic'].apply(lambda t: topic_name_map.get(int(t), f'话题{t}'))

        # 按时间粒度分组
        if interval == 'day':
            df['period'] = df['dt'].dt.strftime('%Y-%m-%d')
        elif interval == 'month':
            df['period'] = df['dt'].dt.strftime('%Y-%m')
        else:  # week（默认）
            df['period'] = df['dt'].dt.to_period('W').apply(lambda p: str(p.start_time.date()))

        # 统计并转换为 ThemeRiver 格式 [[date, count, topic_name], ...]
        grouped = (
            df.groupby(['period', 'topic_name'])
            .size()
            .reset_index(name='count')
            .sort_values('period')
        )

        series_data = [
            [row['period'], int(row['count']), row['topic_name']]
            for _, row in grouped.iterrows()
        ]
        legend = list(grouped['topic_name'].unique())

        return Response(code=200, data={"series": series_data, "legend": legend})
    except Exception as e:
        import traceback
        print(f"[ERROR] /api/topic/evolution: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dynamic-evolution", response_model=Response)
async def get_dynamic_topic_evolution():
    """
    读取 DTM 输出，返回 Sankey 节点/链接数据和时间趋势数据。

    Sankey 节点名格式："{period}::{chain_name}_{chain_id}"
    前端用 "::" 分割后取第二段显示，保证节点名全局唯一。
    """
    if not _DYNAMIC_TOPICS_FILE.exists():
        return Response(
            code=404,
            message="DTM 结果文件不存在，请先运行 data_collector/analysis/run_dynamic_topic.py",
            data=None,
        )
    try:
        raw = json.loads(_DYNAMIC_TOPICS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取 DTM 结果失败: {e}")

    periods: list = raw.get("periods", [])
    chains: list = raw.get("chains", [])

    # ── 链名后处理：修正虚词名、过滤纯噪声链 ────────────────────────────────
    cleaned_chains = []
    for chain in chains:
        best = _select_chain_name(chain)
        if best is None:
            continue  # 全虚词链，直接丢弃
        if chain["name"] != best:
            chain = dict(chain, name=best)  # 浅拷贝，不改原 JSON
        cleaned_chains.append(chain)
    chains = cleaned_chains

    # ── Sankey ───────────────────────────────────────────────────────────────
    sankey_nodes = []
    sankey_links = []
    node_set = set()

    def _node_name(period, chain):
        return f"{period}::{chain['name']}_{chain['chain_id']}"

    for chain in chains:
        sorted_periods = sorted(chain["periods"].keys())
        for i, p in enumerate(sorted_periods):
            nname = _node_name(p, chain)
            if nname not in node_set:
                sankey_nodes.append({"name": nname})
                node_set.add(nname)
            if i > 0:
                prev_p = sorted_periods[i - 1]
                sankey_links.append({
                    "source": _node_name(prev_p, chain),
                    "target": nname,
                    "value": chain["periods"][p]["doc_count"],
                    "keywords": chain["periods"][p]["keywords"][:5],
                })

    # ── Trend（折线图）───────────────────────────────────────────────────────
    trend_series = []
    for chain in chains:
        data = [chain["periods"].get(p, {}).get("doc_count", 0) for p in periods]
        trend_series.append({
            "name": chain["name"],
            "data": data,
            "keywords": chain["keywords"],
        })

    return Response(code=200, data={
        "generated_at": raw.get("generated_at"),
        "periods": periods,
        "sankey": {"nodes": sankey_nodes, "links": sankey_links},
        "trend": {"series": trend_series},
    })


@router.get("/bar", response_model=Response)
async def get_topic_sentiment_bar():
    """按话题大类（Category）汇总的情感分布"""
    try:
        data_loader = get_data_loader()
        df_topics = data_loader.load_bertopic_results()
        if df_topics.empty:
            return Response(code=200, data={"topics": [], "categories": [], "positive": [], "neutral": [], "negative": []})

        # 兼容处理：优先使用 category，其次 topic_name
        if 'category' in df_topics.columns:
            topic_cat_map = df_topics[['Topic', 'category']].drop_duplicates()
        elif 'topic_name' in df_topics.columns:
            topic_cat_map = df_topics[['Topic', 'topic_name']].drop_duplicates()
            topic_cat_map.rename(columns={'topic_name': 'category'}, inplace=True)
        else:
            topic_cat_map = df_topics[['Topic']].copy()
            topic_cat_map['category'] = topic_cat_map['Topic'].apply(lambda x: f"话题{x}")

        df_posts = data_loader.load_posts()
        if df_posts.empty or 'sentiment' not in df_posts.columns:
            return Response(code=200, data={"topics": [], "categories": [], "positive": [], "neutral": [], "negative": []})

        # 关键修复：检查是否有 Topic 列，如果没有则跳过 Topic 过滤
        if 'Topic' not in df_posts.columns:
            print("[WARNING] 帖子数据缺少 Topic 列，无法按话题分类统计")
            return Response(code=200, data={
                "topics": ["未聚类"],
                "categories": ["未聚类"],
                "positive": [0.0],
                "neutral": [0.0],
                "negative": [0.0]
            })

        df_merged = pd.merge(df_posts, topic_cat_map, on='Topic', how='left')
        df_merged['category'] = df_merged['category'].fillna('未分类')

        categories_list = []
        positive_list = []
        neutral_list = []
        negative_list = []

        df_grouped = df_merged[df_merged['Topic'] != -1].groupby('category')['sentiment']

        for category, group in df_grouped:
            total = len(group)
            if total == 0: continue

            pos_pct = round((len(group[group == '积极']) / total) * 100, 1)
            neu_pct = round((len(group[group == '中性']) / total) * 100, 1)
            neg_pct = round((len(group[group == '消极']) / total) * 100, 1)

            categories_list.append(category)
            positive_list.append(pos_pct)
            neutral_list.append(neu_pct)
            negative_list.append(neg_pct)

        return Response(code=200, data={
            "topics": categories_list,
            "categories": categories_list,
            "positive": positive_list,
            "neutral": neutral_list,
            "negative": negative_list
        })
    except Exception as e:
        import traceback
        error_msg = f"[ERROR] /api/topic/bar 接口异常: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=str(e))
