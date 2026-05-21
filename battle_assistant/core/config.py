"""
战报助手 - 配置管理模块
"""
import json
import os
import shutil
from pathlib import Path

DEFAULT_CONFIG = {
    "adb_path": "",
    "serial": "127.0.0.1:16384",
    "game_version": "auto",  # auto / uc / official
    "scroll_count": 5000,
    "scroll_delay": 0.1,
    "scroll_duration": 100,
    "filter_npc": True,
    "filter_incomplete": True,
    "last_export_path": "",
}


class Config:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.data = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        """加载配置文件"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception:
                pass

    def save(self):
        """保存配置文件"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value

    def auto_detect_adb(self) -> str:
        """自动检测 ADB 路径"""
        # 1. 检查配置中是否有
        if self.data["adb_path"] and os.path.exists(self.data["adb_path"]):
            return self.data["adb_path"]

        # 2. 检查常见路径
        candidates = [
            r"C:\Users\27557\.local\bin\platform-tools\adb.exe",
            r"F:\YXShuaiTu-12.0\shell\adb.exe",
            r"E:\emulator\nemu\shell\adb.exe",
            r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
            r"D:\MuMuPlayer-12.0\shell\adb.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                self.data["adb_path"] = path
                self.save()
                return path

        # 3. 检查 PATH
        adb_in_path = shutil.which("adb")
        if adb_in_path:
            self.data["adb_path"] = adb_in_path
            self.save()
            return adb_in_path

        return ""
