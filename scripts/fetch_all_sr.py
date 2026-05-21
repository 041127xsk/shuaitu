"""
fetch_all_sr.py - 扩大化抓取：全量 SR 武将
==========================================
策略：
  1. 从 wujiangInfo.json 取全部 SR 武将列表（132个去重）。
  2. 先从目录文章锚点做精确文本匹配（覆盖约81个）。
  3. 对未匹配的，用别名表 ALIAS_MAP 做二次查找。
  4. 对仍未匹配的，做前缀/子串模糊匹配作为兜底。
  5. 每条请求间隔 1.5 秒，遇到错误隔离后继续。
  6. 结果写入 data/fetched_heroes_all.json 并直接入库 heroes.db。
  7. 支持 --dry-run（只打印匹配结果，不抓取）和 --resume（跳过已成功条目）。

用法：
    python -X utf8 scripts/fetch_all_sr.py
    python -X utf8 scripts/fetch_all_sr.py --dry-run
    python -X utf8 scripts/fetch_all_sr.py --resume
    python -X utf8 scripts/fetch_all_sr.py --output data/my_heroes.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.article_extractor import (
    extract_article_preview_from_feed,
    extract_primary_skill_info,
    fetch_feed,
    parse_feed_content,
    extract_anchors,
)
from src.hero_catalog import (
    fetch_hero_catalog,
    filter_high_star_heroes,
    to_hero_records,
)
from src.database import init_db, upsert_hero, upsert_primary_skill, upsert_crawl_state

DIRECTORY_FEED_ID = "636268ee74424700010125d5"
DEFAULT_OUTPUT = ROOT / "data" / "fetched_heroes_all.json"
DEFAULT_DB = ROOT / "data" / "heroes.db"
REQUEST_DELAY = 1.5  # 秒，避免限流

# ---------------------------------------------------------------------------
# 别名表：武将名(wujiangInfo) -> 目录文章里对应的锚点文本
# 针对51个精确匹配失败的武将手工维护
# ---------------------------------------------------------------------------
ALIAS_MAP: dict[str, list[str]] = {
    "群吕布":   ["群骑吕布", "群吕布"],
    "吕布":     ["魏吕布", "汉吕布", "弓吕布", "吕布"],
    "关羽":     ["蜀关羽", "汉关羽", "关羽"],
    "司马懿":   ["魏司马懿", "SP司马懿", "司马懿"],
    "诸葛亮":   ["弓诸葛亮", "蜀诸葛亮", "诸葛亮"],
    "貂蝉":     ["汉貂蝉", "群貂蝉", "貂蝉"],
    "孙权":     ["蜀孙权", "吴孙权", "孙权"],
    "周瑜":     ["XP周瑜", "吴周瑜", "周瑜"],
    "夏侯惇":   ["夏侯惇"],
    "夏侯渊":   ["夏侯渊"],
    "董卓":     ["汉董卓", "群董卓", "董卓"],
    "袁绍":     ["袁绍"],
    "荀彧":     ["荀彧"],
    "贾诩":     ["魏贾诩", "群贾诩", "贾诩"],
    "张宁":     ["张宁"],
    "郝昭":     ["郝昭"],
    "小乔＆大乔": ["小乔", "大乔"],
    "颜良＆文丑": ["颜良", "文丑", "颜良＆文丑"],
    "卢植":     ["SP卢植", "卢植"],
    "张昭":     ["张昭"],
    "孙坚":     ["汉孙坚", "孙坚"],
    "张春华":   ["张春华"],
    "曹纯":     ["曹纯"],
    "孟获":     ["孟获"],
    "陈宫":     ["陈宫"],
    "木鹿大王":  ["木鹿", "木鹿大王"],
    "华雄":     ["华雄"],
    "灵帝":     ["灵帝"],
    "徐晃":     ["徐晃"],
    "邓艾":     ["邓艾"],
    "吕姬":     ["吕姬（步）", "吕姬"],
    "蔡文姬":   ["蔡文姬"],
    "十常侍":   ["十常侍"],
    "公孙瓒":   ["公孙瓒", "第一公孙瓒"],
    "华佗":     ["华佗"],
    "典韦":     ["典韦"],
    "张梁":     ["张梁"],
    "何太后":   ["何太后"],
    "庞德":     ["庞德"],
    "徐荣":     ["徐荣"],
    "许劭":     ["许劭"],
    "王朗":     ["王朗"],
    "祝融夫人":  ["祝融夫人"],
    "潘凤":     ["潘凤"],
    "牛辅":     ["牛辅"],
    "李傕":     ["李傕"],
    "步皇后":   ["步皇后"],
    "董旻":     ["董旻"],
    "董白":     ["卞夫人董白", "董白"],
    "轲比能":   ["轲比能"],
    "郭汜":     ["郭汜"],
    "黄忠":     ["黄忠"],
}


# ---------------------------------------------------------------------------
# 目录文章锚点匹配
# ---------------------------------------------------------------------------

def _is_valid_article_url(href: str) -> bool:
    """URL 必须含 ds.163.com/article/ 且 feed_id 部分为24位十六进制串。"""
    import re
    if "ds.163.com/article" not in href:
        return False
    feed_id = href.rstrip("/").split("/")[-1]
    return bool(re.fullmatch(r"[0-9a-f]{24}", feed_id))


def build_anchor_lookup(anchors: list[dict]) -> dict[str, str]:
    """返回 {锚点文本: 文章URL} 的字典（去重取第一个，过滤无效链接）。"""
    lookup: dict[str, str] = {}
    for a in anchors:
        text = a["text"]
        href = a["href"]
        if _is_valid_article_url(href) and text not in lookup:
            lookup[text] = href
    return lookup


def resolve_hero_url(hero_name: str, anchor_lookup: dict[str, str]) -> str | None:
    """
    按优先级查找武将文章 URL：
    1. 精确匹配
    2. ALIAS_MAP 别名表
    3. 前缀/子串模糊兜底
    """
    # 1. 精确
    if hero_name in anchor_lookup:
        return anchor_lookup[hero_name]

    # 2. 别名表
    for alias in ALIAS_MAP.get(hero_name, []):
        if alias in anchor_lookup:
            return anchor_lookup[alias]

    # 3. 子串模糊（anchor text 包含 hero_name，或完全相等）
    # 优先短文本（更精确）
    candidates = []
    for text, href in anchor_lookup.items():
        if _is_valid_article_url(href) and (hero_name in text or text == hero_name):
            candidates.append((len(text), href))
    if candidates:
        candidates.sort()
        return candidates[0][1]

    return None


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def fetch_hero_record(
    hero_name: str,
    article_url: str,
    hero_meta: dict,
) -> dict:
    """抓取单个武将，返回结构化记录。出错时返回带 error 字段的 dict。"""
    feed_id = article_url.rstrip("/").split("/")[-1]
    try:
        feed = fetch_feed(feed_id)
        preview = extract_article_preview_from_feed(feed_id, feed)
    except Exception as exc:
        return {
            "hero_name": hero_name,
            "article_url": article_url,
            "feed_id": feed_id,
            "hero_meta": hero_meta,
            "error": str(exc),
        }

    return {
        "hero_name": hero_name,
        "article_url": article_url,
        "feed_id": feed_id,
        "article_title": preview.title,
        "primary_skill": extract_primary_skill_info(preview),
        "hero_meta": hero_meta,
        "four_dimensions_image": preview.four_dimensions_image,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取全量 SR 武将数据")
    parser.add_argument("--output",   default=str(DEFAULT_OUTPUT), help="JSON 输出路径")
    parser.add_argument("--db",       default=str(DEFAULT_DB),     help="SQLite 数据库路径")
    parser.add_argument("--dry-run",  action="store_true",         help="只打印匹配结果，不抓取")
    parser.add_argument("--resume",   action="store_true",         help="跳过数据库里已成功的条目")
    parser.add_argument("--delay",    type=float, default=REQUEST_DELAY, help="请求间隔秒数")
    args = parser.parse_args()

    output_path = Path(args.output)
    db_path     = Path(args.db)

    # --- 1. 拉取武将目录和目录文章 ---
    print("拉取武将目录 (wujiangInfo.json)...")
    catalog = to_hero_records(fetch_hero_catalog())
    high = filter_high_star_heroes(catalog)
    # 按 name 去重，保留第一个
    seen_names: set[str] = set()
    unique_heroes: list = []
    for h in high:
        if h.name not in seen_names:
            seen_names.add(h.name)
            unique_heroes.append(h)
    print(f"  SR 武将去重后: {len(unique_heroes)} 人")

    print(f"\n拉取目录文章 (feed={DIRECTORY_FEED_ID})...")
    directory_feed = fetch_feed(DIRECTORY_FEED_ID)
    directory_body = parse_feed_content(directory_feed)
    anchors = extract_anchors(directory_body.get("longText", ""))
    anchor_lookup = build_anchor_lookup(anchors)
    print(f"  目录文章锚点数: {len(anchor_lookup)}")

    # --- 2. 解析每个武将的文章 URL ---
    hero_map: dict[str, tuple[str, dict]] = {}  # name -> (url, meta)
    no_url: list[str] = []

    for h in unique_heroes:
        meta = {
            "id": h.id, "name": h.name, "unique_name": h.unique_name,
            "quality": h.quality, "star": h.star, "faction": h.faction,
            "cost": h.cost, "unit_type": h.unit_type, "image": h.image,
        }
        url = resolve_hero_url(h.name, anchor_lookup)
        if url:
            hero_map[h.name] = (url, meta)
        else:
            no_url.append(h.name)

    print(f"\n匹配结果: 找到 URL {len(hero_map)} / 找不到 URL {len(no_url)}")
    if no_url:
        print(f"  无法匹配的武将({len(no_url)}): {no_url}")

    if args.dry_run:
        print("\n[--dry-run] 匹配列表:")
        for name, (url, _) in sorted(hero_map.items()):
            feed_id = url.rstrip("/").split("/")[-1]
            print(f"  {name:10} -> {feed_id}")
        return 0

    # --- 3. 已成功条目（用于 --resume）---
    done_feed_ids: set[str] = set()
    if args.resume:
        conn_resume = init_db(db_path)
        rows = conn_resume.execute(
            "SELECT feed_id FROM crawl_state WHERE status='done'"
        ).fetchall()
        done_feed_ids = {r["feed_id"] for r in rows}
        conn_resume.close()
        print(f"[--resume] 已成功条目: {len(done_feed_ids)} 条，将跳过")

    # --- 4. 批量抓取 ---
    conn = init_db(db_path)
    records: list[dict] = []
    ok, fail, skipped = 0, 0, 0
    total = len(hero_map)

    print(f"\n开始抓取 {total} 个武将 (间隔 {args.delay}s)...\n")

    for idx, (hero_name, (article_url, hero_meta)) in enumerate(hero_map.items(), 1):
        feed_id = article_url.rstrip("/").split("/")[-1]

        if feed_id in done_feed_ids:
            print(f"  [{idx:3}/{total}] SKIP  {hero_name}")
            skipped += 1
            continue

        print(f"  [{idx:3}/{total}] {hero_name:10} feed={feed_id} ...", end=" ", flush=True)
        record = fetch_hero_record(hero_name, article_url, hero_meta)
        records.append(record)

        if "error" in record:
            print(f"ERR: {record['error'][:60]}")
            upsert_crawl_state(conn, feed_id, hero_name, article_url,
                               status="error", last_error=record["error"])
            fail += 1
        else:
            skill_name = (record.get("primary_skill") or {}).get("name", "")
            print(f"OK  [{skill_name}]")
            # 写 DB
            try:
                row_id = upsert_hero(conn, record)
                upsert_primary_skill(conn, row_id, record.get("primary_skill") or {})
                upsert_crawl_state(conn, feed_id, hero_name, article_url, status="done")
            except Exception as db_exc:
                print(f"           DB写入失败: {db_exc}")
            ok += 1

        if idx < total:
            time.sleep(args.delay)

    conn.close()

    # --- 5. 无法匹配的写占位记录 ---
    for name in no_url:
        h_meta = next(({"id": h.id, "name": h.name, "unique_name": h.unique_name,
                        "quality": h.quality, "star": h.star, "faction": h.faction,
                        "cost": h.cost, "unit_type": h.unit_type, "image": h.image}
                       for h in unique_heroes if h.name == name), {})
        records.append({
            "hero_name": name,
            "article_url": "",
            "feed_id": "",
            "hero_meta": h_meta,
            "error": "no_article_url_found",
        })

    # --- 6. 写 JSON ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "total_sr": len(unique_heroes),
        "fetched": ok,
        "failed": fail,
        "skipped": skipped,
        "no_url": no_url,
        "heroes": records,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n{'='*50}")
    print(f"  完成: 成功={ok}  失败={fail}  跳过={skipped}  无URL={len(no_url)}")
    print(f"  JSON: {output_path}")
    print(f"  DB  : {db_path}")
    print(f"{'='*50}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
