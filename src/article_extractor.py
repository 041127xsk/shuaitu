from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from src.http_utils import fetch_with_retry


FEED_FACADE_URL = "https://inf.ds.163.com/v1/web/feed/basic/facade"
DEFAULT_TIMEOUT = 20

SECTION_TITLES = {
    "\u6b66\u5c06\u5c5e\u6027",
    "\u4e3b\u6218\u6cd5\u89e3\u6790",
    "\u6b66\u5c06\u4e3b\u6218\u6cd5\u89e3\u6790",
    "\u6b66\u5c06\u4e3b\u6218\u6cd5",
    "\u6218\u6cd5\u62c6\u89e3",
    "\u6b66\u5c06\u62c6\u89e3\u6218\u6cd5\u89e3\u6790",
    "\u5185\u653f",
    "\u642d\u914d\u601d\u8def",
    "\u51e0\u7ec4\u642d\u914d\u53c2\u8003",
    "\u53ef\u884c\u6027\u642d\u914d \u53c2\u8003",
}


@dataclass
class ArticleBlock:
    kind: str
    text: str | None = None
    src: str | None = None
    href: str | None = None


@dataclass
class SkillSection:
    title: str
    paragraphs: list[str]
    images: list[str]


@dataclass
class ArticlePreview:
    feed_id: str
    title: str
    subtitle: str
    intro: str
    blocks: list[ArticleBlock]
    sections: list[SkillSection]
    links: list[str]
    four_dimensions_image: str | None = None


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def _normalize_heading(value: str | None) -> str:
    text = _normalize_text(value)
    if text.startswith("\u3010") and text.endswith("\u3011"):
        text = text[1:-1].strip()
    return text


def _is_section_heading(value: str | None) -> bool:
    raw = _normalize_text(value)
    heading = _normalize_heading(value)
    if not raw:
        return False

    suffixes = (
        "\u4e3b\u6218\u6cd5\u89e3\u6790",
        "\u6b66\u5c06\u4e3b\u6218\u6cd5\u89e3\u6790",
        "\u6b66\u5c06\u4e3b\u6218\u6cd5",
        "\u6218\u6cd5\u62c6\u89e3",
        "\u6b66\u5c06\u62c6\u89e3\u6218\u6cd5\u89e3\u6790",
        "\u6b66\u5c06\u5c5e\u6027",
        "\u5185\u653f",
        "\u642d\u914d\u601d\u8def",
        "\u642d\u914d\u53c2\u8003",
        "S\u8d5b\u5b63\u642d\u914d\u601d\u8def",
        "S\u8d5b\u5b63\u642d\u914d\u53c2\u8003",
    )

    if raw.startswith("\u3010") and raw.endswith("\u3011"):
        return heading in SECTION_TITLES or any(heading.endswith(suffix) for suffix in suffixes)

    if raw == heading:
        if heading in SECTION_TITLES:
            return True
        if len(heading) <= 24 and any(heading.endswith(suffix) for suffix in suffixes):
            return not any(punct in heading for punct in "\u3002\uff01\uff1f!?;\uff1b\uff1a:")

    return False


def _is_skill_prefix(text: str) -> bool:
    match = re.match(r"^([^\u3010\[\]\uff1a:]{1,12})[:\uff1a]", text)
    if not match:
        return False

    prefix = match.group(1).strip()
    prefix_base = re.split(r"[\uff08(]", prefix, maxsplit=1)[0].strip()
    blocked = {
        "\u603b\u4e4b",
        "\u83b7\u53d6\u9014\u5f84",
        "\u6b66\u5c06\u5b9a\u4f4d",
        "\u961f\u4f0d\u5b9a\u4f4d",
        "\u5e38\u7528\u4f4d\u7f6e",
        "\u5e38\u7528\u6218\u6cd5\u642d\u914d",
        "\u6b66\u5c06\u7b80\u4ecb",
        "\u6b66\u5c06\u5c5e\u6027",
        "\u5175\u79cd",
        "\u53ef\u8f6c\u5175\u79cd",
        "\u653b\u51fb\u8ddd\u79bb",
        "C\u503c",
        "\u4e3b\u8981\u73a9\u6cd5",
        "\u6218\u6cd5\u8be6\u89e3",
        "\u62c6\u89e3\u6218\u6cd5",
        "\u4f7f\u7528\u7ec6\u8282",
        "\u6b66\u5c06\u4e3b\u6218\u6cd5",
        "\u6b66\u5c06\u4e3b\u6218\u6cd5\u89e3\u6790",
        "\u6b66\u5c06\u62c6\u89e3\u6218\u6cd5\u89e3\u6790",
        "\u81ea\u5e26\u6218\u6cd5",
        "\u6218\u6cd5\u7c7b\u578b",
        "\u53d1\u52a8\u7387",
        "\u6548\u679c",
        "\u89e3\u6790",
        "\u4e3b\u8981\u73a9\u6cd5",
        "\u6548\u679c\u4e00",
        "\u6548\u679c\u4e8c",
        "\u6ce8\u610f\u4e8b\u9879",
        "\u62c6\u89e3\u6218\u6cd5",
    }
    return prefix_base not in blocked


