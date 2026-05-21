from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.article_extractor import (
    ArticleBlock,
    ArticlePreview,
    SkillSection,
    detect_skill_names,
    extract_anchors,
    extract_feed_ids_from_links,
    extract_primary_skill_info,
    find_skill_text,
    find_anchor_hrefs_by_text,
    split_sections,
    summarize_skill_section,
)


def test_split_sections_groups_main_skill_and_breakdown():
    blocks = [
        ArticleBlock(kind="text", text="武将属性"),
        ArticleBlock(kind="img", src="a.png"),
        ArticleBlock(kind="text", text="主战法解析"),
        ArticleBlock(
            kind="text",
            text="司马师自带战法【运筹决胜】为指挥战法，共有两段效果：",
        ),
        ArticleBlock(
            kind="text",
            text="效果一：自身每次试图发动主动战法时，有30%几率令敌军单体陷入暴走状态，持续1回合。",
        ),
        ArticleBlock(kind="img", src="b.png"),
        ArticleBlock(kind="text", text="战法拆解"),
        ArticleBlock(kind="text", text="司马师可拆解战法为【及锋而试】。"),
    ]

    sections = split_sections(blocks)

    assert [section.title for section in sections] == ["武将属性", "主战法解析", "战法拆解"]
    assert sections[1].paragraphs[0].startswith("司马师自带战法")
    assert sections[2].paragraphs[0].startswith("司马师可拆解战法")


def test_split_sections_recognizes_bracketed_headings():
    blocks = [
        ArticleBlock(kind="text", text="【武将属性】"),
        ArticleBlock(kind="text", text="属性段"),
        ArticleBlock(kind="text", text="【主战法解析】"),
        ArticleBlock(kind="text", text="主战法段"),
        ArticleBlock(kind="text", text="【战法拆解】"),
        ArticleBlock(kind="text", text="拆解段"),
    ]

    sections = split_sections(blocks)

    assert [section.title for section in sections] == ["武将属性", "主战法解析", "战法拆解"]


def test_detect_skill_names_extracts_bracket_names():
    texts = [
        "司马师自带战法【运筹决胜】为指挥战法。",
        "司马师可拆解战法为【及锋而试】。",
    ]

    assert detect_skill_names(texts) == ["运筹决胜", "及锋而试"]


def test_summarize_skill_section_returns_matching_section():
    preview = ArticlePreview(
        feed_id="demo",
        title="demo",
        subtitle="",
        intro="",
        blocks=[],
        sections=[
            SkillSection(title="主战法解析", paragraphs=["a", "b"], images=["x.png"]),
            SkillSection(title="战法拆解", paragraphs=["c"], images=["y.png"]),
        ],
        links=[],
    )

    assert summarize_skill_section(preview, "主战法解析")["paragraph_count"] == 2
    assert summarize_skill_section(preview, "战法拆解")["image_count"] == 1


def test_find_skill_text_collects_relevant_sections():
    preview = ArticlePreview(
        feed_id="demo",
        title="demo",
        subtitle="",
        intro="",
        blocks=[],
        sections=[
            SkillSection(title="武将属性", paragraphs=["ignore"], images=[]),
            SkillSection(title="主战法解析", paragraphs=["keep-1"], images=[]),
            SkillSection(title="战法拆解", paragraphs=["keep-2"], images=[]),
        ],
        links=[],
    )

    assert find_skill_text(preview) == ["keep-1"]


def test_extract_primary_skill_info_uses_main_skill_only():
    preview = ArticlePreview(
        feed_id="demo",
        title="demo",
        subtitle="",
        intro="",
        blocks=[],
        sections=[
            SkillSection(
                title="主战法解析",
                paragraphs=[
                    "司马师自带战法【运筹决胜】为指挥战法，共有两段效果：",
                    "效果一：xxxxx",
                    "效果二：yyyyy",
                ],
                images=["main.png"],
            ),
            SkillSection(
                title="战法拆解",
                paragraphs=["司马师可拆解战法为【及锋而试】。"],
                images=["breakdown.png"],
            ),
        ],
        links=[],
    )

    skill = extract_primary_skill_info(preview)

    assert skill["name"] == "运筹决胜"
    assert skill["title"] == "主战法解析"
    assert skill["paragraph_count"] == 3
    assert skill["image_count"] == 1


def test_extract_primary_skill_info_matches_old_style_heading():
    preview = ArticlePreview(
        feed_id="demo",
        title="demo",
        subtitle="",
        intro="",
        blocks=[],
        sections=[
            SkillSection(
                title="武将主战法解析",
                paragraphs=["战法类型：指挥型战法", "效果：..."],
                images=["main.png"],
            )
        ],
        links=[],
    )

    skill = extract_primary_skill_info(preview)

    assert skill["title"] == "武将主战法解析"
    assert skill["paragraph_count"] == 2


def test_extract_primary_skill_info_matches_very_old_style_heading():
    preview = ArticlePreview(
        feed_id="demo",
        title="demo",
        subtitle="",
        intro="",
        blocks=[],
        sections=[
            SkillSection(
                title="武将主战法",
                paragraphs=["赵云主战法【银龙冲阵】", "效果：..."],
                images=["main.png"],
            )
        ],
        links=[],
    )

    skill = extract_primary_skill_info(preview)

    assert skill["title"] == "武将主战法"
    assert skill["name"] == "银龙冲阵"


def test_extract_primary_skill_info_falls_back_to_raw_blocks():
    preview = ArticlePreview(
        feed_id="demo",
        title="demo",
        subtitle="",
        intro="",
        blocks=[
            ArticleBlock(kind="text", text="吕蒙自带战法【白衣渡江】为指挥型战法。"),
            ArticleBlock(kind="text", text="效果一：..."),
            ArticleBlock(kind="text", text="效果二：..."),
            ArticleBlock(kind="text", text="拆解战法"),
            ArticleBlock(kind="text", text="吕蒙拆解为【神兵天降】。"),
        ],
        sections=[],
        links=[],
    )

    skill = extract_primary_skill_info(preview)

    assert skill["name"] == "白衣渡江"
    assert skill["paragraph_count"] == 3


def test_extract_feed_ids_from_links_picks_article_and_feed_paths():
    links = [
        "https://ds.163.com/article/6358bebc849ee20001053ca3/",
        "https://ds.163.com/feed/63f5a3a93408360001b6b19f/",
        "https://example.com/not-a-feed",
    ]

    assert extract_feed_ids_from_links(links) == [
        "6358bebc849ee20001053ca3",
        "63f5a3a93408360001b6b19f",
    ]


def test_find_anchor_hrefs_by_text_returns_exact_matches():
    anchors = [
        {"text": "司马师", "href": "https://ds.163.com/article/6651d60c99e378294d323998/"},
        {"text": "司马师小乔", "href": "https://ds.163.com/article/638d34850c8dc600014e40b8/"},
        {"text": "司马师", "href": "https://ds.163.com/article/other/"},
    ]

    assert find_anchor_hrefs_by_text(anchors, "司马师") == [
        "https://ds.163.com/article/6651d60c99e378294d323998/",
        "https://ds.163.com/article/other/",
    ]


def test_extract_anchors_keeps_text_and_href():
    html = '<p><a href="https://ds.163.com/article/6651d60c99e378294d323998/">司马师</a></p>'

    anchors = extract_anchors(html)

    assert anchors == [
        {
            "text": "司马师",
            "href": "https://ds.163.com/article/6651d60c99e378294d323998/",
        }
    ]
