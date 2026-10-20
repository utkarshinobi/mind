"""Thin client for the local Ollama server: embeddings and chat."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from mind.config import CHAT_MODEL, EMBED_MODEL, OLLAMA_URL


class OllamaError(RuntimeError):
    pass


def _post(path: str, payload: dict, timeout: float = 600) -> dict:
    req = urllib.request.Request(
        OLLAMA_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise OllamaError(f"Ollama {path} failed ({e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise OllamaError(
            f"Ollama is not reachable at {OLLAMA_URL}. Start it with `brew services start ollama`."
        ) from e


def embed(texts: list[str], model: str = EMBED_MODEL) -> list[list[float]]:
    return _post("/api/embed", {"model": model, "input": texts})["embeddings"]


def chat(messages: list[dict], model: str = CHAT_MODEL, **options) -> str:
    resp = _post("/api/chat", {"model": model, "messages": messages, "stream": False, "options": options})
    return resp["message"]["content"]
