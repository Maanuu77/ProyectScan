"""Widgets that show the generated documents: diagrams and Markdown pages."""

import re

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QTextBlockFormat, QTextCursor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QScrollArea, QTextBrowser

_PICTURE = re.compile(r"<picture>.*?alt=\"([^\"]*)\".*?</picture>", re.S)
_DETAILS = re.compile(r"</?(details|summary)>")


class DiagramView(QScrollArea):
    """Shows an SVG fitted to the available width; taller diagrams scroll."""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._label)
        self._renderer: QSvgRenderer | None = None
        self._background = "#ffffff"

    def show_svg(self, svg: str, background: str) -> None:
        self._renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        self._background = background
        self._label.setStyleSheet(f"background: {background}; border: none;")
        self._redraw()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._redraw()

    def _redraw(self) -> None:
        if self._renderer is None or not self._renderer.isValid():
            return
        natural = self._renderer.defaultSize()
        width = min(self.viewport().width() - 24, natural.width() * 1.5)
        if width <= 0:
            return
        size = QSize(round(width), round(width * natural.height() / natural.width()))
        ratio = self.devicePixelRatioF()
        image = QImage(size * ratio, QImage.Format.Format_ARGB32)
        image.setDevicePixelRatio(ratio)
        image.fill(QColor(self._background))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # With a device pixel ratio set, the painter works in logical pixels.
        self._renderer.render(painter, QRectF(0, 0, size.width(), size.height()))
        painter.end()
        self._label.setPixmap(QPixmap.fromImage(image))


class PageView(QTextBrowser):
    """Shows a generated Markdown page; diagrams are mentioned by name, they have their own entries."""

    def __init__(self):
        super().__init__()
        self.setOpenLinks(False)
        self.document().setDocumentMargin(20)

    def show_markdown(self, markdown: str) -> None:
        text = _PICTURE.sub(lambda m: f"*Diagram: {m.group(1)}*", markdown)
        self.setMarkdown(_DETAILS.sub("", text))
        self._add_spacing()

    def _add_spacing(self) -> None:
        """Markdown import packs blocks tightly; give headings and paragraphs room to breathe."""
        cursor = QTextCursor(self.document())
        block = self.document().begin()
        while block.isValid():
            spacing = QTextBlockFormat(block.blockFormat())
            heading = block.blockFormat().headingLevel()
            spacing.setTopMargin(22 if heading in (1, 2) else 12 if heading else 0)
            spacing.setBottomMargin(8)
            spacing.setLineHeight(130, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            cursor.setPosition(block.position())
            cursor.setBlockFormat(spacing)
            block = block.next()
