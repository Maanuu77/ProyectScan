"""Build the Windows executable: python packaging/build.py

Produces dist/repo-xray.exe, a single file that opens the desktop app with
no console window (ADR-0010).
"""

import struct
import sys
from pathlib import Path

import PyInstaller.__main__
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

# Qt modules the app never uses; leaving them out makes the executable much smaller.
UNUSED_MODULES = [
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtNetwork",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtPdf", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtConcurrent", "PySide6.QtXml", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtUiTools", "tkinter", "pytest", "pytestqt",
]


def make_icon(svg: Path, destination: Path) -> Path:
    """Write a multi-size .ico (PNG entries, as Windows Vista and later expect) from the SVG icon."""
    app = QApplication.instance() or QApplication([])  # noqa: F841 - Qt needs it to render
    icon = QIcon(str(svg))
    images = []
    for size in ICON_SIZES:
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        icon.pixmap(size, size).toImage().save(buffer, "PNG")
        images.append((size, bytes(buffer.data())))

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, data = b"", b""
    for size, png in images:
        side = 0 if size >= 256 else size  # 0 means 256 in the ICO format
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(header + entries + data)
    return destination


def build() -> None:
    icon = make_icon(ROOT / "repo_xray" / "app" / "icon.svg", BUILD / "icon.ico")
    arguments = [
        str(ROOT / "repo_xray" / "__main__.py"),
        "--name", "repo-xray",
        "--onefile",  # one file to download and double-click
        "--windowed",  # no console window behind the app
        "--icon", str(icon),
        "--add-data", f"{ROOT / 'repo_xray' / 'app' / 'icon.svg'}{';' if sys.platform == 'win32' else ':'}repo_xray/app",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(BUILD / "pyinstaller"),
        "--specpath", str(BUILD),
        "--noconfirm",
        "--clean",
    ]
    for module in UNUSED_MODULES:
        arguments += ["--exclude-module", module]
    PyInstaller.__main__.run(arguments)


if __name__ == "__main__":
    build()
