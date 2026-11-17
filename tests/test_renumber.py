from __future__ import annotations

import re

import pytest

from citecheck_zh.checks import run_checks
from citecheck_zh.parse import parse_document
from citecheck_zh.renumber import _compress, renumber_document

DOC = """\
# 标题

正文[3]与[1-2]，另见[2]。

## 参考文献

[1] A. (2020). First entry. J, 1, 1. doi:10.1000/a
[2] B. (2021). Second entry. J, 1, 2. doi:10.1000/b
[3] C. (2022). Third entry. J, 1, 3. doi:10.1000/c
"""


def test_renumber_orders_citations_by_first_appearance():
    result, changed, entries = renumber_document(DOC)
    assert changed == 1
    assert entries == 3
    assert "正文[1]与[2,3]，另见[3]。" in result


def test_renumber_keeps_entry_content_with_new_numbers():
    result, _, _ = renumber_document(DOC)
    section = result.split("## 参考文献", 1)[1]
    numbers = [int(n) for n in re.findall(r"^\[(\d+)\]", section, flags=re.MULTILINE)]
    assert numbers == [1, 2, 3]
    assert section.index("Third entry") < section.index("First entry")
    assert section.index("First entry") < section.index("Second entry")
    assert "[1] C. (2022). Third entry." in section
    assert "[3] B. (2021). Second entry." in section


def test_renumber_output_has_no_order_or_gap_errors():
    result, _, _ = renumber_document(DOC)
    findings = run_checks(parse_document("fixed.md", result))
    assert not [f for f in findings if f.code == "C04"]


def test_renumber_preserves_non_citation_text():
    result, _, _ = renumber_document(DOC)
    assert result.startswith("# 标题\n\n")
    assert result.count("正文") == 1
    assert "另见" in result


def test_renumber_leaves_author_year_citations_alone():
    text = "（张三，2020）见[2]。\n\n## 参考文献\n\n[1] A. (2020). T1. J, 1, 1.\n[2] B. (2021). T2. J, 1, 2.\n"
    result, _, _ = renumber_document(text)
    assert "（张三，2020）" in result
    assert "见[1]。" in result


def test_renumber_compresses_runs():
    assert _compress([1, 2, 3]) == "1-3"
    assert _compress([1, 2, 4]) == "1,2,4"
    assert _compress([5]) == "5"


def test_renumber_compact_consecutive_rewrite():
    text = "正文[1,2,3]。\n\n## 参考文献\n\n[1] A. (2020). T1. J, 1, 1.\n[2] B. (2021). T2. J, 1, 2.\n[3] C. (2022). T3. J, 1, 3.\n"
    result, _, _ = renumber_document(text)
    assert "[1-3]" in result


def test_renumber_requires_reference_section():
    with pytest.raises(ValueError, match="reference section"):
        renumber_document("只有正文[1]。")


def test_renumber_requires_numeric_markers():
    text = "正文[1]。\n\n## 参考文献\n\n张三. (2020). T. J, 1, 1.\n"
    with pytest.raises(ValueError, match="numeric"):
        renumber_document(text)


def test_renumber_cli_writes_output(write_doc, tmp_path, capsys):
    from citecheck_zh.cli import main

    source = write_doc(DOC, "in.md")
    target = tmp_path / "out.md"
    assert main(["renumber", source, "-o", str(target)]) == 0
    text = target.read_text(encoding="utf-8")
    assert "正文[1]与[2,3]" in text
    assert "renumbered 3 entries" in capsys.readouterr().out


def test_renumber_missing_input_exits_two(capsys):
    from citecheck_zh.cli import main

    assert main(["renumber", "nope.md"]) == 2
    assert "file not found" in capsys.readouterr().err
