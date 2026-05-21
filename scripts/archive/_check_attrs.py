import sys
sys.path.insert(0, '.')
from src.article_extractor import fetch_feed, extract_article_preview_from_feed

# 测试多个武将
feed_ids = [
    ('66533efddacca75265173145', '汉吕布'),
    ('639fc0e9c5a3250001d3cb97', '群吕布'),
]

for feed_id, name in feed_ids:
    feed = fetch_feed(feed_id)
    preview = extract_article_preview_from_feed(feed_id, feed)
    print(f'{name}: four_dimensions_image = {preview.four_dimensions_image}')
