from __future__ import annotations

import json

import pytest

from citecheck_zh.checks import filter_by_level, run_checks, summarize
from citecheck_zh.cli import main
from citecheck_zh.demo import CLEAN, SEED_ERRORS
from citecheck_zh.parse import parse_document
from conftest import codes

REF = "## 参考文献\n\n"


def test_c01_unmatched_author_year(run_text):
    _, findings = run_text("正文（张三，2020）。\n\n" + REF + "[1] 李四. (2020). T. J, 1, 1.\n")
    assert "C01" in codes(findings)
    assert findings[0].code == "C01"
    assert findings[0].line == 1


def test_c01_matched_author_year_is_quiet(run_text):
    _, findings = run_text("正文（张三，2020）。\n\n" + REF + "[1] 张三. (2020). T. J, 1, 1.\n")
    assert "C01" not in codes(findings)


def test_c02_uncited_reference(run_text):
    _, findings = run_text(
        "正文[1]。\n\n" + REF + "[1] A. (2020). T1. J, 1, 1.\n[2] B. (2021). T2. J, 1, 2.\n"
    )
    assert codes(findings) == ["C02"]
    assert findings[0].line == 6


def test_c02_all_cited_is_quiet(run_text):
    _, findings = run_text(
        "正文[1][2]。\n\n" + REF + "[1] A. (2020). T1. J, 1, 1.\n[2] B. (2021). T2. J, 1, 2.\n"
    )
    assert findings == []


def test_c03_same_doi_duplicate(run_text):
    _, findings = run_text(
        "正文[1][2]。\n\n" + REF
        + "[1] A. (2020). Alpha title here. J, 1, 1. doi:10.1000/abc\n"
        + "[2] B. (2020). Beta title here. J, 1, 2. doi:10.1000/abc\n"
    )
    assert "C03" in codes(findings)
    assert findings[[f.code for f in findings].index("C03")].line == 6


def test_c03_similar_titles_different_doi(run_text):
    _, findings = run_text(
        "正文[1][2]。\n\n" + REF
        + "[1] A. (2020). Soil respiration along an elevation gradient. J, 1, 1. doi:10.1000/abc\n"
        + "[2] B. (2020). Soil respiration along an elevation gradient. J, 2, 2. doi:10.1000/def\n"
    )
    assert "C03" in codes(findings)


def test_c03_distinct_entries_are_quiet(run_text):
    _, findings = run_text(
        "正文[1][2]。\n\n" + REF
        + "[1] A. (2020). Carbon fluxes in vineyards. J, 1, 1. doi:10.1000/abc\n"
        + "[2] B. (2021). Root turnover in orchards. J, 2, 2. doi:10.1000/def\n"
    )
    assert findings == []


def test_c04_out_of_range(run_text):
    _, findings = run_text("正文[4]。\n\n" + REF + "[1] A. (2020). T. J, 1, 1.\n")
    c04 = [f for f in findings if f.code == "C04"]
    assert len(c04) == 1
    assert c04[0].line == 1


def test_c04_numbering_gap(run_text):
    _, findings = run_text(
        "正文[1][3]。\n\n" + REF + "[1] A. (2020). T1. J, 1, 1.\n[3] C. (2022). T3. J, 1, 3.\n"
    )
    gaps = [f for f in findings if "gap" in f.message_en]
    assert len(gaps) == 1
    assert gaps[0].line == 6


def test_c04_first_appearance_order(run_text):
    _, findings = run_text(
        "正文[2][1]。\n\n" + REF + "[1] A. (2020). T1. J, 1, 1.\n[2] B. (2021). T2. J, 1, 2.\n"
    )
    order = [f for f in findings if "first appearance" in f.message_en]
    assert len(order) == 1
    assert order[0].column > 1


def test_c04_in_order_is_quiet(run_text):
    _, findings = run_text(
        "正文[1][2-3]。\n\n" + REF
        + "[1] A. (2020). T1. J, 1, 1.\n[2] B. (2021). T2. J, 1, 2.\n[3] C. (2022). T3. J, 1, 3.\n"
    )
    assert findings == []


def test_c05_missing_year(run_text):
    _, findings = run_text("正文[1]。\n\n" + REF + "[1] 王五. 无年份. J, 44(5), 500.\n")
    assert "C05" in codes(findings)
    assert findings[[f.code for f in findings].index("C05")].line == 5


def test_c05_entry_with_year_is_quiet(run_text):
    _, findings = run_text("正文[1]。\n\n" + REF + "[1] 王五. (2020). 有年份. J, 44(5), 500.\n")
    assert "C05" not in codes(findings)


def test_c06_mixed_styles(run_text):
    _, findings = run_text(
        "（张三，2020）与[1]。\n\n" + REF + "[1] 张三. (2020). T. J, 1, 1.\n"
    )
    assert codes(findings) == ["C06"]
    assert findings[0].level == "warning"
    assert findings[0].line == 1


def test_c06_single_style_is_quiet(run_text):
    _, findings = run_text("（张三，2020）。\n\n" + REF + "[1] 张三. (2020). T. J, 1, 1.\n")
    assert "C06" not in codes(findings)


def test_c07_malformed_doi(run_text):
    _, findings = run_text("正文[1]。\n\n" + REF + "[1] A. (2020). T. J, 1, 1. doi:10.12345\n")
    assert "C07" in codes(findings)
    assert "10.12345" in findings[[f.code for f in findings].index("C07")].message


def test_c07_doi_too_short_registrant(run_text):
    _, findings = run_text("正文[1]。\n\n" + REF + "[1] A. (2020). T. J, 1, 1. doi:10.12/abc\n")
    assert "C07" in codes(findings)


