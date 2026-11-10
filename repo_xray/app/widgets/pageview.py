"""The page view: a generated Markdown page with its diagrams drawn in place and links that navigate."""

import re
from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QTextBlockFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import QTextBrowser

from repo_xray.app.markdown_html import diagram_name, to_html
from repo_xray.app.theme import MD, Themes
from repo_xray.export.png import renderer_for

MAX_COLUMN = 860  # the widest a page's text runs; wider windows get margins instead of longer lines
MIN_MARGIN = 36
LINE_HEIGHT = 150

DiagramSource = Callable[[str], str | None]  # a diagram's name -> its SVG in the current theme


class PageView(QTextBrowser):
    link_clicked = Signal(str)  # the address as written in the page: `features/x.md`, `diagram:overview`, a URL

    def __init__(self, themes: Themes):
        super().__init__()
        self._themes = themes
        self._markdown = ""
        self._diagrams: DiagramSource | None = None
        self._images: dict[tuple, QImage] = {}
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setObjectName("canvas")
        self.anchorClicked.connect(lambda url: self.link_clicked.emit(url.toString()))
        self._relayout = QTimer(self)
        self._relayout.setSingleShot(True)
        self._relayout.setInterval(120)
        self._relayout.timeout.connect(self._render_keeping_position)
        self._rendered_width = 0
        self._generation = 0
        themes.changed.connect(self._theme_changed)

    def show_markdown(self, markdown: str, diagrams: DiagramSource | None = None, keep_position: bool = False) -> None:
        """Show a page. `diagrams` supplies the SVG of each diagram the page embeds."""
        self._markdown = markdown
        self._diagrams = diagrams
        self._images.clear()
        if keep_position:
            self._render_keeping_position()
        else:
            self._render()

    def markdown(self) -> str:
        return self._markdown

    # Rendering

    def _column(self) -> tuple[float, float]:
        """(margin on each side, width of the text column).

        Measured as if the scroll bar were always there: otherwise laying the page out makes the bar
        appear, which narrows the page, which lays it out again.
        """
        width = self.width() - self.verticalScrollBar().sizeHint().width()
        margin = max(MIN_MARGIN, (width - MAX_COLUMN) / 2)
        return margin, max(width - margin * 2, 120)

    def _render(self) -> None:
        palette = self._themes.palette
        document = self.document()
        font = QFont(self._themes.font or self.font().family())
        font.setPixelSize(MD)
        document.setDefaultFont(font)
        body = to_html(self._markdown, palette, self._themes.mono or "Consolas")
        # A different address every time: the document remembers images by address, and the same
        # diagram must be drawn again when the theme or the width changes.
        self._generation += 1
        body = re.sub(r'src="diagram:([^"#]+)"', rf'src="diagram:\1#{self._generation}"', body)
        self.setHtml(f'<div style="color: {palette.text};">{body}</div>')
        margin, _ = self._column()
        root = document.rootFrame()
        frame = root.frameFormat()
        frame.setLeftMargin(margin)
        frame.setRightMargin(margin)
        frame.setTopMargin(30)
        frame.setBottomMargin(56)
        root.setFrameFormat(frame)
        self._space_lines(document)
        self._rendered_width = self.width()

    @staticmethod
    def _space_lines(document: QTextDocument) -> None:
        """Give the lines of every paragraph room to breathe; rich text has no style for it."""
        cursor = QTextCursor(document)
        block = document.begin()
        while block.isValid():
            spacing = QTextBlockFormat(block.blockFormat())
            spacing.setLineHeight(LINE_HEIGHT, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            cursor.setPosition(block.position())
            cursor.setBlockFormat(spacing)
            block = block.next()

    def _render_keeping_position(self) -> None:
        bar = self.verticalScrollBar()
        fraction = bar.value() / bar.maximum() if bar.maximum() else 0
        self._render()
        bar.setValue(round(fraction * bar.maximum()))

    def loadResource(self, kind: int, url: QUrl):  # noqa: N802 - Qt's name
        name = diagram_name(url.toString().partition("#")[0])
        if name is None or kind != QTextDocument.ResourceType.ImageResource.value:
            return super().loadResource(kind, url)
        return self._diagram_image(name)

    def _diagram_image(self, name: str) -> QImage:
        """The diagram drawn as wide as the text column, never larger than its natural size."""
        _, column = self._column()
        ratio = self.devicePixelRatioF()
        key = (name, self._themes.palette.name, round(column), ratio)
        if key in self._images:
            return self._images[key]
        svg = self._diagrams(name) if self._diagrams is not None else None
        if svg is None:
            return QImage()
        try:
            renderer = renderer_for(svg)
        except ValueError:
            return QImage()
        natural = renderer.defaultSize()
        width = min(column, natural.width())
        height = width * natural.height() / max(natural.width(), 1)
        image = QImage(round(width * ratio), round(height * ratio), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(self._themes.palette.canvas))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        renderer.render(painter, QRectF(0, 0, image.width(), image.height()))
        painter.end()
        image.setDevicePixelRatio(ratio)
        self._images[key] = image
        return image

    # Events

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._markdown and abs(self.width() - self._rendered_width) > 2:
            self._relayout.start()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        over_link = bool(self.anchorAt(event.position().toPoint()))
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if over_link else Qt.CursorShape.IBeamCursor)

    def _theme_changed(self, *_) -> None:
        if self._markdown:
            self._images.clear()
            self._render_keeping_position()
