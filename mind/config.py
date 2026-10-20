"""Paths and model names. Every value can be overridden with an env var."""

from __future__ import annotations

import os
from pathlib import Path

HOME = Path(os.environ.get("MIND_HOME", Path.home() / ".mind"))
DB_PATH = HOME / "mind.db"
SCREENPIPE_DB = Path(os.environ.get("MIND_SCREENPIPE_DB", Path.home() / ".screenpipe" / "db.sqlite"))

_ollama = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_URL = _ollama if _ollama.startswith("http") else f"http://{_ollama}"

EMBED_MODEL = os.environ.get("MIND_EMBED_MODEL", "nomic-embed-text")
CHAT_MODEL = os.environ.get("MIND_CHAT_MODEL", "llama3.2:3b")