def test_c07_valid_doi_is_quiet(run_text):
    _, findings = run_text(
        "正文[1]。\n\n" + REF + "[1] A. (2020). T. J, 1, 1. https://doi.org/10.1111/gcb.14000\n"
    )
    assert findings == []


def test_c08_citations_without_section(run_text):
    _, findings = run_text("正文[1]与（张三，2020）。\n")
    c08 = [f for f in findings if f.code == "C08"]
    assert len(c08) == 1
    assert c08[0].level == "error"
    assert c08[0].line == 1


def test_c08_section_present_is_quiet(run_text):
    _, findings = run_text("正文[1]。\n\n" + REF + "[1] A. (2020). T. J, 1, 1.\n")
    assert "C08" not in codes(findings)


def test_c08_appendix_without_references(run_text):
    text = "正文[1]。\n\n" + REF + "[1] A. (2020). T. J, 1, 1.\n\n# 附录\n\n补充[1]。\n"
    _, findings = run_text(text)
    c08 = [f for f in findings if f.code == "C08"]
    assert len(c08) == 1
    assert c08[0].line == 9


def test_c09_more_than_eight_references(run_text):
    body = "正文[1-9]。\n\n" + REF
    body += "".join(f"[{i}] A{i}. (2020). T{i}. J, 1, {i}.\n" for i in range(1, 10))
    _, findings = run_text(body)
    c09 = [f for f in findings if f.code == "C09"]
    assert len(c09) == 1
    assert c09[0].level == "warning"
    assert "9" in c09[0].message_en


def test_c09_eight_references_is_quiet(run_text):
    body = "正文[1-8]。\n\n" + REF
    body += "".join(f"[{i}] A{i}. (2020). T{i}. J, 1, {i}.\n" for i in range(1, 9))
    _, findings = run_text(body)
    assert "C09" not in codes(findings)


def test_c10_citation_without_year(run_text):
    _, findings = run_text("正文（张三等）。\n\n" + REF + "[1] 张三. (2020). T. J, 1, 1.\n")
    c10 = [f for f in findings if f.code == "C10"]
    assert len(c10) == 1
    assert c10[0].level == "warning"
    assert c10[0].line == 1


def test_c10_with_year_is_quiet(run_text):
    _, findings = run_text("正文（张三等，2020）。\n\n" + REF + "[1] 张三. (2020). T. J, 1, 1.\n")
    assert "C10" not in codes(findings)


def test_clean_example_has_zero_findings():
    findings = run_checks(parse_document("clean.md", CLEAN))
    assert findings == []
    assert summarize(findings) == {"errors": 0, "warnings": 0, "total": 0}


def test_demo_hits_all_ten_rules_at_exact_lines():
    findings = run_checks(parse_document("demo.md", SEED_ERRORS))
    pairs = sorted((f.code, f.line) for f in findings)
    assert len({f.code for f in findings}) == 10
    assert pairs == [
        ("C01", 7),
        ("C01", 18),
        ("C02", 37),
        ("C02", 38),
        ("C03", 31),
        ("C04", 11),
        ("C04", 12),
        ("C04", 23),
        ("C05", 30),
        ("C06", 11),
        ("C07", 38),
        ("C08", 42),
        ("C09", 13),
        ("C10", 14),
    ]


def test_filter_by_level_hides_warnings():
    findings = run_checks(parse_document("demo.md", SEED_ERRORS))
    assert all(f.level == "error" for f in filter_by_level(findings, "error"))
    assert filter_by_level(findings, "warning") == findings


def test_empty_file_is_clean(run_text):
    doc, findings = run_text("")
    assert doc.references == []
    assert findings == []


def test_cli_exit_codes_and_clean_run(write_doc, capsys):
    bad = write_doc(SEED_ERRORS, "bad.md")
    good = write_doc(CLEAN, "good.md")
    assert main(["check", bad, "--color", "never"]) == 1
    assert main(["check", good, "--color", "never"]) == 0
    out = capsys.readouterr().out
    assert "No issues found" in out


def test_cli_missing_file_exits_two(capsys):
    assert main(["check", "does-not-exist.md"]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_error_level_still_exits_one(write_doc, capsys):
    bad = write_doc(SEED_ERRORS, "bad.md")
    assert main(["check", bad, "--min-level", "error"]) == 1
    assert "warning 警告" not in capsys.readouterr().out


def test_cli_json_schema(write_doc, capsys):
    bad = write_doc(SEED_ERRORS, "bad.md")
    main(["check", bad, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "citecheck"
    assert payload["summary"]["total"] == len(payload["findings"])
    assert {"code", "level", "line", "column", "message", "snippet"} <= set(payload["findings"][0])


def test_cli_output_file(write_doc, tmp_path):
    bad = write_doc(CLEAN, "good.md")
    target = tmp_path / "report.txt"
    assert main(["check", bad, "-o", str(target), "--force"]) == 0
    assert "No issues found" in target.read_text(encoding="utf-8")


def test_cli_init_writes_demo(tmp_path):
    target = tmp_path / "demo.md"
    assert main(["init", "-o", str(target)]) == 0
    assert target.read_text(encoding="utf-8").count("\n") > 40


@pytest.mark.parametrize("command", ["check", "renumber", "init"])
def test_help_exits_zero(command, capsys):
    with pytest.raises(SystemExit) as exc:
        main([command, "--help"])
    assert exc.value.code == 0
    assert "usage" in capsys.readouterr().out
