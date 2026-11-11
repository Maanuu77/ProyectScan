"""The parts every diagram is built from, so the three levels read as one family.

A diagram is a header (which level, which question, which project), a few
zones that group cards, connectors between them and a footer. Each part
is drawn here once; the three renderers only decide where things go.
"""

from repo_xray.render import theme as t
from repo_xray.render.svg import Svg, fit_middle, fit_text, text_width, wrap_text

PAD = 40  # margin around every diagram
CARD_RADIUS = 12
ZONE_RADIUS = 16
ZONE_PAD = 16  # between a zone's border and its cards
ZONE_HEADER = 40  # room for a zone's caption above its cards

TITLE_Y = PAD + 46  # baseline of the title's first line
TITLE_LINE = 32
FOOTER_SPACE = 32 + 26 + PAD  # gap, rule to text, margin: what a footer adds below the content

CHIP_HEIGHT = 24
CHIP_GAP = 6
PILL_HEIGHT = 20


# Header and footer


def title_lines(title: str, width: float, max_lines: int = 1) -> list[str]:
    return wrap_text(title, width - PAD * 2, t.TITLE, 700, max_lines=max_lines)


def header(svg: Svg, th: t.Theme, level: int, kicker: str, lines: list[str]) -> float:
    """The level marker, the question the diagram answers and its title.

    Returns the baseline for whatever comes under the title.
    """
    level_marker(svg, th, PAD, PAD + 3, level)
    svg.text(PAD + 58, PAD + 10, kicker, t.LABEL, th.text_muted, weight=700, letter_spacing=1)
    for index, line in enumerate(lines):
        svg.text(PAD, TITLE_Y + index * TITLE_LINE, line, t.TITLE, th.text, weight=700)
    return header_bottom(len(lines))


def header_bottom(lines: int = 1) -> float:
    """Baseline of the line under a title of `lines` lines."""
    return TITLE_Y + (lines - 1) * TITLE_LINE + 25


def level_marker(svg: Svg, th: t.Theme, x: float, y: float, level: int) -> None:
    """Three small bars, the current level filled in: which of the three questions this diagram answers."""
    for index in range(3):
        colour = th.text if index == level - 1 else th.border
        svg.rect(x + index * 17, y, 13, 5, 2.5, fill=colour)


def footer(svg: Svg, th: t.Theme, width: float, height: float, left: str | None, credit: str,
           legend: list[tuple[str, str]] | None = None) -> None:
    """A rule and one line under the content: a note or a legend on the left, the credit on the right."""
    baseline = height - PAD
    svg.line(PAD, baseline - 26, width - PAD, baseline - 26, stroke=th.zone_border, stroke_width=1)
    credit_width = text_width(credit, t.SMALL)
    svg.text(width - PAD, baseline, credit, t.SMALL, th.text_subtle, anchor="end")
    room = width - PAD * 2 - credit_width - 24
    if legend:
        x = PAD
        for colour, label in legend:
            needed = 20 + text_width(label, t.SMALL)
            if x + needed > PAD + room:
                break
            svg.rect(x, baseline - 9, 14, 6, 3, fill=colour, fill_opacity=0.6)
            svg.text(x + 20, baseline, label, t.SMALL, th.text_muted)
            x += needed + 22
    elif left:
        svg.text(PAD, baseline, fit_text(left, room, t.SMALL), t.SMALL, th.text_muted)


# Containers


def zone(svg: Svg, th: t.Theme, x: float, y: float, width: float, height: float, label: str | None = None) -> None:
    """A soft panel that groups cards; its caption sits in the top-left corner."""
    svg.rect(x, y, width, height, ZONE_RADIUS, fill=th.zone, stroke=th.zone_border, stroke_width=1)
    if label:
        svg.text(x + ZONE_PAD + 2, y + 25, fit_text(label, width - ZONE_PAD * 2 - 4, t.LABEL, 700), t.LABEL,
                 th.text_subtle, weight=700, letter_spacing=1)


