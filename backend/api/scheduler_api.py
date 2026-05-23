import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from config.config import MEDIA_CRAWLER_DATA_DIR
from backend.models.schemas import Response

router = APIRouter()

PROJECT_ROOT = Path(__file__).parents[2]
STATUS_FILE = PROJECT_ROOT / "data" / "scheduler_status.json"
CONTROL_FILE = PROJECT_ROOT / "data" / "scheduler_control.json"


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

    # Verify whether the pid in the status file is actually alive
    pid = status.get("pid")
    if status.get("is_running") and pid is not None:
        if not _is_pid_alive(pid):
            status["is_running"] = False

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

    # Sort by mtime descending, keep last 10
    files.sort(key=lambda x: x["mtime"], reverse=True)
    files = files[:10]

    return {"status": "ok", "data": files}


@router.post("/trigger")
async def trigger_manual():
    """请求手动触发一次调度任务"""
    control = _read_json(CONTROL_FILE, {"enabled": True, "trigger_manual": False})
    control["trigger_manual"] = True
    _write_json(CONTROL_FILE, control)
    return {"status": "ok", "message": "已请求手动触发，调度器将在下次轮询时执行"}


@router.post("/toggle-enabled")
async def toggle_enabled():
    """切换调度器启用/禁用状态"""
    control = _read_json(CONTROL_FILE, {"enabled": True, "trigger_manual": False})
    control["enabled"] = not control.get("enabled", True)
    _write_json(CONTROL_FILE, control)
    return {"status": "ok", "enabled": control["enabled"]}
