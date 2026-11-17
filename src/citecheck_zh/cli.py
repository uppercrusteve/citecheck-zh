"""Command line interface for citecheck-zh."""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from . import __version__
from .checks import filter_by_level, run_checks, summarize
from .demo import SEED_ERRORS
from .parse import parse_document
from .renumber import renumber_document
from .report import build_console, render_json, render_table

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_INPUT = 2


def _fail(message: str) -> int:
    print(f"citecheck: {message}", file=sys.stderr)
    return EXIT_INPUT


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        _fail(f"file not found 文件不存在: {path}")
    except IsADirectoryError:
        _fail(f"is a directory 是目录: {path}")
    except UnicodeDecodeError as exc:
        _fail(f"not valid UTF-8 不是 UTF-8 文本: {path} ({exc.reason})")
    except OSError as exc:
        _fail(f"cannot read 无法读取: {path} ({exc.strerror})")
    return None


def _write(path: str, content: str, force: bool) -> bool:
    target = Path(path)
    if target.exists() and not force:
        _fail(f"output exists, use --force 输出已存在: {path}")
        return False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        _fail(f"cannot write 无法写入: {path} ({exc.strerror})")
        return False
    print(f"wrote 已写入: {target}")
    return True


def cmd_check(args: argparse.Namespace) -> int:
    text = _read(args.path)
    if text is None:
        return EXIT_INPUT
    doc = parse_document(args.path, text)
    findings = run_checks(doc)
    total = summarize(findings)
    shown = filter_by_level(findings, args.min_level)

    if args.json:
        payload = render_json(args.path, doc.style, findings, total)
        if args.output:
            return EXIT_OK if _write(args.output, payload + "\n", args.force) else EXIT_INPUT
        print(payload)
    else:
        if args.output:
            buffer = io.StringIO()
            console = build_console("never", stream=buffer)
            render_table(console, args.path, doc.style, shown, total)
            if not _write(args.output, buffer.getvalue(), args.force):
                return EXIT_INPUT
        else:
            console = build_console(args.color)
            render_table(console, args.path, doc.style, shown, total)

    return EXIT_FINDINGS if total["errors"] else EXIT_OK


def cmd_renumber(args: argparse.Namespace) -> int:
    text = _read(args.path)
    if text is None:
        return EXIT_INPUT
    try:
        result, changed, entries = renumber_document(text, args.path)
    except ValueError as exc:
        return _fail(str(exc))
    output = args.output or f"{Path(args.path).stem}.renumbered.md"
    if not _write(output, result, args.force):
        return EXIT_INPUT
    print(f"renumbered {entries} entries, {changed} body line(s) updated")
    return EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    output = args.output
    if not _write(output, SEED_ERRORS, args.force):
        return EXIT_INPUT
    print("demo contains all 10 rule hits (C01-C10); run: citecheck check " + output)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="citecheck",
        description=(
            "中文稿件引文—文献表一致性检查 / "
            "structural citation-reference consistency checker"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subs = parser.add_subparsers(dest="command", required=True)

    check = subs.add_parser(
        "check",
        help="check a manuscript 检查稿件",
        description="Check a UTF-8 Markdown/TXT manuscript and report C01-C10.",
    )
    check.add_argument("path", help="manuscript file 稿件路径")
    check.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    check.add_argument("-o", "--output", help="write the report to a file")
    check.add_argument(
        "--min-level",
        choices=("info", "warning", "error"),
        default="warning",
        help="lowest severity shown (default: warning; errors still set exit code 1)",
    )
    check.add_argument("--force", action="store_true", help="overwrite output file")
    check.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="terminal colour mode (default: auto)",
    )
    check.set_defaults(func=cmd_check)

    renumber = subs.add_parser(
        "renumber",
        help="renumber numeric citations 重排编号",
        description="Renumber citations by first appearance and reorder the list.",
    )
    renumber.add_argument("path", help="manuscript file 稿件路径")
    renumber.add_argument("-o", "--output", help="output file (default: <stem>.renumbered.md)")
    renumber.add_argument("--force", action="store_true", help="overwrite output file")
    renumber.set_defaults(func=cmd_renumber)

    init = subs.add_parser(
        "init",
        help="write a demo manuscript 生成演示稿",
        description="Write a synthetic demo manuscript covering all 10 rules.",
    )
    init.add_argument("-o", "--output", default="demo.md", help="output file (default: demo.md)")
    init.add_argument("--force", action="store_true", help="overwrite output file")
    init.set_defaults(func=cmd_init)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokenPipeError:
        return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
