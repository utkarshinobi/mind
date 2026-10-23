# 002. Store: what we keep per cleaned visit

**Status:** decided, 22 Oct 2026
**Part:** 5. Store (first questions, pulled forward because cleaning decides what we save)
**Book:** ch 6 (RAG), ch 7-8 (finetuning data)

## Context

- Screenpipe is set to **14-day local retention** and actively deletes old data. It is a short-term buffer, not an archive.
- Text typed into text boxes (`AXTextArea`) is the user's own writing: prompts to Claude, Notion notes. Found in 8,810 Chrome, 1,246 Claude, 844 Notion, and 89 VS Code frames.

## Decision

### Q1. Per visit: cleaned text + pointers back to Screenpipe (S3)

Each visit stores its cleaned text, title, URL, start and end time, and the Screenpipe frame IDs it came from. Raw frames are not copied.

| | S1 text only | **S3 text + pointers** | S2 full raw copy |
|:--|:--:|:--:|:--:|
| Size, whole history | ~4 MB | ~4 MB | ~1.5 GB and growing |
| Answer and cite time and page | ✅ | ✅ | ✅ |
| Jump to the exact moment in Screenpipe | ❌ | ✅ | ✅ |
| Re-clean later | ❌ | ✅ within 14 days | ✅ forever |

**Why:** same cost as S1, plus traceability and re-cleaning while raw data exists. S2 duplicates 1.5 GB for the ability to re-clean forever, which isn't needed once cleaning is settled.

### Q2. Your own writing: tag every line `[me]` or `[read]` (W2)

**Why:** a separate collection (W3) is just a filter over the tags, so W2 provides it for free while keeping your line next to what you were responding to. The `[me]` lines are the training set for artifact 4 (finetuning on your writing), exported at that point as a derived file.

## Consequences

- `mind` keeps cleaned text permanently, so it becomes the long-term memory and Screenpipe the short-term buffer.
- Pointers to frames older than 14 days may stop resolving.
- `[me]` means "probably me": reliable in Claude and Notion, less so in Chrome text boxes, which can hold pre-filled or shared text. Accuracy to be checked when Clean is built.

## Follow-up: verified on real data (22 Oct 2026)

First full run: 22,010 frames → 1,421 visits in ~16 s; 638 frames blocked by site; zero
stored visits from a blocked site.

**`[me]` accuracy.** A random sample of 20 Chrome `[me]` lines: 20 of 20 were genuinely typed
by the user (14 code in an online editor, 6 prompts or messages). Known exceptions, outside
Chrome: Terminal and VS Code render their whole buffer as one text area, so command output and
viewed code are tagged `[me]` too. Open question for a follow-up decision.

**Boilerplate vs. typed text.** Of 562 lines judged boilerplate, 67 were typed somewhere. Most
are right to drop (editor starter templates, text-box placeholders like "Write a message…"),
but a phrase the user typed in 8+ visits is dropped as well. Open question: should `[me]`
lines be exempt from the boilerplate rule?
