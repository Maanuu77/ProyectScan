import subprocess
import sys
import textwrap
import threading
import time
import zipfile
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, QSettings, QThread, Qt, QUrl
from PySide6.QtGui import QDropEvent, QGuiApplication, QImage

from repo_xray.app import navigation as nav
from repo_xray.app.navigation import DIAGRAM, PAGE, Target
from repo_xray.app.pages.analysis import DONE, PENDING, RUNNING, AnalysisPage
from repo_xray.app.texts_dialog import TextsDialog
from repo_xray.app.theme import DARK, LIGHT, PALETTES, SYSTEM, Themes
from repo_xray.app.window import MainWindow
from repo_xray.app.workers import ANALYSIS_STAGES, Task, analysis_task
from repo_xray.config import FeatureText
from repo_xray.export.markdown import diagram_path, feature_page
from repo_xray.pipeline import Progress
from repo_xray.render import ids
from tests.conftest import hexagonal_backend, write

TIMEOUT = 30_000
ORDERS_PAGE = Target(PAGE, feature_page("api/order"))
ORDERS_FLOW = Target(DIAGRAM, "flow-post-api-orders")


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def themes(settings):
    manager = Themes(settings)
    manager.set_mode(LIGHT)
    yield manager
    manager.set_mode(SYSTEM)  # leave the application as it was found


@pytest.fixture
def window(qtbot, themes, settings):
    win = MainWindow(themes, settings)
    qtbot.addWidget(win)
    return win


@pytest.fixture
def project(tmp_path):
    folder = tmp_path / "shop"
    hexagonal_backend(folder)
    return folder


def finish(qtbot, window, signal: str = "finished"):
    """Wait for the window's running task to end; the window has handled it when this returns."""
    task = window.task
    assert task is not None
    with qtbot.waitSignal(getattr(task, signal), timeout=TIMEOUT):
        pass
    return task


def analysed(qtbot, window, project):
    window.analyse(project)
    finish(qtbot, window)
    return window


def endless_task(started: threading.Event) -> Task:
    """A task that only ends by being cancelled."""

    def work(job):
        started.set()
        while True:
            job.check()
            time.sleep(0.005)

    return Task(work)


# Background tasks


def test_task_reports_on_the_thread_that_created_it(qtbot):
    seen = {}

    def work(job):
        seen["worker"] = QThread.currentThread()
        job.report(Progress("parse", 1, 2))
        return 42

    task = Task(work)
    task.progress.connect(lambda progress: seen.setdefault("progress", progress))
    task.finished.connect(lambda result: seen.update(result=result, slot=QThread.currentThread()))
    with qtbot.waitSignal(task.finished, timeout=TIMEOUT):
        task.start()
    task.wait()

    assert seen["result"] == 42
    assert seen["progress"] == Progress("parse", 1, 2)
    assert seen["worker"] is not seen["slot"]
    assert seen["slot"] is QThread.currentThread()  # slots may touch widgets safely


def test_task_failure_is_reported_not_raised(qtbot):
    task = Task(lambda job: 1 / 0)

    with qtbot.waitSignal(task.failed, timeout=TIMEOUT) as blocker:
        task.start()
    task.wait()

    assert blocker.args[0].startswith("ZeroDivisionError")


def test_task_stops_when_cancelled(qtbot):
    started = threading.Event()
    outcome = []
    task = endless_task(started)
    task.finished.connect(lambda result: outcome.append("finished"))
    task.failed.connect(lambda error: outcome.append("failed"))
    with qtbot.waitSignal(task.cancelled, timeout=TIMEOUT):
        task.start()
        assert started.wait(TIMEOUT / 1000)
        task.cancel()
    task.wait()

    assert outcome == [] and task.is_cancelling()


