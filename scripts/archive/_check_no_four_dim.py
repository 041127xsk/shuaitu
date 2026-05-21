import sys
sys.path.insert(0, '.')
from src.article_extractor import fetch_feed, extract_article_preview_from_feed
from src.database import init_db

conn = init_db()
# 取10个原本无图的武将
no_four = conn.execute("""
    SELECT name, feed_id FROM heroes
    WHERE four_dimensions_image IS NULL AND article_url IS NOT NULL
    LIMIT 10
""").fetchall()

for name, feed_id in no_four:
    try:
        feed = fetch_feed(feed_id)
        preview = extract_article_preview_from_feed(feed_id, feed)
        result = preview.four_dimensions_image
        print(f'{name}: {result[:60] if result else "(无)"}')
    except Exception as e:
        print(f'{name}: ERR {e}')
