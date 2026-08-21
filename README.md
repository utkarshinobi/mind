# mind

A self-hosted personal memory and idea engine. Built while working through
*AI Engineering* by Chip Huyen, one chapter at a time.

Screen activity is captured by [Screenpipe](https://github.com/screenpipe/screenpipe)
(local, encrypted disk, no cloud transcription). This project starts where
capture ends: normalizing that data into a corpus, evaluating retrieval over it,
and generating ideas from it, all against models I host myself.

## Layout

- `mind/schema.py` — the ingestion contract. Every producer (Screenpipe, phone,
  anything later) normalizes to this one shape.
- `mind/ingest/screenpipe.py` — reads the local Screenpipe API and emits
  normalized entries as JSONL.

## Running

The local Screenpipe API requires a bearer token:

```bash
export MIND_SCREENPIPE_TOKEN="$(cd "$(mktemp -d)" && /Applications/screenpipe.app/Contents/MacOS/bun x screenpipe@latest auth token)"
python3 -m mind.ingest.screenpipe --hours 24
```

Output is one JSON entry per line on stdout; a summary goes to stderr.

## Roadmap

Five artifacts, mapped to the book:

1. Capture-to-corpus pipeline (ch. 1–2)
2. Eval harness with a keyword baseline (ch. 3–4)
3. RAG, measured against that baseline (ch. 5–6)
4. LoRA fine-tune on my own writing (ch. 7–8)
5. Self-hosted serving with vLLM, full system (ch. 9–10)
