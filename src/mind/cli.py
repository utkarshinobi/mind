"""Command-line interface: `mind <command>`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from mind import __version__, config
from mind.clean.privacy import POLICY_TEMPLATE

LEAK_TERMS_TEMPLATE = """\
# Private terms the leak-guard git hook blocks from ever being committed.
# One per line, case-insensitive, at least 3 characters. Lives outside the repo.
# Examples: your personal email, phone number, ID numbers, your bank's name.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mind",
        description="A private memory engine over your own screen history.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.add_parser("init", help="create private config files in MIND_HOME (~/.mind)")
    return parser


def _write_new(path: Path, text: str) -> str:
    if path.exists():
        return f"  exists   {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return f"  created  {path}"


def cmd_init() -> int:
    print("mind init: private files, outside the repo")
    print(_write_new(config.policy_path(), POLICY_TEMPLATE))
    print(_write_new(config.leak_terms_path(), LEAK_TERMS_TEMPLATE))
    print(
        "Next: add your sensitive sites to policy.toml and personal identifiers to leak-terms.txt."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Takes argv and returns an exit code, so tests can call it directly."""
    parser = build_parser()
    args = parser.parse_args(argv)
    match args.command:
        case "init":
            return cmd_init()
        case _:
            parser.print_help(sys.stdout)
            return 0
