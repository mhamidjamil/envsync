"""`envsyncer setup` — (re)run first-run configuration."""

from __future__ import annotations

from envsyncer.core.setup import run_setup


def run(assume_yes: bool = False) -> None:
    run_setup(assume_yes=assume_yes)