def test_dropping_a_task_right_after_it_finishes_does_not_crash():
    # Qt aborts the process when a running QThread is destroyed, so the check runs in its own process.
    script = textwrap.dedent("""
        import gc
        from PySide6.QtCore import QEventLoop
        from PySide6.QtWidgets import QApplication
        from repo_xray.app.workers import Task

        app = QApplication([])
        for _ in range(100):
            task = Task(lambda job: sum(range(2000)))
            loop = QEventLoop()
            task.finished.connect(lambda _: loop.quit())
            task.start()
            loop.exec()
            del task  # what the window does when it starts the next task
            gc.collect()
        print("ok")
    """)

    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120,
                            cwd=Path(__file__).resolve().parent.parent)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


# From the start page to the workspace


def test_the_app_opens_on_the_start_page(qtbot, window):
    assert window.pages.currentWidget() is window.start
    assert window.windowTitle() == "repo-xray"
    assert window.start.recent_rows() == []

    window.show()
    qtbot.waitExposed(window)
    assert window.focusWidget() is window.start.choose  # Enter chooses a folder


def test_analysis_opens_the_workspace_on_the_overview(qtbot, window, project):
    analysed(qtbot, window, project)

    workspace = window.workspace
    assert window.pages.currentWidget() is workspace
    assert window.windowTitle() == "shop — repo-xray"
    assert workspace.target == nav.OVERVIEW_DIAGRAM
    assert workspace.views.currentWidget() is workspace.canvas and workspace.canvas.has_diagram()
    assert workspace.title.full_text() == "Architecture" and workspace.levels.current() == "1"
    assert workspace.sidebar.header.name.full_text() == "shop"
    assert "2 features" in workspace.facts.text() and "2 flows" in workspace.facts.text()


def test_the_keyboard_goes_to_the_diagram_when_the_results_open(qtbot, window, project):
    window.show()
    qtbot.waitExposed(window)
    analysed(qtbot, window, project)

    assert window.focusWidget() is window.workspace.canvas  # + and - zoom at once, without a click


def test_the_sidebar_lists_every_document_by_level(qtbot, window, project):
    analysed(qtbot, window, project)

    assert window.workspace.sidebar.titles() == [
        "Overview", "Architecture", "Summary", "Analysis report",
        "Features", "Feature map", "api", "Catalog", "Orders",
        "Flows", "Key flows", "POST /api/orders", "GET /api/products",
    ]
    assert window.workspace.sidebar.current() == nav.OVERVIEW_DIAGRAM


def test_choosing_a_page_in_the_sidebar_shows_it(qtbot, window, project):
    analysed(qtbot, window, project)
    workspace = window.workspace
    row = workspace.sidebar.titles().index("Orders")

    workspace.sidebar.list.setCurrentRow(row)

    assert workspace.target == ORDERS_PAGE
    assert workspace.views.currentWidget() is workspace.page
    assert "Checkout and order history" in workspace.page.toPlainText()
    assert workspace.levels.current() == "2" and not workspace.zoom_group.isVisibleTo(workspace)


def test_level_tabs_lead_to_each_level_and_follow_the_document(qtbot, window, project):
    analysed(qtbot, window, project)
    workspace = window.workspace

    workspace.levels.button("2").click()
    assert workspace.target == nav.FEATURES_DIAGRAM
    workspace.levels.button("3").click()
    assert workspace.target == ORDERS_FLOW and workspace.title.full_text() == "POST /api/orders"
    workspace.open(nav.SUMMARY_PAGE)
    assert workspace.levels.current() == "1"
    assert workspace.open(Target(PAGE, "architecture/missing.md")) is False  # nothing changes
    assert workspace.target == nav.SUMMARY_PAGE


def test_the_next_and_previous_documents_follow_the_sidebar(qtbot, window, project):
    analysed(qtbot, window, project)
    workspace = window.workspace

    workspace.open_neighbour(1)
    assert workspace.target == nav.SUMMARY_PAGE
    workspace.open_neighbour(-1)
    workspace.open_neighbour(-1)  # already at the first: stays
    assert workspace.target == nav.OVERVIEW_DIAGRAM


