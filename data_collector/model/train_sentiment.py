import gc
import os
import pandas as pd
import torch
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from datasets import load_dataset, Dataset, ClassLabel 
from sklearn.metrics import accuracy_score, f1_score, classification_report
import numpy as np
from config.config import FINAL_MODEL_DIR, RESULTS_FINETUNE_DIR, setup_environment, FINE_TUNED_MODEL_DIR, SENTIMENT_MODEL_PATH
setup_environment()

# ================= 配置区域 =================
# 1. 模型选择
MODEL_NAME = str(FINAL_MODEL_DIR)  # 强大的中文 Roberta 模型

# 2. 任务参数
NUM_LABELS = 3 # 根据你的数据修改：2分类填2，3分类填3
MAX_LENGTH = 128  # 文本最大长度，超过截断
BATCH_SIZE = 16  # 显存够大可以调大 (T4显卡通常支持16-32)
EPOCHS = 3  # 训练轮数
LEARNING_RATE = 1e-5

# 3. 文件路径
DATA_FILE = str(SENTIMENT_MODEL_PATH)  # 数据文件绝对路径
OUTPUT_DIR = str(RESULTS_FINETUNE_DIR)  # 训练输出目录
FINAL_MODEL_PATH = str(FINE_TUNED_MODEL_DIR)  # 最终模型保存目录

# ================= 1. 检查设备 =================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if device.type == "cuda":
    print(f"显卡型号：{torch.cuda.get_device_name(0)}")
    print(f"显存总量：{torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    # 检查是否支持混合精度
    compute_capability = torch.cuda.get_device_capability(0)
    if compute_capability[0] >= 7:
        print("✓ 支持 FP16 混合精度训练")
    else:
        print("⚠ GPU 计算能力较低，可能不支持 FP16")
else:
    print("警告：未检测到 GPU! 请确认已安装 CUDA 版 PyTorch。")

# ================= 2. 加载数据 =================
if not os.path.exists(DATA_FILE):
    raise FileNotFoundError(f"找不到文件 {DATA_FILE}，请确保它和脚本在同一目录下")

print(f">>> 正在加载 {DATA_FILE} ...")
df = pd.read_csv(DATA_FILE)

# 简单的数据清洗
df = df.dropna(subset=['text', 'label'])  # 删除空行
df['text'] = df['text'].astype(str)
df['label'] = df['label'].astype(int)

print(f"数据总量: {len(df)} 条")
print(f"标签分布:\n{df['label'].value_counts()}")

dataset = Dataset.from_pandas(df)
dataset = dataset.cast_column("label", ClassLabel(num_classes=3))
split_dataset = dataset.train_test_split(test_size=0.2, seed=42,  stratify_by_column="label")

# 释放内存
del df
gc.collect()

# ================= 3. 数据预处理 (Tokenization) =================
print(">>> 正在加载分词器并预处理数据...")
tokenizer = BertTokenizer.from_pretrained(MODEL_NAME)


def preprocess_function(examples):
    return tokenizer(
        examples["text"],
        truncation=True,
        padding="max_length",
        max_length=MAX_LENGTH
    )


tokenized_train = split_dataset['train'].map(preprocess_function, batched=True)
tokenized_test = split_dataset['test'].map(preprocess_function, batched=True)

# 释放内存
del split_dataset
gc.collect()

# 重命名列以符合 Trainer 要求
tokenized_train = tokenized_train.rename_column("label", "labels")
tokenized_train.set_format(type='torch', columns=['input_ids', 'attention_mask', 'labels'])

tokenized_test = tokenized_test.rename_column("label", "labels")
tokenized_test.set_format(type='torch', columns=['input_ids', 'attention_mask', 'labels'])

# ================= 4. 加载模型 =================
print(f">>> 正在加载模型 {MODEL_NAME} ...")
model = BertForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=NUM_LABELS)
model.to(device)


# ================= 5. 定义评估指标 =================
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)


    return {
        "accuracy": accuracy_score(labels, predictions),
        "f1_macro": f1_score(labels, predictions, average='macro'),
        "f1_weighted": f1_score(labels, predictions, average='weighted')
    }


# ================= 6. 配置训练参数 (GPU 优化) =================
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    learning_rate=LEARNING_RATE,
    weight_decay=0.01,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="f1_macro",
    logging_steps=10,
    fp16=True,  # 【关键】开启混合精度，大幅加速并节省显存
    dataloader_num_workers=2,  # Linux 服务器建议开启多进程
    report_to="none",  # 关闭 wandb 等报告，避免报错
    gradient_accumulation_steps=1,
    dataloader_pin_memory=True,
    # 【新增】保存 checkpoint 策略
    save_total_limit=2,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_train,
    eval_dataset=tokenized_test,
    compute_metrics=compute_metrics
)

# ================= 7. 开始训练 =================
print(">>> 开始微调训练...")
if device.type == "cuda":
    torch.cuda.empty_cache()
    print(f"训练前显存使用：{torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")

trainer.train()

# ================= 8. 最终评估 =================
print(">>> 测试集最终评估结果:")
eval_results = trainer.evaluate()
for k, v in eval_results.items():
    print(f"{k}: {v:.4f}")

# 打印详细分类报告
predictions_output = trainer.predict(tokenized_test)
preds = np.argmax(predictions_output.predictions, axis=-1)
labels = predictions_output.label_ids
print("\n详细分类报告:")
print(classification_report(labels, preds, digits=4))

# ================= 9. 保存与打包 =================
print(f">>> 保存最佳模型到 {FINAL_MODEL_PATH} ...")
# 保存最佳模型（而不是最后一个epoch的模型）
best_model_path = os.path.join(OUTPUT_DIR, "checkpoint-best")  # 取决于具体保存策略，这里直接保存当前最优
# 更稳妥的方式是直接保存 trainer 中的 model
model.save_pretrained(FINAL_MODEL_PATH)
tokenizer.save_pretrained(FINAL_MODEL_PATH)

# 打包成 zip，方便下载
import shutil

zip_name = "my_sentiment_model"
shutil.make_archive(zip_name, 'zip', FINAL_MODEL_PATH)
print(f"========================================")
print(f"训练完成！模型已打包为: {zip_name}.zip")
print(f"请在服务器下载该文件回本地使用。")
print(f"========================================")

# 【新增】训练后清理
if device.type == "cuda":
    print(f"\n训练后显存峰值：{torch.cuda.max_memory_allocated(0) / 1024**3:.2f} GB")
    torch.cuda.empty_cache()