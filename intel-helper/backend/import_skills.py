"""
导入配将助手数据到 intel-helper

从配将助手的 heroes.db 导入武将战法数据到 intel-helper 的 intel.db
支持下载战法截图到本地目录
"""
import os
import sys
import json
import sqlite3
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_database, Hero


def download_image(args):
    """下载单张图片，返回本地路径"""
    hero_name, url, local_dir = args
    if not url or not isinstance(url, str) or len(url) < 10:
        return None
    
    try:
        filename = f"{hero_name}_{Path(url).name}"
        local_path = Path(local_dir) / filename
        
        if local_path.exists():
            return str(local_path)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(resp.content)
        
        return str(local_path)
    except Exception as e:
        print(f"  下载失败 {hero_name}: {e}")
        return None


def import_hero_skills(
    source_db_path: str = None,
    heroes_images_dir: str = None,
    dry_run: bool = False,
    download_images: bool = True
):
    """
    从配将助手导入武将战法数据

    Args:
        source_db_path: 配将助手 heroes.db 路径，默认从项目根目录 data/heroes.db
        heroes_images_dir: 战法图片目录，默认从项目根目录 data/heroes_images
        dry_run: True 则只打印不写入
        download_images: True 则下载图片到本地
    """
    # 默认路径
    if source_db_path is None:
        source_db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "heroes.db"
        )
    if heroes_images_dir is None:
        heroes_images_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "hero_skill_images"
        )

    if not os.path.exists(source_db_path):
        print(f"源数据库不存在: {source_db_path}")
        print("请先运行配将助手的抓取脚本生成数据")
        return

    # 连接源数据库
    source_conn = sqlite3.connect(source_db_path)
    source_conn.row_factory = sqlite3.Row

    # 获取所有武将及其战法
    query = """
    SELECT
        h.name,
        h.faction,
        h.star,
        h.unit_type,
        h.image,
        h.four_dimensions_image,
        ps.name as skill_name,
        ps.paragraphs_json,
        ps.images_json,
        ps.skill_type,
        ps.trigger_rate
    FROM heroes h
    LEFT JOIN primary_skills ps ON ps.hero_id = h.id
    ORDER BY h.star DESC, h.name
    """
    rows = source_conn.execute(query).fetchall()
    source_conn.close()

    if not rows:
        print("源数据库中没有武将数据")
        return

    # 准备下载任务
    download_tasks = []
    url_to_local = {}  # 缓存：URL -> 本地路径
    
    if download_images:
        print("\n准备下载战法截图到本地...")
        for row in rows:
            hero_name = row["name"]
            if not hero_name or not row["images_json"]:
                continue
            try:
                img_urls = json.loads(row["images_json"]) or []
                if isinstance(img_urls, list):
                    for url in img_urls:
                        if url and isinstance(url, str) and len(url) > 10:
                            download_tasks.append((hero_name, url, heroes_images_dir))
            except (json.JSONDecodeError, TypeError):
                pass
        
        print(f"共 {len(download_tasks)} 张图片待下载")
        
        # 并行下载
        if download_tasks:
            Path(heroes_images_dir).mkdir(parents=True, exist_ok=True)
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(download_image, task): task for task in download_tasks}
                completed = 0
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        url_to_local[download_tasks[len([f for f in futures if f.done()]) - 1][1]] = result
                    completed += 1
                    if completed % 20 == 0:
                        print(f"  已下载 {completed}/{len(download_tasks)}...")

    # 连接目标数据库
    db = get_database()

    imported = 0
    skipped = 0

    with db.get_session() as session:
        for row in rows:
            hero_name = row["name"]
            if not hero_name:
                continue

            # 查找目标数据库中的武将
            hero = session.query(Hero).filter(Hero.name == hero_name).first()

            if not hero:
                # 自动创建武将
                hero = Hero(
                    name=hero_name,
                    camp=_map_camp(row["faction"]),
                    troop_type=_map_troop_type(row["unit_type"]),
                    tags=_build_tags(row)
                )
                session.add(hero)
                session.flush()
            else:
                # 更新战法信息
                pass

            # 更新战法数据
            if row["skill_name"]:
                hero.skill_name = row["skill_name"]
                hero.skill_type = row["skill_type"]

                # 处理战法截图
                images = []
                if row["images_json"]:
                    try:
                        img_urls = json.loads(row["images_json"])
                        if isinstance(img_urls, list):
                            for url in img_urls:
                                if url and isinstance(url, str) and len(url) > 10:
                                    if download_images and url in url_to_local:
                                        # 使用本地路径
                                        images.append(f"/hero_skill_images/{Path(url_to_local[url]).name}")
                                    elif download_images:
                                        # 下载并获取本地路径
                                        result = download_image((hero_name, url, heroes_images_dir))
                                        if result:
                                            images.append(f"/hero_skill_images/{Path(result).name}")
                                    else:
                                        # 直接使用 URL
                                        images.append(url)
                    except (json.JSONDecodeError, TypeError):
                        pass

                hero.skill_images_json = json.dumps(images) if images else None
                hero.skill_trigger_rate = row["trigger_rate"]

            imported += 1

    print(f"\n导入完成: {imported} 个武将已处理")
    if download_images:
        print(f"图片已下载到: {heroes_images_dir}")
    if skipped > 0:
        print(f"跳过: {skipped} 个武将（未找到对应记录）")


def _map_camp(faction: str) -> str:
    """映射阵营名称"""
    if not faction:
        return "群"
    camp_map = {
        "魏": "魏",
        "蜀": "蜀",
        "吴": "吴",
        "群": "群",
        "汉": "蜀",
        "晋": "魏",
        "1": "魏",
        "2": "蜀",
        "3": "吴",
        "4": "群",
    }
    return camp_map.get(faction, "群")


def _map_troop_type(unit_type: str) -> str:
    """映射兵种类型"""
    if not unit_type:
        return "步兵"
    type_map = {
        "步兵": "步兵",
        "骑兵": "骑兵",
        "弓兵": "弓兵",
        "器械": "器械",
        "1": "步兵",
        "2": "骑兵",
        "3": "弓兵",
        "4": "器械",
    }
    return type_map.get(unit_type, "步兵")


def _build_tags(row: sqlite3.Row) -> str:
    """构建标签"""
    tags = []

    # 根据星级添加标签
    star = row["star"]
    if star and star >= 5:
        tags.append("五星")
    elif star and star >= 4:
        tags.append("四星")

    # 根据阵营添加标签
    if row["faction"]:
        tags.append(_map_camp(row["faction"]))

    # 根据战法类型添加标签
    if row["skill_type"]:
        tags.append(row["skill_type"])

    return ",".join(tags) if tags else ""


def main():
    import argparse

    parser = argparse.ArgumentParser(description="导入配将助手武将战法数据")
    parser.add_argument(
        "--source",
        help="配将助手 heroes.db 路径",
        default=None
    )
    parser.add_argument(
        "--images-dir",
        help="战法图片目录",
        default=None
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印不写入"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("导入配将助手武将战法数据")
    print("=" * 50)

    import_hero_skills(
        source_db_path=args.source,
        heroes_images_dir=args.images_dir,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
