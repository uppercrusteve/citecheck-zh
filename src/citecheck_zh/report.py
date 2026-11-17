"""Render findings as a terminal table or as JSON."""

from __future__ import annotations

import json
from collections.abc import Iterable

from rich.console import Console
from rich.table import Table

from . import __version__
from .checks import Finding, summarize

LEVEL_STYLE = {"error": "bold red", "warning": "yellow"}
LEVEL_LABEL = {"error": "error 错误", "warning": "warning 警告"}


def build_console(color: str = "auto", stream=None) -> Console:
    return Console(
        force_terminal=color == "always",
        no_color=color == "never",
        width=110,
        file=stream,
        highlight=False,
        soft_wrap=False,
    )


def render_table(
    console: Console,
    path: str,
    style: str,
    findings: Iterable[Finding],
    total: dict[str, int],
) -> None:
    findings = list(findings)
    console.print(
        f"[bold]citecheck[/bold] v{__version__}  ->  {path}    "
        f"style: [cyan]{style}[/cyan]",
    )
    console.print(
        f"summary 总计: [red]{total['errors']} errors[/red] / "
        f"[yellow]{total['warnings']} warnings[/yellow]",
        highlight=False,
    )
    if not findings:
        console.print("[bold green]未发现问题 / No issues found.[/bold green]")
        return

    table = Table(show_lines=False, header_style="bold", pad_edge=False, expand=True)
    table.add_column("Code", width=5, no_wrap=True)
    table.add_column("Level", width=12, no_wrap=True)
    table.add_column("Line", width=5, justify="right", no_wrap=True)
    table.add_column("Message 说明", ratio=3)
    table.add_column("Source 原文", ratio=2, max_width=38, overflow="ellipsis", no_wrap=True)
    for finding in findings:
        table.add_row(
            finding.code,
            f"[{LEVEL_STYLE[finding.level]}]{LEVEL_LABEL[finding.level]}[/]",
            str(finding.line),
            finding.message,
            f"[dim]{finding.snippet}[/dim]",
        )
    console.print(table)


def render_json(
    path: str,
    style: str,
    findings: Iterable[Finding],
    total: dict[str, int],
) -> str:
    payload = {
        "tool": "citecheck",
        "version": __version__,
        "file": path,
        "style": style,
        "summary": summarize(list(findings)),
        "findings": [f.as_dict() for f in findings],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
