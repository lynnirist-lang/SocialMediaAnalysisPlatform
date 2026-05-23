import json
import os
import sys
import threading
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from config.config import MEDIA_CRAWLER_DATA_DIR
from backend.models.schemas import Response

router = APIRouter()

PROJECT_ROOT = Path(__file__).parents[2]
STATUS_FILE = PROJECT_ROOT / "data" / "scheduler_status.json"
CONTROL_FILE = PROJECT_ROOT / "data" / "scheduler_control.json"

# 调度器固定执行时间
_SCHEDULED_HOURS = [12, 21]

# 防止并发手动触发
_trigger_lock = threading.Lock()
_trigger_running = False


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _is_pid_alive(pid: Optional[int]) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _compute_next_scheduled() -> List[str]:
    """根据固定的 12:00/21:00 计划计算最近两个执行时间点（ISO 字符串）。"""
    now = datetime.now()
    result = []
    for h in _SCHEDULED_HOURS:
        candidate = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        result.append(candidate.isoformat(timespec="seconds"))
    return sorted(result)


@router.get("/status")
async def get_scheduler_status():
    """获取调度器运行状态"""
    default_status = {
        "is_running": False,
        "pid": None,
        "last_run": None,
        "next_scheduled": [],
        "history": [],
    }
    status = _read_json(STATUS_FILE, default_status)

    # 校验 PID 存活
    pid = status.get("pid")
    if status.get("is_running") and pid is not None:
        if not _is_pid_alive(pid):
            status["is_running"] = False

    # 补全下次计划（调度器进程不在时也能正常显示）
    if not status.get("next_scheduled"):
        status["next_scheduled"] = _compute_next_scheduled()

    # 读取启用状态
    control = _read_json(CONTROL_FILE, {"enabled": True})
    status["enabled"] = control.get("enabled", True)

    return {"status": "ok", "data": status}


@router.get("/crawler-files")
async def get_crawler_files():
    """获取 MediaCrawler 最近写入的数据文件列表"""
    crawler_dir = Path(MEDIA_CRAWLER_DATA_DIR)
    if not crawler_dir.exists():
        return {"status": "ok", "data": [], "message": f"目录不存在: {crawler_dir}"}

    files: List[Dict[str, Any]] = []
    try:
        for entry in crawler_dir.iterdir():
            if entry.is_file():
                stat = entry.stat()
                files.append({
                    "filename": entry.name,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "size": stat.st_size,
                })
    except Exception as e:
        return {"status": "error", "data": [], "message": str(e)}

    files.sort(key=lambda x: x["mtime"], reverse=True)
    return {"status": "ok", "data": files[:10]}


def _run_collect_in_background():
    """在后台线程中执行一次完整的数据采集流水线。"""
    global _trigger_running
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from data_collector.scheduler import DataCollectorScheduler
        scheduler = DataCollectorScheduler()
        scheduler.collect_and_process()
    except Exception as e:
        print(f"[ERROR] 手动触发执行失败: {e}")
    finally:
        _trigger_running = False


@router.post("/trigger")
async def trigger_manual():
    """立即在后台线程执行一次数据采集流水线。"""
    global _trigger_running

    # 检查调度器进程是否已在运行
    status = _read_json(STATUS_FILE, {})
    if status.get("is_running") and _is_pid_alive(status.get("pid")):
        raise HTTPException(status_code=409, detail="调度器正在运行中，请稍后再试")

    with _trigger_lock:
        if _trigger_running:
            raise HTTPException(status_code=409, detail="已有手动触发任务正在执行，请稍后再试")
        _trigger_running = True

    t = threading.Thread(target=_run_collect_in_background, daemon=True)
    t.start()
    return {"status": "ok", "message": "已开始执行，请关注任务状态变化"}


@router.post("/toggle-enabled")
async def toggle_enabled():
    """切换调度器启用/禁用状态"""
    control = _read_json(CONTROL_FILE, {"enabled": True, "trigger_manual": False})
    control["enabled"] = not control.get("enabled", True)
    _write_json(CONTROL_FILE, control)
    return {"status": "ok", "enabled": control["enabled"]}
