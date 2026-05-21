"""
emulator.py - ADB 模拟器截图与操控
===================================
通过 ADB 连接 MuMu 模拟器，支持截图、点击、滑动等操作。
"""
from __future__ import annotations

import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple


def _find_adb() -> str:
    """查找 ADB 可执行文件路径。"""
    # MuMu 默认路径（常见位置）
    candidates = [
        r"C:\Users\27557\.local\bin\platform-tools\adb.exe",
        r"F:\YXShuaiTu-12.0\shell\adb.exe",
        r"E:\emulator\nemu\shell\adb.exe",
        r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
        r"D:\MuMuPlayer-12.0\shell\adb.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    
    # 环境变量
    adb_in_path = shutil.which("adb")
    if adb_in_path:
        return adb_in_path

    raise FileNotFoundError(
        "找不到 ADB。请确保 MuMu 模拟器已安装，或将 adb 加入 PATH。"
    )


class EmulatorController:
    """MuMu 模拟器 ADB 控制器。"""

    DEFAULT_SERIAL = "127.0.0.1:16384"

    def __init__(self, serial: str = DEFAULT_SERIAL, adb_path: Optional[str] = None):
        self.serial = serial
        self.adb = adb_path or _find_adb()
        self._connected = False

    def _run(self, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
        """执行 ADB 命令。"""
        cmd = [self.adb, "-s", self.serial] + list(args)
        return subprocess.run(
            cmd, capture_output=True, timeout=timeout
        )

    def connect(self) -> bool:
        """连接模拟器。"""
        result = subprocess.run(
            [self.adb, "connect", self.serial],
            capture_output=True, timeout=10
        )
        output = result.stdout.decode("utf-8", errors="replace")
        self._connected = "connected" in output.lower()
        return self._connected

    def ensure_connected(self) -> None:
        """确保已连接，未连接则自动连接。"""
        if not self._connected:
            if not self.connect():
                raise ConnectionError(f"无法连接到模拟器 {self.serial}")

    def screenshot(self, local_path: str) -> str:
        """
        截图并保存到本地。

        参数:
            local_path: 本地保存路径

        返回:
            本地文件路径
        """
        self.ensure_connected()
        remote_path = "/sdcard/_screenshot.png"

        # 截图
        self._run("shell", "screencap", "-p", remote_path, timeout=15)

        # 拉取到本地
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        self._run("pull", remote_path, local_path, timeout=15)

        # 清理远程文件
        self._run("shell", "rm", remote_path, timeout=5)

        return local_path

    def tap(self, x: int, y: int) -> None:
        """点击屏幕坐标。"""
        self.ensure_connected()
        self._run("shell", "input", "tap", str(x), str(y), timeout=10)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        """滑动屏幕。"""
        self.ensure_connected()
        self._run("shell", "input", "swipe",
                  str(x1), str(y1), str(x2), str(y2), str(duration_ms),
                  timeout=10)

    def key_event(self, keycode: int) -> None:
        """发送按键事件。"""
        self.ensure_connected()
        self._run("shell", "input", "keyevent", str(keycode), timeout=10)

    def get_current_activity(self) -> str:
        """获取当前前台 Activity。"""
        self.ensure_connected()
        result = self._run("shell", "dumpsys window | grep mCurrentFocus", timeout=10)
        return result.stdout.decode("utf-8", errors="replace").strip()

    def get_screen_size(self) -> Tuple[int, int]:
        """获取屏幕分辨率。"""
        self.ensure_connected()
        result = self._run("shell", "wm", "size", timeout=10)
        output = result.stdout.decode("utf-8", errors="replace").strip()
        # 输出格式: "Physical size: 1080x1920"
        for line in output.split("\n"):
            if "size" in line.lower():
                parts = line.split(":")[-1].strip().split("x")
                return int(parts[0]), int(parts[1])
        return 1080, 1920  # 默认值