def fetch_feed(feed_id: str, *, timeout: int = DEFAULT_TIMEOUT) -> dict:
    try:
        response = fetch_with_retry(
            FEED_FACADE_URL,
            params={"feedId": feed_id, "squareId": ""},
            timeout=timeout,
        )
        payload = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"failed to fetch feed {feed_id}: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"feed {feed_id} returned invalid JSON") from exc

    feed = payload.get("result", {}).get("feed")
    if feed is None:
        raise ValueError(f"feed not found: {feed_id}")
    return feed


def parse_feed_content(feed: dict) -> dict:
    content = feed.get("content")
    if isinstance(content, dict):
        payload = content
    else:
        try:
            payload = json.loads(content or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("feed content is not valid JSON") from exc
    return payload.get("body", {})


def iter_blocks(long_text: str) -> list[ArticleBlock]:
    soup = BeautifulSoup(long_text or "", "html.parser")
    blocks: list[ArticleBlock] = []

    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "img"]):
        if node.name == "img":
            src = node.get("src")
            if src:
                blocks.append(ArticleBlock(kind="img", src=src))
            continue

        text = _normalize_text(node.get_text(" ", strip=True))
        if text:
            href = None
            anchor = node.find("a")
            if anchor is not None:
                href = anchor.get("href")
            blocks.append(ArticleBlock(kind="text", text=text, href=href))

    return blocks


def split_sections(blocks: list[ArticleBlock]) -> list[SkillSection]:
    sections: list[SkillSection] = []
    current_title = ""
    current_paragraphs: list[str] = []
    current_images: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_paragraphs, current_images
        if current_title:
            sections.append(
                SkillSection(
                    title=current_title,
                    paragraphs=current_paragraphs[:],
                    images=current_images[:],
                )
            )
        current_title = ""
        current_paragraphs = []
        current_images = []

    for block in blocks:
        if _is_section_heading(block.text):
            flush()
            current_title = _normalize_heading(block.text)
            continue

        if not current_title:
            continue

        if block.kind == "img" and block.src:
            current_images.append(block.src)
        elif block.text:
            current_paragraphs.append(block.text)

    flush()
    return sections


def _extract_four_dimensions_image(blocks: list[ArticleBlock]) -> str | None:
    """
    从 blocks 中提取四维属性图 URL。

    规律：四维属性图出现在"武将属性"section 内，
    通常紧跟在"武将属性"/"武将基础属性"等标题之后，
    有时中间隔着1-2段描述文本（如"普通张角..."）。

    策略：
    1. 找到含"武将属性"/"基础属性"关键词的 text block（优先靠前的）。
    2. 之后扫描所有后续 block，取第一个 img block 的 src。
       允许跳过描述性文字（如武将名/简介），最多扫描到"主战法"标题出现为止。
    """
    FOUR_DIM_KEYWORDS = ("武将属性", "基础属性", "四维属性")

    heading_idx = -1
    for i, block in enumerate(blocks):
        txt = block.text or ""
        if any(kw in txt for kw in FOUR_DIM_KEYWORDS):
            heading_idx = i
            break
        # 如果 block[0] 直接是 img（非标准文章结构），也尝试取第一张图
        if i == 0 and block.kind == "img" and block.src:
            return block.src

    if heading_idx < 0:
        return None

    # 扫描 heading 之后、主战法 section 之前的 img
    for j in range(heading_idx + 1, len(blocks)):
        nxt = blocks[j]
        if nxt.kind == "img" and nxt.src:
            return nxt.src
        # 遇到主战法章节标题则停止搜索
        if nxt.kind == "text" and nxt.text:
            if "主战法" in nxt.text or "战法解析" in nxt.text:
                break
    return None


def extract_article_preview(feed_id: str) -> ArticlePreview:
    feed = fetch_feed(feed_id)
    return extract_article_preview_from_feed(feed_id, feed)