def test_filter_narrows_the_sidebar_and_keeps_the_document(qtbot, window, project):
    analysed(qtbot, window, project)
    workspace = window.workspace

    workspace.sidebar.filter.setText("products")

    assert workspace.sidebar.titles() == ["Flows", "Key flows", "GET /api/products"]
    assert workspace.target == nav.OVERVIEW_DIAGRAM  # filtering does not navigate
    workspace.sidebar.filter.setText("zzz")
    assert workspace.sidebar.titles() == [] and not workspace.sidebar.empty.isHidden()
    workspace.sidebar.filter.clear()
    assert len(workspace.sidebar.titles()) == 13 and workspace.sidebar.current() == nav.OVERVIEW_DIAGRAM


# Themes


def test_switching_theme_redraws_the_document_in_place(qtbot, window, project, themes):
    analysed(qtbot, window, project)
    workspace = window.workspace
    workspace.open(ORDERS_FLOW)
    workspace.canvas.zoom_to(2.0)

    themes.set_mode(DARK)

    assert workspace.canvas._background.name() == PALETTES[DARK].canvas == "#0d1117"
    assert workspace.target == ORDERS_FLOW and workspace.canvas.scale == 2.0  # same place, same zoom
    assert workspace.theme_button.icon_name == "sun" and window.start.theme_button.icon_name == "sun"
    themes.toggle()
    assert workspace.canvas._background.name() == PALETTES[LIGHT].canvas


def test_the_theme_is_remembered(qtbot, window, themes, settings):
    themes.set_mode(DARK)

    assert Themes(settings).mode == DARK


# Recent projects


def test_an_analysed_project_is_remembered_with_what_was_found(qtbot, window, project):
    analysed(qtbot, window, project)

    remembered = window.recent.all()[0]
    assert Path(remembered.path) == project and remembered.title == "shop"
    assert (remembered.apps, remembered.features, remembered.flows) == (1, 2, 2)

    window.close_project()
    rows = window.start.recent_rows()
    assert window.pages.currentWidget() is window.start and window.analysis is None
    assert [row.title.full_text() for row in rows] == ["shop"]
    assert "1 app" in rows[0].details.text() and "just now" in rows[0].details.text()


def test_a_recent_row_opens_its_project_and_can_be_removed(qtbot, window, project):
    analysed(qtbot, window, project)
    window.close_project()
    row = window.start.recent_rows()[0]

    qtbot.mouseClick(row, Qt.MouseButton.LeftButton, pos=QPoint(40, 10))
    finish(qtbot, window)
    assert window.pages.currentWidget() is window.workspace

    window.close_project()
    window.start.recent_rows()[0].remove.click()
    assert window.start.recent_rows() == [] and window.recent.all() == []


def test_the_project_menu_offers_the_other_recent_projects(qtbot, window, project, tmp_path):
    other = tmp_path / "other"
    write(other, {"pyproject.toml": '[project]\nname = "other"\n', "tool.py": "x = 1\n"})
    analysed(qtbot, window, other)
    analysed(qtbot, window, project)

    texts = [text for text, _ in window.project_actions()]

    assert texts[:3] == ["Open another folder…\tCtrl+O", "Analyse again\tF5", "Show in file manager"]
    assert any(text.startswith("other  —  ") for text in texts)
    assert not any(text.startswith("shop  —  ") for text in texts)  # the open project is not offered again
    assert texts[-1] == "Close project"


def test_a_folder_dropped_anywhere_on_the_window_is_analysed(qtbot, window, project):
    data = QMimeData()
    data.setUrls([QUrl.fromLocalFile(str(project))])
    event = QDropEvent(QPointF(50, 50), Qt.DropAction.CopyAction, data, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier)

    window.dropEvent(event)
    finish(qtbot, window)

    assert window.pages.currentWidget() is window.workspace and window.folder == project


# The analysis page


