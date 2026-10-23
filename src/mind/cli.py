"""Command-line interface: `mind <command>`."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from mind import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mind",
        description="A private memory engine over your own screen history.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_subparsers(dest="command", metavar="<command>")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Takes argv and returns an exit code, so tests can call it directly."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
    return 0