def card(svg: Svg, th: t.Theme, x: float, y: float, width: float, height: float, element_id: str | None = None,
         stroke: str | None = None, dashed: bool = False, muted: bool = False) -> None:
    svg.rect(x, y, width, height, CARD_RADIUS, fill=th.surface_muted if muted else th.surface,
             stroke=stroke or th.border, stroke_width=1.5 if stroke else 1,
             stroke_dasharray="4 4" if dashed else None, id=element_id)


def icon_tile(svg: Svg, th: t.Theme, kind: str, x: float, y: float, size: float = 40,
              accent: t.Accent | None = None) -> None:
    """An icon on a tinted rounded square."""
    accent = accent or th.accent(kind)
    glyph = round(size * 0.55)
    svg.rect(x, y, size, size, size * 0.25, fill=accent.soft)
    t.icon(svg, kind, x + (size - glyph) / 2, y + (size - glyph) / 2, glyph, accent.strong)


# Small parts


def chip_width(text: str, dot: bool = False, mono: bool = False) -> float:
    return text_width(text, t.SMALL, mono=mono) + (28 if dot else 18)


def chip(svg: Svg, th: t.Theme, x: float, y: float, text: str, dot: str | None = None, hollow: bool = False,
         radius: float = 6) -> float:
    """A small labelled box for a technology or a related feature. Returns its width."""
    width = chip_width(text, dot=bool(dot) or hollow)
    svg.rect(x, y, width, CHIP_HEIGHT, radius, fill=th.surface_muted, stroke=th.border, stroke_width=1)
    if dot:
        svg.circle(x + 13, y + CHIP_HEIGHT / 2, 4, fill=dot)
    elif hollow:
        svg.circle(x + 13, y + CHIP_HEIGHT / 2, 3.5, fill="none", stroke=th.text_muted, stroke_width=1.5)
    svg.text(x + (23 if dot or hollow else 9), y + 16.5, text, t.SMALL, th.text)
    return width


def pill(svg: Svg, th: t.Theme, cx: float, cy: float, text: str, colour: str | None = None,
         border: str | None = None, weight: int = 400) -> float:
    """A label centred on a connector, on the canvas colour so the line seems to pass behind it."""
    width = text_width(text, t.LABEL, weight) + 18
    svg.rect(cx - width / 2, cy - PILL_HEIGHT / 2, width, PILL_HEIGHT, PILL_HEIGHT / 2, fill=th.background,
             stroke=border or th.border, stroke_width=1)
    svg.text(cx, cy + 4, text, t.LABEL, colour or th.text_muted, weight=weight, anchor="middle")
    return width


def pill_width(text: str, weight: int = 400) -> float:
    return text_width(text, t.LABEL, weight) + 18


def method_badge_width(method: str) -> float:
    return text_width(method, t.LABEL, 700) + 14


def method_badge(svg: Svg, th: t.Theme, x: float, y: float, method: str, height: float = 18) -> float:
    """`GET`, `POST`… in the colour of what the request does. Returns its width."""
    accent = th.accent(t.METHOD_ACCENTS.get(method, "neutral"))
    width = method_badge_width(method)
    svg.rect(x, y, width, height, 5, fill=accent.soft)
    svg.text(x + width / 2, y + height / 2 + 4, method, t.LABEL, accent.strong, weight=700, anchor="middle")
    return width


def route_width(method: str, route: str, max_width: float) -> float:
    return min(method_badge_width(method) + 8 + text_width(route, t.LABEL, mono=True) + 20, max_width)


def route_pill(svg: Svg, th: t.Theme, x: float, cy: float, method: str, route: str, max_width: float) -> float:
    """An HTTP request as it travels: the method's badge, then the route in code type. Returns its width."""
    height = 26
    badge = method_badge_width(method)
    width = route_width(method, route, max_width)
    svg.rect(x, cy - height / 2, width, height, height / 2, fill=th.background, stroke=th.border_strong,
             stroke_width=1)
    method_badge(svg, th, x + 5, cy - 9, method)
    shown = fit_middle(route, width - badge - 8 - 15, t.LABEL, mono=True)
    svg.text(x + 5 + badge + 8, cy + 4, shown, t.LABEL, th.text, mono=True)
    return width


