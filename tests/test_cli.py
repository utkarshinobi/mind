from pathlib import Path

import pytest

from mind import __version__
from mind.cli import main


def test_version_prints_version_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"mind {__version__}"


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: mind" in capsys.readouterr().out


def test_init_creates_private_files_in_mind_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIND_HOME", str(tmp_path / "home"))
    assert main(["init"]) == 0
    assert (tmp_path / "home" / "policy.toml").read_text().startswith("# mind privacy policy")
    assert (tmp_path / "home" / "leak-terms.txt").exists()


def test_init_never_overwrites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIND_HOME", str(tmp_path))
    (tmp_path / "policy.toml").write_text("mine")
    assert main(["init"]) == 0
    assert (tmp_path / "policy.toml").read_text() == "mine"
