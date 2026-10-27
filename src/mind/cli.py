"""Command-line interface: `mind <command>`.

mind init                 create private config files in ~/.mind
mind clean                Screenpipe -> clean visits in ~/.mind/mind.db
mind show VISIT_ID        print one visit's lines
mind stats                what's in the store
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from mind import __version__, config
from mind.clean import CleanStats, clean
from mind.clean.privacy import POLICY_TEMPLATE, PolicyError, load_policy
from mind.screenpipe import ScreenpipeNotFoundError, iter_frames, open_db
from mind.store import Store
from mind.visit import Author

log = logging.getLogger("mind")

LEAK_TERMS_TEMPLATE = """\
# Private terms the leak-guard git hook blocks from ever being committed.
# One per line, case-insensitive, at least 3 characters. Lives outside the repo.
# Examples: your personal email, phone number, ID numbers, your bank's name.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mind",
        description="A private memory engine over your own screen history.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    sub.add_parser("init", help="create private config files in MIND_HOME (~/.mind)")

    p = sub.add_parser("clean", help="rebuild clean visits from Screenpipe")
    p.add_argument("--screenpipe-db", type=Path, help="default: ~/.screenpipe/db.sqlite")
    p.add_argument("--db", type=Path, help="default: ~/.mind/mind.db")

    p = sub.add_parser("show", help="print one visit")
    p.add_argument("visit_id", type=int)
    p.add_argument("--author", choices=[a.value for a in Author], help="only these lines")
    p.add_argument("--db", type=Path)

    p = sub.add_parser("stats", help="summarize the store")
    p.add_argument("--db", type=Path)
    return parser


def fail(message: str) -> int:
    print(f"mind: {message}", file=sys.stderr)
    return 1


def local(dt: datetime) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


# --- init -------------------------------------------------------------------


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


# --- clean ------------------------------------------------------------------


def cmd_clean(screenpipe_db: Path, db: Path) -> int:
    try:
        policy = load_policy(config.policy_path())
    except PolicyError as e:
        return fail(str(e))  # refuse to index anything without the personal blocklist

    started = time.monotonic()
    log.info("reading %s", screenpipe_db)
    try:
        with open_db(screenpipe_db) as con:
            result = clean(iter_frames(con, policy.apps), policy)
    except ScreenpipeNotFoundError as e:
        return fail(str(e))

    with Store(db) as store:
        store.replace_visits(result.visits)
    print_summary(result.stats, db, time.monotonic() - started)
    return 0


def print_summary(s: CleanStats, db: Path, seconds: float) -> None:
    print(f"Cleaned {s.frames_read:,} frames in {seconds:.1f}s")
    print(f"  kept         {s.frames_kept:,}")
    print(
        f"  blocked      {s.blocked_app:,} by app · {s.blocked_host:,} by site · "
        f"{s.blocked_no_url:,} browser screens with no URL"
    )
    print(f"Visits         {s.visits:,}  →  {db}")
    print(f"Lines          {s.lines_read:,} read · {s.lines_me:,} me")
    print(f"Boilerplate    {s.boilerplate_dropped:,} lines dropped")
    print(
        f"Skipped        {s.visits_without_text:,} visits with no text · "
        f"{s.visits_emptied:,} only boilerplate"
    )


# --- show / stats -----------------------------------------------------------


def cmd_show(visit_id: int, author: str | None, db: Path) -> int:
    with Store(db) as store:
        visit = store.visit(visit_id)
        if visit is None:
            return fail(f"no visit #{visit_id} in {db}")
        lines = store.lines(visit_id, Author(author) if author else None)
    ids = visit.frame_ids
    print(f"#{visit_id} · {local(visit.start)} → {local(visit.end)} · {visit.app} · {visit.title}")
    if visit.url:
        print(visit.url)
    print(f"{len(ids)} frames ({ids[0]} … {ids[-1]})\n" if ids else "0 frames\n")
    for line in lines:
        print(f"[{line.author}] {line.text}")
    return 0


def cmd_stats(db: Path) -> int:
    with Store(db) as store:
        s = store.stats()
    print(f"Store    {db}")
    print(f"Visits   {s.visits:,}")
    print(f"Lines    {s.lines_read:,} read · {s.lines_me:,} me")
    if s.first and s.last:
        print(f"Range    {local(s.first)} → {local(s.last)}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Takes argv and returns an exit code, so tests can call it directly."""
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    db = getattr(args, "db", None) or config.db_path()
    match args.command:
        case "init":
            return cmd_init()
        case "clean":
            return cmd_clean(args.screenpipe_db or config.screenpipe_db_path(), db)
        case "show":
            return cmd_show(args.visit_id, args.author, db)
        case "stats":
            return cmd_stats(db)
        case _:
            parser.print_help(sys.stdout)
            return 0
