"""Colours, type scale and icons shared by every diagram.

The light and dark palettes follow GitHub's own colours, so the diagrams
look native in a README in either theme.
"""

from dataclasses import dataclass

from repo_xray.render.svg import Svg


@dataclass(frozen=True)
class Accent:
    strong: str  # icons, labels, connector highlights
    soft: str  # tinted backgrounds


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    surface: str
    surface_muted: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_subtle: str
    connector: str
    accents: dict[str, Accent]

    def accent(self, key: str) -> Accent:
        return self.accents.get(key, self.accents["neutral"])


LIGHT = Theme(
    name="light",
    background="#ffffff",
    surface="#ffffff",
    surface_muted="#f6f8fa",
    border="#d1d9e0",
    border_strong="#afb8c1",
    text="#1f2328",
    text_muted="#59636e",
    text_subtle="#818b98",
    connector="#8c959f",
    accents={
        "web": Accent("#8250df", "#fbefff"),
        "api": Accent("#1a7f37", "#dafbe1"),
        "mobile": Accent("#bc4c00", "#fff1e5"),
        "desktop": Accent("#0969da", "#ddf4ff"),
        "library": Accent("#59636e", "#f6f8fa"),
        "database": Accent("#9a6700", "#fff8c5"),
        "auth": Accent("#bf3989", "#ffeff7"),
        "storage": Accent("#1b7c83", "#d8f6f8"),
        "cache": Accent("#cf222e", "#ffebe9"),
        "messaging": Accent("#6639ba", "#f5f0ff"),
        "search": Accent("#4d7c0f", "#ecfccb"),
        "platform": Accent("#57606a", "#f6f8fa"),
        "external": Accent("#57606a", "#f6f8fa"),
        "users": Accent("#1f2328", "#f6f8fa"),
        "neutral": Accent("#59636e", "#f6f8fa"),
    },
)

DARK = Theme(
    name="dark",
    background="#0d1117",
    surface="#151b23",
    surface_muted="#1b222c",
    border="#3d444d",
    border_strong="#656c76",
    text="#f0f6fc",
    text_muted="#9198a1",
    text_subtle="#6e7681",
    connector="#656c76",
    accents={
        "web": Accent("#ab7df8", "#271c3a"),
        "api": Accent("#3fb950", "#14261b"),
        "mobile": Accent("#f0883e", "#2e1d10"),
        "desktop": Accent("#4493f8", "#0f2236"),
        "library": Accent("#9198a1", "#1b222c"),
        "database": Accent("#d29922", "#2a2210"),
        "auth": Accent("#db61a2", "#2d1424"),
        "storage": Accent("#39c5cf", "#0d2a2d"),
        "cache": Accent("#f85149", "#2d1215"),
        "messaging": Accent("#bc8cff", "#231b36"),
        "search": Accent("#a3e635", "#1c2610"),
        "platform": Accent("#9198a1", "#1b222c"),
        "external": Accent("#9198a1", "#1b222c"),
        "users": Accent("#f0f6fc", "#1b222c"),
        "neutral": Accent("#9198a1", "#1b222c"),
    },
)

THEMES = {"light": LIGHT, "dark": DARK}

# Type scale in px.
TITLE = 26
HEADING = 17
BODY = 13
SMALL = 12
LABEL = 11


