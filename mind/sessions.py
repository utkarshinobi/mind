"""Group raw Screenpipe captures into sessions, the unit of memory.

A screen session is one continuous stretch on one page (same app and URL, or
same app and window when there is no URL). Consecutive frames are ~93%
identical, so a session keeps each distinct line once, in first-seen order.
Short lines that recur across many sessions (toolbars, menus, buttons) are
dropped as boilerplate.

An audio session is a run of transcript segments with no long silence.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

from mind.schema import Entry

# Never index these, regardless of Screenpipe's own ignore list.
DENY_APPS = {
    "Passwords", "Keychain Access", "1Password", "Bitwarden", "Find My",
    "ControlCenter", "Dock", "loginwindow", "screenpipe", "System Settings",
}

SCREEN_GAP = timedelta(minutes=10)
AUDIO_GAP = timedelta(minutes=3)
BOILERPLATE_MIN_SESSIONS = 8
BOILERPLATE_MAX_LEN = 100
MIN_SCREEN_CHARS = 200
MIN_AUDIO_CHARS = 80

_ALNUM = re.compile(r"[A-Za-z0-9]")


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def label(entry: Entry) -> str:
    """One-line human description, used in chunk headers and citations."""
    when = parse_ts(entry.timestamp).astimezone().strftime("%Y-%m-%d %H:%M")
    parts = [when, entry.meta.get("app", ""), entry.meta.get("title", "")]
    if url := entry.meta.get("url"):
        parts.append(url)
    return " · ".join(p for p in parts if p)


@dataclass
class _Screen:
    app: str
    url: str | None
    start: datetime
    end: datetime
    frames: int = 0
    titles: Counter = field(default_factory=Counter)
    lines: dict = field(default_factory=dict)  # insertion-ordered set


def _page_key(app: str, window: str | None, url: str | None) -> tuple:
    if url:
        p = urlsplit(url)
        return app, urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))
    return app, window or ""


def _clean_title(title: str, app: str) -> str:
    return re.sub(rf"\s+-\s+{re.escape(app)}\b.*$", "", title).strip() or title


def screen_sessions(frames: Iterable[tuple]) -> list[Entry]:
    sessions: list[_Screen] = []
    open_by_page: dict[tuple, _Screen] = {}

    for ts, app, window, url, text in frames:
        if not app or app in DENY_APPS or not text:
            continue
        t = parse_ts(ts)
        key = _page_key(app, window, url)
        s = open_by_page.get(key)
        # Reuse the page's session if we were on it recently, so flipping
        # between two tabs doesn't fragment both into many tiny sessions.
        if s is None or t - s.end > SCREEN_GAP:
            s = _Screen(app, url, t, t)
            sessions.append(s)
            open_by_page[key] = s
        s.end = max(s.end, t)
        s.frames += 1
        if window:
            s.titles[window] += 1
        for line in text.split("\n"):
            line = line.strip()
            if line and len(_ALNUM.findall(line)) >= 3:
                s.lines.setdefault(line, None)

    seen_in = Counter()
    for s in sessions:
        seen_in.update(s.lines.keys())
    boilerplate = {
        line for line, n in seen_in.items()
        if n >= BOILERPLATE_MIN_SESSIONS and len(line) <= BOILERPLATE_MAX_LEN
    }

    entries = []
    for s in sessions:
        body = "\n".join(line for line in s.lines if line not in boilerplate)
        if len(body) < MIN_SCREEN_CHARS:
            continue
        title = _clean_title(s.titles.most_common(1)[0][0], s.app) if s.titles else s.app
        meta = {"app": s.app, "title": title, "end": s.end.isoformat(), "frames": s.frames}
        if s.url:
            meta["url"] = s.url
        entries.append(Entry("screenpipe.screen", s.start.isoformat(), body, meta))
    return entries


def audio_sessions(rows: Iterable[tuple]) -> list[Entry]:
    groups: list[dict] = []
    for ts, text, speaker, is_input in rows:
        text = " ".join((text or "").split())
        if not text:
            continue
        t = parse_ts(ts)
        if not groups or t - groups[-1]["end"] > AUDIO_GAP:
            groups.append({"start": t, "end": t, "lines": []})
        g = groups[-1]
        g["end"] = t
        who = "mic" if is_input else "system"
        if speaker is not None:
            who += f" s{speaker}"
        g["lines"].append(f"[{who}] {text}")

    entries = []
    for g in groups:
        body = "\n".join(g["lines"])
        if len(body) < MIN_AUDIO_CHARS:
            continue
        minutes = max(1, round((g["end"] - g["start"]).total_seconds() / 60))
        meta = {"app": "audio", "title": f"conversation, ~{minutes} min",
                "end": g["end"].isoformat(), "segments": len(g["lines"])}
        entries.append(Entry("screenpipe.audio", g["start"].isoformat(), body, meta))
    return entries


def chunk(text: str, size: int = 1200, overlap_lines: int = 2) -> list[str]:
    """Split on line boundaries into ~size-char chunks with a little overlap."""
    lines = text.split("\n")
    chunks, buf, length = [], [], 0
    for line in lines:
        if len(line) > size:  # pathological single line: hard-wrap it
            line = line[:size]
        if buf and length + len(line) > size:
            chunks.append("\n".join(buf))
            buf = buf[-overlap_lines:]
            length = sum(len(x) + 1 for x in buf)
        buf.append(line)
        length += len(line) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks
