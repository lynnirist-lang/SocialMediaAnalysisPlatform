import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import pandas as pd
import torch
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer
from data_collector.cleaners.weibo_preprocessor import WeiboPreprocessor
import jieba.posseg as pseg

from config.config import (
    BERTOPIC_MODEL_DIR,
    USER_DICT_PATH,
    STOPWORDS_PATH,
    DynamicFileManager,
    GeneratedFiles
)

print("🚀 启动 BERTopic (修复版)")

# ================= 1. 初始化预处理器 (加载词典/停用词) =================
print(f"🔧 加载资源：UserDict={USER_DICT_PATH}, Stopwords={STOPWORDS_PATH}")
preprocessor = WeiboPreprocessor(
    stopwords_file_path=str(STOPWORDS_PATH),
    user_dict_path=str(USER_DICT_PATH)  # 转为字符串
)


# ================= 2. 定义适配 BERTopic 的分词函数 =================
def custom_tokenizer(text):
    if not isinstance(text, str) or len(text.strip()) == 0:
        return []
    words = pseg.cut(text)
    allowed_pos = ['n', 'nr', 'ns', 'nt', 'nz', 'nw']
    tokens = [
        w.word for w in words
        if w.flag in allowed_pos
           and len(w.word) > 1
           and w.word not in preprocessor.stopwords
    ]
    return tokens


# ================= 3. 准备数据并保留索引映射 =================
def merge_posts_and_comments_with_index():
    print("📂 读取并合并数据...")
    latest_posts = DynamicFileManager.get_latest_posts_cleaned()
    latest_comments = DynamicFileManager.get_latest_comments_cleaned()

    if not latest_posts or not latest_comments:
        raise FileNotFoundError("找不到清洗后的帖子或评论文件")

    # 尝试多种编码读取
    posts = None
    for encoding in ['utf-8-sig', 'utf-8', 'gbk']:
        try:
            posts = pd.read_csv(str(latest_posts), encoding=encoding, low_memory=False)
            print(f"✅ Posts使用编码: {encoding}")
            break
        except UnicodeDecodeError:
            continue

    comments = None
    for encoding in ['utf-8-sig', 'utf-8', 'gbk']:
        try:
            comments = pd.read_csv(str(latest_comments), encoding=encoding, low_memory=False)
            print(f"✅ Comments使用编码: {encoding}")
            break
        except UnicodeDecodeError:
            continue

    if posts is None or comments is None:
        raise ValueError("无法正确读取CSV文件")

    # 合并评论
    comments_grouped = comments.groupby('note_id')['cleaned_content'].apply(
        lambda x: ' || '.join(x.dropna().astype(str).str.strip())
    ).reset_index(name='all_comments')

    merged = posts.merge(comments_grouped, on='note_id', how='left')

    documents = []
    valid_indices = []  # 记录哪些行被加入了建模

    for idx, row in merged.iterrows():
        post_text = str(row['cleaned_content']).strip()
        comments_text = str(row.get('all_comments', '')).strip() if pd.notna(row.get('all_comments')) else ""

        if comments_text:
            full_text = f"{post_text} 评论：{comments_text}"
        else:
            full_text = post_text

        if full_text and len(full_text) > 5:
            documents.append(full_text)
            valid_indices.append(idx)

    print(f"✅ 准备完毕，共 {len(documents)} 条原始文本用于建模")
    return documents, merged, valid_indices, latest_posts


documents, merged_df, valid_indices, latest_posts = merge_posts_and_comments_with_index()

# ================= 4. 配置 CountVectorizer =================
# 根据文档数量动态调整参数，避免 max_df < min_df 错误
n_docs = len(documents)
print(f"📊 文档总数: {n_docs}，动态调整向量器参数...")

# 动态计算 min_df 和 max_df
if n_docs < 100:
    min_df_val = 2
    max_df_val = 0.8
elif n_docs < 500:
    min_df_val = 3
    max_df_val = 0.85
else:
    min_df_val = 5
    max_df_val = 0.75

