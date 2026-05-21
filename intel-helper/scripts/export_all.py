#!/usr/bin/env python
"""
一键导出脚本 - 率土战报情报库
导出所有表数据为 JSON 和 CSV 格式
"""
import os
import sys
import json
import csv
from pathlib import Path
from datetime import datetime


# 项目根目录 (intel-helper 是项目根目录)
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)

# 添加 backend 到路径
sys.path.insert(0, str(PROJECT_ROOT))

from backend.logger_config import script_log, script_error, get_scripts_logger


def print_ok(msg):
    print(f"\033[92m[OK]\033[0m {msg}")
    script_log(f"[EXPORT] {msg}")


def print_warn(msg):
    print(f"\033[93m[WARN]\033[0m {msg}")
    script_log(f"[EXPORT] [WARN] {msg}")


def print_error(msg):
    print(f"\033[91m[ERROR]\033[0m {msg}")
    script_error(f"[EXPORT] {msg}")


def get_timestamp_dir():
    """生成带时间戳的目录名"""
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def export_table_to_json(table_name: str, data: list, export_dir: Path) -> dict:
    """导出表数据为 JSON"""
    result = {
        "table": table_name,
        "count": len(data),
        "json_path": str(export_dir / f"{table_name}.json"),
        "success": False,
        "error": None
    }
    
    try:
        json_path = export_dir / f"{table_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        result["success"] = True
    except Exception as e:
        result["error"] = str(e)
    
    return result


def export_table_to_csv(table_name: str, data: list, export_dir: Path) -> dict:
    """导出表数据为 CSV (UTF-8-SIG)"""
    result = {
        "table": table_name,
        "count": len(data),
        "csv_path": str(export_dir / f"{table_name}.csv"),
        "success": False,
        "error": None
    }
    
    if not data:
        result["success"] = True
        result["csv_path"] = None
        return result
    
    try:
        csv_path = export_dir / f"{table_name}.csv"
        # 使用 UTF-8-SIG 以便 Excel 正确显示中文
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            # 获取所有可能的字段
            all_keys = set()
            for item in data:
                if isinstance(item, dict):
                    all_keys.update(item.keys())
            
            fieldnames = sorted(list(all_keys))
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for item in data:
                if isinstance(item, dict):
                    # 扁平化嵌套对象
                    flat_item = {}
                    for key, value in item.items():
                        if isinstance(value, (dict, list)):
                            flat_item[key] = json.dumps(value, ensure_ascii=False)
                        else:
                            flat_item[key] = value
                    writer.writerow(flat_item)
        
        result["success"] = True
    except Exception as e:
        result["error"] = str(e)
    
    return result


def get_table_counts(db_session) -> dict:
    """获取所有表的记录数"""
    counts = {}
    tables = [
        "hero", "player", "intel_snapshot", 
        "observed_team", "observed_team_member",
        "player_alias", "player_team"
    ]
    
    from backend.database import (
        Hero, Player, IntelSnapshot, ObservedTeam,
        ObservedTeamMember, PlayerAlias, PlayerTeam
    )
    
    table_map = {
        "hero": Hero,
        "player": Player,
        "intel_snapshot": IntelSnapshot,
        "observed_team": ObservedTeam,
        "observed_team_member": ObservedTeamMember,
        "player_alias": PlayerAlias,
        "player_team": PlayerTeam
    }
    
    for table_name in tables:
        try:
            model = table_map.get(table_name)
            if model:
                counts[table_name] = db_session.query(model).count()
            else:
                counts[table_name] = 0
        except Exception:
            counts[table_name] = -1  # 表不存在
    
    return counts


