"""The start page: choose a project, or go back to a recent one."""

from importlib.resources import as_file, files
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout,
                               QWidget)

from repo_xray.app.recent import RecentProject, RecentProjects, ago
from repo_xray.app.theme import Themes
from repo_xray.app.widgets.common import (Button, ElidedLabel, IconButton, IconLabel, IconTile, caps, label,
                                          set_property, tag)

COLUMN = 760
LEVELS = (
    ("layers", "Overview", "What is it made of?", "Apps, databases and services, read from build files and imports."),
    ("grid", "Features", "What does it do?", "One card per feature, with the layers it touches and what it calls."),
    ("flow", "Flows", "What happens when…?", "A request followed from the screen to the database."),
)


def dropped_folder(event) -> Path | None:
    """The single folder being dragged, or None for anything else."""
    urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
    path = Path(urls[0].toLocalFile()) if len(urls) == 1 and urls[0].isLocalFile() else None
    return path if path is not None and path.is_dir() else None


class Mark(QWidget):
    """The app's own icon, drawn from its SVG at any size."""

    def __init__(self, size: int = 52):
        super().__init__()
        with as_file(files("repo_xray.app") / "icon.svg") as icon:
            self._renderer = QSvgRenderer(str(icon))
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._renderer.render(painter, QRectF(0, 0, self.width(), self.height()))


class RecentRow(QFrame):
    """One recent project: its name, where it is and what the last analysis found."""

    opened = Signal(Path)
    removed = Signal(Path)

    def __init__(self, project: RecentProject, themes: Themes):
        super().__init__()
        self.project = project
        self.setProperty("role", "card")
        self.setProperty("interactive", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Open {project.path}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 8, 10)
        layout.setSpacing(12)
        layout.addWidget(IconLabel("folder", themes, 18))
        texts = QVBoxLayout()
        texts.setSpacing(1)
        self.title = ElidedLabel(project.title, "heading")
        self.path = ElidedLabel(project.path, "subtle", Qt.TextElideMode.ElideMiddle)
        texts.addWidget(self.title)
        texts.addWidget(self.path)
        layout.addLayout(texts, 1)
        details = "  ·  ".join(part for part in (project.summary(), ago(project.opened)) if part)
        self.details = label(details, "subtle")
        self.details.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.details)
        self.remove = IconButton("close", themes, "Remove from the list", size=14, tone="text_subtle")
        self.remove.clicked.connect(lambda: self.removed.emit(Path(project.path)))
        layout.addWidget(self.remove)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.opened.emit(Path(self.project.path))


