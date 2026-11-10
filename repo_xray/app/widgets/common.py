"""Small building blocks shared by every screen: labels, buttons, menus, a spinner.

They take their look from the style sheet (through the `role` and `variant`
properties) and their icons from the current palette, and they follow the
theme when it changes without the screens having to do anything.
"""

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy,
                               QToolButton, QWidget)

from repo_xray.app import icons
from repo_xray.app.theme import Themes

ICON_COLOURS = {"primary": "accent_on", "link": "accent_text"}  # by button variant; the rest use the text colour
ICON_GAP = 5  # between a button's icon and its text


def restyle(widget: QWidget) -> None:
    """Make the style sheet look at the widget again, after one of its properties changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_property(widget: QWidget, name: str, value) -> None:
    if widget.property(name) != value:
        widget.setProperty(name, value)
        restyle(widget)


def label(text: str = "", role: str | None = None, wrap: bool = False, selectable: bool = False) -> QLabel:
    widget = QLabel(text)
    if role:
        widget.setProperty("role", role)
    widget.setWordWrap(wrap)
    if selectable:
        widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return widget


def caps(text: str) -> QLabel:
    """A small heading in spaced capitals, for sections."""
    widget = label(text.upper(), "caps")
    font = widget.font()
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
    widget.setFont(font)
    return widget


def tag(text: str, tone: str | None = None) -> QLabel:
    """A small rounded label: a state, a count, a kind."""
    widget = label(text, "tag")
    if tone:
        widget.setProperty("tone", tone)
    widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
    return widget


def hairline(vertical: bool = False) -> QFrame:
    line = QFrame()
    line.setObjectName("hairline")
    if vertical:
        line.setFixedWidth(1)
    else:
        line.setFixedHeight(1)
    return line


class Button(QPushButton):
    """A push button with an optional icon that follows the theme."""

    def __init__(self, text: str, themes: Themes, icon: str | None = None, variant: str | None = None,
                 tooltip: str | None = None):
        super().__init__(text)
        self._themes = themes
        self._icon = icon
        self._variant = variant
        if variant:
            self.setProperty("variant", variant)
        if tooltip:
            self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        themes.changed.connect(self._refresh_icon)
        self._refresh_icon()

    def set_icon(self, name: str | None) -> None:
        self._icon = name
        self._refresh_icon()

    def setText(self, text: str) -> None:  # noqa: N802 - Qt's name
        super().setText(text)
        self._refresh_icon()  # the icon keeps a gap to its text only while there is a text

    def _refresh_icon(self, *_) -> None:
        if self._icon:
            palette = self._themes.palette
            colour = getattr(palette, ICON_COLOURS.get(self._variant, "text"))
            gap = ICON_GAP if self.text() else 0
            self.setIconSize(QSize(16 + gap, 16))
            self.setIcon(icons.icon(self._icon, colour, palette.text_subtle, gap=gap))


class IconButton(QToolButton):
    """A square button that shows only an icon; its tooltip says what it does."""

    def __init__(self, icon: str, themes: Themes, tooltip: str, variant: str = "ghost", checkable: bool = False,
                 size: int = 16, tone: str = "text_muted"):
        super().__init__()
        self._themes = themes
        self._icon = icon
        self._tone = tone
        self.setProperty("variant", variant)
        self.setProperty("shape", "icon")
        self.setToolTip(tooltip)
        self.setCheckable(checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(size, size))
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        themes.changed.connect(self._refresh_icon)
        self._refresh_icon()

    def set_icon(self, name: str) -> None:
        self._icon = name
        self._refresh_icon()

    @property
    def icon_name(self) -> str:
        return self._icon

    def _refresh_icon(self, *_) -> None:
        palette = self._themes.palette
        self.setIcon(icons.icon(self._icon, getattr(palette, self._tone), palette.text_subtle,
                                size=self.iconSize().width()))


class Segmented(QWidget):
    """A row of choices of which exactly one is on, like tabs."""

    selected = Signal(str)

    def __init__(self, choices: list[tuple[str, str, str]]):
        """`choices` are (key, text, tooltip)."""
        super().__init__()
        self.setObjectName("segmented")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._buttons: dict[str, QToolButton] = {}
        for key, text, tooltip in choices:
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tooltip)
            button.setCheckable(True)
            button.setProperty("variant", "segment")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _=False, k=key: self.selected.emit(k))
            self._group.addButton(button)
            self._buttons[key] = button
            layout.addWidget(button)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def select(self, key: str | None) -> None:
        """Show `key` as chosen without announcing it; None leaves nothing chosen."""
        self._group.setExclusive(False)
        for name, button in self._buttons.items():
            button.setChecked(name == key)
        self._group.setExclusive(True)

    def current(self) -> str | None:
        return next((key for key, button in self._buttons.items() if button.isChecked()), None)

    def button(self, key: str) -> QToolButton:
        return self._buttons[key]


class ElidedLabel(QLabel):
    """A one-line label that shortens its text with an ellipsis instead of pushing the layout wider."""

    def __init__(self, text: str = "", role: str | None = None, mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight):
        super().__init__()
        self._full = text
        self._mode = mode
        if role:
            self.setProperty("role", role)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(24)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt's name
        self._full = text
        self.setToolTip(text)
        self._elide()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        shown = QFontMetrics(self.font()).elidedText(self._full, self._mode, max(self.width() - 2, 0))
        super().setText(shown)

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetrics(self.font())
        return QSize(metrics.horizontalAdvance(self._full) + 4, metrics.height() + 2)


class Spinner(QWidget):
    """A turning arc: something is running and cannot say how far it is."""

    def __init__(self, themes: Themes, size: int = 16, tone: str = "accent_text"):
        super().__init__()
        self._themes = themes
        self._tone = tone
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._turn)

    def showEvent(self, event) -> None:  # noqa: N802
        self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()

    def _turn(self) -> None:
        self._angle = (self._angle + 24) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = 2.0
        box = QRectF(inset, inset, self.width() - inset * 2, self.height() - inset * 2)
        track = self._themes.colour("active")
        painter.setPen(QPen(track, 2))
        painter.drawEllipse(box)
        pen = QPen(self._themes.colour(self._tone), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(box, -self._angle * 16, 100 * 16)


class Dot(QWidget):
    """A small filled circle in a palette colour: a state, a mark."""

    def __init__(self, themes: Themes, tone: str = "text_subtle", size: int = 8):
        super().__init__()
        self._themes = themes
        self.tone = tone
        self.setFixedSize(size, size)
        themes.changed.connect(self._repaint)

    def _repaint(self, *_) -> None:
        self.update()

    def set_tone(self, tone: str) -> None:
        self.tone = tone
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._themes.colour(self.tone))
        painter.drawEllipse(QPointF(self.width() / 2, self.height() / 2), self.width() / 2, self.height() / 2)


class IconLabel(QWidget):
    """An icon drawn in a palette colour, for places that are not buttons."""

    def __init__(self, icon: str, themes: Themes, size: int = 16, tone: str = "text_muted"):
        super().__init__()
        self._themes = themes
        self._icon = icon
        self._tone = tone
        self._size = size
        self.setFixedSize(size, size)
        themes.changed.connect(self._repaint)

    def _repaint(self, *_) -> None:
        self.update()

    def set_icon(self, icon: str, tone: str | None = None) -> None:
        self._icon = icon
        self._tone = tone or self._tone
        self.update()

    @property
    def icon_name(self) -> str:
        return self._icon

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        icons.paint(painter, self._icon, self._themes.colour(self._tone), 0, 0, self._size)


class IconTile(QWidget):
    """An icon on a tinted rounded square, like the tiles of the diagrams."""

    def __init__(self, icon: str, themes: Themes, size: int = 36, tone: str = "accent_text", fill: str = "accent_soft"):
        super().__init__()
        self._themes = themes
        self._icon, self._tone, self._fill = icon, tone, fill
        self.setFixedSize(size, size)
        themes.changed.connect(self._repaint)

    def _repaint(self, *_) -> None:
        self.update()

    def set_icon(self, icon: str, tone: str, fill: str) -> None:
        self._icon, self._tone, self._fill = icon, tone, fill
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._themes.colour(self._fill))
        side = self.width()
        painter.drawRoundedRect(QRectF(0, 0, side, side), side * 0.26, side * 0.26)
        glyph = round(side * 0.5)
        icons.paint(painter, self._icon, self._themes.colour(self._tone), (side - glyph) / 2, (side - glyph) / 2, glyph)


def menu(parent: QWidget) -> QMenu:
    """A menu with rounded corners; without the translucent window its corners would show the old square."""
    result = QMenu(parent)
    result.setWindowFlags(result.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
    result.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    return result


def blend(colour: QColor, onto: QColor, amount: float) -> QColor:
    """`colour` mixed over `onto`: 0 gives `onto`, 1 gives `colour`."""
    return QColor(
        round(onto.red() + (colour.red() - onto.red()) * amount),
        round(onto.green() + (colour.green() - onto.green()) * amount),
        round(onto.blue() + (colour.blue() - onto.blue()) * amount),
    )
