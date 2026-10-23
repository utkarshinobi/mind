from pathlib import Path

import pytest

from mind.clean.privacy import (
    DEFAULT_APPS,
    DEFAULT_POLICY,
    POLICY_TEMPLATE,
    PolicyError,
    PolicyMissingError,
    host_matches,
    load_policy,
)


@pytest.mark.parametrize("app", sorted(DEFAULT_APPS))
def test_allowed_apps_pass(app: str) -> None:
    assert DEFAULT_POLICY.allows_app(app)


@pytest.mark.parametrize("app", ["Finder", "Passwords", "Find My", None, ""])
def test_other_apps_rejected(app: str | None) -> None:
    assert not DEFAULT_POLICY.allows_app(app)


@pytest.mark.parametrize(
    ("host", "pattern", "matches"),
    [
        ("accounts.google.com", "accounts.google.com", True),  # exact
        ("vault.example.com", "*.example.com", True),  # subdomain
        ("example.com", "*.example.com", True),  # the base domain itself
        ("a.b.example.com", "*.example.com", True),  # deep subdomain
        ("notexample.com", "*.example.com", False),  # lookalike
        ("example.com.evil.net", "*.example.com", False),  # suffix trick
        ("mail.google.com", "accounts.google.com", False),  # sibling
    ],
)
def test_host_matching(host: str, pattern: str, matches: bool) -> None:
    assert host_matches(host, pattern) is matches


def test_default_blocks_login_and_password_managers() -> None:
    assert DEFAULT_POLICY.blocks_url("https://accounts.google.com/signin?x=1")
    assert DEFAULT_POLICY.blocks_url("https://my.1password.com/vaults")


def test_mail_allowed() -> None:
    assert not DEFAULT_POLICY.blocks_url("https://mail.google.com/mail/u/0/#inbox")


def test_frame_without_url_allowed() -> None:
    assert not DEFAULT_POLICY.blocks_url(None)


def write_policy(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "policy.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_policy_file_merges_with_defaults(tmp_path: Path) -> None:
    toml = """
[apps]
add = ["Obsidian"]
remove = ["Terminal"]

[block]
hosts = ["*.mybank.test"]
"""
    policy = load_policy(write_policy(tmp_path, toml))
    assert "Obsidian" in policy.apps
    assert "Terminal" not in policy.apps
    assert policy.blocks_url("https://secure.mybank.test/login")
    assert policy.blocks_url("https://accounts.google.com/")  # defaults still apply


def test_template_is_valid_and_blocks_only_defaults(tmp_path: Path) -> None:
    policy = load_policy(write_policy(tmp_path, POLICY_TEMPLATE))
    assert policy == DEFAULT_POLICY


def test_missing_policy_file_says_how_to_fix(tmp_path: Path) -> None:
    with pytest.raises(PolicyMissingError, match="mind init"):
        load_policy(tmp_path / "policy.toml")


def test_invalid_toml_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="not valid TOML"):
        load_policy(write_policy(tmp_path, "[block\nhosts = "))


def test_wrong_types_are_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match=r"block\.hosts must be a list of strings"):
        load_policy(write_policy(tmp_path, '[block]\nhosts = "*.mybank.test"\n'))
