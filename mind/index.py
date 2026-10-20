"""Build the index: Screenpipe DB → sessions → chunks → embeddings."""

from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np

from mind import ollama, sessions
from mind.config import EMBED_MODEL
from mind.ingest import screenpipe_db
from mind.store import Store

BATCH = 64


def build(store: Store, log: Callable[[str], None] = print) -> None:
    t0 = time.time()
    con = screenpipe_db.connect()
    entries = sessions.screen_sessions(screenpipe_db.frames(con))
    entries += sessions.audio_sessions(screenpipe_db.audio(con))
    entries.sort(key=lambda e: e.timestamp)

    items = []
    for e in entries:
        lbl = sessions.label(e)
        # The label goes into every chunk so both keyword and vector search
        # can match on app, page title, URL, and date, not just body text.
        items.append((e, lbl, [f"{lbl}\n{c}" for c in sessions.chunk(e.text)]))
    store.replace(items)
    log(f"sessions: {len(entries)}  chunks: {sum(len(c) for _, _, c in items)}  ({time.time() - t0:.1f}s)")

    todo = store.unembedded(EMBED_MODEL)
    if not todo:
        log("embeddings: all cached")
        return
    log(f"embedding {len(todo)} new chunks with {EMBED_MODEL}...")
    t1 = time.time()
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        # nomic-embed-text is trained with task prefixes; documents and
        # queries must use matching ones.
        vecs = ollama.embed([f"search_document: {text}" for _, text in batch])
        store.put_embeddings(EMBED_MODEL, [h for h, _ in batch], np.asarray(vecs, dtype=np.float32))
        done = min(i + BATCH, len(todo))
        if done % (BATCH * 10) == 0 or done == len(todo):
            rate = done / (time.time() - t1)
            log(f"  {done}/{len(todo)}  ({rate:.0f}/s)")
