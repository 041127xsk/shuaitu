#!/usr/bin/env python
"""
一键备份脚本 - 率土战报情报库
备份 data/ 目录下的所有数据库和导出文件
"""
import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)

# 添加项目根目录到路径
sys.path.insert(0, str(PROJECT_ROOT))

from backend.logger_config import script_log, script_error, get_scripts_logger


def print_ok(msg):
    print(f"\033[92m[OK]\033[0m {msg}")
    script_log(f"[BACKUP] {msg}")


def print_warn(msg):
    print(f"\033[93m[WARN]\033[0m {msg}")
    script_log(f"[BACKUP] [WARN] {msg}")


def print_error(msg):
    print(f"\033[91m[ERROR]\033[0m {msg}")
    script_error(f"[BACKUP] {msg}")


def get_timestamp_dir():
    """生成带时间戳的目录名"""
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def backup_file(src_path: Path, dest_dir: Path) -> dict:
    """备份单个文件，返回备份信息"""
    result = {
        "source": str(src_path),
        "destination": str(dest_dir / src_path.name),
        "size": 0,
        "success": False,
        "error": None
    }
    
    try:
        if src_path.exists():
            shutil.copy2(src_path, dest_dir / src_path.name)
            result["size"] = src_path.stat().st_size
            result["success"] = True
        else:
            result["error"] = "文件不存在"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def main():
    print("=" * 60)
    print("率土战报情报库 - 一键备份")
    print("=" * 60)
    print()

    # 初始化日志
    logger = get_scripts_logger()
    logger.info("=" * 50)
    logger.info("开始备份")
    logger.info(f"时间: {datetime.now().isoformat()}")

    # 1. 创建备份目录
    backup_root = PROJECT_ROOT / "backups"
    backup_root.mkdir(exist_ok=True)
    print_ok(f"备份根目录: {backup_root}")

    # 2. 创建时间戳子目录
    timestamp = get_timestamp_dir()
    backup_dir = backup_root / timestamp
    backup_dir.mkdir(exist_ok=True)
    print_ok(f"备份目录: {backup_dir}")

    # 3. 定义要备份的文件模式
    data_dir = PROJECT_ROOT / "data"
    if not data_dir.exists():
        print_error(f"data 目录不存在: {data_dir}")
        return 1

    # 备份文件扩展名
    extensions = [".db", ".json", ".csv"]
    
    # 4. 收集并备份文件
    backup_results = []
    total_size = 0
    success_count = 0
    fail_count = 0

    for ext in extensions:
        for file_path in data_dir.rglob(f"*{ext}"):
            # 跳过截图目录中的图片
            if "screenshots" in file_path.parts:
                continue
            if "hero_skill_images" in file_path.parts:
                continue
            
            result = backup_file(file_path, backup_dir)
            backup_results.append(result)
            
            if result["success"]:
                success_count += 1
                total_size += result["size"]
                rel_path = file_path.relative_to(data_dir)
                print_ok(f"已备份: {rel_path} ({result['size'] / 1024:.1f} KB)")
            else:
                fail_count += 1
                rel_path = file_path.relative_to(data_dir)
                print_warn(f"备份失败: {rel_path} - {result['error']}")

    # 5. 备份 logs 目录（最近的日志）
    logs_dir = PROJECT_ROOT / "logs"
    logs_backup_dir = backup_dir / "logs"
    logs_backup_count = 0
    
    if logs_dir.exists():
        # 确保备份目录存在
        logs_backup_dir.mkdir(exist_ok=True)
        
        # 只备份最近的 .log 文件
        log_files = sorted(logs_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]
        for log_file in log_files:
            try:
                shutil.copy2(log_file, logs_backup_dir / log_file.name)
                logs_backup_count += 1
            except Exception as e:
                print_warn(f"日志备份失败: {log_file.name} - {e}")
        
        if logs_backup_count > 0:
            print_ok(f"已备份 {logs_backup_count} 个日志文件")

    # 6. 生成备份清单
    manifest = {
        "backup_time": datetime.now().isoformat(),
        "backup_directory": str(backup_dir),
        "source_data_directory": str(data_dir),
        "total_files": success_count,
        "failed_files": fail_count,
        "total_size_bytes": total_size,
        "total_size_formatted": f"{total_size / 1024 / 1024:.2f} MB",
        "files": [
            {
                "source": r["source"],
                "destination": r["destination"],
                "size_bytes": r["size"],
                "success": r["success"],
                "error": r["error"]
            }
            for r in backup_results
        ],
        "logs_backup": {
            "count": logs_backup_count,
            "directory": str(logs_backup_dir)
        }
    }

    # 7. 保存清单
    manifest_path = backup_dir / "backup_manifest.json"
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        print_ok(f"备份清单: {manifest_path}")
    except Exception as e:
        print_error(f"保存备份清单失败: {e}")

    # 8. 打印汇总
    print()
    print("=" * 60)
    print("备份完成")
    print("=" * 60)
    print(f"备份目录: {backup_dir}")
    print(f"成功备份: {success_count} 个文件")
    if fail_count > 0:
        print(f"备份失败: {fail_count} 个文件")
    print(f"总大小: {total_size / 1024 / 1024:.2f} MB")
    print(f"清单文件: {manifest_path}")
    print("=" * 60)

    # 记录日志
    logger.info(f"备份完成: {backup_dir}")
    logger.info(f"成功: {success_count}, 失败: {fail_count}, 大小: {total_size / 1024 / 1024:.2f} MB")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_warn("备份已取消")
        sys.exit(1)
    except Exception as e:
        print_error(f"备份失败: {e}")
        script_error(f"备份失败: {e}")
        sys.exit(1)
