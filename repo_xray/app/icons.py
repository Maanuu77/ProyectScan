"""The app's icons: one family of outline icons, drawn on a 24-unit grid.

Each icon is a few SVG shapes stroked in whatever colour is asked for, so
the same icon serves light and dark and every state of a control. They are
rendered by Qt at the screen's pixel density and remembered.
"""

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

STROKE = 1.75

# Shapes on a 24x24 grid. A string is a path; ("c", cx, cy, r) a circle;
# ("r", x, y, w, h, rx) a rounded rectangle; ("d", cx, cy, r) a filled dot.
ICONS: dict[str, tuple] = {
    "folder": ("M3 7.5a2 2 0 0 1 2-2h4.2l2 2.5H19a2 2 0 0 1 2 2V17.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z",),
    "folder-open": ("M3 9V7.5a2 2 0 0 1 2-2h4.2l2 2.5H18a2 2 0 0 1 2 2V11",
                    "M4.6 19.5h13.2a2 2 0 0 0 1.9-1.4l1.6-5.2a1.4 1.4 0 0 0-1.3-1.9H7.2a2 2 0 0 0-1.9 1.4L3 19.5"),
    "layers": ("M12 3.5 3.5 8l8.5 4.5L20.5 8 12 3.5Z", "M3.5 12l8.5 4.5 8.5-4.5", "M3.5 16l8.5 4.5 8.5-4.5"),
    "grid": (("r", 3.5, 3.5, 7, 7, 1.6), ("r", 13.5, 3.5, 7, 7, 1.6), ("r", 3.5, 13.5, 7, 7, 1.6),
             ("r", 13.5, 13.5, 7, 7, 1.6)),
    "flow": (("r", 3, 3.5, 8, 5.5, 1.6), ("r", 13, 15, 8, 5.5, 1.6), "M11 6.2h4.5a2 2 0 0 1 2 2V15", "M15 12.6l2.5 2.4 2.5-2.4"),
    "page": ("M6.5 3h7.5l4.5 4.5V19a2 2 0 0 1-2 2h-10a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z", "M14 3v4.5h4.5", "M8.5 12.5h7",
             "M8.5 16.5h5"),
    "report": ("M4 4v14a2 2 0 0 0 2 2h14", "M8.5 16v-4", "M12.5 16V8", "M16.5 16v-6"),
    "search": (("c", 10.8, 10.8, 6.3), "M15.5 15.5 20.5 20.5"),
    "sun": (("c", 12, 12, 4), "M12 2.5v2.2", "M12 19.3v2.2", "M2.5 12h2.2", "M19.3 12h2.2", "M5.3 5.3l1.5 1.5",
            "M17.2 17.2l1.5 1.5", "M5.3 18.7l1.5-1.5", "M17.2 6.8l1.5-1.5"),
    "moon": ("M20 14.2A8.3 8.3 0 1 1 9.8 4a6.6 6.6 0 0 0 10.2 10.2Z",),
    "monitor": (("r", 3, 4, 18, 12.5, 2), "M8.5 20.5h7", "M12 16.5v4"),
    "export": ("M12 3.5v11", "M7.5 10.2l4.5 4.5 4.5-4.5", "M4.5 19.8h15"),
    "pencil": ("M4 20l1-4.2L16.3 4.5a2.2 2.2 0 0 1 3.2 3.2L8.2 19 4 20Z", "M14.4 6.4l3.2 3.2"),
    "plus": ("M12 5v14", "M5 12h14"),
    "minus": ("M5 12h14",),
    "fit": ("M4 9V5.5A1.5 1.5 0 0 1 5.5 4H9", "M15 4h3.5A1.5 1.5 0 0 1 20 5.5V9", "M20 15v3.5a1.5 1.5 0 0 1-1.5 1.5H15",
            "M9 20H5.5A1.5 1.5 0 0 1 4 18.5V15"),
    "expand": ("M14 4h6v6", "M20 4l-6.5 6.5", "M10 20H4v-6", "M4 20l6.5-6.5"),
    "collapse": ("M20 9.5h-5.5V4", "M14.5 9.5 20.5 3.5", "M4 14.5h5.5V20", "M9.5 14.5 3.5 20.5"),
    "close": ("M6.5 6.5l11 11", "M17.5 6.5l-11 11"),
    "check": ("M5 12.6l4.4 4.4L19 7.4",),
    "chevron-right": ("M9.5 6l6 6-6 6",),
    "chevron-down": ("M6 9.5l6 6 6-6",),
    "chevron-up": ("M6 14.5l6-6 6 6",),
    "arrow-left": ("M19.5 12h-15", "M10.5 6l-6 6 6 6"),
    "warning": ("M12 4 2.8 19.6h18.4L12 4Z", "M12 10v4.6", "M12 17.2v.3"),
    "info": (("c", 12, 12, 9), "M12 11v5.6", "M12 7.6v.3"),
    "error": (("c", 12, 12, 9), "M9 9l6 6", "M15 9l-6 6"),
    "success": (("c", 12, 12, 9), "M8 12.4l2.8 2.8L16 9.6"),
    "refresh": ("M20 12a8 8 0 1 1-2.4-5.7", "M20.2 4v5h-5"),
    "globe": (("c", 12, 12, 9), "M3 12h18", "M12 3c3 3.2 3 14.8 0 18", "M12 3c-3 3.2-3 14.8 0 18"),
    "clock": (("c", 12, 12, 9), "M12 7.2v5.2l3.4 2"),
    "trash": ("M4.5 7h15", "M9.5 7V4.5h5V7", "M6.5 7l.9 12.5h9.2L17.5 7"),
    "sidebar": (("r", 3, 4, 18, 16, 2.2), "M9.2 4v16"),
    "external": ("M13.5 4.5h6v6", "M19.5 4.5 11 13", "M17.5 14v4a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 18V8A1.5 1.5 0 0 1 6 6.5h4"),
    "copy": (("r", 8.5, 8.5, 12, 12, 2), "M15.5 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.5a2 2 0 0 0 2 2h2.5"),
    "image": (("r", 3, 4, 18, 16, 2.2), ("c", 8.8, 9.6, 1.7), "M21 15.5l-4.8-4.8L7.5 20"),
    "stop": (("r", 6.5, 6.5, 11, 11, 2),),
    "star": ("M12 3.6l2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8Z",),
    "archive": (("r", 3, 4, 18, 5, 1.4), "M5 9v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9", "M10 13.2h4"),
    "code": ("M8.5 7.5 4 12l4.5 4.5", "M15.5 7.5 20 12l-4.5 4.5"),
    "dot": (("d", 12, 12, 3.2),),
    "ring": (("c", 12, 12, 3.4),),
    "more": (("d", 5.5, 12, 1.4), ("d", 12, 12, 1.4), ("d", 18.5, 12, 1.4)),
    "users": (("c", 12, 8, 4), "M4 21c0-5 4-7 8-7s8 2 8 7"),
    "command": ("M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3Z",),
}


