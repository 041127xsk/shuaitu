"""
战报助手 - 主入口
"""
import sys
from pathlib import Path

# 添加项目路径
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battle_assistant.gui import BattleAssistantApp


def main():
    app = BattleAssistantApp()
    app.run()


if __name__ == "__main__":
    main()
