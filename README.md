===========================================================
📊 共 747 条数据，开始预测...
✅ 完成！保存至: E:\pycharm\code\SocialMediaAnalysis\words\sentiment_data\comments_model_20260513.csv
📊 统计: 747 条, note_id范围: 5176726767275958-5298118578146409

============================================================
📂 处理文件: comments_cleaned_20260511.csv
💾 输出到: E:\pycharm\code\SocialMediaAnalysis\words\sentiment_data\comments_model_20260511.csv
============================================================
📊 共 994 条数据，开始预测...
✅ 完成！保存至: E:\pycharm\code\SocialMediaAnalysis\words\sentiment_data\comments_model_20260511.csv
📊 统计: 994 条, note_id范围: 5293477034200215-5297435098484992

============================================================
📂 处理文件: comments_cleaned_20260507.csv
💾 输出到: E:\pycharm\code\SocialMediaAnalysis\words\sentiment_data\comments_model_20260507.csv
============================================================
📊 共 1203 条数据，开始预测...
      [WARN] 情感分析失败: Command '['E:\\pycharm\\code\\SocialMediaAnalysis\\.venv\\Scripts\\python.exe', 'E:\\pycharm\\code\\SocialMediaAnalysis\\data_collector\\model\\predict.py']' timed out after 600.0 seconds
Traceback (most recent call last):
  File "E:\pycharm\code\SocialMediaAnalysis\data_collector\scheduler.py", line 498, in _trigger_downstream_tasks
    result = subprocess.run(
             ^^^^^^^^^^^^^^^
  File "E:\pycharm\python-amd\Lib\subprocess.py", line 550, in run
    stdout, stderr = process.communicate(input, timeout=timeout)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\pycharm\python-amd\Lib\subprocess.py", line 1228, in communicate
    sts = self.wait(timeout=self._remaining_time(endtime))
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\pycharm\python-amd\Lib\subprocess.py", line 1264, in wait
    return self._wait(timeout=timeout)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\pycharm\python-amd\Lib\subprocess.py", line 1591, in _wait
    raise TimeoutExpired(self.args, timeout)
subprocess.TimeoutExpired: Command '['E:\\pycharm\\code\\SocialMediaAnalysis\\.venv\\Scripts\\python.exe', 'E:\\pycharm\\code\\SocialMediaAnalysis\\data_collector\\model\\predict.py']' timed out after 600.0 seconds
   👤 5.2 启动用户画像提取...
   📂 找到 14 个帖子用户文件, 0 个评论用户文件
============================================================
🚀 启动高级用户特征提取流程（多维动态特征体系）
============================================================
