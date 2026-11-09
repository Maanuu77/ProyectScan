"""Long tasks that run on a background thread so the window never freezes."""

import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from repo_xray.export.archive import build_bundle, write_zip
from repo_xray.export.markdown import Bundle, build_documents
from repo_xray.parsers.cache import ParseCache
from repo_xray.pipeline import STAGES, Analysis, Cancelled, Progress, analyse

# The stages the analysis screen lists: the pipeline's own, then drawing the diagrams.
ANALYSIS_STAGES: dict[str, str] = {**STAGES, "render": "Drawing the diagrams"}


class Job:
    """What background work is given: a way to report progress and to learn that it should stop."""

    def __init__(self, report: Callable[[object], None], stop: threading.Event):
        self.report = report
        self._stop = stop

    def cancelled(self) -> bool:
        return self._stop.is_set()

    def check(self) -> None:
        """Stop here if the user cancelled."""
        if self._stop.is_set():
            raise Cancelled()


Work = Callable[[Job], object]


class _Runner(QObject):
    """Lives on the background thread and does the work there."""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, work: Work, stop: threading.Event):
        super().__init__()
        self._work = work
        self._stop = stop

    def run(self) -> None:
        try:
            result = self._work(Job(self.progress.emit, self._stop))
        except Cancelled:
            self.cancelled.emit()
        except Exception as exc:  # shown to the user instead of crashing the app
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.finished.emit(result)


class Task(QObject):
    """Runs `work(job)` in the background and reports on the thread that created the task.

    The task itself stays on the window's thread, so anything connected to its
    signals, lambdas included, may safely update widgets. Exactly one of
    `finished`, `failed` or `cancelled` is emitted, once.
    """

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, work: Work):
        super().__init__()
        self._stop = threading.Event()
        self._thread = QThread()
        self._runner = _Runner(work, self._stop)
        self._runner.moveToThread(self._thread)
        self._thread.started.connect(self._runner.run)
        # Signal-to-signal connections to an object on this thread are queued into it.
        self._runner.progress.connect(self.progress)
        for signal, relay in ((self._runner.finished, self.finished), (self._runner.failed, self.failed),
                              (self._runner.cancelled, self.cancelled)):
            signal.connect(relay)
            signal.connect(self._thread.quit)
        self._thread.finished.connect(self._release)

    def start(self) -> None:
        # Keep the task, and so its QThread, alive until the thread has really stopped: Qt aborts the
        # whole process if a running QThread is destroyed, e.g. when the window replaces its task
        # right after `finished`, while the thread is still winding down.
        _RUNNING.add(self)
        self._thread.start()

    def cancel(self) -> None:
        """Ask the work to stop; it does so at its next checkpoint and `cancelled` is emitted."""
        self._stop.set()

    def is_cancelling(self) -> bool:
        return self._stop.is_set()

    def wait(self) -> None:
        self._thread.wait()

    def _release(self) -> None:
        self._thread.wait()  # the thread has left its event loop; this returns at once
        _RUNNING.discard(self)


_RUNNING: set[Task] = set()


def analysis_task(folder: Path, cache: ParseCache | None = None) -> Task:
    """Analyse `folder` and render its documents; finishes with (Analysis, Bundle).

    With a `cache`, a later analysis of the same folder only reads the files that changed.
    """

    def work(job: Job) -> tuple[Analysis, Bundle]:
        analysis = analyse(folder, job.report, job.cancelled, cache)
        job.check()
        job.report(Progress("render"))
        documents = build_documents(analysis)
        job.check()
        return analysis, documents

    return Task(work)


def export_task(analysis: Analysis, destination: Path) -> Task:
    """Write the zip with PNG copies; finishes with the path written."""

    def work(job: Job) -> Path:
        bundle = build_bundle(analysis)
        job.check()
        return write_zip(bundle, destination)

    return Task(work)
