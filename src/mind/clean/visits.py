"""Group cleaned frames into visits (decision 001, 2b).

One visit = the same app on the same page (URL without its #fragment, or the window
title when there's no URL). Away more than 10 minutes = a new visit. Flipping between
tabs within 10 minutes keeps adding to each tab's open visit instead of fragmenting.
Within a visit every line is kept once, in first-seen order.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

from mind.screenpipe import Frame
from mind.visit import Author, Line, Visit

VISIT_GAP = timedelta(minutes=10)
SOURCE = "screenpipe.screen"


def normalize_url(url: str) -> str:
    """Drop the #fragment, keep the ?query (it often identifies the page)."""
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))


def page_key(frame: Frame) -> tuple[str, str]:
    app = frame.app or ""
    if frame.url:
        return app, normalize_url(frame.url)
    return app, frame.window or ""


def clean_title(window: str, app: str) -> str:
    """'Reverse Pairs - LeetCode - Google Chrome - Profile' -> 'Reverse Pairs - LeetCode'."""
    return re.sub(rf"\s+-\s+{re.escape(app)}\b.*$", "", window).strip() or window


@dataclass
class _OpenVisit:
    app: str
    url: str | None
    start: datetime
    end: datetime
    frame_ids: list[int] = field(default_factory=list)
    titles: Counter[str] = field(default_factory=Counter)
    lines: dict[str, Author] = field(default_factory=dict)  # insertion-ordered: first seen

    def add(self, frame: Frame, lines: Iterable[Line]) -> None:
        self.end = max(self.end, frame.time)
        self.frame_ids.append(frame.id)
        if frame.window:
            self.titles[frame.window] += 1
        for line in lines:
            if line.text not in self.lines:
                self.lines[line.text] = line.author
            elif line.author is Author.ME:
                # Seen as typed anywhere in the visit means typed. Reassigning a dict key
                # keeps its original position, so first-seen order is preserved.
                self.lines[line.text] = Author.ME

    def build(self) -> Visit:
        title = clean_title(self.titles.most_common(1)[0][0], self.app) if self.titles else self.app
        return Visit(
            source=SOURCE,
            app=self.app,
            title=title,
            url=self.url,
            start=self.start,
            end=self.end,
            frame_ids=tuple(self.frame_ids),
            lines=tuple(Line(text, author) for text, author in self.lines.items()),
        )


def group_visits(
    items: Iterable[tuple[Frame, list[Line]]], gap: timedelta = VISIT_GAP
) -> list[Visit]:
    """items: (frame, its cleaned lines), in time order."""
    visits: list[_OpenVisit] = []
    open_by_page: dict[tuple[str, str], _OpenVisit] = {}
    for frame, lines in items:
        key = page_key(frame)
        visit = open_by_page.get(key)
        if visit is None or frame.time - visit.end > gap:
            url = normalize_url(frame.url) if frame.url else None
            visit = _OpenVisit(frame.app or "", url, frame.time, frame.time)
            visits.append(visit)
            open_by_page[key] = visit
        visit.add(frame, lines)
    return [v.build() for v in visits]
