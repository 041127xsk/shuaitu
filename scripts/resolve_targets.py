from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.article_extractor import fetch_feed, parse_feed_content
from src.hero_catalog import fetch_hero_catalog, filter_high_star_heroes, resolve_hero_links_from_directory, to_hero_records


DIRECTORY_FEED_ID = "636268ee74424700010125d5"

TARGET_QUERIES = {
    "群吕布": ["群骑吕布", "群吕布"],
    "张机": ["张机"],
    "赵云": ["赵云"],
    "曹操": ["曹操"],
    "刘备": ["刘备"],
    "吕蒙": ["吕蒙"],
}


def main() -> int:
    try:
        directory_feed = fetch_feed(DIRECTORY_FEED_ID)
        directory_body = parse_feed_content(directory_feed)
        catalog = to_hero_records(fetch_hero_catalog())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    high_star = filter_high_star_heroes(catalog)
    jin_high_star = [hero.name for hero in high_star if hero.faction == "晋"]

    resolved: dict[str, list[str]] = {}
    long_text = directory_body.get("longText", "")
    for display_name, queries in TARGET_QUERIES.items():
        group: list[str] = []
        for query in queries:
            group.extend(resolve_hero_links_from_directory(long_text, [query]).get(query, []))
        resolved[display_name] = list(dict.fromkeys(group))

    payload = {
        "high_star_count": len(high_star),
        "jin_high_star_names": sorted(set(jin_high_star)),
        "target_names": list(TARGET_QUERIES.keys()),
        "resolved": resolved,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
