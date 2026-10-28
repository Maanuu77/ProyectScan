"""Start the desktop app."""

import sys

from PySide6.QtWidgets import QApplication

from repo_xray import __version__
from repo_xray.app import style
from repo_xray.app.window import MainWindow


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("repo-xray")
    app.setApplicationVersion(__version__)
    theme = style.apply(app)
    window = MainWindow(theme)
    window.show()
    return app.exec()