def main():
    print("=" * 60)
    print("率土战报情报库 - 一键导出")
    print("=" * 60)
    print()

    # 初始化日志
    logger = get_scripts_logger()
    logger.info("=" * 50)
    logger.info("开始导出")
    logger.info(f"时间: {datetime.now().isoformat()}")

    # 1. 初始化数据库
    db_file = PROJECT_ROOT / "data" / "intel.db"
    db_url = f"sqlite:///{db_file}"
    
    if not db_file.exists():
        print_error(f"数据库文件不存在: {db_file}")
        return 1
    
    print_ok(f"数据库: {db_file}")

    try:
        from backend.database import init_database
        db = init_database(db_url)
        print_ok("数据库连接成功")
    except Exception as e:
        print_error(f"数据库连接失败: {e}")
        script_error(f"导出失败 - 数据库连接: {e}")
        return 1

    # 2. 创建导出目录
    export_root = PROJECT_ROOT / "exports"
    export_root.mkdir(exist_ok=True)
    
    timestamp = get_timestamp_dir()
    export_dir = export_root / timestamp
    export_dir.mkdir(exist_ok=True)
    print_ok(f"导出目录: {export_dir}")

    # 3. 准备导出结果收集
    export_results = []
    summary = {
        "export_time": datetime.now().isoformat(),
        "database_path": str(db_file),
        "export_directory": str(export_dir),
        "tables": {},
        "total_records": 0,
        "success": True,
        "error": None
    }

    # 4. 定义要导出的表
    # 先导入模型
    from backend.database import (
        Hero, Player, IntelSnapshot, ObservedTeam, PlayerTeam
    )
    
    # 导出的表和对应的模型
    export_configs = [
        ("hero", Hero, Hero.to_dict),
        ("player", Player, lambda x: {
            "id": x.id, "name": x.name, "normalized_name": x.normalized_name,
            "alliance": x.alliance, "server": x.server, "season": x.season,
            "notes": x.notes, "created_at": x.created_at.isoformat() if x.created_at else None,
            "updated_at": x.updated_at.isoformat() if x.updated_at else None
        }),
        ("intel_snapshot", IntelSnapshot, IntelSnapshot.to_dict),
        ("observed_team", ObservedTeam, ObservedTeam.to_dict),
        ("player_team", PlayerTeam, PlayerTeam.to_dict),
    ]
    
    with db.get_session() as session:
        # 获取表记录数
        counts = get_table_counts(session)
        
        for table_name, model, serializer in export_configs:
            count = counts.get(table_name, 0)
            print(f"\n导出表: {table_name} ({count} 条记录)")
            
            if count < 0:
                print_warn(f"表 {table_name} 不存在，跳过")
                summary["tables"][table_name] = {
                    "exists": False,
                    "count": 0,
                    "json_exported": False,
                    "csv_exported": False
                }
                continue
            
            try:
                records = session.query(model).all()
                data = [serializer(r) for r in records]
                
                # 导出 JSON
                json_result = export_table_to_json(table_name, data, export_dir)
                export_results.append(json_result)
                
                if json_result["success"]:
                    print_ok(f"JSON: {json_result['json_path']} ({count} 条)")
                else:
                    print_error(f"JSON 导出失败: {json_result['error']}")
                
                # 导出 CSV
                csv_result = export_table_to_csv(table_name, data, export_dir)
                export_results.append(csv_result)
                
                if csv_result["success"] and csv_result["csv_path"]:
                    print_ok(f"CSV: {csv_result['csv_path']} ({count} 条)")
                elif csv_result["success"]:
                    print_warn(f"CSV: 无数据，跳过")
                else:
                    print_error(f"CSV 导出失败: {csv_result['error']}")
                
                summary["tables"][table_name] = {
                    "exists": True,
                    "count": count,
                    "json_exported": json_result["success"],
                    "json_path": json_result.get("json_path"),
                    "csv_exported": csv_result["success"],
                    "csv_path": csv_result.get("csv_path")
                }
                summary["total_records"] += count
                
            except Exception as e:
                print_error(f"导出 {table_name} 失败: {e}")
                script_error(f"导出 {table_name} 失败: {e}")
                summary["tables"][table_name] = {
                    "exists": True,
                    "count": 0,
                    "error": str(e)
                }

    # 5. 保存导出摘要
    summary_path = export_dir / "export_summary.json"
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print_ok(f"导出摘要: {summary_path}")
    except Exception as e:
        print_error(f"保存导出摘要失败: {e}")

    # 6. 打印汇总
    print()
    print("=" * 60)
    print("导出完成")
    print("=" * 60)
    print(f"导出目录: {export_dir}")
    print(f"总记录数: {summary['total_records']}")
    print(f"摘要文件: {summary_path}")
    print("=" * 60)
    
    # 记录日志
    logger.info(f"导出完成: {export_dir}")
    logger.info(f"总记录数: {summary['total_records']}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_warn("导出已取消")
        sys.exit(1)
    except Exception as e:
        print_error(f"导出失败: {e}")
        script_error(f"导出失败: {e}")
        sys.exit(1)
