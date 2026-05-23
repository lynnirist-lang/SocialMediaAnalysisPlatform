import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import torch
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import json
import os
from pathlib import Path
import re
from datetime import datetime
from config.config import FINE_TUNED_MODEL_DIR

sys.path.append(str(Path(__file__).parent.parent.parent))
from config.config import DynamicFileManager, SENTIMENT_DATA_DIR, CLEANED_DATA_DIR, find_all_dated_files

model_path = FINE_TUNED_MODEL_DIR

print("⏳ 正在加载模型...")
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)
model.eval()
print("✅ 模型加载完毕！\n")


def predict_sentiment_batch(texts, batch_size=32):
    results = []
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        inputs = tokenizer(batch_texts, return_tensors="pt", truncation=True, padding=True, max_length=128)

        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
            confidence, prediction = torch.max(probs, 1)

        for pred_id, conf_score in zip(prediction.tolist(), confidence.tolist()):
            results.append((pred_id, conf_score))

    return results


def process_file(input_file, output_file, data_type="posts"):
    print(f"\n{'=' * 60}")
    print(f"📂 处理文件: {input_file.name}")
    print(f"💾 输出到: {output_file}")
    print(f"{'=' * 60}")

    if not input_file.exists():
        print(f"❌ 文件不存在，跳过")
        return False

    try:
        df = pd.read_csv(input_file)
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        return False

    content_col = 'cleaned_content' if 'cleaned_content' in df.columns else 'content'
    if content_col not in df.columns:
        print(f"❌ 未找到内容列")
        return False

    texts = df[content_col].fillna('').tolist()
    note_ids = df['note_id'].tolist() if 'note_id' in df.columns else list(range(len(texts)))

    print(f"📊 共 {len(texts)} 条数据，开始预测...")
    predictions = predict_sentiment_batch(texts)

    results = []
    for i, (text, note_id) in enumerate(zip(texts, note_ids)):
        pred_id, score = predictions[i]
        results.append({
            'note_id': note_id,
            'text': text,
            'label': pred_id,
            '置信度': score,
            'data_type': data_type
        })

    result_df = pd.DataFrame(results)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')

    print(f"✅ 完成！保存至: {output_file}")
    print(f"📊 统计: {len(result_df)} 条, note_id范围: {result_df['note_id'].min()}-{result_df['note_id'].max()}")
    return True


def extract_date_from_filename(filename):
    match = re.search(r'(\d{8})', filename)
    if match:
        return match.group(1)
    return datetime.now().strftime('%Y%m%d')


if __name__ == "__main__":
    processed_count = 0

    # 1. 处理所有帖子文件
    print("\n" + "=" * 60)
    print("📝 开始处理帖子数据")
    print("=" * 60)

    posts_files = find_all_dated_files(CLEANED_DATA_DIR, 'posts_cleaned_*.csv')
    if not posts_files:
        fixed_file = CLEANED_DATA_DIR / 'posts_cleaned.csv'
        if fixed_file.exists():
            posts_files = [fixed_file]

    for posts_file in posts_files:
        date_str = extract_date_from_filename(posts_file.name)
        output_file = SENTIMENT_DATA_DIR / f"posts_model_{date_str}.csv"

        if output_file.exists():
            print(f"\n⏭️  跳过已存在: {output_file.name}")
            continue

        if process_file(posts_file, output_file, "posts"):
            processed_count += 1

    # 2. 处理所有评论文件
    print("\n" + "=" * 60)
    print("💬 开始处理评论数据")
    print("=" * 60)

    comments_files = find_all_dated_files(CLEANED_DATA_DIR, 'comments_cleaned_*.csv')
    if not comments_files:
        fixed_file = CLEANED_DATA_DIR / 'comments_cleaned.csv'
        if fixed_file.exists():
            comments_files = [fixed_file]

    for comments_file in comments_files:
        date_str = extract_date_from_filename(comments_file.name)
        output_file = SENTIMENT_DATA_DIR / f"comments_model_{date_str}.csv"

        if output_file.exists():
            print(f"\n⏭️  跳过已存在: {output_file.name}")
            continue

        if process_file(comments_file, output_file, "comments"):
            processed_count += 1

    print("\n" + "=" * 60)
    print(f"🎉 全部完成！共处理 {processed_count} 个文件")
    print("=" * 60)
