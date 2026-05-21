#!/usr/bin/env python
"""
一键启动脚本 - 率土战报情报库
自动检查环境并启动 FastAPI 服务
"""
import os
import sys
import socket
import subprocess
from pathlib import Path
from datetime import datetime


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)

# 添加项目根目录到路径
sys.path.insert(0, str(PROJECT_ROOT))

from backend.logger_config import script_log, script_error, get_scripts_logger, LOGS_DIR


def print_ok(msg):
    print(f"\033[92m[OK]\033[0m {msg}")
    script_log(f"[START] {msg}")


def print_warn(msg):
    print(f"\033[93m[WARN]\033[0m {msg}")
    script_log(f"[START] [WARN] {msg}")


def print_error(msg):
    print(f"\033[91m[ERROR]\033[0m {msg}")
    script_error(f"[START] {msg}")


def check_port(port: int) -> bool:
    """检查端口是否被占用"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.close()
        return False  # 端口可用
    except OSError:
        return True  # 端口被占用


def find_available_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """寻找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        if not check_port(port):
            return port
    return start_port


def main():
    print("=" * 60)
    print("率土战报情报库 - 一键启动")
    print("=" * 60)
    print()

    # 1. 检查 Python
    try:
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            print_error("需要 Python 3.8 或更高版本")
            print(f"当前版本: Python {version.major}.{version.minor}.{version.micro}")
            return 1
        print_ok(f"Python 版本: {version.major}.{version.minor}.{version.micro}")
    except Exception as e:
        print_error(f"检查 Python 版本失败: {e}")
        return 1

    # 2. 检查项目目录
    print_ok(f"项目根目录: {PROJECT_ROOT}")

    # 3. 检查关键文件
    main_file = PROJECT_ROOT / "backend" / "main.py"
    if not main_file.exists():
        print_error(f"主入口文件不存在: {main_file}")
        return 1
    print_ok("主入口文件: backend/main.py")

    # 4. 检查依赖
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        print_ok("核心依赖已安装: FastAPI, Uvicorn, SQLAlchemy")
    except ImportError as e:
        print_error(f"缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return 1

    # 5. 检查并创建目录
    data_dir = PROJECT_ROOT / "data"
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        print_warn(f"已创建 data 目录: {data_dir}")
    else:
        print_ok(f"data 目录: {data_dir}")

    logs_dir = PROJECT_ROOT / "logs"
    if not logs_dir.exists():
        logs_dir.mkdir(parents=True, exist_ok=True)
        print_warn(f"已创建 logs 目录: {logs_dir}")
    else:
        print_ok(f"logs 目录: {logs_dir}")

    # 6. 检查 .env
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print_warn(".env 文件不存在，OCR/AI 功能可能无法使用")
    else:
        print_ok(".env 配置文件存在")

    # 7. 检查 API Key
    dashscope_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not dashscope_key:
        print_warn("DASHSCOPE_API_KEY 未配置，OCR/AI 功能可能失败")
    else:
        key_preview = dashscope_key[:4] + "..." + dashscope_key[-4:] if len(dashscope_key) > 10 else "***"
        print_ok(f"API Key: {key_preview}")

    # 8. 检查数据库
    db_file = data_dir / "intel.db"
    if db_file.exists():
        size = db_file.stat().st_size
        print_ok(f"数据库文件: {db_file} ({size / 1024:.1f} KB)")
    else:
        print_warn("数据库文件不存在，将自动创建")

    # 9. 初始化数据库
    try:
        from backend.database import init_database
        db_url = f"sqlite:///{db_file}"
        db = init_database(db_url)
        print_ok("数据库初始化成功")
    except Exception as e:
        print_error(f"数据库初始化失败: {e}")
        return 1

    # 10. 检查端口
    default_port = 8000
    if check_port(default_port):
        print_warn(f"端口 {default_port} 已被占用，尝试其他端口...")
        port = find_available_port()
        if port != default_port:
            print_warn(f"使用端口: {port}")
        else:
            print_error("无法找到可用端口")
            return 1
    else:
        port = default_port
        print_ok(f"端口 {port} 可用")

    # 11. 启动服务
    print()
    print("=" * 60)
    print_ok("准备启动服务...")
    print(f"Web 地址: http://localhost:{port}")
    print(f"API 文档: http://localhost:{port}/docs")
    print(f"日志目录: {logs_dir}")
    print("=" * 60)
    print()
    print("按 Ctrl+C 停止服务")
    print()

    # 记录启动信息
    logger = get_scripts_logger()
    logger.info(f"=" * 50)
    logger.info(f"服务启动")
    logger.info(f"时间: {datetime.now().isoformat()}")
    logger.info(f"端口: {port}")
    logger.info(f"数据库: {db_file}")
    logger.info(f"日志目录: {logs_dir}")

    # 自动打开浏览器
    import webbrowser
    import threading
    import time

    def open_browser():
        time.sleep(2)  # 等待服务启动
        webbrowser.open(f"http://localhost:{port}")

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    try:
        # 使用 uvicorn 启动
        uvicorn_cmd = [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", str(port)
        ]
        subprocess.run(uvicorn_cmd, cwd=PROJECT_ROOT)
    except KeyboardInterrupt:
        print()
        print_ok("服务已停止")
        logger.info("服务已停止")
        return 0
    except Exception as e:
        print_error(f"启动失败: {e}")
        script_error(f"启动失败: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
