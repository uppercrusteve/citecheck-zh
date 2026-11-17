"""Rules C01-C10 for citation/reference consistency.

Every rule is purely structural: it compares normalized names, numbers,
DOIs and titles.  Severity is fixed per rule and never inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from .parse import Document, normalize, squash

LEVEL_ORDER = {"warning": 1, "error": 2}


@dataclass
class Finding:
    code: str
    level: str
    line: int
    column: int
    message_en: str
    message_zh: str
    snippet: str

    @property
    def message(self) -> str:
        return f"{self.message_zh} / {self.message_en}"

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "level": self.level,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "message_zh": self.message_zh,
            "message_en": self.message_en,
            "snippet": self.snippet,
        }


def _snippet(doc: Document, line: int, column: int, width: int = 70) -> str:
    if not 1 <= line <= len(doc.lines):
        return ""
    text = doc.lines[line - 1].strip()
    if len(text) <= width:
        return text
    start = max(0, column - 1 - width // 3)
    chunk = text[start:start + width]
    prefix = "…" if start > 0 else ""
    suffix = "…" if start + width < len(text) else ""
    return f"{prefix}{chunk}{suffix}"


def _author_matches(left: str, right: str) -> bool:
    left = squash(left)
    right = squash(right)
    if not left or not right:
        return False
    return left == right or left.startswith(right) or right.startswith(left)


def _citation_resolves(doc: Document, citation) -> bool:
    for ref in doc.references:
        if citation.year is not None and ref.year != citation.year:
            continue
        for author in citation.authors:
            if any(_author_matches(author, known) for known in ref.surnames):
                return True
    return False


def _c01_unmatched_citations(doc: Document) -> list[Finding]:
    findings: list[Finding] = []
    for citation in doc.author_year_citations:
        if citation.year is None:
            continue
        if _citation_resolves(doc, citation):
            continue
        names = "、".join(citation.authors)
        findings.append(
            Finding(
                "C01",
                "error",
                citation.line,
                citation.column,
                f"in-text citation has no reference entry: {names} ({citation.year})",
                f"正文引用在文献表中无匹配：{names}（{citation.year}）",
                _snippet(doc, citation.line, citation.column),
            )
        )
    return findings


def _c02_uncited_references(doc: Document) -> list[Finding]:
    findings: list[Finding] = []
    cited_numbers: set[int] = set()
    for citation in doc.numeric_citations:
        cited_numbers.update(citation.numbers)
    for ref in doc.references:
        used = ref.number is not None and ref.number in cited_numbers
        if not used:
            for citation in doc.author_year_citations:
                if citation.year is None:
                    continue
                if citation.year is not None and ref.year != citation.year:
                    continue
                if any(
                    _author_matches(author, known)
                    for author in citation.authors
                    for known in ref.surnames
                ):
                    used = True
                    break
        if used:
            continue
        label = f"[{ref.number}] " if ref.number is not None else ""
        findings.append(
            Finding(
                "C02",
                "error",
                ref.line,
                1,
                "reference entry is never cited in the body",
                f"文献条目从未在正文被引用：{label}{ref.title or ref.text[:40]}",
                _snippet(doc, ref.line, 1),
            )
        )
    return findings


def _c03_duplicates(doc: Document) -> list[Finding]:
    findings: list[Finding] = []
    refs = doc.references
    for i, left in enumerate(refs):
        for right in refs[i + 1:]:
            same_doi = (
                left.doi is not None
                and right.doi is not None
                and normalize(left.doi) == normalize(right.doi)
            )
            similarity = 0.0
            left_title = squash(left.title)
            right_title = squash(right.title)
            if len(left_title) >= 8 and len(right_title) >= 8:
                similarity = SequenceMatcher(None, left_title, right_title).ratio()
            if not same_doi and similarity < 0.9:
                continue
            label_left = f"[{left.number}]" if left.number is not None else f"L{left.line}"
            reason_en = "same DOI" if same_doi else f"title similarity {similarity:.2f}"
            reason_zh = "DOI 相同" if same_doi else f"标题相似度 {similarity:.2f}"
            findings.append(
                Finding(
                    "C03",
                    "error",
                    right.line,
                    1,
                    f"duplicate reference (with {label_left}; {reason_en})",
                    f"文献重复（与 {label_left}；{reason_zh}）",
                    _snippet(doc, right.line, 1),
                )
            )
            break
        else:
            continue
        continue
    return findings


def _c04_numeric_problems(doc: Document) -> list[Finding]:
    numeric = doc.numeric_citations
    if not numeric:
        return []
    findings: list[Finding] = []
    known = {ref.number for ref in doc.references if ref.number is not None}
    numbered = sorted(n for n in known if n is not None)

    for citation in numeric:
        missing = [n for n in citation.numbers if n not in known]
        if missing:
            listed = ", ".join(str(n) for n in missing)
            findings.append(
                Finding(
                    "C04",
                    "error",
                    citation.line,
                    citation.column,
                    f"citation number(s) out of range: {listed}",
                    f"引用编号越界：{listed}",
                    _snippet(doc, citation.line, citation.column),
                )
            )

    for left, right in zip(numbered, numbered[1:], strict=False):
        if right - left <= 1:
            continue
        gap = ", ".join(str(n) for n in range(left + 1, right))
        line = min(
            (ref.line for ref in doc.references if ref.number == right),
            default=1,
        )
        findings.append(
            Finding(
                "C04",
                "error",
                line,
                1,
                f"reference numbering gap before [{right}]: {gap}",
                f"文献编号断档（[{right}] 之前缺 {gap}）",
                _snippet(doc, line, 1),
            )
        )

    seen: set[int] = set()
    highest = 0
    reported: set[int] = set()
    for citation in numeric:
        fresh = [n for n in citation.numbers if n not in seen]
        if not fresh:
            continue
        lowest = min(fresh)
        if lowest < highest and citation.line not in reported:
            findings.append(
                Finding(
                    "C04",
                    "error",
                    citation.line,
                    citation.column,
                    "first appearance order does not follow numbering "
                    f"([{lowest}] appears after [{highest}])",
                    f"首次出现顺序与编号不一致（[{lowest}] 出现在 [{highest}] 之后）",
                    _snippet(doc, citation.line, citation.column),
                )
            )
            reported.add(citation.line)
        seen.update(fresh)
        highest = max(highest, max(fresh))
    return findings


def _c05_missing_year(doc: Document) -> list[Finding]:
    return [
        Finding(
            "C05",
            "error",
            ref.line,
            1,
            "reference entry has no year",
            "文献条目缺年份",
            _snippet(doc, ref.line, 1),
        )
        for ref in doc.references
        if ref.year is None
    ]


def _c06_mixed_styles(doc: Document) -> list[Finding]:
    numeric = doc.numeric_citations
    author_year = doc.author_year_citations
    if not numeric or not author_year:
        return []
    first = min(numeric[0].line, author_year[0].line)
    second_line = max(numeric[0].line, author_year[0].line)
    line = second_line if second_line > first else second_line
    citation = numeric[0] if numeric[0].line == line else author_year[0]
    return [
        Finding(
            "C06",
            "warning",
            citation.line,
            citation.column,
            "both author-year and numeric citation styles are used",
            "同一稿件混用著者-年份与顺序编码两种引用制",
            _snippet(doc, citation.line, citation.column),
        )
    ]


def _c07_bad_doi(doc: Document) -> list[Finding]:
    findings: list[Finding] = []
    for ref in doc.references:
        for bad in ref.bad_dois:
            findings.append(
                Finding(
                    "C07",
                    "error",
                    ref.line,
                    1,
                    f"malformed DOI: {bad}",
                    f"DOI 格式非法：{bad}",
                    _snippet(doc, ref.line, 1),
                )
            )
    return findings


def _c08_missing_section(doc: Document) -> list[Finding]:
    if not doc.citations:
        return []
    section_chunk = doc.chunk_of(doc.section.heading_line) if doc.section else -1
    chunks: dict[int, object] = {}
    for citation in doc.citations:
        chunk = doc.chunk_of(citation.line)
        chunks.setdefault(chunk, citation)
    findings: list[Finding] = []
    for chunk, citation in chunks.items():
        if chunk == section_chunk:
            continue
        findings.append(
            Finding(
                "C08",
                "error",
                citation.line,
                citation.column,
                "citations found but no reference section in this part",
                "本部分有引用但找不到参考文献区",
                _snippet(doc, citation.line, citation.column),
            )
        )
    return findings


def _c09_long_citation(doc: Document) -> list[Finding]:
    findings: list[Finding] = []
    for citation in doc.citations:
        count = len(citation.numbers) if citation.style == "numeric" else len(citation.authors)
        if count <= 8:
            continue
        findings.append(
            Finding(
                "C09",
                "warning",
                citation.line,
                citation.column,
                f"single citation bundles {count} references",
                f"单处引用包含 {count} 篇文献（超过 8 篇）",
                _snippet(doc, citation.line, citation.column),
            )
        )
    return findings


def _c10_missing_citation_year(doc: Document) -> list[Finding]:
    findings: list[Finding] = []
    for citation in doc.author_year_citations:
        if citation.year is not None:
            continue
        names = "、".join(citation.authors)
        findings.append(
            Finding(
                "C10",
                "warning",
                citation.line,
                citation.column,
                f"author-year citation has no year: {names}",
                f"正文引用缺年份：{names}",
                _snippet(doc, citation.line, citation.column),
            )
        )
    return findings


ALL_CHECKS = (
    _c01_unmatched_citations,
    _c02_uncited_references,
    _c03_duplicates,
    _c04_numeric_problems,
    _c05_missing_year,
    _c06_mixed_styles,
    _c07_bad_doi,
    _c08_missing_section,
    _c09_long_citation,
    _c10_missing_citation_year,
)


def run_checks(doc: Document) -> list[Finding]:
    """Run every rule and return findings sorted by position."""
    if doc.section is None:
        checks = (
            _c04_numeric_problems,
            _c06_mixed_styles,
            _c08_missing_section,
            _c09_long_citation,
            _c10_missing_citation_year,
        )
        findings = [finding for check in checks for finding in check(doc)]
    else:
        findings = [finding for check in ALL_CHECKS for finding in check(doc)]
    findings.sort(key=lambda f: (f.line, f.column, f.code))
    return findings


def summarize(findings: list[Finding]) -> dict[str, int]:
    errors = sum(1 for f in findings if f.level == "error")
    warnings = sum(1 for f in findings if f.level == "warning")
    return {"errors": errors, "warnings": warnings, "total": len(findings)}


def filter_by_level(findings: list[Finding], min_level: str) -> list[Finding]:
    threshold = LEVEL_ORDER[min_level]
    return [f for f in findings if LEVEL_ORDER[f.level] >= threshold]
