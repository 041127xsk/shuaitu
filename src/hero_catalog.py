from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import requests

from src.article_extractor import extract_anchors, find_anchor_hrefs_by_text
from src.http_utils import fetch_with_retry


WUJIANG_INFO_URL = "https://s.166.net/config/sh_stzb/wujiangInfo.json?_t=1648539610183"


@dataclass(frozen=True)
class HeroRecord:
    id: int
    name: str
    unique_name: str
    quality: str
    star: int
    faction: str
    cost: float
    unit_type: str
    image: str


def fetch_hero_catalog(url: str = WUJIANG_INFO_URL) -> list[dict]:
    response = fetch_with_retry(url)
    payload = response.json()
    if isinstance(payload, dict):
        return list(payload.values())
    if isinstance(payload, list):
        return payload
    raise ValueError("unexpected wujiangInfo payload")


def to_hero_records(items: Iterable[dict]) -> list[HeroRecord]:
    records: list[HeroRecord] = []
    for item in items:
        records.append(
            HeroRecord(
                id=int(item["id"]),
                name=str(item["name"]),
                unique_name=str(item.get("uniqueName", "")),
                quality=str(item.get("quality", "")),
                star=int(item.get("star", 0)),
                faction=str(item.get("contory", "")),
                cost=float(item.get("cost", 0) or 0),
                unit_type=str(item.get("type", "")),
                image=str(item.get("image", "")),
            )
        )
    return records


def filter_high_star_heroes(records: Iterable[HeroRecord]) -> list[HeroRecord]:
    return [record for record in records if record.star >= 4 or record.quality.endswith("SR")]


def resolve_hero_links_from_directory(long_text: str, hero_names: Iterable[str]) -> dict[str, list[str]]:
    anchors = extract_anchors(long_text)
    resolved: dict[str, list[str]] = {}
    for name in hero_names:
        resolved[name] = find_anchor_hrefs_by_text(anchors, name)
    return resolved
