"""debug: 检查单个武将的主战法段落质量"""
import sys
sys.path.insert(0, '.')
from src.article_extractor import fetch_feed, extract_article_preview_from_feed, extract_primary_skill_info

feed_id = '639fc0e9c5a3250001d3cb97'  # 群吕布
feed = fetch_feed(feed_id)
preview = extract_article_preview_from_feed(feed_id, feed)

print(f"sections 数量: {len(preview.sections)}")
for i, sec in enumerate(preview.sections):
    print(f"  [{i}] title={sec.title!r}  paragraphs={len(sec.paragraphs)}  images={len(sec.images)}")

ps = extract_primary_skill_info(preview)
print()
print(f"主战法名: {ps['name']!r}")
print(f"段落数: {ps['paragraph_count']}")
print("--- 所有段落 ---")
for j, p in enumerate(ps['paragraphs']):
    print(f"  [{j:02d}] {p[:100]}")
