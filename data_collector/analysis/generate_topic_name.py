import ast
import re
import sys
import os
import json
import pandas as pd
from openai import OpenAI

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(project_root, ".env"), override=False)
except ImportError:
    pass

from config.config import DynamicFileManager


def main():
    api_key = os.getenv('SILICONFLOW_API_KEY', '')
    if not api_key:
        raise EnvironmentError("未设置环境变量 SILICONFLOW_API_KEY，请先 export SILICONFLOW_API_KEY=<your_key>")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.siliconflow.cn/v1"
    )

    # 1. 获取最新文件
    latest_file = DynamicFileManager.get_latest_bertopic_topics()
    if not latest_file:
        print("❌ 未找到输入文件")
        return

    csv_path = str(latest_file)
    df = pd.read_csv(csv_path, encoding='utf-8-sig')

    # 2. 核心优化后的获取函数
    def get_topic_info_optimized(row):
        """
        优化后的提示词逻辑
        """
        if row['Topic'] == -1:
            return "碎化噪声/非集中讨论", "其他"

        try:
            kw_list = ast.literal_eval(row['Representation'])[:10]
            doc_list = ast.literal_eval(row['Representative_Docs'])[:3]
            docs_context = "\n".join([f"原文{i + 1}: {str(d)[:200]}" for i, d in enumerate(doc_list)])
        except:
            kw_list = str(row['Representation']).split(',')[:10]
            docs_context = "暂无参考原文"

        # 这里的 Prompt 进行了大幅度升级
        prompt = f"""你是一名资深的社交媒体舆情专家。请对以下聚类出的数据进行深度抽象：

【关键词】：{', '.join(kw_list)}
【典型博文摘要】：
{docs_context}

---
任务要求：
1. **标题生成**：生成一个 4-10 字的精准标题。要求：
   - 必须是名词性短语（动宾结构亦可）。
   - 严禁包含“讨论”、“关于”、“分析”、“研究”等虚词。
   - 必须反映核心矛盾或事件（如：AI代写作业争议、伊朗公民撤离进展）。
2. **精准分类**：从以下类别中选出一个。准则如下：
   - [社会民生]：涉及民生福利、公共安全、日常生活、教育公平。
   - [科技数码]：涉及AI、手机发布、软硬件更新、航天科研。
   - [娱乐八卦]：涉及明星动态、影视剧综、网红轶事。
   - [时尚生活]：涉及美妆、穿搭、装修、旅游攻略、美食。
   - [国际时政]：涉及大国博弈、外交事务、海外战争、地缘政治。
   - [金融经济]：涉及股市、房产政策、财报、宏观经济分析。
   - [其他]：无法归入上述任何一类的碎杂信息。

输出必须是标准的 JSON 格式：
{{"title": "起好的标题", "category": "分类名称"}}"""

        try:
            response = client.chat.completions.create(
                model="deepseek-ai/DeepSeek-V3",
                messages=[
                    {"role": "system", "content": "你是一个精通JSON输出的舆情分析系统。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 降低温度，增加分类的确定性
                response_format={"type": "json_object"}
            )

            content = json.loads(response.choices[0].message.content.strip())
            return content.get("title", "未归类话题"), content.get("category", "其他")
        except Exception as e:
            print(f"Row {row['Topic']} Error: {e}")
            return f"话题_{row['Topic']}", "其他"

    # 3. 运行处理
    print("正在使用优化后的 Prompt 进行分析...")
    results = []

    # 使用 tqdm 显示进度
    try:
        from tqdm import tqdm
        for _, row in tqdm(df.iterrows(), total=len(df)):
            results.append(get_topic_info_optimized(row))
    except ImportError:
        for _, row in df.iterrows():
            results.append(get_topic_info_optimized(row))

    # 4. 赋值并保存
    df['topic_name'], df['category'] = zip(*results)

    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"处理完成！结果已更新: {csv_path}")



if __name__ == "__main__":
    main()