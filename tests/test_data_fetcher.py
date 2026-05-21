from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_fetcher import bundle_to_dict, collect_feed_ids


def test_collect_feed_ids_deduplicates_urls():
    hero_links = {
        "司马师": [
            "https://ds.163.com/article/6651d60c99e378294d323998/",
            "https://ds.163.com/article/6651d60c99e378294d323998/",
        ],
        "刘备": ["https://ds.163.com/feed/63a30d1fc3e1e500013d5b40/"],
    }

    assert collect_feed_ids(hero_links) == [
        "6651d60c99e378294d323998",
        "63a30d1fc3e1e500013d5b40",
    ]


def test_bundle_to_dict_exports_expected_keys():
    bundle = type(
        "Tmp",
        (),
        {
            "hero_name": "司马师",
            "article_url": "https://ds.163.com/article/6651d60c99e378294d323998/",
            "feed_id": "6651d60c99e378294d323998",
            "article": {"x": 1},
            "primary_skill": {"name": "运筹决胜"},
        },
    )()

    data = bundle_to_dict(bundle)

    assert data["hero_name"] == "司马师"
    assert data["primary_skill"]["name"] == "运筹决胜"
