from __future__ import annotations

from citecheck_zh.demo import SEED_ERRORS
from citecheck_zh.parse import normalize, parse_document, squash

REF_HEAD = "## 参考文献\n\n"


def test_normalize_fullwidth_to_halfwidth():
    assert normalize("（张三，２０２０）") == "(张三,2020)"


def test_squash_removes_punctuation_and_case():
    assert squash("Soil Respiration: A Review.") == "soilrespirationareview"


def test_section_bounds_and_reference_lines():
    text = "# 标题\n\n正文[1]。\n\n## 参考文献\n\n[1] A. (2020). T. J, 1, 1.\n\n## 附录\n\n尾注。\n"
    doc = parse_document("t.md", text)
    assert doc.section is not None
    assert doc.section.heading_line == 5
    assert doc.section.start == 6
    assert doc.section.end == 9
    assert [ref.line for ref in doc.references] == [7]


def test_reference_section_not_scanned_as_citations():
    text = "正文见[1]。\n\n" + REF_HEAD + "[1] A. (2020). T. J, 1, 1.\n[2] B. (2021). T2. J, 1, 2.\n"
    doc = parse_document("t.md", text)
    assert len(doc.numeric_citations) == 1
    assert doc.numeric_citations[0].line == 1


def test_numeric_groups_expand_ranges():
    text = "见[2,5]与[7-9]。\n\n" + REF_HEAD + "[1] A. (2020). T. J, 1, 1.\n"
    doc = parse_document("t.md", text)
    numbers = [c.numbers for c in doc.numeric_citations]
    assert numbers == [[2, 5], [7, 8, 9]]


def test_fullwidth_brackets_are_numeric_citations():
    text = "见［3］。\n\n" + REF_HEAD + "[1] A. (2020). T. J, 1, 1.\n"
    doc = parse_document("t.md", text)
    assert len(doc.numeric_citations) == 1
    assert doc.numeric_citations[0].numbers == [3]


def test_chinese_author_year_with_deng():
    doc = parse_document("x", "张三等（2021）指出。\n\n" + REF_HEAD + "[1] 张三. (2021). T. J, 1, 1.\n")
    cites = doc.author_year_citations
    assert cites[0].authors == ["张三"]
    assert cites[0].year == 2021


def test_english_et_al_author_year():
    doc = parse_document(
        "x", "Smith et al. (2019) showed.\n\n" + REF_HEAD + "[1] Smith, J. (2019). T. J, 1, 1.\n"
    )
    cites = doc.author_year_citations
    assert cites[0].authors == ["Smith"]
    assert cites[0].year == 2019


def test_ampersand_pair_author_year():
    doc = parse_document(
        "x",
        "（Smith & Jones, 2019）\n\n" + REF_HEAD + "[1] Smith, J., & Jones, K. (2019). T. J, 1, 1.\n",
    )
    assert doc.author_year_citations[0].authors == ["Smith", "Jones"]


def test_multiple_segments_in_one_parenthesis():
    text = "（张三，2020；李四，2019）\n\n" + REF_HEAD + "[1] 张三. (2020). T. J, 1, 1.\n"
    doc = parse_document("x", text)
    assert [(c.authors, c.year) for c in doc.author_year_citations] == [(["张三"], 2020), (["李四"], 2019)]


def test_reference_metadata_skips_doi_digits_for_year():
    doc = parse_document(
        "x", "正文[1]。\n\n" + REF_HEAD + "[1] 王五. 无年份条目. J, 44(5), 500. doi:10.17521/cjpe.2020.0001\n"
    )
    assert doc.references[0].year is None
    assert doc.references[0].doi == "10.17521/cjpe.2020.0001"


def test_duplicate_titles_case_difference_is_similar():
    doc = parse_document(
        "x",
        "正文[1][2]。\n\n" + REF_HEAD
        + "[1] A. (2020). Soil Respiration along a Gradient. J, 1, 1.\n"
        + "[2] B. (2020). soil respiration along a gradient. J, 1, 1.\n",
    )
    assert squash(doc.references[0].title) == squash(doc.references[1].title)


def test_demo_reference_count_and_heading():
    doc = parse_document("demo.md", SEED_ERRORS)
    assert len(doc.references) == 12
    assert doc.section is not None
    assert doc.lines[doc.section.heading_line - 1] == "## 参考文献"


def test_h1_chunks_split_appendix():
    doc = parse_document("demo.md", SEED_ERRORS)
    assert doc.h1_chunks == [1, 40]
    assert doc.chunk_of(42) == 2
    assert doc.chunk_of(5) == 1
