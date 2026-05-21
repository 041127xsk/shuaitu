"""详查田丰武将主战法 section"""
import sys
sys.path.insert(0, '.')
from src.article_extractor import fetch_feed, extract_article_preview_from_feed, detect_skill_names

feed_id = '6644a9e71f09ca0fdb544f5a'
feed = fetch_feed(feed_id)
preview = extract_article_preview_from_feed(feed_id, feed)

main_section = next((s for s in preview.sections if '主战法' in s.title and '拆解' not in s.title), None)
if main_section:
    print(f"section title: {main_section.title!r}")
    names = detect_skill_names(main_section.paragraphs)
    print(f"detect_skill_names: {names}")
    print("前10段:")
    for i, p in enumerate(main_section.paragraphs[:10]):
        print(f"  [{i}] {p[:100]}")
else:
    print("未找到主战法 section")
    print("所有sections:", [(s.title, len(s.paragraphs)) for s in preview.sections])
