# 004. Leak guards: keeping personal data out of a public repo

**Status:** decided, 22 Oct 2026

## Context

The repo is public, and the app processes a full screen history. An audit before building
found history clean, but two exposures: commit metadata carried a personal email, and the
first plan draft put a personal URL blocklist (which sites are sensitive *to me*) into source
code. A blocklist is itself personal data.

## Decision

Three gates, plus a design rule.

```
 LAPTOP                                                 GITHUB (public)
  commit ──▶ GATE 1 git hooks ──▶ push ──▶ GATE 2 push protection ──▶ PR ──▶ GATE 3 CI
             stops leaks               rejects known                         backstop
             before they exist         key formats                           (after push)
```

| Check | Gate 1 (local hooks) | Gate 3 (CI) |
|:--|:--:|:--:|
| Secrets (gitleaks) | ✅ staged changes | ✅ every commit in the PR |
| Data files (`.db`, `.sqlite*`, `.jsonl`, `.parquet`, `.env*`, `data/`, > 500 KB) | ✅ | ✅ |
| Personal data patterns (email, phone, card, SSN) | ✅ files + commit message | ✅ changed files |
| Private terms from `~/.mind/leak-terms.txt` | ✅ files + commit message | n/a |
| Commit email must be a GitHub noreply address | ✅ | ✅ every commit in the PR |
| Dependency vulnerabilities (pip-audit) + Dependabot | | ✅ |
| Least-privilege workflow, Actions pinned to SHAs | | ✅ |

**Design rule:** personal values never live in the repo. The privacy blocklist lives in
`~/.mind/policy.toml`, private terms in `~/.mind/leak-terms.txt`. Code ships generic
defaults only. Tests use synthetic data only.

## Why CI alone isn't enough

CI runs *after* the push. On a public repo, by the time CI fails, the data is already
visible (and possibly cached or cloned). Gate 1 is the only gate that prevents a leak.
CI catches what slips past it, such as a commit made on a machine without hooks.

## Why private terms aren't checked in CI

A committed list of "terms to block" would publish exactly those terms. So that list stays
on the laptop, and CI checks generic patterns instead.

## Consequences

- New clones need `make hooks` once. Without it, only CI protects the repo.
- Pattern checks can false-positive. Deliberate test fixtures mark the line with
  `leakguard: allow`. The lockfile is skipped for pattern checks (wheel names look like numbers).
- Findings are printed masked, so logs never echo what was caught.
