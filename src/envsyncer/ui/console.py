"""Centralised, colored terminal output built on `rich`.

All user-facing printing goes through here so the tool has one consistent
visual language and so tests can capture output from a single place.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

# Semantic glyphs kept in one place so the look stays consistent.
_OK = "[bold green]✓[/]"
_ERR = "[bold red]✗[/]"
_WARN = "[bold yellow]![/]"
_INFO = "[bold cyan]•[/]"
_UP = "[bold green]↑[/]"
_DOWN = "[bold blue]↓[/]"
_DEL = "[bold red]✂[/]"


def success(message: str) -> None:
    console.print(f"{_OK} {message}")


def error(message: str) -> None:
    console.print(f"{_ERR} [red]{message}[/]")


def warn(message: str) -> None:
    console.print(f"{_WARN} [yellow]{message}[/]")


def info(message: str) -> None:
    console.print(f"{_INFO} {message}")


def uploaded(message: str) -> None:
    console.print(f"{_UP} {message}")


def downloaded(message: str) -> None:
    console.print(f"{_DOWN} {message}")


def removed(message: str) -> None:
    console.print(f"{_DEL} [red]{message}[/]")


def plain(message: str = "") -> None:
    console.print(message)


def banner(title: str, subtitle: str = "") -> None:
    """Print a framed welcome/section banner."""
    body = Text(title, style="bold")
    if subtitle:
        body.append("\n" + subtitle, style="dim")
    console.print(Panel(body, border_style="cyan", expand=False))