def test_the_analysis_page_shows_stages_and_real_counts(qtbot, themes, tmp_path):
    page = AnalysisPage(themes)
    qtbot.addWidget(page)

    page.start(tmp_path / "shop")
    assert set(page.stage_states().values()) == {PENDING} and list(page.stage_states()) == list(ANALYSIS_STAGES)
    assert page.heading.full_text() == "Analysing shop"

    page.show_progress(Progress("scan"))
    page.show_progress(Progress("parse", 30, 120, "api/src/Order.java"))
    states = page.stage_states()
    assert (states["scan"], states["parse"], states["stack"]) == (DONE, RUNNING, PENDING)
    assert page.rows["parse"].count.text() == "30 of 120 files"
    assert (page.bar.value(), page.bar.maximum()) == (30, 120)
    assert page.detail.full_text() == "api/src/Order.java"

    page.show_progress(Progress("features"))
    states = page.stage_states()
    assert states["parse"] == states["calls"] == DONE and states["features"] == RUNNING
    assert page.rows["features"].count.text() == ""  # nothing to count: no number is shown
    assert page.rows["parse"].count.text() == "30 of 120 files"  # what was counted stays
    page.show_progress(Progress("render"))
    assert page.stage_states()["texts"] == DONE and page.stage_states()["render"] == RUNNING


def test_a_failed_analysis_is_explained_in_place(qtbot, window, project):
    (project / "xray.toml").write_text("language = \n", encoding="utf-8")

    window.analyse(project)
    finish(qtbot, window, "failed")

    assert window.pages.currentWidget() is window.analysing  # no dialog, and not back to the start
    title, text = window.analysing.problem()
    assert title == "xray.toml could not be read" and "Fix or delete the file" in text
    assert window.analysing.problem_detail.text() and not window.analysing.retry.isHidden()

    (project / "xray.toml").unlink()
    window.analysing.retry.click()
    finish(qtbot, window)
    assert window.pages.currentWidget() is window.workspace


def test_a_folder_that_does_not_exist_is_explained_without_starting(qtbot, window, tmp_path):
    window.analyse(tmp_path / "missing")

    assert window.task is None
    title, _ = window.analysing.problem()
    assert title == "This folder cannot be opened"
    assert str(tmp_path / "missing") in window.analysing.problem_detail.text()
    window.analysing.back.click()
    assert window.pages.currentWidget() is window.start


def test_a_folder_without_code_says_what_is_missing(qtbot, window, tmp_path):
    empty = tmp_path / "notes"
    write(empty, {"README.md": "# Notes\n", "todo.txt": "nothing\n"})

    window.analyse(empty)
    finish(qtbot, window)

    assert window.pages.currentWidget() is window.analysing and window.analysis is None
    title, text = window.analysing.problem()
    assert title == "No source files found in notes" and "Python, Java, TypeScript" in text
    assert window.analysing.retry.isHidden()  # trying again would find the same
    assert window.recent.all() == []  # not worth remembering


def test_cancelling_an_analysis_returns_to_the_start(qtbot, window, project, monkeypatch):
    started = threading.Event()
    monkeypatch.setattr("repo_xray.app.window.analysis_task", lambda folder, cache: endless_task(started))
    window.analyse(project)
    assert started.wait(TIMEOUT / 1000) and window.analysing.is_running()

    window.analysing.cancel.click()
    assert not window.analysing.cancel.isEnabled()  # asked once: it says it is stopping
    finish(qtbot, window, "cancelled")

    assert window.pages.currentWidget() is window.start and window.task is None


def test_cancelling_over_earlier_results_goes_back_to_them(qtbot, window, project, tmp_path, monkeypatch):
    analysed(qtbot, window, project)
    started = threading.Event()
    monkeypatch.setattr("repo_xray.app.window.analysis_task", lambda folder, cache: endless_task(started))
    window.analyse(tmp_path)
    assert started.wait(TIMEOUT / 1000)

    window.cancel()
    finish(qtbot, window, "cancelled")

    assert window.pages.currentWidget() is window.workspace and window.folder == project


