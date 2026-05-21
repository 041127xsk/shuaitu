"""
auto_scroll_reports.py - 自动翻页战报（配合 stzbHelper 抓包）
============================================================
用 ADB 模拟向上滑动战报列表，stzbHelper 自动捕获数据。
自动检测屏幕分辨率，自适应滑动坐标。

用法：
    python auto_scroll_reports.py              # 默认滑动 5000 次
    python auto_scroll_reports.py --count 100  # 滑动 100 次
    python auto_scroll_reports.py --delay 0.2  # 每次间隔 0.2 秒
"""
from __future__ import annotations

import subprocess
import sys
import time

ADB = r"C:\Users\27557\.local\bin\platform-tools\adb.exe"
SERIAL = "127.0.0.1:16384"


def get_screen_size() -> tuple[int, int]:
    """获取屏幕分辨率。"""
    result = subprocess.run(
        [ADB, "-s", SERIAL, "shell", "wm", "size"],
        capture_output=True, text=True, timeout=10
    )
    output = result.stdout.strip()
    # 输出格式: "Physical size: 1080x1920"
    for line in output.split("\n"):
        if "size" in line.lower():
            parts = line.split(":")[-1].strip().split("x")
            return int(parts[0]), int(parts[1])
    return 1080, 1920


def auto_scroll(
    count: int = 5000,
    delay: float = 0.1,
    duration_ms: int = 100,
):
    """自动滑动战报列表。"""
    w, h = get_screen_size()

    # 自适应坐标：水平居中，垂直在战报列表区域滑动（约 40% 到 15%）
    cx = w // 2
    y_start = int(h * 0.4)
    y_end = int(h * 0.15)

    print(f"Auto-scroll battle reports")
    print(f"  Screen: {w}x{h}")
    print(f"  Swipe: ({cx}, {y_start}) -> ({cx}, {y_end})")
    print(f"  Count: {count}, Delay: {delay}s, Duration: {duration_ms}ms")
    print()

    for i in range(count):
        subprocess.run(
            [ADB, "-s", SERIAL, "shell", "input", "swipe",
             str(cx), str(y_start), str(cx), str(y_end), str(duration_ms)],
            capture_output=True, timeout=10
        )
        print(f"[{i+1}/{count}] Swipe up", flush=True)

        if i < count - 1:
            time.sleep(delay)

    print(f"\nDone. {count} swipes completed.")
    print("Check stzbHelper for captured data.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Auto-scroll battle reports")
    parser.add_argument("--count", type=int, default=5000, help="Number of swipes (default: 5000)")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between swipes in seconds (default: 0.1)")
    parser.add_argument("--duration", type=int, default=100, help="Swipe duration in ms (default: 100)")
    args = parser.parse_args()

    auto_scroll(count=args.count, delay=args.delay, duration_ms=args.duration)
