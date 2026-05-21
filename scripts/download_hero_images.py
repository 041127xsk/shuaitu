"""
下载武将战法截图到本地目录
解决外链图片无法访问的问题
"""
import os
import json
import sqlite3
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# 配置
PROJECT_ROOT = Path(__file__).parent.parent
SOURCE_DB = PROJECT_ROOT / "data" / "heroes.db"
LOCAL_IMAGES_DIR = PROJECT_ROOT / "intel-helper" / "data" / "hero_skill_images"
MAX_WORKERS = 5
TIMEOUT = 15


def get_hero_images():
    """从数据库获取所有武将战法截图"""
    conn = sqlite3.connect(str(SOURCE_DB))
    conn.row_factory = sqlite3.Row
    
    query = """
    SELECT h.name, ps.images_json
    FROM heroes h
    LEFT JOIN primary_skills ps ON ps.hero_id = h.id
    WHERE ps.images_json IS NOT NULL AND ps.images_json != '[]'
    """
    
    results = []
    for row in conn.execute(query):
        images = []
        try:
            images = json.loads(row["images_json"]) or []
        except (json.JSONDecodeError, TypeError):
            pass
        
        if images:
            results.append({
                "hero_name": row["name"],
                "images": images
            })
    
    conn.close()
    return results


def download_image(args):
    """下载单张图片"""
    hero_name, url = args
    filename = f"{hero_name}_{Path(url).name}"
    local_path = LOCAL_IMAGES_DIR / filename
    
    # 已存在则跳过
    if local_path.exists():
        return hero_name, url, local_path, "skipped"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        
        LOCAL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(resp.content)
        
        return hero_name, url, local_path, "success"
    except Exception as e:
        return hero_name, url, None, f"failed: {e}"


def main():
    print("=" * 50)
    print("下载武将战法截图到本地")
    print("=" * 50)
    
    # 确保目录存在
    LOCAL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    # 获取武将图片
    heroes = get_hero_images()
    print(f"\n找到 {len(heroes)} 个武将有战法截图")
    
    # 收集所有要下载的图片
    tasks = []
    for hero in heroes:
        for url in hero["images"]:
            if url and isinstance(url, str) and len(url) > 10:
                tasks.append((hero["hero_name"], url))
    
    print(f"共 {len(tasks)} 张图片待下载")
    print(f"保存目录: {LOCAL_IMAGES_DIR}")
    
    # 下载
    stats = {"success": 0, "skipped": 0, "failed": 0}
    failed_list = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_image, task): task for task in tasks}
        
        for future in tqdm(as_completed(futures), total=len(tasks), desc="下载中"):
            hero, url, local_path, status = future.result()
            if status == "success":
                stats["success"] += 1
            elif status == "skipped":
                stats["skipped"] += 1
            else:
                stats["failed"] += 1
                if len(failed_list) < 10:  # 只记录前10个失败
                    failed_list.append((hero, url, status))
    
    print("\n" + "=" * 50)
    print("下载完成!")
    print(f"  成功: {stats['success']}")
    print(f"  跳过: {stats['skipped']}")
    print(f"  失败: {stats['failed']}")
    
    if failed_list:
        print("\n失败列表 (前10个):")
        for hero, url, status in failed_list:
            print(f"  {hero}: {status}")
            print(f"    URL: {url[:80]}...")
    
    # 生成映射文件
    mapping = {}
    for hero in heroes:
        hero_images = []
        for url in hero["images"]:
            if url and isinstance(url, str) and len(url) > 10:
                filename = f"{hero['hero_name']}_{Path(url).name}"
                local_file = LOCAL_IMAGES_DIR / filename
                if local_file.exists():
                    # 使用相对路径
                    hero_images.append(f"/hero_skill_images/{filename}")
        if hero_images:
            mapping[hero["hero_name"]] = hero_images
    
    mapping_file = LOCAL_IMAGES_DIR / "mapping.json"
    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    
    print(f"\n映射文件已生成: {mapping_file}")


if __name__ == "__main__":
    main()
