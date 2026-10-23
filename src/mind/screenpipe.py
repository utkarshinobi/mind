"""Read Screenpipe's SQLite database directly, read-only.

Much faster than paging through Screenpipe's REST API. While the Screenpipe app is
running it can hold a lock on the database; then we copy the database and its WAL
to a temporary snapshot and read that instead. The snapshot is deleted on exit.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


class ScreenpipeNotFoundError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class Frame:
    id: int
    time: datetime  # UTC
    app: str | None
    window: str | None
    url: str | None
    tree: str | None  # accessibility_tree_json
    full_text: str | None


def parse_timestamp(ts: str) -> datetime:
    """Screenpipe stores ISO 8601 strings. Normalize to an aware UTC datetime."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


@contextmanager
def open_db(path: Path, timeout: float = 2.0) -> Iterator[sqlite3.Connection]:
    """Open Screenpipe's database read-only, falling back to a snapshot if it's locked."""
    if not path.exists():
        raise ScreenpipeNotFoundError(f"Screenpipe database not found at {path}")
    snapshot_dir: Path | None = None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=timeout)
        con.execute("SELECT 1 FROM frames LIMIT 1")
    except sqlite3.OperationalError as e:
        if "locked" not in str(e).lower():
            raise
        snapshot_dir = Path(tempfile.mkdtemp(prefix="mind-snapshot-"))
        con = _open_snapshot(path, snapshot_dir)
    try:
        yield con
    finally:
        con.close()
        if snapshot_dir:
            shutil.rmtree(snapshot_dir, ignore_errors=True)


def _open_snapshot(path: Path, snapshot_dir: Path) -> sqlite3.Connection:
    for suffix in ("", "-wal"):
        src = Path(f"{path}{suffix}")
        if src.exists():
            shutil.copy2(src, snapshot_dir / f"db.sqlite{suffix}")
    return sqlite3.connect(snapshot_dir / "db.sqlite")


def iter_frames(con: sqlite3.Connection, apps: Iterable[str]) -> Iterator[Frame]:
    """Yield frames from the given apps in time order, one at a time.

    A generator, so ~24k frames with large accessibility trees never sit in memory at once.
    Screenpipe stores timestamps in UTC, so ordering by the string is ordering by time.
    """
    app_list = sorted(apps)
    marks = ",".join("?" * len(app_list))
    rows = con.execute(
        "SELECT id, timestamp, app_name, window_name, browser_url, accessibility_tree_json, "
        f"full_text FROM frames WHERE app_name IN ({marks}) ORDER BY timestamp, id",
        app_list,
    )
    for id_, ts, app, window, url, tree, full_text in rows:
        yield Frame(id_, parse_timestamp(ts), app, window, url, tree, full_text)
