"""Start the desktop app."""

import sys
from importlib.resources import as_file, files

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from repo_xray import __version__
from repo_xray.app import style
from repo_xray.app.window import MainWindow


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("repo-xray")
    app.setApplicationVersion(__version__)
    with as_file(files("repo_xray.app") / "icon.svg") as icon:
        app.setWindowIcon(QIcon(str(icon)))
    theme = style.apply(app)
    window = MainWindow(theme)
    window.show()
    return app.exec()