def extract_article_preview_from_feed(feed_id: str, feed: dict) -> ArticlePreview:
    body = parse_feed_content(feed)
    links = extract_links(body.get("longText", ""))
    blocks = iter_blocks(body.get("longText", ""))
    sections = split_sections(blocks)
    four_dim_img = _extract_four_dimensions_image(blocks)
    return ArticlePreview(
        feed_id=feed_id,
        title=body.get("title", ""),
        subtitle=body.get("subTitle", ""),
        intro=body.get("text", ""),
        blocks=blocks,
        sections=sections,
        links=links,
        four_dimensions_image=four_dim_img,
    )


def preview_to_dict(preview: ArticlePreview) -> dict:
    return {
        "feed_id": preview.feed_id,
        "title": preview.title,
        "subtitle": preview.subtitle,
        "intro": preview.intro,
        "blocks": [asdict(block) for block in preview.blocks],
        "sections": [asdict(section) for section in preview.sections],
        "links": preview.links,
        "four_dimensions_image": preview.four_dimensions_image,
    }


def summarize_skill_section(preview: ArticlePreview, title: str) -> dict:
    for section in preview.sections:
        if section.title == title:
            return {
                "title": section.title,
                "paragraph_count": len(section.paragraphs),
                "image_count": len(section.images),
                "paragraphs": section.paragraphs,
                "images": section.images,
            }

    return {
        "title": title,
        "paragraph_count": 0,
        "image_count": 0,
        "paragraphs": [],
        "images": [],
    }


def find_skill_text(preview: ArticlePreview) -> list[str]:
    collected: list[str] = []
    for section in preview.sections:
        if "\u4e3b\u6218\u6cd5" in section.title and "\u62c6\u89e3" not in section.title:
            collected.extend(section.paragraphs)
    return collected


_SKILL_NAME_BLOCKLIST = {
    "武将基础属性", "武将属性", "主战法解析", "武将主战法", "主战法分析",
    "战法机制解读", "拆解战法", "武将拆解战法解析", "文臣内政", "内政",
    "搭配思路", "推荐搭配", "武将简介", "武将定位",
    "武将技能", "技能解析", "赛季搭配思路", "赛季搭配参考",
    "友情提示", "战法冲突", "其武将成就", "阵容搭配",
    "内政和拆解战法", "特别推荐阵容",
}

def detect_skill_names(texts: Iterable[str]) -> list[str]:
    """从段落中提取【战法名】，过滤掉已知的章节标题和噪声词。"""
    names: list[str] = []
    pattern = re.compile(r"\u3010([^\u3011]{1,20})\u3011")
    for text in texts:
        for match in pattern.findall(text):
            if match not in names and match not in _SKILL_NAME_BLOCKLIST:
                names.append(match)
    return names


def _trim_skill_paragraphs(paragraphs: list[str]) -> list[str]:
    """
    清洗主战法段落，去除结尾广告/水印，保留战法描述和搭配思路。

    策略：
    1. 找到战法名（【...】）首次出现位置，确认有真实战法描述。
    2. 之后遇到"结尾噪声"特征时截断整个后续：
       - 本文毕、欢迎点赞/转发/留言、置顶帖、账号交易
       - 极短段落（< 25 字）且含关注/群聊/二维码等推广词
    3. 对纯小标题行逐条跳过（不截断后续，搭配思路有价值）：
       - 示例/参考/推荐搭配X（纯标题行）
       - 以上战报鸣谢@XXX
       - 大神@XXX 战报
    """
    CUTOFF_PHRASES = (
        "本文毕",
        "欢迎点赞",
        "欢迎转发",
        "欢迎留言",
        "置顶帖",
        "账号交易",
    )
    CUTOFF_SHORT_KEYWORDS = ("关注老碧", "关注作者", "群聊", "二维码")

    SKIP_PATTERNS = (
        re.compile(r"^(示例|参考|推荐)搭配[一二三四五六七八九十\d]?\s*$"),
        re.compile(r"^以上战报鸣谢"),
        re.compile(r"^大神@\S+\s*(战报|分享)?\s*$"),
    )

    # 先过滤广告行（无论在哪个位置）
    paragraphs = [p for p in paragraphs if not _is_ad_line(p)]

    skill_name_idx = -1
    for i, p in enumerate(paragraphs):
        if re.search(r"【[^】]{1,20}】", p):
            skill_name_idx = i
            break

    result: list[str] = []
    for i, p in enumerate(paragraphs):
        after_skill = skill_name_idx >= 0 and i > skill_name_idx

        if after_skill:
            if any(phrase in p for phrase in CUTOFF_PHRASES):
                break
            if len(p) < 25 and any(kw in p for kw in CUTOFF_SHORT_KEYWORDS):
                break
            if any(pat.search(p) for pat in SKIP_PATTERNS):
                continue

        result.append(p)
    return result


