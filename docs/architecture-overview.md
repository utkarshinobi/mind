## The one-line version

`mind` answers questions about your past by finding what you saw and handing it to a language model.

```
   "what was that article on vector DBs I read last week?"
                            │
                            ▼
                ┌───────────────────────┐
                │         mind          │
                └───────────────────────┘
                            │
                            ▼
   "You read 'Vector DBs explained' on Pinecone's blog on Oct 9 [1]"
```

The model doesn't remember your life. It reads the relevant pieces **at the moment you ask**. That pattern is called **RAG** (retrieval-augmented generation), and it's how most AI apps built on private data work.

---

## Every RAG app has two pipelines

This is the most important idea in the whole design.

```
 PIPELINE 1: INDEXING  (runs in the background, prepares your data)
 ════════════════════════════════════════════════════════════════

  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ 1.Capture│───▶│ 2.Clean  │───▶│ 3.Chunk  │───▶│ 4.Embed  │───▶│ 5.Store  │
  │          │    │          │    │          │    │          │    │          │
  │Screenpipe│    │drop junk,│    │split into│    │text →    │    │database  │
  │records   │    │duplicates│    │memory    │    │numbers   │    │you can   │
  │screen    │    │passwords │    │units     │    │(meaning) │    │search    │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └────┬─────┘
                                                                       │
 PIPELINE 2: ASKING  (runs when you ask a question)                    │
 ══════════════════════════════════════════════════                    │
                                                                       │
  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐         │
  │ 6.Ask    │───▶│7.Retrieve│◀───┼──────────┼────┼──────────┼─────────┘
  │          │    │          │    │          │    │          │
  │your      │    │find the  │───▶│ 8.Prompt │───▶│ 9.Model  │───▶  answer
  │question  │    │8 most    │    │          │    │          │      + sources
  │          │    │relevant  │    │question +│    │LLM reads │
  │          │    │chunks    │    │sources + │    │& writes  │
  │          │    │          │    │rules     │    │answer    │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

**Why split it?** Indexing is slow: embedding thousands of chunks takes minutes. Asking has to be fast: you want an answer in seconds. So the slow work happens ahead of time.

---

## The nine parts

| # | Part | What it does, in one line | Book |
|:--|:--|:--|:--|
| 1 | **Capture** | Records what's on screen and what's said | none (Screenpipe does it) |
| 2 | **Clean** | Removes UI junk, duplicates, private apps | ch 8 |
| 3 | **Chunk** | Cuts data into pieces small enough to search and read | ch 6 |
| 4 | **Embed** | Turns text into numbers so similar meanings land close together | ch 6 |
| 5 | **Store** | Saves chunks and numbers so they can be searched | ch 6 |
| 6 | **Ask** | How you talk to it (terminal, app, chat) | ch 10 |
| 7 | **Retrieve** | Finds the chunks most related to your question | ch 6 |
| 8 | **Prompt** | Packages question + sources + instructions for the model | ch 5 |
| 9 | **Model** | The LLM that reads the sources and writes the answer | ch 2, 9 |

---

## Two more layers that make it good, not just working

```
                      ┌─────────────────────────────────────┐
  10. AGENT           │ Instead of searching once, the model │
  (smarter asking)    │ decides: search again? narrow by     │     ch 6
                      │ date? open the full page? Then       │
                      │ answers. More budget = more digging. │
                      └─────────────────────────────────────┘

                      ┌─────────────────────────────────────┐
  11. EVALUATION      │ 50 questions with known answers.     │
  (is it any good?)   │ Run them after every change. Did the │     ch 3-4
                      │ score go up or down?                 │
                      └─────────────────────────────────────┘
```

**Evaluation is what separates an AI app from an AI demo.** Without it, every change is a guess. With it, you can say "hybrid search beat keyword search by 18%" and know it's true.

---

## Where each part stands

```
  1 Capture     ██████████  done (Screenpipe, hardened)
  2 Clean       ███░░░░░░░  idea proven in prototype, not decided
  3 Chunk       ███░░░░░░░  idea proven in prototype, not decided
  4 Embed       ██░░░░░░░░  model downloaded, not decided
  5 Store       ██░░░░░░░░  prototype only
  6 Ask         ██░░░░░░░░  prototype CLI only
  7 Retrieve    ██░░░░░░░░  prototype only
  8 Prompt      █░░░░░░░░░  prototype only
  9 Model       ███░░░░░░░  Ollama running, 2 models, not decided
 10 Agent       ░░░░░░░░░░  not started
 11 Evaluation  ░░░░░░░░░░  not started
```

"Prototype" means the code exists on the parked branch, but we haven't made the decision together yet.

---

When you say **what next**, I'll take the first part to finalize, lay out the options with diagrams, recommend one, and wait for your call.
