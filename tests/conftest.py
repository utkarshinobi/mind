"""Shared test fixtures. Every fixture here is synthetic: no real Screenpipe data, ever."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from mind.screenpipe import Frame

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


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="rewrite golden files from current output instead of comparing",
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-golden"))


def node(
    text: str,
    role: str = "AXStaticText",
    *,
    left: float = 0.1,
    top: float = 0.1,
    width: float = 0.2,
    height: float = 0.02,
) -> dict[str, Any]:
    """One accessibility-tree node, shaped like Screenpipe's. Positions are screen fractions."""
    return {
        "role": role,
        "text": text,
        "bounds": {"left": left, "top": top, "width": width, "height": height},
    }


def tree(*nodes: dict[str, Any]) -> str:
    return json.dumps(list(nodes))


T0 = datetime(2026, 8, 25, 19, 0, tzinfo=UTC)


def frame(
    id: int,
    *,
    at: timedelta = timedelta(0),
    app: str | None = "Google Chrome",
    url: str | None = "https://example.com/page",
    window: str | None = "Example - Google Chrome",
    tree: str | None = None,
    full_text: str | None = "example text",
) -> Frame:
    """A Frame `at` after T0 (25 Aug 2026, 19:00 UTC)."""
    return Frame(id, T0 + at, app, window, url, tree, full_text)


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