def arrow_head(svg: Svg, x: float, y: float, dx: float, dy: float, colour: str, size: float = 7.5) -> None:
    """Filled triangle with its tip at (x, y), pointing along the unit vector (dx, dy)."""
    half = size * 0.55
    bx, by = x - dx * size, y - dy * size
    svg.polygon([(x, y), (bx - dy * half, by + dx * half), (bx + dy * half, by - dx * half)], fill=colour)


def curve(svg: Svg, x1: float, y1: float, x2: float, y2: float, colour: str, width: float = 1.5,
          opacity: float | None = None) -> None:
    """A horizontal S-curve from (x1, y1) to (x2, y2), ending in an arrow head."""
    bend = (x2 - x1) * 0.5
    svg.path(f"M {x1:.1f} {y1:.1f} C {x1 + bend:.1f} {y1:.1f} {x2 - bend:.1f} {y2:.1f} {x2 - 5:.1f} {y2:.1f}",
             fill="none", stroke=colour, stroke_width=width, stroke_opacity=opacity, stroke_linecap="round")
    arrow_head(svg, x2, y2, 1, 0, colour)


def curve_point(x1: float, y1: float, x2: float, y2: float, u: float) -> tuple[float, float]:
    """The point at `u` (0 to 1) along the curve that `curve()` draws."""
    bend = (x2 - x1) * 0.5
    a, b, c, d = (1 - u) ** 3, 3 * (1 - u) ** 2 * u, 3 * (1 - u) * u ** 2, u ** 3
    return (a * x1 + b * (x1 + bend) + c * (x2 - bend) + d * x2, a * y1 + b * y1 + c * y2 + d * y2)


def polyline(svg: Svg, points: list[tuple[float, float]], colour: str, width: float = 1.5, radius: float = 10,
             dashed: bool = False, arrow: bool = True) -> None:
    """A connector along straight segments with rounded corners, ending in an arrow head."""
    (ax, ay), (bx, by) = points[-2], points[-1]
    length = max(((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5, 1)
    ux, uy = (bx - ax) / length, (by - ay) / length
    end = (bx - ux * 5, by - uy * 5) if arrow else (bx, by)  # the line stops inside the arrow head
    path = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    for index in range(1, len(points) - 1):
        (px, py), (cx, cy), (nx, ny) = points[index - 1], points[index], points[index + 1]
        before = max(((cx - px) ** 2 + (cy - py) ** 2) ** 0.5, 1)
        after = max(((nx - cx) ** 2 + (ny - cy) ** 2) ** 0.5, 1)
        r = min(radius, before / 2, after / 2)
        path.append(f"L {cx - (cx - px) / before * r:.1f} {cy - (cy - py) / before * r:.1f}")
        path.append(f"Q {cx:.1f} {cy:.1f} {cx + (nx - cx) / after * r:.1f} {cy + (ny - cy) / after * r:.1f}")
    path.append(f"L {end[0]:.1f} {end[1]:.1f}")
    svg.path(" ".join(path), fill="none", stroke=colour, stroke_width=width, stroke_linecap="round",
             stroke_dasharray="5 4" if dashed else None)
    if arrow:
        arrow_head(svg, bx, by, ux, uy, colour)


def stat_width(value: str, label: str) -> float:
    return text_width(value, t.BODY, 700) + 5 + text_width(label, t.SMALL)


def stat(svg: Svg, th: t.Theme, x: float, y: float, value: str, label: str) -> float:
    """A number that stands out and the word that says what it counts. Returns its width."""
    svg.text(x, y, value, t.BODY, th.text, weight=700)
    svg.text(x + text_width(value, t.BODY, 700) + 5, y, label, t.SMALL, th.text_muted)
    return stat_width(value, label)