class StartPage(QWidget):
    folder_chosen = Signal(Path)

    def __init__(self, themes: Themes, recent: RecentProjects, version: str = ""):
        super().__init__()
        self._themes = themes
        self._recent = recent
        self.setObjectName("canvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setAcceptDrops(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(16, 12, 16, 0)
        bar.addStretch()
        self.theme_button = IconButton("moon", themes, "Switch between light and dark")
        self.theme_button.clicked.connect(themes.toggle)
        bar.addWidget(self.theme_button)
        outer.addLayout(bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        centre = QHBoxLayout(body)
        centre.setContentsMargins(32, 8, 32, 40)
        centre.addStretch(1)
        column = QWidget()
        column.setMaximumWidth(COLUMN)
        column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        centre.addWidget(column, 100)
        centre.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(self._hero(version))
        layout.addSpacing(26)
        layout.addWidget(self._dropzone())
        layout.addSpacing(14)
        layout.addLayout(self._levels())
        layout.addSpacing(30)

        heading = QHBoxLayout()
        self.recent_title = caps("Recent projects")
        heading.addWidget(self.recent_title)
        heading.addStretch()
        self.clear = Button("Clear list", themes, variant="link")
        self.clear.clicked.connect(self._clear_recent)
        heading.addWidget(self.clear)
        layout.addLayout(heading)
        layout.addSpacing(8)
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(6)
        layout.addLayout(self.recent_box)
        layout.addStretch(1)

        themes.changed.connect(self._theme_changed)
        self._theme_changed()
        self.refresh_recent()

    # Parts

    def _hero(self, version: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(Mark(52), alignment=Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        title = QHBoxLayout()
        title.setSpacing(10)
        title.addWidget(label("repo-xray", "display"))
        if version:
            title.addWidget(tag(f"v{version}"), alignment=Qt.AlignmentFlag.AlignBottom)
        title.addStretch()
        texts.addLayout(title)
        texts.addWidget(label("Architecture documentation generated from source code: what a project is made of, "
                              "what it does and what happens when someone uses it.", "muted", wrap=True))
        row.addLayout(texts, 1)
        return row

    def _dropzone(self) -> QFrame:
        self.dropzone = QFrame()
        self.dropzone.setProperty("role", "dropzone")
        self.dropzone.setMinimumHeight(206)
        zone = QVBoxLayout(self.dropzone)
        zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zone.setSpacing(6)
        zone.addWidget(IconTile("folder-open", self._themes, 44), alignment=Qt.AlignmentFlag.AlignHCenter)
        zone.addSpacing(8)
        heading = label("Drop a project folder here", "title")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zone.addWidget(heading)
        hint = label("Python, Java and TypeScript projects. Your code never leaves this computer.", "muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zone.addWidget(hint)
        zone.addSpacing(10)
        self.choose = Button("Choose folder…", self._themes, "folder", "primary", "Choose the project's folder  (Ctrl+O)")
        self.choose.clicked.connect(self.choose_folder)
        zone.addWidget(self.choose, alignment=Qt.AlignmentFlag.AlignHCenter)
        return self.dropzone

    def _levels(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(10)
        for column, (icon, title, question, text) in enumerate(LEVELS):
            card = QFrame()
            card.setProperty("role", "card")
            box = QVBoxLayout(card)
            box.setContentsMargins(14, 12, 14, 14)
            box.setSpacing(4)
            head = QHBoxLayout()
            head.setSpacing(8)
            head.addWidget(IconLabel(icon, self._themes, 16, "accent_text"))
            head.addWidget(label(f"{column + 1} · {title}", "heading"))
            head.addStretch()
            box.addLayout(head)
            box.addWidget(label(question, "muted"))
            box.addWidget(label(text, "subtle", wrap=True))
            box.addStretch()
            grid.addWidget(card, 0, column)
            grid.setColumnStretch(column, 1)
        return grid

    # Recent projects

    def refresh_recent(self) -> None:
        while self.recent_box.count():
            old = self.recent_box.takeAt(0).widget()
            old.hide()  # deleteLater() waits for the event loop; until then it would still be drawn
            old.deleteLater()
        projects = self._recent.all()
        self.recent_title.setVisible(bool(projects))
        self.clear.setVisible(bool(projects))
        for project in projects:
            row = RecentRow(project, self._themes)
            row.opened.connect(self.folder_chosen)
            row.removed.connect(self._remove_recent)
            self.recent_box.addWidget(row)

    def recent_rows(self) -> list[RecentRow]:
        rows = (self.recent_box.itemAt(i).widget() for i in range(self.recent_box.count()))
        return [row for row in rows if isinstance(row, RecentRow)]

    def _remove_recent(self, folder: Path) -> None:
        self._recent.forget(folder)
        self.refresh_recent()

    def _clear_recent(self) -> None:
        self._recent.clear()
        self.refresh_recent()

    # Choosing a folder

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.choose.setFocus()  # Enter opens the folder dialog: the page's one main action

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose the project folder")
        if folder:
            self.folder_chosen.emit(Path(folder))

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if dropped_folder(event) is not None:
            event.acceptProposedAction()
            self.set_drop_highlight(True)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.set_drop_highlight(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self.set_drop_highlight(False)
        folder = dropped_folder(event)
        if folder is not None:
            event.acceptProposedAction()
            self.folder_chosen.emit(folder)

    def set_drop_highlight(self, active: bool) -> None:
        set_property(self.dropzone, "active", active)

    def _theme_changed(self, *_) -> None:
        self.theme_button.set_icon("sun" if self._themes.is_dark else "moon")
