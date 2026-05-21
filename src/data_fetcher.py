from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from src.article_extractor import extract_article_preview, extract_feed_ids_from_links, extract_primary_skill_info


@dataclass
class HeroArticleBundle:
    hero_name: str
    article_url: str
    feed_id: str
    article: dict
    primary_skill: dict


def bundle_hero_article(hero_name: str, article_url: str, feed_id: str | None = None) -> HeroArticleBundle:
    resolved_feed_id = feed_id or article_url.rstrip("/").split("/")[-1]
    preview = extract_article_preview(resolved_feed_id)
    return HeroArticleBundle(
        hero_name=hero_name,
        article_url=article_url,
        feed_id=resolved_feed_id,
        article=asdict(preview),
        primary_skill=extract_primary_skill_info(preview),
    )


def bundle_hero_articles(hero_links: dict[str, list[str]]) -> list[HeroArticleBundle]:
    bundles: list[HeroArticleBundle] = []
    for hero_name, urls in hero_links.items():
        if not urls:
            continue
        bundles.append(bundle_hero_article(hero_name, urls[0]))
    return bundles


def bundle_to_dict(bundle: HeroArticleBundle) -> dict:
    return {
        "hero_name": bundle.hero_name,
        "article_url": bundle.article_url,
        "feed_id": bundle.feed_id,
        "article": bundle.article,
        "primary_skill": bundle.primary_skill,
    }


def collect_feed_ids(hero_links: dict[str, list[str]]) -> list[str]:
    feed_ids: list[str] = []
    for urls in hero_links.values():
        feed_ids.extend(extract_feed_ids_from_links(urls))
    return list(dict.fromkeys(feed_ids))
