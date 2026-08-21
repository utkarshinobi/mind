"""Screenpipe producer: local REST API -> normalized Entry JSONL on stdout.

Reads via the authenticated API rather than db.sqlite directly; the app holds
a write lock on the database while running.

Usage:
    export MIND_SCREENPIPE_TOKEN=...   # `screenpipe auth token`
    python3 -m mind.ingest.screenpipe --hours 24
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta

from mind.schema import Entry, clean_text

API = "http://localhost:3030"

# Frames from these apps are UI chrome, not thinking.
APP_DENYLIST = {"ControlCenter", "Dock", "loginwindow"}


def raw_sql(query: str, token: str) -> list[dict]:
    req = urllib.request.Request(
        f"{API}/raw_sql",
        data=json.dumps({"query": query}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def cutoff_iso(hours: float) -> str:
    # Frames are stored as ISO 8601 local time with offset; comparing against
    # a cutoff in the same format works as long as the machine's offset is
    # stable across the window.
    return (datetime.now().astimezone() - timedelta(hours=hours)).isoformat()


def fetch_screen(token: str, since: str, limit: int) -> list[Entry]:
    rows = raw_sql(
        "SELECT timestamp, app_name, window_name, browser_url, full_text "
        f"FROM frames WHERE timestamp > '{since}' AND full_text IS NOT NULL "
        f"ORDER BY timestamp LIMIT {limit}",
        token,
    )
    entries: list[Entry] = []
    prev_text = None
    for r in rows:
        if r.get("app_name") in APP_DENYLIST:
            continue
        text = clean_text(r.get("full_text"))
        if not text or text == prev_text:  # drop empties and consecutive dupes
            continue
        prev_text = text
        meta = {k: v for k, v in (
            ("app", r.get("app_name")),
            ("window", r.get("window_name")),
            ("url", r.get("browser_url")),
        ) if v}
        entries.append(Entry("screenpipe.screen", r["timestamp"], text, meta))
    return entries


def fetch_audio(token: str, since: str, limit: int) -> list[Entry]:
    rows = raw_sql(
        "SELECT timestamp, transcription, speaker_id "
        f"FROM audio_transcriptions WHERE timestamp > '{since}' "
        f"ORDER BY timestamp LIMIT {limit}",
        token,
    )
    entries: list[Entry] = []
    for r in rows:
        text = clean_text(r.get("transcription"))
        if not text:
            continue
        meta = {}
        if r.get("speaker_id") is not None:
            meta["speaker_id"] = r["speaker_id"]
        entries.append(Entry("screenpipe.audio", r["timestamp"], text, meta))
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=2000, help="max rows per source")
    args = ap.parse_args()

    token = os.environ.get("MIND_SCREENPIPE_TOKEN")
    if not token:
        print("error: set MIND_SCREENPIPE_TOKEN (see README)", file=sys.stderr)
        return 1

    since = cutoff_iso(args.hours)
    entries = fetch_screen(token, since, args.limit) + fetch_audio(token, since, args.limit)
    entries.sort(key=lambda e: e.timestamp)

    for e in entries:
        print(e.to_json())

    by_source: dict[str, int] = {}
    for e in entries:
        by_source[e.source] = by_source.get(e.source, 0) + 1
    print(
        f"[mind] {len(entries)} entries since {since} "
        + " ".join(f"{k}={v}" for k, v in sorted(by_source.items())),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
