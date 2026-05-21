import sys, time
sys.path.insert(0, '.')
from src.database import init_db
from src.article_extractor import fetch_feed, extract_article_preview_from_feed

conn = init_db()
heroes = conn.execute("""
    SELECT id, name, feed_id, article_url
    FROM heroes
    WHERE article_url IS NOT NULL
      AND article_url != ''
      AND (four_dimensions_image IS NULL OR four_dimensions_image = '')
""").fetchall()

total = len(heroes)
found = 0
still_missing = 0
errors = 0

for i, row in enumerate(heroes):
    row_id, name, feed_id, article_url = row
    try:
        feed = fetch_feed(feed_id)
        preview = extract_article_preview_from_feed(feed_id, feed)
        four_dim = preview.four_dimensions_image

        conn.execute(
            "UPDATE heroes SET four_dimensions_image = ? WHERE id = ?",
            (four_dim, row_id)
        )
        conn.commit()

        if four_dim:
            found += 1
            print(f'[{i+1}/{total}] OK  {name}')
        else:
            still_missing += 1
            print(f'[{i+1}/{total}] N/A {name}')
    except Exception as e:
        errors += 1
        print(f'[{i+1}/{total}] ERR {name}: {e}')

    time.sleep(0.3)

print()
print(f'完成: 新增={found}  仍无图={still_missing}  错误={errors}')
