"""Renumber numeric citations by first appearance and rebuild the list."""

from __future__ import annotations

import re

from .parse import Document, _expand_numbers, parse_document

_NUM_GROUP_RE = re.compile(r"[\[［]\s*([0-9]+(?:\s*[-–—~,，、]\s*[0-9]+)*)\s*[\]］]")


def _compress(numbers: list[int]) -> str:
    parts: list[str] = []
    index = 0
    while index < len(numbers):
        start = numbers[index]
        end = start
        while index + 1 < len(numbers) and numbers[index + 1] == end + 1:
            index += 1
            end = numbers[index]
        if end - start >= 2:
            parts.append(f"{start}-{end}")
        elif end != start:
            parts.append(f"{start},{end}")
        else:
            parts.append(str(start))
        index += 1
    return ",".join(parts)


def _plan(doc: Document) -> tuple[dict[int, int], list]:
    order: list[int] = []
    known = {ref.number for ref in doc.references if ref.number is not None}
    for citation in doc.numeric_citations:
        for number in citation.numbers:
            if number in known and number not in order:
                order.append(number)
    for ref in doc.references:
        if ref.number is not None and ref.number not in order:
            order.append(ref.number)
    mapping = {old: new for new, old in enumerate(order, start=1)}
    # Duplicate entries share a number; keep every one of them in the rebuilt
    # list instead of silently dropping all but the first.
    ordered = [ref for old in order for ref in doc.references if ref.number == old]
    return mapping, ordered


def rewrite_citations(line: str, mapping: dict[int, int]) -> str:
    """Map every numeric citation group on a line, preserving the rest."""

    def replace(match: re.Match[str]) -> str:
        numbers = sorted(
            # Unknown numbers (dangling citations) stay as they are rather
            # than disappearing from the text.
            {mapping.get(n, n) for n in _expand_numbers(match.group(1))}
        )
        if not numbers:
            return match.group(0)
        return f"[{_compress(numbers)}]"

    rewritten = _NUM_GROUP_RE.sub(replace, line)
    if rewritten == line:
        return line
    # Collapse doubled spaces inside the line but leave a trailing double
    # space alone: it is a Markdown hard line break.
    return re.sub(r"(?<=\S)[ \t]{2,}(?=\S)", " ", rewritten)


def renumber_document(text: str, path: str = "<stdin>") -> tuple[str, int, int]:
    """Return ``(new_text, changed_lines, entry_count)``."""
    doc = parse_document(path, text)
    if doc.section is None:
        raise ValueError("no reference section found")
    if not any(ref.number is not None for ref in doc.references):
        raise ValueError("reference list has no numeric markers")
    mapping, ordered = _plan(doc)

    changed = 0
    lines = list(doc.lines)
    section = doc.section
    for idx, line in enumerate(lines):
        if section.start <= idx + 1 < section.end:
            continue
        new_line = rewrite_citations(line, mapping)
        if new_line != line:
            changed += 1
            lines[idx] = new_line

    rebuilt: list[str] = []
    for ref in ordered:
        rebuilt.append(f"[{mapping[ref.number]}] {ref.text}")
        rebuilt.append("")

    heading = doc.lines[section.heading_line - 1]
    body = lines[: section.heading_line - 1]
    tail = lines[section.end - 1:]
    out = body + [heading, ""] + rebuilt
    if tail:
        out.extend(tail)
    result = "\n".join(out).rstrip("\n") + "\n"
    return result, changed, len(ordered)
