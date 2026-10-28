"""The main window: choose a project, watch the analysis, preview and export the documents."""

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QProgressBar, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from repo_xray.app.preview import DiagramView, PageView
from repo_xray.app.workers import Task, analysis_task, export_task
from repo_xray.export.markdown import FOLDER, Bundle, feature_page
from repo_xray.pipeline import Analysis
from repo_xray.render.theme import THEMES, Theme

MAX_RECENT = 5
KIND_NAMES = {"web": "web app", "api": "API", "mobile": "mobile app", "desktop": "desktop app", "library": "app"}


class StartPage(QWidget):
    folder_chosen = Signal(Path)

    def __init__(self, settings: QSettings):
        super().__init__()
        self.settings = settings
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 48)
        layout.setSpacing(10)

        title = QLabel("repo-xray")
        title.setObjectName("title")
        subtitle = QLabel("Turn a project into clear architecture docs: what it is made of, "
                          "what it does and what happens when someone uses it.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(24)

        self.dropzone = QFrame()
        self.dropzone.setObjectName("dropzone")
        self.dropzone.setMinimumHeight(220)
        zone = QVBoxLayout(self.dropzone)
        zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zone.setSpacing(12)
        heading = QLabel("Drop a project folder here")
        heading.setObjectName("heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("Python, Java and TypeScript projects. Your code never leaves this computer.")
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.choose = QPushButton("Choose project folder…")
        self.choose.setObjectName("primary")
        self.choose.setCursor(Qt.CursorShape.PointingHandCursor)
        self.choose.clicked.connect(self._choose)
        zone.addWidget(heading)
        zone.addWidget(hint)
        zone.addWidget(self.choose, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.dropzone)

        layout.addSpacing(20)
        self.recent_title = QLabel("RECENT PROJECTS")
        self.recent_title.setObjectName("section")
        layout.addWidget(self.recent_title)
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(0)
        layout.addLayout(self.recent_box)
        layout.addStretch()
        self.refresh_recent()

    def refresh_recent(self) -> None:
        while self.recent_box.count():
            old = self.recent_box.takeAt(0).widget()
            old.hide()  # deleteLater() waits for the event loop; until then it would still be drawn
            old.deleteLater()
        recent = [p for p in self.settings.value("recent", [], list) if Path(p).is_dir()]
        self.recent_title.setVisible(bool(recent))
        for path in recent:
            button = QPushButton(f"{Path(path).name}   ·   {path}")
            button.setObjectName("link")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, p=path: self.folder_chosen.emit(Path(p)))
            self.recent_box.addWidget(button)

    def _choose(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose the project folder")
        if folder:
            self.folder_chosen.emit(Path(folder))

    def dragEnterEvent(self, event) -> None:
        if self._dropped_folder(event) is not None:
            event.acceptProposedAction()
            self._highlight(True)

    def dragLeaveEvent(self, event) -> None:
        self._highlight(False)

    def dropEvent(self, event) -> None:
        self._highlight(False)
        folder = self._dropped_folder(event)
        if folder is not None:
            self.folder_chosen.emit(folder)

    def _highlight(self, active: bool) -> None:
        self.dropzone.setProperty("active", active)
        self.dropzone.style().unpolish(self.dropzone)
        self.dropzone.style().polish(self.dropzone)

    @staticmethod
    def _dropped_folder(event) -> Path | None:
        urls = event.mimeData().urls()
        path = Path(urls[0].toLocalFile()) if len(urls) == 1 and urls[0].isLocalFile() else None
        return path if path is not None and path.is_dir() else None


class ProgressPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 64, 64, 64)
        layout.addStretch()
        self.heading = QLabel()
        self.heading.setObjectName("heading")
        self.message = QLabel()
        self.message.setObjectName("muted")
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        layout.addWidget(self.heading)
        layout.addSpacing(8)
        layout.addWidget(self.bar)
        layout.addWidget(self.message)
        layout.addStretch()

    def start(self, folder: Path) -> None:
        self.heading.setText(f"Analysing {folder.name}…")
        self.update(0, "Starting")

    def update(self, fraction: float, message: str) -> None:
        self.bar.setValue(round(fraction * 1000))
        self.message.setText(message)


class ResultsPage(QWidget):
    export_requested = Signal()
    restart_requested = Signal()

    def __init__(self, theme: Theme):
        super().__init__()
        self.theme = theme
        self.bundle: Bundle = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title = QLabel()
        self.title.setObjectName("heading")
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        titles.addWidget(self.title)
        titles.addWidget(self.summary)
        top.addLayout(titles, 1)
        self.light = QPushButton("Light")
        self.dark = QPushButton("Dark")
        group = QButtonGroup(self)
        for button in (self.light, self.dark):
            button.setCheckable(True)
            group.addButton(button)
            top.addWidget(button)
        (self.dark if theme.name == "dark" else self.light).setChecked(True)
        top.addSpacing(12)
        self.restart = QPushButton("New analysis")
        self.restart.clicked.connect(self.restart_requested)
        self.export = QPushButton("Export zip…")
        self.export.setObjectName("primary")
        self.export.clicked.connect(self.export_requested)
        top.addWidget(self.restart)
        top.addWidget(self.export)
        layout.addLayout(top)

        self.export_status = QLabel()
        self.export_status.setObjectName("hint")
        self.export_status.hide()
        layout.addWidget(self.export_status)

        body = QHBoxLayout()
        body.setSpacing(16)
        self.documents = QListWidget()
        self.documents.setFixedWidth(260)
        self.documents.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.documents.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.documents.currentItemChanged.connect(self._show_current)
        body.addWidget(self.documents)
        self.views = QStackedWidget()
        self.diagram = DiagramView()
        self.page = PageView()
        self.views.addWidget(self.diagram)
        self.views.addWidget(self.page)
        body.addWidget(self.views, 1)
        layout.addLayout(body, 1)
        self.dark.toggled.connect(self._show_current)  # connected last: the list must exist

    def show_results(self, analysis: Analysis, bundle: Bundle) -> None:
        self.bundle = bundle
        stack = analysis.stack
        self.title.setText(stack.name)
        apps = ", ".join(f"{a.name} ({KIND_NAMES.get(a.kind, 'app')})" for a in stack.apps) or "no apps found"
        self.summary.setText(f"{apps}  ·  {len(analysis.features.features)} features  ·  "
                             f"{len(analysis.flows)} flows  ·  {len(analysis.files)} files")
        self.export_status.hide()
        self.documents.clear()
        self._section("DIAGRAMS")
        self._entry("What is it made of?", ("diagram", "overview"))
        self._entry("What does it do?", ("diagram", "features"))
        for flow in analysis.highlights:
            self._entry(f"When: {flow.title}", ("diagram", f"flow-{flow.key}"))
        self._section("PAGES")
        self._entry("Architecture overview", ("page", f"{FOLDER}/README.md"))
        for feature in analysis.features.features:
            self._entry(f"{feature.name}  ·  {feature.app}", ("page", feature_page(feature.key)))
        self.documents.setCurrentRow(1)

    def _section(self, title: str) -> None:
        item = QListWidgetItem(title)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = item.font()
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 0.8)
        item.setFont(font)
        self.documents.addItem(item)

    def _entry(self, text: str, target: tuple[str, str]) -> None:
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, target)
        item.setToolTip(text)
        self.documents.addItem(item)

    def _show_current(self, *_) -> None:
        item = self.documents.currentItem()
        target = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not target:
            return
        kind, name = target
        if kind == "page":
            self.page.show_markdown(str(self.bundle[name]))
            self.views.setCurrentWidget(self.page)
            return
        theme = THEMES["dark" if self.dark.isChecked() else "light"]
        self.diagram.show_svg(str(self.bundle[f"{FOLDER}/images/{name}-{theme.name}.svg"]), theme.background)
        self.views.setCurrentWidget(self.diagram)

    def set_export_status(self, text: str | None) -> None:
        self.export_status.setVisible(bool(text))
        self.export_status.setText(text or "")
        self.export.setEnabled(text is None)


