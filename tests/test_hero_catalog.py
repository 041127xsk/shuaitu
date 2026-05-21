from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.hero_catalog import HeroRecord, filter_high_star_heroes, resolve_hero_links_from_directory, to_hero_records


def test_filter_high_star_heroes_keeps_sr_and_high_star():
    records = [
        HeroRecord(1, "A", "A", "3-R", 3, "魏", 2.0, "步", "x"),
        HeroRecord(2, "B", "B", "4-SR", 4, "晋", 3.0, "骑", "y"),
        HeroRecord(3, "C", "C", "5-UR", 5, "汉", 4.0, "弓", "z"),
    ]

    filtered = filter_high_star_heroes(records)

    assert [r.name for r in filtered] == ["B", "C"]


def test_to_hero_records_maps_source_fields():
    items = [
        {
            "id": 100701,
            "name": "司马师",
            "uniqueName": "司马师-晋-骑",
            "quality": "4-SR",
            "star": 4,
            "contory": "晋",
            "cost": 2,
            "type": "步",
            "image": "img.png",
        }
    ]

    records = to_hero_records(items)

    assert records[0].name == "司马师"
    assert records[0].faction == "晋"


def test_resolve_hero_links_from_directory_uses_exact_title():
    html = '<p><a href="https://ds.163.com/article/6651d60c99e378294d323998/">司马师</a> <a href="https://ds.163.com/article/x/">司马师小乔</a></p>'

    resolved = resolve_hero_links_from_directory(html, ["司马师", "司马昭"])

    assert resolved["司马师"] == ["https://ds.163.com/article/6651d60c99e378294d323998/"]
    assert resolved["司马昭"] == []
