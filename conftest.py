"""conftest.py — 项目根目录，确保 src 包可被测试直接导入。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
