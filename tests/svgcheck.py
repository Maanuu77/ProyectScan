"""Helpers to inspect a rendered diagram in tests."""

import xml.etree.ElementTree as ElementTree

from repo_xray.render.svg import text_width

SVG = "{http://www.w3.org/2000/svg}"


def parse(svg: str) -> ElementTree.Element:
    return ElementTree.fromstring(svg)


def texts(svg: str) -> list[str]:
    return [element.text for element in parse(svg).iter(f"{SVG}text")]


def by_id(svg: str, element_id: str) -> ElementTree.Element | None:
    return next((e for e in parse(svg).iter() if e.attrib.get("id") == element_id), None)


def ids(svg: str) -> list[str]:
    return [e.attrib["id"] for e in parse(svg).iter() if "id" in e.attrib]


def box(element: ElementTree.Element) -> tuple[float, float, float, float]:
    """x, y, width and height of a <rect>."""
    return tuple(float(element.attrib[name]) for name in ("x", "y", "width", "height"))


def text_span(element: ElementTree.Element) -> tuple[float, float]:
    """Where a <text> starts and ends horizontally, measured the way the renderers measure."""
    x, size = float(element.attrib["x"]), float(element.attrib["font-size"])
    width = text_width(element.text or "", size, int(element.attrib.get("font-weight", 400)),
                       mono="font-family" in element.attrib)
    anchor = element.attrib.get("text-anchor", "start")
    if anchor == "end":
        return x - width, x
    if anchor == "middle":
        return x - width / 2, x + width / 2
    return x, x + width


def overflowing(svg: str, margin: float = 0) -> list[str]:
    """Texts that reach outside the canvas, or closer to its edges than `margin`."""
    root = parse(svg)
    width = float(root.attrib["width"])
    return [e.text for e in root.iter(f"{SVG}text")
            if text_span(e)[0] < margin - 0.01 or text_span(e)[1] > width - margin + 0.01]


def texts_outside_their_card(svg: str, card_id: str) -> list[str]:
    """Texts that start inside the card named `card_id` but run past its right edge."""
    x, y, width, height = box(by_id(svg, card_id))
    outside = []
    for element in parse(svg).iter(f"{SVG}text"):
        start, end = text_span(element)
        baseline = float(element.attrib["y"])
        if x <= start <= x + width and y <= baseline <= y + height and end > x + width + 0.01:
            outside.append(element.text)
    return outside
