"""The index: sessions, their chunks, a full-text index, and cached embeddings.

Lives in ~/.mind/mind.db, outside the repo. Sessions and chunks are rebuilt
from scratch on every index run; embeddings are cached by chunk-text hash, so
a rebuild only embeds chunks it has never seen.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from mind.config import DB_PATH
from mind.schema import Entry

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id     INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    start  TEXT NOT NULL,  -- UTC ISO 8601
    label  TEXT NOT NULL,
    meta   TEXT NOT NULL,  -- JSON
    text   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id         INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    ord        INTEGER NOT NULL,
    text       TEXT NOT NULL,
    hash       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_session ON chunks(session_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='id', tokenize='porter unicode61'
);
CREATE TABLE IF NOT EXISTS embeddings (
    hash  TEXT NOT NULL,
    model TEXT NOT NULL,
    vec   BLOB NOT NULL,  -- float32, L2-normalized
    PRIMARY KEY (hash, model)
);
"""


@dataclass
class Chunk:
    id: int
    session_id: int
    source: str
    start: str
    label: str
    meta: dict
    text: str


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


class Store:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path)
        self.con.executescript(SCHEMA)

    def replace(self, items: list[tuple[Entry, str, list[str]]]) -> None:
        """Atomically replace all sessions and chunks. items: (entry, label, chunk_texts)."""
        with self.con:
            self.con.execute("DELETE FROM chunks")
            self.con.execute("DELETE FROM sessions")
            for entry, label, chunks in items:
                cur = self.con.execute(
                    "INSERT INTO sessions (source, start, label, meta, text) VALUES (?, ?, ?, ?, ?)",
                    (entry.source, entry.timestamp, label, json.dumps(entry.meta), entry.text),
                )
                self.con.executemany(
                    "INSERT INTO chunks (session_id, ord, text, hash) VALUES (?, ?, ?, ?)",
                    [(cur.lastrowid, i, c, text_hash(c)) for i, c in enumerate(chunks)],
                )
            self.con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('rebuild')")

    def unembedded(self, model: str) -> list[tuple[str, str]]:
        return self.con.execute(
            "SELECT DISTINCT c.hash, c.text FROM chunks c "
            "LEFT JOIN embeddings e ON e.hash = c.hash AND e.model = ? WHERE e.hash IS NULL",
            (model,),
        ).fetchall()

    def put_embeddings(self, model: str, hashes: list[str], vecs: np.ndarray) -> None:
        vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
        with self.con:
            self.con.executemany(
                "INSERT OR REPLACE INTO embeddings (hash, model, vec) VALUES (?, ?, ?)",
                [(h, model, v.astype(np.float32).tobytes()) for h, v in zip(hashes, vecs)],
            )

    def vectors(self, model: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(chunk_ids, session_starts, matrix) for every embedded chunk."""
        rows = self.con.execute(
            "SELECT c.id, s.start, e.vec FROM chunks c "
            "JOIN sessions s ON s.id = c.session_id "
            "JOIN embeddings e ON e.hash = c.hash AND e.model = ?",
            (model,),
        ).fetchall()
        if not rows:
            return np.array([], dtype=np.int64), np.array([], dtype=str), np.zeros((0, 0), np.float32)
        ids = np.array([r[0] for r in rows], dtype=np.int64)
        starts = np.array([r[1] for r in rows])
        matrix = np.vstack([np.frombuffer(r[2], dtype=np.float32) for r in rows])
        return ids, starts, matrix

    def keyword(self, match: str, limit: int, since: str | None, until: str | None) -> list[int]:
        sql = ("SELECT c.id FROM chunks_fts f JOIN chunks c ON c.id = f.rowid "
               "JOIN sessions s ON s.id = c.session_id WHERE chunks_fts MATCH ?")
        args: list = [match]
        if since:
            sql += " AND s.start >= ?"
            args.append(since)
        if until:
            sql += " AND s.start < ?"
            args.append(until)
        sql += " ORDER BY f.rank LIMIT ?"
        args.append(limit)
        return [r[0] for r in self.con.execute(sql, args)]

    def chunk(self, chunk_id: int) -> Chunk:
        r = self.con.execute(
            "SELECT c.id, c.session_id, s.source, s.start, s.label, s.meta, c.text FROM chunks c "
            "JOIN sessions s ON s.id = c.session_id WHERE c.id = ?",
            (chunk_id,),
        ).fetchone()
        return Chunk(r[0], r[1], r[2], r[3], r[4], json.loads(r[5]), r[6])

    def stats(self) -> dict:
        q = lambda sql: self.con.execute(sql).fetchone()  # noqa: E731
        return {
            "sessions": dict(self.con.execute("SELECT source, COUNT(*) FROM sessions GROUP BY source").fetchall()),
            "chunks": q("SELECT COUNT(*) FROM chunks")[0],
            "embedded": q("SELECT COUNT(DISTINCT hash) FROM embeddings")[0],
            "range": q("SELECT MIN(start), MAX(start) FROM sessions"),
        }