def test_a_newer_analysis_replaces_the_one_that_is_running(qtbot, window, project, tmp_path, monkeypatch):
    started = threading.Event()
    tasks = [endless_task(started)]
    monkeypatch.setattr("repo_xray.app.window.analysis_task",
                        lambda folder, cache: tasks.pop() if tasks else analysis_task(folder, cache))
    window.analyse(tmp_path)
    first = window.task
    assert started.wait(TIMEOUT / 1000)

    window.analyse(project)  # the first one is told to stop and its outcome is ignored
    finish(qtbot, window)
    first.wait()

    assert first.is_cancelling()
    assert window.pages.currentWidget() is window.workspace and window.analysis.root == project


# Texts and language


def test_texts_dialog_shows_found_texts_as_hints(qtbot, window, project, themes):
    analysed(qtbot, window, project)
    dialog = TextsDialog(window.analysis, themes, window)
    qtbot.addWidget(dialog)

    row = dialog.rows["api/order"]
    assert list(dialog.rows) == ["api/catalog", "api/order"]
    assert row.name.text() == "" and row.name.placeholderText() == "Orders"
    assert row.description.placeholderText() == "Checkout and order history"
    assert row.source.text() == "From the code"
    assert dialog.feature_texts() == {} and dialog.project_description() is None  # nothing typed, nothing saved
    assert dialog.counter.text() == "0 of 2 in your words" and not row.reset.isEnabled()

    row.name.setText("  Purchases ")
    dialog.description.setPlainText("A small shop\nfor good things ")
    assert dialog.feature_texts() == {"api/order": FeatureText(name="Purchases")}
    assert dialog.project_description() == "A small shop for good things"
    assert dialog.counter.text() == "1 of 2 in your words"
    assert row.name.property("edited") is True and row.description.property("edited") is False


def test_texts_dialog_filters_and_puts_a_feature_back(qtbot, window, project, themes):
    analysed(qtbot, window, project)
    dialog = TextsDialog(window.analysis, themes, window)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.rows["api/order"].description.setText("Buying things")

    dialog.filter.setText("catal")
    assert dialog.visible_keys() == ["api/catalog"]
    dialog.filter.setText("buying")  # the user's own words are searched too
    assert dialog.visible_keys() == ["api/order"]
    dialog.filter.clear()
    dialog.scope.button("edited").click()
    assert dialog.visible_keys() == ["api/order"]
    dialog.filter.setText("nothing")
    assert dialog.visible_keys() == [] and not dialog.nothing.isHidden()

    dialog.filter.clear()
    dialog.rows["api/order"].reset.click()
    assert dialog.feature_texts() == {} and dialog.visible_keys() == []  # nothing is "in your words" any more


def test_saved_texts_come_back_as_values_and_generated_ones_are_marked(qtbot, window, project, themes):
    write(project, {"xray.toml": 'description = "A shop"\n\n[features."api/order"]\nname = "Purchases"\n'
                                 'description = "Buying"\n'})
    analysed(qtbot, window, project)
    dialog = TextsDialog(window.analysis, themes, window)
    qtbot.addWidget(dialog)

    order, catalog = dialog.rows["api/order"], dialog.rows["api/catalog"]
    assert (order.name.text(), order.description.text(), order.source.text()) == ("Purchases", "Buying", "Yours")
    assert order.name.placeholderText() == "Orders"  # what was found stays as the hint
    assert dialog.description.toPlainText() == "A shop"
    assert catalog.source.text() in ("From the code", "Written by repo-xray")
    assert dialog.feature_texts() == {"api/order": FeatureText(name="Purchases", description="Buying")}


def test_saving_texts_refreshes_the_documents_in_place(qtbot, window, project):
    analysed(qtbot, window, project)
    workspace = window.workspace
    workspace.open(nav.FEATURES_DIAGRAM)

    window._save_and_refresh("es", "Una tienda pequeña", {"api/order": FeatureText(name="Compras")})
    assert window.pages.currentWidget() is workspace  # no progress screen for a refresh
    assert workspace.is_busy() and not workspace.edit.isEnabled() and not workspace.export.isEnabled()
    assert workspace.status.full_text() == "Updating the documents…"
    finish(qtbot, window)

    assert window.analysis.language == "es"
    assert window.analysis.stack.description == "Una tienda pequeña"
    assert "Compras" in [f.name for f in window.analysis.features.features]
    assert workspace.target == nav.FEATURES_DIAGRAM  # the reader stays where they were
    assert "Compras" in workspace.sidebar.titles()
    assert not workspace.is_busy() and workspace.edit.isEnabled()
    assert 'name = "Compras"' in (project / "xray.toml").read_text(encoding="utf-8")
    assert window.cache.hits > 0  # the refresh did not read the files again


