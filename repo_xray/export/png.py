"""PNG copies of the diagrams, for places that do not show SVG (slides, social posts, Word).

Qt renders them (ADR-0006), so no extra native library such as Cairo is needed.
"""

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from repo_xray.export.markdown import FOLDER, Bundle

SCALE = 2  # sharp on high-density screens


def svg_to_png(svg: str, background: str, scale: float = SCALE) -> bytes:
    _ensure_application()
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("Invalid SVG")
    size = renderer.defaultSize()
    image = QImage(round(size.width() * scale), round(size.height() * scale), QImage.Format.Format_ARGB32)
    image.fill(QColor(background))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    renderer.render(painter)
    painter.end()

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def add_png_copies(bundle: Bundle) -> None:
    """Add `architecture/png/<name>.png` next to every SVG diagram of the bundle."""
    from repo_xray.render.theme import THEMES

    for path, content in list(bundle.items()):
        if not path.startswith(f"{FOLDER}/images/") or not path.endswith(".svg"):
            continue
        name = path.rpartition("/")[2][:-4]
        theme = THEMES["dark" if name.endswith("-dark") else "light"]
        bundle[f"{FOLDER}/png/{name}.png"] = svg_to_png(str(content), theme.background)


def _ensure_application() -> None:
    # Qt needs an application object to load fonts; the desktop app already has one. A full
    # QApplication (not a QGuiApplication) keeps widgets possible later in the same process.
    if QApplication.instance() is None:
        _ensure_application.app = QApplication([])
