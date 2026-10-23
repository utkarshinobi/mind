# 003. Tooling: language, project setup, and how changes land

**Status:** decided, 22 Oct 2026

## Language: Python

Go was considered. It handles nearly all of this app well (pipeline, SQLite, HTTP to local
models, agents, eval). Python won anyway:

| | Python | Go |
|:--|:--|:--|
| Fine-tuning (ch 7-8) | ✅ PyTorch / MLX | ❌ not realistic |
| AI libraries, book ecosystem, tutorials | ✅ where the field works | ⚠️ thinner, more hand-rolled |
| Quick data exploration | ✅ | ⚠️ clunky |
| One language end to end | ✅ | ❌ would still need Python for training |

## Project setup

| Choice | Picked | Why |
|:--|:--|:--|
| Env + dependencies | **uv** | One tool for venv, lockfile, Python version. `uv.lock` makes CI reproducible |
| Format + lint | **ruff** | Replaces black, isort, flake8 in one fast tool |
| Types | **mypy**, strict on `src/` | Catches bugs before running; forces clear function contracts |
| Tests | **pytest** | The standard; fixtures and parametrize keep tests short |
| Layout | **src/** | Tests run against the installed package, so they can't pass by importing loose files |
| Database | stdlib **sqlite3** | No dependency; full-text search (FTS5) is built in |

## How changes land

A **stack of small PRs**, each reviewable on its own and green in CI. Managed with plain
`git` + `gh`: each PR's base is the branch below it. Merged bottom-up with merge commits,
then the next PR is retargeted to `main`.

## Consequences

- Old milestone-0 code (API reader, `Entry` schema) is removed. The direct database reader
  and `Visit`/`Line` types replace it.
- Python returns for fine-tuning in the same codebase, no second language.
