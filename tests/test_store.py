import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from conftest import T0

from mind.store import SCHEMA_VERSION, SchemaVersionError, Store
from mind.visit import Author, Line, Visit


def make_visit(n: int, *lines: Line) -> Visit:
    return Visit(
        source="screenpipe.screen",
        app="Google Chrome",
        title=f"Page {n}",
        url=f"https://site.test/{n}",
        start=T0 + timedelta(hours=n),
        end=T0 + timedelta(hours=n, minutes=30),
        frame_ids=(n * 10, n * 10 + 1, n * 10 + 5),
        lines=lines or (Line(f"read line {n}"), Line(f"typed line {n}", Author.ME)),
    )


def test_schema_created_and_reopen_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "mind.db"
    Store(path).close()
    with Store(path) as store:  # second open must not try to recreate tables
        assert store.con.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_unknown_schema_version_refused(tmp_path: Path) -> None:
    path = tmp_path / "mind.db"
    con = sqlite3.connect(path)
    con.execute("PRAGMA user_version = 99")
    con.close()
    with pytest.raises(SchemaVersionError, match="v99"):
        Store(path)


def test_round_trip(tmp_path: Path) -> None:
    original = make_visit(1)
    with Store(tmp_path / "mind.db") as store:
        store.replace_visits([original])
        assert store.visit(1) == original  # every field, incl. frame IDs and aware datetimes


def test_second_replace_leaves_no_duplicates(tmp_path: Path) -> None:
    with Store(tmp_path / "mind.db") as store:
        store.replace_visits([make_visit(1), make_visit(2)])
        store.replace_visits([make_visit(3)])
        stats = store.stats()
    assert stats.visits == 1
    assert (stats.lines_read, stats.lines_me) == (1, 1)


def test_failure_mid_replace_keeps_previous_data(tmp_path: Path) -> None:
    broken = make_visit(2, Line(None))  # type: ignore[arg-type]  # violates NOT NULL
    with Store(tmp_path / "mind.db") as store:
        store.replace_visits([make_visit(1)])
        with pytest.raises(sqlite3.IntegrityError):
            store.replace_visits([make_visit(5), broken])
        assert store.stats().visits == 1
        assert store.visit(1) == make_visit(1)


def test_lines_filtered_by_author(tmp_path: Path) -> None:
    with Store(tmp_path / "mind.db") as store:
        store.replace_visits([make_visit(1)])
        assert store.lines(1, Author.ME) == [Line("typed line 1", Author.ME)]
        assert store.lines(1, Author.READ) == [Line("read line 1")]


def test_foreign_keys_enforced(tmp_path: Path) -> None:
    with Store(tmp_path / "mind.db") as store, pytest.raises(sqlite3.IntegrityError):
        store.con.execute(
            "INSERT INTO visit_lines (visit_id, ord, author, text) VALUES (404, 0, 'read', 'x')"
        )


def test_unknown_visit_is_none(tmp_path: Path) -> None:
    with Store(tmp_path / "mind.db") as store:
        assert store.visit(1) is None
