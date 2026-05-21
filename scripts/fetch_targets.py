from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.article_extractor import extract_article_preview_from_feed, extract_primary_skill_info, fetch_feed, parse_feed_content
from src.hero_catalog import fetch_hero_catalog, filter_high_star_heroes, resolve_hero_links_from_directory, to_hero_records
from src.ai_extract import enrich_skill
from src.database import get_connection, init_db, upsert_crawl_state, get_pending_crawl_targets


DIRECTORY_FEED_ID = "636268ee74424700010125d5"
OUTPUT_PATH = ROOT / "data" / "fetched_heroes.json"

# 固定优先抓取列表（保留兼容，按优先级排在前面）
TARGET_QUERIES = {
    "\u7fa4\u5415\u5e03": ["\u7fa4\u9a91\u5415\u5e03", "\u7fa4\u5415\u5e03"],
    "\u5f20\u673a": ["\u5f20\u673a"],
    "\u8d75\u4e91": ["\u8d75\u4e91"],
    "\u66f9\u64cd": ["\u66f9\u64cd"],
    "\u5218\u5907": ["\u5218\u5907"],
    "\u5415\u8499": ["\u5415\u8499"],
}


def build_link_map(directory_long_text: str, high_star_catalog: list) -> dict[str, list[str]]:
    """
    遍历全部高星武将，从目录页解析文章链接。
    - TARGET_QUERIES 中的名字优先（可含别名）
    - 其余武将按名字精确匹配
    返回 {武将名: [url列表]}，url 已去重
    """
    long_text = directory_long_text or ""

    # 第一步：处理 TARGET_QUERIES（支持别名映射）
    resolved: dict[str, list[str]] = {}
    for display_name, queries in TARGET_QUERIES.items():
        urls: list[str] = []
        for query in queries:
            urls.extend(resolve_hero_links_from_directory(long_text, [query]).get(query, []))
        if urls:
            resolved[display_name] = list(dict.fromkeys(urls))

    # 第二步：遍历全部高星武将，补充未覆盖的武将
    for hero in high_star_catalog:
        if hero.name in resolved:
            continue  # 已在 TARGET_QUERIES 中处理
        urls = resolve_hero_links_from_directory(long_text, [hero.name]).get(hero.name, [])
        if urls:
            resolved[hero.name] = list(dict.fromkeys(urls))

    return resolved


def _get_done_feed_ids(conn) -> set[str]:
    """从 crawl_state 表获取已完成的 feed_id 集合。"""
    rows = conn.execute(
        "SELECT feed_id FROM crawl_state WHERE status = 'done'"
    ).fetchall()
    return {row["feed_id"] for row in rows}


