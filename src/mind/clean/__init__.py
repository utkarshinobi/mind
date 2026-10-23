"""Clean: raw Screenpipe frames -> visits made of clean, tagged lines (decision 001).

frames ─▶ privacy (2a) ─▶ structure (N5 ①②) ─▶ visits (2b) ─▶ statistics (N5 ③) ─▶ visits
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from mind.clean.boilerplate import drop_boilerplate
from mind.clean.privacy import Policy
from mind.clean.tree import extract_lines
from mind.clean.visits import group_visits
from mind.screenpipe import Frame
from mind.visit import Author, Line, Visit


@dataclass
class CleanStats:
    frames_read: int = 0
    blocked_app: int = 0
    blocked_host: int = 0
    frames_kept: int = 0
    visits: int = 0
    lines_me: int = 0
    lines_read: int = 0
    boilerplate_dropped: int = 0
    visits_without_text: int = 0  # nothing left after the structure step (e.g. new-tab pages)
    visits_emptied: int = 0  # had text, but all of it was boilerplate


@dataclass(frozen=True)
class CleanResult:
    visits: list[Visit]
    stats: CleanStats


def clean(frames: Iterable[Frame], policy: Policy) -> CleanResult:
    stats = CleanStats()

    def allowed_with_lines() -> Iterator[tuple[Frame, list[Line]]]:
        for frame in frames:
            stats.frames_read += 1
            if not policy.allows_app(frame.app):
                stats.blocked_app += 1
            elif policy.blocks_url(frame.url):
                stats.blocked_host += 1
            else:
                stats.frames_kept += 1
                yield frame, extract_lines(frame.tree, frame.full_text)

    visits = group_visits(allowed_with_lines())
    with_text = [v for v in visits if v.lines]
    stats.visits_without_text = len(visits) - len(with_text)
    result = drop_boilerplate(with_text)

    stats.visits = len(result.visits)
    stats.boilerplate_dropped = result.lines_dropped
    stats.visits_emptied = result.visits_emptied
    for visit in result.visits:
        for line in visit.lines:
            if line.author is Author.ME:
                stats.lines_me += 1
            else:
                stats.lines_read += 1
    return CleanResult(result.visits, stats)
