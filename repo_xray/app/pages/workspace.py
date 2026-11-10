"""The workspace: the sidebar with every document, and the document on show.

    ┌ sidebar ─────┬ top bar: level tabs · title · zoom · find · theme · language · edit · export ┐
    │ project      ├───────────────────────────────────────────────────────────────────────────────┤
    │ filter       │                                                                               │
    │ OVERVIEW     │                       a diagram (canvas) or a page                            │
    │ FEATURES     │                                                                               │
    │ FLOWS        ├───────────────────────────────────────────────────────────────────────────────┤
    └──────────────┴ status bar: what is running · how to move around · what the analysis found ──┘
"""

import re
from posixpath import dirname, normpath

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLineEdit, QProgressBar, QSplitter, QStackedWidget, QVBoxLayout,
                               QWidget)

from repo_xray.app import navigation as nav
from repo_xray.app.markdown_html import diagram_name
from repo_xray.app.navigation import DIAGRAM, PAGE, REPORT, Navigation, Target
from repo_xray.app.report import TITLE as REPORT_TITLE
from repo_xray.app.report import build_report
from repo_xray.app.theme import DARK, LIGHT, SYSTEM, Themes
from repo_xray.app.widgets import canvas as canvas_module
from repo_xray.app.widgets.canvas import DiagramCanvas
from repo_xray.app.widgets.common import (Button, ElidedLabel, IconButton, Segmented, Spinner, hairline, label, menu,
                                          tag)
from repo_xray.app.widgets.pageview import PageView
from repo_xray.app.widgets.sidebar import WIDTH as SIDEBAR_WIDTH
from repo_xray.app.widgets.sidebar import Sidebar
from repo_xray.export.markdown import Bundle, diagram_path
from repo_xray.pipeline import Analysis

LANGUAGE_NAMES = {"en": "English", "es": "Español"}
COMPACT_BELOW = 1180  # narrower than this, buttons keep their icon and lose their words
ROOMY_FROM = 1500  # from this width there is room to say what kind of document is on show
TIGHT_BELOW = 1080
LEVELS = [(str(level), nav.LEVEL_TITLES[level], f"{nav.LEVEL_QUESTIONS[level]}  (Ctrl+{level})")
          for level in (nav.OVERVIEW, nav.FEATURES, nav.FLOWS)]
HINTS = {
    DIAGRAM: "Drag to move  ·  Ctrl + wheel to zoom  ·  Double-click to zoom in  ·  Click a card to open it",
    PAGE: "Click a diagram to open it  ·  Links lead to other pages",
    REPORT: "What the analysis read, and what it could not resolve",
}


class FindBar(QFrame):
    """Find a word in the diagram on show: type, Enter for the next match, Esc to close."""

    closed = Signal()

    def __init__(self, themes: Themes, canvas: DiagramCanvas, parent: QWidget):
        super().__init__(parent)
        self.setProperty("role", "findbar")
        self._canvas = canvas
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 6, 6)
        layout.setSpacing(4)
        self.field = QLineEdit()
        self.field.setPlaceholderText("Find in diagram")
        self.field.setProperty("variant", "quiet")
        self.field.setFixedWidth(200)
        self.field.textChanged.connect(canvas.find)
        self.field.returnPressed.connect(lambda: canvas.find_next(1))
        self.field.installEventFilter(self)
        layout.addWidget(self.field)
        self.count = label("", "subtle")
        self.count.setMinimumWidth(52)
        self.count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count)
        self.previous = IconButton("chevron-up", themes, "Previous match  (Shift+Enter)", size=14)
        self.previous.clicked.connect(lambda: canvas.find_next(-1))
        self.next = IconButton("chevron-down", themes, "Next match  (Enter)", size=14)
        self.next.clicked.connect(lambda: canvas.find_next(1))
        self.close_button = IconButton("close", themes, "Close  (Esc)", size=14)
        self.close_button.clicked.connect(self.close_bar)
        for button in (self.previous, self.next, self.close_button):
            layout.addWidget(button)
        canvas.matches_changed.connect(self._show_count)
        self.hide()

    def open(self) -> None:
        self.show()
        self.raise_()
        self.adjustSize()
        self.field.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.field.selectAll()
        self._canvas.find(self.field.text())

    def close_bar(self) -> None:
        self.hide()
        self._canvas.clear_find()
        self._canvas.setFocus()
        self.closed.emit()

    def _show_count(self, current: int, total: int) -> None:
        self.count.setText(f"{current} of {total}" if total else ("No matches" if self.field.text().strip() else ""))

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.field and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.close_bar()
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._canvas.find_next(-1)
                return True
        return False


