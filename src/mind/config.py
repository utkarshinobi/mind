"""Where mind keeps its files.

Everything personal lives under MIND_HOME (default ~/.mind), outside the repo.
These are functions, not constants, so an env var set at runtime (or in a test) is respected.
"""

from __future__ import annotations

import os
from pathlib import Path


def mind_home() -> Path:
    return Path(os.environ.get("MIND_HOME", Path.home() / ".mind"))


def db_path() -> Path:
    return mind_home() / "mind.db"


def policy_path() -> Path:
    return mind_home() / "policy.toml"


def screenpipe_db_path() -> Path:
    return Path(os.environ.get("MIND_SCREENPIPE_DB", Path.home() / ".screenpipe" / "db.sqlite"))
