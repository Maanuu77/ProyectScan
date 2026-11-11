"""The main window: it owns the three screens and everything that happens between them.

    start page  ->  analysis page  ->  workspace
                      (a problem is explained there, in place)

Screens only show things and announce what the user asked for. Running
the analysis, saving texts, exporting and remembering projects is done
here, so each screen can be tested without the others.
"""

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QStackedWidget

from repo_xray import __version__
from repo_xray.app import navigation as nav
from repo_xray.app.pages.analysis import AnalysisPage
from repo_xray.app.pages.start import StartPage, dropped_folder
from repo_xray.app.pages.workspace import WorkspacePage
from repo_xray.app.recent import RecentProjects
from repo_xray.app.texts_dialog import TextsDialog
from repo_xray.app.theme import Themes
from repo_xray.app.widgets.common import menu
from repo_xray.app.widgets.sidebar import recent_action_text
from repo_xray.app.widgets.toast import Toasts
from repo_xray.app.workers import Task, analysis_task, export_task
from repo_xray.config import save_texts
from repo_xray.export.markdown import Bundle
from repo_xray.export.png import svg_to_png
from repo_xray.parsers.cache import ParseCache
from repo_xray.pipeline import Analysis

MAX_RECENT_IN_MENU = 6
MINIMUM_SIZE = (940, 600)


