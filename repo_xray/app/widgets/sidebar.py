"""The sidebar: which project is open, a filter, and every document grouped by level."""

from pathlib import Path

from PySide6.QtCore import QEvent, QModelIndex, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                               QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

from repo_xray.app import icons
from repo_xray.app.navigation import ENTRY, GROUP, NOTE, SECTION, NavItem, Navigation, Target
from repo_xray.app.theme import SM, XS, Themes
from repo_xray.app.widgets.common import ElidedLabel, IconLabel, IconTile, label
from repo_xray.render import theme as diagrams

ITEM = Qt.ItemDataRole.UserRole
HEIGHTS = {SECTION: 36, GROUP: 26, ENTRY: 30, NOTE: 30}
WIDTH, MIN_WIDTH, MAX_WIDTH = 272, 220, 420


class ProjectHeader(QFrame):
    """The open project: its name and folder. A click opens the project menu."""

    clicked = Signal()

    def __init__(self, themes: Themes):
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Project menu: open another folder, analyse again…")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 10, 12)
        layout.setSpacing(10)
        layout.addWidget(IconTile("folder", themes, 32))
        texts = QVBoxLayout()
        texts.setSpacing(0)
        self.name = ElidedLabel("", "heading")
        self.path = ElidedLabel("", "subtle", Qt.TextElideMode.ElideMiddle)
        texts.addWidget(self.name)
        texts.addWidget(self.path)
        layout.addLayout(texts, 1)
        layout.addWidget(IconLabel("chevron-down", themes, 14, "text_subtle"))

    def set_project(self, name: str, path: Path) -> None:
        self.name.setText(name)
        self.path.setText(str(path))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()