def _get_error_feed_ids(conn) -> set[str]:
    """从 crawl_state 表获取失败的 feed_id 集合。"""
    rows = conn.execute(
        "SELECT feed_id FROM crawl_state WHERE status = 'error'"
    ).fetchall()
    return {row["feed_id"] for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取武将攻略主脚本")
    parser.add_argument("--limit", type=int, default=0, help="最多抓取多少个武将（0=不限，全部）")
    parser.add_argument("--sleep", type=float, default=1.5, help="每次请求间隔秒数（默认1.5）")
    parser.add_argument("--no-ai", action="store_true", help="跳过 AI 结构化抽取（网络不通时使用）")
    parser.add_argument("--resume", action="store_true", help="断点续跑：跳过已完成的武将")
    parser.add_argument("--retry-errors", action="store_true", help="重试之前失败的武将")
    parser.add_argument("--db", default=str(ROOT / "data" / "heroes.db"), help="SQLite 数据库路径（用于断点续跑）")
    args = parser.parse_args()

    # 初始化数据库（用于断点续跑状态管理）
    db_path = Path(args.db)
    conn = init_db(db_path)

    try:
        directory_feed = fetch_feed(DIRECTORY_FEED_ID)
        directory_body = parse_feed_content(directory_feed)
        catalog = to_hero_records(fetch_hero_catalog())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    high_star = filter_high_star_heroes(catalog)
    hero_lookup = {hero.name: hero for hero in high_star}

    # 遍历全部高星武将解析链接
    link_map = build_link_map(directory_body.get("longText", ""), high_star)
    total_with_links = len(link_map)

    # 断点续跑：获取已处理的 feed_id
    done_feed_ids = _get_done_feed_ids(conn)
    error_feed_ids = _get_error_feed_ids(conn)

    if args.resume:
        print(f"断点续跑模式：已完成 {len(done_feed_ids)} 个，失败 {len(error_feed_ids)} 个")

    # 统计
    success_count = 0
    error_count = 0
    skipped_no_link = 0
    skipped_done = 0
    records: list[dict] = []

    for hero_name, urls in link_map.items():
        if args.limit > 0 and success_count >= args.limit:
            break
        if not urls:
            skipped_no_link += 1
            continue

        article_url = urls[0]
        feed_id = article_url.rstrip("/").split("/")[-1]

        # 断点续跑：跳过已完成的
        if args.resume and feed_id in done_feed_ids:
            skipped_done += 1
            continue

        # 重试模式：只处理之前失败的
        if args.retry_errors and feed_id not in error_feed_ids:
            continue

        if args.sleep > 0 and success_count > 0:
            time.sleep(args.sleep)

        # 标记为处理中
        upsert_crawl_state(
            conn,
            feed_id=feed_id,
            hero_name=hero_name,
            article_url=article_url,
            status="pending",
        )

        try:
            preview_feed = fetch_feed(feed_id)
            preview = extract_article_preview_from_feed(feed_id, preview_feed)
        except Exception as exc:
            error_count += 1
            # 记录错误状态到 crawl_state
            upsert_crawl_state(
                conn,
                feed_id=feed_id,
                hero_name=hero_name,
                article_url=article_url,
                status="error",
                last_error=str(exc),
            )
            records.append(
                {
                    "hero_name": hero_name,
                    "article_url": article_url,
                    "feed_id": feed_id,
                    "error": str(exc),
                }
            )
            continue

        primary_skill = extract_primary_skill_info(preview)
        # AI 结构化抽取战法字段（--no-ai 时跳过，网络不通时用此参数加速）
        if args.no_ai:
            ai_extraction = {
                "skill_name": primary_skill.get("name") or "",
                "skill_type": None,
                "trigger_type": None,
                "trigger_rate": None,
                "trigger_condition": None,
                "targets": None,
                "effects": [],
                "duration": None,
                "notes": None,
                "ai_extracted": False,
            }
        else:
            ai_extraction = enrich_skill(
                primary_skill.get("paragraphs") or [],
                skill_name_hint=primary_skill.get("name") or "",
            )

        record = {
            "hero_name": hero_name,
            "article_url": article_url,
            "feed_id": feed_id,
            "article_title": preview.title,
            "primary_skill": primary_skill,
            "ai_extraction": ai_extraction,
        }

        hero = hero_lookup.get(hero_name)
        if hero is not None:
            record["hero_meta"] = {
                "id": hero.id,
                "name": hero.name,
                "unique_name": hero.unique_name,
                "quality": hero.quality,
                "star": hero.star,
                "faction": hero.faction,
                "cost": hero.cost,
                "unit_type": hero.unit_type,
                "image": hero.image,
            }

        records.append(record)
        success_count += 1

        # 标记为完成
        upsert_crawl_state(
            conn,
            feed_id=feed_id,
            hero_name=hero_name,
            article_url=article_url,
            status="done",
        )

    payload = {
        "directory_feed_id": DIRECTORY_FEED_ID,
        "high_star_count": len(high_star),
        "heroes_with_article_links": total_with_links,
        "heroes_fetched": success_count,
        "heroes_error": error_count,
        "heroes_skipped_no_link": skipped_no_link,
        "heroes_skipped_done": skipped_done,
        "heroes": records,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "saved_to": str(OUTPUT_PATH),
        "total_with_links": total_with_links,
        "fetched": success_count,
        "errors": error_count,
        "skipped_no_link": skipped_no_link,
        "skipped_done": skipped_done,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
