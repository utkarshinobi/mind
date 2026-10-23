"""Leak guard: stop personal data from reaching the public repo.

Shared by the local git hooks (Gate 1) and CI (Gate 3), so both enforce the same rules.

    python tools/leakguard.py files  PATH...         forbidden file types, paths, and sizes
    python tools/leakguard.py pii    PATH...         emails, phone numbers, card numbers, SSNs
    python tools/leakguard.py terms  PATH...         your private terms (~/.mind/leak-terms.txt)
    python tools/leakguard.py msg    FILE            pii + terms on a commit message
    python tools/leakguard.py author [--range A..B]  commit emails must be GitHub noreply

A line containing `leakguard: allow` is skipped by pii and terms, for deliberate test fixtures.
Findings are printed masked, so the guard itself never echoes what it caught.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_BYTES = 500 * 1024
DATA_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".jsonl", ".parquet"}
PII_SKIP_FILES = {"uv.lock"}  # package hashes and wheel names look like numbers and phones
ALLOW_MARKER = "leakguard: allow"
TERMS_PATH = Path(os.environ.get("MIND_LEAK_TERMS", Path.home() / ".mind" / "leak-terms.txt"))

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\w+])(?:\+\d{1,3}[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)")
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
NOREPLY = re.compile(r"^(\d+\+)?[A-Za-z0-9-]+@users\.noreply\.github\.com$")
GITHUB_COMMITTER = "noreply@github.com"  # commits GitHub itself creates (merges, web edits)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    preview: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"{where}: {self.kind} ({self.preview})"


def mask(text: str) -> str:
    return text if len(text) <= 4 else f"{text[:2]}…{text[-2:]}"


# --- files -----------------------------------------------------------------


def forbidden_reason(path: str) -> str | None:
    """Why this path must never be committed, or None if it's fine."""
    p = Path(path)
    if p.name == ".env" or p.name.startswith(".env."):
        return "environment file"
    if p.parts and p.parts[0] == "data":
        return "data/ directory"
    base = re.sub(r"-(wal|shm|journal)$", "", p.name)  # SQLite sidecars: x.db-wal
    if Path(base).suffix.lower() in DATA_SUFFIXES:
        return "data file"
    if p.is_file() and p.stat().st_size > MAX_FILE_BYTES:
        return f"larger than {MAX_FILE_BYTES // 1024} KB"
    return None


def check_files(paths: Sequence[str]) -> list[Finding]:
    return [Finding(p, 0, reason, "blocked") for p in paths if (reason := forbidden_reason(p))]


# --- pii -------------------------------------------------------------------


def email_allowed(address: str) -> bool:
    local, _, domain = address.lower().partition("@")
    return (
        "noreply" in local
        or domain.endswith("noreply.github.com")
        or domain in {"example.com", "example.org", "example.net"}
        or address.lower() == "git@github.com"
    )


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def find_pii(text: str) -> Iterator[tuple[str, str]]:
    """Yield (kind, match) for every likely piece of personal data in one line."""
    for m in EMAIL.finditer(text):
        if not email_allowed(m.group()):
            yield "email address", m.group()
    for m in PHONE.finditer(text):
        yield "phone number", m.group()
    for m in CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and luhn_valid(digits):
            yield "card number", m.group()
    for m in SSN.finditer(text):
        yield "SSN", m.group()


def read_lines(path: str) -> list[str]:
    """Text lines of a file; empty for missing or binary files."""
    try:
        return Path(path).read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError):
        return []


def scan_lines(
    path: str, lines: Sequence[str], *, pii: bool, terms: Sequence[str] = ()
) -> list[Finding]:
    """Scan lines for personal data patterns (if pii) and private terms."""
    findings = []
    for n, line in enumerate(lines, 1):
        if ALLOW_MARKER in line:
            continue
        if pii:
            for kind, match in find_pii(line):
                findings.append(Finding(path, n, kind, mask(match)))
        lowered = line.lower()
        for term in terms:
            if term in lowered:
                findings.append(Finding(path, n, "private term", mask(term)))
    return findings


def check_pii(paths: Sequence[str]) -> list[Finding]:
    return [
        f
        for p in paths
        if Path(p).name not in PII_SKIP_FILES
        for f in scan_lines(p, read_lines(p), pii=True)
    ]


# --- terms -----------------------------------------------------------------


def load_terms(path: Path) -> list[str] | None:
    """Private terms, lowercased. None if the file doesn't exist."""
    if not path.exists():
        return None
    terms = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        term = raw.strip().lower()
        if len(term) >= 3 and not term.startswith("#"):
            terms.append(term)
    return terms


def terms_or_warn(path: Path) -> list[str]:
    terms = load_terms(path)
    if terms is None:
        print(f"leakguard: warning: {path} not found, private-term check skipped", file=sys.stderr)
        return []
    return terms


def check_terms(paths: Sequence[str], terms: Sequence[str]) -> list[Finding]:
    return [f for p in paths for f in scan_lines(p, read_lines(p), pii=False, terms=terms)]


def check_message(path: str, terms: Sequence[str]) -> list[Finding]:
    """A commit message gets both checks: it's free text, like a file nobody reviews."""
    lines = [ln for ln in read_lines(path) if not ln.startswith("#")]  # git's comment lines
    return scan_lines("commit message", lines, pii=True, terms=terms)


# --- author ----------------------------------------------------------------


def email_ok(email: str) -> bool:
    return bool(NOREPLY.match(email)) or email == GITHUB_COMMITTER


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def identity_email(var: str) -> str:
    """Email git will use, from `git var GIT_AUTHOR_IDENT` (respects config and env)."""
    m = re.search(r"<([^>]*)>", git("var", var))
    return m.group(1) if m else ""


def check_author(commit_range: str | None) -> list[Finding]:
    if commit_range:
        emails = set(git("log", "--format=%ae%n%ce", commit_range).split())
    else:
        emails = {identity_email("GIT_AUTHOR_IDENT"), identity_email("GIT_COMMITTER_IDENT")}
    return [
        Finding("commit identity", 0, "email is not a GitHub noreply address", mask(e))
        for e in sorted(emails)
        if not email_ok(e)
    ]


# --- cli -------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="leakguard", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("files", "pii", "terms"):
        sub.add_parser(name).add_argument("paths", nargs="*")
    sub.add_parser("msg").add_argument("path")
    sub.add_parser("author").add_argument("--range", dest="commit_range")
    args = parser.parse_args(argv)

    match args.cmd:
        case "files":
            findings = check_files(args.paths)
        case "pii":
            findings = check_pii(args.paths)
        case "terms":
            findings = check_terms(args.paths, terms_or_warn(TERMS_PATH))
        case "msg":
            findings = check_message(args.path, terms_or_warn(TERMS_PATH))
        case "author":
            findings = check_author(args.commit_range)

    for f in findings:
        print(f"leakguard: {f}", file=sys.stderr)
    if findings:
        print(
            f"leakguard: blocked, {len(findings)} finding(s). Nothing was committed.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