class MainWindow(QMainWindow):
    def __init__(self, theme: Theme, settings: QSettings | None = None):
        super().__init__()
        self.settings = settings or QSettings("repo-xray", "repo-xray")
        self.setWindowTitle("repo-xray")
        self.resize(1280, 820)
        self.analysis: Analysis | None = None
        self.task: Task | None = None
        self.export_message: QMessageBox | None = None

        self.pages = QStackedWidget()
        self.start = StartPage(self.settings)
        self.progress = ProgressPage()
        self.results = ResultsPage(theme)
        for page in (self.start, self.progress, self.results):
            self.pages.addWidget(page)
        self.setCentralWidget(self.pages)

        self.start.folder_chosen.connect(self.analyse)
        self.results.export_requested.connect(self.choose_export)
        self.results.restart_requested.connect(self.show_start)

    def show_start(self) -> None:
        self.start.refresh_recent()
        self.pages.setCurrentWidget(self.start)

    def analyse(self, folder: Path) -> None:
        self.progress.start(folder)
        self.pages.setCurrentWidget(self.progress)
        self.task = analysis_task(folder)
        self.task.progress.connect(lambda message, fraction: self.progress.update(fraction, message))
        self.task.finished.connect(lambda result: self._analysed(folder, *result))
        self.task.failed.connect(self._analysis_failed)
        self.task.start()

    def _analysed(self, folder: Path, analysis: Analysis, bundle: Bundle) -> None:
        self.analysis = analysis
        self._remember(folder)
        self.results.show_results(analysis, bundle)
        self.pages.setCurrentWidget(self.results)

    def _analysis_failed(self, error: str) -> None:
        QMessageBox.warning(self, "The analysis failed", f"repo-xray could not analyse this folder.\n\n{error}")
        self.show_start()

    def choose_export(self) -> None:
        if self.analysis is None:
            return
        documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        suggested = str(Path(documents) / f"{self.analysis.stack.name}-architecture.zip")
        path, _ = QFileDialog.getSaveFileName(self, "Export documentation", suggested, "Zip files (*.zip)")
        if path:
            self.export(Path(path))

    def export(self, destination: Path) -> None:
        self.results.set_export_status("Exporting… rendering the diagrams and writing the zip.")
        self.task = export_task(self.analysis, destination)
        self.task.finished.connect(self._exported)
        self.task.failed.connect(self._export_failed)
        self.task.start()

    def _exported(self, path: Path) -> None:
        self.results.set_export_status(None)
        box = QMessageBox(self)
        box.setWindowTitle("Documentation exported")
        box.setText(f"The documentation is in {path.name}.\n\nOpen HOW-TO-USE.md inside the zip "
                    "to add it to your repository.")
        open_folder = box.addButton("Show in folder", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        box.buttonClicked.connect(lambda button: button is open_folder and QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(path.parent))))
        box.open()  # not exec(): the window keeps running while the message is shown
        self.export_message = box

    def _export_failed(self, error: str) -> None:
        self.results.set_export_status(None)
        QMessageBox.warning(self, "The export failed", f"The zip could not be written.\n\n{error}")

    def _remember(self, folder: Path) -> None:
        recent = [p for p in self.settings.value("recent", [], list) if p != str(folder)]
        self.settings.setValue("recent", [str(folder), *recent][:MAX_RECENT])
