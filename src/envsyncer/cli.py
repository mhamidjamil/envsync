"""Command-line entry point.

Thin wiring only: parse arguments, resolve the ``--yes`` flag, and delegate to
the matching ``commands/*`` module. All business logic lives in ``core`` and
``commands`` so it stays testable without going through Typer.
"""

from __future__ import annotations

from typing import Callable

import typer

from envsyncer import __version__
from envsyncer.commands import add as add_cmd
from envsyncer.commands import doctor as doctor_cmd
from envsyncer.commands import exclude as exclude_cmd
from envsyncer.commands import profile as profile_cmd
from envsyncer.commands import pull as pull_cmd
from envsyncer.commands import push as push_cmd
from envsyncer.commands import setup as setup_cmd
from envsyncer.commands import status as status_cmd
from envsyncer.commands import sync as sync_cmd
from envsyncer.ui.console import error, warn
from envsyncer.utils.errors import EnvSyncerError, UserAbort

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    help="Effortless sync of developer secret files to a private GitHub vault.",
)

_YES = typer.Option(False, "--yes", "-y", help="Assume yes / non-interactive.")


def _guard(func: Callable[..., None], *args: object) -> None:
    """Run a command, turning expected errors into clean exits (no traceback)."""
    try:
        func(*args)
    except UserAbort as exc:
        warn(str(exc))
        raise typer.Exit(1)
    except EnvSyncerError as exc:
        error(str(exc))
        raise typer.Exit(1)
    except KeyboardInterrupt:  # pragma: no cover
        warn("Interrupted.")
        raise typer.Exit(130)


def _yes(ctx: typer.Context, local: bool) -> bool:
    return bool((ctx.obj or {}).get("yes")) or local


@app.callback(invoke_without_command=True)
def _main(
    ctx: typer.Context,
    yes: bool = _YES,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    if version:
        typer.echo(f"envsyncer {__version__}")
        raise typer.Exit()
    ctx.obj = {"yes": yes}
    # Bare `envsyncer` runs the default sync.
    if ctx.invoked_subcommand is None:
        _guard(sync_cmd.run, yes)


@app.command(help="Sync secrets for the current project (same as bare `envsyncer`).")
def sync(ctx: typer.Context, yes: bool = _YES) -> None:
    _guard(sync_cmd.run, _yes(ctx, yes))


@app.command(help="Show what a sync would do, without changing anything.")
def status(ctx: typer.Context, yes: bool = _YES) -> None:
    _guard(status_cmd.run, _yes(ctx, yes))


@app.command(help="Upload all local secrets to the active profile.")
def push(ctx: typer.Context, yes: bool = _YES) -> None:
    _guard(push_cmd.run, _yes(ctx, yes))


@app.command(help="Download the active profile's secrets to local.")
def pull(ctx: typer.Context, yes: bool = _YES) -> None:
    _guard(pull_cmd.run, _yes(ctx, yes))


@app.command(help="View or switch the active profile.")
def profile(ctx: typer.Context, name: str = typer.Argument(None), yes: bool = _YES) -> None:
    _guard(profile_cmd.run, name, _yes(ctx, yes))


@app.command(help="Register an extra secret filename/glob to scan for (e.g. local.properties).")
def add(ctx: typer.Context, pattern: str = typer.Argument(None), yes: bool = _YES) -> None:
    _guard(add_cmd.run, pattern, _yes(ctx, yes))


@app.command(help="Register an extra glob to exclude from scanning (e.g. '*.local').")
def exclude(ctx: typer.Context, pattern: str = typer.Argument(None), yes: bool = _YES) -> None:
    _guard(exclude_cmd.run, pattern, _yes(ctx, yes))


@app.command(help="Re-run first-time setup (auth + vault selection).")
def setup(ctx: typer.Context, yes: bool = _YES) -> None:
    _guard(setup_cmd.run, _yes(ctx, yes))


@app.command(help="Diagnose configuration and connectivity.")
def doctor(ctx: typer.Context, yes: bool = _YES) -> None:
    _guard(doctor_cmd.run, _yes(ctx, yes))


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
