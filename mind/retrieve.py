"""Hybrid retrieval: BM25 keyword search + embedding search, fused by rank.

Keyword search catches exact names, URLs, commands, and error strings that
embeddings blur together. Embedding search catches paraphrases that share no
words with the query. Reciprocal rank fusion merges the two lists without
needing their scores to be comparable.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

import numpy as np

from mind import ollama
from mind.config import EMBED_MODEL
from mind.store import Chunk, Store

RRF_K = 60
CANDIDATES = 50

STOPWORDS = set("""
a an and are as at be been did do does for from had has have how i in is it its me my
of on or so that the this to was were what when where which who why with you your about
""".split())


class Retriever:
    def __init__(self, store: Store, model: str = EMBED_MODEL):
        self.store = store
        self.model = model
        self.ids, self.starts, self.matrix = store.vectors(model)

    def keyword(self, query: str, since: str | None = None, until: str | None = None) -> list[int]:
        terms = [t for t in re.findall(r"\w+", query.lower()) if t not in STOPWORDS]
        if not terms:
            return []
        match = " OR ".join(f'"{t}"' for t in terms)
        return self.store.keyword(match, CANDIDATES, since, until)

    def semantic(self, query: str, since: str | None = None, until: str | None = None) -> list[int]:
        if not len(self.ids):
            return []
        q = np.asarray(ollama.embed([f"search_query: {query}"], self.model)[0], dtype=np.float32)
        scores = self.matrix @ (q / np.linalg.norm(q))
        if since:
            scores = np.where(self.starts >= since, scores, -np.inf)
        if until:
            scores = np.where(self.starts < until, scores, -np.inf)
        top = np.argsort(-scores)[:CANDIDATES]
        return [int(self.ids[i]) for i in top if np.isfinite(scores[i])]

    def search(self, query: str, k: int = 8, since: str | None = None, until: str | None = None,
               per_session: int = 2) -> list[Chunk]:
        fused: dict[int, float] = defaultdict(float)
        for ranked in (self.keyword(query, since, until), self.semantic(query, since, until)):
            for rank, cid in enumerate(ranked):
                fused[cid] += 1 / (RRF_K + rank)

        # Cap chunks per session so one long page can't crowd out everything else.
        hits, per = [], Counter()
        for cid in sorted(fused, key=fused.get, reverse=True):
            c = self.store.chunk(cid)
            if per[c.session_id] >= per_session:
                continue
            per[c.session_id] += 1
            hits.append(c)
            if len(hits) == k:
                break
        return hits
