"""检查战法名提取异常的武将"""
import sys, json
sys.path.insert(0, '.')
from src.article_extractor import fetch_feed, extract_article_preview_from_feed, extract_primary_skill_info

PROBLEM_HEROES = [
    ("孙坚",   "68eb37262d07e635d9aa9365"),
    ("灵帝",   "687715b87fde177cc390b459"),
    ("董卓",   "674fadcfa41e9f41ca19965c"),
    ("黄月英", "674d06972f6f832645649324"),
    ("周瑜",   "664980c2dacca75265fb5953"),
    ("田丰",   "6644a9e71f09ca0fdb544f5a"),
    ("公孙瓒", "68bd2006bb8d7452c5143463"),
]

for name, feed_id in PROBLEM_HEROES:
    feed = fetch_feed(feed_id)
    preview = extract_article_preview_from_feed(feed_id, feed)
    ps = extract_primary_skill_info(preview)
    print(f"\n[{name}]  战法名={ps['name']!r}  段落数={ps['paragraph_count']}")
    for j, p in enumerate(ps['paragraphs'][:5]):
        print(f"    [{j}] {p[:100]}")
    if ps['paragraph_count'] > 5:
        print(f"    ... 共 {ps['paragraph_count']} 段")
    # 看 sections
    print(f"  sections: {[(s.title, len(s.paragraphs)) for s in preview.sections]}")
    print(f"  article_title: {preview.title!r}")
