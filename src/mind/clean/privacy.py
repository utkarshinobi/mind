"""Privacy policy: which apps are indexed, which sites are never indexed (decision 001, 2a).

The code ships only generic defaults. Your personal list (banks, bills, anything sensitive
*to you*) lives in ~/.mind/policy.toml, outside the repo, because a blocklist reveals
which sites you use. `mind init` creates a template.
"""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_APPS = frozenset(
    {"Google Chrome", "Claude", "Preview", "Code", "Notion", "Typeless", "Terminal"}
)

# Browsers report a URL per screen. When one doesn't, the site can't be checked against the
# blocklist, so the screen is dropped: unverifiable means not indexed (fails safe).
BROWSER_APPS = frozenset({"Google Chrome"})

# Generic sensitive sites, safe to publish because they reveal nothing personal.
DEFAULT_BLOCKED_HOSTS = (
    "*.1password.com",
    "*.bitwarden.com",
    "*.lastpass.com",
    "accounts.google.com",
    "appleid.apple.com",
    "login.microsoftonline.com",
    "platform.openai.com",
    "platform.claude.com",
)

POLICY_TEMPLATE = """\
# mind privacy policy. Lives in ~/.mind, outside the repo. Never commit it.
#
# Built-in defaults already block password managers, common login pages,
# and public API key consoles. Add anything sensitive *to you* below.

[apps]
# Indexed by default: Google Chrome, Claude, Preview, Code, Notion, Typeless, Terminal
add = []       # e.g. ["Obsidian"]
remove = []    # e.g. ["Terminal"]

[block]
# Sites never indexed. "*.example.com" blocks example.com and every subdomain.
hosts = [
    # "*.yourbank.com",
]
"""


class PolicyError(ValueError):
    pass


class PolicyMissingError(PolicyError):
    pass


def host_matches(host: str, pattern: str) -> bool:
    """`*.x.com` matches x.com and any subdomain, but not lookalikes like notx.com."""
    host, pattern = host.lower(), pattern.lower()
    if pattern.startswith("*."):
        base = pattern[2:]
        return host == base or host.endswith("." + base)
    return host == pattern


@dataclass(frozen=True)
class Policy:
    apps: frozenset[str] = DEFAULT_APPS
    blocked_hosts: tuple[str, ...] = DEFAULT_BLOCKED_HOSTS

    def allows_app(self, app: str | None) -> bool:
        return app is not None and app in self.apps

    def unverifiable(self, app: str | None, url: str | None) -> bool:
        """A browser screen with no URL: its site can't be checked, so don't index it."""
        return app in BROWSER_APPS and not url

    def blocks_url(self, url: str | None) -> bool:
        if not url:
            return False
        host = urlsplit(url).hostname
        return host is not None and any(host_matches(host, p) for p in self.blocked_hosts)


DEFAULT_POLICY = Policy()


def _string_list(table: dict[str, Any], key: str, where: str) -> list[str]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise PolicyError(f"{where}.{key} must be a list of strings")
    return value


def load_policy(path: Path) -> Policy:
    """Defaults plus the personal additions in policy.toml."""
    if not path.exists():
        raise PolicyMissingError(
            f"No privacy policy at {path}. Run `mind init`, then add your sensitive sites."
        )
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise PolicyError(f"{path} is not valid TOML: {e}") from e

    apps_table, block_table = data.get("apps", {}), data.get("block", {})
    if not isinstance(apps_table, dict) or not isinstance(block_table, dict):
        raise PolicyError(f"{path}: [apps] and [block] must be tables")
    add = _string_list(apps_table, "add", "apps")
    remove = _string_list(apps_table, "remove", "apps")
    hosts = _string_list(block_table, "hosts", "block")

    return Policy(
        apps=(DEFAULT_APPS | set(add)) - set(remove),
        blocked_hosts=_dedupe((*DEFAULT_BLOCKED_HOSTS, *hosts)),
    )


def _dedupe(items: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))
