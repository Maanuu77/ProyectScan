"""PNG copies of the diagrams, for places that do not show SVG (slides, social posts, Word).

Qt renders them (ADR-0006), so no extra native library such as Cairo is needed.
"""

import html
import re
from functools import lru_cache

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QColor, QFontDatabase, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from repo_xray.export.markdown import FOLDER, Bundle

SCALE = 2  # sharp on high-density screens
_FONT_FAMILY = re.compile(r'font-family="([^"]*)"')


def svg_to_png(svg: str, background: str, scale: float = SCALE) -> bytes:
    renderer = renderer_for(svg)
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


def renderer_for(svg: str) -> QSvgRenderer:
    """A Qt renderer that draws `svg` with the fonts a browser would pick. Raises ValueError if it is not SVG."""
    ensure_application()
    renderer = QSvgRenderer(QByteArray(for_qt(svg).encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("Invalid SVG")
    return renderer


def for_qt(svg: str) -> str:
    """The same SVG with each list of font families replaced by the first one installed here.

    A browser walks `font-family="-apple-system, 'Segoe UI', Helvetica…"` until it finds a font.
    Qt's SVG renderer does not, and falls back to its default font, so the preview and the PNG
    copies would not look like the diagram on GitHub.
    """
    return _FONT_FAMILY.sub(lambda match: f'font-family="{_first_installed(match.group(1))}"', svg)


@lru_cache(maxsize=16)
def _first_installed(families: str) -> str:
    installed = _installed_families()
    names = [name.strip().strip("'\"") for name in html.unescape(families).split(",")]
    for name in names:
        if name in installed:
            return name
    if "monospace" in names:
        return _fixed_family()
    return families  # nothing known: leave the list, Qt will use its default


def _installed_families() -> set[str]:
    return set(QFontDatabase.families())


def _fixed_family() -> str:
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


def add_png_copies(bundle: Bundle) -> None:
    """Add `architecture/png/<name>.png` next to every SVG diagram of the bundle."""
    from repo_xray.render.theme import THEMES

    for path, content in list(bundle.items()):
        if not path.startswith(f"{FOLDER}/images/") or not path.endswith(".svg"):
            continue
        name = path.rpartition("/")[2][:-4]
        theme = THEMES["dark" if name.endswith("-dark") else "light"]
        bundle[f"{FOLDER}/png/{name}.png"] = svg_to_png(str(content), theme.background)


def ensure_application() -> None:
    # Qt needs an application object to load fonts; the desktop app already has one. A full
    # QApplication (not a QGuiApplication) keeps widgets possible later in the same process.
    if QApplication.instance() is None:
        ensure_application.app = QApplication([])
