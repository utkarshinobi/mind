"""Answer a question about your past from retrieved sources, with citations."""

from __future__ import annotations

from datetime import datetime

from mind import ollama
from mind.retrieve import Retriever
from mind.store import Chunk

SYSTEM = """You answer questions about the user's own past, using excerpts of what was on \
their screen or said aloud near their computer.

Rules:
- Use only the numbered sources. Cite them inline like [2].
- Each source starts with a line giving when, which app, and which page it came from.
- If the sources don't answer the question, say so plainly, then say what the closest \
sources were about.
- Be concise and specific: names, dates, titles, URLs."""

MAX_SOURCE_CHARS = 1800


def answer(retriever: Retriever, question: str, k: int = 8,
           since: str | None = None, until: str | None = None) -> tuple[str, list[Chunk]]:
    hits = retriever.search(question, k=k, since=since, until=until)
    if not hits:
        return "Nothing in your history matched that.", []

    sources = "\n\n".join(f"[{i}] {h.text[:MAX_SOURCE_CHARS]}" for i, h in enumerate(hits, 1))
    today = datetime.now().astimezone().strftime("%A, %Y-%m-%d")
    prompt = f"Today is {today}.\n\nSources:\n\n{sources}\n\nQuestion: {question}"
    reply = ollama.chat(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.2,
        num_ctx=8192,  # Ollama defaults to 2048, which silently truncates the sources
    )
    return reply.strip(), hits
