"""Statistics step (decision 001, N5 step 3).

A short line that shows up in many different visits is site chrome ("LeetCode Logo",
tab labels), not content. Runs after the structure step, so real words like `nums`
have already been glued into sentences that are unique to one page.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace

from mind.visit import Visit

MIN_VISITS = 8
MAX_LEN = 100


@dataclass(frozen=True)
class BoilerplateResult:
    visits: list[Visit]
    lines_dropped: int  # line occurrences removed across all visits
    visits_emptied: int  # visits with nothing left, removed


def boilerplate_lines(
    visits: Sequence[Visit], min_visits: int = MIN_VISITS, max_len: int = MAX_LEN
) -> set[str]:
    seen_in = Counter[str]()
    for visit in visits:
        seen_in.update({line.text for line in visit.lines})  # a set: count each visit once
    return {text for text, n in seen_in.items() if n >= min_visits and len(text) <= max_len}


def drop_boilerplate(
    visits: Sequence[Visit], min_visits: int = MIN_VISITS, max_len: int = MAX_LEN
) -> BoilerplateResult:
    boiler = boilerplate_lines(visits, min_visits, max_len)
    kept, dropped, emptied = [], 0, 0
    for visit in visits:
        lines = tuple(line for line in visit.lines if line.text not in boiler)
        dropped += len(visit.lines) - len(lines)
        if lines:
            kept.append(replace(visit, lines=lines))
        else:
            emptied += 1
    return BoilerplateResult(kept, dropped, emptied)
