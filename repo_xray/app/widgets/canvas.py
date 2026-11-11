"""The diagram canvas: zoom, pan, fit, find and click-through over one SVG.

The diagram is drawn by Qt's SVG renderer at whatever scale is asked, so it
stays sharp at any zoom. Two things are read from the SVG's own text: its
`<text>` elements, to find words in the diagram, and the ids of its cards
(see `render/ids.py`), which make them clickable.
"""

import xml.etree.ElementTree as ElementTree
from collections.abc import Iterable

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QKeyEvent, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from repo_xray.app.theme import Themes
from repo_xray.export.png import installed_family, renderer_for
from repo_xray.render.svg import FONT_FAMILY, MONO_FAMILY

FIT_WIDTH, FIT_ALL = "width", "all"
MIN_SCALE, MAX_SCALE = 0.1, 8.0
MAX_FIT = 1.25  # fitting never blows a small diagram up past this
STEPS = (0.1, 0.25, 0.33, 0.5, 0.67, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0)
CACHE_PIXELS = 20_000_000  # above this the diagram is drawn straight to the screen instead of to a pixmap
DRAG_THRESHOLD = 4
SVG = "{http://www.w3.org/2000/svg}"


class DiagramCanvas(QWidget):
    zoom_changed = Signal(float)  # the new scale; 1.0 is 100 %
    element_clicked = Signal(str)  # id of the card that was clicked
    matches_changed = Signal(int, int)  # (which match is current, from 1; how many there are)

    def __init__(self, themes: Themes):
        super().__init__()
        self._themes = themes
        self._renderer: QSvgRenderer | None = None
        self._size = QSizeF()
        self._background = QColor(themes.palette.canvas)
        self._scale = 1.0
        self._origin = QPointF()  # where the diagram's top-left corner is, in widget coordinates
        self._fit: str | None = FIT_WIDTH
        self._cache: QPixmap | None = None
        self._texts: list[tuple[str, QRectF, QFont]] = []
        self._regions: list[tuple[str, QRectF]] = []
        self._clickable: set[str] | None = None
        self._hover: str | None = None
        self._matches: list[QRectF] = []
        self._current = -1
        self._query = ""
        self._press: QPointF | None = None
        self._press_origin = QPointF()
        self._dragging = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(200, 160)
        themes.changed.connect(self._theme_changed)

    # What is shown

    def show_svg(self, svg: str, background: str, keep_view: bool = False) -> None:
        """Show a diagram. `keep_view` keeps zoom and position, for the same diagram drawn again."""
        self._renderer = renderer_for(svg)
        self._size = QSizeF(self._renderer.defaultSize())
        self._background = QColor(background)
        self._cache = None
        self._texts = _text_boxes(svg)
        ids = _ids(svg)
        self._regions = [(i, self._renderer.boundsOnElement(i)) for i in ids if self._renderer.elementExists(i)]
        self._hover = None
        if keep_view:
            self._clamp()
        else:
            self._fit = FIT_WIDTH
            self._apply_fit()
        if self._query:
            self.find(self._query)
        self.update()
        self.zoom_changed.emit(self._scale)

    def clear(self) -> None:
        self._renderer, self._cache, self._texts, self._regions, self._matches = None, None, [], [], []
        self.update()

    def has_diagram(self) -> bool:
        return self._renderer is not None

    def element_ids(self) -> list[str]:
        """The ids of the named parts of the diagram on show."""
        return [element_id for element_id, _ in self._regions]

    def set_clickable(self, ids: Iterable[str] | None) -> None:
        """Which named parts react to the pointer; None means every part that has an id."""
        self._clickable = set(ids) if ids is not None else None

    # Zoom and position

    @property
    def scale(self) -> float:
        return self._scale

    @property
    def fit_mode(self) -> str | None:
        return self._fit

    def content_rect(self) -> QRectF:
        """Where the diagram is drawn, in widget coordinates."""
        return QRectF(self._origin, self._size * self._scale)

    def zoom_to(self, scale: float, anchor: QPointF | None = None) -> None:
        """Set the scale, keeping the point of the diagram under `anchor` (the centre by default) where it is."""
        if self._renderer is None:
            return
        scale = min(max(scale, MIN_SCALE), MAX_SCALE)
        anchor = anchor if anchor is not None else QPointF(self.width() / 2, self.height() / 2)
        point = (anchor - self._origin) / self._scale
        self._set_scale(scale)
        self._origin = anchor - point * scale
        self._fit = None
        self._clamp()
        self.update()

    def zoom_in(self) -> None:
        self.zoom_to(next((step for step in STEPS if step > self._scale * 1.01), MAX_SCALE))

    def zoom_out(self) -> None:
        self.zoom_to(next((step for step in reversed(STEPS) if step < self._scale * 0.99), MIN_SCALE))

    def actual_size(self) -> None:
        self.zoom_to(1.0)

    def fit(self, mode: str = FIT_WIDTH) -> None:
        """Fit the diagram's width (reading size, scrolls down) or the whole diagram (overview)."""
        self._fit = mode
        self._apply_fit()
        self.update()

    def toggle_fit(self) -> None:
        self.fit(FIT_ALL if self._fit == FIT_WIDTH else FIT_WIDTH)

    def pan(self, dx: float, dy: float) -> None:
        self._origin += QPointF(dx, dy)
        self._clamp()
        self.update()

    def _set_scale(self, scale: float) -> None:
        if abs(scale - self._scale) > 1e-6:
            self._scale = scale
            self._cache = None
            self.zoom_changed.emit(scale)

    def _apply_fit(self) -> None:
        if self._renderer is None or self._size.isEmpty() or self.width() <= 0:
            return
        across = self.width() / self._size.width()
        down = self.height() / self._size.height()
        self._set_scale(max(min(across if self._fit == FIT_WIDTH else min(across, down), MAX_FIT), MIN_SCALE))
        self._origin = QPointF(0, 0)
        self._clamp()

    def _clamp(self) -> None:
        """Keep the diagram in view: edge to edge when it is larger than the canvas; when smaller, centred
        across and, like a page, starting at the top (only "fit all" centres it down the canvas too)."""
        width, height = self._size.width() * self._scale, self._size.height() * self._scale
        x = (self.width() - width) / 2 if width <= self.width() else min(max(self._origin.x(), self.width() - width), 0)
        if height > self.height():
            y = min(max(self._origin.y(), self.height() - height), 0)
        else:
            y = (self.height() - height) / 2 if self._fit == FIT_ALL else 0
        self._origin = QPointF(x, y)

    # Find

    def find(self, text: str) -> int:
        """Mark every label that contains `text`. Returns how many there are."""
        self._query = text
        self._matches = []
        needle = text.casefold().strip()
        if needle:
            for content, box, font in self._texts:
                start = content.casefold().find(needle)
                if start >= 0:
                    metrics = QFontMetricsF(font)
                    before = metrics.horizontalAdvance(content[:start])
                    width = metrics.horizontalAdvance(content[start:start + len(needle)])
                    self._matches.append(QRectF(box.left() + before - 2, box.top(), width + 4, box.height()))
        self._matches.sort(key=lambda r: (r.top(), r.left()))
        self._current = 0 if self._matches else -1
        self._reveal_current()
        self.update()
        self.matches_changed.emit(self._current + 1, len(self._matches))
        return len(self._matches)

    def find_next(self, step: int = 1) -> None:
        if not self._matches:
            return
        self._current = (self._current + step) % len(self._matches)
        self._reveal_current()
        self.update()
        self.matches_changed.emit(self._current + 1, len(self._matches))

    def clear_find(self) -> None:
        self.find("")

    def match_count(self) -> int:
        return len(self._matches)

    def _reveal_current(self) -> None:
        """Scroll so the current match is in view, with some room around it."""
        if self._current < 0:
            return
        box = self._to_widget(self._matches[self._current])
        margin = 48

        def shift(start: float, end: float, size: float) -> float:
            """How far to move along one axis; a match longer than the view shows where it starts."""
            if start < margin or end - start > size - margin * 2:
                return margin - start
            return size - margin - end if end > size - margin else 0.0

        dx, dy = shift(box.left(), box.right(), self.width()), shift(box.top(), box.bottom(), self.height())
        if dx or dy:
            self._origin += QPointF(dx, dy)
            self._clamp()

    # Painting

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._background)
        if self._renderer is None:
            return
        target = self.content_rect()
        ratio = self.devicePixelRatioF()
        pixels = target.width() * target.height() * ratio * ratio
        if pixels <= CACHE_PIXELS:
            if self._cache is None:
                self._cache = self._render_cache(target.size(), ratio)
            painter.drawPixmap(target.topLeft(), self._cache)
        else:  # too large to keep as a picture: draw what is visible, straight from the SVG
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setClipRect(self.rect())
            self._renderer.render(painter, target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_matches(painter)
        self._paint_hover(painter)

    def _render_cache(self, size: QSizeF, ratio: float) -> QPixmap:
        image = QImage(max(round(size.width() * ratio), 1), max(round(size.height() * ratio), 1),
                       QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(self._background)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self._renderer.render(painter, QRectF(0, 0, image.width(), image.height()))
        painter.end()
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(ratio)
        return pixmap

    def _paint_matches(self, painter: QPainter) -> None:
        if not self._matches:
            return
        palette = self._themes.palette
        other, current = QColor(palette.warning), QColor(palette.accent)
        other.setAlphaF(0.28)
        current.setAlphaF(0.38)
        for index, match in enumerate(self._matches):
            box = self._to_widget(match)
            painter.setPen(QPen(QColor(palette.accent), 1.5) if index == self._current else Qt.PenStyle.NoPen)
            painter.setBrush(current if index == self._current else other)
            painter.drawRoundedRect(box, 3, 3)

    def _paint_hover(self, painter: QPainter) -> None:
        box = next((b for i, b in self._regions if i == self._hover), None)
        if box is None:
            return
        painter.setPen(QPen(QColor(self._themes.palette.accent), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        radius = 12 * self._scale
        painter.drawRoundedRect(self._to_widget(box), radius, radius)

    def _to_widget(self, box: QRectF) -> QRectF:
        return QRectF(self._origin.x() + box.x() * self._scale, self._origin.y() + box.y() * self._scale,
                      box.width() * self._scale, box.height() * self._scale)

    def _theme_changed(self, *_) -> None:
        self.update()

    # Pointer and keyboard

    def element_at(self, position: QPointF) -> str | None:
        """The clickable part under a point of the widget; the smallest one when parts overlap."""
        point = (position - self._origin) / self._scale
        hits = [(box.width() * box.height(), i) for i, box in self._regions
                if box.contains(point) and (self._clickable is None or i in self._clickable)]
        return min(hits)[1] if hits else None

    def resizeEvent(self, event) -> None:  # noqa: N802
        if self._fit is not None:
            self._apply_fit()
        else:
            self._clamp()

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self._renderer is None:
            return
        delta = event.angleDelta()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_to(self._scale * (1.0015 ** delta.y()), event.position())
        else:
            pixels = event.pixelDelta()
            dx, dy = (pixels.x(), pixels.y()) if not pixels.isNull() else (delta.x() * 0.6, delta.y() * 0.6)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                dx, dy = dy, dx
            self.pan(dx, dy)
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton) and self._renderer is not None:
            self._press = event.position()
            self._press_origin = QPointF(self._origin)
            self._dragging = False
            self.setFocus()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._press is not None:
            delta = event.position() - self._press
            if not self._dragging and delta.manhattanLength() >= DRAG_THRESHOLD:
                self._dragging = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if self._dragging:
                self._origin = self._press_origin + delta
                self._clamp()
                self.update()
            return
        hover = self.element_at(event.position()) if self._renderer is not None else None
        if hover != self._hover:
            self._hover = hover
            self.setCursor(Qt.CursorShape.PointingHandCursor if hover else Qt.CursorShape.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._press is None:
            return
        clicked = None if self._dragging else self.element_at(event.position())
        self._press, self._dragging = None, False
        self.setCursor(Qt.CursorShape.PointingHandCursor if self._hover else Qt.CursorShape.ArrowCursor)
        if clicked and event.button() == Qt.MouseButton.LeftButton:
            self.element_clicked.emit(clicked)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self._renderer is None or self.element_at(event.position()):
            return
        if self._fit is None:
            self.fit(FIT_WIDTH)
        else:
            self.zoom_to(1.0 if abs(self._scale - 1.0) > 0.01 else 2.0, event.position())

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hover is not None:
            self._hover = None
            self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key, step = event.key(), 80
        page = self.height() * 0.85
        actions = {
            Qt.Key.Key_Plus: self.zoom_in, Qt.Key.Key_Equal: self.zoom_in, Qt.Key.Key_Minus: self.zoom_out,
            Qt.Key.Key_0: lambda: self.fit(FIT_WIDTH), Qt.Key.Key_1: self.actual_size,
            Qt.Key.Key_Left: lambda: self.pan(step, 0), Qt.Key.Key_Right: lambda: self.pan(-step, 0),
            Qt.Key.Key_Up: lambda: self.pan(0, step), Qt.Key.Key_Down: lambda: self.pan(0, -step),
            Qt.Key.Key_PageUp: lambda: self.pan(0, page), Qt.Key.Key_PageDown: lambda: self.pan(0, -page),
            Qt.Key.Key_Space: lambda: self.pan(0, page if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else -page),
            Qt.Key.Key_Home: lambda: self.pan(0, 1e9), Qt.Key.Key_End: lambda: self.pan(0, -1e9),
        }
        if key in actions and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            actions[key]()
        else:
            super().keyPressEvent(event)


def _ids(svg: str) -> list[str]:
    try:
        return [element.attrib["id"] for element in ElementTree.fromstring(svg).iter() if "id" in element.attrib]
    except ElementTree.ParseError:
        return []


def _text_boxes(svg: str) -> list[tuple[str, QRectF, QFont]]:
    """Every label of the diagram with the box it is drawn in and its font, in diagram coordinates."""
    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError:
        return []
    boxes = []
    for element in root.iter(f"{SVG}text"):
        content = element.text or ""
        if not content.strip():
            continue
        try:
            x, y, size = float(element.attrib["x"]), float(element.attrib["y"]), float(element.attrib["font-size"])
        except (KeyError, ValueError):
            continue
        font = QFont(installed_family(MONO_FAMILY if "font-family" in element.attrib else FONT_FAMILY))
        font.setPixelSize(max(round(size), 1))
        font.setWeight(QFont.Weight(int(element.attrib.get("font-weight", 400))))
        width = QFontMetricsF(font).horizontalAdvance(content)
        anchor = element.attrib.get("text-anchor", "start")
        left = x - width if anchor == "end" else x - width / 2 if anchor == "middle" else x
        boxes.append((content, QRectF(left, y - size * 0.92, width, size * 1.3), font))
    return boxes
