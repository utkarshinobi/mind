"""Shared test fixtures. Every fixture here is synthetic: no real Screenpipe data, ever."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

# The subset of Screenpipe's `frames` table that mind reads.
SCREENPIPE_SCHEMA = """
CREATE TABLE frames (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    app_name TEXT,
    window_name TEXT,
    browser_url TEXT,
    accessibility_tree_json TEXT,
    full_text TEXT
)
"""

FRAME_DEFAULTS: dict[str, Any] = {
    "app_name": "Google Chrome",
    "window_name": "Example - Google Chrome",
    "browser_url": "https://example.com/page",
    "accessibility_tree_json": None,
    "full_text": "example text",
}

MakeScreenpipeDb = Callable[[Sequence[dict[str, Any]]], Path]


@pytest.fixture
def make_screenpipe_db(tmp_path: Path) -> MakeScreenpipeDb:
    """Build a fake Screenpipe database. Each row needs `id` and `timestamp`."""

    def make(rows: Sequence[dict[str, Any]]) -> Path:
        path = tmp_path / "screenpipe.sqlite"
        con = sqlite3.connect(path)
        con.execute(SCREENPIPE_SCHEMA)
        for row in rows:
            full = {**FRAME_DEFAULTS, **row}
            cols = ", ".join(full)
            marks = ", ".join("?" * len(full))
            con.execute(f"INSERT INTO frames ({cols}) VALUES ({marks})", list(full.values()))
        con.commit()
        con.close()
        return path

    return make
