"""mind CLI.

    python3 -m mind index                    rebuild the index from Screenpipe
    python3 -m mind search "query"           show matching sources
    python3 -m mind ask "question"           answer from your history, with citations
    python3 -m mind stats                    what's in the index
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from mind.ollama import OllamaError


def _utc(local_date: str) -> str:
    return datetime.fromisoformat(local_date).astimezone(timezone.utc).isoformat()


def _range(args) -> tuple[str | None, str | None]:
    since = _utc(args.since) if args.since else None
    if args.days:
        since = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()
    until = _utc(args.until) if args.until else None
    return since, until


def _print_sources(hits) -> None:
    for i, h in enumerate(hits, 1):
        print(f"  [{i}] {h.label}")


def main() -> int:
    ap = argparse.ArgumentParser(prog="mind", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index", help="rebuild the index from Screenpipe")
    sub.add_parser("stats", help="show index contents")
    for name in ("search", "ask"):
        p = sub.add_parser(name)
        p.add_argument("query")
        p.add_argument("-k", type=int, default=8, help="number of sources")
        p.add_argument("--since", help="local date, e.g. 2026-09-01")
        p.add_argument("--until", help="local date, exclusive")
        p.add_argument("--days", type=int, help="only the last N days")
    args = ap.parse_args()

    from mind.store import Store
    store = Store()

    try:
        if args.cmd == "index":
            from mind import index
            index.build(store)
        elif args.cmd == "stats":
            s = store.stats()
            print(f"sessions: {s['sessions']}\nchunks:   {s['chunks']}\nembedded: {s['embedded']}")
            print(f"range:    {s['range'][0]} → {s['range'][1]}")
        else:
            from mind.retrieve import Retriever
            retriever = Retriever(store)
            since, until = _range(args)
            if args.cmd == "search":
                hits = retriever.search(args.query, k=args.k, since=since, until=until)
                for i, h in enumerate(hits, 1):
                    body = " ".join(h.text.split("\n", 1)[-1].split())
                    print(f"[{i}] {h.label}\n    {body[:240]}\n")
            else:
                from mind.ask import answer
                text, hits = answer(retriever, args.query, k=args.k, since=since, until=until)
                print(text)
                if hits:
                    print("\nSources:")
                    _print_sources(hits)
    except OllamaError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
