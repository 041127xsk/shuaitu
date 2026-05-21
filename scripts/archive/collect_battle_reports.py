"""
collect_battle_reports.py - 率土之滨战报自动滚动采集
===================================================
通过 ADB 连接 MuMu 模拟器，自动截图 + 滚动 + OCR + 存入数据库。

用法：
    python scripts/collect_battle_reports.py --season 5607 --until "2026/05/03 20:00:00"
    python scripts/collect_battle_reports.py --season 5607 --max-pages 10
    python scripts/collect_battle_reports.py --season 5607 --once
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ocr_paddle import GameOCR
from src.report_parser import BattleReportParser
from src.database import init_db, upsert_crawl_state


SCREENSHOTS_DIR = ROOT / "data" / "screenshots" / "battle_reports"


def find_adb() -> str:
    """查找 ADB 路径"""
    for root, dirs, files in os.walk("F:\\"):
        if "adb.exe" in files and "YXShuaiTu" in root:
            return os.path.join(root, "adb.exe")
    raise FileNotFoundError("ADB not found")


def screenshot(adb: str, serial: str, name: str) -> str:
    """截图并拉取到本地"""
    remote = f"/sdcard/{name}.png"
    local = str(SCREENSHOTS_DIR / f"{name}.png")
    subprocess.run([adb, "-s", serial, "shell", "screencap", "-p", remote], capture_output=True)
    subprocess.run([adb, "-s", serial, "pull", remote, local], capture_output=True)
    return local


def swipe(adb: str, serial: str, x: int, y1: int, y2: int, duration: int = 400):
    """模拟滑动"""
    subprocess.run([adb, "-s", serial, "shell", "input", "swipe",
                    str(x), str(y1), str(x), str(y2), str(duration)], capture_output=True)


def parse_timestamp(ts: str) -> datetime | None:
    """解析时间戳"""
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d%H:%M:%S"):
        try:
            return datetime.strptime(ts.strip(), fmt)
        except ValueError:
            continue
    return None


def collect_page(
    ocr: GameOCR,
    parser: BattleReportParser,
    image_path: str,
) -> list[dict]:
    """识别单页战报"""
    result = ocr.recognize(image_path)
    reports = parser.parse(result)
    return [r.to_dict() for r in reports]


def main() -> int:
    parser = argparse.ArgumentParser(description="率土之滨战报自动滚动采集")
    parser.add_argument("--season", default="5607", help="赛季标识")
    parser.add_argument("--until", default="", help="采集到此时间之前停止 (格式: 2026/05/03 20:00:00)")
    parser.add_argument("--max-pages", type=int, default=50, help="最多采集页数")
    parser.add_argument("--once", action="store_true", help="只采集当前页，不滚动")
    parser.add_argument("--scroll-distance", type=int, default=450, help="每次滚动距离(px)")
    parser.add_argument("--scroll-delay", type=float, default=1.5, help="滚动后等待秒数")
    parser.add_argument("--db", default=str(ROOT / "data" / "heroes.db"), help="数据库路径")
    parser.add_argument("--serial", default="127.0.0.1:16384", help="ADB 设备地址")
    args = parser.parse_args()

    # 初始化
    print(f"连接模拟器 {args.serial} ...")
    adb = find_adb()
    print(f"ADB: {adb}")

    print("初始化 OCR 引擎 ...")
    ocr = GameOCR()
    report_parser = BattleReportParser(season=args.season)

    conn = init_db(args.db)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    until_time = parse_timestamp(args.until) if args.until else None
    print(f"赛季: {args.season}")
    print(f"停止时间: {until_time or '不限制'}")
    print(f"最大页数: {args.max_pages}")
    print()

    all_reports = []
    # 去重：相同玩家 + 相同队伍不重复入库
    # key = (player_a, player_b, tuple(sorted(heroes_a)), tuple(sorted(heroes_b)))
    seen_teams = set()

    for page in range(1, args.max_pages + 1):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"--- Page {page} [{ts}] ---")

        # 截图
        image_path = screenshot(adb, args.serial, f"report_p{page}_{ts}")

        # OCR + 解析
        reports = collect_page(ocr, report_parser, image_path)

        new_count = 0
        for r in reports:
            # 去重：相同玩家 + 相同队伍
            heroes_a = tuple(sorted(r.get("heroes_a", [])))
            heroes_b = tuple(sorted(r.get("heroes_b", [])))
            team_key = (r.get("player_a", ""), r.get("player_b", ""), heroes_a, heroes_b)
            if team_key in seen_teams:
                continue
            seen_teams.add(team_key)

            # 检查时间戳是否早于停止时间
            if until_time and r.get("timestamp"):
                report_time = parse_timestamp(r["timestamp"])
                if report_time and report_time < until_time:
                    print(f"  [STOP] 时间 {r['timestamp']} 早于截止时间 {until_time}")
                    _save_reports(conn, all_reports, args.season)
                    conn.close()
                    print(f"\n采集完成，共 {len(all_reports)} 条战报。")
                    return 0

            all_reports.append(r)
            new_count += 1

            result_icon = {"win": "胜", "loss": "负", "draw": "平"}.get(r.get("result", ""), "?")
            heroes_a_str = "、".join(r.get("heroes_a", [])) or "-"
            heroes_b_str = "、".join(r.get("heroes_b", [])) or "-"
            print(f"  [{result_icon}] {r.get('player_a','')} ({heroes_a_str}) vs {r.get('player_b','')} ({heroes_b_str}) {r.get('timestamp','')}")

        if new_count == 0:
            print("  [SKIP] 无新战报")

        # 单页模式不滚动
        if args.once:
            break

        # 滚动到下一页
        print(f"  滚动 {args.scroll_distance}px ...")
        swipe(adb, args.serial, 540, 850, 850 - args.scroll_distance, 400)
        time.sleep(args.scroll_delay)

    # 存库
    _save_reports(conn, all_reports, args.season)
    conn.close()

    print(f"\n采集完成，共 {len(all_reports)} 条战报。")
    return 0


def _save_reports(conn, reports: list[dict], season: str):
    """将战报存入数据库"""
    for r in reports:
        feed_id = f"battle_{r.get('timestamp','').replace('/','').replace(':','').replace(' ','')}_{hash(str(r)) % 10000:04d}"
        upsert_crawl_state(
            conn,
            feed_id=feed_id,
            hero_name=r.get("player_a", "unknown"),
            article_url="",
            status="done",
        )
    print(f"  [DB] 已存入 {len(reports)} 条战报")


if __name__ == "__main__":
    raise SystemExit(main())
