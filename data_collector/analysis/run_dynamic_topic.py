"""
动态主题建模（Dynamic Topic Modeling, DTM）

流程：
  1. 加载所有历史清洗帖子文件，按 note_id 去重
  2. 计算全量 sentence-transformers embedding（只算一次）
  3. 按周分片，在每片上独立运行 BERTopic（UMAP + HDBSCAN + ClassTF-IDF）
  4. 用各片主题的 centroid embedding 计算跨期 cosine 相似度，贪婪对齐 → 演化链
  5. 保存 JSON 供 API 读取
"""
import json
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.config import (
    ANALYSIS_DATA_DIR,
    BERTOPIC_MODEL_DIR,
    CLEANED_DATA_DIR,
    STOPWORDS_PATH,
    find_all_dated_files,
    setup_environment,
)

setup_environment()

# 加载停用词（用于过滤虚词，提升关键词质量）
_STOPWORDS: set = set()
try:
    with open(STOPWORDS_PATH, encoding="utf-8") as _f:
        _STOPWORDS = {line.strip() for line in _f if line.strip()}
except Exception:
    pass

OUTPUT_FILE = ANALYSIS_DATA_DIR / "dynamic_topics.json"

SIMILARITY_THRESHOLD = 0.60   # 跨期主题对齐阈值
MIN_DOCS_PER_SLICE = 30       # 每片最少文档数（过少则跳过）
MAX_CHAINS = 8                # 最终保留的演化链数
MIN_CHAIN_PERIODS = 2         # 链至少跨越的期数（过短则过滤）


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def _tokenize_zh(text: str) -> str:
    import jieba
    return " ".join(
        t for t in jieba.cut(str(text))
        if len(t.strip()) > 1 and t not in _STOPWORDS
    )