def icon(svg: Svg, kind: str, x: float, y: float, size: float, color: str) -> None:
    """Draw a simple outline icon with its top-left corner at (x, y)."""
    s = size / 24
    stroke = {"fill": "none", "stroke": color, "stroke_width": max(1.5, 1.8 * s),
              "stroke_linecap": "round", "stroke_linejoin": "round"}

    def p(*points: tuple[float, float]) -> list[tuple[float, float]]:
        return [(x + px * s, y + py * s) for px, py in points]

    def d(commands: str) -> str:
        # Commands written on a 24x24 grid; every number pair is scaled and offset.
        out, numbers = [], []
        for token in commands.replace(",", " ").split():
            if token.isalpha():
                out.append(token)
            else:
                numbers.append(float(token))
                if len(numbers) == 2:
                    out.append(f"{x + numbers[0] * s:.1f} {y + numbers[1] * s:.1f}")
                    numbers = []
        return " ".join(out)

    if kind == "users":
        svg.circle(x + 12 * s, y + 8 * s, 4 * s, **stroke)
        svg.path(d("M 4 21 C 4 16 8 14 12 14 C 16 14 20 16 20 21"), **stroke)
    elif kind == "web":
        svg.rect(x + 2 * s, y + 4 * s, 20 * s, 16 * s, 2.5 * s, **stroke)
        svg.line(*p((2, 9))[0], *p((22, 9))[0], **stroke)
        svg.circle(x + 5.5 * s, y + 6.5 * s, 0.6 * s, fill=color)
        svg.circle(x + 8 * s, y + 6.5 * s, 0.6 * s, fill=color)
    elif kind == "api":
        svg.rect(x + 3 * s, y + 3 * s, 18 * s, 7.5 * s, 2 * s, **stroke)
        svg.rect(x + 3 * s, y + 13.5 * s, 18 * s, 7.5 * s, 2 * s, **stroke)
        svg.circle(x + 7 * s, y + 6.75 * s, 0.9 * s, fill=color)
        svg.circle(x + 7 * s, y + 17.25 * s, 0.9 * s, fill=color)
    elif kind == "mobile":
        svg.rect(x + 6 * s, y + 2 * s, 12 * s, 20 * s, 2.5 * s, **stroke)
        svg.line(*p((10.5, 18.5))[0], *p((13.5, 18.5))[0], **stroke)
    elif kind == "desktop":
        svg.rect(x + 2 * s, y + 3 * s, 20 * s, 13 * s, 2 * s, **stroke)
        svg.line(*p((12, 16))[0], *p((12, 20))[0], **stroke)
        svg.line(*p((8, 21))[0], *p((16, 21))[0], **stroke)
    elif kind == "database":
        svg.path(d("M 4 6 C 4 3.3 20 3.3 20 6 C 20 8.7 4 8.7 4 6 Z"), **stroke)
        svg.path(d("M 4 6 L 4 18 C 4 20.7 20 20.7 20 18 L 20 6"), **stroke)
        svg.path(d("M 4 12 C 4 14.7 20 14.7 20 12"), **stroke)
    elif kind == "auth":
        svg.path(d("M 12 2.5 L 20 5.5 L 20 11 C 20 16 16.5 19.5 12 21.5 C 7.5 19.5 4 16 4 11 L 4 5.5 Z"), **stroke)
        svg.path(d("M 8.5 12 L 11 14.5 L 15.5 9.5"), **stroke)
    elif kind == "storage":
        svg.path(d("M 3 7 L 3 19 C 3 19.6 3.4 20 4 20 L 20 20 C 20.6 20 21 19.6 21 19 "
                   "L 21 9 C 21 8.4 20.6 8 20 8 L 12 8 L 10 5 L 4 5 C 3.4 5 3 5.4 3 6 Z"), **stroke)
    elif kind == "cache":
        svg.polygon(p((13, 2), (4, 14), (11, 14), (10, 22), (20, 9), (13, 9)), **stroke)
    elif kind == "messaging":
        svg.rect(x + 2.5 * s, y + 5 * s, 19 * s, 14 * s, 2 * s, **stroke)
        svg.path(d("M 3 6.5 L 12 13 L 21 6.5"), **stroke)
    elif kind == "search":
        svg.circle(x + 10.5 * s, y + 10.5 * s, 6.5 * s, **stroke)
        svg.line(*p((15.5, 15.5))[0], *p((21, 21))[0], **stroke)
    elif kind == "deploy":
        svg.path(d("M 7 18 C 4 18 2.5 16 2.5 13.8 C 2.5 11.5 4.3 9.8 6.5 9.8 C 7.3 6.8 9.6 5 12.5 5 "
                   "C 16 5 18.6 7.6 18.8 11 C 20.6 11.3 21.8 12.8 21.8 14.6 C 21.8 16.5 20.3 18 18.4 18 Z"), **stroke)
    else:  # library, platform, external and anything unknown
        svg.path(d("M 12 2.5 L 21 7.2 L 21 16.8 L 12 21.5 L 3 16.8 L 3 7.2 Z"), **stroke)
        svg.path(d("M 3 7.2 L 12 12 L 21 7.2 M 12 12 L 12 21.5"), **stroke)


# Layers reuse accents that already read as their meaning.
LAYER_ACCENTS = {
    "entry": "web",
    "application": "api",
    "domain": "database",
    "data": "desktop",
    "integration": "neutral",
}

# Distinct colours for features, in the order they are assigned; hues that layers
# do not use come first.
FEATURE_PALETTE = {
    "light": ["#0969da", "#bc4c00", "#bf3989", "#1b7c83", "#cf222e", "#1a7f37", "#9a6700", "#8250df"],
    "dark": ["#4493f8", "#f0883e", "#db61a2", "#39c5cf", "#f85149", "#3fb950", "#d29922", "#ab7df8"],
}
