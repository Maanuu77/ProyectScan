"""A tiny SVG writer and text measurement.

Diagrams use only SVG Tiny features (no CSS, markers or filters) so that
browsers, GitHub and Qt's renderer (preview and PNG export) draw them the
same way.
"""

from xml.sax.saxutils import escape, quoteattr

FONT_FAMILY = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

# Advance widths of Helvetica/Arial in 1/1000 em for printable ASCII (32-126).
_WIDTHS = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
]
# Segoe UI and San Francisco run wider than Arial; measuring a bit wide keeps text inside its box.
_SAFETY = 1.08
_BOLD = 1.07


def text_width(text: str, size: float, weight: int = 400) -> float:
    units = sum(_WIDTHS[ord(c) - 32] if 32 <= ord(c) <= 126 else 600 for c in text)
    factor = _BOLD if weight >= 600 else 1.0
    return units / 1000 * size * _SAFETY * factor


def fit_text(text: str, max_width: float, size: float, weight: int = 400) -> str:
    """Shorten `text` with an ellipsis so it fits in `max_width`."""
    if text_width(text, size, weight) <= max_width:
        return text
    while text and text_width(text + "…", size, weight) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def wrap_text(text: str, max_width: float, size: float, weight: int = 400, max_lines: int = 3) -> list[str]:
    """Split `text` into lines no wider than `max_width`; the last line is shortened if needed."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if text_width(candidate, size, weight) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit_text(lines[-1] + " …", max_width, size, weight)
    return [fit_text(line, max_width, size, weight) for line in lines]


def _number(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


class Svg:
    def __init__(self, width: float, height: float, background: str, title: str, description: str):
        self.width = width
        self.height = height
        self.parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{_number(width)}" height="{_number(height)}" '
            f'viewBox="0 0 {_number(width)} {_number(height)}" role="img" font-family={quoteattr(FONT_FAMILY)}>',
            f"<title>{escape(title)}</title>",
            f"<desc>{escape(description)}</desc>",
        ]
        self.rect(0, 0, width, height, fill=background)

    def _element(self, tag: str, attributes: dict, content: str | None = None) -> None:
        rendered = " ".join(
            f"{key.rstrip('_').replace('_', '-')}={quoteattr(_number(v) if isinstance(v, float) else str(v))}"
            for key, value in attributes.items() if value is not None for v in [value]
        )
        if content is None:
            self.parts.append(f"<{tag} {rendered}/>")
        else:
            self.parts.append(f"<{tag} {rendered}>{content}</{tag}>")

    def rect(self, x: float, y: float, width: float, height: float, radius: float = 0, **style) -> None:
        self._element("rect", {"x": float(x), "y": float(y), "width": float(width), "height": float(height),
                               "rx": float(radius) if radius else None, **style})

    def circle(self, cx: float, cy: float, r: float, **style) -> None:
        self._element("circle", {"cx": float(cx), "cy": float(cy), "r": float(r), **style})

    def line(self, x1: float, y1: float, x2: float, y2: float, **style) -> None:
        self._element("line", {"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2), **style})

    def path(self, d: str, **style) -> None:
        self._element("path", {"d": d, **style})

    def polygon(self, points: list[tuple[float, float]], **style) -> None:
        self._element("polygon", {"points": " ".join(f"{_number(x)},{_number(y)}" for x, y in points), **style})

    def text(self, x: float, y: float, content: str, size: float, fill: str, weight: int = 400,
             anchor: str = "start", letter_spacing: float | None = None) -> None:
        """`y` is the baseline."""
        self._element("text", {
            "x": float(x), "y": float(y), "font_size": float(size), "font_weight": weight, "fill": fill,
            "text_anchor": anchor if anchor != "start" else None,
            "letter_spacing": float(letter_spacing) if letter_spacing else None,
        }, escape(content))

    def group_start(self, transform: str | None = None, opacity: float | None = None) -> None:
        attributes = {"transform": transform, "opacity": float(opacity) if opacity is not None else None}
        rendered = " ".join(f"{k}={quoteattr(_number(v) if isinstance(v, float) else v)}"
                            for k, v in attributes.items() if v is not None)
        self.parts.append(f"<g {rendered}>" if rendered else "<g>")

    def group_end(self) -> None:
        self.parts.append("</g>")

    def to_string(self) -> str:
        return "\n".join([*self.parts, "</svg>"]) + "\n"
