"""The visit store: ~/.mind/mind.db, the long-term memory (decision 002, S3 + W2).

Screenpipe deletes raw data after 14 days; this keeps the cleaned visits forever,
with frame IDs pointing back to Screenpipe while the raw frames still exist.
Every `mind clean` replaces all visits in one transaction: readers see either the
old set or the new set, never half of each.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from mind.visit import Author, Line, Visit

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE visits (
    id        INTEGER PRIMARY KEY,
    source    TEXT NOT NULL,
    app       TEXT NOT NULL,
    title     TEXT NOT NULL,
    url       TEXT,
    start_at  TEXT NOT NULL,  -- UTC, ISO 8601
    end_at    TEXT NOT NULL,
    frame_ids TEXT NOT NULL   -- JSON array of Screenpipe frame IDs
);
CREATE TABLE visit_lines (
    visit_id INTEGER NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
    ord      INTEGER NOT NULL,
    author   TEXT NOT NULL CHECK (author IN ('me', 'read')),
    text     TEXT NOT NULL,
    PRIMARY KEY (visit_id, ord)
);
CREATE INDEX visit_lines_author ON visit_lines(author);
"""


class SchemaVersionError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoreStats:
    visits: int
    lines_read: int
    lines_me: int
    first: datetime | None
    last: datetime | None


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.con = sqlite3.connect(path)
        self.con.execute("PRAGMA foreign_keys = ON")  # off by default in SQLite
        self._migrate()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.con.close()

    def _migrate(self) -> None:
        """PRAGMA user_version records which schema the file has. 0 means a new file."""
        version = self.con.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            self.con.executescript(SCHEMA)
            self.con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        elif version != SCHEMA_VERSION:
            raise SchemaVersionError(
                f"{self.path} has schema v{version}; this version of mind expects v{SCHEMA_VERSION}"
            )

    def replace_visits(self, visits: Iterable[Visit]) -> None:
        with self.con:  # one transaction: commits on success, rolls back on any error
            self.con.execute("DELETE FROM visits")  # lines go too, via ON DELETE CASCADE
            for visit in visits:
                cur = self.con.execute(
                    "INSERT INTO visits (source, app, title, url, start_at, end_at, frame_ids) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        visit.source,
                        visit.app,
                        visit.title,
                        visit.url,
                        visit.start.isoformat(),
                        visit.end.isoformat(),
                        json.dumps(visit.frame_ids),
                    ),
                )
                self.con.executemany(
                    "INSERT INTO visit_lines (visit_id, ord, author, text) VALUES (?, ?, ?, ?)",
                    [
                        (cur.lastrowid, i, line.author.value, line.text)
                        for i, line in enumerate(visit.lines)
                    ],
                )

    def lines(self, visit_id: int, author: Author | None = None) -> list[Line]:
        sql = "SELECT text, author FROM visit_lines WHERE visit_id = ?"
        args: list[object] = [visit_id]
        if author is not None:
            sql += " AND author = ?"
            args.append(author.value)
        rows = self.con.execute(sql + " ORDER BY ord", args)
        return [Line(text, Author(a)) for text, a in rows]

    def visit(self, visit_id: int) -> Visit | None:
        row = self.con.execute(
            "SELECT source, app, title, url, start_at, end_at, frame_ids FROM visits WHERE id = ?",
            (visit_id,),
        ).fetchone()
        if row is None:
            return None
        source, app, title, url, start_at, end_at, frame_ids = row
        return Visit(
            source=source,
            app=app,
            title=title,
            url=url,
            start=datetime.fromisoformat(start_at),
            end=datetime.fromisoformat(end_at),
            frame_ids=tuple(json.loads(frame_ids)),
            lines=tuple(self.lines(visit_id)),
        )

    def stats(self) -> StoreStats:
        visits, first, last = self.con.execute(
            "SELECT COUNT(*), MIN(start_at), MAX(start_at) FROM visits"
        ).fetchone()
        by_author = dict(
            self.con.execute("SELECT author, COUNT(*) FROM visit_lines GROUP BY author").fetchall()
        )
        return StoreStats(
            visits=visits,
            lines_read=by_author.get("read", 0),
            lines_me=by_author.get("me", 0),
            first=datetime.fromisoformat(first) if first else None,
            last=datetime.fromisoformat(last) if last else None,
        )
