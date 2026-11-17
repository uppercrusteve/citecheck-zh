"""Structural parsing for Chinese manuscripts and reference lists.

The parser extracts only structural facts: where citations sit, which
reference entries exist, what DOIs and years appear.  It never tries to
interpret meaning, so downstream checks stay explainable.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

CJK = "一-龥"

HEADING_WORDS = (
    "参考文献",
    "引用文献",
    "references",
    "literature cited",
    "bibliography",
    "works cited",
)

_HEADING_RE = re.compile(
    rf"^(#{{1,6}})\s*({'|'.join(HEADING_WORDS)})\s*[:：]?\s*$",
    re.IGNORECASE,
)
_PLAIN_HEADING_RE = re.compile(
    rf"^\s*({'|'.join(HEADING_WORDS)})\s*[:：]?\s*$", re.IGNORECASE
)
_ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
_NUMBER_MARKER_RE = re.compile(r"^\s*[\[［]\s*(\d+)\s*[\]］]\s*|^\s*(\d+)[.)、]\s+")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+")

_CITATION_NUM_RE = re.compile(r"[\[［]\s*([0-9]+(?:\s*[-–—~,，、]\s*[0-9]+)*)\s*[\]］]")
_PAREN_RE = re.compile(r"[（(]([^（）()]{2,160})[）)]")
_YEAR_RE = re.compile(r"(?<![0-9])((?:19|20)\d{2})([a-z])?(?![0-9])")
_DOI_RE = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
_DOI_CANDIDATE_RE = re.compile(r"10\.[^\s,，;；。]+")
_DOI_URL_RE = re.compile(r"https?://(?:dx\.)?doi\.org/\S+", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

_STOP_WORDS = {
    "et",
    "al",
    "and",
    "the",
    "of",
    "in",
    "on",
    "for",
    "with",
    "eds",
    "ed",
    "by",
}
_CN_LEAD_PARTICLES = "由在见据与和及对从"
_MULTI_AUTHOR_MARKERS = re.compile(r"等|等人|et\s+al\.?|&|\band\b", re.IGNORECASE)

_NARRATIVE_CN_RE = re.compile(
    rf"([{CJK}]{{2,4}})(等|等人)?\s*[（(]\s*((?:19|20)\d{{2}})[a-z]?\s*[)）]"
)
_NARRATIVE_EN_RE = re.compile(
    r"([A-Z][A-Za-z'’\-]+(?:\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z'’\-]+"
    r"|&\s+[A-Z][A-Za-z'’\-]+))?)\s*\(\s*((?:19|20)\d{2})[a-z]?\s*\)"
)


def normalize(text: str) -> str:
    """Full-width to half-width, collapse whitespace, lower-case."""
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def squash(text: str) -> str:
    """Normalized form with all punctuation and whitespace removed."""
    return re.sub(r"[\W_]+", "", normalize(text))


@dataclass
class Reference:
    """One entry in the reference list."""

    line: int
    text: str
    number: int | None = None
    year: int | None = None
    doi: str | None = None
    bad_dois: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    surnames: list[str] = field(default_factory=list)
    title: str = ""


@dataclass
class Citation:
    """One in-text citation occurrence."""

    line: int
    column: int
    style: str
    raw: str
    numbers: list[int] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    year: int | None = None


@dataclass
class ReferenceSection:
    """Reference block bounds.  ``start``/``end`` are 1-based, end exclusive."""

    heading_line: int
    level: int
    start: int
    end: int


@dataclass
class Document:
    """Parsed manuscript."""

    path: str
    lines: list[str]
    citations: list[Citation] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    section: ReferenceSection | None = None
    h1_chunks: list[int] = field(default_factory=list)

    @property
    def numeric_citations(self) -> list[Citation]:
        return [c for c in self.citations if c.style == "numeric"]

    @property
    def author_year_citations(self) -> list[Citation]:
        return [c for c in self.citations if c.style == "author-year"]

    @property
    def style(self) -> str:
        has_num = bool(self.numeric_citations)
        has_ay = bool(self.author_year_citations)
        if has_num and has_ay:
            return "mixed"
        if has_num:
            return "numeric"
        if has_ay:
            return "author-year"
        return "none"

    def chunk_of(self, line: int) -> int:
        """Index of the level-1 heading block that contains ``line``."""
        chunk = 0
        for start in self.h1_chunks:
            if start <= line:
                chunk += 1
        return chunk


def _find_section(lines: list[str]) -> ReferenceSection | None:
    for idx, line in enumerate(lines):
        stripped = line.strip()
        match = _HEADING_RE.match(stripped)
        if match:
            level = len(match.group(1))
            end = len(lines)
            for j in range(idx + 1, len(lines)):
                nested = _ANY_HEADING_RE.match(lines[j].strip())
                if nested and len(nested.group(1)) <= level:
                    end = j
                    break
            return ReferenceSection(idx + 1, level, idx + 2, end + 1)
        if _PLAIN_HEADING_RE.match(stripped) and not stripped.startswith("#"):
            return ReferenceSection(idx + 1, 7, idx + 2, len(lines) + 1)
    return None


def _strip_parens(text: str) -> str:
    return re.sub(r"[（(][^（）()]*[）)]", " ", text)


def _extract_year(text: str) -> int | None:
    cleaned = _DOI_CANDIDATE_RE.sub(" ", text)
    cleaned = _DOI_URL_RE.sub(" ", cleaned)
    cleaned = _URL_RE.sub(" ", cleaned)
    match = _YEAR_RE.search(cleaned)
    if not match:
        return None
    return int(match.group(1))


def _split_authors(prefix: str) -> list[str]:
    prefix = re.sub(r"\bet\s+al\.?", ",", prefix, flags=re.IGNORECASE)
    prefix = prefix.replace("等人", ",").replace("等", ",")
    raw_parts = re.split(r"[,，、;；]", prefix)
    authors: list[str] = []
    for part in raw_parts:
        part = part.strip().strip(".*†‡ ").strip()
        if not part:
            continue
        cn = re.findall(rf"[{CJK}]{{2,4}}", part)
        if cn:
            authors.extend(cn)
            continue
        en = re.findall(r"[A-Z][A-Za-z'’\-]+", part)
        for name in en:
            if name.lower() not in _STOP_WORDS:
                authors.append(name)
    cleaned: list[str] = []
    for name in authors:
        name = name.replace("等人", "")
        if len(name) >= 2 and name.lower() not in _STOP_WORDS:
            if name not in cleaned:
                cleaned.append(name)
    return cleaned


def _split_surnames(authors: list[str]) -> list[str]:
    surnames: list[str] = []
    for name in authors:
        if re.fullmatch(rf"[{CJK}]{{2,4}}", name):
            token = name
        else:
            token = name
        token = normalize(token)
        if token and token not in surnames:
            surnames.append(token)
    return surnames


def _extract_title(text: str, year: int | None) -> str:
    body = text
    if year is not None:
        match = re.search(rf"(?<![0-9]){year}[a-z]?(?![0-9])", body)
        if match:
            body = body[match.end():]
    else:
        body = re.sub(r"^.*?[.。]", "", body, count=1)
    body = body.strip().lstrip(").,，。:：;； ")
    title = re.split(r"[.。?？!！]", body, maxsplit=1)[0]
    return title.strip()[:300]


def _scan_doi(raw: str) -> tuple[str | None, list[str]]:
    valid: list[str] = []
    bad: list[str] = []
    for match in _DOI_CANDIDATE_RE.finditer(raw):
        token = match.group(0).rstrip(".,;:，；。、)")
        candidate = token
        for prefix in ("doi:", "doi：", "DOI:", "DOI："):
            candidate = candidate.removeprefix(prefix).strip()
        if re.fullmatch(r"10\.\d{4,9}/\S+", candidate):
            if not candidate.endswith("/") and candidate not in valid:
                valid.append(candidate)
        elif candidate and candidate not in bad:
            bad.append(candidate)
    for match in _DOI_URL_RE.finditer(raw):
        token = match.group(0).rstrip(".,;:，；。、)")
        candidate = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", token, flags=re.IGNORECASE)
        if not re.fullmatch(r"10\.\d{4,9}/\S+", candidate):
            if candidate and candidate not in bad:
                bad.append(candidate)
    return (valid[0] if valid else None), bad


def _parse_reference(line: int, block: str) -> Reference:
    text = block.strip()
    number: int | None = None
    marker = _NUMBER_MARKER_RE.match(text)
    if marker:
        number = int(marker.group(1) or marker.group(2))
        text = text[marker.end():].strip()
    bullet = _BULLET_RE.match(text)
    if bullet:
        text = text[bullet.end():].strip()
    year = _extract_year(text)
    doi, bad = _scan_doi(text)
    prefix = text
    if year is not None:
        match = re.search(rf"(?<![0-9]){year}[a-z]?(?![0-9])", prefix)
        if match:
            prefix = prefix[: match.start()]
    else:
        prefix = re.split(r"[.。]", prefix, maxsplit=1)[0]
    authors = _split_authors(prefix)
    return Reference(
        line=line,
        text=text,
        number=number,
        year=year,
        doi=doi,
        bad_dois=bad,
        authors=authors,
        surnames=_split_surnames(authors),
        title=_extract_title(text, year),
    )


def _parse_references(lines: list[str], section: ReferenceSection) -> list[Reference]:
    refs: list[Reference] = []
    start_idx = section.start - 1
    end_idx = section.end - 1
    current: list[str] = []
    current_line = 0
    is_numbered = False

    def flush() -> None:
        nonlocal current, current_line, is_numbered
        if current:
            block = " ".join(part.strip() for part in current if part.strip())
            if block:
                refs.append(_parse_reference(current_line, block))
        current = []
        current_line = 0
        is_numbered = False

    for idx in range(start_idx, end_idx):
        raw = lines[idx]
        stripped = raw.strip()
        if not stripped:
            flush()
            continue
        marker = _NUMBER_MARKER_RE.match(stripped)
        bullet = _BULLET_RE.match(stripped)
        if marker or bullet:
            flush()
            current_line = idx + 1
            current = [stripped]
            is_numbered = bool(marker)
            continue
        if not current:
            current_line = idx + 1
            current = [stripped]
            is_numbered = False
            continue
        if is_numbered:
            current.append(stripped)
        else:
            # A new unnumbered entry normally starts after a blank line, but
            # tolerate tight lists by splitting on a terminal period.
            current.append(stripped)
    flush()
    return refs


def _expand_numbers(body: str) -> list[int]:
    numbers: list[int] = []
    for part in re.split(r"[,，、]", body):
        part = part.strip()
        if not part:
            continue
        rng = re.fullmatch(r"(\d+)\s*[-–—~]\s*(\d+)", part)
        if rng:
            low, high = int(rng.group(1)), int(rng.group(2))
            if 0 <= high - low <= 200:
                numbers.extend(range(low, high + 1))
            else:
                numbers.extend([low, high])
            continue
        if re.fullmatch(r"\d+", part):
            numbers.append(int(part))
    seen: list[int] = []
    for num in numbers:
        if num not in seen:
            seen.append(num)
    return seen


def _clean_cn_token(token: str) -> str:
    token = token.strip()
    while token and token[0] in _CN_LEAD_PARTICLES:
        token = token[1:]
    token = token.removesuffix("等人").removesuffix("等")
    return token


def _authors_from_text(text: str) -> list[str]:
    authors: list[str] = []
    for token in re.findall(rf"[{CJK}]{{2,4}}", text):
        token = _clean_cn_token(token)
        if len(token) >= 2 and token not in authors:
            authors.append(token)
    for token in re.findall(r"[A-Z][A-Za-z'’\-]+", text):
        low = token.lower()
        if low in _STOP_WORDS:
            continue
        if token not in authors:
            authors.append(token)
    return authors


def _parse_paren_segment(segment: str) -> tuple[list[str], int | None]:
    segment = segment.strip()
    year_match = _YEAR_RE.search(segment)
    year = int(year_match.group(1)) if year_match else None
    author_part = segment[: year_match.start()] if year_match else segment
    author_part = author_part.strip().strip(",;，；.。 ")
    marker = _MULTI_AUTHOR_MARKERS.search(segment)
    if not year and not marker:
        return [], None
    authors = _authors_from_text(author_part)
    if not authors or len(authors) > 12:
        return [], None
    return authors, year


def _scan_citations(
    lines: list[str],
    section: ReferenceSection | None,
    references: list[Reference],
) -> list[Citation]:
    citations: list[Citation] = []
    known = sorted(
        {name for ref in references for name in ref.surnames}, key=len, reverse=True
    )

    def trim_to_known(token: str) -> str:
        token = _clean_cn_token(token)
        for surname in known:
            if len(token) > len(surname) and normalize(token).endswith(surname):
                return token[-len(surname):]
        return token

    in_fence = False
    for idx, raw in enumerate(lines):
        line_no = idx + 1
        if raw.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if section and section.start <= line_no < section.end:
            continue
        text = unicodedata.normalize("NFKC", raw)

        for match in _CITATION_NUM_RE.finditer(text):
            citations.append(
                Citation(
                    line=line_no,
                    column=match.start() + 1,
                    style="numeric",
                    raw=match.group(0),
                    numbers=_expand_numbers(match.group(1)),
                )
            )

        taken: list[tuple[int, int]] = []
        for match in _NARRATIVE_CN_RE.finditer(text):
            token = trim_to_known(match.group(1))
            if len(token) < 2:
                continue
            citations.append(
                Citation(
                    line=line_no,
                    column=match.start() + 1,
                    style="author-year",
                    raw=match.group(0),
                    authors=[token],
                    year=int(match.group(3)),
                )
            )
            taken.append((match.start(), match.end()))

        for match in _NARRATIVE_EN_RE.finditer(text):
            if any(a <= match.start() < b for a, b in taken):
                continue
            authors = _authors_from_text(match.group(1))
            if not authors:
                continue
            citations.append(
                Citation(
                    line=line_no,
                    column=match.start() + 1,
                    style="author-year",
                    raw=match.group(0),
                    authors=authors,
                    year=int(match.group(2)),
                )
            )
            taken.append((match.start(), match.end()))

        for match in _PAREN_RE.finditer(text):
            if any(a <= match.start() < b for a, b in taken):
                continue
            content = match.group(1).strip()
            if content.lower().startswith("http") or re.fullmatch(r"[\d\s.,，-]+", content):
                continue
            for segment in re.split(r"[;；]", content):
                authors, year = _parse_paren_segment(segment)
                if not authors:
                    continue
                citations.append(
                    Citation(
                        line=line_no,
                        column=match.start() + 1,
                        style="author-year",
                        raw=match.group(0),
                        authors=authors,
                        year=year,
                    )
                )
    citations.sort(key=lambda c: (c.line, c.column))
    return citations


def parse_document(path: str, text: str) -> Document:
    """Parse ``text`` into a :class:`Document`."""
    lines = text.splitlines()
    section = _find_section(lines)
    references = _parse_references(lines, section) if section else []
    citations = _scan_citations(lines, section, references)
    h1_chunks = [
        idx + 1 for idx, line in enumerate(lines) if re.match(r"^#\s+\S", line.strip())
    ]
    return Document(
        path=path,
        lines=lines,
        citations=citations,
        references=references,
        section=section,
        h1_chunks=h1_chunks,
    )
