"""The ingestion contract.

Every producer (Screenpipe frames, audio transcripts, phone shares, anything
added later) normalizes to Entry. Nothing downstream may depend on any
producer-specific field.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict


@dataclass
class Entry:
    source: str            # e.g. "screenpipe.screen", "screenpipe.audio", "phone.share"
    timestamp: str         # ISO 8601 with offset
    text: str
    meta: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def clean_text(raw: str | None) -> str:
    """Collapse whitespace; empty string means 'drop this entry'."""
    if not raw:
        return ""
    return " ".join(raw.split())