class MainWindow(QMainWindow):
    def __init__(self, themes: Themes, settings: QSettings | None = None):
        super().__init__()
        self.themes = themes
        self.settings = settings or QSettings("repo-xray", "repo-xray")
        self.recent = RecentProjects(self.settings)
        self.setWindowTitle("repo-xray")
        self.setMinimumSize(*MINIMUM_SIZE)
        self.resize(1360, 860)
        self.setAcceptDrops(True)
        self.analysis: Analysis | None = None
        self.folder: Path | None = None  # the project being analysed or shown
        self.task: Task | None = None
        self.cache = ParseCache()  # a refresh after editing texts only reads the files that changed
        self._sidebar_before_fullscreen = True

        self.pages = QStackedWidget()
        self.start = StartPage(themes, self.recent, __version__)
        self.analysing = AnalysisPage(themes)
        self.workspace = WorkspacePage(themes)
        for page in (self.start, self.analysing, self.workspace):
            self.pages.addWidget(page)
        self.setCentralWidget(self.pages)
        self.toasts = Toasts(self.pages, themes)

        self.start.folder_chosen.connect(self.analyse)
        self.analysing.cancel_requested.connect(self.cancel)
        self.analysing.retry_requested.connect(self.analyse_again)
        self.analysing.choose_requested.connect(self.choose_folder)
        self.analysing.back_requested.connect(self.show_start)
        workspace = self.workspace
        workspace.export_requested.connect(self.choose_export)
        workspace.save_diagram_requested.connect(self.choose_diagram_file)
        workspace.copy_diagram_requested.connect(self.copy_diagram)
        workspace.copy_page_requested.connect(self.copy_page)
        workspace.language_changed.connect(self.change_language)
        workspace.edit_requested.connect(self.edit_texts)
        workspace.project_menu_requested.connect(self.project_menu)
        workspace.external_link_requested.connect(self._open_link)
        workspace.fullscreen_requested.connect(self.toggle_fullscreen)
        self._shortcuts()
        self._restore_window()

    # Screens

    def show_start(self) -> None:
        self.start.refresh_recent()
        self.pages.setCurrentWidget(self.start)
        self.setWindowTitle("repo-xray")

    def close_project(self) -> None:
        self._drop_task()
        self.analysis = self.folder = None
        self.show_start()

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose the project folder",
                                                  str(self.folder.parent) if self.folder else "")
        if folder:
            self.analyse(Path(folder))

    # Analysis

    def analyse(self, folder: Path, quiet: bool = False) -> None:
        """Analyse `folder`; `quiet` keeps the results on screen while they are refreshed."""
        folder = Path(folder).absolute()
        self._drop_task()
        if not quiet:
            self.folder = folder
            self.analysing.start(folder)
            self.pages.setCurrentWidget(self.analysing)
            self.setWindowTitle(f"{folder.name} — repo-xray")
            if not folder.is_dir():
                self.analysing.show_problem(
                    "This folder cannot be opened",
                    "It may have been moved, renamed or deleted, or it is on a drive that is not connected.",
                    str(folder))
                return
        else:
            self.workspace.set_busy("Updating the documents…")
        task = self.task = analysis_task(folder, self.cache)
        if not quiet:
            task.progress.connect(self.analysing.show_progress)
        task.finished.connect(lambda result, t=task: self._analysed(t, folder, *result, quiet=quiet))
        task.failed.connect(lambda error, t=task: self._analysis_failed(t, error, quiet))
        task.cancelled.connect(lambda t=task: self._analysis_cancelled(t, quiet))
        task.start()

    def analyse_again(self) -> None:
        """Read the project again: on the results, quietly; after a failure, from the start."""
        if self.folder is None:
            return
        showing_results = self.pages.currentWidget() is self.workspace and self.analysis is not None
        if showing_results and self.workspace.is_busy():
            return
        self.analyse(self.folder, quiet=showing_results)

    def cancel(self) -> None:
        if self.task is not None:
            self.task.cancel()

    def _drop_task(self) -> None:
        """Forget the running task, if any: it is told to stop and its result will be ignored."""
        if self.task is not None:
            self.task.cancel()
            self.task = None
            self.workspace.set_busy(None)

    def _analysed(self, task: Task, folder: Path, analysis: Analysis, bundle: Bundle, quiet: bool = False) -> None:
        if task is not self.task:
            return  # a newer analysis replaced this one
        self.task = None
        self.analysing.stop()
        self.workspace.set_busy(None)
        if not analysis.files:
            self._no_sources(analysis, quiet)
            return
        self.analysis, self.folder = analysis, folder
        stack = analysis.stack
        self.recent.remember(folder, stack.name, len(stack.apps), len(analysis.features.features), len(analysis.flows))
        self.workspace.show_results(analysis, bundle, keep_selection=quiet)
        self.pages.setCurrentWidget(self.workspace)
        self.setWindowTitle(f"{stack.name} — repo-xray")
        if not quiet:
            self.workspace.focus_document()

    def _no_sources(self, analysis: Analysis, quiet: bool) -> None:
        diagnostic = next((d for d in analysis.diagnostics if d.code == "no-sources"), None)
        text = diagnostic.detail if diagnostic else "This folder has no Python, Java or TypeScript files."
        if quiet:
            self.toasts.show("The project has no source files any more; the documents were not updated.", "warning")
            return
        self.analysing.show_problem(f"No source files found in {analysis.root.name}", text, str(analysis.root),
                                    can_retry=False, tone="empty")

    def _analysis_failed(self, task: Task, error: str, quiet: bool) -> None:
        if task is not self.task:
            return
        self.task = None
        self.analysing.stop()
        if quiet:
            self.workspace.set_busy(None)
            self.toasts.show(f"The documents could not be updated. {error}", "error")
            return
        kind, _, message = error.partition(": ")
        if "xray.toml" in error or kind == "TOMLDecodeError":
            title, text = "xray.toml could not be read", ("The project's xray.toml has an error. "
                                                          "Fix or delete the file, then try again.")
        else:
            title, text = "The analysis failed", ("repo-xray could not analyse this folder. Nothing was changed in it. "
                                                  "If it keeps happening, the detail below helps to report it.")
        self.analysing.show_problem(title, text, message or error)

    def _analysis_cancelled(self, task: Task, quiet: bool) -> None:
        if task is not self.task:
            return
        self.task = None
        self.analysing.stop()
        if quiet:
            self.workspace.set_busy(None)
        elif self.analysis is not None:
            self.folder = self.analysis.root
            self.pages.setCurrentWidget(self.workspace)  # back to the results that were already there
            self.setWindowTitle(f"{self.analysis.stack.name} — repo-xray")
        else:
            self.show_start()

    # Texts and language

    def change_language(self, language: str | None) -> None:
        if self.analysis is None or language == self.analysis.config.language:
            return
        config = self.analysis.config
        self._save_and_refresh(language, config.description, config.features)

    def edit_texts(self) -> None:
        if self.analysis is None or self.workspace.is_busy():
            return
        dialog = TextsDialog(self.analysis, self.themes, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_and_refresh(self.analysis.config.language, dialog.project_description(), dialog.feature_texts())

    def _save_and_refresh(self, language, description, features) -> None:
        try:
            save_texts(self.analysis.root, language, description, features)
        except OSError as exc:
            self.toasts.show(f"xray.toml could not be written in the project. {exc}", "error")
            return
        self.analyse(self.analysis.root, quiet=True)

    # Export

    def choose_export(self) -> None:
        if self.analysis is None or self.workspace.is_busy():
            return
        suggested = str(self._documents_folder() / f"{self.analysis.stack.name}-architecture.zip")
        path, _ = QFileDialog.getSaveFileName(self, "Export documentation", suggested, "Zip files (*.zip)")
        if path:
            self.export(Path(path))

    def export(self, destination: Path) -> None:
        self._drop_task()
        self.workspace.set_busy("Exporting: rendering the PNG copies and writing the zip…")
        task = self.task = export_task(self.analysis, destination)
        task.finished.connect(lambda path, t=task: self._exported(t, path))
        task.failed.connect(lambda error, t=task: self._export_failed(t, error))
        task.start()

    def _exported(self, task: Task, path: Path) -> None:
        if task is not self.task:
            return
        self.task = None
        self.workspace.set_busy(None)
        self.toasts.show(f"Documentation exported to {path.name}. Open HOW-TO-USE.md inside the zip to add it "
                         "to your repository.", "success", ("Show in folder", lambda: self._reveal(path.parent)), 12000)

    def _export_failed(self, task: Task, error: str) -> None:
        if task is not self.task:
            return
        self.task = None
        self.workspace.set_busy(None)
        self.toasts.show(f"The zip could not be written. {error}", "error")

    def choose_diagram_file(self, kind: str) -> None:
        current = self.workspace.current_diagram()
        if current is None:
            return
        name, _ = current
        suggested = self._documents_folder() / f"{self.analysis.stack.name}-{name}-{self.themes.palette.name}.{kind}"
        filters = "SVG image (*.svg)" if kind == "svg" else "PNG image (*.png)"
        path, _ = QFileDialog.getSaveFileName(self, "Save this diagram", str(suggested), filters)
        if path:
            self.save_diagram(Path(path))

    def save_diagram(self, destination: Path) -> bool:
        """Write the diagram on show as SVG or PNG, by the destination's extension."""
        current = self.workspace.current_diagram()
        if current is None:
            return False
        _, svg = current
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.suffix.lower() == ".png":
                destination.write_bytes(svg_to_png(svg, self.themes.palette.diagram.background))
            else:
                destination.write_text(svg, encoding="utf-8")
        except (OSError, ValueError) as exc:
            self.toasts.show(f"The diagram could not be saved. {exc}", "error")
            return False
        self.toasts.show(f"Diagram saved as {destination.name}.", "success",
                         ("Show in folder", lambda: self._reveal(destination.parent)))
        return True

    def copy_diagram(self) -> bool:
        current = self.workspace.current_diagram()
        if current is None:
            return False
        image = QImage.fromData(svg_to_png(current[1], self.themes.palette.diagram.background), "PNG")
        QGuiApplication.clipboard().setImage(image)
        self.toasts.show("Diagram copied. Paste it into a document, a slide or a chat.", "success")
        return True

    def copy_page(self) -> bool:
        markdown = self.workspace.current_markdown()
        if markdown is None:
            return False
        QGuiApplication.clipboard().setText(markdown)
        self.toasts.show("Page copied as Markdown.", "success")
        return True

    def _documents_folder(self) -> Path:
        remembered = self.settings.value("export_folder", "", str)
        if remembered and Path(remembered).is_dir():
            return Path(remembered)
        return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation))

    def _reveal(self, folder: Path) -> None:
        self.settings.setValue("export_folder", str(folder))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    @staticmethod
    def _open_link(address: str) -> None:
        QDesktopServices.openUrl(QUrl(address))

    # Project menu and shortcuts

    def project_actions(self) -> list[tuple[str, object]]:
        """(text, what to call) for the project menu; ("-", None) is a separator."""
        actions: list[tuple[str, object]] = [
            ("Open another folder…\tCtrl+O", self.choose_folder),
            ("Analyse again\tF5", self.analyse_again),
            ("Show in file manager", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder)))),
        ]
        others = [p for p in self.recent.all() if self.folder is None or Path(p.path) != self.folder]
        if others:
            actions.append(("-", None))
            for project in others[:MAX_RECENT_IN_MENU]:
                actions.append((recent_action_text(project.title, project.path),
                                lambda path=project.path: self.analyse(Path(path))))
        return [*actions, ("-", None), ("Close project", self.close_project)]

    def project_menu(self) -> None:
        popup = menu(self)
        for text, callback in self.project_actions():
            if text == "-":
                popup.addSeparator()
            else:
                popup.addAction(text).triggered.connect(lambda _=False, call=callback: call())
        header = self.workspace.sidebar.header
        popup.exec(header.mapToGlobal(header.rect().bottomLeft()))

    def _shortcuts(self) -> None:
        workspace = self.workspace

        def on_results(action):
            """Only while the workspace is showing: the other screens have no documents to act on."""
            return lambda: self.pages.currentWidget() is workspace and action()

        bindings = {
            "Ctrl+O": self.choose_folder,
            "F5": self.analyse_again,
            "Ctrl+R": self.analyse_again,
            "Ctrl+1": on_results(lambda: workspace.open_level(nav.OVERVIEW)),
            "Ctrl+2": on_results(lambda: workspace.open_level(nav.FEATURES)),
            "Ctrl+3": on_results(lambda: workspace.open_level(nav.FLOWS)),
            "Ctrl+K": on_results(self._focus_filter),
            "Ctrl+F": on_results(workspace.open_find),
            "Ctrl+E": on_results(self.choose_export),
            "Ctrl+Shift+C": on_results(self.copy_diagram),
            "Ctrl+T": on_results(self.edit_texts),
            "Ctrl+B": on_results(workspace.toggle_sidebar),
            "Ctrl+D": self.themes.toggle,
            "Ctrl+PgDown": on_results(lambda: workspace.open_neighbour(1)),
            "Ctrl+PgUp": on_results(lambda: workspace.open_neighbour(-1)),
            "Ctrl+=": on_results(workspace.canvas.zoom_in),
            "Ctrl++": on_results(workspace.canvas.zoom_in),
            "Ctrl+-": on_results(workspace.canvas.zoom_out),
            "Ctrl+0": on_results(workspace.canvas.fit),
            "F11": self.toggle_fullscreen,
            "Esc": self._escape,
        }
        self.shortcuts: dict[str, QShortcut] = {}
        for keys, action in bindings.items():
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(action)
            self.shortcuts[keys] = shortcut

    def _focus_filter(self) -> None:
        if not self.workspace.sidebar.isVisible():
            self.workspace.toggle_sidebar()
        self.workspace.sidebar.focus_filter()

    def _escape(self) -> None:
        if self.pages.currentWidget() is self.analysing and self.analysing.is_running():
            self.cancel()
        elif self.workspace.find_bar.isVisible():
            self.workspace.find_bar.close_bar()
        elif self.isFullScreen():
            self.toggle_fullscreen()

    def toggle_fullscreen(self) -> None:
        """Full screen gives the diagram the whole display: the sidebar steps aside until it ends."""
        sidebar = self.workspace.sidebar
        if self.isFullScreen():
            self.showNormal()
            sidebar.setVisible(self._sidebar_before_fullscreen)
            self.workspace.fullscreen_button.set_icon("expand")
        else:
            self._sidebar_before_fullscreen = sidebar.isVisible()
            sidebar.setVisible(False)
            self.showFullScreen()
            self.workspace.fullscreen_button.set_icon("collapse")

    # Window

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if dropped_folder(event) is not None:
            event.acceptProposedAction()
            self.start.set_drop_highlight(True)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.start.set_drop_highlight(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        """A folder dropped anywhere on the window is analysed, whatever screen is showing."""
        self.start.set_drop_highlight(False)
        folder = dropped_folder(event)
        if folder is not None:
            event.acceptProposedAction()
            self.analyse(folder)

    def _restore_window(self) -> None:
        geometry = self.settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        splitter = self.settings.value("window/splitter")
        if splitter is not None:
            self.workspace.splitter.restoreState(splitter)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.cancel()
        if not self.isFullScreen():
            self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/splitter", self.workspace.splitter.saveState())
        super().closeEvent(event)
