"""
network_capture - 率土之滨战报网络抓包模块
==========================================
使用 mitmproxy 拦截游戏 HTTP 请求，直接获取战报数据。
"""
from .capture import start_proxy, analyze_capture, setup_emulator_proxy, remove_emulator_proxy

__all__ = ["start_proxy", "analyze_capture", "setup_emulator_proxy", "remove_emulator_proxy"]
