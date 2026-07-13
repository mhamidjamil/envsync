"""Interactive prompts — numbered menus, confirmations, text/secret input.

Every prompt honours *non-interactive mode* (``--yes``): when ``assume_yes`` is
True we never block waiting for input. Confirmations auto-accept; a menu with a
declared default auto-selects it, and a menu without one raises rather than
guessing (we never silently pick a destructive branch).
"""

from __future__ import annotations

from rich.prompt import Confirm, Prompt

from envsyncer.ui.console import console
from envsyncer.utils.errors import UserAbort


def confirm(question: str, *, assume_yes: bool = False, default: bool = True) -> bool:
    """Yes/no confirmation. Auto-returns ``True`` under ``--yes``."""
    if assume_yes:
        return True
    return Confirm.ask(question, default=default)


def ask_text(question: str, *, default: str | None = None) -> str:
    """Free-text prompt (never used for secrets)."""
    return Prompt.ask(question, default=default)


def ask_secret(question: str) -> str:
    """Prompt for a secret value with the input hidden."""
    return Prompt.ask(question, password=True).strip()


def select(
    title: str,
    options: list[str],
    *,
    assume_yes: bool = False,
    default_index: int | None = None,
) -> int:
    """Show a numbered menu and return the chosen zero-based index.

    ``default_index`` is auto-selected under ``--yes`` (or when the user hits
    enter). With no default under ``--yes`` we cannot proceed safely, so raise.
    """
    if assume_yes:
        if default_index is None:
            raise UserAbort(f"'{title}' needs a choice but ran with --yes and no default.")
        return default_index

    console.print(f"\n[bold]{title}[/]")
    for i, option in enumerate(options, start=1):
        marker = " [dim](default)[/]" if default_index == i - 1 else ""
        console.print(f"  [cyan]{i}[/]. {option}{marker}")

    choices = [str(i) for i in range(1, len(options) + 1)]
    default = str(default_index + 1) if default_index is not None else None
    answer = Prompt.ask("\n>", choices=choices, default=default, show_choices=False)
    return int(answer) - 1
