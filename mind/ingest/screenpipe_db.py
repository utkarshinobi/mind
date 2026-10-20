"""Read Screenpipe's SQLite database directly, read-only.

Much faster than paging through the REST API for a full index build. While the
Screenpipe app is running it can hold a lock on the database; in that case we
copy the database and its WAL to a temporary snapshot and read that instead.
"""

from __future__ import annotations

import atexit
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from pathlib import Path

from mind.config import SCREENPIPE_DB


def connect(path: Path = SCREENPIPE_DB) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"Screenpipe database not found at {path}")
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
        con.execute("SELECT 1 FROM frames LIMIT 1")
        return con
    except sqlite3.OperationalError as e:
        if "locked" not in str(e).lower():
            raise
    return _snapshot(path)


def _snapshot(path: Path) -> sqlite3.Connection:
    snap_dir = Path(tempfile.mkdtemp(prefix="mind-snapshot-"))
    atexit.register(shutil.rmtree, snap_dir, ignore_errors=True)
    for suffix in ("", "-wal"):
        src = Path(f"{path}{suffix}")
        if src.exists():
            shutil.copy2(src, snap_dir / f"db.sqlite{suffix}")
    return sqlite3.connect(snap_dir / "db.sqlite")


def frames(con: sqlite3.Connection) -> Iterator[tuple]:
    """Yield (timestamp, app, window, url, text) in time order."""
    yield from con.execute(
        "SELECT timestamp, app_name, window_name, browser_url, full_text FROM frames "
        "WHERE full_text IS NOT NULL AND full_text != '' ORDER BY timestamp"
    )


def audio(con: sqlite3.Connection) -> Iterator[tuple]:
    """Yield (timestamp, text, speaker_id, is_input_device) in time order."""
    yield from con.execute(
        "SELECT timestamp, transcription, speaker_id, is_input_device FROM audio_transcriptions "
        "WHERE transcription IS NOT NULL AND transcription != '' ORDER BY timestamp"
    )
