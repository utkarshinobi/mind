from pathlib import Path

import pytest
from conftest import MakeScreenpipeDb, node, tree

from mind import __version__
from mind.cli import main


@pytest.fixture
def mind_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated MIND_HOME, so tests never touch the real ~/.mind."""
    home = tmp_path / "home"
    monkeypatch.setenv("MIND_HOME", str(home))
    return home


@pytest.fixture
def screenpipe(make_screenpipe_db: MakeScreenpipeDb, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake Screenpipe with one readable page, one blocked site, and one other app."""
    page = tree(
        node("Settings", "AXButton", top=0.05),
        node("How do decorators work?", top=0.1),
        node("can you show an example", "AXTextArea", top=0.8),
    )
    path = make_screenpipe_db(
        [
            {"id": 1, "timestamp": "2026-08-25T19:00:00+00:00", "accessibility_tree_json": page},
            {"id": 2, "timestamp": "2026-08-25T19:01:00+00:00", "accessibility_tree_json": page},
            {
                "id": 3,
                "timestamp": "2026-08-25T19:02:00+00:00",
                "browser_url": "https://secure.mybank.test/accounts",
                "full_text": "account balance",
            },
            {"id": 4, "timestamp": "2026-08-25T19:03:00+00:00", "app_name": "Finder"},
        ]
    )
    monkeypatch.setenv("MIND_SCREENPIPE_DB", str(path))
    return path


def init_with_blocked_bank(mind_home: Path) -> None:
    assert main(["init"]) == 0
    (mind_home / "policy.toml").write_text('[block]\nhosts = ["*.mybank.test"]\n')


def test_version_prints_version_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"mind {__version__}"


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: mind" in capsys.readouterr().out


def test_init_creates_private_files_in_mind_home(mind_home: Path) -> None:
    assert main(["init"]) == 0
    assert (mind_home / "policy.toml").read_text().startswith("# mind privacy policy")
    assert (mind_home / "leak-terms.txt").exists()


def test_init_never_overwrites(mind_home: Path) -> None:
    mind_home.mkdir()
    (mind_home / "policy.toml").write_text("mine")
    assert main(["init"]) == 0
    assert (mind_home / "policy.toml").read_text() == "mine"


def test_clean_refuses_without_policy(
    mind_home: Path, screenpipe: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["clean"]) == 1
    assert "mind init" in capsys.readouterr().err
    assert not (mind_home / "mind.db").exists()  # nothing indexed unprotected


def test_clean_end_to_end(
    mind_home: Path, screenpipe: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    init_with_blocked_bank(mind_home)
    assert main(["clean"]) == 0

    out = capsys.readouterr().out
    assert "Cleaned 3 frames" in out  # Finder is filtered out at read time
    assert "1 by site" in out
    assert "Visits         1" in out
    assert (mind_home / "mind.db").exists()  # MIND_HOME respected


def test_show_prints_tagged_lines(
    mind_home: Path, screenpipe: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    init_with_blocked_bank(mind_home)
    main(["clean"])
    capsys.readouterr()

    assert main(["show", "1"]) == 0
    out = capsys.readouterr().out
    assert "2 frames (1 … 2)" in out
    assert "[read] How do decorators work?" in out
    assert "[me] can you show an example" in out
    assert "Settings" not in out
    assert "balance" not in out

    assert main(["show", "1", "--author", "me"]) == 0
    assert "[read]" not in capsys.readouterr().out


def test_show_unknown_visit_fails(mind_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["show", "42"]) == 1
    assert "no visit #42" in capsys.readouterr().err


def test_missing_screenpipe_database_fails(
    mind_home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    init_with_blocked_bank(mind_home)
    assert main(["clean", "--screenpipe-db", str(tmp_path / "nope.sqlite")]) == 1
    assert "not found" in capsys.readouterr().err


def test_stats_after_clean(
    mind_home: Path, screenpipe: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    init_with_blocked_bank(mind_home)
    main(["clean"])
    capsys.readouterr()
    assert main(["stats"]) == 0
    out = capsys.readouterr().out
    assert "Visits   1" in out
    assert "1 read · 1 me" in out
