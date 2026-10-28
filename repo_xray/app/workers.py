"""Long tasks that run on a background thread so the window never freezes."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from repo_xray.export.archive import build_bundle, write_zip
from repo_xray.export.markdown import Bundle, build_documents
from repo_xray.pipeline import Analysis, analyse

Work = Callable[[Callable[[str, float], None]], object]


class _Runner(QObject):
    """Lives on the background thread and does the work there."""

    progress = Signal(str, float)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, work: Work):
        super().__init__()
        self._work = work

    def run(self) -> None:
        try:
            result = self._work(lambda message, fraction: self.progress.emit(message, fraction))
        except Exception as exc:  # shown to the user instead of crashing the app
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.finished.emit(result)


class Task(QObject):
    """Runs `work(report)` in the background and reports on the thread that created the task.

    The task itself stays on the window's thread, so anything connected to its
    signals, lambdas included, may safely update widgets.
    """

    progress = Signal(str, float)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, work: Work):
        super().__init__()
        self._thread = QThread()
        self._runner = _Runner(work)
        self._runner.moveToThread(self._thread)
        self._thread.started.connect(self._runner.run)
        # Signal-to-signal connections to an object on this thread are queued into it.
        self._runner.progress.connect(self.progress)
        self._runner.finished.connect(self.finished)
        self._runner.failed.connect(self.failed)
        self._runner.finished.connect(self._thread.quit)
        self._runner.failed.connect(self._thread.quit)

    def start(self) -> None:
        self._thread.start()

    def wait(self) -> None:
        self._thread.wait()


def analysis_task(folder: Path) -> Task:
    """Analyse `folder` and render its documents; finishes with (Analysis, Bundle)."""

    def work(report) -> tuple[Analysis, Bundle]:
        analysis = analyse(folder, lambda message, fraction: report(message, fraction * 0.9))
        report("Drawing the diagrams", 0.92)
        documents = build_documents(analysis)
        report("Done", 1.0)
        return analysis, documents

    return Task(work)


def export_task(analysis: Analysis, destination: Path) -> Task:
    """Write the zip with PNG copies; finishes with the path written."""

    def work(report) -> Path:
        report("Rendering PNG copies", 0.2)
        bundle = build_bundle(analysis)
        report("Writing the zip", 0.8)
        return write_zip(bundle, destination)

    return Task(work)
