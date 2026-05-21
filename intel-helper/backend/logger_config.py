"""
统一日志配置模块
- logs/app.log: 应用运行日志
- logs/db_error.log: 数据库操作错误
- logs/ai_error.log: AI/OCR 调用错误
- logs/scripts.log: 脚本操作日志
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def setup_logger(
    name: str,
    log_file: str,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    format_string: str = None
) -> logging.Logger:
    """
    创建带文件轮转的日志记录器
    
    Args:
        name: 日志记录器名称
        log_file: 日志文件名
        level: 日志级别
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量
        format_string: 自定义格式字符串
    
    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    # 格式化
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    
    formatter = logging.Formatter(
        format_string,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 文件 handler (带轮转)
    file_path = LOGS_DIR / log_file
    file_handler = RotatingFileHandler(
        filename=str(file_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 控制台 handler (可选，主要用于调试)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# 预定义的日志记录器
def get_app_logger() -> logging.Logger:
    """应用运行日志"""
    return setup_logger("app", "app.log")


def get_db_logger() -> logging.Logger:
    """数据库操作错误日志"""
    return setup_logger("db", "db_error.log", level=logging.ERROR)


def get_ai_logger() -> logging.Logger:
    """AI/OCR 调用错误日志"""
    return setup_logger("ai", "ai_error.log", level=logging.ERROR)


def get_scripts_logger() -> logging.Logger:
    """脚本操作日志"""
    return setup_logger("scripts", "scripts.log")


def log_exception(logger: logging.Logger, exc: Exception, extra_msg: str = ""):
    """记录异常，带完整 traceback"""
    import traceback
    tb = "".join(traceback.format_tb(exc.__traceback__))
    msg = f"{extra_msg}\n{type(exc).__name__}: {str(exc)}\nTraceback:\n{tb}"
    logger.error(msg)
    return msg


# ============================================================================
# 便捷函数
# ============================================================================

def info(module: str, message: str):
    """记录 info 日志到 app.log"""
    logger = get_app_logger()
    logger.info(f"[{module}] {message}")


def error(module: str, message: str):
    """记录 error 日志到 app.log"""
    logger = get_app_logger()
    logger.error(f"[{module}] {message}")


def db_error(module: str, message: str, exc: Exception = None):
    """记录数据库错误到 db_error.log"""
    logger = get_db_logger()
    if exc:
        log_exception(logger, exc, f"[{module}] {message}")
    else:
        logger.error(f"[{module}] {message}")


def ai_error(module: str, message: str, exc: Exception = None):
    """记录 AI/OCR 错误到 ai_error.log"""
    logger = get_ai_logger()
    if exc:
        log_exception(logger, exc, f"[{module}] {message}")
    else:
        logger.error(f"[{module}] {message}")


def script_log(message: str):
    """记录脚本操作到 scripts.log"""
    logger = get_scripts_logger()
    logger.info(message)


def script_error(message: str, exc: Exception = None):
    """记录脚本错误到 scripts.log"""
    logger = get_scripts_logger()
    if exc:
        log_exception(logger, exc, message)
    else:
        logger.error(message)


if __name__ == "__main__":
    # 测试日志
    print("测试日志模块...")
    info("test", "这是一条 info 日志")
    db_error("test", "这是一条数据库错误日志", Exception("测试异常"))
    ai_error("test", "这是一条 AI 错误日志", Exception("AI 调用失败"))
    script_log("这是一条脚本日志")
    script_error("这是一条脚本错误", Exception("测试错误"))
    print(f"\n日志目录: {LOGS_DIR}")
    print("日志文件:")
    for f in LOGS_DIR.glob("*.log"):
        print(f"  - {f.name}")