print(f"⚙️ 使用参数: min_df={min_df_val}, max_df={max_df_val}")

vectorizer_model = CountVectorizer(
    tokenizer=custom_tokenizer,
    preprocessor=None,
    min_df=min_df_val,
    max_df=max_df_val,
    ngram_range=(1, 1)
)

# ================= 5. 初始化 BERTopic =================
from bertopic.vectorizers import ClassTfidfTransformer

device = "cuda" if torch.cuda.is_available() else "cpu"
embedding_model = SentenceTransformer(str(BERTOPIC_MODEL_DIR), device=device)

ctfidf_model = ClassTfidfTransformer(reduce_frequent_words=True)
topic_model = BERTopic(
    embedding_model=embedding_model,
    vectorizer_model=vectorizer_model,
    ctfidf_model=ctfidf_model,
    min_topic_size=8,
    nr_topics="auto",
    verbose=True,
    calculate_probabilities=False
)

# ================= 6. 运行建模 =================
print("\n🔄 开始训练 (GPU 加速)...")
try:
    topics, probs = topic_model.fit_transform(documents)
except ValueError as e:
    if "max_df corresponds to < documents than min_df" in str(e):
        print(f"\n⚠️ 检测到参数冲突，尝试降低 min_df 并提高 max_df...")
        # 重试策略：降低 min_df，提高 max_df
        vectorizer_model = CountVectorizer(
            tokenizer=custom_tokenizer,
            preprocessor=None,
            min_df=2,
            max_df=0.95,
            ngram_range=(1, 1)
        )
        topic_model = BERTopic(
            embedding_model=embedding_model,
            vectorizer_model=vectorizer_model,
            ctfidf_model=ctfidf_model,
            min_topic_size=8,
            nr_topics="auto",
            verbose=True,
            calculate_probabilities=False
        )
        topics, probs = topic_model.fit_transform(documents)
    else:
        raise
# ================= 7. 将 Topic ID 写回原文件 =================
print("\n💾 正在将 Topic ID 映射回原始数据...")

merged_df['Topic'] = -1

for i, topic_id in enumerate(topics):
    original_idx = valid_indices[i]
    merged_df.at[original_idx, 'Topic'] = topic_id

# 关键修复：使用读取时的同一文件路径
output_csv_path = str(latest_posts)
try:
    merged_df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
    print(f"✅ 已将 Topic 列更新至: {output_csv_path}")

    # 验证写入
    df_check = pd.read_csv(output_csv_path, nrows=3)
    if 'Topic' in df_check.columns:
        topic_counts = df_check['Topic'].value_counts()
        print(f"✅ 验证成功：Topic 列存在，前3行分布: {topic_counts.to_dict()}")
    else:
        print("❌ 验证失败：Topic 列未写入")
except Exception as e:
    print(f"⚠️ 保存 CSV 失败: {e}")
    import traceback

    traceback.print_exc()

# ================= 8. 输出主题概览并保存 =================
print("\n📊 主题概览:")
topic_info_df = topic_model.get_topic_info()
print(topic_info_df)

output_path = str(GeneratedFiles.get_bertopic_topics_path())
topic_info_df.to_csv(output_path, index=False, encoding='utf-8-sig')

print(f"\n✅ 完成！结果已保存至 {output_path}")

# ================= 9. 自动生成 topic_name 和 category =================
print("\n🤖 开始生成话题名称和分类...")
generate_script = os.path.join(project_root, "data_collector", "analysis", "generate_topic_name.py")

if os.path.exists(generate_script):
    try:
        result = subprocess.run(
            [sys.executable, generate_script],
            cwd=project_root,
            timeout=600,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("✅ 话题命名和分类完成")
        else:
            print(f"⚠️ 话题命名失败: {result.stderr}")
    except Exception as e:
        print(f"⚠️ 执行话题命名脚本异常: {e}")
else:
    print("⚠️ 未找到 generate_topic_name.py，跳过话题命名")
