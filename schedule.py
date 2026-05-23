from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Optional, Dict
import asyncio
import os
import subprocess
from pathlib import Path
from tools import utils


class WeiboHotSearchScheduler:
    """微博热搜定时爬取调度器"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.job_id = "weibo_hot_search_daily"
        self.project_root = Path(__file__).parent.parent.parent

    async def _fetch_hot_search_and_crawl(self):
        """执行完整的微博热搜爬取流程"""
        try:
            utils.logger.info("[Scheduler] ===== 开始执行微博热搜定时任务 =====")

            # Step 1: 获取热搜关键词并保存到文件
            utils.logger.info("[Scheduler] Step 1/3: 获取微博热搜关键词...")
            from tools.get_weibo_hot_search import WeiboHotSearchCrawler
            from datetime import datetime
            import glob

            crawler = WeiboHotSearchCrawler()
            keywords = await crawler.get_hot_keywords()

            if not keywords:
                utils.logger.warning("[Scheduler] 未获取到热搜关键词，使用默认关键词")
                keywords = ["热点", "新闻", "社会"]

            # 清理旧的关键词文件，只保留当天的
            timestamp = datetime.now().strftime("%Y-%m-%d")
            old_files = glob.glob(os.path.join(crawler.hot_words_dir, "hot_keywords_*.txt"))
            for old_file in old_files:
                if timestamp not in old_file:
                    try:
                        os.remove(old_file)
                        utils.logger.info(f"[Scheduler] 删除旧文件: {old_file}")
                    except Exception as e:
                        utils.logger.warning(f"[Scheduler] 删除文件失败: {e}")

            # 保存到文件
            filename = f"hot_keywords_{timestamp}.txt"
            out_path = os.path.join(crawler.hot_words_dir, filename)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(keywords))

            utils.logger.info(f"[Scheduler] ✓ 获取到 {len(keywords)} 个热搜关键词")
            # Step 2: 运行主爬虫（自动读取热搜关键词文件）
            utils.logger.info("[Scheduler] Step 2/3: 爬取热搜帖子和评论...")
            import config
            config.KEYWORDS_FILE = "data/words/hot_words"
            config.PLATFORM = "wb"
            config.CRAWLER_TYPE = "search"

            from main import main as crawler_main
            await crawler_main()

            utils.logger.info("[Scheduler] ✓ 爬取帖子和评论完成")

            # 强制关闭所有 Chrome 进程，释放 CDP 端口
            utils.logger.info("[Scheduler] 强制关闭浏览器进程...")
            import subprocess
            try:
                # Windows: 关闭所有 chrome.exe 进程
                subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                               capture_output=True, timeout=5)
                await asyncio.sleep(3)
                utils.logger.info("[Scheduler] ✓ 浏览器进程已清理")
            except Exception as e:
                utils.logger.warning(f"[Scheduler] 清理浏览器进程失败: {e}")

            # Step 3: 获取发帖人信息（复用已登录状态）
            utils.logger.info("[Scheduler] Step 3/3: 获取发帖人信息...")
            from media_platform.weibo.fetch_poster_info import fetch_and_save_creator_info

            await fetch_and_save_creator_info()

            utils.logger.info("[Scheduler] ✓ 获取发帖人信息完成")

            # 强制关闭所有 Chrome 进程，释放 CDP 端口
            utils.logger.info("[Scheduler] 强制关闭浏览器进程...")
            import subprocess
            try:
                # Windows: 关闭所有 chrome.exe 进程
                subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                               capture_output=True, timeout=5)
                await asyncio.sleep(3)
                utils.logger.info("[Scheduler] ✓ 浏览器进程已清理")
            except Exception as e:
                utils.logger.warning(f"[Scheduler] 清理浏览器进程失败: {e}")

            # Step 4: 获取评论用户信息（新增）
            utils.logger.info("[Scheduler] Step 4/4: 获取评论用户信息...")
            from media_platform.weibo.fetch_comment_user_info import fetch_and_save_comment_user_info

            await fetch_and_save_comment_user_info(None)

            utils.logger.info("[Scheduler] ✓ 获取评论用户信息完成")

            utils.logger.info("[Scheduler] ===== 微博热搜定时任务全部完成 =====")

        except Exception as e:
            utils.logger.error(f"[Scheduler] 定时任务执行失败: {e}", exc_info=True)

    async def _run_command(self, cmd: list, description: str):
        """执行命令并等待完成

        Args:
            cmd: 命令列表
            description: 任务描述（用于日志）
        """
        try:
            utils.logger.info(f"[Scheduler] 执行: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root)
            )

            # 实时输出日志
            async def read_stream(stream, prefix):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode('utf-8', errors='ignore').strip()
                    if text:
                        utils.logger.info(f"[{prefix}] {text}")

            # 并行读取stdout和stderr
            await asyncio.gather(
                read_stream(process.stdout, description),
                read_stream(process.stderr, description)
            )

            # 等待进程结束
            returncode = await process.wait()

            if returncode != 0:
                raise RuntimeError(f"命令执行失败，返回码: {returncode}")

            utils.logger.info(f"[Scheduler] ✓ {description} 完成")

        except Exception as e:
            utils.logger.error(f"[Scheduler] ✗ {description} 失败: {e}")
            raise

    def start(self, hour: int = 12, minute: int = 0):
        """启动调度器

        Args:
            hour: 执行小时 (默认12点)
            minute: 执行分钟 (默认0分)
        """
        if self.is_running:
            utils.logger.warning("[Scheduler] 调度器已在运行")
            return

        # 添加每天定时任务
        self.scheduler.add_job(
            self._fetch_hot_search_and_crawl,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=self.job_id,
            name='微博热搜每日爬取',
            misfire_grace_time=3600,  # 错过1小时内仍可执行
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True
        utils.logger.info(f"[Scheduler] 调度器已启动: 每天 {hour:02d}:{minute:02d} 执行")

    def stop(self):
        """停止调度器"""
        if not self.is_running:
            utils.logger.warning("[Scheduler] 调度器未在运行")
            return

        self.scheduler.shutdown(wait=False)
        self.is_running = False
        utils.logger.info("[Scheduler] 调度器已停止")

    def enable_job(self):
        """启用定时任务"""
        if self.scheduler.get_job(self.job_id):
            self.scheduler.resume_job(self.job_id)
            utils.logger.info("[Scheduler] 定时任务已启用")
            return True
        return False

    def disable_job(self):
        """禁用定时任务"""
        if self.scheduler.get_job(self.job_id):
            self.scheduler.pause_job(self.job_id)
            utils.logger.info("[Scheduler] 定时任务已禁用")
            return True
        return False

    def get_status(self) -> Dict:
        """获取调度器状态"""
        job = self.scheduler.get_job(self.job_id)
        return {
            "is_running": self.is_running,
            "job_exists": job is not None,
            "job_paused": job.next_run_time is None if job else False,
            "next_run_time": str(job.next_run_time) if job and job.next_run_time else None,
            "schedule": "每天 12:00"
        }


# 全局实例
weibo_scheduler = WeiboHotSearchScheduler()


if __name__ == "__main__":
    """直接运行时立即执行一次任务"""
    utils.logger.info("[Scheduler] 检测到直接运行模式，立即执行一次任务...")
    asyncio.run(weibo_scheduler._fetch_hot_search_and_crawl())
    utils.logger.info("[Scheduler] 任务执行完毕")
