"""The analysis page: what is being done right now, and what went wrong when it does.

Progress is shown as facts. Each stage is pending, running or done; the
one stage that can be counted (reading files) shows how many of how many,
with a bar. Nothing here is an estimate.
"""

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QProgressBar, QSizePolicy, QStackedLayout, QVBoxLayout, QWidget

from repo_xray.app.theme import Themes
from repo_xray.app.widgets.common import Button, ElidedLabel, IconLabel, IconTile, Spinner, label
from repo_xray.app.workers import ANALYSIS_STAGES
from repo_xray.pipeline import Progress

PENDING, RUNNING, DONE = "pending", "running", "done"
CARD = 560


class StageRow(QWidget):
    """One stage of the analysis: a mark for its state, its name and, when it counts, how far it is."""

    def __init__(self, key: str, text: str, themes: Themes):
        super().__init__()
        self.key = key
        self.state = PENDING
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(10)
        self._mark = QStackedLayout()
        self._icon = IconLabel("ring", themes, 16, "text_subtle")
        self._spinner = Spinner(themes, 16)
        holder = QWidget()
        holder.setFixedSize(16, 16)
        holder.setLayout(self._mark)
        self._mark.addWidget(self._icon)
        self._mark.addWidget(self._spinner)
        layout.addWidget(holder)
        self.text = label(text, "muted")
        layout.addWidget(self.text)
        layout.addStretch()
        self.count = label("", "subtle")
        layout.addWidget(self.count)

    def set_state(self, state: str, count: str = "") -> None:
        self.state = state
        self._mark.setCurrentWidget(self._spinner if state == RUNNING else self._icon)
        if state == DONE:
            self._icon.set_icon("check", "success")
        elif state == PENDING:
            self._icon.set_icon("ring", "text_subtle")
        self.text.setProperty("role", "muted" if state == PENDING else None)
        self.text.style().unpolish(self.text)
        self.text.style().polish(self.text)
        self.count.setText(count)


