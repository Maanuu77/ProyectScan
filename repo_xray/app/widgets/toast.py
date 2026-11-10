"""Toasts: short messages that appear over the window and leave on their own.

They replace the message boxes of 1.0: an export that finished or a text
that was saved does not need the reader to stop and press OK. A toast may
offer one action ("Show in folder"), and a problem stays until dismissed.
"""

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

from repo_xray.app.theme import Themes
from repo_xray.app.widgets.common import Button, IconButton, IconLabel, label

TONES = {"success": ("success", "success"), "info": ("info", "text_muted"), "warning": ("warning", "warning"),
         "error": ("error", "danger")}  # tone -> (icon, colour)
TIMEOUT = 6500
MARGIN = 20
WIDTH = 380


class Toast(QFrame):
    def __init__(self, parent: QWidget, themes: Themes, message: str, tone: str = "info",
                 action: tuple[str, Callable[[], None]] | None = None):
        super().__init__(parent)
        self.setProperty("role", "toast")
        self.message = message
        self.tone = tone
        icon, colour = TONES.get(tone, TONES["info"])
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 8, 10)
        layout.setSpacing(10)
        layout.addWidget(IconLabel(icon, themes, 18, colour))
        text = label(message, wrap=True)
        layout.addWidget(text, 1)
        self.action: Button | None = None
        if action is not None:
            self.action = Button(action[0], themes, variant="link")
            self.action.clicked.connect(action[1])
            self.action.clicked.connect(self.dismiss)
            layout.addWidget(self.action)
        self.close_button = IconButton("close", themes, "Dismiss", size=14)
        self.close_button.clicked.connect(self.dismiss)
        layout.addWidget(self.close_button)
        self.setFixedWidth(WIDTH)

    def dismiss(self) -> None:
        self.hide()
        self.deleteLater()


class Toasts(QObject):
    """Shows toasts in the bottom-right corner of a host widget, the newest at the bottom."""

    def __init__(self, host: QWidget, themes: Themes):
        super().__init__(host)
        self._host = host
        self._themes = themes
        self._toasts: list[Toast] = []
        host.installEventFilter(self)

    def show(self, message: str, tone: str = "info", action: tuple[str, Callable[[], None]] | None = None,
             timeout: int | None = None) -> Toast:
        toast = Toast(self._host, self._themes, message, tone, action)
        toast.destroyed.connect(lambda _=None, t=toast: self._forget(t))
        self._toasts.append(toast)
        toast.adjustSize()
        toast.show()
        toast.raise_()
        self._place()
        stay = timeout if timeout is not None else (0 if tone == "error" else TIMEOUT)
        if stay:
            QTimer.singleShot(stay, toast, toast.dismiss)  # the toast as context: no call once it is gone
        return toast

    def current(self) -> list[Toast]:
        """The toasts that have not been dismissed, oldest first."""
        return [toast for toast in self._toasts if not toast.isHidden()]

    def clear(self) -> None:
        for toast in list(self._toasts):
            toast.dismiss()

    def _forget(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._place()

    def _place(self) -> None:
        try:
            y = self._host.height() - MARGIN
            right = self._host.width() - MARGIN
        except RuntimeError:  # the window is closing: its toasts go with it
            return
        for toast in reversed(self._toasts):
            try:
                if toast.isHidden():
                    continue
                height = max(toast.layout().totalHeightForWidth(WIDTH), toast.sizeHint().height())
                toast.setGeometry(right - WIDTH, y - height, WIDTH, height)
                y -= height + 10
            except RuntimeError:  # already deleted by Qt
                continue

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._host and event.type() == QEvent.Type.Resize:
            self._place()
        return False
