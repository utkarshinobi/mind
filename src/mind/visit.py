"""The domain types every stage shares: a visit to one page, made of lines.

This replaces the milestone-0 `Entry` contract. Producers (Screenpipe today,
others later) produce Visits; everything downstream reads Visits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Author(StrEnum):
    ME = "me"  # text the user typed (AXTextArea)
    READ = "read"  # everything else on screen


@dataclass(frozen=True)
class Line:
    text: str
    author: Author = Author.READ


@dataclass(frozen=True)
class Visit:
    source: str  # e.g. "screenpipe.screen"
    app: str
    title: str
    url: str | None
    start: datetime  # UTC
    end: datetime  # UTC
    frame_ids: tuple[int, ...]  # pointers back to Screenpipe frames
    lines: tuple[Line, ...]
