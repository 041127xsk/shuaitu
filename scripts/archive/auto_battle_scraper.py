"""
自动翻页抓包脚本
================
全自动流程：设置代理 → 启动 mitmdump → adb 翻页 → 恢复代理 → 解析结果

用法:
    py scripts/auto_battle_scraper.py
"""
import subprocess
import time
import json
import sys
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
MITMDUMP = Path("C:/Users/27557/AppData/Local/Programs/Python/Python312/Scripts/mitmdump.exe")
ADB = Path("C:/Users/27557/.local/bin/platform-tools/adb.exe")
ADB_DEVICE = "127.0.0.1:16384"

# 模拟器访问宿主机的地址（MuMu 标准）
# 如果 10.0.2.2 不通，改为电脑实际局域网 IP
PROXY_HOST = os.getenv("PROXY_HOST", "10.0.2.2")
PROXY_PORT = 8090

OUTPUT_DIR = ROOT / "data" / "captures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
FLOW_FILE = OUTPUT_DIR / f"battle_{TIMESTAMP}.mitm"
TEXT_LOG = OUTPUT_DIR / f"battle_{TIMESTAMP}.txt"
SUMMARY_JSON = OUTPUT_DIR / f"battle_{TIMESTAMP}.json"

# 屏幕参数：横屏 1920x1080 (SurfaceOrientation: 1)
# 战报列表在屏幕中间，向下滑动查看更多
SWIPE_X = 960         # 屏幕中间 (1920/2)
SWIPE_Y_START = 850   # 滑动起点（列表底部）
SWIPE_Y_END = 450     # 滑动终点（列表顶部）
SWIPE_DURATION = 400  # 滑动持续时间(ms)


def adb(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(ADB), "-s", ADB_DEVICE] + cmd,
        capture_output=True,
        text=True,
    )


def set_proxy():
    print("[1] 设置模拟器代理...")
    r = adb(["shell", "settings", "put", "global", "http_proxy", f"{PROXY_HOST}:{PROXY_PORT}"])
    if r.returncode != 0:
        print(f"[!] 设置代理警告: {r.stderr}")
    print(f"    代理: {PROXY_HOST}:{PROXY_PORT}")


def clear_proxy():
    print("[6] 清除模拟器代理...")
    adb(["shell", "settings", "put", "global", "http_proxy", ":0"])
    adb(["shell", "settings", "delete", "global", "http_proxy"])


def swipe_up():
    adb([
        "shell", "input", "swipe",
        str(SWIPE_X), str(SWIPE_Y_START),
        str(SWIPE_X), str(SWIPE_Y_END),
        str(SWIPE_DURATION),
    ])


def tap(x: int, y: int):
    adb(["shell", "input", "tap", str(x), str(y)])


def start_mitmdump():
    print(f"[2] 启动 mitmdump...")
    print(f"    保存到: {FLOW_FILE}")

    # 同时输出文本日志和 mitm 流文件
    proc = subprocess.Popen(
        [
            str(MITMDUMP),
            "-p", str(PROXY_PORT),
            "--ssl-insecure",
            "-w", str(FLOW_FILE),
            "--flow-detail", "2",
        ],
        stdout=open(str(TEXT_LOG), "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(2)
    print(f"[OK] mitmdump PID={proc.pid}")
    return proc


def do_swipes(count: int = 15, interval: float = 2.0):
    print(f"[4] 开始自动翻页 ({count} 次)...")
    for i in range(count):
        swipe_up()
        time.sleep(interval)
        # 偶尔点一下防止页面卡住
        if i % 4 == 3:
            tap(SWIPE_X, 1200)
            time.sleep(0.5)
        print(f"    进度: {i+1}/{count}")


def stop_mitmdump(proc: subprocess.Popen):
    print("[5] 停止 mitmdump...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def analyze_logs() -> dict:
    """简单分析文本日志，提取 URL 列表"""
    urls = []
    domains = set()
    if TEXT_LOG.exists():
        with open(TEXT_LOG, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                # mitmdump --flow-detail 2 输出格式里找 URL
                if line.startswith("http://") or line.startswith("https://"):
                    urls.append(line)
                elif "GET " in line or "POST " in line:
                    parts = line.split()
                    for p in parts:
                        if p.startswith("http"):
                            urls.append(p)
                # 提取域名
                if "://" in line:
                    from urllib.parse import urlparse
                    try:
                        d = urlparse(line.split()[0]).netloc
                        if d:
                            domains.add(d)
                    except Exception:
                        pass
    return {"urls": urls[:50], "domains": sorted(domains)[:20], "url_count": len(urls)}


def main():
    print("=" * 60)
    print("  自动战报翻页抓包工具")
    print("=" * 60)

    if not MITMDUMP.exists():
        print(f"[!] 找不到 mitmdump: {MITMDUMP}")
        return 1

    # 设置代理
    set_proxy()

    # 启动抓包
    mitm_proc = start_mitmdump()

    # 给几秒钟切到战报页面
    print("\n[3] 请在 3 秒内确保模拟器已打开战报页面...")
    time.sleep(3)

    # 自动翻页
    try:
        do_swipes(count=15, interval=2.0)
    except KeyboardInterrupt:
        print("\n[!] 用户中断")

    # 收尾
    stop_mitmdump(mitm_proc)
    clear_proxy()

    # 分析
    analysis = analyze_logs()
    summary = {
        "timestamp": datetime.now().isoformat(),
        "flow_file": str(FLOW_FILE),
        "text_log": str(TEXT_LOG),
        **analysis,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[OK] 完成!")
    print(f"    流量文件: {FLOW_FILE}")
    print(f"    文本日志: {TEXT_LOG}")
    print(f"    摘要文件: {SUMMARY_JSON}")
    print(f"    捕获 URL: {analysis['url_count']} 条")
    print(f"\n    查看方式:")
    print(f"    1. 用 mitmweb 打开图形界面: mitmweb -r {FLOW_FILE}")
    print(f"    2. 导出为 HAR: mitmdump -n -r {FLOW_FILE} --save-stream-file - | mitmproxy2har")
    print(f"    3. 直接看文本: type {TEXT_LOG}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
