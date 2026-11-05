from pathlib import Path

import pytest
from conftest import node, tree

from mind.clean.tree import CONTROL_ROLES, extract_lines
from mind.visit import Author, Line

TREES = Path(__file__).parent.parent / "data" / "trees"
GOLDEN_APPS = {
    "claude_chat": "Claude",
    "leetcode_problem": "Google Chrome",
    "mail_inbox": "Google Chrome",
    "terminal": "Terminal",
}


def texts(lines: list[Line]) -> list[str]:
    return [line.text for line in lines]


@pytest.mark.parametrize("role", sorted(CONTROL_ROLES))
def test_control_roles_dropped(role: str) -> None:
    assert extract_lines(tree(node("Settings panel", role)), None) == []


@pytest.mark.parametrize("role", ["AXStaticText", "AXLink", "AXHeading", "AXCell", "AXTextField"])
def test_content_roles_kept_as_read(role: str) -> None:
    assert extract_lines(tree(node("Reverse Pairs", role)), None) == [Line("Reverse Pairs")]


def test_fragments_on_one_row_glued_into_sentence() -> None:
    lines = extract_lines(
        tree(
            node("Given an integer array", left=0.02, width=0.15),
            node("nums", left=0.175, width=0.03),
            node(", return", left=0.205, width=0.04),
            node("the number of pairs.", left=0.25, width=0.1),
        ),
        None,
    )
    assert texts(lines) == ["Given an integer array nums, return the number of pairs."]


def test_fragment_sitting_slightly_lower_stays_on_the_line() -> None:
    # Inline code is often rendered a pixel or two lower than the text around it.
    lines = extract_lines(
        tree(
            node("Given an integer array", left=0.02, top=0.21, width=0.15),
            node("nums", left=0.175, top=0.213, width=0.03, height=0.017),
            node(", return the count", left=0.205, top=0.21, width=0.1),
        ),
        None,
    )
    assert texts(lines) == ["Given an integer array nums, return the count"]


def test_nodes_sharing_one_height_keep_screenpipes_order() -> None:
    # Regression: scrolling areas report many nodes at one height. Sorting that "row"
    # left to right shuffled paragraphs and code into one giant scrambled line.
    lines = extract_lines(
        tree(
            node("def", left=0.30, top=0.1, width=0.02),
            node("search", left=0.33, top=0.1, width=0.05),
            node("(mat):", left=0.39, top=0.1, width=0.05),
            node("lo = 0", left=0.30, top=0.1, width=0.05),
            node("hi = len", left=0.36, top=0.1, width=0.05),
        ),
        None,
    )
    assert texts(lines) == ["def search (mat):", "lo = 0 hi = len"]


def test_moving_down_starts_a_new_line() -> None:
    lines = extract_lines(
        tree(node("first line here", top=0.1), node("second line here", top=0.2)), None
    )
    assert texts(lines) == ["first line here", "second line here"]


def test_columns_at_same_height_stay_separate() -> None:
    lines = extract_lines(
        tree(
            node("Trip planning ideas", "AXLink", left=0.01, width=0.15),
            node("How do Python decorators work?", left=0.3, width=0.4),
        ),
        None,
    )
    assert texts(lines) == ["Trip planning ideas", "How do Python decorators work?"]


def test_nested_duplicate_kept_once() -> None:
    lines = extract_lines(
        tree(node("493. Reverse Pairs", "AXLink"), node("493. Reverse Pairs")), None
    )
    assert texts(lines) == ["493. Reverse Pairs"]


def test_text_area_tagged_me() -> None:
    lines = extract_lines(tree(node("show me an example please", "AXTextArea")), None)
    assert lines == [Line("show me an example please", Author.ME)]


def test_multiline_text_area_split_into_lines() -> None:
    lines = extract_lines(tree(node("first thought\n\nsecond thought", "AXTextArea")), None)
    assert lines == [Line("first thought", Author.ME), Line("second thought", Author.ME)]


@pytest.mark.parametrize("app", ["Terminal", "Code"])
def test_buffer_apps_text_area_is_read(app: str) -> None:
    # Their text area is terminal output or an open file, not something you typed.
    lines = extract_lines(tree(node("make test\n43 passed", "AXTextArea")), None, app)
    assert lines == [Line("make test"), Line("43 passed")]


@pytest.mark.parametrize("app", ["Google Chrome", "Claude", "Notion", "Typeless", None])
def test_other_apps_text_area_is_me(app: str | None) -> None:
    lines = extract_lines(tree(node("my own words here", "AXTextArea")), None, app)
    assert lines == [Line("my own words here", Author.ME)]


def test_typed_text_keeps_indentation_and_spacing() -> None:
    # Regression: punctuation tidying used to strip code indentation and "% make" spacing.
    lines = extract_lines(
        tree(node("def f(x):\n    return x  \nuser % make test", "AXTextArea")), None
    )
    assert texts(lines) == ["def f(x):", "    return x", "user % make test"]


def test_typed_and_read_text_stay_in_screenpipes_order() -> None:
    lines = extract_lines(
        tree(
            node("answer I read", top=0.4),
            node("question I typed", "AXTextArea", top=0.8),
            node("footer text here", top=0.9),
        ),
        None,
    )
    assert lines == [
        Line("answer I read"),
        Line("question I typed", Author.ME),
        Line("footer text here"),
    ]


@pytest.mark.parametrize("text", ["ok", "--", "·  ·", "1."])
def test_lines_with_fewer_than_three_alphanumerics_dropped(text: str) -> None:
    assert extract_lines(tree(node(text)), None) == []


def test_nodes_without_position_ignored() -> None:
    raw = '[{"role": "AXStaticText", "text": "no bounds here"}]'
    assert extract_lines(raw, None) == []


@pytest.mark.parametrize("tree_json", [None, "", "not json", '{"a": 1}'])
def test_unusable_tree_falls_back_to_full_text(tree_json: str | None) -> None:
    lines = extract_lines(tree_json, "Reverse Pairs\nok\n  Example  1: \n")
    assert texts(lines) == ["Reverse Pairs", "Example 1:"]


def test_golden_screens_present() -> None:
    # Regression: a too-broad .gitignore once kept tests/data out of git, so CI collected
    # zero golden cases and silently skipped them. Fail loudly instead.
    assert set(GOLDEN_APPS) == {p.stem for p in TREES.glob("*.json")}


@pytest.mark.parametrize("name", sorted(GOLDEN_APPS))
def test_golden(name: str, update_golden: bool) -> None:
    """Whole synthetic screens -> expected lines. Run `pytest --update-golden` to rewrite."""
    lines = extract_lines((TREES / f"{name}.json").read_text(), None, GOLDEN_APPS[name])
    actual = "".join(f"[{line.author}] {line.text}\n" for line in lines)
    golden = TREES / f"{name}.golden.txt"
    if update_golden:
        golden.write_text(actual)
    assert actual == golden.read_text()