class NavDelegate(QStyledItemDelegate):
    """Paints the rows of the navigation: section titles, group titles, entries with their icon and badge."""

    def __init__(self, themes: Themes, parent=None):
        super().__init__(parent)
        self._themes = themes

    def sizeHint(self, option, index: QModelIndex) -> QSize:  # noqa: N802
        item: NavItem = index.data(ITEM)
        return QSize(100, HEIGHTS.get(item.kind, 30) if item else 30)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        item: NavItem = index.data(ITEM)
        if item is None:
            return
        p = self._themes.palette
        rect = QRectF(option.rect)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(option.font)
        if item.kind == SECTION:
            font.setPixelSize(XS)
            font.setWeight(QFont.Weight.Bold)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
            painter.setFont(font)
            painter.setPen(QColor(p.text_subtle))
            text_rect = rect.adjusted(18, 12, -14, 0)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, item.title.upper())
            if item.badge:
                font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0)
                font.setWeight(QFont.Weight.DemiBold)
                painter.setFont(font)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, item.badge)
        elif item.kind == GROUP:
            font.setPixelSize(SM)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(p.text_muted))
            metrics = QFontMetricsF(font)
            text = metrics.elidedText(item.title, Qt.TextElideMode.ElideRight, rect.width() - 34)
            painter.drawText(rect.adjusted(20, 4, -14, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        elif item.kind == NOTE:
            font.setPixelSize(SM)
            font.setItalic(True)
            painter.setFont(font)
            painter.setPen(QColor(p.text_subtle))
            painter.drawText(rect.adjusted(20, 0, -14, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, item.title)
        else:
            self._paint_entry(painter, option, rect, item, font)
        painter.restore()

    def _paint_entry(self, painter: QPainter, option, rect: QRectF, item: NavItem, font: QFont) -> None:
        p = self._themes.palette
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        row = rect.adjusted(8, 1, -8, -1)
        if selected or hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(p.accent_soft if selected else p.hover))
            painter.drawRoundedRect(row, 6, 6)
        colour = QColor(p.accent_text if selected else p.text_muted)
        icons.paint(painter, item.icon or "dot", colour, row.left() + 10, row.center().y() - 8, 16)

        badge_width = 0.0
        if item.badge:
            badge_width = self._paint_badge(painter, row, item, font)
        font.setWeight(QFont.Weight.DemiBold if selected else QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(p.text if selected or hovered else p.text))
        room = row.width() - 36 - 10 - (badge_width + 8 if badge_width else 0)
        text = QFontMetricsF(font).elidedText(item.title, Qt.TextElideMode.ElideRight, room)
        painter.drawText(QRectF(row.left() + 36, row.top(), room, row.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)

    def _paint_badge(self, painter: QPainter, row: QRectF, item: NavItem, font: QFont) -> float:
        """A flow's HTTP method in its diagram colour, or a count. Returns the badge's width."""
        p = self._themes.palette
        badge_font = QFont(font)
        badge_font.setPixelSize(10)
        badge_font.setWeight(QFont.Weight.Bold)
        width = QFontMetricsF(badge_font).horizontalAdvance(item.badge) + 12
        box = QRectF(row.right() - width - 8, row.center().y() - 8, width, 16)
        if item.badge_tone == "method":
            accent = p.diagram.accent(diagrams.METHOD_ACCENTS.get(item.badge, "neutral"))
            fill, text = QColor(accent.soft), QColor(accent.strong)
        elif item.badge_tone == "warning":
            fill, text = QColor(p.warning_soft), QColor(p.warning)
        else:
            fill, text = QColor(p.active), QColor(p.text_muted)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(box, 5, 5)
        painter.setFont(badge_font)
        painter.setPen(text)
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, item.badge)
        return width


class NavList(QListWidget):
    """The list of documents. Headings cannot be selected; arrows move between entries."""

    def __init__(self, themes: Themes):
        super().__init__()
        self.setItemDelegate(NavDelegate(themes, self))
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setUniformItemSizes(False)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover)
        themes.changed.connect(self._repaint)

    def _repaint(self, *_) -> None:
        self.viewport().update()

    def viewportEvent(self, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.ToolTip:
            item = self.itemAt(event.pos())
            nav: NavItem | None = item.data(ITEM) if item else None
            self.setToolTip(nav.hint if nav and nav.hint else "")
        return super().viewportEvent(event)


class Sidebar(QWidget):
    target_selected = Signal(object)  # the Target the reader chose
    project_menu_requested = Signal()
    filter_changed = Signal(str)

    def __init__(self, themes: Themes):
        super().__init__()
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setMinimumWidth(MIN_WIDTH)
        self._navigation = Navigation()
        self._shown = Navigation()
        self._current: Target | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = ProjectHeader(themes)
        self.header.clicked.connect(self.project_menu_requested)
        layout.addWidget(self.header)

        search = QHBoxLayout()
        search.setContentsMargins(12, 0, 12, 4)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter features and flows")
        self.filter.setProperty("variant", "quiet")
        self.filter.setClearButtonEnabled(True)
        self.filter.setToolTip("Type to filter the list  (Ctrl+K)")
        self._search_icon = self.filter.addAction(icons.icon("search", themes.palette.text_subtle),
                                                  QLineEdit.ActionPosition.LeadingPosition)
        self.filter.textChanged.connect(self._filter)
        search.addWidget(self.filter)
        layout.addLayout(search)

        self.list = NavList(themes)
        self.list.currentItemChanged.connect(self._current_changed)
        layout.addWidget(self.list, 1)

        self.empty = label("Nothing matches the filter.", "subtle")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.empty.setContentsMargins(16, 24, 16, 24)
        self.empty.hide()
        layout.addWidget(self.empty)
        self._themes = themes
        themes.changed.connect(self._theme_changed)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(WIDTH, 600)

    # Content

    def set_project(self, name: str, path: Path) -> None:
        self.header.set_project(name, path)

    def set_navigation(self, navigation: Navigation, current: Target | None = None) -> None:
        """List the documents of an analysis and show `current` as selected (without announcing it)."""
        self._navigation = navigation
        self._current = current
        self._fill()

    def select(self, target: Target | None) -> None:
        """Show `target` as the current document. Does not emit `target_selected`."""
        self._current = target
        self.list.blockSignals(True)
        self.list.setCurrentItem(None)
        for row in range(self.list.count()):
            item = self.list.item(row)
            if target is not None and item.data(ITEM).target == target:
                self.list.setCurrentItem(item)
                self.list.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)
                break
        self.list.blockSignals(False)
        self.list.viewport().update()

    def current(self) -> Target | None:
        return self._current

    def titles(self) -> list[str]:
        """Every row as shown, for tests and accessibility."""
        return [self.list.item(row).data(ITEM).title for row in range(self.list.count())]

    def shown(self) -> Navigation:
        return self._shown

    def focus_filter(self) -> None:
        self.filter.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.filter.selectAll()

    def _fill(self) -> None:
        self._shown = self._navigation.filtered(self.filter.text())
        self.list.blockSignals(True)
        self.list.clear()
        for nav in self._shown.items:
            item = QListWidgetItem()
            item.setData(ITEM, nav)
            item.setSizeHint(QSize(100, HEIGHTS[nav.kind]))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable if nav.kind == ENTRY
                          else Qt.ItemFlag.NoItemFlags)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.empty.setVisible(not self._shown.items and bool(self.filter.text().strip()))
        self.list.setVisible(bool(self._shown.items) or not self.filter.text().strip())
        self.select(self._current)

    def _filter(self, text: str) -> None:
        self._fill()
        self.filter_changed.emit(text)

    def _current_changed(self, item: QListWidgetItem | None, _previous=None) -> None:
        nav: NavItem | None = item.data(ITEM) if item is not None else None
        if nav is not None and nav.target is not None and nav.target != self._current:
            self._current = nav.target
            self.target_selected.emit(nav.target)

    def _theme_changed(self, *_) -> None:
        self._search_icon.setIcon(icons.icon("search", self._themes.palette.text_subtle))


def recent_action_text(name: str, path: str, limit: int = 46) -> str:
    """`Benchify — …/Proyectos/Benchify`: a menu line for a recent project."""
    short = path if len(path) <= limit else "…" + path[-(limit - 1):]
    return f"{name}  —  {short}"

