"""Tests for tools/leakguard.py.

The fake personal data below is deliberate test input, so those lines carry the
`leakguard: allow` marker that tells the guard to skip them.
"""

import os
import subprocess
from pathlib import Path

import leakguard
import pytest


def write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


# --- files -----------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "mind.db",
        "screen.sqlite",
        "x.sqlite3",
        "db.sqlite-wal",
        "db.sqlite-shm",
        "export.jsonl",
        "frames.parquet",
        ".env",
        ".env.local",
        "data/notes.txt",
        "src/data.db",
    ],
)
def test_forbidden_paths_blocked(path: str) -> None:
    assert leakguard.forbidden_reason(path) is not None


@pytest.mark.parametrize("path", ["src/mind/cli.py", "README.md", "uv.lock", "docs/data.md"])
def test_normal_paths_allowed(path: str) -> None:
    assert leakguard.forbidden_reason(path) is None


def test_large_file_blocked(tmp_path: Path) -> None:
    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * 600 * 1024)
    assert leakguard.forbidden_reason(str(big)) == "larger than 500 KB"


# --- pii -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("contact jane.doe@gmail.com today", "email address"),  # leakguard: allow
        ("call (415) 555-0134", "phone number"),  # leakguard: allow
        ("call +1 415-555-0134", "phone number"),  # leakguard: allow
        ("card 4111 1111 1111 1111", "card number"),  # leakguard: allow
        ("ssn 078-05-1120", "SSN"),  # leakguard: allow
    ],
)
def test_pii_detected(line: str, kind: str) -> None:
    assert kind in [k for k, _ in leakguard.find_pii(line)]


@pytest.mark.parametrize(
    "line",
    [
        "Co-Authored-By: Claude <noreply@anthropic.com>",
        "author 34977336+someone@users.noreply.github.com",
        "see user@example.com",
        "git clone git@github.com:owner/repo.git",
        "build 1234567812345678 is not a card",  # fails the Luhn check
        "released 2026-10-22, version 1.11.0",
    ],
)
def test_harmless_lines_pass(line: str) -> None:
    assert list(leakguard.find_pii(line)) == []


def test_allow_marker_skips_line(tmp_path: Path) -> None:
    path = write(tmp_path / "f.py", "x = 'jane.doe@gmail.com'  # leakguard: allow\n")
    assert leakguard.check_pii([path]) == []


def test_lockfile_not_scanned_for_pii(tmp_path: Path) -> None:
    path = write(tmp_path / "uv.lock", "ios_13_0_arm64 415 555 0134\n")  # leakguard: allow
    assert leakguard.check_pii([path]) == []


def test_findings_are_masked(tmp_path: Path) -> None:
    path = write(tmp_path / "f.md", "mail jane.doe@gmail.com\n")  # leakguard: allow
    [finding] = leakguard.check_pii([path])
    assert "jane.doe" not in str(finding)
    assert finding.line == 1


# --- terms -----------------------------------------------------------------


def test_private_term_matched_case_insensitively(tmp_path: Path) -> None:
    terms_file = tmp_path / "terms.txt"
    write(terms_file, "# comment\nAcmeBank\nx\n")
    terms = leakguard.load_terms(terms_file)
    assert terms == ["acmebank"]  # comment and too-short term ignored
    path = write(tmp_path / "notes.md", "paid rent via ACMEBANK portal\n")
    assert [f.kind for f in leakguard.check_terms([path], terms)] == ["private term"]


def test_terms_check_only_checks_terms(tmp_path: Path) -> None:
    # Regression: the terms hook used to also run pattern checks, flagging uv.lock.
    path = write(tmp_path / "uv.lock", "size 4111111111111111\n")  # leakguard: allow
    assert leakguard.check_terms([path], ["acmebank"]) == []


def test_private_term_in_commit_message(tmp_path: Path) -> None:
    msg = write(
        tmp_path / "COMMIT_EDITMSG", "Add acmebank to blocklist\n# acmebank in a comment is fine\n"
    )
    findings = leakguard.check_message(msg, ["acmebank"])
    assert len(findings) == 1
    assert findings[0].path == "commit message"


def test_missing_terms_file_warns_and_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(leakguard, "TERMS_PATH", tmp_path / "absent.txt")
    path = write(tmp_path / "f.md", "anything\n")
    assert leakguard.main(["terms", path]) == 0
    assert "not found" in capsys.readouterr().err


# --- author ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "ok"),
    [
        ("34977336+someone@users.noreply.github.com", True),
        ("someone@users.noreply.github.com", True),
        ("noreply@github.com", True),
        ("someone@gmail.com", False),  # leakguard: allow
        ("someone@users.noreply.github.com.evil.com", False),  # leakguard: allow
    ],
)
def test_email_ok(email: str, ok: bool) -> None:
    assert leakguard.email_ok(email) is ok


def test_author_range_flags_personal_email(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    def commit(email: str, msg: str) -> None:
        env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,  # ignore the developer's own git config
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_EMAIL": email,
        }
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", msg], check=True, env=env)

    subprocess.run(["git", "init", "-q"], check=True)
    commit("1+a@users.noreply.github.com", "base")
    commit("1+a@users.noreply.github.com", "good")
    assert leakguard.check_author("HEAD~1..HEAD") == []
    commit("someone@gmail.com", "bad")  # leakguard: allow
    [finding] = leakguard.check_author("HEAD~2..HEAD")
    assert "noreply" in finding.kind


def test_main_returns_1_and_reports_on_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert leakguard.main(["files", str(tmp_path / "mind.db")]) == 1
    assert "blocked" in capsys.readouterr().err
