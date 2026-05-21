#!/usr/bin/env python3
"""
scripts/export_heroes.py
========================
统一导出脚本：支持 JSON / CSV 两种格式，可按阵营/星级过滤。

用法:
    python scripts/export_heroes.py                          # 默认 JSON，全部武将
    python scripts/export_heroes.py --format json            # JSON
    python scripts/export_heroes.py --format csv              # CSV
    python scripts/export_heroes.py --faction 魏 --star 5    # 魏国5星及以上
    python scripts/export_heroes.py --with-paragraphs         # 含主战法段落全文
    python scripts/export_heroes.py -o data/export_魏国.csv   # 指定输出路径
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db, export_heroes, export_summary


# JSON / CSV 共同字段（不含原始 JSON 字符串）
COMMON_FIELDS = [
    "name", "unique_name", "quality", "star", "faction",
    "cost", "unit_type", "image",
    "feed_id", "article_url", "article_title",
    "four_dimensions_image",
    "skill_title", "skill_name",
    "skill_paragraph_count", "skill_image_count",
]

ALL_FIELDS = COMMON_FIELDS + ["skill_paragraphs_json", "skill_images_json"]


def _flatten_paragraphs(rows: list[dict]) -> list[dict]:
    """将 paragraphs_json / images_json 字符串转为列表，嵌入 dict。"""
    for row in rows:
        for key in ("skill_paragraphs_json", "skill_images_json"):
            val = row.get(key)
            if val and isinstance(val, str):
                try:
                    row[key] = json.loads(val)
                except Exception:
                    row[key] = []
    return rows


def to_json(rows: list[dict], summary: dict, *, pretty: bool = False) -> str:
    payload = {
        "summary": summary,
        "heroes": rows,
    }
    indent = 2 if pretty else None
    return json.dumps(payload, ensure_ascii=False, indent=indent)


def to_csv(rows: list[dict], fieldnames: list[str]) -> str:
    import io
    buf = io.StringIO()
    # 展开 paragraphs / images 为换行分隔字符串
    expanded = []
    for row in rows:
        r = {}
        for k, v in row.items():
            if isinstance(v, (list, dict)):
                v = "\n".join(str(x) for x in v) if v else ""
            r[k] = v
        expanded.append(r)

    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(expanded)
    return buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="统一导出武将数据")
    parser.add_argument(
        "--format", "-f", choices=["json", "csv"], default="json",
        help="导出格式（默认 json）"
    )
    parser.add_argument(
        "--faction", choices=["魏", "群", "吴", "蜀", "汉", "晋"],
        help="按阵营过滤"
    )
    parser.add_argument(
        "--star", "-s", type=int,
        help="最低星级（如 --star 5 表示5星及以上）"
    )
    parser.add_argument(
        "--with-paragraphs", action="store_true",
        help="导出时含主战法段落全文（JSON 模式下 paragraphs 为数组）"
    )
    parser.add_argument(
        "--output", "-o",
        help="输出文件路径（默认 stdout）"
    )
    parser.add_argument(
        "--pretty", "-p", action="store_true",
        help="JSON 格式化缩进"
    )
    args = parser.parse_args()

    conn = init_db()

    # 导出
    rows = export_heroes(
        conn,
        faction=args.faction,
        star=args.star,
        with_paragraphs=args.with_paragraphs,
    )
    summary = export_summary(conn)

    # 应用过滤后的 summary 裁剪
    if args.faction or args.star:
        total = len(rows)
        with_skill = sum(1 for r in rows if r.get("skill_name"))
        with_fd = sum(1 for r in rows if r.get("four_dimensions_image"))
        summary = {
            "total": total,
            "with_skill_name": with_skill,
            "with_four_dimensions_image": with_fd,
            "filter": {
                "faction": args.faction,
                "star": args.star,
            },
        }

    if args.format == "json":
        if args.with_paragraphs:
            rows = _flatten_paragraphs(rows)
        output = to_json(rows, summary, pretty=args.pretty)
    else:
        fields = ALL_FIELDS if args.with_paragraphs else COMMON_FIELDS
        output = to_csv(rows, fields)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"已导出到 {args.output}（{len(rows)} 条）", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