class WorkspacePage(QWidget):
    export_requested = Signal()  # the documentation zip
    save_diagram_requested = Signal(str)  # "svg" or "png"
    copy_diagram_requested = Signal()
    copy_page_requested = Signal()
    language_changed = Signal(object)  # "en", "es", or None to detect it from the code
    edit_requested = Signal()
    project_menu_requested = Signal()
    external_link_requested = Signal(str)
    fullscreen_requested = Signal()

    def __init__(self, themes: Themes):
        super().__init__()
        self._themes = themes
        self.analysis: Analysis | None = None
        self.bundle: Bundle = {}
        self.navigation = Navigation()
        self.target: Target | None = None
        self._report = ""
        self._busy = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        self.sidebar = Sidebar(themes)
        self.sidebar.target_selected.connect(self.open)
        self.sidebar.project_menu_requested.connect(self.project_menu_requested)
        self.splitter.addWidget(self.sidebar)

        main = QWidget()
        main.setObjectName("canvas")
        main.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        column = QVBoxLayout(main)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._top_bar())
        self.activity = QProgressBar()  # a thin moving bar under the top bar while documents are refreshed
        self.activity.setRange(0, 0)
        self.activity.setTextVisible(False)
        self.activity.setFixedHeight(2)
        self.activity_slot = QStackedWidget()
        self.activity_slot.setFixedHeight(2)
        self.activity_slot.addWidget(hairline())
        self.activity_slot.addWidget(self.activity)
        column.addWidget(self.activity_slot)

        self.views = QStackedWidget()
        self.canvas = DiagramCanvas(themes)
        self.canvas.zoom_changed.connect(self._show_zoom)
        self.canvas.element_clicked.connect(self._element_clicked)
        self.page = PageView(themes)
        self.page.link_clicked.connect(self._link_clicked)
        self.views.addWidget(self.canvas)
        self.views.addWidget(self.page)
        column.addWidget(self.views, 1)
        self.find_bar = FindBar(themes, self.canvas, self.views)
        self.views.installEventFilter(self)

        column.addWidget(hairline())
        column.addWidget(self._status_bar())
        self.splitter.addWidget(main)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([SIDEBAR_WIDTH, 1000])
        layout.addWidget(self.splitter)

        themes.changed.connect(self._theme_changed)
        self._theme_changed()

    # Building the chrome

    def _top_bar(self) -> QWidget:
        themes = self._themes
        bar = QWidget()
        bar.setObjectName("topbar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        bar.setFixedHeight(48)
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 0, 12, 0)
        row.setSpacing(6)

        self.sidebar_button = IconButton("sidebar", themes, "Show or hide the sidebar  (Ctrl+B)")
        self.sidebar_button.clicked.connect(self.toggle_sidebar)
        row.addWidget(self.sidebar_button)
        self.levels = Segmented(LEVELS)
        self.levels.selected.connect(lambda key: self.open_level(int(key)))
        row.addWidget(self.levels)
        row.addSpacing(8)
        self.title = ElidedLabel("", "heading")
        row.addWidget(self.title, 1)
        self.kind = tag("")
        row.addWidget(self.kind)
        row.addSpacing(8)

        self.zoom_group = QWidget()
        zoom = QHBoxLayout(self.zoom_group)
        zoom.setContentsMargins(0, 0, 0, 0)
        zoom.setSpacing(2)
        self.zoom_out = IconButton("minus", themes, "Zoom out  (-)")
        self.zoom_out.clicked.connect(self.canvas_action("zoom_out"))
        self.zoom_level = Button("100%", themes, variant="ghost", tooltip="Zoom")
        self.zoom_level.setFixedWidth(60)
        self.zoom_level.clicked.connect(self._zoom_menu)
        self.zoom_in = IconButton("plus", themes, "Zoom in  (+)")
        self.zoom_in.clicked.connect(self.canvas_action("zoom_in"))
        self.fit_button = IconButton("fit", themes, "Fit the width, or the whole diagram  (0)")
        self.fit_button.clicked.connect(self.canvas_action("toggle_fit"))
        self.find_button = IconButton("search", themes, "Find in the diagram  (Ctrl+F)")
        self.find_button.clicked.connect(self.open_find)
        for widget in (self.zoom_out, self.zoom_level, self.zoom_in, self.fit_button, self.find_button):
            zoom.addWidget(widget)
        row.addWidget(self.zoom_group)
        row.addWidget(hairline(vertical=True))

        self.fullscreen_button = IconButton("expand", themes, "Full screen  (F11)")
        self.fullscreen_button.clicked.connect(self.fullscreen_requested)
        row.addWidget(self.fullscreen_button)
        self.theme_button = IconButton("moon", themes, "Theme: light, dark or follow the system")
        self.theme_button.clicked.connect(self._theme_menu)
        row.addWidget(self.theme_button)
        self.language = IconButton("globe", themes, "Language of the documents")
        self.language.clicked.connect(self._language_menu)
        row.addWidget(self.language)
        self.edit = Button("Edit texts", themes, "pencil", tooltip="Rename features and rewrite descriptions  (Ctrl+T)")
        self.edit.clicked.connect(self.edit_requested)
        row.addWidget(self.edit)
        self.export = Button("Export", themes, "export", "primary", "Export the documentation or this diagram  (Ctrl+E)")
        self.export.clicked.connect(self._export_menu)
        row.addWidget(self.export)
        self._labelled = [(self.edit, "Edit texts"), (self.export, "Export")]
        return bar

    def _status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("statusbar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        bar.setFixedHeight(28)
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(8)
        self.spinner = Spinner(self._themes, 14)
        self.spinner.hide()
        row.addWidget(self.spinner)
        self.status = ElidedLabel("", "subtle")
        row.addWidget(self.status, 1)
        self.notes = Button("", self._themes, "warning", "link", "Open the analysis report")
        self.notes.clicked.connect(lambda: self.open(nav.REPORT_PAGE))
        self.notes.hide()
        row.addWidget(self.notes)
        self.facts = label("", "subtle")
        row.addWidget(self.facts)
        return bar

    def canvas_action(self, name: str):
        return lambda *_: getattr(self.canvas, name)()

    # Showing results

    def show_results(self, analysis: Analysis, bundle: Bundle, keep_selection: bool = False) -> None:
        """Show a finished analysis. `keep_selection` stays on the current document, for a refresh."""
        previous = self.target if keep_selection else None
        self.analysis = analysis
        self.bundle = bundle
        self._report = build_report(analysis)
        self.navigation = nav.build(analysis)
        self.sidebar.set_project(analysis.stack.name, analysis.root)
        if not keep_selection:
            self.sidebar.filter.clear()
        self.sidebar.set_navigation(self.navigation)
        self._show_language(analysis)
        self._show_facts(analysis)
        self.canvas.set_clickable(i for i in _element_ids(bundle) if nav.target_of_element(analysis, i) is not None)
        target = previous if previous is not None and self.navigation.find(previous) else nav.OVERVIEW_DIAGRAM
        self.target = None
        self.open(target, keep_view=keep_selection)

    def open(self, target: Target | None, keep_view: bool = False) -> bool:
        """Show a document. Returns False when the analysis has no such document."""
        if target is None or self.analysis is None or not self._exists(target):
            return False
        same = target == self.target
        self.target = target
        item = self.navigation.find(target)
        self.title.setText(item.title if item else REPORT_TITLE)
        self.kind.setText({DIAGRAM: "Diagram", PAGE: "Page", REPORT: "Report"}[target.kind])
        self.levels.select(str(item.level) if item and item.level else None)
        self.sidebar.select(target)
        self.zoom_group.setVisible(target.kind == DIAGRAM)
        if target.kind == DIAGRAM:
            palette = self._themes.palette
            self.canvas.show_svg(self._diagram(target.name), palette.diagram.background, keep_view=keep_view and same)
            self.views.setCurrentWidget(self.canvas)
        else:
            if self.find_bar.isVisible():
                self.find_bar.close_bar()
            markdown = self._report if target.kind == REPORT else str(self.bundle[target.name])
            self.page.show_markdown(markdown, self._diagram, keep_position=keep_view and same)
            self.views.setCurrentWidget(self.page)
        if not self._busy:
            self.status.setText(HINTS[target.kind])
        return True

    def open_level(self, level: int) -> bool:
        return self.open(self.navigation.home(level))

    def open_neighbour(self, step: int) -> bool:
        """The next or previous document in the sidebar's order."""
        shown = self.sidebar.shown()
        return self.open(shown.neighbour(self.target, step) if self.target else None)

    def current_diagram(self) -> tuple[str, str] | None:
        """(name, SVG in the current theme) of the diagram on show, or None when a page is shown."""
        if self.target is None or self.target.kind != DIAGRAM:
            return None
        return self.target.name, self._diagram(self.target.name)

    def current_markdown(self) -> str | None:
        if self.target is None or self.target.kind == DIAGRAM:
            return None
        return self._report if self.target.kind == REPORT else str(self.bundle[self.target.name])

    def _exists(self, target: Target) -> bool:
        if target.kind == REPORT:
            return True
        if target.kind == DIAGRAM:
            return diagram_path(target.name, LIGHT) in self.bundle
        return target.name in self.bundle

    def _diagram(self, name: str) -> str | None:
        content = self.bundle.get(diagram_path(name, self._themes.palette.name))
        return str(content) if content is not None else None

    def _show_facts(self, analysis: Analysis) -> None:
        files = len(analysis.files)
        took = f"{analysis.seconds:.1f} s" if analysis.seconds >= 0.1 else "under 0.1 s"
        self.facts.setText(f"{files:,} file{'' if files == 1 else 's'}  ·  {len(analysis.features.features)} features"
                           f"  ·  {len(analysis.flows)} flows  ·  analysed in {took}")
        problems = [d for d in analysis.diagnostics if d.severity != "info"]
        self.notes.setVisible(bool(problems))
        if problems:
            self.notes.setText(f"{len(problems)} warning{'' if len(problems) == 1 else 's'}")

    # Navigation from inside documents

    def _element_clicked(self, element_id: str) -> None:
        target = nav.target_of_element(self.analysis, element_id) if self.analysis else None
        if target is not None and target != self.target:
            self.open(target)

    def _link_clicked(self, address: str) -> None:
        name = diagram_name(address)
        if name is not None:
            self.open(Target(DIAGRAM, name))
        elif "://" in address or address.startswith("mailto:"):
            self.external_link_requested.emit(address)
        elif self.target is not None and self.target.kind == PAGE:
            path = normpath(f"{dirname(self.target.name)}/{address.partition('#')[0]}")
            self.open(Target(PAGE, path))

    # Language, theme, zoom and export menus

    def _show_language(self, analysis: Analysis) -> None:
        chosen = analysis.config.language
        detected = LANGUAGE_NAMES.get(analysis.detected_language, analysis.detected_language)
        current = LANGUAGE_NAMES.get(chosen, chosen) if chosen else f"automatic ({detected})"
        self.language.setToolTip(f"Language of the documents: {current}")

    def language_choices(self) -> list[tuple[str, object, bool]]:
        """(text, value, whether it is the current choice) for the language menu."""
        if self.analysis is None:
            return []
        detected = LANGUAGE_NAMES.get(self.analysis.detected_language, self.analysis.detected_language)
        chosen = self.analysis.config.language
        choices = [(f"Auto  ({detected})", None, chosen is None)]
        return choices + [(name, code, chosen == code) for code, name in LANGUAGE_NAMES.items()]

    def _language_menu(self) -> None:
        popup = menu(self)
        for text, value, current in self.language_choices():
            action = popup.addAction(text)
            action.setCheckable(True)
            action.setChecked(current)
            action.triggered.connect(lambda _=False, v=value: self.language_changed.emit(v))
        popup.exec(self.language.mapToGlobal(self.language.rect().bottomLeft()))

    def _theme_menu(self) -> None:
        popup = menu(self)
        for mode, text in ((SYSTEM, "Follow the system"), (LIGHT, "Light"), (DARK, "Dark")):
            action = popup.addAction(text)
            action.setCheckable(True)
            action.setChecked(self._themes.mode == mode)
            action.triggered.connect(lambda _=False, m=mode: self._themes.set_mode(m))
        popup.exec(self.theme_button.mapToGlobal(self.theme_button.rect().bottomLeft()))

    def _zoom_menu(self) -> None:
        popup = menu(self)
        popup.addAction("Fit width").triggered.connect(lambda: self.canvas.fit(canvas_module.FIT_WIDTH))
        popup.addAction("Fit whole diagram").triggered.connect(lambda: self.canvas.fit(canvas_module.FIT_ALL))
        popup.addSeparator()
        for percent in (50, 75, 100, 150, 200, 400):
            popup.addAction(f"{percent}%").triggered.connect(lambda _=False, p=percent: self.canvas.zoom_to(p / 100))
        popup.exec(self.zoom_level.mapToGlobal(self.zoom_level.rect().bottomLeft()))

    def export_actions(self) -> list[tuple[str, str, bool]]:
        """(text, what it does, whether it is available now) for the export menu."""
        diagram = self.target is not None and self.target.kind == DIAGRAM
        return [
            ("Documentation as a zip…\tCtrl+E", "zip", True),
            ("-", "", True),
            ("This diagram as SVG…", "svg", diagram),
            ("This diagram as PNG…", "png", diagram),
            ("Copy this diagram as an image\tCtrl+Shift+C", "copy-diagram", diagram),
            ("Copy this page as Markdown", "copy-page", not diagram),
        ]

    def run_export_action(self, key: str) -> None:
        {"zip": self.export_requested.emit, "svg": lambda: self.save_diagram_requested.emit("svg"),
         "png": lambda: self.save_diagram_requested.emit("png"), "copy-diagram": self.copy_diagram_requested.emit,
         "copy-page": self.copy_page_requested.emit}[key]()

    def _export_menu(self) -> None:
        popup = menu(self)
        for text, key, enabled in self.export_actions():
            if text == "-":
                popup.addSeparator()
                continue
            action = popup.addAction(text)
            action.setEnabled(enabled)
            action.triggered.connect(lambda _=False, k=key: self.run_export_action(k))
        popup.exec(self.export.mapToGlobal(self.export.rect().bottomLeft()))

    def _show_zoom(self, scale: float) -> None:
        self.zoom_level.setText(f"{round(scale * 100)}%")

    # Find, sidebar, busy state

    def open_find(self) -> None:
        if self.target is not None and self.target.kind == DIAGRAM:
            self.find_bar.open()
            self._place_find_bar()

    def toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def set_busy(self, text: str | None) -> None:
        """Show what is running, and keep the user from starting something else meanwhile."""
        self._busy = text is not None
        self.spinner.setVisible(self._busy)
        self.activity_slot.setCurrentIndex(1 if self._busy else 0)
        self.status.setText(text if text else (HINTS[self.target.kind] if self.target else ""))
        for control in (self.export, self.edit, self.language):
            control.setEnabled(not self._busy)

    def is_busy(self) -> bool:
        return self._busy

    # Events

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.views and event.type() == QEvent.Type.Resize:
            self._place_find_bar()
        return False

    def _place_find_bar(self) -> None:
        self.find_bar.adjustSize()
        self.find_bar.move(self.views.width() - self.find_bar.width() - 16, 12)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_compact()

    def _apply_compact(self) -> None:
        """In a narrow window the buttons keep their icons and give their words back to the title."""
        compact = self.width() < COMPACT_BELOW
        for button, text in self._labelled:
            button.setText("" if compact else text)
        self.kind.setVisible(self.width() >= ROOMY_FROM)
        # Below this even the icons crowd each other: the two with a key of their own (0 and F11) step aside.
        for button in (self.fit_button, self.fullscreen_button):
            button.setVisible(self.width() >= TIGHT_BELOW)

    def _theme_changed(self, *_) -> None:
        self.theme_button.set_icon("sun" if self._themes.is_dark else "moon")
        if self.target is not None and self.analysis is not None:
            self.open(self.target, keep_view=True)


def _element_ids(bundle: Bundle) -> set[str]:
    """Every id carried by a card of any diagram of the bundle."""
    found: set[str] = set()
    for path, content in bundle.items():
        if path.endswith("-light.svg"):
            found.update(re.findall(r' id="([^"]+)"', str(content)))
    return found
