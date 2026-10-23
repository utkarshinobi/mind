import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import MakeScreenpipeDb

from mind.screenpipe import ScreenpipeNotFoundError, iter_frames, open_db, parse_timestamp

ALL_APPS = {"Google Chrome", "Claude", "Finder"}


def test_connection_is_read_only(make_screenpipe_db: MakeScreenpipeDb) -> None:
    path = make_screenpipe_db([{"id": 1, "timestamp": "2026-08-25T19:14:00+00:00"}])
    with open_db(path) as con, pytest.raises(sqlite3.OperationalError, match="readonly"):
        con.execute("DELETE FROM frames")


def test_only_requested_apps_returned(make_screenpipe_db: MakeScreenpipeDb) -> None:
    path = make_screenpipe_db(
        [
            {"id": 1, "timestamp": "2026-08-25T19:00:00+00:00", "app_name": "Google Chrome"},
            {"id": 2, "timestamp": "2026-08-25T19:01:00+00:00", "app_name": "Finder"},
            {"id": 3, "timestamp": "2026-08-25T19:02:00+00:00", "app_name": "Claude"},
        ]
    )
    with open_db(path) as con:
        assert [f.app for f in iter_frames(con, {"Google Chrome", "Claude"})] == [
            "Google Chrome",
            "Claude",
        ]


def test_frames_come_in_time_order(make_screenpipe_db: MakeScreenpipeDb) -> None:
    path = make_screenpipe_db(
        [
            {"id": 1, "timestamp": "2026-08-25T19:05:00+00:00"},
            {"id": 2, "timestamp": "2026-08-25T19:01:00+00:00"},
            {"id": 3, "timestamp": "2026-08-25T19:03:00+00:00"},
        ]
    )
    with open_db(path) as con:
        assert [f.id for f in iter_frames(con, ALL_APPS)] == [2, 3, 1]


@pytest.mark.parametrize(
    "ts",
    ["2026-08-26T02:14:37+00:00", "2026-08-25T19:14:37-07:00", "2026-08-26T02:14:37"],
)
def test_timestamps_normalized_to_utc(ts: str) -> None:
    assert parse_timestamp(ts) == datetime(2026, 8, 26, 2, 14, 37, tzinfo=UTC)


def test_null_columns_become_none(make_screenpipe_db: MakeScreenpipeDb) -> None:
    path = make_screenpipe_db(
        [
            {
                "id": 1,
                "timestamp": "2026-08-25T19:00:00+00:00",
                "browser_url": None,
                "accessibility_tree_json": None,
            }
        ]
    )
    with open_db(path) as con:
        [frame] = iter_frames(con, ALL_APPS)
    assert frame.url is None
    assert frame.tree is None


def test_missing_database_raises_clear_error(tmp_path: Path) -> None:
    with (
        pytest.raises(ScreenpipeNotFoundError, match="not found"),
        open_db(tmp_path / "nope.sqlite"),
    ):
        pass


def test_locked_database_falls_back_to_snapshot(make_screenpipe_db: MakeScreenpipeDb) -> None:
    path = make_screenpipe_db([{"id": 7, "timestamp": "2026-08-25T19:00:00+00:00"}])
    writer = sqlite3.connect(path)
    writer.execute("BEGIN EXCLUSIVE")  # like Screenpipe mid-write
    try:
        with open_db(path, timeout=0.1) as con:
            assert [f.id for f in iter_frames(con, ALL_APPS)] == [7]
    finally:
        writer.rollback()
        writer.close()