def _run_slice_bertopic(texts, embs, embed_model):
    """对单个时间片运行 BERTopic，返回 (model, topic_assignments)"""
    from bertopic import BERTopic
    from umap import UMAP
    from hdbscan import HDBSCAN
    from bertopic.vectorizers import ClassTfidfTransformer
    from sklearn.feature_extraction.text import CountVectorizer

    n = len(texts)
    umap_model = UMAP(
        n_neighbors=min(10, max(2, n - 1)),
        n_components=min(5, max(2, n - 2)),
        min_dist=0.0,
        metric="cosine",
        random_state=42,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=max(3, n // 15),
        min_samples=1,
        prediction_data=True,
    )
    vectorizer = CountVectorizer(
        tokenizer=str.split,
        min_df=1,
        max_df=1.0,
        max_features=3000,
    )
    model = BERTopic(
        embedding_model=embed_model,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        ctfidf_model=ClassTfidfTransformer(reduce_frequent_words=True),
        nr_topics="auto",
        verbose=False,
    )
    tokenized = [_tokenize_zh(t) for t in texts]
    topics, _ = model.fit_transform(tokenized, embeddings=embs)
    return model, topics


def _extract_slice_topics(model, embeddings, topic_assignments):
    """提取各主题的关键词、文档数、centroid embedding"""
    result = []
    for tid in sorted(set(t for t in topic_assignments if t != -1)):
        idxs = [i for i, t in enumerate(topic_assignments) if t == tid]
        keywords = [w for w, _ in model.get_topic(tid)[:8] if w]
        centroid = embeddings[idxs].mean(axis=0)
        result.append({
            "local_id": tid,
            "keywords": keywords,
            "doc_count": len(idxs),
            "centroid": centroid,   # ndarray，后续序列化时去掉
        })
    return result


def _kw_overlap(kws1: list, kws2: list) -> bool:
    """两个主题的关键词集合是否有至少 1 个共同词。"""
    return bool(set(kws1) & set(kws2))


def _align_topics(prev_topics, curr_topics):
    """
    贪婪 cosine 匹配两个时间片之间的主题。
    双重条件：cosine 相似度 >= 阈值 且 关键词至少有 1 个重叠。
    返回 [(prev_idx, curr_idx, similarity)]，按相似度降序。
    """
    if not prev_topics or not curr_topics:
        return []
    sims = cosine_similarity(
        np.stack([t["centroid"] for t in prev_topics]),
        np.stack([t["centroid"] for t in curr_topics]),
    )
    matched, used_curr = [], set()
    order = sorted(
        ((i, int(np.argmax(sims[i])), float(np.max(sims[i]))) for i in range(len(prev_topics))),
        key=lambda x: -x[2],
    )
    for pi, ci, sim in order:
        if (sim >= SIMILARITY_THRESHOLD
                and ci not in used_curr
                and _kw_overlap(prev_topics[pi]["keywords"], curr_topics[ci]["keywords"])):
            matched.append((pi, ci, sim))
            used_curr.add(ci)
    return matched


def _build_chains(slices_topics, periods):
    """根据逐期对齐结果构建话题演化链"""
    chains = []
    # pcmap[period_idx][local_topic_id] → chain_id
    pcmap = [{} for _ in periods]

    def _new_chain(pidx, topic):
        cid = len(chains)
        chains.append({
            "chain_id": cid,
            "name": topic["keywords"][0] if topic["keywords"] else f"话题{cid}",
            "keywords": topic["keywords"],
            "periods": {
                periods[pidx]: {
                    "doc_count": topic["doc_count"],
                    "keywords": topic["keywords"],
                }
            },
        })
        pcmap[pidx][topic["local_id"]] = cid

    # 第一期：所有主题开新链
    for t in slices_topics[0]:
        _new_chain(0, t)

    for pidx in range(1, len(periods)):
        prev = slices_topics[pidx - 1]
        curr = slices_topics[pidx]
        matched_curr = set()

        for pi, ci, sim in _align_topics(prev, curr):
            cid = pcmap[pidx - 1].get(prev[pi]["local_id"])
            if cid is None:
                continue
            chains[cid]["periods"][periods[pidx]] = {
                "doc_count": curr[ci]["doc_count"],
                "keywords": curr[ci]["keywords"],
            }
            pcmap[pidx][curr[ci]["local_id"]] = cid
            matched_curr.add(ci)

        # 未被匹配的当期主题 → 新链
        for ci, t in enumerate(curr):
            if ci not in matched_curr:
                _new_chain(pidx, t)

    return chains


# ── LLM 语义命名 ──────────────────────────────────────────────────────────────

def _name_chains_with_llm(chains: list) -> list:
    """调用 SiliconFlow DeepSeek 为每条演化链生成语义标题。"""
    api_key = os.getenv("SILICONFLOW_API_KEY", "")
    if not api_key:
        print("[INFO] 未设置 SILICONFLOW_API_KEY，跳过 LLM 语义命名")
        return chains
    try:
        from openai import OpenAI
    except ImportError:
        print("[WARNING] openai 未安装（pip install openai），跳过 LLM 命名")
        return chains

    client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
    print(f"\n🏷️  LLM 语义命名（共 {len(chains)} 条演化链）...")

    for chain in chains:
        core_kws = [k for k in chain["keywords"] if k not in _STOPWORDS and len(k) > 1]
        if not core_kws:
            chain["name"] = "碎化噪声"
            print(f"  [{chain['chain_id']}] 全虚词 → 碎化噪声")
            continue

        # 汇总各时期有意义的关键词
        period_kws: list = []
        for pd_data in chain["periods"].values():
            period_kws.extend(pd_data["keywords"][:5])
        extra_kws = list(dict.fromkeys(
            k for k in period_kws if k not in _STOPWORDS and len(k) > 1
        ))[:10]

        prompt = (
            "你是社交媒体舆情专家，根据话题关键词生成精准标题。\n\n"
            f"【核心关键词】：{', '.join(core_kws[:8])}\n"
            f"【各时期补充关键词】：{', '.join(extra_kws)}\n\n"
            '要求：4-8 字名词性短语，禁含"讨论/分析/关于"等虚词，'
            "反映核心事件（如：特朗普访华、AI大模型竞争）。\n"
            '输出格式：{"title": "话题标题"}'
        )

        try:
            resp = client.chat.completions.create(
                model="deepseek-ai/DeepSeek-V3",
                messages=[
                    {"role": "system", "content": "你是精通JSON输出的舆情分析系统。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content.strip())
            new_name = data.get("title") or chain["name"]
            print(f"  [{chain['chain_id']}] {chain['name']} → {new_name}")
            chain["name"] = new_name
        except Exception as e:
            print(f"  [WARNING] 链 {chain['chain_id']} 命名失败: {e}")

    return chains


# ── 主函数 ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("动态主题建模 (DTM) 开始")
    print("=" * 60)

    # 1. 加载所有历史帖子文件并去重
    all_files = find_all_dated_files(CLEANED_DATA_DIR, "posts_cleaned_[0-9]*.csv")
    if not all_files:
        print("❌ 未找到清洗后帖子文件")
        return

    frames = []
    for f in all_files:
        try:
            frames.append(pd.read_csv(f, encoding="utf-8-sig"))
        except Exception as e:
            print(f"  跳过 {f.name}: {e}")
    if not frames:
        print("❌ 所有文件读取失败")
        return

    df = pd.concat(frames, ignore_index=True)
    if "note_id" in df.columns:
        df = df.drop_duplicates(subset=["note_id"]).reset_index(drop=True)
    print(f"✓ 加载帖子: {len(df)} 条 (共 {len(all_files)} 个文件，已去重)")

    date_col = next(
        (c for c in ["create_date_time", "created_at", "date", "publish_time"] if c in df.columns),
        None,
    )
    text_col = "cleaned_content" if "cleaned_content" in df.columns else "content"
    if not date_col:
        print("❌ 未找到时间列，退出")
        return

    df["_dt"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=["_dt", text_col]).reset_index(drop=True)
    # 按周分片（数据跨度不足多月时，月粒度不够）
    df["_period"] = df["_dt"].dt.to_period("W").astype(str)

    counts = df["_period"].value_counts()
    periods = sorted(p for p in counts.index if counts[p] >= MIN_DOCS_PER_SLICE)
    print(f"✓ 有效时间片 ({MIN_DOCS_PER_SLICE}+ 篇): {periods}")

    if len(periods) < 2:
        print("❌ 有效时间片不足 2 个，无法构建演化链")
        return

    # 2. 全量 embedding（只算一次，各片复用）
    print("\n📐 计算全量文本向量...")
    from sentence_transformers import SentenceTransformer
    embed_model = SentenceTransformer(str(BERTOPIC_MODEL_DIR))
    all_embeddings = embed_model.encode(
        df[text_col].astype(str).tolist(),
        show_progress_bar=True,
        batch_size=64,
    )
    print(f"✓ 向量维度: {all_embeddings.shape}")

    # 3. 按时间片运行 BERTopic
    slices_topics = []
    for pidx, period in enumerate(periods):
        mask = (df["_period"] == period)
        row_idx = df.index[mask].tolist()
        texts = df.loc[row_idx, text_col].astype(str).tolist()
        embs = all_embeddings[row_idx]

        print(f"\n[{pidx + 1}/{len(periods)}]  {period}  ({len(texts)} 篇)")
        try:
            model, topic_assignments = _run_slice_bertopic(texts, embs, embed_model)
            slice_info = _extract_slice_topics(model, embs, topic_assignments)
            noise = sum(1 for t in topic_assignments if t == -1)
            print(f"  → {len(slice_info)} 主题  |  噪声 {noise} 篇")
            for t in slice_info[:4]:
                print(f"     [{t['local_id']}] {t['keywords'][:5]}  ({t['doc_count']} 篇)")
        except Exception as exc:
            print(f"  ❌ 处理失败: {exc}")
            slice_info = []
        slices_topics.append(slice_info)

    # 4. 构建演化链
    print("\n🔗 构建主题演化链...")
    chains = _build_chains(slices_topics, periods)

    # 过滤短链 & 按总文档量排序，取 top N
    chains = [c for c in chains if len(c["periods"]) >= MIN_CHAIN_PERIODS]
    chains.sort(
        key=lambda c: sum(v["doc_count"] for v in c["periods"].values()),
        reverse=True,
    )
    chains = chains[:MAX_CHAINS]

    print(f"✓ 稳定演化链: {len(chains)} 条")

    # 5. LLM 语义命名
    chains = _name_chains_with_llm(chains)
    for c in chains:
        total = sum(v["doc_count"] for v in c["periods"].values())
        print(f"  [{c['chain_id']}] {c['name']}  |  {len(c['periods'])} 期  |  {total} 篇")

    # 6. 序列化（去掉 centroid ndarray）
    clean_chains = [
        {
            "chain_id": c["chain_id"],
            "name": c["name"],
            "keywords": c["keywords"],
            "periods": {
                p: {"doc_count": v["doc_count"], "keywords": v["keywords"]}
                for p, v in c["periods"].items()
            },
        }
        for c in chains
    ]

    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "periods": periods,
        "chains": clean_chains,
    }
    ANALYSIS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✅ 已保存: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
