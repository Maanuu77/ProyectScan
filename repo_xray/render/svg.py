"""A tiny SVG writer and text measurement.

Diagrams use only SVG Tiny features (no CSS, markers, filters, clipping or
arc commands) so that browsers, GitHub and Qt's renderer (preview and PNG
export) draw them the same way.

SVG has no layout engine: nothing wraps or truncates by itself, and the
font is whatever the reader's system offers. So every text is measured
here, a little wide, before it is placed.
"""

import re
import unicodedata
from functools import lru_cache
from xml.sax.saxutils import escape, quoteattr

FONT_FAMILY = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO_FAMILY = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

# Advance widths of Helvetica/Arial in 1/1000 em for printable ASCII (32-126).
_WIDTHS = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
]
# Common characters outside ASCII that are not an accented letter.
_EXTRA = {
    "·": 278, "•": 350, "…": 1000, "–": 556, "—": 1000, "‘": 222, "’": 222, "“": 333, "”": 333,
    "«": 556, "»": 556, "¿": 611, "¡": 333, "°": 400, "×": 584, "€": 556, "£": 556, " ": 278,
    "→": 1000, "←": 1000, "↔": 1000, "↑": 500, "↓": 500, "≥": 549, "≤": 549, "≈": 549,
    "ß": 611, "æ": 889, "ø": 611, "Æ": 1000, "Ø": 778, "©": 737, "®": 737, "™": 1000, "✓": 800,
}
_UNKNOWN = 600  # letters of other scripts: closer to the average than to the widest
_WIDE = 1000  # CJK and emoji fill the em square
_MONO = 610  # Menlo and SF Mono are 602, Consolas 550: measuring for the widest keeps text in its box
# Segoe UI and San Francisco run wider than Arial; measuring a bit wide keeps text inside its box.
_SAFETY = 1.08
_BOLD = 1.07

ELLIPSIS = "…"
# Places where a long identifier may be split: after a separator, or between "lower" and "Upper".
_SOFT_BREAK = re.compile(r"(?<=[/._\-:,;=&?])|(?<=[a-z0-9])(?=[A-Z])")


@lru_cache(maxsize=4096)
def _units(char: str) -> int:
    code = ord(char)
    if 32 <= code <= 126:
        return _WIDTHS[code - 32]
    if char in _EXTRA:
        return _EXTRA[char]
    category = unicodedata.category(char)
    if category in ("Mn", "Me", "Cf"):  # combining accents and zero-width joiners take no room
        return 0
    base = unicodedata.normalize("NFD", char)[0]
    if base != char and 32 <= ord(base) <= 126:  # an accented letter is as wide as its base: é like e
        return _WIDTHS[ord(base) - 32]
    if unicodedata.east_asian_width(char) in ("W", "F") or category == "So":
        return _WIDE
    return _UNKNOWN


def text_width(text: str, size: float, weight: int = 400, mono: bool = False) -> float:
    """How wide `text` is drawn, in pixels, measured slightly wide so it never overflows."""
    if mono:
        return sum(_MONO if _units(c) else 0 for c in text) / 1000 * size
    factor = _BOLD if weight >= 600 else 1.0
    return sum(_units(c) for c in text) / 1000 * size * _SAFETY * factor


def fit_text(text: str, max_width: float, size: float, weight: int = 400, mono: bool = False) -> str:
    """Shorten `text` with an ellipsis at the end so it fits in `max_width`."""
    if text_width(text, size, weight, mono) <= max_width:
        return text
    low, high = 0, len(text)  # the longest prefix that fits with the ellipsis, by bisection
    while low < high:
        middle = (low + high + 1) // 2
        if text_width(text[:middle].rstrip() + ELLIPSIS, size, weight, mono) <= max_width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + ELLIPSIS


def fit_middle(text: str, max_width: float, size: float, weight: int = 400, mono: bool = False) -> str:
    """Shorten `text` in the middle, keeping its start and its end: `/api/v1/…/{id}/revision`.

    For routes, paths and qualified names, where the end says as much as the start.
    """
    if text_width(text, size, weight, mono) <= max_width:
        return text
    keep = len(text) - 1
    while keep > 1:
        head = (keep + 1) // 2
        candidate = text[:head].rstrip() + ELLIPSIS + text[len(text) - (keep - head):].lstrip()
        if text_width(candidate, size, weight, mono) <= max_width:
            return candidate
        keep -= 1
    return fit_text(text, max_width, size, weight, mono)


def wrap_text(text: str, max_width: float, size: float, weight: int = 400, max_lines: int = 3,
              mono: bool = False) -> list[str]:
    """Split `text` into lines no wider than `max_width`; the last line is shortened if needed.

    A word wider than a whole line (a long identifier, a route) is split where it reads best:
    after `/`, `.`, `-` or `_`, or between the words of a camelCase name.
    """
    lines: list[str] = []
    current = ""
    for word in text.split():
        pieces = [word] if text_width(word, size, weight, mono) <= max_width else _pieces(
            word, max_width, size, weight, mono)
        for index, piece in enumerate(pieces):
            glue = " " if index == 0 and current else ""
            if text_width(current + glue + piece, size, weight, mono) <= max_width or not current:
                current = current + glue + piece
            else:
                lines.append(current)
                current = piece
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit_text(lines[-1].rstrip(" .,;:") + ELLIPSIS, max_width, size, weight, mono)
    return [fit_text(line, max_width, size, weight, mono) for line in lines]


def _pieces(word: str, max_width: float, size: float, weight: int, mono: bool) -> list[str]:
    """Cut a word that is wider than a line into parts that fit, at soft breaks when there are any."""
    pieces: list[str] = []
    for part in (p for p in _SOFT_BREAK.split(word) if p):
        while text_width(part, size, weight, mono) > max_width and len(part) > 1:
            cut = len(part) - 1
            while cut > 1 and text_width(part[:cut], size, weight, mono) > max_width:
                cut -= 1
            pieces.append(part[:cut])
            part = part[cut:]
        pieces.append(part)
    return pieces


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
        """A rectangle. `id="…"` names it, so a viewer can find it and make it clickable."""
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
             anchor: str = "start", letter_spacing: float | None = None, mono: bool = False) -> None:
        """`y` is the baseline. `mono` draws code (routes, identifiers) in a monospaced font."""
        self._element("text", {
            "x": float(x), "y": float(y), "font_size": float(size), "font_weight": weight, "fill": fill,
            "font_family": MONO_FAMILY if mono else None,
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
