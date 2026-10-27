from dataclasses import replace

from conftest import T0

from mind.clean.boilerplate import drop_boilerplate
from mind.visit import Author, Line, Visit


def visit(n: int, *texts: str) -> Visit:
    return Visit(
        source="test",
        app="Google Chrome",
        title=f"page {n}",
        url=f"https://site.test/{n}",
        start=T0,
        end=T0,
        frame_ids=(n,),
        lines=tuple(Line(t) for t in texts),
    )


def kept_texts(visits: list[Visit]) -> list[list[str]]:
    return [[line.text for line in v.lines] for v in visits]


def test_short_line_in_eight_visits_dropped() -> None:
    visits = [visit(i, "Settings", f"content {i}") for i in range(8)]
    result = drop_boilerplate(visits)
    assert kept_texts(result.visits) == [[f"content {i}"] for i in range(8)]
    assert result.lines_dropped == 8


def test_short_line_in_seven_visits_kept() -> None:
    visits = [visit(i, "Settings", f"content {i}") for i in range(7)]
    assert drop_boilerplate(visits).lines_dropped == 0


def test_long_line_in_eight_visits_kept() -> None:
    long_line = "x" * 101
    visits = [visit(i, long_line, f"content {i}") for i in range(8)]
    assert drop_boilerplate(visits).lines_dropped == 0


def test_repeats_inside_one_visit_count_once() -> None:
    # 11 occurrences, but only 7 distinct visits: the rule counts visits, not occurrences.
    visits = [visit(i, "Settings", f"content {i}") for i in range(6)]
    visits.append(visit(6, "Settings", "Settings", "Settings", "Settings", "Settings"))
    assert drop_boilerplate(visits).lines_dropped == 0


def test_typed_line_in_eight_visits_kept() -> None:
    # A phrase you keep typing is a theme, not site chrome.
    visits = [visit(i, f"content {i}") for i in range(8)]
    visits = [replace(v, lines=(*v.lines, Line("case for an idea", Author.ME))) for v in visits]
    result = drop_boilerplate(visits)
    assert result.lines_dropped == 0


def test_same_text_dropped_where_read_kept_where_typed() -> None:
    visits = [visit(i, "Settings", f"content {i}") for i in range(8)]
    visits.append(replace(visit(8, "content 8"), lines=(Line("Settings", Author.ME),)))
    result = drop_boilerplate(visits)
    assert result.lines_dropped == 8
    assert result.visits[-1].lines == (Line("Settings", Author.ME),)


def test_visit_left_empty_is_removed() -> None:
    visits = [visit(i, "Settings", f"content {i}") for i in range(8)] + [visit(99, "Settings")]
    result = drop_boilerplate(visits)
    assert len(result.visits) == 8
    assert result.visits_emptied == 1
