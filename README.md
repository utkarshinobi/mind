# mind

A self-hosted personal memory and idea engine. Built while working through
*AI Engineering* by Chip Huyen, one chapter at a time.

Screen activity is captured by [Screenpipe](https://github.com/screenpipe/screenpipe)
(local, encrypted disk, no cloud transcription). This project starts where
capture ends: normalizing that data into a corpus, evaluating retrieval over it,
and generating ideas from it, all against models I host myself.

## Layout

```
src/mind/      the app (installed as the `mind` command)
tests/         pytest suite, synthetic fixtures only
decisions/     why each design choice was made
docs/          architecture overview
book/          chapter notes from AI Engineering
```

## Local models

Served by Ollama on `localhost:11434` (`brew services start ollama`).

| Model | Size | Use |
|:--|--:|:--|
| `llama3.2:3b` | 2.0 GB | Default. Non-reasoning, terse, good for extraction and summarization |
| `qwen3:4b` | 2.5 GB | Reasoning model. Keep for tasks that benefit from deliberation |

`qwen3:4b` reasons before answering and ignores `/no_think`, so it needs a much larger
`num_predict` and is a poor fit for structured extraction. Default to `llama3.2:3b`.

## Development

Requires [uv](https://docs.astral.sh/uv/) (`brew install uv`).

```bash
make install    # create .venv, install everything pinned in uv.lock
make check      # format check, lint, type check, tests (same as CI)
make fmt        # auto-format and auto-fix lint
uv run mind --version
```

Output is one JSON entry per line on stdout; a summary goes to stderr.

## Roadmap

Five artifacts, mapped to the book:

1. Capture-to-corpus pipeline (ch. 1–2)
2. Eval harness with a keyword baseline (ch. 3–4)
3. RAG, measured against that baseline (ch. 5–6)
4. LoRA fine-tune on my own writing (ch. 7–8)
5. Self-hosted serving with vLLM, full system (ch. 9–10)
