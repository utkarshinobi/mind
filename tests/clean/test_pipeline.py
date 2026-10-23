from datetime import timedelta

from conftest import frame, node, tree

from mind.clean import clean
from mind.clean.privacy import DEFAULT_POLICY
from mind.screenpipe import Frame

PROBLEMS = [
    "reverse pairs",
    "majority elements",
    "valid anagrams",
    "merged intervals",
    "longest substrings",
    "rotated arrays",
    "missing numbers",
    "duplicate files",
    "island counts",
]


def leetcode_frame(i: int, subject: str) -> Frame:
    """One LeetCode problem page, shaped like the 15-line sample in decisions/001-clean.md."""
    screen = tree(
        node("LeetCode Logo", "AXLink", left=0.01, top=0.05, width=0.03),  # junk
        node("Layouts", "AXPopUpButton", left=0.4, top=0.05, width=0.05),  # junk
        node("Settings", "AXButton", left=0.5, top=0.05, width=0.05),  # junk
        node("Premium", "AXLink", left=0.9, top=0.05, width=0.05),  # junk
        node("Description", left=0.01, top=0.09, width=0.06),  # junk (tab as text)
        node("Editorial", left=0.08, top=0.09, width=0.05),  # junk (tab as text)
        node(f"{490 + i}. {subject.title()}", "AXLink", left=0.02, top=0.13, width=0.2),  # real
        node("Hard", left=0.02, top=0.17, width=0.03),  # real, alone on its row
        node("Given an integer array", left=0.02, top=0.21, width=0.15),  # real
        node("nums", left=0.175, top=0.212, width=0.03, height=0.018),  # real
        node(", return", left=0.205, top=0.21, width=0.04),  # real
        node("the number of", left=0.25, top=0.21, width=0.08),  # real
        node(f"{subject}.", left=0.335, top=0.21, width=0.1),  # real
        node("Submit", "AXButton", left=0.7, top=0.9, width=0.05),  # junk
        node("Run", "AXButton", left=0.6, top=0.9, width=0.04),  # junk
    )
    url = f"https://leetcode.com/problems/{subject.replace(' ', '-')}/"
    return frame(i, url=url, tree=screen, at=timedelta(minutes=15 * i))


def test_decision_001_scorecard() -> None:
    """Regression for the N5 scorecard: all 8 junk lines removed, only `Hard` lost,
    and `nums` survives because it's glued into its sentence."""
    result = clean([leetcode_frame(i, s) for i, s in enumerate(PROBLEMS)], DEFAULT_POLICY)

    reverse_pairs = result.visits[0]
    assert [line.text for line in reverse_pairs.lines] == [
        "490. Reverse Pairs",
        "Given an integer array nums, return the number of reverse pairs.",
    ]


def test_stats_add_up() -> None:
    frames = [
        frame(1, url="https://site.test/a", full_text="first page text"),
        frame(2, url="https://site.test/a", full_text="first page text\nmore text here"),
        frame(3, app="Finder", full_text="file list"),
        frame(4, url="https://accounts.google.com/signin", full_text="sign in page"),
        frame(5, url="https://site.test/b", tree=tree(node("typed note", "AXTextArea"))),
    ]
    stats = clean(frames, DEFAULT_POLICY).stats
    assert stats.frames_read == 5
    assert stats.blocked_app == 1
    assert stats.blocked_host == 1
    assert stats.frames_kept == 3
    assert stats.visits == 2
    assert (stats.lines_read, stats.lines_me) == (2, 1)
    assert stats.frames_read == stats.blocked_app + stats.blocked_host + stats.frames_kept