def test_language_menu_offers_auto_and_both_languages(qtbot, window, project):
    analysed(qtbot, window, project)
    workspace = window.workspace

    assert workspace.language_choices() == [("Auto  (English)", None, True), ("English", "en", False),
                                            ("Español", "es", False)]
    assert workspace.language.toolTip() == "Language of the documents: automatic (English)"

    workspace.language_changed.emit("es")
    finish(qtbot, window)

    assert [current for _, _, current in workspace.language_choices()] == [False, False, True]
    assert workspace.language.toolTip() == "Language of the documents: Español"
    workspace.language_changed.emit("es")  # already Spanish: nothing to do
    assert window.task is None


def test_a_refresh_that_fails_keeps_the_documents_and_says_why(qtbot, window, project):
    analysed(qtbot, window, project)
    (project / "xray.toml").write_text("language = \n", encoding="utf-8")

    window.analyse_again()
    finish(qtbot, window, "failed")

    assert window.pages.currentWidget() is window.workspace and not window.workspace.is_busy()
    toast = window.toasts.current()[-1]
    assert toast.tone == "error" and "could not be updated" in toast.message


# Export


def test_export_writes_the_zip_and_says_so(qtbot, window, project, tmp_path):
    analysed(qtbot, window, project)
    destination = tmp_path / "out" / "shop-architecture.zip"

    window.export(destination)
    assert window.workspace.is_busy() and not window.workspace.export.isEnabled()
    finish(qtbot, window)

    assert not window.workspace.is_busy() and window.workspace.export.isEnabled()
    toast = window.toasts.current()[-1]
    assert toast.tone == "success" and "shop-architecture.zip" in toast.message
    assert toast.action is not None and toast.action.text() == "Show in folder"
    with zipfile.ZipFile(destination) as archive:
        assert "architecture/README.md" in archive.namelist()


def test_export_menu_offers_what_fits_the_document(qtbot, window, project):
    analysed(qtbot, window, project)
    workspace = window.workspace

    on_diagram = {key: enabled for _, key, enabled in workspace.export_actions() if key}
    workspace.open(nav.SUMMARY_PAGE)
    on_page = {key: enabled for _, key, enabled in workspace.export_actions() if key}

    assert on_diagram == {"zip": True, "svg": True, "png": True, "copy-diagram": True, "copy-page": False}
    assert on_page == {"zip": True, "svg": False, "png": False, "copy-diagram": False, "copy-page": True}


def test_the_diagram_on_show_is_saved_as_svg_or_png(qtbot, window, project, tmp_path, themes):
    analysed(qtbot, window, project)
    window.workspace.open(ORDERS_FLOW)
    themes.set_mode(DARK)

    assert window.save_diagram(tmp_path / "exports" / "flow.svg")
    assert window.save_diagram(tmp_path / "exports" / "flow.png")

    svg = (tmp_path / "exports" / "flow.svg").read_text(encoding="utf-8")
    assert svg.startswith("<svg") and "#0d1117" in svg and "OrderController" in svg  # the theme on screen
    image = QImage(str(tmp_path / "exports" / "flow.png"))
    assert not image.isNull() and image.pixelColor(2, 2).name() == "#0d1117"
    assert [toast.message for toast in window.toasts.current()][-1] == "Diagram saved as flow.png."

    window.workspace.open(nav.SUMMARY_PAGE)
    assert window.save_diagram(tmp_path / "exports" / "page.svg") is False  # a page is not a diagram


