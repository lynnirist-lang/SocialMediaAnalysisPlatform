"""
定时数据采集任务
从 MediaCrawler 获取最新数据并执行完整处理流程
"""
import glob
import json
import shlex
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
import time
import re
from pathlib import Path
from datetime import datetime
import schedule
import pandas as pd
import subprocess

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import (
    MEDIA_CRAWLER_DATA_DIR,
    CLEANED_DATA_DIR,
    AUTHOR_DIR,
    STOPWORDS_PATH,
    USER_DICT_PATH,
    GeneratedFiles,
    DynamicFileManager,
    SENTIMENT_DATA_DIR,
    CRAWLER_WORK_DIR,
    CRAWLER_COMMAND,
    CRAWLER_TIMEOUT,
    CRAWLER_SKIP_ON_FAILURE,
)
from data_collector.cleaners.weibo_preprocessor import WeiboPreprocessor
from data_collector.cleaners.weibo_data_loader import WeiboDataLoader


class DataCollectorScheduler:
    """数据采集调度器"""

    STATUS_FILE = Path(__file__).parent.parent / "data" / "scheduler_status.json"
    CONTROL_FILE = Path(__file__).parent.parent / "data" / "scheduler_control.json"

    def __init__(self):
        self.preprocessor = WeiboPreprocessor(
            stopwords_file_path=str(STOPWORDS_PATH),
            user_dict_path=str(USER_DICT_PATH)
        )
        self.data_loader = WeiboDataLoader(data_dir=str(MEDIA_CRAWLER_DATA_DIR))

    # ------------------------------------------------------------------
    # Status / control file helpers
    # ------------------------------------------------------------------

    def _write_status(self, is_running: bool, last_run: dict = None) -> None:
        """Write scheduler status to JSON file."""
        try:
            # Compute next scheduled times from registered jobs
            next_times = []
            for job in schedule.jobs:
                if "pipeline" in (job.tags or set()):
                    if job.next_run:
                        next_times.append(job.next_run.isoformat(timespec="seconds"))
            next_times.sort()

            # Load existing history
            history = []
            if self.STATUS_FILE.exists():
                try:
                    existing = json.loads(self.STATUS_FILE.read_text(encoding="utf-8"))
                    history = existing.get("history", [])
                except Exception:
                    history = []

            # Append last_run to history (keep last 10)
            if last_run is not None:
                history.append(last_run)
                history = history[-10:]

            status = {
                "is_running": is_running,
                "pid": os.getpid(),
                "last_run": last_run,
                "next_scheduled": next_times,
                "history": history,
            }

            self.STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.STATUS_FILE.write_text(
                json.dumps(status, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"   [WARN] Failed to write scheduler status: {e}")

    def _read_control(self) -> dict:
        """Read control file; returns {'enabled': True} if file not found."""
        try:
            if self.CONTROL_FILE.exists():
                return json.loads(self.CONTROL_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"   [WARN] Failed to read scheduler control file: {e}")
        return {"enabled": True}

    def _run_crawler(self) -> dict:
        """
        启动爬虫项目并等待其完成。

        返回格式：
          {"status": "success"|"skipped"|"failed"|"timeout",
           "returncode": int|None,
           "duration_s": float,
           "message": str}
        """
        if not CRAWLER_COMMAND:
            return {"status": "skipped", "returncode": None,
                    "duration_s": 0.0, "message": "CRAWLER_COMMAND 未配置，跳过爬虫"}

        work_dir = str(CRAWLER_WORK_DIR) if CRAWLER_WORK_DIR and CRAWLER_WORK_DIR.exists() else None
        cmd_parts = shlex.split(CRAWLER_COMMAND, posix=False)

        print(f"\n{'─' * 50}")
        print(f"🕷️  启动爬虫: {CRAWLER_COMMAND}")
        if work_dir:
            print(f"   工作目录: {work_dir}")
        print(f"   超时限制: {CRAWLER_TIMEOUT}s")
        print(f"{'─' * 50}")

        t0 = datetime.now()
        try:
            proc = subprocess.Popen(
                cmd_parts,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # 实时打印爬虫输出，同时等待超时
            try:
                stdout, _ = proc.communicate(timeout=CRAWLER_TIMEOUT)
                if stdout:
                    for line in stdout.splitlines()[-30:]:   # 最多打印末尾30行
                        print(f"   [CRAWLER] {line}")
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                duration = (datetime.now() - t0).total_seconds()
                msg = f"爬虫超时（>{CRAWLER_TIMEOUT}s），已强制终止"
                print(f"   ⚠️  {msg}")
                return {"status": "timeout", "returncode": None,
                        "duration_s": round(duration, 1), "message": msg}

            duration = (datetime.now() - t0).total_seconds()
            if proc.returncode == 0:
                msg = f"爬虫执行成功 (耗时 {duration:.0f}s)"
                print(f"   ✅ {msg}")
                return {"status": "success", "returncode": 0,
                        "duration_s": round(duration, 1), "message": msg}
            else:
                msg = f"爬虫退出码 {proc.returncode}（耗时 {duration:.0f}s）"
                print(f"   ❌ {msg}")
                return {"status": "failed", "returncode": proc.returncode,
                        "duration_s": round(duration, 1), "message": msg}

        except FileNotFoundError:
            duration = (datetime.now() - t0).total_seconds()
            msg = f"找不到爬虫命令：{cmd_parts[0]}"
            print(f"   ❌ {msg}")
            return {"status": "failed", "returncode": None,
                    "duration_s": round(duration, 1), "message": msg}
        except Exception as e:
            duration = (datetime.now() - t0).total_seconds()
            msg = f"爬虫启动异常：{e}"
            print(f"   ❌ {msg}")
            return {"status": "failed", "returncode": None,
                    "duration_s": round(duration, 1), "message": msg}

    def _get_content_dates(self) -> list:
        """获取内容数据(帖子/评论)的可用日期"""
        if not self.data_loader.data_dir:
            return []

        dates = set()
        data_dir = Path(self.data_loader.data_dir)

        for pattern in ['*_contents_*.csv', '*_comments_*.csv']:
            for file in data_dir.glob(pattern):
                match = re.search(r'(\d{4}-\d{2}-\d{2})', file.name)
                if match:
                    dates.add(match.group(1))

        return sorted(list(dates))

    def _get_creator_dates(self) -> list:
        """获取创作者数据的可用日期"""
        if not self.data_loader.data_dir:
            return []

        dates = set()
        data_dir = Path(self.data_loader.data_dir)

        for file in data_dir.glob('*_creators_*.csv'):
            match = re.search(r'(\d{4}-\d{2}-\d{2})', file.name)
            if match:
                dates.add(match.group(1))

        return sorted(list(dates))

    def collect_and_process(self):
        """执行完整的数据采集和处理流程"""

        # Check control file – skip if scheduler is disabled
        control = self._read_control()
        if not control.get("enabled", True):
            print(f"\n[INFO] Scheduler disabled via control file – skipping run.")
            return

        start_time = datetime.now()
        print(f"\n{'=' * 60}")
        print(f"🕒 开始完整流水线 - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 60}")

        # Mark as running
        self._write_status(is_running=True)

        run_record = {
            "start_time": start_time.isoformat(timespec="seconds"),
            "end_time": None,
            "status": "failed",
            "error": None,
            "crawler": None,
            "stats": {},
        }

        try:
            # ── 步骤 0：运行爬虫（若已配置）──────────────────────────────
            crawler_result = self._run_crawler()
            run_record["crawler"] = crawler_result

            # 爬虫失败时根据配置决定是否继续
            if crawler_result["status"] in ("failed", "timeout"):
                if CRAWLER_SKIP_ON_FAILURE:
                    end_time = datetime.now()
                    run_record["end_time"] = end_time.isoformat(timespec="seconds")
                    run_record["status"] = "failed"
                    run_record["error"] = f"爬虫未成功：{crawler_result['message']}"
                    self._write_status(is_running=False, last_run=run_record)
                    print(f"\n⏭️  CRAWLER_SKIP_ON_FAILURE=true，跳过本次分析")
                    return
                else:
                    print(f"\n⚠️  爬虫失败但 CRAWLER_SKIP_ON_FAILURE=false，继续分析")

            # ── 步骤 1：分别获取内容和创作者的可用日期 ──────────────────
            content_dates = self._get_content_dates()
            creator_dates = self._get_creator_dates()

            if not content_dates:
                print("❌ 没有可用的内容数据日期(帖子/评论)")
                return

            latest_content_date = content_dates[-1]
            print(f"\n📅 内容数据日期: {latest_content_date}")
            if creator_dates:
                print(f"📅 创作者数据日期: {creator_dates[-1]}")

            # 2. 加载帖子和评论(使用内容日期)
            print("\n📥 步骤 1/5: 从 MediaCrawler 加载原始数据...")
            df_posts_raw = self.data_loader.load_posts(date=latest_content_date)
            df_comments_raw = self.data_loader.load_comments(date=latest_content_date)

            print(f"   ✅ 帖子: {len(df_posts_raw)} 条")
            print(f"   ✅ 评论: {len(df_comments_raw)} 条")

            if df_posts_raw.empty and df_comments_raw.empty:
                print("❌ 没有新内容数据，跳过本次任务")
                return

            # 3. 加载所有创作者数据(不限制日期)
            print("   👤 加载创作者数据...")
            if creator_dates:
                latest_creator_date = creator_dates[-1]
                print(f"   📅 使用日期: {latest_creator_date}")

                # 尝试两种文件名模式
                df_creators = pd.DataFrame()
                for pattern in ['search_creators_*.csv', 'creator_creators_*.csv']:
                    df_temp = self.data_loader.load_creators(date=latest_creator_date, pattern=pattern)
                    if not df_temp.empty:
                        if df_creators.empty:
                            df_creators = df_temp
                        else:
                            df_creators = pd.concat([df_creators, df_temp], ignore_index=True)

                # 去重
                if not df_creators.empty and 'user_id' in df_creators.columns:
                    before_count = len(df_creators)
                    df_creators = df_creators.drop_duplicates(subset='user_id', keep='last')
                    after_count = len(df_creators)
                    if before_count != after_count:
                        print(f"   📊 去重: {before_count} → {after_count} 条")
            else:
                df_creators = pd.DataFrame()

            if not df_creators.empty:
                print(f"   ✅ 创作者: {len(df_creators)} 条")
            else:
                print("   ⚠️ 没有找到创作者数据")

            # 3.5 加载评论用户数据（新增）
            print("   💬 加载评论用户数据...")
            df_comment_users = pd.DataFrame()

            # 从爬虫目录直接加载 search_comment_users 文件
            comment_users_file = os.path.join(self.data_loader.data_dir,
                                                  f'search_comment_users_{latest_content_date}.csv')
            if os.path.exists(comment_users_file):
                try:
                    df_comment_users = pd.read_csv(
                        comment_users_file,
                        encoding='utf-8-sig',
                        engine='python',  # 使用 Python 引擎，更宽容
                        on_bad_lines='skip'  # 跳过无法解析的行
                    )
                    print(f"   ✅ 加载文件: search_comment_users_{latest_content_date}.csv")

                    # 去重
                    if 'user_id' in df_comment_users.columns:
                        before_count = len(df_comment_users)
                        df_comment_users = df_comment_users.drop_duplicates(subset='user_id', keep='last')
                        after_count = len(df_comment_users)
                        if before_count != after_count:
                            print(f"   📊 去重: {before_count} → {after_count} 条")

                    print(f"   ✅ 评论用户: {len(df_comment_users)} 条")
                except Exception as e:
                    print(f"   ❌ 加载评论用户失败: {e}")
            else:
                print(f"   ⚠️ 未找到评论用户文件: search_comment_users_{latest_content_date}.csv")

            # 4. 清洗帖子数据
            print("\n🧹 步骤 2/5: 清洗帖子数据...")
            df_posts_cleaned = self.preprocessor.process_dataframe(
                df_posts_raw,
                text_column='content',
                filter_ads=True,
                author_column='nickname',
                deduplicate=True,
                dedup_method='semantic'
            )

            posts_output_path = GeneratedFiles.get_posts_cleaned_path()
            df_posts_cleaned.to_csv(posts_output_path, index=False, encoding='utf-8-sig')
            print(f"   ✅ 已保存: {posts_output_path.name} ({len(df_posts_cleaned)} 条)")

            # 5. 清洗评论数据
            print("\n🧹 步骤 3/5: 清洗评论数据...")
            df_comments_cleaned = self.preprocessor.process_dataframe(
                df_comments_raw,
                text_column='content',
                filter_ads=False,
                deduplicate=True,
                dedup_method='exact'
            )

            comments_output_path = GeneratedFiles.get_comments_cleaned_path()
            df_comments_cleaned.to_csv(comments_output_path, index=False, encoding='utf-8-sig')
            print(f"   ✅ 已保存: {comments_output_path.name} ({len(df_comments_cleaned)} 条)")

            # 6. 保存创作者数据
            print("\n👤 步骤 4/5: 处理创作者数据...")
            if not df_creators.empty:
                date_str = datetime.now().strftime('%Y%m%d')
                creators_output = AUTHOR_DIR / f"creators_{date_str}.csv"
                df_creators.to_csv(creators_output, index=False, encoding='utf-8-sig')
                print(f"   ✅ 已保存: {creators_output.name} ({len(df_creators)} 条)")
            else:
                print("   ⚠️ 跳过创作者数据保存")
            # 6.5 保存评论用户数据（新增）
            print("\n💬 步骤 4.5/5: 处理评论用户数据...")
            if not df_comment_users.empty:
                date_str = datetime.now().strftime('%Y%m%d')
                comment_users_output = AUTHOR_DIR / f"comment_users_{date_str}.csv"
                df_comment_users.to_csv(comment_users_output, index=False, encoding='utf-8-sig')
                print(f"   ✅ 已保存: {comment_users_output.name} ({len(df_comment_users)} 条)")
            else:
                print("   ⚠️ 跳过评论用户数据保存")

            # 7. 触发下游分析任务
            print("\n🔄 步骤 5/5: 触发下游分析任务...")

            # 准备用户画像的创作者文件列表(只包含本次新生成的)
            latest_creators = list(AUTHOR_DIR.glob('creators_*.csv'))
            # 排除固定的 creators_01/02/03.csv
            latest_creators = [f for f in latest_creators if not re.match(r'creators_0[1-3]\.csv', f.name)]

            # 按修改时间排序,只保留最新的1个
            if latest_creators:
                latest_creators.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                latest_creators = latest_creators[:1]
                print(f"   📊 用户画像将使用: {latest_creators[0].name}")

            # 新增：准备评论用户文件列表
            latest_comment_users = list(AUTHOR_DIR.glob('comment_users_*.csv'))
            if latest_comment_users:
                latest_comment_users.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                latest_comment_users = latest_comment_users[:1]
                print(f"   📊 用户画像将使用评论用户文件: {latest_comment_users[0].name}")

            # 合并所有用户信息文件（创作者 + 评论用户）
            all_user_files = latest_creators + latest_comment_users

            # 通过环境变量传递文件路径
            creators_env = ';'.join(str(f) for f in all_user_files) if all_user_files else ''
            env = os.environ.copy()
            env['CREATORS_FILES'] = creators_env
            print(f"   📤 传递 {len(all_user_files)} 个用户文件给下游任务")
            self._trigger_downstream_tasks(env)

            # Mark run as successful
            end_time = datetime.now()
            run_record["end_time"] = end_time.isoformat(timespec="seconds")
            run_record["status"] = "success"
            run_record["stats"] = {
                "posts_raw": len(df_posts_raw),
                "comments_raw": len(df_comments_raw),
                "posts_cleaned": len(df_posts_cleaned),
                "comments_cleaned": len(df_comments_cleaned),
            }
            self._write_status(is_running=False, last_run=run_record)

        except Exception as e:
            print(f"\n❌ 数据采集失败: {e}")
            import traceback
            traceback.print_exc()

            end_time = datetime.now()
            run_record["end_time"] = end_time.isoformat(timespec="seconds")
            run_record["status"] = "failed"
            run_record["error"] = str(e)
            self._write_status(is_running=False, last_run=run_record)

    def _trigger_downstream_tasks(self, env=None):
        """触发下游分析任务(BERTopic + 情感分析并行 + 用户画像)"""
        project_root = Path(__file__).parent.parent

        if env is None:
            env = os.environ.copy()

        today_str = datetime.now().strftime('%Y%m%d')

        # 6.1 BERTopic：若今日输出已存在则跳过，否则以非阻塞方式启动
        bertopic_script = project_root / "data_collector" / "analysis" / "run_bertopic.py"
        bertopic_proc = None

        existing_topic = DynamicFileManager.get_latest_bertopic_topics()
        if existing_topic and today_str in existing_topic.name:
            print(f"   [SKIP] 今日 BERTopic 输出已存在: {existing_topic.name}，跳过重训练")
        elif bertopic_script.exists():
            print("   [START] 5.1 BERTopic 主题分析（后台启动）...")
            bertopic_proc = subprocess.Popen(
                [sys.executable, str(bertopic_script)],
                cwd=str(project_root),
                env=env
            )
        else:
            print(f"   [WARN] BERTopic 脚本不存在: {bertopic_script}")

        # 6.1.5 情感分析（与 BERTopic 并行执行）
        print("   [START] 5.1.5 情感预测（与 BERTopic 并行）...")
        sentiment_ok = False
        try:
            from data_collector.model.predict import process_file

            posts_file = DynamicFileManager.get_latest_posts_cleaned()
            if posts_file:
                match = re.search(r'(\d{8})', posts_file.name)
                date_str = match.group(1) if match else today_str
                output_file = SENTIMENT_DATA_DIR / f"posts_model_{date_str}.csv"

                if not output_file.exists():
                    print(f"      [RUN] 执行情感预测: {posts_file.name}")
                    success = process_file(posts_file, output_file, "posts")
                    if not success:
                        print("      [WARN] 情感预测失败")
                    else:
                        sentiment_ok = True
                else:
                    print(f"      [SKIP] 情感文件已存在: {output_file.name}")
                    sentiment_ok = True
            else:
                print("      [WARN] 未找到帖子文件，跳过情感分析")
        except Exception as e:
            print(f"      [WARN] 情感分析失败: {e}")
            import traceback
            traceback.print_exc()

        # 等待 BERTopic 完成（最多 30 分钟）
        if bertopic_proc is not None:
            print("   [WAIT] 等待 BERTopic 完成...")
            try:
                bertopic_proc.wait(timeout=1800)
                if bertopic_proc.returncode == 0:
                    topics_file = DynamicFileManager.get_latest_bertopic_topics()
                    if topics_file:
                        print(f"   [OK] BERTopic 完成 -> {topics_file.name}")
                    else:
                        print("   [WARN] BERTopic 执行成功但未找到输出文件")
                else:
                    print(f"   [FAIL] BERTopic 失败 (退出码: {bertopic_proc.returncode})")
            except subprocess.TimeoutExpired:
                bertopic_proc.kill()
                print("   [FAIL] BERTopic 超时 (30min)，已终止")

        # 数据合并（BERTopic + 情感均完成后执行）
        try:
            posts_file = DynamicFileManager.get_latest_posts_cleaned()
            if posts_file and sentiment_ok:
                print("      [RUN] 生成合并文件...")
                merged_files = DynamicFileManager.merge_all_posts_with_sentiment_and_topic()
                if merged_files:
                    print(f"      [OK] 合并完成: {merged_files[-1].name}")
                    df_check = pd.read_csv(merged_files[-1], encoding='utf-8-sig')
                    sent_count = df_check['sentiment'].notna().sum() if 'sentiment' in df_check.columns else 0
                    print(f"      [STAT] {len(df_check)} 条, 含情感: {sent_count}")
                else:
                    print("      [WARN] 合并失败")
        except Exception as e:
            print(f"      [WARN] 合并失败: {e}")
            import traceback
            traceback.print_exc()

        # 6.2 运行用户画像提取
        print("   👤 5.2 启动用户画像提取...")
        user_char_script = project_root / "user_characters" / "advanced_extractor.py"

        if user_char_script.exists():
            result = subprocess.run(
                [sys.executable, str(user_char_script)],
                cwd=str(project_root),
                timeout=3600,
                env=env
            )

            if result.returncode == 0:
                user_stats_files = DynamicFileManager.get_all_user_stats_files()
                if user_stats_files:
                    latest_file = user_stats_files[0]
                    print(f"   ✅ 用户画像完成 → {latest_file.name}")

                    try:
                        df_stats = pd.read_csv(latest_file, encoding='utf-8-sig')
                        print(f"   📊 生成 {len(df_stats)} 个用户画像")
                    except Exception as e:
                        print(f"   ⚠️ 读取统计文件失败: {e}")
                else:
                    print("   ⚠️ 用户画像执行成功但未找到输出文件")
            else:
                print(f"   ❌ 用户画像失败 (退出码: {result.returncode})")
        else:
            print(f"   ⚠️ 用户画像脚本不存在: {user_char_script}")

        # 6.3 动态主题建模（DTM）
        print("\n🌊 5.3 动态主题演化建模...")
        dtm_script = project_root / "data_collector" / "analysis" / "run_dynamic_topic.py"
        if dtm_script.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(dtm_script)],
                    cwd=str(project_root),
                    timeout=1800,
                    env=env,
                )
                if result.returncode == 0:
                    print("   [OK] DTM 完成")
                else:
                    print(f"   [FAIL] DTM 失败 (退出码: {result.returncode})")
            except subprocess.TimeoutExpired:
                print("   [FAIL] DTM 超时 (30min)")
            except Exception as e:
                print(f"   [WARN] DTM 执行异常: {e}")
        else:
            print(f"   [WARN] DTM 脚本不存在: {dtm_script}")

        self._sync_to_database_and_refresh_cache()

    def _sync_to_database_and_refresh_cache(self):
        """将最新 CSV 同步到 SQLite 并刷新 API 缓存"""
        print("\n💾 同步数据到 SQLite ...")
        try:
            from config.config import USE_DATABASE

            if not USE_DATABASE:
                print("   ⏭️ USE_DATABASE=false，跳过数据库同步")
                return

            from backend.services.db_sync import sync_all_from_csv

            stats = sync_all_from_csv(clear_comments=True)
            print(f"   ✅ 同步完成: posts={stats['posts']}, comments={stats['comments']}, user_stats={stats['user_stats']}")

            try:
                from backend.api.main import data_loader

                data_loader._db_available = None
                data_loader.invalidate_all_cache()
                print("   ✅ API 缓存已刷新")
            except Exception as cache_err:
                print(f"   ⚠️ 缓存刷新失败: {cache_err}")
        except Exception as e:
            print(f"   ⚠️ 数据库同步失败（CSV 仍可用）: {e}")

    def run_scheduler(self):
        """
        运行定时任务

        默认在每天 12:00 和 21:00 执行采集流程。
        若环境变量 COLLECT_INTERVAL_HOURS 被设置为非零整数，则额外按该间隔（小时）触发一次。
        """
        print(f"🚀 启动定时任务调度器")
        print(f"⏰ 采集时间: 每日 12:00 / 21:00")
        print(f"📂 数据源: {MEDIA_CRAWLER_DATA_DIR}")
        print(f"📋 流程: 采集 → 清洗 → BERTopic → 用户画像\n")

        # 立即执行一次
        self.collect_and_process()

        # 固定时间触发（12:00 和 21:00）
        schedule.every().day.at("12:00").do(self.collect_and_process).tag("pipeline")
        schedule.every().day.at("21:00").do(self.collect_and_process).tag("pipeline")

        # 可选：若设置了 COLLECT_INTERVAL_HOURS（且非零），按小时间隔额外触发
        interval_hours = int(os.getenv('COLLECT_INTERVAL_HOURS', '0'))
        if interval_hours > 0:
            print(f"⏰ 额外间隔: 每 {interval_hours} 小时触发一次")
            schedule.every(interval_hours).hours.do(self.collect_and_process).tag("pipeline")

        # 每日凌晨 3 点额外执行一次数据库同步（防止仅手动跑过 CSV 未入库）
        schedule.every().day.at("03:00").do(self._sync_to_database_and_refresh_cache).tag("db_sync")

        # 持续运行：缩短轮询间隔，任务触发更及时
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)
        except KeyboardInterrupt:
            print("\n⏹️  定时任务已停止")


def main():
    """主函数"""
    scheduler = DataCollectorScheduler()
    scheduler.run_scheduler()


if __name__ == "__main__":
    main()
