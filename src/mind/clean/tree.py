"""Structure step: one frame's accessibility tree -> clean, readable lines.

Screenpipe stores every piece of on-screen text as a node with a role and a position.
This step uses both (decision 001, N5 steps 1 and 2):

  1. Drop controls (buttons, tabs, checkboxes, dropdowns) by role.
  2. Glue neighboring fragments back into sentences, so "Given an integer array"
     + "nums" + ", return" becomes one line.

Nodes are read in Screenpipe's order, which is reading order. Positions only decide where
a line ends. They can't be used to sort: in a scrolling area, an app may report hundreds
of nodes at one height, and sorting those left to right shuffles paragraphs and code.

Text the user typed (AXTextArea) is kept as its own block and tagged `me`.
Falls back to the flat `full_text` when a frame has no usable tree.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from mind.visit import Author, Line

CONTROL_ROLES = frozenset(
    {
        "AXButton",
        "AXRadioButton",  # includes Chrome's tab strip
        "AXPopUpButton",
        "AXCheckBox",
        "AXComboBox",
        "AXMenuItem",
        "AXMenuButton",
        "AXDisclosureTriangle",
    }
)
TYPED_ROLE = "AXTextArea"
# Apps whose text area is a display buffer (terminal output, an open file), not a box
# you type into. Their text is `read`, so `me` stays trustworthy (decision 002 amendment).
BUFFER_APPS = frozenset({"Terminal", "Code"})
MIN_ALNUM = 3
# Neighboring fragments further apart than this (fraction of screen width) are
# separate columns, e.g. a sidebar next to the main content.
COLUMN_GAP = 0.04

_ALNUM = re.compile(r"[A-Za-z0-9]")
_SPACE_BEFORE_CLOSE = re.compile(r"\s+([,.;:!?%)\]}])")
_SPACE_AFTER_OPEN = re.compile(r"([(\[{])\s+")


@dataclass(frozen=True)
class Node:
    role: str
    text: str
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def center_y(self) -> float:
        return self.top + self.height / 2


def parse_nodes(tree_json: str) -> list[Node] | None:
    """Nodes that have text and a position. None if the JSON isn't a usable tree."""
    try:
        raw = json.loads(tree_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, list):
        return None
    nodes = []
    for item in raw:
        node = _to_node(item)
        if node is not None:
            nodes.append(node)
    return nodes


def _to_node(item: Any) -> Node | None:
    if not isinstance(item, dict):
        return None
    text, bounds = item.get("text"), item.get("bounds")
    if not isinstance(text, str) or not text.strip() or not isinstance(bounds, dict):
        return None
    try:
        return Node(
            role=str(item.get("role", "")),
            text=text,
            left=float(bounds["left"]),
            top=float(bounds["top"]),
            width=float(bounds["width"]),
            height=float(bounds["height"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def has_enough_text(line: str) -> bool:
    return len(_ALNUM.findall(line)) >= MIN_ALNUM


def tidy(text: str) -> str:
    """Collapse whitespace and remove spaces glued in front of punctuation."""
    text = " ".join(text.split())
    text = _SPACE_BEFORE_CLOSE.sub(r"\1", text)
    return _SPACE_AFTER_OPEN.sub(r"\1", text)


def starts_new_line(line: list[Node], node: Node) -> bool:
    """A node ends the current line if it moved down or up, jumped back left, or jumped
    far right. Slightly lower inline fragments (like `code` in a sentence) stay on the line."""
    prev = line[-1]
    top, bottom = min(n.top for n in line), max(n.bottom for n in line)
    return (
        not top <= node.center_y <= bottom
        or node.left < prev.left
        or node.left - prev.right > COLUMN_GAP
    )


def is_nested_duplicate(prev: Node, node: Node) -> bool:
    """The same text at the same spot, e.g. a link and the text inside it."""
    return node.text == prev.text and node.left < prev.right


def extract_lines(
    tree_json: str | None, full_text: str | None, app: str | None = None
) -> list[Line]:
    nodes = parse_nodes(tree_json) if tree_json else None
    if nodes is None:
        return _from_full_text(full_text)
    typed_author = Author.READ if app in BUFFER_APPS else Author.ME

    lines: list[Line] = []
    current: list[Node] = []

    def finish_line() -> None:
        text = tidy(" ".join(n.text for n in current))
        if has_enough_text(text):
            lines.append(Line(text))
        current.clear()

    for node in nodes:
        if node.role in CONTROL_ROLES:
            continue
        if node.role == TYPED_ROLE:
            finish_line()
            # Typed text is kept as typed: indentation and spacing can matter (code, commands).
            typed = (t.rstrip() for t in node.text.splitlines())
            lines.extend(Line(t, typed_author) for t in typed if has_enough_text(t))
        elif current and starts_new_line(current, node):
            finish_line()
            current.append(node)
        elif not (current and is_nested_duplicate(current[-1], node)):
            current.append(node)
    finish_line()
    return lines


def _from_full_text(full_text: str | None) -> list[Line]:
    if not full_text:
        return []
    return [Line(t) for raw in full_text.splitlines() if has_enough_text(t := tidy(raw))]
