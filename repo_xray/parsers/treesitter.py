"""Small helpers shared by the tree-sitter parsers (see ADR-0007)."""

import re

from tree_sitter import Node

_JSDOC_LINE_PREFIX = re.compile(r"^\s*\*\s?")


def text(node: Node | None) -> str:
    return node.text.decode("utf-8", errors="replace") if node is not None and node.text else ""


def line(node: Node) -> int:
    return node.start_point[0] + 1


def end_line(node: Node) -> int:
    return node.end_point[0] + 1


def doc_comment(node: Node) -> str | None:
    """The `/** ... */` comment right before `node`, without markers or `@tags`."""
    previous = node.prev_named_sibling
    if previous is None or "comment" not in previous.type:
        return None
    raw = text(previous)
    if not raw.startswith("/**") or previous.end_point[0] < node.start_point[0] - 1:
        return None
    lines = [_JSDOC_LINE_PREFIX.sub("", part) for part in raw[3:-2].splitlines()]
    kept = []
    for part in lines:
        if part.lstrip().startswith("@"):
            break
        kept.append(part.strip())
    cleaned = " ".join(p for p in kept if p)
    return cleaned or None


def string_value(node: Node) -> str | None:
    """Value of a plain string literal, or None if `node` is not one."""
    if node.type in ("string_literal", "string"):
        return "".join(text(c) for c in node.named_children if c.type in ("string_fragment", "escape_sequence"))
    return None


def descendants(node: Node, *types: str):
    """Every descendant of `node` whose type is in `types`, in source order."""
    stack = list(reversed(node.children))
    while stack:
        current = stack.pop()
        if current.type in types:
            yield current
        stack.extend(reversed(current.children))