def test_copying_puts_the_diagram_or_the_page_on_the_clipboard(qtbot, window, project):
    analysed(qtbot, window, project)
    clipboard = QGuiApplication.clipboard()
    clipboard.clear()

    assert window.copy_diagram() and not window.copy_page()
    assert not clipboard.image().isNull()

    window.workspace.open(ORDERS_PAGE)
    assert window.copy_page() and not window.copy_diagram()
    assert clipboard.text().startswith("# Orders")


# Moving around from inside the documents


def test_clicking_a_card_of_a_diagram_opens_what_it_stands_for(qtbot, window, project):
    analysed(qtbot, window, project)
    workspace = window.workspace
    workspace.open(nav.FEATURES_DIAGRAM)

    workspace.canvas.element_clicked.emit(ids.feature_id("api/order"))
    assert workspace.target == ORDERS_PAGE

    workspace.open(ORDERS_FLOW)
    workspace.canvas.element_clicked.emit(ids.step_id(1, "api/order"))  # a step leads to its feature
    assert workspace.target == ORDERS_PAGE

    workspace.open(nav.OVERVIEW_DIAGRAM)
    workspace.canvas.element_clicked.emit(ids.app_id("api"))
    assert workspace.target == nav.FEATURES_DIAGRAM


def test_only_cards_that_lead_somewhere_react_to_the_pointer(qtbot, window, project):
    analysed(qtbot, window, project)
    canvas = window.workspace.canvas
    window.workspace.open(nav.FEATURES_DIAGRAM)

    assert canvas._clickable == {ids.feature_id("api/order"), ids.feature_id("api/catalog")}
    assert ids.app_id("api") in canvas.element_ids()  # it would lead to this same diagram: it does not react

    window.workspace.open(nav.OVERVIEW_DIAGRAM)
    assert canvas._clickable == {ids.app_id("api")}
    window.workspace.open(ORDERS_FLOW)
    assert ids.step_id(1, "api/order") in canvas._clickable


def test_diagrams_are_drawn_when_they_are_opened_not_before(qtbot, window, project):
    analysed(qtbot, window, project)
    bundle = window.workspace.bundle
    flow = diagram_path("flow-post-api-orders", "light")

    assert bundle.is_written(diagram_path("overview", "light")) and bundle.is_written(diagram_path("features", "dark"))
    assert flow in bundle and not bundle.is_written(flow)  # listed, not drawn

    window.workspace.open(ORDERS_FLOW)

    assert bundle.is_written(flow)
    assert not bundle.is_written(diagram_path("flow-post-api-orders", "dark"))  # the other theme can wait
    assert not bundle.is_written(diagram_path("flow-get-api-products", "light"))


def test_links_of_a_page_lead_to_other_documents(qtbot, window, project):
    analysed(qtbot, window, project)
    workspace = window.workspace
    external = []
    workspace.external_link_requested.connect(external.append)

    workspace.open(ORDERS_PAGE)
    workspace.page.link_clicked.emit("../README.md")
    assert workspace.target == nav.SUMMARY_PAGE

    workspace.page.link_clicked.emit("features/api-order.md")
    assert workspace.target == ORDERS_PAGE
    workspace.page.link_clicked.emit("diagram:flow-post-api-orders")
    assert workspace.target == ORDERS_FLOW and workspace.views.currentWidget() is workspace.canvas

    workspace.open(nav.REPORT_PAGE)
    assert "Analysis report" in workspace.page.toPlainText() and workspace.title.full_text() == "Analysis report"
    workspace.page.link_clicked.emit("https://example.com/docs")
    assert external == ["https://example.com/docs"] and workspace.target == nav.REPORT_PAGE


def test_pages_show_their_diagrams_in_the_current_theme(qtbot, window, project, themes):
    analysed(qtbot, window, project)
    workspace = window.workspace
    workspace.open(ORDERS_PAGE)

    light = workspace.page._diagram_image("flow-post-api-orders")
    themes.set_mode(DARK)
    dark = workspace.page._diagram_image("flow-post-api-orders")

    assert not light.isNull() and light.pixelColor(1, 1).name() == "#ffffff"
    assert dark.pixelColor(1, 1).name() == "#0d1117"


