from datetime import timedelta

from conftest import T0, frame

from mind.clean.visits import clean_title, group_visits
from mind.screenpipe import Frame
from mind.visit import Author, Line

A = "https://site.test/a"
B = "https://site.test/b"


def lines(*texts: str) -> list[Line]:
    return [Line(t) for t in texts]


def minutes(n: float) -> timedelta:
    return timedelta(minutes=n)


def visits_of(*items: tuple[Frame, list[Line]]) -> list[list[int]]:
    """Frame IDs per visit: the easiest shape to assert on."""
    return [list(v.frame_ids) for v in group_visits(items)]


def test_same_page_within_gap_is_one_visit() -> None:
    assert visits_of(
        (frame(1, url=A), lines("x")),
        (frame(2, url=A, at=minutes(9)), lines("y")),
    ) == [[1, 2]]


def test_gap_just_over_ten_minutes_starts_new_visit() -> None:
    assert visits_of(
        (frame(1, url=A), lines("x")),
        (frame(2, url=A, at=minutes(10) + timedelta(seconds=1)), lines("y")),
    ) == [[1], [2]]


def test_gap_of_exactly_ten_minutes_is_same_visit() -> None:
    assert visits_of(
        (frame(1, url=A), lines("x")),
        (frame(2, url=A, at=minutes(10)), lines("y")),
    ) == [[1, 2]]


def test_tab_flipping_keeps_two_visits() -> None:
    # A -> B -> A within 10 minutes: two visits, not three.
    assert visits_of(
        (frame(1, url=A), lines("x")),
        (frame(2, url=B, at=minutes(1)), lines("y")),
        (frame(3, url=A, at=minutes(2)), lines("z")),
    ) == [[1, 3], [2]]


def test_fragment_ignored_query_kept() -> None:
    assert visits_of(
        (frame(1, url=A + "#intro"), lines("x")),
        (frame(2, url=A + "#details"), lines("y")),
        (frame(3, url=A + "?tab=2"), lines("z")),
    ) == [[1, 2], [3]]


def test_no_url_falls_back_to_window_title() -> None:
    assert visits_of(
        (frame(1, url=None, window="notes.md", app="Code"), lines("x")),
        (frame(2, url=None, window="notes.md", app="Code"), lines("y")),
        (frame(3, url=None, window="todo.md", app="Code"), lines("z")),
    ) == [[1, 2], [3]]


def test_visit_records_pointers_and_times() -> None:
    [visit] = group_visits(
        [
            (frame(10, url=A + "#x"), lines("x")),
            (frame(11, url=A, at=minutes(5)), lines("y")),
        ]
    )
    assert visit.frame_ids == (10, 11)
    assert visit.start == T0
    assert visit.end == T0 + minutes(5)
    assert visit.url == A  # stored without the fragment


def test_lines_deduped_in_first_seen_order() -> None:
    [visit] = group_visits(
        [
            (frame(1, url=A), lines("one", "two")),
            (frame(2, url=A), lines("two", "three", "one")),
        ]
    )
    assert [line.text for line in visit.lines] == ["one", "two", "three"]


def test_line_seen_as_typed_anywhere_stays_typed() -> None:
    [visit] = group_visits(
        [
            (frame(1, url=A), [Line("hello there"), Line("other")]),
            (frame(2, url=A), [Line("hello there", Author.ME)]),
        ]
    )
    assert visit.lines == (Line("hello there", Author.ME), Line("other"))


def test_title_is_most_common_window_without_browser_suffix() -> None:
    [visit] = group_visits(
        [
            (frame(1, url=A, window="Loading..."), lines("x")),
            (frame(2, url=A, window="Reverse Pairs - LeetCode - Google Chrome - Work"), lines("y")),
            (frame(3, url=A, window="Reverse Pairs - LeetCode - Google Chrome - Work"), lines("z")),
        ]
    )
    assert visit.title == "Reverse Pairs - LeetCode"


def test_clean_title_leaves_other_apps_alone() -> None:
    assert clean_title("notes.md - project", "Code") == "notes.md - project"
