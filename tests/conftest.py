from __future__ import annotations

from pathlib import Path

import pytest

from citecheck_zh.checks import run_checks
from citecheck_zh.parse import parse_document


@pytest.fixture
def run_text():
    def _run(text: str, name: str = "t.md"):
        doc = parse_document(name, text)
        return doc, run_checks(doc)

    return _run


@pytest.fixture
def write_doc(tmp_path: Path):
    def _write(text: str, name: str = "t.md") -> str:
        path = tmp_path / name
        path.write_text(text, encoding="utf-8", newline="\n")
        return str(path)

    return _write


def codes(findings) -> list[str]:
    return [f.code for f in findings]