def extract_primary_skill_info(preview: ArticlePreview) -> dict:
    main_section = next((section for section in preview.sections if "\u4e3b\u6218\u6cd5" in section.title and "\u62c6\u89e3" not in section.title), None)
    if main_section is None:
        fallback = _extract_primary_skill_from_blocks(preview.blocks)
        if fallback is None:
            return {
                "title": "\u4e3b\u6218\u6cd5\u89e3\u6790",
                "name": "",
                "paragraph_count": 0,
                "image_count": 0,
                "paragraphs": [],
                "images": [],
            }
        return fallback

    skill_names = detect_skill_names(main_section.paragraphs)
    trimmed = _trim_skill_paragraphs(main_section.paragraphs)
    return {
        "title": main_section.title,
        "name": skill_names[0] if skill_names else "",
        "paragraph_count": len(trimmed),
        "image_count": len(main_section.images),
        "paragraphs": trimmed,
        "images": main_section.images,
    }


_AD_PREFIXES = (
    "友情提示",
    "大神快捷充值",
    "老碧账号",
    "可白嫖",
)


def _is_ad_line(text: str) -> bool:
    """判断是否是广告/推广插入行，这类行应在段落解析时忽略。"""
    return any(text.startswith(p) for p in _AD_PREFIXES)


def _extract_primary_skill_from_blocks(blocks: list[ArticleBlock]) -> dict | None:
    start_index = None
    for index, block in enumerate(blocks):
        text = block.text or ""
        if not text:
            continue
        if _is_ad_line(text):  # 跳过广告行，不作为起始点
            continue
        if (
            "\u81ea\u5e26\u6218\u6cd5" in text
            or "\u4e3b\u6218\u6cd5" in text
            or re.match(r"^[【\[][^】\]]{2,12}[】\]]", text)
            or _is_skill_prefix(text)
        ):
            start_index = index
            break

    if start_index is None:
        return None

    paragraphs: list[str] = []
    images: list[str] = []
    title = "\u4e3b\u6218\u6cd5\u89e3\u6790"

    for block in blocks[start_index:]:
        text = block.text or ""
        if text and _is_ad_line(text):  # 跳过正文中混入的广告行
            continue
        if paragraphs and text and (
            "\u62c6\u89e3\u6218\u6cd5" in text
            or "\u6218\u6cd5\u62c6\u89e3" in text
            or "\u6b66\u5c06\u5c5e\u6027" in text
            or "\u5185\u653f" in text
            or "\u4e3b\u8981\u73a9\u6cd5" in text
            or "S\u8d5b\u5b63\u642d\u914d\u53c2\u8003" in text
            or "\u6cd5\u5200" in text
        ):
            break
        if block.kind == "img" and block.src:
            images.append(block.src)
            continue
        if text:
            paragraphs.append(text)

    if not paragraphs:
        return None

    skill_names = detect_skill_names(paragraphs)
    if not skill_names:
        for paragraph in paragraphs:
            match = re.match(r"^([^\u3010\[\]\uff1a:]{2,12})[:\uff1a]", paragraph)
            if match and _is_skill_prefix(paragraph):
                skill_names = [match.group(1).strip()]
                break
    return {
        "title": title,
        "name": skill_names[0] if skill_names else "",
        "paragraph_count": len(paragraphs),
        "image_count": len(images),
        "paragraphs": paragraphs,
        "images": images,
    }


def extract_links(long_text: str) -> list[str]:
    return [item["href"] for item in extract_anchors(long_text)]


def extract_anchors(long_text: str) -> list[dict]:
    soup = BeautifulSoup(long_text or "", "html.parser")
    anchors: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        text = _normalize_text(anchor.get_text(" ", strip=True))
        key = (text, href)
        if key in seen:
            continue
        seen.add(key)
        anchors.append({"text": text, "href": href})
    return anchors


def extract_feed_ids_from_links(links: Iterable[str]) -> list[str]:
    feed_ids: list[str] = []
    seen: set[str] = set()
    for href in links:
        path = urlparse(href).path
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"article", "feed"}:
            feed_id = parts[1]
            if feed_id not in seen:
                seen.add(feed_id)
                feed_ids.append(feed_id)
    return feed_ids


def find_anchor_hrefs_by_text(anchors: Iterable[dict], text: str) -> list[str]:
    hrefs: list[str] = []
    for anchor in anchors:
        if anchor.get("text") == text and anchor.get("href"):
            hrefs.append(anchor["href"])
    return hrefs