def test_find_counts_matches_in_the_diagram_and_closes_clean(qtbot, window, project):
    analysed(qtbot, window, project)
    workspace = window.workspace
    window.show()
    workspace.open(ORDERS_FLOW)

    workspace.open_find()
    workspace.find_bar.field.setText("order")
    assert not workspace.find_bar.isHidden() and workspace.canvas.match_count() >= 2
    assert workspace.find_bar.count.text().startswith("1 of ")
    workspace.find_bar.next.click()
    assert workspace.find_bar.count.text().startswith("2 of ")
    workspace.find_bar.field.setText("zzzz")
    assert workspace.find_bar.count.text() == "No matches"

    workspace.open(nav.SUMMARY_PAGE)  # a page has nothing to find in: the bar goes away
    assert workspace.find_bar.isHidden() and workspace.canvas.match_count() == 0
    workspace.open_find()
    assert workspace.find_bar.isHidden()


# The window


def test_shortcuts_act_on_the_workspace_only(qtbot, window, project):
    window.shortcuts["Ctrl+2"].activated.emit()  # on the start page: nothing to do, and no error
    assert window.pages.currentWidget() is window.start

    analysed(qtbot, window, project)
    workspace = window.workspace
    window.shortcuts["Ctrl+2"].activated.emit()
    assert workspace.target == nav.FEATURES_DIAGRAM
    window.shortcuts["Ctrl+3"].activated.emit()
    assert workspace.target == ORDERS_FLOW
    window.shortcuts["Ctrl+PgDown"].activated.emit()
    assert workspace.target == Target(DIAGRAM, "flow-get-api-products")
    window.shortcuts["Ctrl+1"].activated.emit()
    assert workspace.target == nav.OVERVIEW_DIAGRAM
    before = workspace.canvas.scale
    window.shortcuts["Ctrl+="].activated.emit()
    assert workspace.canvas.scale > before
    window.shortcuts["Ctrl+0"].activated.emit()
    assert workspace.canvas.fit_mode == "width"


def test_the_sidebar_can_step_aside_and_full_screen_gives_it_back(qtbot, window, project):
    analysed(qtbot, window, project)
    window.show()
    sidebar = window.workspace.sidebar
    assert sidebar.isVisible()

    window.shortcuts["Ctrl+B"].activated.emit()
    assert not sidebar.isVisible()
    window.shortcuts["Ctrl+K"].activated.emit()  # the filter lives in the sidebar: it comes back
    assert sidebar.isVisible()

    window.toggle_fullscreen()
    assert window.isFullScreen() and not sidebar.isVisible()
    assert window.workspace.fullscreen_button.icon_name == "collapse"
    window.shortcuts["Esc"].activated.emit()
    assert not window.isFullScreen() and sidebar.isVisible()


def test_a_narrow_window_keeps_icons_and_drops_words(qtbot, window, project):
    analysed(qtbot, window, project)
    window.show()
    workspace = window.workspace

    window.resize(1400, 800)
    assert (workspace.edit.text(), workspace.export.text()) == ("Edit texts", "Export")
    assert workspace.fit_button.isVisible()
    window.resize(960, 640)
    assert (workspace.edit.text(), workspace.export.text()) == ("", "")
    assert workspace.edit.toolTip() and not workspace.fit_button.isVisible()
    assert workspace.levels.button("1").text() == "Overview"  # the levels always say their names


def test_the_window_remembers_the_sidebar_width(qtbot, window, project, themes, settings):
    analysed(qtbot, window, project)
    window.show()
    window.workspace.splitter.setSizes([340, 900])
    width = window.workspace.splitter.sizes()[0]

    window.close()
    again = MainWindow(themes, settings)
    qtbot.addWidget(again)
    analysed(qtbot, again, project)
    again.show()

    assert again.workspace.splitter.sizes()[0] == pytest.approx(width, abs=30)
