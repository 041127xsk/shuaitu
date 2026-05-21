"""临时探查脚本：分析目录文章里的武将志专属链接"""
import sys, json
sys.path.insert(0, '.')
from src.article_extractor import fetch_feed, parse_feed_content, extract_anchors
from src.hero_catalog import fetch_hero_catalog, to_hero_records, filter_high_star_heroes

DIRECTORY_FEED_ID = "636268ee74424700010125d5"
directory_feed = fetch_feed(DIRECTORY_FEED_ID)
directory_body = parse_feed_content(directory_feed)
anchors = extract_anchors(directory_body.get("longText", ""))
article_anchors = [a for a in anchors if "ds.163.com/article" in a["href"]]

# 找武将志专属条目
wj_keywords = ["武将解析", "武将志", "S1赛季武将志", "S2赛季武将志", "赛季武将志", "武将解说"]
wj_anchors = [a for a in article_anchors if any(kw in a["text"] for kw in wj_keywords)]
print(f"武将志专属链接数: {len(wj_anchors)}")
print()
for a in sorted(wj_anchors, key=lambda x: x["text"]):
    print(f"  {a['text'][:60]:60}  {a['href']}")

# 同时输出所有锚点到文件供进一步分析
with open("data/directory_anchors.json", "w", encoding="utf-8") as f:
    json.dump(article_anchors, f, ensure_ascii=False, indent=2)
print(f"\n所有文章锚点已保存到 data/directory_anchors.json ({len(article_anchors)}条)")
