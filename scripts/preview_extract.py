from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.article_extractor import (
    detect_skill_names,
    extract_article_preview,
    extract_feed_ids_from_links,
    extract_primary_skill_info,
    find_skill_text,
    preview_to_dict,
)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/preview_extract.py <feed_id>")
        return 1

    feed_id = sys.argv[1]
    try:
        preview = extract_article_preview(feed_id)
    except Exception as exc:
        print(json.dumps({"feed_id": feed_id, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    skill_texts = find_skill_text(preview)
    primary_skill = extract_primary_skill_info(preview)
    result = {
        "article": preview_to_dict(preview),
        "linked_feed_ids": extract_feed_ids_from_links(preview.links),
        "skill_names": detect_skill_names(skill_texts),
        "main_skill": primary_skill,
        "skill_breakdown": None,
        "skill_texts": skill_texts,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
