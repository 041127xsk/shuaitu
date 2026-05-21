"""
server.py - 率土之滨战报采集 API 服务
======================================
本地 Web API，可随时调用采集战报。

启动：
    python scripts/server.py
    python scripts/server.py --port 8080

API 端点：
    POST /collect          启动采集任务
    GET  /status            查看采集状态
    GET  /reports           查看已采集战报
    GET  /reports/export    导出战报 JSON
    POST /screenshot        截图并识别当前页面
    GET  /health            健康检查
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ocr_paddle import GameOCR
from src.report_parser import BattleReportParser
from src.database import init_db, upsert_crawl_state

app = FastAPI(title="率土之滨战报采集 API", version="1.0.0")

# 全局状态
_state = {
    "collecting": False,
    "last_collect_time": None,
    "total_reports": 0,
    "current_page": 0,
    "error": None,
}
_reports: list[dict] = []
_lock = threading.Lock()


def find_adb() -> str:
    for root, dirs, files in os.walk("F:\\"):
        if "adb.exe" in files and "YXShuaiTu" in root:
            return os.path.join(root, "adb.exe")
    raise FileNotFoundError("ADB not found")


def screenshot(adb: str, serial: str, name: str) -> str:
    remote = f"/sdcard/{name}.png"
    local = str(ROOT / "data" / "screenshots" / f"{name}.png")
    os.makedirs(os.path.dirname(local), exist_ok=True)
    subprocess.run([adb, "-s", serial, "shell", "screencap", "-p", remote], capture_output=True)
    subprocess.run([adb, "-s", serial, "pull", remote, local], capture_output=True)
    return local


def swipe(adb: str, serial: str, distance: int = 450):
    subprocess.run([adb, "-s", serial, "shell", "input", "swipe",
                    "540", "850", "540", str(850 - distance), "400"], capture_output=True)


def parse_timestamp(ts: str) -> Optional[datetime]:
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d%H:%M:%S"):
        try:
            return datetime.strptime(ts.strip(), fmt)
        except ValueError:
            continue
    return None


# ==================== API Models ====================

class CollectRequest(BaseModel):
    season: str = "5607"
    until: str = ""  # "2026/05/01 00:00:00"
    max_pages: int = 50
    scroll_distance: int = 450
    scroll_delay: float = 1.5


class ScreenshotRequest(BaseModel):
    season: str = "5607"


# ==================== API Endpoints ====================

@app.get("/health")
def health():
    """健康检查"""
    try:
        adb = find_adb()
        adb_ok = os.path.exists(adb)
    except Exception:
        adb_ok = False
    return {"status": "ok", "adb": adb_ok, "collecting": _state["collecting"]}


@app.post("/collect")
def start_collect(req: CollectRequest, background_tasks: BackgroundTasks):
    """启动采集任务（后台运行）"""
    if _state["collecting"]:
        raise HTTPException(409, "采集任务正在运行中")

    _state["collecting"] = True
    _state["error"] = None
    _state["current_page"] = 0

    background_tasks.add_task(_collect_task, req)
    return {"message": "采集任务已启动", "params": req.dict()}


@app.get("/status")
def get_status():
    """查看采集状态"""
    return _state


@app.get("/reports")
def get_reports(limit: int = 100, offset: int = 0):
    """查看已采集战报"""
    with _lock:
        total = len(_reports)
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "reports": _reports[offset:offset + limit],
        }


@app.get("/reports/export")
def export_reports():
    """导出所有战报为 JSON"""
    return {
        "count": len(_reports),
        "reports": _reports,
        "exported_at": datetime.now().isoformat(),
    }


@app.post("/screenshot")
def take_screenshot(req: ScreenshotRequest):
    """截图并识别当前页面"""
    try:
        adb = find_adb()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = screenshot(adb, "127.0.0.1:16384", f"manual_{ts}")

        ocr = GameOCR()
        parser = BattleReportParser(season=req.season)
        result = ocr.recognize(image_path)
        reports = parser.parse(result)

        report_dicts = [r.to_dict() for r in reports]

        with _lock:
            _reports.extend(report_dicts)

        return {
            "image": image_path,
            "blocks": len(result.blocks),
            "reports": report_dicts,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ==================== Background Task ====================

def _collect_task(req: CollectRequest):
    """后台采集任务"""
    global _reports
    try:
        adb = find_adb()
        serial = "127.0.0.1:16384"
        ocr = GameOCR()
        parser = BattleReportParser(season=req.season)
        conn = init_db(str(ROOT / "data" / "heroes.db"))

        until_time = parse_timestamp(req.until) if req.until else None
        seen_teams = set()
        new_reports = []

        for page in range(1, req.max_pages + 1):
            if not _state["collecting"]:
                break

            _state["current_page"] = page
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = screenshot(adb, serial, f"collect_p{page}_{ts}")

            result = ocr.recognize(image_path)
            reports = parser.parse(result)

            for r in reports:
                r_dict = r.to_dict()

                # 去重：相同玩家 + 相同队伍
                heroes_a = tuple(sorted(r_dict.get("heroes_a", [])))
                heroes_b = tuple(sorted(r_dict.get("heroes_b", [])))
                team_key = (r_dict.get("player_a", ""), r_dict.get("player_b", ""), heroes_a, heroes_b)
                if team_key in seen_teams:
                    continue
                seen_teams.add(team_key)

                # 检查截止时间
                if until_time and r_dict.get("timestamp"):
                    report_time = parse_timestamp(r_dict["timestamp"])
                    if report_time and report_time < until_time:
                        _state["collecting"] = False
                        break

                new_reports.append(r_dict)

                # 存库
                feed_id = f"battle_{r_dict.get('timestamp','').replace('/','').replace(':','').replace(' ','')}_{hash(str(r_dict)) % 10000:04d}"
                upsert_crawl_state(conn, feed_id=feed_id, hero_name=r_dict.get("player_a", "unknown"), status="done")

            # 实时更新进度
            with _lock:
                _reports.extend(new_reports)
                _state["total_reports"] = len(_reports)
            new_reports = []

            if not _state["collecting"]:
                break

            # 滚动
            swipe(adb, serial, req.scroll_distance)
            time.sleep(req.scroll_delay)

        conn.close()

        _state["last_collect_time"] = datetime.now().isoformat()

    except Exception as e:
        _state["error"] = str(e)
    finally:
        _state["collecting"] = False


# ==================== Main ====================

if __name__ == "__main__":
    import uvicorn
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"启动采集 API 服务: http://127.0.0.1:{port}")
    print(f"API 文档: http://127.0.0.1:{port}/docs")
    uvicorn.run(app, host="127.0.0.1", port=port)
