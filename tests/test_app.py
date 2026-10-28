import zipfile

import pytest
from PySide6.QtCore import QSettings, QThread, Qt

from repo_xray.app.preview import DiagramView, PageView
from repo_xray.app.window import MAX_RECENT, MainWindow
from repo_xray.app.workers import Task
from repo_xray.render.theme import LIGHT
from tests.conftest import hexagonal_backend

TIMEOUT = 30_000


@pytest.fixture
def window(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    win = MainWindow(LIGHT, settings)
    qtbot.addWidget(win)
    return win


@pytest.fixture
def project(tmp_path):
    folder = tmp_path / "shop"
    hexagonal_backend(folder)
    return folder


def analysed(qtbot, window, project):
    window.analyse(project)
    with qtbot.waitSignal(window.task.finished, timeout=TIMEOUT):
        pass
    return window


def test_task_reports_on_the_thread_that_created_it(qtbot):
    seen = {}

    def work(report):
        seen["worker"] = QThread.currentThread()
        report("halfway", 0.5)
        return 42

    task = Task(work)
    task.progress.connect(lambda message, fraction: seen.setdefault("progress", (message, fraction)))
    task.finished.connect(lambda result: seen.update(result=result, slot=QThread.currentThread()))
    with qtbot.waitSignal(task.finished, timeout=TIMEOUT):
        task.start()
    task.wait()

    assert seen["result"] == 42
    assert seen["progress"] == ("halfway", 0.5)
    assert seen["worker"] is not seen["slot"]
    assert seen["slot"] is QThread.currentThread()  # slots may touch widgets safely


def test_task_failure_is_reported_not_raised(qtbot):
    task = Task(lambda report: 1 / 0)

    with qtbot.waitSignal(task.failed, timeout=TIMEOUT) as blocker:
        task.start()
    task.wait()

    assert blocker.args[0].startswith("ZeroDivisionError")


def test_analysis_shows_diagrams_and_pages(qtbot, window, project):
    analysed(qtbot, window, project)

    assert window.pages.currentWidget() is window.results
    assert window.results.title.text() == "shop"
    entries = [window.results.documents.item(i).text() for i in range(window.results.documents.count())]
    assert entries[:3] == ["DIAGRAMS", "What is it made of?", "What does it do?"]
    assert "Orders  ·  api" in entries and "Architecture overview" in entries
    assert window.results.views.currentWidget() is window.results.diagram

    window.results.documents.setCurrentRow(entries.index("Orders  ·  api"))
    assert window.results.views.currentWidget() is window.results.page
    assert "Checkout and order history" in window.results.page.toPlainText()


def test_light_and_dark_previews(qtbot, window, project):
    analysed(qtbot, window, project)
    window.results.documents.setCurrentRow(1)

    window.results.dark.setChecked(True)

    assert window.results.diagram._background == "#0d1117"


def test_recent_projects_are_remembered_without_duplicates(qtbot, window, tmp_path, project):
    folders = [tmp_path / f"p{i}" for i in range(MAX_RECENT + 1)]
    for folder in folders:
        folder.mkdir()
        window._remember(folder)
    window._remember(folders[2])

    recent = window.settings.value("recent", [], list)

    assert recent[0] == str(folders[2])
    assert len(recent) == MAX_RECENT
    assert len(set(recent)) == MAX_RECENT


def test_export_writes_the_zip(qtbot, window, project, tmp_path):
    analysed(qtbot, window, project)
    destination = tmp_path / "out" / "shop-architecture.zip"

    window.export(destination)
    assert not window.results.export.isEnabled()
    with qtbot.waitSignal(window.task.finished, timeout=TIMEOUT):
        pass

    assert window.results.export.isEnabled()
    assert window.export_message is not None and window.export_message.isVisible()
    with zipfile.ZipFile(destination) as archive:
        assert "architecture/README.md" in archive.namelist()


def test_a_failed_analysis_returns_to_the_start(qtbot, window, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr("repo_xray.app.window.QMessageBox.warning", lambda *args: warnings.append(args[2]))

    window.analyse(tmp_path / "missing")
    with qtbot.waitSignal(window.task.failed, timeout=TIMEOUT):
        pass

    assert window.pages.currentWidget() is window.start
    assert "could not analyse" in warnings[0]


def test_page_view_mentions_diagrams_instead_of_raw_html(qtbot):
    view = PageView()
    qtbot.addWidget(view)

    view.show_markdown('# Title\n\n<picture>\n  <img alt="Overview" src="x.svg">\n</picture>\n\n'
                       '<details><summary>2 files</summary>\n\n- a\n</details>\n')

    text = view.toPlainText()
    assert "Diagram: Overview" in text and "<picture>" not in text and "<summary>" not in text


def test_diagram_view_fits_the_width(qtbot):
    view = DiagramView()
    qtbot.addWidget(view)
    view.resize(500, 400)
    view.show()

    view.show_svg('<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="500" viewBox="0 0 1000 500">'
                  '<rect width="1000" height="500" fill="#123456"/></svg>', "#ffffff")

    pixmap = view._label.pixmap()
    ratio = pixmap.devicePixelRatio()
    assert pixmap.width() / ratio <= view.viewport().width()
    assert round(pixmap.width() / pixmap.height()) == 2
    assert view._label.alignment() & Qt.AlignmentFlag.AlignHCenter