class AnalysisPage(QWidget):
    cancel_requested = Signal()
    retry_requested = Signal()
    choose_requested = Signal()
    back_requested = Signal()

    def __init__(self, themes: Themes):
        super().__init__()
        self._themes = themes
        self._started = 0.0
        self.setObjectName("canvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.addStretch(1)
        column = QVBoxLayout()
        column.addStretch(2)
        self.card = QFrame()
        self.card.setProperty("role", "panel")
        self.card.setMaximumWidth(CARD)
        self.card.setMinimumWidth(360)
        self.card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        column.addWidget(self.card)
        column.addStretch(3)
        outer.addLayout(column, 100)
        outer.addStretch(1)

        self.stack = QStackedLayout(self.card)
        self.stack.addWidget(self._running_view())
        self.stack.addWidget(self._problem_view())

        self._clock = QTimer(self)
        self._clock.setInterval(200)
        self._clock.timeout.connect(self._tick)

    # Views

    def _running_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(0)
        self.heading = ElidedLabel("", "title")
        layout.addWidget(self.heading)
        self.path = ElidedLabel("", "subtle", Qt.TextElideMode.ElideMiddle)
        layout.addWidget(self.path)
        layout.addSpacing(18)

        self.rows: dict[str, StageRow] = {}
        for key, text in ANALYSIS_STAGES.items():
            row = StageRow(key, text, self._themes)
            self.rows[key] = row
            layout.addWidget(row)
            if key == "parse":  # the one stage with something to count: its bar and the file being read
                self.bar = QProgressBar()
                self.bar.setTextVisible(False)
                self.bar.setRange(0, 1)
                self.detail = ElidedLabel("", "mono", Qt.TextElideMode.ElideMiddle)
                box = QVBoxLayout()
                box.setContentsMargins(26, 2, 0, 6)
                box.setSpacing(4)
                box.addWidget(self.bar)
                box.addWidget(self.detail)
                layout.addLayout(box)
        layout.addSpacing(16)
        footer = QHBoxLayout()
        self.elapsed = label("", "subtle")
        footer.addWidget(self.elapsed)
        footer.addStretch()
        self.cancel = Button("Cancel", self._themes, "stop", tooltip="Stop the analysis  (Esc)")
        self.cancel.clicked.connect(self._cancel)
        footer.addWidget(self.cancel)
        layout.addLayout(footer)
        return view

    def _problem_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(26, 26, 26, 22)
        layout.setSpacing(0)
        self.problem_icon = IconTile("error", self._themes, 40, "danger", "danger_soft")
        layout.addWidget(self.problem_icon)
        layout.addSpacing(14)
        self.problem_title = label("", "title", wrap=True)
        layout.addWidget(self.problem_title)
        layout.addSpacing(6)
        self.problem_text = label("", "muted", wrap=True, selectable=True)
        layout.addWidget(self.problem_text)
        layout.addSpacing(8)
        self.problem_detail = label("", "mono", wrap=True, selectable=True)
        layout.addWidget(self.problem_detail)
        layout.addSpacing(20)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.choose = Button("Choose another folder…", self._themes, "folder", "primary")
        self.choose.clicked.connect(self.choose_requested)
        self.retry = Button("Try again", self._themes, "refresh")
        self.retry.clicked.connect(self.retry_requested)
        self.back = Button("Back to start", self._themes, variant="ghost")
        self.back.clicked.connect(self.back_requested)
        buttons.addWidget(self.choose)
        buttons.addWidget(self.retry)
        buttons.addStretch()
        buttons.addWidget(self.back)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return view

    # Running

    def start(self, folder: Path) -> None:
        self.heading.setText(f"Analysing {folder.name}")
        self.path.setText(str(folder))
        for row in self.rows.values():
            row.set_state(PENDING)
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.detail.setText("")
        self.cancel.setEnabled(True)
        self.cancel.setText("Cancel")
        self._started = time.perf_counter()
        self._tick()
        self._clock.start()
        self.stack.setCurrentIndex(0)

    def show_progress(self, progress: Progress) -> None:
        """Mark the stage that is running; the stages before it are done."""
        if progress.stage not in self.rows:
            return
        keys = list(self.rows)
        current = keys.index(progress.stage)
        for index, key in enumerate(keys):
            row = self.rows[key]
            if index < current:
                if row.state != DONE:
                    row.set_state(DONE, row.count.text())
            elif index == current:
                counted = f"{progress.done:,} of {progress.total:,} files" if progress.total else ""
                row.set_state(RUNNING, counted)
        if progress.stage == "parse" and progress.total:
            self.bar.setRange(0, progress.total)
            self.bar.setValue(progress.done)
            self.detail.setText(progress.detail)
        elif current > keys.index("parse"):
            self.bar.setValue(self.bar.maximum())
            self.detail.setText("")

    def stage_states(self) -> dict[str, str]:
        return {key: row.state for key, row in self.rows.items()}

    def is_running(self) -> bool:
        return self.stack.currentIndex() == 0 and self._clock.isActive()

    def stop(self) -> None:
        """The analysis ended, one way or another: stop the clock and the spinners."""
        self._clock.stop()

    def _cancel(self) -> None:
        self.cancel.setEnabled(False)
        self.cancel.setText("Stopping…")
        self.cancel_requested.emit()

    def _tick(self) -> None:
        self.elapsed.setText(f"{time.perf_counter() - self._started:.1f} s")

    # Problems

    def show_problem(self, title: str, text: str, detail: str = "", can_retry: bool = True,
                     tone: str = "danger") -> None:
        """Say what went wrong, in place, with what the user can do about it."""
        self.stop()
        icon = "error" if tone == "danger" else "search"
        self.problem_icon.set_icon(icon, tone if tone == "danger" else "text_muted",
                                   "danger_soft" if tone == "danger" else "active")
        self.problem_title.setText(title)
        self.problem_text.setText(text)
        self.problem_detail.setText(detail)
        self.problem_detail.setVisible(bool(detail))
        self.retry.setVisible(can_retry)
        self.stack.setCurrentIndex(1)

    def problem(self) -> tuple[str, str] | None:
        """(title, text) of the problem on show, or None while the analysis runs."""
        if self.stack.currentIndex() != 1:
            return None
        return self.problem_title.text(), self.problem_text.text()
