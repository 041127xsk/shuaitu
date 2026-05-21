"""
战报助手 - ADB 工具模块
"""
import subprocess
from typing import Optional, Tuple


class ADBHelper:
    def __init__(self, adb_path: str, serial: str = "127.0.0.1:16384"):
        self.adb_path = adb_path
        self.serial = serial

    def _run(self, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
        """执行 ADB 命令"""
        cmd = [self.adb_path, "-s", self.serial] + list(args)
        return subprocess.run(cmd, capture_output=True, timeout=timeout)

    def connect(self) -> bool:
        """连接模拟器"""
        result = subprocess.run(
            [self.adb_path, "connect", self.serial],
            capture_output=True, text=True, timeout=10
        )
        return "connected" in result.stdout.lower()

    def get_screen_size(self) -> Tuple[int, int]:
        """获取屏幕分辨率"""
        result = self._run("shell", "wm", "size", timeout=10)
        output = result.stdout.decode("utf-8", errors="replace").strip()
        for line in output.split("\n"):
            if "size" in line.lower():
                parts = line.split(":")[-1].strip().split("x")
                return int(parts[0]), int(parts[1])
        return 1080, 1920

    def detect_game(self) -> Optional[str]:
        """检测游戏版本，返回进程名"""
        result = self._run("shell", "ps -A | grep stzb", timeout=10)
        output = result.stdout.decode("utf-8", errors="replace")
        if "com.netease.stzb.uc" in output:
            return "uc"
        elif "com.netease.stzb.netease" in output:
            return "official"
        return None

    def get_current_activity(self) -> str:
        """获取当前前台 Activity"""
        result = self._run("shell", "dumpsys window | grep mCurrentFocus", timeout=10)
        return result.stdout.decode("utf-8", errors="replace").strip()

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 100):
        """执行滑动"""
        self._run("shell", "input", "swipe",
                  str(x1), str(y1), str(x2), str(y2), str(duration),
                  timeout=10)

    def tap(self, x: int, y: int):
        """执行点击"""
        self._run("shell", "input", "tap", str(x), str(y), timeout=10)

    def screenshot(self, local_path: str) -> str:
        """截图"""
        remote_path = "/sdcard/_screenshot.png"
        self._run("shell", "screencap", "-p", remote_path, timeout=15)
        self._run("pull", remote_path, local_path, timeout=15)
        self._run("shell", "rm", remote_path, timeout=5)
        return local_path

    def is_connected(self) -> bool:
        """检查是否连接"""
        result = subprocess.run(
            [self.adb_path, "devices"],
            capture_output=True, text=True, timeout=10
        )
        return self.serial in result.stdout and "device" in result.stdout
