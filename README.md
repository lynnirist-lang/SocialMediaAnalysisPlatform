🔄 步骤 5/5: 触发下游分析任务...
   📊 用户画像将使用: creators_20260524.csv
   📊 用户画像将使用评论用户文件: comment_users_20260524.csv
   📤 传递 2 个用户文件给下游任务
   [SKIP] 今日 BERTopic 输出已存在: bertopic_topics_20260524.csv，跳过重训练
   [START] 5.1.5 情感预测（串行执行）...
      [WARN] 情感分析失败: cannot access local variable 'posts_file' where it is not associated with a value
Traceback (most recent call last):
  File "E:\pycharm\code\SocialMediaAnalysis\data_collector\scheduler.py", line 499, in _trigger_downstream_tasks
    [sys.executable, str(sentiment_script), str(posts_file), str(output_file)],
                                                ^^^^^^^^^^
UnboundLocalError: cannot access local variable 'posts_file' where it is not associated with a value
   👤 5.2 启动用户画像提取...
INFO:     127.0.0.1:56418 - "GET /api/scheduler/status HTTP/1.1" 200 OK
Traceback (most recent call last):
  File "E:\pycharm\code\SocialMediaAnalysis\user_characters\advanced_extractor.py", line 3, in <module>
    import pandas as pd
  File "E:\pycharm\code\SocialMediaAnalysis\.venv\Lib\site-packages\pandas\__init__.py", line 34, in <module>
    from pandas.compat import (
  File "E:\pycharm\code\SocialMediaAnalysis\.venv\Lib\site-packages\pandas\compat\__init__.py", line 28, in <module>
    from pandas.compat.pyarrow import (
  File "E:\pycharm\code\SocialMediaAnalysis\.venv\Lib\site-packages\pandas\compat\pyarrow.py", line 12, in <module>
    import pyarrow as pa
  File "E:\pycharm\code\SocialMediaAnalysis\.venv\Lib\site-packages\pyarrow\__init__.py", line 71, in <module>
    from pyarrow.lib import (BuildInfo, CppBuildInfo, RuntimeInfo, set_timezone_db_path,
  File "pyarrow/scalar.pxi", line 20, in init pyarrow.lib
    from uuid import UUID
  File "<frozen importlib._bootstrap>", line 1176, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1147, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 690, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 936, in exec_module
  File "<frozen importlib._bootstrap_external>", line 1032, in get_code
  File "<frozen importlib._bootstrap_external>", line 1130, in get_data
KeyboardInterrupt
INFO:     Shutting down
   ❌ 用户画像失败 (退出码: 3221225786)
