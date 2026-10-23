# 001. Clean: what goes into the index

**Status:** decided, 22 Oct 2026
**Part:** 2. Clean (indexing pipeline)
**Book:** ch 8 (dataset engineering)

## Context

Screenpipe had captured 24,096 frames by mid-October. Three problems showed up in the real data:

| Problem | Evidence |
|:--|:--|
| Private apps leaking in | 36 frames from Apple Passwords, 29 from Find My, despite an ignore list |
| Massive repetition | Consecutive frames are 93% identical. One 75-minute LeetCode visit = 560 frames |
| UI noise | About a third of on-screen text is controls (buttons, checkboxes, dropdowns) |

Each frame carries two versions of the screen: `full_text` (flat lines) and `accessibility_tree_json` (every text node with its role and screen position).

## Decision

### 2a. Privacy: allowlist of apps + URL blocklist

Only listed apps are indexed (Chrome, Claude, Code, Notion, Preview). Sensitive sites inside allowed apps are blocked by URL.

**Why:** a denylist already failed once (Apple Passwords got through because nobody listed it). An allowlist fails safe, and the five apps cover ~98% of captured text.

### 2b. Duplicates: each line once per page visit

Frames from one page visit are merged. Each distinct line is kept once, in first-seen order.

**Why:** dropping exact duplicates barely helps, since frames are rarely byte-identical. Line-level merging shrinks 24k frames to ~1,300 visits with no text lost.

### 2c. Noise: structure first, then statistics (N5)

1. **Structure.** Drop text the accessibility tree marks as a control (button, radio button, checkbox, dropdown). Glue text on the same screen row back into sentences.
2. **Statistics.** Drop short lines that appear on 8+ different pages.

Tested on 15 real lines from one LeetCode frame (8 junk, 7 real):

| Option | Junk removed | Real text lost | Sentences whole |
|:--|:--:|:--:|:--:|
| N1 keep | 0 of 8 | 0 of 7 | no |
| N3 statistics only | 8 of 8 | 3 of 7 (`Hard`, `nums`, `, return`) | no |
| N4 structure only | 4 of 8 | 0 of 7 | yes |
| **N5 structure + stats** | **8 of 8** | **1 of 7** (`Hard`) | **yes** |

**Why:** statistics alone drops real words like `nums` because they appear on 36 problem pages. Running structure first glues `nums` into its sentence, which appears on only 2 pages, so it survives.

## Consequences

- Cleaned text is ~10,000× smaller than raw (33 MB → 3 KB for one visit).
- Occasionally loses a short real word that sits alone on its row (e.g. difficulty labels).
- The allowlist must be updated by hand when a new useful app appears.