def svg(name: str, colour: str, stroke: float = STROKE) -> str:
    """The icon as an SVG document stroked in `colour`."""
    shapes = []
    for shape in ICONS[name]:
        if isinstance(shape, str):
            shapes.append(f'<path d="{shape}"/>')
        elif shape[0] == "c":
            shapes.append(f'<circle cx="{shape[1]}" cy="{shape[2]}" r="{shape[3]}"/>')
        elif shape[0] == "d":
            shapes.append(f'<circle cx="{shape[1]}" cy="{shape[2]}" r="{shape[3]}" fill="{colour}" stroke="none"/>')
        else:
            _, x, y, width, height, radius = shape
            shapes.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
            f'stroke="{colour}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
            + "".join(shapes) + "</svg>")


@lru_cache(maxsize=512)
def pixmap(name: str, colour: str, size: int = 16, ratio: float = 1.0) -> QPixmap:
    """The icon as a pixmap of `size` logical pixels, sharp at the given device pixel ratio."""
    renderer = QSvgRenderer(QByteArray(svg(name, colour).encode("utf-8")))
    image = QImage(QSize(round(size * ratio), round(size * ratio)), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, image.width(), image.height()))
    painter.end()
    result = QPixmap.fromImage(image)
    result.setDevicePixelRatio(ratio)
    return result


def icon(name: str, colour: str, disabled: str | None = None, size: int = 16, ratio: float = 2.0) -> QIcon:
    """A QIcon in `colour`, with `disabled` for controls that are switched off."""
    result = QIcon()
    result.addPixmap(pixmap(name, colour, size, ratio), QIcon.Mode.Normal)
    result.addPixmap(pixmap(name, disabled or colour, size, ratio), QIcon.Mode.Disabled)
    return result


def paint(painter: QPainter, name: str, colour: QColor | str, x: float, y: float, size: int = 16) -> None:
    """Draw the icon with its top-left corner at (x, y), for widgets that paint themselves."""
    ratio = painter.device().devicePixelRatioF() if painter.device() is not None else 1.0
    colour = colour.name() if isinstance(colour, QColor) else colour
    painter.drawPixmap(QRectF(x, y, size, size), pixmap(name, colour, size, ratio), QRectF(0, 0, size * ratio, size * ratio))
