"""验证多个武将的段落清洗效果"""
import sys
sys.path.insert(0, '.')
from src.article_extractor import fetch_feed, extract_article_preview_from_feed, extract_primary_skill_info

# 抽取几个典型武将验证
SAMPLES = [
    ("张机",   "62a35aeb7442470001563c12"),
    ("赵云",   "63a9b6ec0c8dc60001ab6b76"),
    ("曹操",   "62a369d1340836000141315e"),
    ("刘备",   "63a30d1fc3e1e500013d5b40"),
    ("诸葛亮", "6665da93afa5516927193025"),
]

for name, feed_id in SAMPLES:
    feed = fetch_feed(feed_id)
    preview = extract_article_preview_from_feed(feed_id, feed)
    ps = extract_primary_skill_info(preview)
    print(f"\n[{name}] 战法={ps['name']!r}  段落数={ps['paragraph_count']}")
    for j, p in enumerate(ps['paragraphs']):
        marker = "  "
        # 标出可疑噪声行
        noisy = any(kw in p for kw in ["关注", "群聊", "本文毕", "点赞", "转发", "欢迎"])
        if noisy:
            marker = "!!"
        print(f"  {marker}[{j:02d}] {p[:90]}")
